# MediAssist v4 - Quick Start Guide

## Installation

1. **Install new dependencies:**
```bash
pip install -r requirements.txt
```

The following packages were added for new features:
- `cryptography` - For data encryption and security

## Running the Application

```bash
python app.py
# or
uvicorn app:app --reload
```

Visit: `http://localhost:8000`

## Feature Quick Start

### 1. Check Medication Interactions

```bash
curl -X POST "http://localhost:8000/api/check-drug-interactions?token=YOUR_TOKEN&medications=Cetirizine&medications=Paracetamol"
```

### 2. Track Health Metrics

Add a metric:
```bash
curl -X POST "http://localhost:8000/api/health-metric?token=YOUR_TOKEN&metric=blood_pressure&value=120&unit=mmHg&status=normal"
```

View dashboard:
```bash
curl "http://localhost:8000/api/health-dashboard?token=YOUR_TOKEN"
```

### 3. Request Expert Consultation

Get available experts:
```bash
curl "http://localhost:8000/api/experts?token=YOUR_TOKEN"
```

Request consultation:
```bash
curl -X POST "http://localhost:8000/api/request-consultation" \
  -H "Content-Type: application/json" \
  -d '{
    "token": "YOUR_TOKEN",
    "question": "I have persistent headaches for 3 days",
    "category": "symptoms",
    "preferred_language": "en"
  }'
```

### 4. Multi-Language Support

Get UI strings in Spanish:
```bash
curl "http://localhost:8000/api/ui-strings?language=es"
```

Supported languages:
- `en` - English
- `es` - Spanish
- `fr` - French
- `de` - German
- `hi` - Hindi

### 5. Data Privacy

Export your data (GDPR):
```bash
curl "http://localhost:8000/api/export-data?token=YOUR_TOKEN" > user_data_export.json
```

Delete your account:
```bash
curl -X POST "http://localhost:8000/api/delete-account?token=YOUR_TOKEN"
```

View audit log:
```bash
curl "http://localhost:8000/api/audit-log?token=YOUR_TOKEN"
```

### 6. Enhanced Profile

Update profile with new fields:
```bash
curl -X POST "http://localhost:8000/api/update-profile-extended?token=YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "family_history": ["Diabetes", "Heart disease"],
    "lifestyle_activities": ["Running", "Yoga"],
    "dietary_preferences": ["Vegetarian"],
    "emergency_contact": "9876543210",
    "email": "user@example.com",
    "phone": "9876543210",
    "language": "en"
  }'
```

## API Response Examples

### Medication Interaction Check
```json
{
  "medications": ["Warfarin", "Aspirin"],
  "interactions": [
    {
      "medication1": "Warfarin",
      "medication2": "Aspirin",
      "severity": "severe",
      "type": "caution",
      "description": "Significantly increased bleeding risk",
      "recommendation": "Discuss with your doctor about using both medications together"
    }
  ],
  "risk_level": "severe",
  "total_interactions": 1
}
```

### Health Dashboard
```json
{
  "username": "john_doe",
  "dashboard": {
    "last_updated": "2026-03-20T10:30:00",
    "health_metrics": {
      "blood_pressure": [
        {
          "metric": "blood_pressure",
          "value": 120,
          "unit": "mmHg",
          "status": "normal",
          "timestamp": "2026-03-20T10:00:00"
        }
      ]
    },
    "profile": {
      "age": 35,
      "conditions": ["Hypertension"],
      "medications": ["Amlodipine 5mg"]
    }
  }
}
```

### Experts
```json
{
  "username": "john_doe",
  "experts": [
    {
      "id": "dr_001",
      "name": "Dr. Rajesh Kumar",
      "specialization": "General Medicine",
      "available": true,
      "response_time": "15-30 minutes",
      "rating": 4.8
    }
  ],
  "count": 1
}
```

## Feature Highlights

✨ **What's New:**
- 🔍 Drug interaction checker
- 📊 Health analytics & trends
- 👨‍⚕️ Expert consultation booking
- 🌍 Multi-language support
- 🔐 Enhanced security & privacy
- 👤 Extended user profiles

## Security Features

- ✅ End-to-end encryption
- ✅ GDPR compliance (data export & deletion)
- ✅ Audit logging
- ✅ Role-based access control
- ✅ Secure password hashing
- ✅ Session token management

## Troubleshooting

### Issue: "Import 'cryptography' could not be resolved"
**Solution:** Install chromatography:
```bash
pip install cryptography
```

### Issue: "Token missing" in requests
**Solution:** Include your authentication token:
```bash
curl -X GET "http://localhost:8000/api/health-dashboard?token=YOUR_TOKEN"
```

## Integration with Existing Features

The new features integrate seamlessly with MediAssist's existing capabilities:
- **Chat + Health Metrics**: Add metrics while chatting about symptoms
- **Chat + Expert Consultation**: Expert can see your chat history
- **Reports + Analytics**: Uploaded lab reports automatically populate metrics
- **Medications + Drug Interactions**: Medication cards include interaction warnings
## Environment Variables

The following environment variables should be set in `.env`:

```
GEMINI_API_KEY=your_api_key_here
MODEL_NAME=gemini-2.5-flash-lite
PORT=8000
ENCRYPTION_KEY=your_encryption_key_here (optional)
```

## Data Storage

All data is stored locally in the `memory/` directory:
- User profiles: `memory/{username}/profile.json`
- Chat sessions: `memory/{username}/{session_id}.json`
- Health analytics: `memory/{username}/analytics.json`
- Consultations: `memory/consultations/{username}_consultations.json`
- Audit logs: `memory/audit_logs/{username}_audit.json`

## Next Steps

1. **Test the API**: Run the Quick Start examples above
2. **Update Frontend**: Integrate UI components for new features
3. **Connect Experts**: Link real doctor scheduling platform

See [FEATURES.md](FEATURES.md) for detailed API documentation.
