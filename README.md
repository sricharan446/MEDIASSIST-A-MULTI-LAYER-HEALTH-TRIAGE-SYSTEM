# MediAssist — AI Health Triage System

> An intelligent, conversational health guidance system powered by **Google Gemini**, **RAG**, and a **Medical Knowledge Graph** — runs as a single Python server, zero deployment overhead.

![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python&logoColor=white)
![FastAPI](https://img.shields.io/badge/FastAPI-0.100+-009688?logo=fastapi&logoColor=white)
![Gemini](https://img.shields.io/badge/Google_Gemini-API-4285F4?logo=google&logoColor=white)
![ChromaDB](https://img.shields.io/badge/ChromaDB-RAG-orange)
![License](https://img.shields.io/badge/License-MIT-green)

---

## Table of Contents

- [Overview](#-overview)
- [Features](#-features)
- [System Architecture](#-system-architecture)
- [Setup Guide](#-setup-guide)
- [Project Structure](#-project-structure)
- [Environment Configuration](#-environment-configuration)
- [API Reference](#-api-reference)
- [Chat Pipeline](#-chat-pipeline)
- [Medical Intelligence](#-medical-intelligence)
- [Pharmacy Order Cards](#-pharmacy-order-cards)
- [Emergency Hospital Finder](#-emergency-hospital-finder)
- [Knowledge Graph](#-knowledge-graph)
- [RAG Pipeline](#-rag-pipeline)
- [Memory System](#-memory-system)
- [Authentication & Security](#-authentication--security)
- [Dependencies](#-dependencies)
- [Disclaimer](#-disclaimer)

---

## Overview

**MediAssist** is an intelligent, conversational health guidance system designed to help users understand their symptoms, interpret medical reports, and receive personalised health recommendations — all powered by Google Gemini and a multi-layer medical intelligence pipeline.

It is **not a replacement for professional medical care**, but a first-line triage tool that:

- Detects potentially life-threatening symptoms instantly and raises emergency alerts with nearby hospital links
- Predicts likely conditions from described symptoms using weighted scoring across 15 diseases
- Analyses uploaded lab reports (PDF, image, text) and flags 13 abnormal biomarkers
- Draws on a curated medical knowledge base via Retrieval-Augmented Generation (RAG)
- Queries an expanded local Knowledge Graph (308 nodes, 21 clusters) for fast concept lookups
- Falls back to live DuckDuckGo web search when local knowledge is insufficient
- Appends interactive medication order cards (PharmEasy · 1mg · Netmeds) for every response

The entire system runs as a **single Python server** — no separate frontend deployment or Node.js required.

---

## Features

| Feature | Description |
|---|---|
| **Symptom Checker** | Describes symptoms → scores against 15 disease patterns → Gemini generates triage response with risk level |
| **Medication Order Cards** | Every response includes interactive pharmacy cards (PharmEasy, 1mg, Netmeds) with strip quantity selector |
| **Medical Report Analyser** | Upload PDF, image, or text lab report → 13 biomarkers checked → Gemini explains findings in plain language |
| **Emergency Triage** | 21 life-threatening keywords trigger instant EMERGENCY ALERT + nearby hospital finder |
| **Hospital Finder** | On emergency, auto-detects location → shows Google Maps, Practo (GP booking), Justdial hospital listings |
| **Medical Q&A** | General health questions answered using RAG over 8 pre-loaded medical knowledge files |
| **Knowledge Graph Lookup** | 308-node NetworkX graph with 115 searchable terms across 21 disease clusters |
| **Health History Tracking** | Multi-session chat memory, capped at 50 messages/session, 20 sent to Gemini per request |
| **Personalised Risk** | Age and known conditions boost confidence scores for relevant disease predictions |
| **Web-Augmented Answers** | AI agent falls back to DuckDuckGo search for queries beyond local knowledge |

---

## System Architecture

```
BROWSER (index.html)
HTML + CSS + Vanilla JS UI
 |
 | HTTP REST API
 v
FASTAPI SERVER (app.py)
 Auth (users.json)
 Sessions (memory/)
 File Upload (uploads/)
 Chat Pipeline (in priority order):
 1. Emergency Detector instant alert (21 keywords) + hospital finder
 2. Uploaded Report Gemini analysis
 3. Symptom Predictor 15 diseases + flood guard + medication card
 4. Knowledge Graph 308 nodes, 21 clusters, 115 search terms
 5. RAG Search ChromaDB + MiniLM + Gemini
 6. AI Agent Gemini + Web Search
 | |
 v v
Google Gemini API ChromaDB (chroma_db/)
gemini-2.5-flash-lite all-MiniLM-L6-v2 embeddings
 |
 v
DuckDuckGo Web Search
(aiohttp scraper, agent fallback)
```

**Data flow:** User message → FastAPI auth check → pipeline evaluates layers in order → first confident match returns response → response saved to session file → returned to browser.

---

## Setup Guide

### Prerequisites

| Requirement | Notes |
|---|---|
| Python 3.9+ | Required |
| Google Gemini API Key | Free tier at [aistudio.google.com](https://aistudio.google.com/app/apikey) |
| Tesseract OCR | Optional — only needed for image report uploads |

### Step 1 — Clone the Repository

```bash
git clone https://github.com/sricharan446/ai-developer-assistant.git
cd ai-developer-assistant
```

### Step 2 — Create Virtual Environment

```bash
python -m venv .venv

# Mac / Linux
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### Step 3 — Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4 — Configure `.env`

Create a `.env` file in the project root:

```env
GEMINI_API_KEY=your_key_here
MODEL_NAME=gemini-2.5-flash-lite
PORT=8000
CHROMA_DB_PATH=./chroma_db
```

> Make sure the file is named exactly `.env` (not `_env`). Python's `dotenv` only loads `.env`.

### Step 5 — Run

```bash
# Option A — direct
python app.py

# Option B — uvicorn with hot reload (recommended for development)
uvicorn app:app --reload --port 8000 --host 0.0.0.0
```

Open **http://localhost:8000**, sign up, and start chatting.

### Troubleshooting

| Error | Fix |
|---|---|
| `No module named 'fastapi'` | `pip install -r requirements.txt` |
| `GEMINI_API_KEY not set` | Check `.env` exists in same folder as `app.py` |
| `Port already in use` | Set `PORT=8001` in `.env` |
| Image OCR not working | Install OS-level Tesseract + uncomment `pytesseract` in requirements |
| ChromaDB crash on startup | Delete `chroma_db/` folder and restart |

---

## Project Structure

```
project/
 app.py ← Main server (FastAPI + all business logic)
 index.html ← Frontend UI (served by FastAPI at /)
 requirements.txt ← Python dependencies
 .env ← API keys & config
 users.json ← User auth store (username → SHA-256 hash + UUID token)

 knowledge_graph/
 graph.py ← NetworkX graph: 308 nodes, 328 edges, 21 clusters

 rag/
 rag_engine.py ← ChromaDB indexing + semantic search
 document_loader.py ← PDF and text file loader

 medical_data/ ← Pre-loaded knowledge base (8 .txt files)
 common_medicines.txt
 diabetes.txt
 diseases.txt
 fever.txt
 hypertension.txt
 medicines.txt
 symptoms.txt
 symptom_disease_map.txt

 chroma_db/ ← Persistent ChromaDB vector store (auto-generated)
 memory/ ← Per-user session & profile storage (auto-generated)
 {username}/
 profile.json
 {session_uuid}.json
 last_report.json
 uploads/ ← Uploaded medical reports (auto-generated)
```

---

## Environment Configuration

| Variable | Default | Description |
|---|---|---|
| `GEMINI_API_KEY` | *(required)* | Google Gemini API key |
| `MODEL_NAME` | `gemini-2.5-flash-lite` | Gemini model to use |
| `PORT` | `8000` | Server port |
| `CHROMA_DB_PATH` | `./chroma_db` | ChromaDB persistent storage path |

---

## API Reference

### Auth

| Method | Path | Body | Description |
|---|---|---|---|
| `POST` | `/api/signup` | `{username, password}` | Register new user (3–32 chars, alphanumeric) |
| `POST` | `/api/login` | `{username, password, age?, known_conditions?}` | Login → returns `{token, username}` |
| `POST` | `/api/logout` | `?token=` | Invalidates token server-side |

### Sessions

| Method | Path | Description |
|---|---|---|
| `GET` | `/api/sessions` | List all sessions with `last_activity` timestamp |
| `GET` | `/api/sessions/{sid}/history` | Get last 20 messages for a session |
| `DELETE` | `/api/sessions/{sid}` | Delete a session |

### Core Features

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/chat` | Main chat endpoint — runs the full pipeline |
| `POST` | `/api/upload` | Upload medical report (PDF / TXT / PNG / JPG, max 10MB) |
| `POST` | `/api/profile` | Save user age + known conditions *(token required)* |
| `GET` | `/api/health` | Gemini connectivity check |
| `GET` | `/api/models` | List available Gemini models |
| `GET` | `/api/nearby-hospitals` | Returns hospital finder links for given `lat` & `lng` |
| `GET` | `/api/pharmacy-links` | Returns pharmacy order links for a given `medicine` name |
| `GET` | `/` | Serves `index.html` |

---

## Chat Pipeline

When a message hits `POST /api/chat`, the system evaluates it in this exact order:

```
1. Auth validation → Token lookup in users.json
2. Input validation → Non-empty, max 2000 chars, stripped
3. Emergency detection → 21 keyword check → immediate alert + show_hospital_finder: true
4. Uploaded report → If user has a report and message contains report keywords
5. Symptom prediction → Score against 15 diseases + flood guard → Gemini + medication card
6. Knowledge Graph → Match against 115 terms → 308-node NetworkX lookup → Gemini
7. RAG search → ChromaDB semantic search → Gemini with context
8. Gemini direct → Clean medical prompt with last 20 messages of history
```

---

## Medical Intelligence

### Emergency Detector

Checks for **21** life-threatening keyword patterns:

- **Original 12:** `chest pain`, `breathing difficulty`, `shortness of breath`, `unconscious`, `stroke`, `heart attack`, `severe headache`, `blood vomiting`, `seizure`, `can't breathe`, `cannot breathe`, `no pulse`
- **Added 9:** `paralysis`, `unable to move`, `fainting`, `collapsed`, `suicidal`, `overdose`, `poisoning`, `anaphylaxis`, `allergic reaction`, `severe bleeding`, `choking`

Returns an immediate ` EMERGENCY ALERT` and triggers the Hospital Finder — bypasses all other pipeline logic.

### Symptom Predictor

Negation-aware keyword scoring against **15 diseases**: Diabetes, Hypertension, Migraine, Viral Infection, Common Cold, Flu, COVID, Malaria, Muscle Strain, Anxiety, Anemia, Gastroenteritis, Asthma, UTI, Dengue Fever.

- **Flood guard:** if >5 diseases trigger simultaneously, routes directly to Gemini
- **Negation guard:** `"no "`, `"not "`, `"without "` within 30 chars before a symptom suppresses that match
- **Confidence formula:** `(score / max_score) × 90 + 5` → adjusted by age (≥60 → +5) and known conditions (+7 if matching), capped at 100
- **Risk levels:** Low (<50%) · Moderate (50–74%) · High (75–84%) · Critical (≥85%)

### Lab Value Analyser

Regex extraction + threshold evaluation for **13 biomarkers**: HbA1c, Creatinine, Hemoglobin, Cholesterol, Vitamin D, TSH, WBC, RBC, Platelets, Blood Pressure — with named label and raw numeric pattern detection.

---

## Pharmacy Order Cards

After every medication card, PharmEasy links are upgraded into interactive order cards in the chat UI.

### How It Works

- `processPharmacyLinks()` runs on every assistant message after markdown render
- Hides only the `"Buy on PharmEasy"` list item, inserts a full pharmacy card below the medicine's properties block — Type, Dosage, Composition all remain visible
- Strip counter (1–9) updates the card's label to remind the user how many strips to add to cart

### Pharmacy Sites

| Site | URL Pattern |
|---|---|
| PharmEasy | `pharmeasy.in/search/all?name={medicine}` |
| 1mg (Tata) | `1mg.com/search/all?name={medicine}` |
| Netmeds | `netmeds.com/catalogsearch/result/all?q={medicine}` |

> **Note:** Direct order placement is not supported — pharmacy sites have no public ordering API. Cards deep-link to the product search page where the user completes purchase.

---

## Emergency Hospital Finder

When an emergency is detected, MediAssist automatically requests the user's geolocation and surfaces nearby care options.

### Flow

1. Emergency keyword matched → ` EMERGENCY ALERT` shown
2. Frontend calls `navigator.geolocation.getCurrentPosition()`
3. On success → fetches `/api/nearby-hospitals?lat=&lng=&city=` → renders 4 clickable site cards
4. On failure / permission denied → falls back to generic search links
5. Always shows ** Call 112 (Emergency)** and ** Call 102 (Ambulance)** quick-dial buttons

### Platform Links

| Platform | Purpose | URL Pattern |
|---|---|---|
| Google Maps | Map view with directions | `maps.google.com/maps/search/hospitals/@{lat},{lng},14z` |
| Google Search | Hospital search | `google.com/search?q=hospitals+near+me` |
| Practo | Book general physician appointment | `practo.com/search/doctors?results_type=doctor&q=[general+physician]&city={city}` |
| Justdial | Hospital directory with ratings | `justdial.com/{City}/Hospitals` |

---

## Knowledge Graph

Built with **NetworkX** as an undirected graph — **308 nodes · 328 edges · 21 clusters · 115 searchable terms**.

Supports exact match → case-insensitive → partial/substring match. Cross-cluster bridges connect shared symptoms like Fatigue → Anemia/Diabetes/Thyroid, Cough → Asthma/Cold.

**21 Clusters:** Fever/Viral · Diabetes · Hypertension · Common Cold · Headache/Migraine · Flu · COVID-19 · Malaria · Muscle Strain · Anxiety · Anaemia · Gastroenteritis · Asthma · UTI · Dengue · Acidity/GERD · Thyroid · Kidney · Liver · Cholesterol/Heart · Skin

---

## RAG Pipeline

- **Embedding model:** `all-MiniLM-L6-v2` via `sentence-transformers` (fully local, no API call)
- **Chunking:** 1000-char pieces, max 8 chunks (8000 chars) per file
- **Relevance filter:** only returns chunks with L2 distance < 1.2
- **Pre-loaded knowledge base:** 8 `.txt` files in `medical_data/` auto-indexed at startup

---

## Memory System

File-based persistence under `memory/{username}/`:

| File | Contents |
|---|---|
| `profile.json` | `{age, known_conditions}` |
| `{uuid}.json` | Session: `{id, user, created_at, name, messages[]}` |
| `last_report.json` | `{text, filename}` — last uploaded medical report |

- Sessions capped at `MAX_SESSIONS = 50` per user — oldest auto-deleted
- Session files capped at **50 messages** — prevents unbounded disk growth
- **History window:** last 20 messages sent to Gemini per request

---

## Authentication & Security

- Usernames validated with `^[a-zA-Z0-9_]{3,32}$`, empty usernames blocked
- Passwords stored as SHA-256 hash, minimum 6 characters
- UUID token generated at login, invalidated server-side on logout
- `/api/profile` requires token — prevents auth bypass
- `FileOperationsTool` path-restricted to `medical_data/`, `uploads/`, `memory/` — blocks `.env` and `users.json` access
- `asyncio.Lock()` prevents concurrent writes corrupting `users.json`
- Symptom flood guard: >5 disease matches → route to Gemini directly

---

## Dependencies

| Category | Packages |
|---|---|
| Web framework | `fastapi`, `uvicorn[standard]`, `pydantic`, `python-multipart`, `python-dotenv` |
| HTTP & scraping | `aiohttp`, `beautifulsoup4` |
| AI / LLM | `google-genai` |
| RAG & embeddings | `chromadb`, `sentence-transformers` |
| Knowledge graph | `networkx` |
| PDF reading | `pymupdf`, `pdfplumber`, `pypdf` |
| Image OCR *(optional)* | `pytesseract`, `Pillow` *(requires OS Tesseract install)* |

---

## Disclaimer

MediAssist is an AI-powered informational tool and is **not a substitute for professional medical advice, diagnosis, or treatment**. Always consult a qualified healthcare professional for medical decisions. In a genuine emergency, call **112** immediately.

---

*Built with using Python · FastAPI · Google Gemini · ChromaDB · NetworkX*