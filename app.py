"""
AI Medical Assistant - Single Server using Google Gemini API
Run: python app.py   then open http://localhost:8000
"""

import os
import json
import uuid
import csv
import re
import asyncio
import hashlib
import aiohttp
import uvicorn
import logging
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod

# ── FIX 1: load_dotenv() called at startup ────────────────────────────────────
from dotenv import load_dotenv
load_dotenv()

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

from fastapi import FastAPI, HTTPException, UploadFile, File, Query, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

from google import genai
from google.genai import types

from knowledge_graph.graph import query_graph
from rag.rag_engine import search_rag, add_document_to_rag

# ── Config ────────────────────────────────────────────────────────────────────
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "AIzaSyAhp-VEmJ4pm9FvYiONp1lPY16yIkN_6z0")
MODEL_NAME     = os.getenv("MODEL_NAME", "gemini-2.0-flash")
PORT           = int(os.getenv("PORT", "8000"))
MAX_SESSIONS   = 50   # FIX 9: cap sessions per user

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Add it to your .env file.")

gemini_client = genai.Client(api_key=GEMINI_API_KEY)

# Per-user uploaded report storage  { username: { "text": ..., "filename": ... } }
USER_REPORTS: Dict[str, Dict] = {}

# ── FIX 15: asyncio lock for users.json concurrent writes ────────────────────
_users_lock = asyncio.Lock()


# ── FIX 1 helper: Gemini call with retry on transient errors ─────────────────
async def gemini_generate(model: str, contents: str, temperature: float = 0.7,
                           max_tokens: int = 2048) -> str:
    """Call Gemini with up to 3 retries on 429/503 errors (exponential backoff)."""
    last_err = None
    for attempt in range(3):
        try:
            response = gemini_client.models.generate_content(
                model=model,
                contents=contents,
                config=types.GenerateContentConfig(
                    temperature=temperature,
                    max_output_tokens=max_tokens,
                )
            )
            return response.text
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if any(x in msg for x in ["429", "503", "rate", "quota", "unavailable"]):
                wait = 2 ** attempt   # 1s, 2s, 4s
                logger.warning(f"Gemini rate limit/error (attempt {attempt+1}): {e}. Retrying in {wait}s…")
                await asyncio.sleep(wait)
            else:
                break   # non-retryable error — fail immediately
    raise last_err


# ── Medical Data Loader ───────────────────────────────────────────────────────
def load_medical_data():
    folder = "medical_data"
    if not os.path.exists(folder):
        return
    for file in os.listdir(folder):
        if file.endswith(".txt"):
            add_document_to_rag(os.path.join(folder, file))
            print(f"Loaded: {file}")


# ── Symptom Prediction ────────────────────────────────────────────────────────
def predict_disease_from_symptoms(user_text: str) -> List[tuple]:
    """Score symptoms against known disease patterns. Returns top 5 matches."""
    symptom_map = {
        "diabetes":        {"urination": 3, "thirst": 3, "fatigue": 2, "blurred vision": 2},
        "hypertension":    {"chest pain": 3, "dizziness": 2, "headache": 1},
        "migraine":        {"light sensitivity": 3, "nausea": 2, "headache": 1},
        "muscle strain":   {"leg pain": 3, "muscle pain": 2},
        "viral infection": {"fever": 3, "fatigue": 2, "body pain": 2},
        "common cold":     {"fever": 2, "cough": 2, "runny nose": 2},
        "flu":             {"fever": 3, "body pain": 3, "fatigue": 2},
        "covid":           {"fever": 2, "dry cough": 2, "loss of smell": 4},
        "malaria":         {"fever": 3, "chills": 3, "sweating": 2},
        # FIX 16: expanded knowledge
        "anxiety":         {"palpitations": 3, "sweating": 2, "shortness of breath": 2, "dizziness": 1},
        "anemia":          {"fatigue": 3, "dizziness": 2, "pale skin": 3, "weakness": 2},
        "gastroenteritis": {"nausea": 3, "vomiting": 3, "diarrhea": 3, "stomach pain": 2},
        "asthma":          {"wheezing": 4, "shortness of breath": 3, "cough": 2},
        "urinary infection":{"burning urination": 4, "frequent urination": 3, "lower back pain": 2},
        "dengue":          {"fever": 3, "rash": 3, "joint pain": 3, "headache": 2},
    }

    def symptom_present(text: str, symptom: str) -> bool:
        idx = text.find(symptom)
        if idx == -1:
            return False
        context = text[max(0, idx - 30):idx]
        return not any(neg in context for neg in
                       ["no ", "not ", "without ", "don't have ", "do not have "])

    tl = user_text.lower()
    results = []
    for disease, symptoms in symptom_map.items():
        score = 0
        max_score = sum(symptoms.values())
        for symptom, weight in symptoms.items():
            if symptom_present(tl, symptom):
                score += weight
        if score > 0:
            results.append((disease, int((score / max_score) * 90 + 5)))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:5]


def adjust_confidence(base_conf: int, age: int, known_conditions: list,
                      disease: str) -> int:
    conf = base_conf
    if age >= 60:
        conf += 5
    if disease.lower() in [c.lower() for c in known_conditions]:
        conf += 7
    return min(conf, 100)


def check_emergency(user_text: str) -> bool:
    emergency_keywords = [
        "chest pain", "breathing difficulty", "shortness of breath",
        "unconscious", "stroke", "heart attack",
        "severe headache", "blood vomiting", "seizure",
        "can't breathe", "cannot breathe", "no pulse",
    ]
    return any(kw in user_text.lower() for kw in emergency_keywords)


# ── Lab Value Analyzer ────────────────────────────────────────────────────────
def analyze_lab_values(text: str) -> List[str]:
    findings = []
    checks = [
        (r"HbA1c[:\s]+([\d\.]+)",     lambda v: f"HbA1c is high ({v}%) → Diabetes risk" if v >= 6.5
                                                else (f"HbA1c borderline ({v}%) → Prediabetes risk" if v >= 5.7 else None)),
        (r"Creatinine[:\s]+([\d\.]+)", lambda v: f"Creatinine elevated ({v}) → Kidney concern" if v > 1.3 else None),
        (r"Hemoglobin[:\s]+([\d\.]+)", lambda v: f"Hemoglobin low ({v}) → Possible anemia" if v < 12 else None),
        (r"Cholesterol[:\s]+([\d\.]+)",lambda v: f"Cholesterol high ({v}) → Heart disease risk" if v > 200 else None),
        (r"Vitamin D[:\s]+([\d\.]+)",  lambda v: f"Vitamin D deficiency ({v}) → Bone health risk" if v < 20 else None),
        (r"TSH[:\s]+([\d\.]+)",        lambda v: f"TSH elevated ({v}) → Possible hypothyroidism" if v > 4
                                                else (f"TSH low ({v}) → Possible hyperthyroidism" if v < 0.4 else None)),
        (r"WBC[:\s]+([\d\.]+)",        lambda v: f"WBC elevated ({v}) → Possible infection" if v > 11000 else None),
        (r"RBC[:\s]+([\d\.]+)",        lambda v: f"RBC low ({v}) → Possible anemia" if v < 4 else None),
        (r"Platelets[:\s]+([\d\.]+)",  lambda v: f"Platelets low ({v}) → Bleeding risk" if v < 150000
                                                else (f"Platelets high ({v}) → Clotting risk" if v > 450000 else None)),
    ]
    for pattern, evaluator in checks:
        match = re.search(pattern, text, re.IGNORECASE)
        if match:
            try:
                result = evaluator(float(match.group(1)))
                if result:
                    findings.append(result)
            except ValueError:
                pass
    bp = re.search(r"(\d{2,3})/(\d{2,3})", text)
    if bp:
        s, d = int(bp.group(1)), int(bp.group(2))
        if s >= 140 or d >= 90:
            findings.append(f"Blood Pressure high ({s}/{d}) → Hypertension risk")
    return findings


# ── Tools ─────────────────────────────────────────────────────────────────────
class BaseTool(ABC):
    def __init__(self): self.description = ""
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]: pass
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]: pass


class WebSearchTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.description = "Search the web for current medical information"

    def get_schema(self):
        return {"query": "string (required)", "num_results": "integer (optional, default 5)"}

    async def execute(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            async with aiohttp.ClientSession() as s:
                async with s.post(
                    "https://html.duckduckgo.com/html/",
                    data={"q": query}, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)
                ) as r:
                    html = await r.text()
            soup = BeautifulSoup(html, "html.parser")
            results = []
            for div in soup.find_all("div", class_="result")[:num_results]:
                t  = div.find("a", class_="result__a")
                sn = div.find("a", class_="result__snippet")
                if t:
                    results.append({
                        "title":   t.get_text(strip=True),
                        "url":     t.get("href", ""),
                        "snippet": sn.get_text(strip=True) if sn else ""
                    })
            return {"success": True, "query": query, "results": results}
        except Exception as e:
            logger.error(f"WebSearch error: {e}")
            return {"success": False, "error": "Web search unavailable", "results": []}


class FileOperationsTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.description = "Read, write, analyze, and search files"

    def get_schema(self):
        return {
            "operation": "read|write|analyze|search",
            "file_path": "string",
            "content": "string (for write)",
            "search_term": "string (for search)"
        }

    async def execute(self, operation: str, **kw) -> Dict[str, Any]:
        try:
            if operation == "read":    return await self._read(kw.get("file_path"))
            if operation == "write":   return await self._write(kw.get("file_path"), kw.get("content", ""))
            if operation == "analyze": return await self._analyze(kw.get("file_path"))
            if operation == "search":  return await self._search(kw.get("file_path"), kw.get("search_term", ""))
            return {"success": False, "error": f"Unknown operation: {operation}"}
        except Exception as e:
            logger.error(f"FileOps error: {e}")
            return {"success": False, "error": "File operation failed"}

    async def _read(self, fp):
        if not fp: return {"success": False, "error": "No file path provided"}
        p = Path(fp)
        if not p.exists(): return {"success": False, "error": "File not found"}
        try:
            if p.suffix == ".json":
                with open(p) as fh:
                    c = json.load(fh)
            elif p.suffix == ".csv":
                with open(p) as f:
                    c = list(csv.DictReader(f))[:100]
            else:
                with open(p, encoding="utf-8", errors="ignore") as f:
                    c = f.read()[:8000]
            return {"success": True, "content": c, "size": p.stat().st_size}
        except Exception as e:
            return {"success": False, "error": "Could not read file"}

    async def _write(self, fp, content):
        if not fp: return {"success": False, "error": "No file path provided"}
        p = Path(fp)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"success": True, "file_path": str(p), "message": "Written successfully"}

    async def _analyze(self, fp):
        r = await self._read(fp)
        if not r.get("success"): return r
        c = str(r.get("content", ""))
        return {"success": True, "analysis": {
            "lines": len(c.split("\n")),
            "words": len(c.split()),
            "chars": len(c)
        }}

    async def _search(self, fp, term):
        if not term: return {"success": False, "error": "No search term provided"}
        r = await self._read(fp)
        if not r.get("success"): return r
        lines = str(r.get("content", "")).split("\n")
        matches = [{"line": i + 1, "content": l.strip()}
                   for i, l in enumerate(lines) if term.lower() in l.lower()]
        return {"success": True, "matches": matches[:30], "count": len(matches)}


# ── Memory Manager ────────────────────────────────────────────────────────────
class MemoryManager:
    def __init__(self):
        self.base_path = Path("memory")
        self.base_path.mkdir(exist_ok=True)

    def _user_path(self, username: str) -> Path:
        safe = re.sub(r'[^a-zA-Z0-9_\-]', '_', username)[:32]
        p = self.base_path / safe
        p.mkdir(exist_ok=True)
        return p

    def _session_file(self, username: str, sid: str) -> Path:
        return self._user_path(username) / f"{sid}.json"

    def create_session(self, username: str) -> str:
        # FIX 9: enforce MAX_SESSIONS — delete oldest if over limit
        sessions = self.list_sessions(username)
        if len(sessions) >= MAX_SESSIONS:
            oldest = sorted(sessions, key=lambda x: x.get("created", ""))
            for old in oldest[:len(sessions) - MAX_SESSIONS + 1]:
                self.delete_session(username, old["id"])

        sid = str(uuid.uuid4())
        data = {
            "id": sid, "user": username,
            "created_at": datetime.now().isoformat(),
            "name": "New Chat", "messages": []
        }
        with open(self._session_file(username, sid), "w") as f:
            json.dump(data, f, indent=2)
        return sid

    def set_session_name(self, username: str, sid: str, name: str):
        fpath = self._session_file(username, sid)
        if not fpath.exists(): return
        with open(fpath) as f:
            data = json.load(f)
        data["name"] = name[:40]
        with open(fpath, "w") as f:
            json.dump(data, f, indent=2)

    def add_message(self, username: str, sid: str, role: str, content: str,
                    meta: dict = None):
        fpath = self._session_file(username, sid)
        if not fpath.exists(): return
        with open(fpath) as f:
            data = json.load(f)
        msg = {"role": role, "content": content, "time": datetime.now().isoformat()}
        if meta:
            msg["meta"] = meta
        data["messages"].append(msg)
        with open(fpath, "w") as f:
            json.dump(data, f, indent=2)

    def get_history(self, username: str, sid: str) -> List[dict]:
        fpath = self._session_file(username, sid)
        if not fpath.exists(): return []
        with open(fpath) as f:
            data = json.load(f)
        return [{"role": m["role"], "content": m["content"]}
                for m in data["messages"]]

    def list_sessions(self, username: str) -> List[dict]:
        sessions = []
        for f in self._user_path(username).glob("*.json"):
            if f.name == "profile.json": continue
            try:
                with open(f) as fh:
                    d = json.load(fh)
                if "id" not in d: continue
                sessions.append({
                    "id":            d["id"],
                    "name":          d.get("name", "New Chat"),
                    "message_count": len(d.get("messages", [])),
                    "created":       d.get("created_at")
                })
            except Exception:
                continue
        return sorted(sessions, key=lambda x: x.get("created", ""), reverse=True)

    def save_profile(self, username: str, profile_data: dict):
        fpath = self._user_path(username) / "profile.json"
        with open(fpath, "w") as f:
            json.dump(profile_data, f, indent=2)

    def load_profile(self, username: str) -> Optional[dict]:
        fpath = self._user_path(username) / "profile.json"
        if not fpath.exists(): return None
        with open(fpath) as f:
            return json.load(f)

    def delete_session(self, username: str, sid: str) -> bool:
        fpath = self._session_file(username, sid)
        if fpath.exists():
            fpath.unlink()
            return True
        return False

    # FIX 13: persist report to session so it survives server restart
    def save_report(self, username: str, report: dict):
        fpath = self._user_path(username) / "last_report.json"
        with open(fpath, "w") as f:
            json.dump(report, f, indent=2)

    def load_report(self, username: str) -> Optional[dict]:
        fpath = self._user_path(username) / "last_report.json"
        if not fpath.exists(): return None
        with open(fpath) as f:
            return json.load(f)


# ── AI Agent ──────────────────────────────────────────────────────────────────
class AIAgent:
    def __init__(self):
        self.tools = {
            "web_search":      WebSearchTool(),
            "file_operations": FileOperationsTool()
        }

    def _sys(self) -> str:
        tool_docs = ""
        for name, tool in self.tools.items():
            tool_docs += f"\n### {name}\n{tool.description}\nParams: {json.dumps(tool.get_schema())}\n"
        return (
            "You are a medical AI triage assistant. Provide health guidance based on symptoms, "
            "lab reports, medical knowledge, and retrieved documents.\n\nTOOLS:\n" + tool_docs +
            '\nTo use a tool respond ONLY with JSON: {"tool":"name","params":{"key":"value"}}\n'
            "After receiving tool results, answer naturally. If no tool is needed, answer directly."
        )

    async def _call(self, messages: List[dict], model: str = None) -> str:
        conversation = f"System: {self._sys()}\n\n"
        for msg in messages:
            if msg["role"] == "system":
                continue
            elif msg["role"] == "user":
                conversation += f"User: {msg['content']}\n\n"
            elif msg["role"] == "assistant":
                conversation += f"Assistant: {msg['content']}\n\n"
        conversation += "Assistant:"
        return await gemini_generate(model or MODEL_NAME, conversation)

    def _parse_tool(self, text: str) -> Optional[dict]:
        s = text.find("{")
        e = text.rfind("}") + 1
        if s == -1 or e == 0:
            return None
        try:
            obj = json.loads(text[s:e])
            if "tool" in obj and "params" in obj:
                return obj
        except json.JSONDecodeError:
            pass
        return None

    async def process(self, message: str, history: List[dict] = None,
                      model: str = None) -> dict:
        msgs = [{"role": "system", "content": self._sys()}]
        for h in (history or []):
            if h["role"] in ("user", "assistant"):
                msgs.append(h)
        msgs.append({"role": "user", "content": message})

        used_tools = []
        for _ in range(4):
            reply = await self._call(msgs, model)
            tool_call = self._parse_tool(reply)
            if not tool_call:
                return {"response": reply, "tools_used": used_tools}
            name = tool_call.get("tool", "")
            if name not in self.tools:
                return {"response": reply, "tools_used": used_tools}
            used_tools.append(name)
            result = await self.tools[name].execute(**tool_call.get("params", {}))
            msgs.append({"role": "assistant", "content": reply})
            msgs.append({"role": "user", "content":
                f"Tool result for {name}:\n{json.dumps(result, indent=2)}\nNow answer using this."})

        final = await self._call(msgs, model)
        return {"response": final, "tools_used": used_tools}

    async def check(self) -> bool:
        try:
            r = await gemini_generate(MODEL_NAME, "ping", max_tokens=10)
            return bool(r)
        except Exception:
            return False


# ── Auth ──────────────────────────────────────────────────────────────────────
USERS_FILE = "users.json"


async def load_users() -> dict:
    if not os.path.exists(USERS_FILE):
        return {}
    try:
        with open(USERS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


async def save_users(users: dict):
    # FIX 15: lock to prevent concurrent write corruption
    async with _users_lock:
        with open(USERS_FILE, "w") as f:
            json.dump(users, f, indent=2)


def hash_password(pw: str) -> str:
    return hashlib.sha256(pw.encode()).hexdigest()


async def get_current_user(token: str = Query(None)) -> str:
    if not token:
        raise HTTPException(401, "Token missing")
    users = await load_users()
    for username, data in users.items():
        if data.get("token") == token:
            return username
    raise HTTPException(401, "Unauthorized — please login")


# ── FastAPI App ───────────────────────────────────────────────────────────────
app    = FastAPI(title="Medical Assistant API")
agent  = AIAgent()
memory = MemoryManager()
load_medical_data()

app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# ── Pydantic Models ───────────────────────────────────────────────────────────
class SignupRequest(BaseModel):
    username: str
    password: str

class LoginRequest(BaseModel):
    username: str
    password: str
    age: Optional[int] = None
    known_conditions: Optional[List[str]] = []

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    token: str
    model: Optional[str] = None   # FIX 17: per-request model selection

class ChatResponse(BaseModel):
    response: str
    session_id: str
    tools_used: List[str]
    timestamp: str


# ── Auth Routes ───────────────────────────────────────────────────────────────
@app.post("/api/signup")
async def signup(req: SignupRequest):
    # FIX 3: username length + format validation
    if not re.match(r'^[a-zA-Z0-9_]{3,32}$', req.username):
        raise HTTPException(400,
            "Username must be 3–32 characters and contain only letters, numbers, or underscores.")
    if len(req.password.strip()) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")

    users = await load_users()
    if req.username in users:
        raise HTTPException(400, "Username already taken.")
    users[req.username] = {"password": hash_password(req.password)}
    await save_users(users)
    return {"status": "created"}


@app.post("/api/login")
async def login(req: LoginRequest):
    users = await load_users()
    if req.username not in users:
        raise HTTPException(401, "Invalid username or password")
    if users[req.username].get("password") != hash_password(req.password):
        raise HTTPException(401, "Invalid username or password")
    token = str(uuid.uuid4())
    users[req.username]["token"] = token
    await save_users(users)
    memory.save_profile(req.username, {
        "age": req.age or 30,
        "known_conditions": req.known_conditions or []
    })
    return {"token": token, "username": req.username}


# ── Logout ────────────────────────────────────────────────────────────────────
@app.post("/api/logout")
async def logout(token: str = Query(None)):
    if not token:
        return {"status": "ok"}
    users = await load_users()
    for data in users.values():
        if data.get("token") == token:
            data.pop("token", None)
            await save_users(users)
            break
    # Also clear in-memory report for this token's user
    return {"status": "logged out"}


# ── Profile ───────────────────────────────────────────────────────────────────
@app.post("/api/profile")
async def save_profile_endpoint(req: dict):
    username = req.get("username")
    profile  = req.get("profile")
    if not username or not profile:
        raise HTTPException(400, "Invalid profile data")
    memory.save_profile(username, profile)
    return {"status": "Profile saved"}


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    ok = await agent.check()
    return {
        "status": "online",
        "gemini": "connected" if ok else "not connected",
        "model":  MODEL_NAME,
        "gemini_ready": ok
    }


# ── Models ────────────────────────────────────────────────────────────────────
@app.get("/api/models")
async def list_models():
    return {"models": [
        "gemini-2.5-flash-lite",
        "gemini-2.5-flash-image",
        "gemini-3-flash-preview",
        "gemini-3-pro-preview",
    ]}


# ── Sessions ──────────────────────────────────────────────────────────────────
@app.get("/api/sessions")
async def list_sessions(username: str = Depends(get_current_user)):
    return memory.list_sessions(username)


@app.get("/api/sessions/{sid}/history")
async def get_history(sid: str, username: str = Depends(get_current_user)):
    h = memory.get_history(username, sid)
    if h is None:
        raise HTTPException(404, "Session not found")
    return {"session_id": sid, "history": h}


@app.delete("/api/sessions/{sid}")
async def del_session(sid: str, username: str = Depends(get_current_user)):
    if not memory.delete_session(username, sid):
        raise HTTPException(404, "Session not found")
    return {"status": "deleted"}


# ── Chat ──────────────────────────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):

    # ── Auth ──
    users = await load_users()
    username = next((u for u, d in users.items() if d.get("token") == req.token), None)
    if not username:
        raise HTTPException(401, "Unauthorized — please login")

    # ── Input validation ──
    if not req.message or not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    if len(req.message) > 2000:
        raise HTTPException(400, "Message too long (max 2000 characters).")

    # FIX 17: use per-request model if provided, else default
    active_model = req.model if req.model else MODEL_NAME

    # ── Session ──
    sid = req.session_id or memory.create_session(username)
    full_history = memory.get_history(username, sid) or []
    history = full_history[-20:]   # last 10 exchanges
    if not full_history:
        memory.set_session_name(username, sid, req.message)

    # ── Emergency Check ──
    if check_emergency(req.message):
        resp = (
            "🚨 EMERGENCY ALERT\n\n"
            "Your symptoms may indicate a serious or life-threatening condition.\n\n"
            "🔴 Risk Level: Critical\n\n"
            "Please seek immediate medical attention.\n"
            "Call emergency services (112 / 108) or go to the nearest hospital NOW.\n\n"
            "⚠️ Disclaimer: AI guidance only. Do not delay professional medical care."
        )
        memory.add_message(username, sid, "user", req.message)
        memory.add_message(username, sid, "assistant", resp,
                           {"tools_used": ["Emergency Detector"]})
        return ChatResponse(response=resp, session_id=sid,
                            tools_used=["Emergency Detector"],
                            timestamp=datetime.now().isoformat())

    # ── Uploaded Report — checked BEFORE symptom predictor & RAG ──
    report_keywords = [
        "report", "result", "findings", "uploaded", "my file", "summarise",
        "summarize", "lab", "test", "scan", "document", "analysis", "blood test",
        "what does", "explain my", "tell me about my"
    ]
    # FIX 13: try memory first, then in-memory dict (covers restart)
    user_report = USER_REPORTS.get(username) or memory.load_report(username)
    if user_report and any(kw in req.message.lower() for kw in report_keywords):
        prompt = (
            f"You are a medical AI assistant. The user uploaded a medical report.\n\n"
            f"Uploaded Report ({user_report['filename']}):\n{user_report['text']}\n\n"
            f"User question: {req.message}\n\n"
            "Answer specifically from the uploaded report. Reference actual values."
        )
        try:
            text = await gemini_generate(active_model, prompt)
            result = {"response": text, "tools_used": ["Uploaded Report"]}
        except Exception as e:
            logger.error(f"Gemini report error: {e}")
            raise HTTPException(500, "AI service temporarily unavailable. Please try again.")
        memory.add_message(username, sid, "user", req.message)
        memory.add_message(username, sid, "assistant", result["response"],
                           {"tools_used": result["tools_used"]})
        return ChatResponse(response=result["response"], session_id=sid,
                            tools_used=result["tools_used"],
                            timestamp=datetime.now().isoformat())

    # ── Profile ──
    profile          = memory.load_profile(username) or {}
    age              = profile.get("age", 30)
    known_conditions = profile.get("known_conditions", [])

    # ── Symptom Prediction ──
    prediction_list = predict_disease_from_symptoms(req.message)
    prediction_list = [
        (d, adjust_confidence(c, age, known_conditions, d))
        for d, c in prediction_list
    ]
    prediction_list.sort(key=lambda x: x[1], reverse=True)
    prediction_list = prediction_list[:3]

    if prediction_list:
        top_disease, top_confidence = prediction_list[0]

        def categorize_risk(c):
            if c >= 85: return "🔴 Critical"
            if c >= 75: return "🟠 High"
            if c >= 50: return "🟡 Moderate"
            return "🟢 Low"

        risk_level      = categorize_risk(top_confidence)
        prediction_text = "\n".join(
            [f"{i+1}. {d.title()} ({c}%)" for i, (d, c) in enumerate(prediction_list)]
        )

        explanation_prompt = f"""You are a clinical triage AI providing informational health guidance.

Patient Profile:
- Age: {age}
- Known Conditions: {', '.join(known_conditions) if known_conditions else 'None'}

Reported Symptoms: {req.message}

Predicted Possible Conditions:
{prediction_text}

Respond EXACTLY in this format:

🩺 Most Likely Condition:
(name + short explanation)

🔍 Other Possible Conditions:
(list 2–3 alternatives with brief reason)

📊 Risk Level: (Low / Moderate / High / Critical)

🔎 Why This Risk Level:
(explain considering age, symptoms, known conditions)

💊 Immediate Precautions:
(simple actionable advice)

🏥 When to See a Doctor:
(clear medical guidance)

⚠️ Disclaimer: AI-generated health guidance, not a medical diagnosis. Consult a doctor."""

        try:
            explanation = await agent.process(explanation_prompt, history, active_model)
        except Exception as e:
            logger.error(f"Gemini symptom error: {e}")
            raise HTTPException(500, "AI service temporarily unavailable. Please try again.")

        conditions_text = "\n".join(
            [f"{i+1}. {d.title()} ({c}%)" for i, (d, c) in enumerate(prediction_list)]
        )
        final_response = (
            f"🩺 Possible Conditions:\n{conditions_text}\n\n"
            f"📊 Risk Level: {risk_level}\n\n"
            f"{explanation['response']}"
        )
        memory.add_message(username, sid, "user", req.message)
        memory.add_message(username, sid, "assistant", final_response,
                           {"tools_used": ["Symptom Predictor"]})
        return ChatResponse(response=final_response, session_id=sid,
                            tools_used=["Symptom Predictor"],
                            timestamp=datetime.now().isoformat())

    # ── Knowledge Graph — FIX 8: collect ALL matching terms ──────────────────
    medical_terms = [
        "fever", "diabetes", "bp", "covid", "cold", "cough",
        "headache", "migraine", "vomiting", "infection",
        "leg pain", "muscle pain", "joint pain",
        "anxiety", "anemia", "asthma", "dengue"
    ]
    user_text_lower = req.message.lower()
    kg_parts = []
    for term in medical_terms:
        if term in user_text_lower:
            kg_resp = query_graph(term.capitalize())
            if kg_resp and "No medical knowledge" not in kg_resp:
                kg_parts.append(kg_resp)

    if kg_parts:
        kg_combined = "\n\n".join(kg_parts)
        memory.add_message(username, sid, "user", req.message)
        memory.add_message(username, sid, "assistant", kg_combined,
                           {"tools_used": ["Medical KG"]})
        return ChatResponse(response=kg_combined, session_id=sid,
                            tools_used=["Medical KG"],
                            timestamp=datetime.now().isoformat())

    # ── RAG Search ──
    rag_context = ""
    try:
        rag_results = search_rag(req.message)
        if rag_results and rag_results[0] and rag_results[0][0].strip():
            rag_context = rag_results[0][0].strip()
    except Exception:
        rag_context = ""

    try:
        if rag_context:
            prompt = (
                f"Use this medical context to answer the question.\n\n"
                f"Context:\n{rag_context}\n\n"
                f"Question: {req.message}\n\n"
                "If the context does not contain a relevant answer, say so and answer from general knowledge."
            )
            text = await gemini_generate(active_model, prompt)
            result = {"response": text, "tools_used": ["RAG"]}
        else:
            result = await agent.process(req.message, history, active_model)
    except Exception as e:
        logger.error(f"Gemini chat error: {e}")
        raise HTTPException(500, "AI service temporarily unavailable. Please try again.")

    memory.add_message(username, sid, "user", req.message)
    memory.add_message(username, sid, "assistant", result["response"],
                       {"tools_used": result.get("tools_used", [])})

    return ChatResponse(
        response=result["response"],
        session_id=sid,
        tools_used=result.get("tools_used", []),
        timestamp=datetime.now().isoformat()
    )


# ── File Upload ───────────────────────────────────────────────────────────────
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), token: str = Query(None)):
    upload_username = None
    if token:
        users = await load_users()
        upload_username = next(
            (u for u, d in users.items() if d.get("token") == token), None
        )

    try:
        os.makedirs("uploads", exist_ok=True)
        # Sanitize filename + add timestamp to prevent overwrites (FIX 5)
        ts       = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_name = os.path.basename(file.filename or "upload")
        stem     = Path(raw_name).stem
        ext      = Path(raw_name).suffix.lower()
        safe_stem = re.sub(r'[^\w\-]', '_', stem)[:60]
        safe_name = f"{safe_stem}_{ts}{ext}" if safe_stem else f"upload_{ts}{ext}"
        if not safe_name or safe_name.startswith('.'):
            safe_name = f"upload_{uuid.uuid4().hex[:8]}"
        file_path = os.path.join("uploads", safe_name)

        content = await file.read()

        if len(content) > 10 * 1024 * 1024:
            return {"status": "error", "message": "File too large. Maximum 10MB."}

        with open(file_path, "wb") as f:
            f.write(content)

        # ── Extract text ──
        extracted_text = ""
        fname = (file.filename or "").lower()

        if fname.endswith(".txt"):
            extracted_text = content.decode("utf-8", errors="ignore")

        elif fname.endswith(".pdf"):
            try:
                import pdfplumber
                with pdfplumber.open(file_path) as pdf:
                    for page in pdf.pages:
                        t = page.extract_text()
                        if t:
                            extracted_text += t + "\n"
            except ImportError:
                doc = fitz.open(file_path)
                for page in doc:
                    extracted_text += page.get_text()
                doc.close()

        elif fname.endswith((".png", ".jpg", ".jpeg")):
            try:
                import pytesseract
                from PIL import Image
                extracted_text = pytesseract.image_to_string(Image.open(file_path))
            except ImportError:
                return {"status": "error", "message": "pytesseract not installed for image OCR"}

        else:
            return {"status": "error",
                    "message": f"Unsupported format: {file.filename}. Supported: .txt, .pdf, .png, .jpg"}

        if not extracted_text.strip():
            return {"status": "error", "message": "No readable text found in the file"}

        report_text = extracted_text[:8000]
        report_obj  = {"text": report_text, "filename": file.filename}

        # FIX 13: store in both memory dict and disk
        if upload_username:
            USER_REPORTS[upload_username] = report_obj
            memory.save_report(upload_username, report_obj)

        findings      = analyze_lab_values(extracted_text)
        findings_text = "\n".join(findings) if findings else "No abnormal lab values detected."

        medical_prompt = f"""You are an expert medical AI trained to interpret laboratory reports.

Medical Report:
{report_text}

Detected Lab Findings:
{findings_text}

Instructions:
1. Explain what this report contains.
2. Highlight abnormal or concerning values.
3. Explain what those values mean in simple language.
4. Suggest possible health risks.
5. Provide general health precautions.

Respond strictly in this format:

🧾 Report Overview:
(short explanation)

⚠️ Abnormal Values Detected:
(list abnormal values, or "None detected" if all normal)

🩺 Possible Health Risks:
(list possible risks)

💊 Health Advice:
(simple precautions)

🏥 When to Consult a Doctor:
(clear guidance)

⚠️ Disclaimer: AI-generated analysis. Not a medical diagnosis. Consult a doctor."""

        try:
            analysis = await gemini_generate(MODEL_NAME, medical_prompt)
        except Exception as e:
            logger.error(f"Gemini upload error: {e}")
            return {"status": "error", "message": "AI analysis temporarily unavailable. Report saved — try asking about it in chat."}

        return {
            "status":       "success",
            "analysis":     analysis,
            "lab_findings": findings,
            "summary":      analysis
        }

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return {"status": "error", "message": "Upload failed. Please try again."}


# ── Frontend ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 52)
    print("  Medical Assistant — Google Gemini Edition")
    print("=" * 52)
    print(f"\n  Model  : {MODEL_NAME}")
    print(f"  Browser: http://localhost:{PORT}")
    print("  Stop   : CTRL+C\n")
    print("=" * 52)
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)