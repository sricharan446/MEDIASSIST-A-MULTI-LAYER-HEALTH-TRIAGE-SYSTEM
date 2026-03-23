"""
Security & Privacy Module
Handles encryption, audit logging, and data protection
"""

import json
import hashlib
import hmac
import base64
from typing import Any, Dict, Optional, List
from datetime import datetime
from pathlib import Path
from cryptography.fernet import Fernet
import os


class SecurityManager:
    """
    Handles data encryption, audit logging, and access control
    """

    def __init__(self):
        self.audit_log_dir = Path("memory") / "audit_logs"
        self.audit_log_dir.mkdir(parents=True, exist_ok=True)

        # Initialize cipher for sensitive data (use env-based key in production)
        self.encryption_key = os.getenv("ENCRYPTION_KEY", "").encode() or Fernet.generate_key()
        if isinstance(self.encryption_key, str):
            # Hash a provided key to proper Fernet key format
            self.encryption_key = base64.urlsafe_b64encode(hashlib.sha256(self.encryption_key).digest())
        self.cipher = Fernet(self.encryption_key)

    def encrypt_data(self, data: str) -> str:
        """Encrypt sensitive string data"""
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive string data"""
        try:
            return self.cipher.decrypt(encrypted_data.encode()).decode()
        except Exception:
            return ""

    def hash_password(self, password: str, salt: Optional[str] = None) -> tuple:
        """
        Hash password with salt
        Returns: (hashed_password, salt)
        """
        if salt is None:
            salt = os.urandom(32).hex()

        hashed = hashlib.pbkdf2_hmac(
            'sha256',
            password.encode(),
            salt.encode(),
            100000
        )

        return hashed.hex(), salt

    def verify_password(self, password: str, hashed: str, salt: str) -> bool:
        """Verify password against hash"""
        new_hash, _ = self.hash_password(password, salt)
        return hmac.compare_digest(new_hash, hashed)

    def log_audit_event(self, username: str, action: str, resource: str,
                       status: str = "success", details: Optional[Dict] = None):
        """
        Log an audit event for compliance and security monitoring
        """
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "username": username,
            "action": action,
            "resource": resource,
            "status": status,
            "details": details or {},
            "ip_address": "unknown",
            "user_agent": "unknown",
        }

        user_audit_file = self.audit_log_dir / f"{username}_audit.json"
        audit_entries = []

        if user_audit_file.exists():
            with open(user_audit_file, "r") as f:
                audit_entries = json.load(f)

        audit_entries.append(audit_entry)

        if len(audit_entries) > 500:
            audit_entries = audit_entries[-500:]

        with open(user_audit_file, "w") as f:
            json.dump(audit_entries, f, indent=2)

    def get_audit_log(self, username: str, limit: int = 50) -> List[Dict]:
        """Get user's audit log"""
        user_audit_file = self.audit_log_dir / f"{username}_audit.json"

        if not user_audit_file.exists():
            return []

        with open(user_audit_file, "r") as f:
            entries = json.load(f)

        return entries[-limit:] if limit is not None else entries

    def export_user_data(self, username: str) -> Dict[str, Any]:
        """
        Export all user data for GDPR compliance
        """
        exported_data = {
            "export_date": datetime.now().isoformat(),
            "username": username,
            "profile": {},
            "sessions": [],
            "analytics": {},
            "audit_log": [],
        }

        profile_file = Path("memory") / username / "profile.json"
        if profile_file.exists():
            with open(profile_file, "r") as f:
                exported_data["profile"] = json.load(f)

        analytics_file = Path("memory") / username / "analytics.json"
        if analytics_file.exists():
            with open(analytics_file, "r") as f:
                exported_data["analytics"] = json.load(f)

        exported_data["audit_log"] = self.get_audit_log(username, limit=None)

        return exported_data

    def delete_user_data(self, username: str) -> bool:
        """
        Delete all user data (GDPR right to be forgotten)
        """
        try:
            user_dir = Path("memory") / username
            if user_dir.exists():
                import shutil
                shutil.rmtree(user_dir)

            audit_file = Path("memory") / "audit_logs" / f"{username}_audit.json"
            if audit_file.exists():
                audit_file.unlink()

            self.log_audit_event(
                "admin",
                "DELETE_USER_DATA",
                username,
                status="success",
                details={"reason": "User requested data deletion"}
            )

            return True
        except Exception:
            return False

    def set_role(self, username: str, role: str):
        """Set user role for role-based access control"""
        roles_file = self.audit_log_dir / "user_roles.json"
        roles = {}

        if roles_file.exists():
            with open(roles_file, "r") as f:
                roles = json.load(f)

        roles[username] = {
            "role": role,
            "assigned_at": datetime.now().isoformat(),
        }

        with open(roles_file, "w") as f:
            json.dump(roles, f, indent=2)

    def get_role(self, username: str) -> str:
        """Get user's role"""
        roles_file = self.audit_log_dir / "user_roles.json"

        if not roles_file.exists():
            return "user"

        with open(roles_file, "r") as f:
            roles = json.load(f)

        return roles.get(username, {}).get("role", "user")

    def check_permission(self, username: str, action: str) -> bool:
        """Check if user has permission for action"""
        role = self.get_role(username)

        permissions = {
            "admin": ["read", "write", "delete", "manage_users", "view_audit_logs"],
            "doctor": ["read", "write", "view_patient_data"],
            "user": ["read", "write"],
        }

        return action in permissions.get(role, [])


security_manager = SecurityManager()
