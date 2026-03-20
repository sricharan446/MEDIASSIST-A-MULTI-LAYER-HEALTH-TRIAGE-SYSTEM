# MediAssist v4 - New Features Documentation

This document describes all the new features added to MediAssist Health Triage System.

## 1. Medication Interaction Checker

**Location:** `/api/check-drug-interactions`

**Feature:** Checks for drug-drug interactions among provided medications.

**Supported Interactions:**
- NSAIDs with other medications
- SSRIs (Selective Serotonin Reuptake Inhibitors)
- Benzodiazepines
- Blood thinners
- And more...

**API Endpoint:**
```
POST /api/check-drug-interactions
Query Parameters:
  - token: User authentication token
  - medications: List[str] - Medication names to check

Response:
{
  "medications": [...],
  "interactions": [
    {
      "medication1": "...",
      "medication2": "...",
      "severity": "severe|moderate|mild",
      "type": "contraindicated|caution|monitor|ok",
      "description": "...",
      "recommendation": "..."
    }
  ],
  "risk_level": "severe|moderate|mild|none",
  "total_interactions": 0
}
```

## 2. Health Analytics & Trends Dashboard

**Location:** `/api/health-dashboard`, `/api/health-trends`, `/api/health-metric`, `/api/health-report`

**Features:**
- Track health metrics over time
- View health trends and statistics
- Generate personalized health reports
- Dashboard summary with recent metrics

**API Endpoints:**

### Get Health Dashboard
```
GET /api/health-dashboard
Query Parameters:
  - token: User authentication token

Response: Health metrics, profile info, recent analytics
```

### Add Health Metric
```
POST /api/health-metric
Query Parameters:
  - token: User authentication token
  - metric: str - Metric name (e.g., "blood_pressure", "glucose")
  - value: float - Metric value
  - unit: str - Unit (e.g., "mmHg", "mg/dL")
  - status: str - Status ("normal", "elevated", "concerning")
```

### Get Health Trends
```
GET /api/health-trends
Query Parameters:
  - token: User authentication token
  - metric: str (optional) - Specific metric to track
  - days: int - Number of days to analyze (default: 30)
```

### Generate Health Report
```
GET /api/health-report
Query Parameters:
  - token: User authentication token

Response: Text-based comprehensive health report
```

## 3. Notification System

**Location:** `/api/notifications`, `/api/mark-notification-read`, `/api/notification-preferences`

**Features:**
- Email and SMS notifications
- Medication reminders
- Follow-up reminders
- Emergency alerts
- In-app notifications
- Notification preferences management

**API Endpoints:**

### Get Notifications
```
GET /api/notifications
Query Parameters:
  - token: User authentication token
  - unread_only: bool - Only unread notifications (default: false)
```

### Mark Notification as Read
```
POST /api/mark-notification-read
Query Parameters:
  - token: User authentication token
  - notification_id: str - ID of notification to mark as read
```

### Update Notification Preferences
```
POST /api/notification-preferences
Query Parameters:
  - token: User authentication token
  - email_enabled: bool
  - sms_enabled: bool
  - medication_reminders: bool
  - follow_up_reminders: bool
```

## 4. Voice Input & Output

**Location:** `/api/voice-input`, `/api/voice-output`, `/api/voice-languages`

**Features:**
- Speech-to-text for voice queries
- Text-to-speech for responses
- Support for multiple languages
- Different voice styles (neutral, friendly, professional, calm, energetic)

**API Endpoints:**

### Process Voice Input
```
POST /api/voice-input
Body:
{
  "token": "...",
  "audio_base64": "...",  // Base64 encoded audio
  "language": "en|es|fr|de|hi"
}

Response:
{
  "status": "success|error",
  "transcription": {
    "text": "...",
    "confidence": 0.95,
    "language": "en",
    "duration_seconds": 5.2
  }
}
```

### Generate Voice Output
```
POST /api/voice-output
Query Parameters:
  - token: User authentication token
  - text: str - Text to convert to speech
  - language: str - Language (default: "en")
  - voice_style: str - Voice style (default: "neutral")

Response:
{
  "status": "success|error",
  "audio": {
    "audio_base64": "...",
    "language": "en",
    "voice_style": "neutral",
    "duration_seconds": 2.5
  }
}
```

### Get Voice Languages
```
GET /api/voice-languages

Response:
{
  "languages": {
    "en": "English",
    "es": "Spanish",
    "fr": "French",
    "de": "German",
    "hi": "Hindi"
  },
  "voice_styles": {
    "neutral": "Professional and neutral tone",
    "friendly": "Warm and friendly tone",
    ...
  }
}
```

## 5. Expert Consultation & Doctor Chat

**Location:** `/api/experts`, `/api/request-consultation`, `/api/my-consultations`, `/api/close-consultation`, `/api/schedule-appointment`

**Features:**
- Browse available medical experts
- Request consultations with experts
- Chat with doctors
- Schedule appointments
- Rate and provide feedback

**Sample Experts:**
- Dr. Rajesh Kumar (General Medicine)
- Dr. Priya Singh (Cardiology)
- Dr. Amit Patel (Neurology)
- Ms. Sneha Verma (Nutritionist)

**API Endpoints:**

### Get Available Experts
```
GET /api/experts
Query Parameters:
  - token: User authentication token
  - category: str - "all|doctors|nutritionists" (default: "all")

Response:
{
  "experts": [
    {
      "id": "dr_001",
      "name": "Dr. Name",
      "specialization": "...",
      "available": true,
      "response_time": "15-30 minutes",
      "rating": 4.8
    }
  ]
}
```

### Request Consultation
```
POST /api/request-consultation
Body:
{
  "token": "...",
  "question": "...",
  "category": "general|medication|lab_report|symptoms",
  "preferred_language": "en"
}

Response:
{
  "status": "success",
  "consultation": {
    "id": "...",
    "username": "...",
    "expert_id": "...",
    "status": "pending|in_progress|closed",
    "created_at": "...",
    "messages": [...]
  }
}
```

### Get My Consultations
```
GET /api/my-consultations
Query Parameters:
  - token: User authentication token

Response:
{
  "consultations": [...],
  "count": 5
}
```

### Close Consultation
```
POST /api/close-consultation
Query Parameters:
  - token: User authentication token
  - consultation_id: str
  - rating: int (1-5, optional)
  - feedback: str (optional)
```

### Schedule Appointment
```
POST /api/schedule-appointment
Query Parameters:
  - token: User authentication token
  - expert_id: str
  - date: str (YYYY-MM-DD)
  - time: str (HH:MM)
  - reason: str - Reason for appointment

Response:
{
  "status": "success",
  "appointment": {
    "id": "...",
    "date": "...",
    "time": "...",
    "meeting_link": "https://meet.example.com/..."
  }
}
```

## 6. Multi-Language Support

**Location:** `/api/ui-strings`, `/api/supported-languages`

**Supported Languages:**
- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Hindi (hi)

**API Endpoints:**

### Get UI Strings
```
GET /api/ui-strings
Query Parameters:
  - language: str - Language code (default: "en")

Response:
{
  "language": "en",
  "strings": {
    "welcome": "Welcome to MediAssist",
    "chat_placeholder": "Ask me about your symptoms...",
    ...
  }
}
```

### Get Supported Languages
```
GET /api/supported-languages

Response:
{
  "languages": {
    "en": "English",
    "es": "Spanish",
    ...
  }
}
```

## 7. Data Privacy & Security

**Location:** `/api/export-data`, `/api/delete-account`, `/api/audit-log`

**Features:**
- End-to-end encryption for sensitive data
- GDPR-compliant data export
- Account deletion with complete data removal
- Audit logging for all user actions
- Role-based access control
- Password hashing with salt

**API Endpoints:**

### Export User Data (GDPR)
```
GET /api/export-data
Query Parameters:
  - token: User authentication token

Response:
{
  "status": "success",
  "data_export": {
    "export_date": "...",
    "username": "...",
    "profile": {...},
    "sessions": [...],
    "analytics": {...},
    "notifications": [...],
    "audit_log": [...]
  }
}
```

### Delete User Account
```
POST /api/delete-account
Query Parameters:
  - token: User authentication token

Response:
{
  "status": "success",
  "message": "Your account and all associated data have been deleted."
}
```

### Get Audit Log
```
GET /api/audit-log
Query Parameters:
  - token: User authentication token

Response:
{
  "username": "...",
  "audit_log": [
    {
      "timestamp": "...",
      "action": "LOGIN|CHAT|UPDATE_PROFILE|...",
      "resource": "...",
      "status": "success|failure",
      "details": {...}
    }
  ]
}
```

## 8. Enhanced User Profile

**Location:** `/api/update-profile-extended`

**New Profile Fields:**
- `family_history`: List of hereditary conditions
- `lifestyle_activities`: Exercise, hobbies, etc.
- `dietary_preferences`: Dietary habits and restrictions
- `emergency_contact`: Contact info for emergencies
- `email`: User email address
- `phone`: User phone number
- `language`: Preferred language
- `notification_preferences`: Notification configuration

**API Endpoint:**

### Update Extended Profile
```
POST /api/update-profile-extended
Query Parameters:
  - token: User authentication token
  - profile_data: Dict - Profile fields to update

Response:
{
  "status": "success",
  "profile": {
    "age": 30,
    "known_conditions": [...],
    "allergies": [...],
    "family_history": [...],
    "lifestyle_activities": [...],
    "dietary_preferences": [...],
    "emergency_contact": "...",
    "email": "...",
    "phone": "...",
    "language": "en",
    "notification_preferences": {...}
  }
}
```

## Security Features

### Encryption
- Sensitive data is encrypted using Fernet (AES-128)
- Passwords are hashed using PBKDF2 with SHA-256
- Session tokens are invalidated on logout

### Audit Logging
- All user actions are logged with timestamps
- Audit logs are stored securely per user
- Includes action, resource, status, and details

### Role-Based Access Control (RBAC)
- Three roles: **user**, **doctor**, **admin**
- Different permissions for each role
- Users can only access their own data

### GDPR Compliance
- Right to data export
- Right to be forgotten (account deletion)
- Data processing transparency
- Consent management for notifications

## Storage Structure

```
memory/
  {username}/
    profile.json              # User profile
    analytics.json            # Health metrics and trends
    {session_id}.json         # Chat sessions
  notifications/
    {username}_notifications.json    # User notifications
    emergency_alerts.json            # Emergency log
  audit_logs/
    {username}_audit.json     # User audit log
    emergency_alerts.json     # System emergency alerts
    user_roles.json           # Role assignments
  consultations/
    {username}_consultations.json    # Consultations
    appointments.json         # Appointments
    experts.json              # Expert directory
  voice_logs/
    {username}_voice_log.json # Voice interactions
```

## Integration with Existing Features

All new features integrate seamlessly with existing MediAssist features:
- Medication cards in responses include drug interaction warnings
- Health metrics are tracked from lab uploads and chat inputs
- Expert consultations can include chat history
- Notifications are sent for emergency alerts and follow-ups
- Voice input/output works with all existing chat features

## Development Notes

- All service modules use JSON file storage for persistence
- Async/await for non-blocking operations
- Error handling with proper HTTP status codes
- Security manager enforces access control
- Audit logging for compliance tracking
- Language manager supports text translation

## Future Enhancements

- Integration with real email/SMS providers (SendGrid, Twilio)
- Advanced speech recognition (Google Cloud Speech-to-Text)
- Appointment confirmations via calendar integration
- Wearable device integration for real-time health data
- Machine learning for personalized recommendations
- Real-time video consultations with doctors
