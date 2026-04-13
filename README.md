# MediAssist

MediAssist is a FastAPI-based health triage app with a single-page web UI. It combines emergency screening, symptom-based triage, optional follow-up questioning, uploaded lab report analysis, medication safety checks, lightweight expert consultation flows, and local file-backed user data.

## What Changed

The current app is no longer just a simple symptom checker. The active workflow now includes:

- Token-based signup, login, logout, and profile persistence
- Chat routing for emergency detection, symptom triage, uploaded report Q&A, appointment booking, and tablet-order guidance
- Follow-up question state stored per session when symptoms are ambiguous
- Lab upload analysis with structured metric extraction and trend comparison against prior reports
- Health dashboard, trends, and report generation from saved metrics
- Expert consultation, appointment scheduling, audit logging, and data export/deletion APIs

## Core Workflow

### 1. Authentication and Profile

1. User signs up with `username` and `password`
2. User logs in and receives a token
3. Login also seeds or updates the saved health profile
4. The frontend uses that token for chat, uploads, analytics, consultations, and privacy endpoints

### 2. Chat Routing

Each `POST /api/chat` request is routed roughly like this:

```text
User message
  -> token validation
  -> session lookup / creation
  -> preferred-name memory checks
  -> emergency detector
  -> special follow-up flows
       - appointment booking
       - tablet order guidance
       - symptom clarification
  -> uploaded report Q&A (if the user refers to a saved report)
  -> symptom predictor + medication safety
  -> Gemini-generated final response
  -> session history + sources saved to local storage
```

### 3. Lab Report Workflow

1. User uploads `txt`, `pdf`, `png`, `jpg`, or `jpeg`
2. Text is extracted from the file
3. Structured lab metrics are parsed from the content
4. Findings and trend comparisons are generated
5. The latest report is saved for future chat-based follow-up
6. Users can later ask questions about the uploaded report in chat

### 4. Data Persistence

The app stores data locally:

- `users.json` for authentication state
- `memory/<username>/` for profile, sessions, analytics, and lab history
- `memory/consultations/` for expert consultations and appointments
- `memory/audit_logs/` for audit events
- `uploads/` for uploaded files
- `chroma_db/` for optional RAG data

## Features

- Emergency detection with hospital/escalation guidance
- Symptom prediction for common conditions
- Adaptive follow-up triage when confidence is low or details are missing
- Uploaded report analysis with metric extraction and trend comparison
- Medication cards, drug interaction checks, and profile-aware safety warnings
- Appointment-booking and tablet-order assistant flows inside chat
- Health metric tracking, dashboard summaries, and generated health reports
- Expert consultation and appointment scheduling endpoints
- UI localization endpoints
- Audit logging plus export/delete account flows
- Optional RAG and knowledge-graph support with graceful degradation

## Project Structure

```text
MediAssist/
├── app.py
├── index.html
├── models.py
├── requirements.txt
├── run.ps1
├── run.bat
├── med_safety.py
├── lab_services.py
├── services/
│   ├── analytics.py
│   ├── expert_consultation.py
│   ├── language.py
│   ├── profile.py
│   ├── response_validator.py
│   ├── security.py
│   └── triage.py
├── prompts/
├── rag/
├── knowledge_graph/
├── medical_data/
├── uploads/
├── memory/
└── chroma_db/
```

## Main API Surface

### Auth and Profile

- `POST /api/signup`
- `POST /api/login`
- `POST /api/logout`
- `POST /api/profile`
- `GET /api/profile`
- `POST /api/update-profile-extended`

### Chat and Sessions

- `POST /api/chat`
- `GET /api/health`
- `GET /api/models`
- `GET /api/sessions`
- `GET /api/sessions/{sid}/history`
- `DELETE /api/sessions/{sid}`
- `GET /api/handoff-summary`

### Lab and Medication

- `POST /api/upload`
- `GET /api/lab-history`
- `POST /api/check-drug-interactions`
- `GET /api/pharmacy-links`
- `GET /api/nearby-hospitals`
- `GET /api/resolve-city`

### Analytics and Consultation

- `GET /api/health-dashboard`
- `POST /api/health-metric`
- `GET /api/health-trends`
- `GET /api/health-report`
- `GET /api/experts`
- `POST /api/request-consultation`
- `GET /api/my-consultations`
- `POST /api/close-consultation`
- `POST /api/schedule-appointment`

### Localization and Privacy

- `GET /api/ui-strings`
- `GET /api/supported-languages`
- `GET /api/export-data`
- `POST /api/delete-account`
- `GET /api/audit-log`

## Setup

### Prerequisites

- Python 3.10+
- A valid Google Gemini API key

### Install

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

### Configure

Create `.env` from `.env.example` and set at least:

```env
GEMINI_API_KEY=your_api_key_here
MODEL_NAME=gemini-2.5-flash-lite
PORT=8000
CHROMA_DB_PATH=./chroma_db
ENCRYPTION_KEY=your_secret_key
```

### Run

Use either:

```powershell
.\.venv\Scripts\python.exe app.py
```

or:

```powershell
.\run.ps1
```

Then open:

- `http://localhost:8000`
- `http://localhost:8000/docs`

## Notes

- Authentication currently uses SHA-256 hashing in `app.py`
- Stronger PBKDF2 helpers exist in `services/security.py` but are not wired into login yet
- Uploaded image OCR depends on `pytesseract`
- PDF extraction prefers `pdfplumber` and falls back to `PyMuPDF`
- RAG support is optional and designed to fail gracefully if unavailable
- This project stores user data locally and is intended for development/demo use, not production clinical deployment

## Related Docs

- [QUICK_START.md](QUICK_START.md)
- [DEPLOYMENT.md](DEPLOYMENT.md)
- [DEPLOYMENT_CHECKLIST.md](DEPLOYMENT_CHECKLIST.md)

## Disclaimer

MediAssist provides informational guidance only. It is not a substitute for professional medical advice, diagnosis, or treatment.
