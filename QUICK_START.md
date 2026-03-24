# Quick Start

## 1. Create and use the local virtual environment

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

If `python` points to the Microsoft Store shim on Windows, use an installed interpreter directly to create the environment, then use `.venv\Scripts\python.exe` for project commands.

## 2. Configure `.env`

Minimum configuration:

```env
GEMINI_API_KEY=your_api_key_here
MODEL_NAME=gemini-2.5-flash-lite
PORT=8000
CHROMA_DB_PATH=./chroma_db
```

Optional:

```env
ENCRYPTION_KEY=your_secret_key
```

## 3. Run the application

```powershell
.\.venv\Scripts\python.exe app.py
```

Open:

- `http://localhost:8000`
- `http://localhost:8000/docs`

## 4. Basic API flow

### Sign up

```bash
curl -X POST "http://localhost:8000/api/signup" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "Pass@1234"}'
```

### Log in

```bash
curl -X POST "http://localhost:8000/api/login" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "Pass@1234"}'
```

### Send a chat request

```bash
curl -X POST "http://localhost:8000/api/chat?token=YOUR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"message": "I have fever and cough", "session_id": "demo-session"}'
```

### Upload a lab file

```bash
curl -X POST "http://localhost:8000/api/upload?token=YOUR_TOKEN" \
  -F "file=@report.txt"
```

## 5. Feature-specific examples

### Check drug interactions

```bash
curl -X POST "http://localhost:8000/api/check-drug-interactions?token=YOUR_TOKEN&medications=Warfarin&medications=Aspirin"
```

### Add and view health metrics

```bash
curl -X POST "http://localhost:8000/api/health-metric?token=YOUR_TOKEN&metric=blood_pressure&value=120&unit=mmHg&status=normal"
```

```bash
curl "http://localhost:8000/api/health-dashboard?token=YOUR_TOKEN"
```

### View supported languages

```bash
curl "http://localhost:8000/api/supported-languages"
```

Current UI languages in code:

- `en`
- `es`
- `fr`
- `de`
- `hi`

### Request a consultation

```bash
curl -X POST "http://localhost:8000/api/request-consultation?token=YOUR_TOKEN&expert_id=dr_001" \
  -H "Content-Type: application/json" \
  -d '{
    "question": "I have persistent headaches for 3 days",
    "category": "symptoms",
    "preferred_language": "en"
  }'
```

## 6. Operational notes

- ChromaDB-backed RAG is optional at runtime; the app now degrades safely if the vector store cannot initialize
- User state is stored in local JSON files under `memory/`
- Uploaded files are stored under `uploads/`
- The current auth routes use `SHA-256` hashing in `app.py`; stronger PBKDF2 helpers exist in `services/security.py` but are not wired into login yet

## 7. Troubleshooting

### `GEMINI_API_KEY is not set`

Add the key to `.env` and restart the app.

### Windows `python.exe` cannot run

Use the project interpreter directly:

```powershell
.\.venv\Scripts\python.exe app.py
```

### ChromaDB fails with read-only database

The app should still start, but RAG search will return empty results until `chroma_db/` is writable.

### Permission errors under `memory/`

Make sure the workspace is writable. Profile and RAG initialization now fail closed more safely, but persistent features still need write access for full functionality.
