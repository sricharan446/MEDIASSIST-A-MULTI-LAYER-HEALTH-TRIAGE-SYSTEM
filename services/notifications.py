"""
Notification System Module
Handles email, SMS, and in-app notifications
"""

import json
from typing import Any, Dict, List, Optional
from datetime import datetime
from pathlib import Path


class NotificationManager:
    """
    Manages notifications for users
    Supports email, SMS, medication reminders, follow-up reminders, and emergency alerts
    """
    
    def __init__(self):
        self.notifications_dir = Path("memory") / "notifications"
        self.notifications_dir.mkdir(parents=True, exist_ok=True)
    
    def send_notification(self, username: str, message: str, notification_type: str = "general", 
                         priority: str = "normal", channels: List[str] = None) -> Dict[str, Any]:
        """
        Send a notification to a user
        
        Args:
            username: User identifier
            message: Notification message
            notification_type: Type of notification (general, reminder, alert, urgent)
            priority: Priority level (low, normal, high, urgent)
            channels: List of channels to use (email, sms, in-app)
        
        Returns:
            Notification record with status
        """
        if channels is None:
            channels = ["in-app"]
        
        notification = {
            "id": f"{datetime.now().isoformat()}_{username}",
            "username": username,
            "message": message,
            "type": notification_type,
            "priority": priority,
            "channels": channels,
            "timestamp": datetime.now().isoformat(),
            "status": "sent",
            "read": False,
        }
        
        # Save notification to user's notification log
        user_notif_file = self.notifications_dir / f"{username}_notifications.json"
        notifications = []
        
        if user_notif_file.exists():
            with open(user_notif_file, "r") as f:
                notifications = json.load(f)
        
        notifications.append(notification)
        
        # Keep only last 100 notifications
        if len(notifications) > 100:
            notifications = notifications[-100:]
        
        with open(user_notif_file, "w") as f:
            json.dump(notifications, f, indent=2)
        
        # Simulate sending via channels
        if "email" in channels:
            self._send_email_notification(username, message, priority)
        
        if "sms" in channels:
            self._send_sms_notification(username, message, priority)
        
        return notification
    
    def send_medication_reminder(self, username: str, medication: str, dosage: str, 
                                time: str, channels: List[str] = None) -> Dict[str, Any]:
        """Send medication reminder"""
        message = f"Reminder: Take {medication} ({dosage}) at {time}"
        return self.send_notification(
            username,
            message,
            notification_type="medication_reminder",
            priority="high",
            channels=channels or ["in-app"]
        )
    
    def send_follow_up_reminder(self, username: str, condition: str, days_since: int,
                               channels: List[str] = None) -> Dict[str, Any]:
        """Send follow-up reminder"""
        message = f"Follow-up reminder: It's been {days_since} days since your last check-in for {condition}. How are you feeling?"
        return self.send_notification(
            username,
            message,
            notification_type="follow_up",
            priority="normal",
            channels=channels or ["in-app"]
        )
    
    def send_emergency_alert(self, username: str, alert_message: str, 
                            emergency_contact: Optional[str] = None) -> Dict[str, Any]:
        """Send emergency alert"""
        notification = self.send_notification(
            username,
            alert_message,
            notification_type="emergency",
            priority="urgent",
            channels=["email", "sms", "in-app"] if emergency_contact else ["in-app"]
        )
        
        # Log emergency alert
        with open(self.notifications_dir / "emergency_alerts.json", "a") as f:
            f.write(json.dumps(notification) + "\n")
        
        return notification
    
    def get_user_notifications(self, username: str, unread_only: bool = False) -> List[Dict[str, Any]]:
        """Get user's notifications"""
        user_notif_file = self.notifications_dir / f"{username}_notifications.json"
        
        if not user_notif_file.exists():
            return []
        
        with open(user_notif_file, "r") as f:
            notifications = json.load(f)
        
        if unread_only:
            notifications = [n for n in notifications if not n.get("read", False)]
        
        return notifications
    
    def mark_notification_as_read(self, username: str, notification_id: str) -> bool:
        """Mark a notification as read"""
        user_notif_file = self.notifications_dir / f"{username}_notifications.json"
        
        if not user_notif_file.exists():
            return False
        
        with open(user_notif_file, "r") as f:
            notifications = json.load(f)
        
        for notif in notifications:
            if notif["id"] == notification_id:
                notif["read"] = True
                break
        
        with open(user_notif_file, "w") as f:
            json.dump(notifications, f, indent=2)
        
        return True
    
    def _send_email_notification(self, username: str, message: str, priority: str):
        """
        Simulate email sending
        In production, integrate with real email service (SendGrid, AWS SES, etc.)
        """
        # Placeholder for email service integration
        pass
    
    def _send_sms_notification(self, username: str, message: str, priority: str):
        """
        Simulate SMS sending
        In production, integrate with real SMS service (Twilio, AWS SNS, etc.)
        """
        # Placeholder for SMS service integration
        pass


# Global notification manager instance
notification_manager = NotificationManager()
