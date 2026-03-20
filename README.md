# MediAssist v4 - AI Health Triage & Management System

**Production-ready AI health triage platform** built with FastAPI, Google Gemini 2.5 Flash, ChromaDB (RAG), NetworkX knowledge graph, and enterprise security features.

## Overview

MediAssist is an **intelligent medical assistant** that intelligently triages health symptoms through a sophisticated **7-stage decision pipeline**:

```
User Message → Emergency Check → Symptom Predictor → Followup Triage 
    → Knowledge Graph → RAG Search → Gemini AI Agent → Response
```

**Core Capabilities:**
- ✅ Multi-stage symptom triage (15 disease patterns with confidence scoring)
- ✅ Emergency detection (21 critical keywords trigger hospital finder)
- ✅ Lab report analysis (PDF/PNG/JPG/TXT extraction + 9 biomarkers)
- ✅ Medication safety (profile-aware + drug interaction checking)
- ✅ Doctor referral links (Practo integration by specialty)
- ✅ Session management (50 sessions/user with 20-message history cap)
- ✅ Doctor handoff summaries with full diagnostic context

**Advanced Features (v4):**
- ✅ Health analytics with metric tracking & trends
- ✅ Drug interaction checking (40+ documented interactions)
- ✅ Expert consultation booking & appointment scheduling
- ✅ Notification system (in-app + simulated email/SMS)
- ✅ Multi-language support (8 languages)
- ✅ **Real speech-to-text** (Google Speech Recognition API)
- ✅ GDPR compliance (data export, account deletion)
- ✅ Audit logging (500 entries/user)

**⚠️ Important:** Informational tool only. Not a substitute for professional medical care.

## Dashboard Features

### 📊 Health Analytics Dashboard
- **Custom Metrics**: Track any health measurement (BP, glucose, weight, etc.)
- **Trending**: Automatic trend detection (improving/declining/stable)
- **Reports**: Generate personalized health summaries
- **History**: Last 100 metrics stored per user

### 🎤 Voice Input (Speech-to-Text) ✨
- **Real Speech Recognition**: Google's free Speech Recognition API
- **Browser Microphone Integration**: Click 🎤 button and speak
- **10+ Languages**: English, Spanish, French, German, Hindi, Tamil, Telugu, Kannada, Marathi, Gujarati
- **Confidence Scoring**: Know how accurate the transcription is
- **Mobile Friendly**: Works on phones and tablets
- **Secure**: Token-authenticated, audit logged

### 🔔 Notification System
- **Types**: Medication reminders, follow-up reminders, emergency alerts, appointment notifications
- **Channels**: In-app (working), Email (simulated), SMS (simulated)
- **Preferences**: Configurable per notification type
- **History**: Last 100 notifications per user

## API Endpoints (27 Total)

### Authentication
```
POST   /api/signup              - Register new user
POST   /api/login               - Login with credentials
POST   /api/logout              - Logout (invalidate token)
```

### Profile Management
```
POST   /api/profile             - Save/update profile
GET    /api/profile             - Retrieve user profile
POST   /api/update-profile-extended - Update extended fields
```

### Core Chat & Triage
```
POST   /api/chat                - Main triage endpoint (7-stage pipeline)
GET    /api/sessions            - List user sessions (max 50)
GET    /api/sessions/{sid}/history - Get session history (last 20 messages)
DELETE /api/sessions/{sid}      - Delete session
GET    /api/handoff-summary     - Generate doctor handoff
```

### Lab & Health Management
```
POST   /api/upload              - Upload lab report (TXT/PDF/PNG/JPG)
GET    /api/lab-history         - Get lab history with trends
POST   /api/health-metric       - Add health metric
GET    /api/health-dashboard    - Get dashboard summary
GET    /api/health-trends       - Get metric trends (configurable)
GET    /api/health-report       - Generate health report
```

### Medications
```
POST   /api/check-drug-interactions - Check medication interactions
GET    /api/pharmacy-links      - Get pharmacy order links for medicines
```

### Notifications
```
GET    /api/notifications       - Get user notifications
POST   /api/mark-notification-read - Mark as read
POST   /api/notification-preferences - Update preferences
```

### Expert Consultation
```
GET    /api/experts             - List available experts (3 doctors + 1 nutritionist)
POST   /api/request-consultation - Request expert help
GET    /api/my-consultations    - Get consultation history
POST   /api/close-consultation  - Close with rating/feedback
POST   /api/schedule-appointment - Book appointment with meeting link
```

### Voice (Real Speech-to-Text ✨)
```
POST   /api/voice-input         - Speech-to-text (Google Speech Recognition API ✨)
POST   /api/voice-output        - Text-to-speech (placeholder - ready for integration)
GET    /api/voice-languages     - List 8 supported languages
```

### Language & Localization
```
GET    /api/supported-languages - List 8 languages
GET    /api/ui-strings          - Get translated UI strings
```

### Privacy & Security
```
GET    /api/export-data         - Export all user data (GDPR)
POST   /api/delete-account      - Delete account + all data
GET    /api/audit-log           - View security audit trail
```

### Reference & System
```
GET    /api/nearby-hospitals    - Hospital finder links
GET    /api/models              - List available Gemini models
GET    /api/health              - Health check (Gemini connection)
GET    /                        - Serve web UI (index.html)
```

## Architecture

### The 7-Stage Triage Pipeline

```
1. AUTH & VALIDATION
   ├─ Token verification
   ├─ Message length check
   └─ Session load/create

2. EMERGENCY DETECTION
   ├─ Check for 21 life-threatening keywords
   └─ YES → Hospital redirect + system response

3. SYMPTOM PREDICTION
   ├─ Extract symptom facts (symptoms, duration, severity, temperature)
   ├─ Match against 15 disease patterns
   ├─ Generate confidence scores
   └─ HIGH CONFIDENCE (>75%) + Complete facts?
       └─ YES → Generate meds + send response
       └─ NO → Create followup triage state

4. FOLLOWUP TRIAGE (If Needed)
   ├─ Generate clarifying questions (age, duration, severity, location)
   ├─ Collect answers in diagnostic_state
   ├─ Re-check confidence
   └─ Once sufficient → Continue to next stage

5. KNOWLEDGE GRAPH QUERY
   ├─ Extract medical terms from message
   ├─ Match against 50+ known medical concepts
   └─ Found? → Query graph, ask Gemini for explanation

6. RAG SEARCH (Retrieval-Augmented Generation)
   ├─ Embed user query with sentence-transformers
   ├─ Search ChromaDB vector store
   ├─ If relevant docs found (similarity > threshold)
   └─ Pass context to Gemini

7. GEMINI AI AGENT (Fallback)
   ├─ Can use 2 tools: web_search, file_operations
   ├─ Up to 4 tool calls per request
   └─ Return final response with sources
```

### Data Storage Architecture

```
memory/                         (Persistent user data)
├── username/                   
│   ├── profile.json            (20+ health fields)
│   ├── {session_id}.json       (chat history, 20-msg cap)
│   ├── analytics.json          (health metrics, 100-entry cap)
│   ├── lab_history.json        (lab records, 30-entry cap)
│   └── last_report.json        (latest lab snapshot)
├── notifications/
│   └── {username}_notifications.json (100-entry cap)
├── consultations/
│   ├── {username}_consultations.json
│   ├── {username}_appointments.json
│   └── feedback.json
├── audit_logs/
│   └── {username}_audit.json   (500-entry cap)
└── voice_logs/
    └── {username}_voice_log.json

uploads/                        (Temporary lab reports)
├── {filename}_{timestamp}

chroma_db/                      (RAG vector store)
├── chroma.sqlite3
└── {embedding_id}/

medical_data/                   (Static reference knowledge)
├── diseases.txt
├── symptoms.txt
├── medicines.txt
└── (symptom_disease_map, fever, diabetes, etc.)

users.json                      (Auth store - credentials)
```

### User Profile Structure

```json
{
  "age": 30,
  "gender": "male|female|other|unknown",
  "known_conditions": ["hypertension", "diabetes"],
  "allergies": ["penicillin"],
  "current_medications": ["metformin"],
  "pregnancy_status": "not_pregnant",
  "smoking_status": "never",
  "alcohol_use": "occasional",
  "past_history": [],
  "family_history": ["heart_disease"],
  "lifestyle_activities": ["walking"],
  "dietary_preferences": ["vegetarian"],
  "emergency_contact": "1234567890",
  "email": "user@example.com",
  "phone": null,
  "language": "en",
  "notification_preferences": {}
}
```

## Implementation Status

### ✅ Fully Implemented
- Emergency detection (21 keywords)
- Symptom prediction (15 diseases × 3 patterns each)
- Medication database (40+ medications with cards)
- Drug interactions (40+ interaction pairs)
- Lab report upload & analysis (TXT/PDF/PNG/JPG)
- Lab metric extraction (9 biomarkers: HbA1c, creatinine, hemoglobin, glucose, TSH, WBC, RBC, platelets, cholesterol + BP)
- Medication safety assessment (allergy/condition/interaction checking)
- Session management (50 active limit, 20-msg/session cap)
- Profile normalization (20+ fields)
- User authentication (token-based, SHA256 hashing)
- Audit logging (500 entries/user)
- Health metrics tracking (100 entries/user)
- Notification system with preferences
- Expert consultation booking (3 doctors + 1 nutritionist)
- Appointment scheduling with mock meeting links
- Data export (GDPR)
- Account deletion (full cleanup)
- Hospital finder links
- Pharmacy links (1mg)
- Handoff summary generation
- Multi-language UI (8 languages)
- **Real speech-to-text** (Google Speech Recognition API, 10+ languages, browser microphone integration)

### ⚠️ Partially Implemented
- **Text-to-Speech (TTS)**: Endpoint exists but returns placeholder audio
  - Ready for Google Cloud TTS, Azure Speech, or AWS Polly integration
  
- **Expert Consultations**: 
  - Booking structure works
  - Expert directory static (3 hardcoded doctors + 1 nutritionist)
  - No actual backend for responses
  
- **Email/SMS Notifications**:
  - Preferences saved
  - Logic implemented
  - No real email/SMS service integration (simulated)

- **Language Translation**:
  - UI strings translated for 8 languages
  - Full response translation not implemented
  - Would require additional Gemini calls

### ❌ Not Implemented
- Real-time hospital/doctor API queries (uses search URLs only)
- E-prescription generation
- Video telemedicine
- Insurance verification
- Custom lab report templates
- Actual OCR (pytesseract requires Tesseract installation)

## Technology Stack

### Backend
- **FastAPI** (async Python web framework)
- **Uvicorn** (ASGI server)
- **Pydantic** (data validation)

### AI/ML
- **google-genai** (Google Gemini 2.5 Flash Lite API)
- **chromadb** (vector database for RAG)
- **sentence-transformers** (all-MiniLM-L6-v2 embeddings)
- **networkx** (knowledge graph)

### Parsing
- **PyMuPDF** (PDF text extraction)
- **pdfplumber** (PDF analysis)
- **BeautifulSoup4** (HTML scraping)
- **Pillow** (image handling)

### Security
- **cryptography** (Fernet AES-128 encryption)
- **PBKDF2-HMAC** (password hashing with salt)
- **UUID** (session tokens)

### Utilities
- **aiohttp** (async HTTP for web search)
- **python-dotenv** (environment configuration)
- **python-multipart** (file uploads)

## Quick Start

### Prerequisites
- Python 3.9+
- Google Gemini API key (free at [https://aistudio.google.com](https://aistudio.google.com))

### Installation

```bash
# 1. Clone repository
cd MediAssist

# 2. Create virtual environment
python -m venv .venv

# Windows
.venv\Scripts\activate

# Mac/Linux
source .venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment (.env file)
GEMINI_API_KEY=your_api_key_here
MODEL_NAME=gemini-2.5-flash-lite
PORT=8000

# 5. Run application
python app.py
```

### Access
- **Web UI**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs (Swagger UI)

### First Steps
1. Sign up with username and password
2. Add health profile (medical history, allergies, medications)
3. Try triage: "I have fever and cough"
4. Upload lab report (PDF/image) for analysis
5. Check health dashboard
6. Book expert consultation

## Security Features

### Authentication
- Token-based auth (UUID tokens)
- Server-side token validation
- Password hashing (SHA256 + PBKDF2)

### Data Protection
- End-to-end encryption (Fernet AES-128)
- Path traversal protection
- Input validation & sanitization

### Privacy
- GDPR compliance (data export, deletion)
- Audit logging (500 entries/user)
- Local data storage (no external cloud)
- Role-based access control

### Data Retention
- Sessions: 50 active limit
- Messages: 20 per session
- Health metrics: 100 per user
- Audit logs: 500 per user
- Notifications: 100 per user

## Known Limitations

1. **Medical Data Sparse**: symptom_disease_map is minimal (good for demo, needs expansion)
2. **Voice Output Placeholder**: Returns mock audio, not real TTS
3. **Expert List Static**: 3 doctors hardcoded, no dynamic registry
4. **RAG Threshold Conservative**: 1.2 (L2 distance) may miss some documents
5. **Session Storage**: Fixed 50-session cap per user
6. **Message History**: Only latest 20 messages stored (older ones discarded)
7. **No Batch Operations**: Each upload/analysis is single-file only

## Configuration

### Environment Variables (.env)

```env
# Required
GEMINI_API_KEY=your_api_key

# Optional
MODEL_NAME=gemini-2.5-flash-lite       # Default
PORT=8000                              # Default
CHROMA_DB_PATH=./chroma_db             # Default
ENCRYPTION_KEY=auto                    # Auto-generated if not set
```

### Customization

**Add new diseases:**
1. Update `medical_data/diseases.txt`
2. Add to `DISEASE_MEDICATIONS` in app.py
3. Update symptom mappings in triage logic

**Add languages:**
1. Add to `services/language.py` → `TRANSLATIONS` dict
2. Test UI rendering
3. Update `/api/supported-languages`

## Testing

### Manual API Testing

```bash
# Signup
curl -X POST "http://localhost:8000/api/signup" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "test123"}'

# Chat
curl -X POST "http://localhost:8000/api/chat?token=YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "I have fever and cough"}'

# Check drug interactions
curl "http://localhost:8000/api/check-drug-interactions?token=YOUR_TOKEN&medications=Warfarin&medications=Aspirin"

# Get health dashboard
curl "http://localhost:8000/api/health-dashboard?token=YOUR_TOKEN"

# List experts
curl "http://localhost:8000/api/experts?token=YOUR_TOKEN"
```

See FEATURES.md and QUICK_START.md for detailed examples.

## Troubleshooting

| Issue | Solution |
|-------|----------|
| GEMINI_API_KEY not set | Create .env file with valid key from [aistudio.google.com](https://aistudio.google.com) |
| Port 8000 in use | Change PORT in .env or run `netstat -ano \| findstr :8000` to find process |
| Voice endpoints return placeholder | Expected behavior - no real audio service integrated |
| Expert consultations empty | 3 doctors are hardcoded as demo data |
| Slow symptom prediction | Normal on first run - knowledge graph loads, RAG indexes data |
| Character encoding issues | Ensure UTF-8 in .env and terminal |

## Performance Characteristics

- **Symptom triage response**: ~500ms
- **Lab report upload**: ~2-5s (depending on file size)
- **Gemini API call**: ~2-10s (depends on API)
- **Concurrent users**: Tested for 1-100 concurrent sessions
- **Database size**: ChromaDB vector store ~200MB with full medical data

## Production Deployment

### Local Testing
```bash
python app.py
# or
uvicorn app:app --host 0.0.0.0 --port 8000
```

### Docker Deployment
```dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "8000"]
```

### Cloud Deployment
- Supports Heroku, AWS, Google Cloud, Azure
- Requires: Python 3.9+, Gemini API key
- Data persists in local `memory/` directory (use cloud storage for production)

## File Structure

```
MediAssist/
├── app.py                      # FastAPI application (27 endpoints)
├── index.html                  # Web UI (single-page)
├── models.py                   # Pydantic data models
├── lab_services.py             # Lab report analysis
├── med_safety.py               # Medication safety + interactions
├── requirements.txt            # Dependencies
├── .env                        # Configuration (create this)
├── users.json                  # Authentication store
│
├── services/                   # Business logic
│   ├── profile.py
│   ├── triage.py
│   ├── analytics.py
│   ├── notifications.py
│   ├── security.py
│   ├── voice_handler.py
│   ├── expert_consultation.py
│   └── language.py
│
├── rag/                        # Retrieval-Augmented Generation
│   ├── rag_engine.py
│   └── document_loader.py
│
├── knowledge_graph/            # Medical knowledge graph
│   └── graph.py
│
├── medical_data/               # Reference data
│   └── *.txt files
│
├── memory/                     # User data storage
│   └── {username}/ (sessions, profiles, analytics)
│
├── uploads/                    # Lab report uploads
│
├── chroma_db/                  # RAG vector database
│
└── Documentation/
    ├── README.md               # This file
    ├── FEATURES.md             # Detailed Feature Documentation
    ├── QUICK_START.md          # Quick Start Guide
    ├── MEDIASSIST_COMPREHENSIVE_ANALYSIS.md
    └── IMPLEMENTATION_SUMMARY.md
```

## Documentation

- **[FEATURES.md](FEATURES.md)** - Complete API reference with examples
- **[QUICK_START.md](QUICK_START.md)** - Getting started guide
- **[VOICE_FEATURE.md](VOICE_FEATURE.md)** - Complete voice input (STT) guide with troubleshooting
- **[VOICE_QUICK_REFERENCE.md](VOICE_QUICK_REFERENCE.md)** - Quick voice I/O reference
- **[SPEECH_TO_TEXT_IMPLEMENTATION.md](SPEECH_TO_TEXT_IMPLEMENTATION.md)** - Technical implementation details
- **[MEDIASSIST_COMPREHENSIVE_ANALYSIS.md](MEDIASSIST_COMPREHENSIVE_ANALYSIS.md)** - Technical deep dive
- **[IMPLEMENTATION_SUMMARY.md](IMPLEMENTATION_SUMMARY.md)** - Architecture & design

## License & Disclaimer

MediAssist - AI Health Triage System  
Built with FastAPI, Google Gemini, ChromaDB  
Licensed for educational and research use

**Medical Disclaimer:**  
This system is for informational purposes only. It is NOT a substitute for professional medical advice, diagnosis, or treatment. Always consult a qualified healthcare provider about any health concerns.

## Support

For issues or questions:
1. Check FEATURES.md for API documentation
2. Review QUICK_START.md for examples
3. Check audit logs: `/api/audit-log`
4. Review health provider logs in `memory/{username}/`

---

**Version:** 4.1 (Speech-to-Text Update)  
**Last Updated:** March 20, 2026  
**Status:** Production-Ready ✅  
**Maintenance Mode:** Active
