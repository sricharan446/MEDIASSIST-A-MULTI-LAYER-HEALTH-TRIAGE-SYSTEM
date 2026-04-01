from typing import Any, Dict, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field


class SignupRequest(BaseModel):
    username: str
    password: str


class LoginRequest(BaseModel):
    username: str
    password: str
    age: Optional[int] = None
    gender: Optional[str] = None
    city: Optional[str] = None
    known_conditions: List[str] = Field(default_factory=list)
    allergies: List[str] = Field(default_factory=list)
    current_medications: List[str] = Field(default_factory=list)
    pregnancy_status: Optional[str] = None
    smoking_status: Optional[str] = None
    alcohol_use: Optional[str] = None
    past_history: List[str] = Field(default_factory=list)
    # Enhanced profile fields
    family_history: List[str] = Field(default_factory=list)
    lifestyle_activities: List[str] = Field(default_factory=list)
    dietary_preferences: List[str] = Field(default_factory=list)
    emergency_contact: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None
    language: str = "en"


class ChatRequest(BaseModel):
    message: str = ""
    session_id: Optional[str] = None
    token: str
    model: Optional[str] = None
    current_city: Optional[str] = None


class ChatResponse(BaseModel):
    response: str
    session_id: str
    tools_used: List[str] = Field(default_factory=list)
    timestamp: str
    show_hospital_finder: bool = False
    practo_url: str = ""
    needs_followup: bool = False
    followup_questions: List[Dict[str, Any]] = Field(default_factory=list)
    safety_alerts: List[str] = Field(default_factory=list)
    sources: List[Dict[str, Any]] = Field(default_factory=list)


class ProfileRequest(BaseModel):
    token: str
    profile: Dict[str, Any]


# New models for enhanced features
class MedicationInteraction(BaseModel):
    med1: str
    med2: str
    interaction_type: str  # "contraindicated", "caution", "monitor", "ok"
    severity: str  # "severe", "moderate", "mild"
    description: str
    recommendation: str


class HealthTrendData(BaseModel):
    metric: str
    date: str
    value: float
    unit: str
    status: str  # "normal", "elevated", "concerning"


class ExpertConsultation(BaseModel):
    token: str
    question: str
    category: str  # "general", "medication", "lab_report", "symptoms"
    preferred_language: Optional[str] = "en"


