"""
Expert Consultation Module
Connects users with medical professionals and experts
"""

import json
from typing import Optional, Dict, Any, List
from datetime import datetime
from pathlib import Path


class ExpertConsultationManager:
    """
    Manages connections between users and medical experts
    Handles scheduling, messaging, and consultation tracking
    """
    
    def __init__(self):
        self.consultations_dir = Path("memory") / "consultations"
        self.consultations_dir.mkdir(parents=True, exist_ok=True)
        self.experts_file = self.consultations_dir / "experts.json"
        self._init_experts()
    
    def _init_experts(self):
        """Initialize expert database"""
        if not self.experts_file.exists():
            with open(self.experts_file, "w") as f:
                json.dump({
                    "doctors": [
                        {
                            "id": "dr_001",
                            "name": "Dr. Rajesh Kumar",
                            "specialization": "General Medicine",
                            "available": True,
                            "response_time": "15-30 minutes",
                            "rating": 4.8,
                        },
                        {
                            "id": "dr_002",
                            "name": "Dr. Priya Singh",
                            "specialization": "Cardiology",
                            "available": True,
                            "response_time": "30-60 minutes",
                            "rating": 4.9,
                        },
                        {
                            "id": "dr_003",
                            "name": "Dr. Amit Patel",
                            "specialization": "Neurology",
                            "available": False,
                            "response_time": "1-2 hours",
                            "rating": 4.7,
                        },
                    ],
                    "nutritionists": [
                        {
                            "id": "nut_001",
                            "name": "Ms. Sneha Verma",
                            "specialization": "Diabetic Diet Planning",
                            "available": True,
                            "response_time": "1 hour",
                            "rating": 4.6,
                        },
                    ],
                }, f, indent=2)
    
    def get_available_experts(self, category: str = "all") -> List[Dict[str, Any]]:
        """Get list of available experts"""
        with open(self.experts_file, "r") as f:
            experts_data = json.load(f)
        
        experts = []
        
        if category == "all":
            for expert_list in experts_data.values():
                experts.extend([e for e in expert_list if e.get("available", False)])
        else:
            expert_list = experts_data.get(category, [])
            experts = [e for e in expert_list if e.get("available", False)]
        
        return experts
    
    def request_consultation(self, username: str, expert_id: str, 
                            question: str, category: str,
                            preferred_language: str = "en") -> Dict[str, Any]:
        """
        Request a consultation with an expert
        
        Args:
            username: User ID
            expert_id: Expert ID
            question: Consultation question
            category: Category (general, medication, lab_report, symptoms)
            preferred_language: Preferred language for consultation
        
        Returns:
            Consultation request with status
        """
        consultation = {
            "id": f"{datetime.now().isoformat()}_{username}_{expert_id}",
            "username": username,
            "expert_id": expert_id,
            "question": question,
            "category": category,
            "language": preferred_language,
            "status": "pending",
            "created_at": datetime.now().isoformat(),
            "estimated_response_time": "15-30 minutes",
            "messages": [],
        }
        
        # Save consultation
        user_consultations_file = self.consultations_dir / f"{username}_consultations.json"
        consultations = []
        
        if user_consultations_file.exists():
            with open(user_consultations_file, "r") as f:
                consultations = json.load(f)
        
        consultations.append(consultation)
        
        with open(user_consultations_file, "w") as f:
            json.dump(consultations, f, indent=2)
        
        return consultation
    
    def get_consultations(self, username: str) -> List[Dict[str, Any]]:
        """Get all consultations for a user"""
        user_consultations_file = self.consultations_dir / f"{username}_consultations.json"
        
        if not user_consultations_file.exists():
            return []
        
        with open(user_consultations_file, "r") as f:
            consultations = json.load(f)
        
        return consultations
    
    def add_message_to_consultation(self, username: str, consultation_id: str, 
                                   sender: str, message: str) -> bool:
        """Add a message to a consultation"""
        user_consultations_file = self.consultations_dir / f"{username}_consultations.json"
        
        if not user_consultations_file.exists():
            return False
        
        with open(user_consultations_file, "r") as f:
            consultations = json.load(f)
        
        for consultation in consultations:
            if consultation["id"] == consultation_id:
                consultation["messages"].append({
                    "sender": sender,  # "user" or "expert"
                    "message": message,
                    "timestamp": datetime.now().isoformat(),
                })
                
                # Update status if expert responds
                if sender == "expert" and consultation["status"] == "pending":
                    consultation["status"] = "in_progress"
                
                break
        
        with open(user_consultations_file, "w") as f:
            json.dump(consultations, f, indent=2)
        
        return True
    
    def close_consultation(self, username: str, consultation_id: str, 
                          rating: Optional[int] = None, feedback: Optional[str] = None) -> bool:
        """Close a consultation"""
        user_consultations_file = self.consultations_dir / f"{username}_consultations.json"
        
        if not user_consultations_file.exists():
            return False
        
        with open(user_consultations_file, "r") as f:
            consultations = json.load(f)
        
        for consultation in consultations:
            if consultation["id"] == consultation_id:
                consultation["status"] = "closed"
                consultation["closed_at"] = datetime.now().isoformat()
                if rating:
                    consultation["rating"] = rating
                if feedback:
                    consultation["feedback"] = feedback
                break
        
        with open(user_consultations_file, "w") as f:
            json.dump(consultations, f, indent=2)
        
        return True
    
    def get_expert_profile(self, expert_id: str) -> Optional[Dict[str, Any]]:
        """Get expert's profile"""
        with open(self.experts_file, "r") as f:
            experts_data = json.load(f)
        
        for expert_list in experts_data.values():
            for expert in expert_list:
                if expert["id"] == expert_id:
                    return expert
        
        return None
    
    def schedule_appointment(self, username: str, expert_id: str, 
                            appointment_date: str, appointment_time: str,
                            reason: str) -> Dict[str, Any]:
        """Schedule an appointment with an expert"""
        appointment = {
            "id": f"appt_{datetime.now().isoformat()}",
            "username": username,
            "expert_id": expert_id,
            "date": appointment_date,
            "time": appointment_time,
            "reason": reason,
            "status": "scheduled",
            "created_at": datetime.now().isoformat(),
            "meeting_link": "https://meet.example.com/consultation123",  # Placeholder
        }
        
        # Save appointment
        appointments_file = self.consultations_dir / "appointments.json"
        appointments = []
        
        if appointments_file.exists():
            with open(appointments_file, "r") as f:
                appointments = json.load(f)
        
        appointments.append(appointment)
        
        with open(appointments_file, "w") as f:
            json.dump(appointments, f, indent=2)
        
        return appointment


# Global expert consultation manager instance
expert_manager = ExpertConsultationManager()
