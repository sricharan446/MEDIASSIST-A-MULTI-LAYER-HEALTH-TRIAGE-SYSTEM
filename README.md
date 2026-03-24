# MediAssist - AI Health Triage System

MediAssist is a FastAPI-based health triage application that combines rule-based screening, a medical knowledge graph, RAG retrieval with ChromaDB, Google Gemini-backed responses, lab report parsing, and file-based user state.

## Features

- **Emergency detection** - 21 life-threatening keyword patterns with instant hospital redirect
- **Symptom prediction** - 15 disease patterns with confidence scoring
- **Follow-up triage** - Adaptive questions when confidence is low or symptoms are ambiguous
- **Knowledge graph** - NetworkX-based medical term lookup
- **RAG search** - ChromaDB vector store for medical document retrieval
- **Gemini AI** - Google Gemini 2.5 Flash Lite for response generation
- **Medication database** - 15 diseases with prescription cards including dosage and pharmacy links
- **Drug interaction checker** - 40+ documented interactions with severity levels
- **Medication safety** - Checks against allergies, conditions, pregnancy, and current medications
- **Lab report analysis** - Upload TXT, PDF, PNG, or JPG; extracts 9 biomarkers + blood pressure
- **Lab trend tracking** - Compare current vs previous reports
- **Expert consultation** - Book appointments with doctors and nutritionists
- **Multi-language UI** - English, Spanish, French, German, Hindi
- **Health analytics** - Track custom metrics with trend analysis and dashboard
- **GDPR compliance** - Data export and account deletion

## Architecture

```
User Message
  -> Emergency Check (21 keywords)
  -> Symptom Predictor (15 diseases)
  -> Follow-up Triage (when needed)
  -> Knowledge Graph
  -> RAG Search (when available)
  -> Gemini Response
```

## Project Structure

```
MediAssist/
├── app.py                    # Main FastAPI application
├── models.py                 # Pydantic request/response models
├── index.html                # Frontend UI
├── requirements.txt          # Python dependencies
├── med_safety.py             # Medication safety & drug interactions
├── lab_services.py           # Lab report parsing & analysis
├── services/
│   ├── profile.py            # User profile management
│   ├── triage.py             # Symptom triage logic
│   ├── analytics.py          # Health metrics & trends
│   ├── security.py           # Encryption & audit logging
│   ├── expert_consultation.py # Doctor consultation
│   └── language.py           # Multi-language support
├── rag/
│   ├── rag_engine.py         # ChromaDB RAG retrieval
│   └── document_loader.py    # Document text extraction
├── knowledge_graph/
│   └── graph.py              # NetworkX medical knowledge graph
├── medical_data/             # Static medical reference files
├── memory/                   # User data (profiles, sessions, analytics)
├── uploads/                  # Uploaded lab reports
└── chroma_db/                # ChromaDB vector store
```

## API Endpoints

### Authentication
- `POST /api/signup` - Register new user
- `POST /api/login` - Login and get token
- `POST /api/logout` - Invalidate token

### Chat & Triage
- `POST /api/chat` - Main chat endpoint with multi-stage routing
- `GET /api/health` - Health check
- `GET /api/models` - List available models

### Profile & Sessions
- `POST /api/profile` - Save user profile
- `GET /api/profile` - Get user profile
- `GET /api/sessions` - List user sessions
- `GET /api/sessions/{sid}/history` - Get session history
- `DELETE /api/sessions/{sid}` - Delete session
- `GET /api/handoff-summary` - Generate doctor handoff summary
- `POST /api/update-profile-extended` - Update extended profile fields

### Lab & Health Tracking
- `POST /api/upload` - Upload lab report (TXT/PDF/PNG/JPG)
- `GET /api/lab-history` - Get lab history with trends
- `POST /api/health-metric` - Add health metric
- `GET /api/health-dashboard` - Get health dashboard
- `GET /api/health-trends` - Get health trends
- `GET /api/health-report` - Generate health report

### Medication
- `POST /api/check-drug-interactions` - Check drug interactions
- `GET /api/pharmacy-links` - Get pharmacy order links
- `GET /api/nearby-hospitals` - Hospital finder links

### Consultation
- `GET /api/experts` - List available experts
- `POST /api/request-consultation` - Request consultation
- `GET /api/my-consultations` - Get user consultations
- `POST /api/close-consultation` - Close consultation with feedback
- `POST /api/schedule-appointment` - Schedule appointment

### Localization
- `GET /api/ui-strings` - UI translations
- `GET /api/supported-languages` - List languages

### Privacy
- `GET /api/export-data` - Export user data (GDPR)
- `POST /api/delete-account` - Delete account and data
- `GET /api/audit-log` - Get user audit log

## Setup

### Prerequisites
- Python 3.10+
- A valid `GEMINI_API_KEY` from Google AI Studio

### Installation

```powershell
# Create virtual environment
python -m venv .venv

# Activate (Windows PowerShell)
.\.venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Configuration

Create a `.env` file:

```env
GEMINI_API_KEY=your_api_key_here
MODEL_NAME=gemini-2.5-flash-lite
PORT=8000
CHROMA_DB_PATH=./chroma_db
```

### Running

```powershell
.\.venv\Scripts\python.exe app.py
```

Open:
- UI: `http://localhost:8000`
- API Docs: `http://localhost:8000/docs`

## Quick Start

See [QUICK_START.md](QUICK_START.md) for detailed examples and curl commands.

## Storage Model

```
users.json                         # Authentication store
memory/{username}/profile.json     # User profile
memory/{username}/*.json           # Chat sessions
memory/{username}/analytics.json   # Health metrics
memory/{username}/lab_history.json # Lab history
memory/consultations/              # Consultation data
memory/audit_logs/                 # Audit trails
uploads/                           # Uploaded files
chroma_db/                         # Vector store
```

### Data Limits
- Max 50 sessions per user
- Session history: last 20 messages for AI context
- Stored messages: max 50 per session
- Health metrics: max 100 entries
- Audit log: max 500 entries
- Lab history: max 30 records

## Security Notes

- `app.py` hashes passwords with SHA-256
- `services/security.py` includes PBKDF2-HMAC-SHA256 helpers (not yet wired to auth routes)
- Fernet encryption for sensitive data
- Token-based authentication
- Path traversal protection on file operations
- Audit logging for compliance

## RAG Behavior

The RAG engine gracefully degrades if ChromaDB cannot initialize:
- App import still succeeds
- `search_rag()` returns empty results
- `add_document_to_rag()` returns status message

## Known Limitations

- Medical responses are informational only, not clinical advice
- Expert consultation is mock/static (no real provider network)
- Localization covers UI strings only, not full response translation
- OCR requires Tesseract installation
- Storage is local JSON + ChromaDB, not a scalable database

## Disclaimer

This project is for informational and development purposes only. It is not a substitute for professional medical advice, diagnosis, or treatment.
