"""
AI Agent - Single Server using Ollama (FREE & Local)
Run: python app.py   then open http://localhost:8000
"""

import os
import json
import uuid
import csv
import re
import hashlib
import requests
import aiohttp
import uvicorn
import shutil
import logging
logging.getLogger().setLevel(logging.ERROR)
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod

from fastapi import FastAPI, HTTPException, UploadFile, File, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from fastapi import Depends, Query

from bs4 import BeautifulSoup

import fitz  # PDF reader

from knowledge_graph.graph import query_graph
from rag.rag_engine import search_rag, add_document_to_rag

OLLAMA_URL  = os.getenv("OLLAMA_URL",  "http://localhost:11434")
MODEL_NAME  = os.getenv("MODEL_NAME",  "llama3.2")
PORT        = int(os.getenv("PORT",    "8000"))
MEMORY_PATH = os.getenv("MEMORY_PATH", "/tmp/agent_memory")


def load_medical_data():
    folder = "medical_data"
    for file in os.listdir(folder):
        if file.endswith(".txt"):
            path = os.path.join(folder, file)
            add_document_to_rag(path)
            print(f"Loaded: {file}")


def read_pdf_text(file_path):
    text = ""
    try:
        doc = fitz.open(file_path)
        for page in doc:
            text += page.get_text()
        doc.close()
    except:
        text = ""
    return text

def predict_disease(text):
    text = text.lower()

    if "fever" in text and "cough" in text:
        return "Possible viral infection or COVID"

    if "headache" in text and "vomiting" in text:
        return "Possible migraine"

    if "chest pain" in text:
        return "Possible heart-related issue"

    if "thirst" in text and "urination" in text:
        return "Possible diabetes"

    return None

# ── Tools ────────────────────────────────────────────────────────────────────
class BaseTool(ABC):
    def __init__(self): self.description = ""
    @abstractmethod
    async def execute(self, **kwargs) -> Dict[str, Any]: pass
    @abstractmethod
    def get_schema(self) -> Dict[str, Any]: pass

class WebSearchTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.description = "Search the web for current information"
    def get_schema(self):
        return {"query": "string (required)", "num_results": "integer (optional, default 5)"}
    async def execute(self, query: str, num_results: int = 5) -> Dict[str, Any]:
        try:
            headers = {"User-Agent": "Mozilla/5.0"}
            async with aiohttp.ClientSession() as s:
                async with s.post("https://html.duckduckgo.com/html/",
                    data={"q": query}, headers=headers,
                    timeout=aiohttp.ClientTimeout(total=10)) as r:
                    html = await r.text()
            soup = BeautifulSoup(html, "html.parser")
            results = []
            for div in soup.find_all("div", class_="result")[:num_results]:
                t = div.find("a", class_="result__a")
                sn = div.find("a", class_="result__snippet")
                if t:
                    results.append({"title": t.get_text(strip=True),
                                    "url": t.get("href",""),
                                    "snippet": sn.get_text(strip=True) if sn else ""})
            return {"success": True, "query": query, "results": results}
        except Exception as e:
            return {"success": False, "error": str(e), "results": []}

class FileOperationsTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.description = "Read, write, and analyze files"
    def get_schema(self):
        return {"operation": "read|write|analyze|search",
                "file_path": "string", "content": "string", "search_term": "string"}
    async def execute(self, operation: str, **kw) -> Dict[str, Any]:
        try:
            if operation == "read":    return await self._read(kw.get("file_path"))
            if operation == "write":   return await self._write(kw.get("file_path"), kw.get("content",""))
            if operation == "analyze": return await self._analyze(kw.get("file_path"))
            if operation == "search":  return await self._search(kw.get("file_path"), kw.get("search_term",""))
            return {"success": False, "error": "Unknown operation"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    async def _read(self, fp):
        if not fp: return {"success": False, "error": "No path"}
        p = Path(fp)
        if not p.exists(): return {"success": False, "error": f"Not found: {fp}"}
        if p.suffix == ".json": c = json.load(open(p))
        elif p.suffix == ".csv":
            with open(p) as f: c = list(csv.DictReader(f))[:100]
        else: c = open(p, encoding="utf-8").read()[:8000]
        return {"success": True, "content": c, "size": p.stat().st_size}
    async def _write(self, fp, content):
        if not fp: return {"success": False, "error": "No path"}
        p = Path(fp); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(content, encoding="utf-8")
        return {"success": True, "file_path": str(p), "message": "Written successfully"}
    async def _analyze(self, fp):
        r = await self._read(fp)
        if not r.get("success"): return r
        c = str(r.get("content",""))
        return {"success": True, "analysis": {"lines": len(c.split("\n")),
                "words": len(c.split()), "chars": len(c)}}
    async def _search(self, fp, term):
        r = await self._read(fp)
        if not r.get("success"): return r
        lines = str(r.get("content","")).split("\n")
        m = [{"line": i+1, "content": l.strip()}
             for i,l in enumerate(lines) if term.lower() in l.lower()]
        return {"success": True, "matches": m[:30], "count": len(m)}

# ── Memory ───────────────────────────────────────────────────────────────────
class MemoryManager:
    def __init__(self):
        self.base_path = Path("memory")
        self.base_path.mkdir(exist_ok=True)

    def _user_path(self, username):
        p = self.base_path / username
        p.mkdir(exist_ok=True)
        return p

    def _session_file(self, username, sid):
        return self._user_path(username) / f"{sid}.json"

    # 🟢 create session
    def create_session(self, username):
        sid = str(uuid.uuid4())
        data = {
            "id": sid,
            "user": username,
            "created_at": datetime.now().isoformat(),
            "name": "New Chat",
            "messages": []
        }
        with open(self._session_file(username, sid), "w") as f:
            json.dump(data, f, indent=2)
        return sid
    def set_session_name(self, username, sid, name):
        fpath = self._session_file(username, sid)
        if not fpath.exists():
            return

        data = json.load(open(fpath))
        data["name"] = name[:40]  # limit length

        with open(fpath, "w") as f:
            json.dump(data, f, indent=2)

    # 🟢 add message
    def add_message(self, username, sid, role, content, meta=None):
        fpath = self._session_file(username, sid)

        if not fpath.exists():
            return

        data = json.load(open(fpath))
        msg = {
            "role": role,
            "content": content,
            "time": datetime.now().isoformat()
        }
        if meta:
            msg["meta"] = meta

        data["messages"].append(msg)

        with open(fpath, "w") as f:
            json.dump(data, f, indent=2)

    # 🟢 history
    def get_history(self, username, sid):
        fpath = self._session_file(username, sid)
        if not fpath.exists():
            return []

        data = json.load(open(fpath))
        return [{"role":m["role"],"content":m["content"]} for m in data["messages"]]

    # 🟢 list sessions
    def list_sessions(self, username):
        upath = self._user_path(username)
        sessions = []

        for f in upath.glob("*.json"):

        # Skip profile.json
            if f.name == "profile.json":
                continue

            try:
                d = json.load(open(f))

                if "id" not in d:
                    continue

                sessions.append({
                "id": d.get("id"),
                "name": d.get("name", "New Chat"),
                "message_count": len(d.get("messages", [])),
                "created": d.get("created_at")
            })

            except Exception:
                continue

        return sessions
    def get_profile_file(self, username):
        return self._user_path(username) / "profile.json"

    def save_profile(self, username, profile_data):
        fpath = self.get_profile_file(username)
        with open(fpath, "w") as f:
            json.dump(profile_data, f, indent=2)

    def load_profile(self, username):
        fpath = self.get_profile_file(username)
        if not fpath.exists():
            return None
        return json.load(open(fpath))

    # 🟢 delete
    def delete_session(self, username, sid):
        fpath = self._session_file(username, sid)

        if fpath.exists():
            fpath.unlink()
            return True

        return False


def predict_disease_from_symptoms(user_text):
    symptom_map = {
        "diabetes": {
            "urination": 3,
            "thirst": 3,
            "fatigue": 2,
            "blurred vision": 2
        },
        "hypertension": {
            "chest pain": 3,
            "dizziness": 2,
            "headache": 1
        },
        "migraine": {
            "light sensitivity": 3,
            "nausea": 2,
            "headache": 1
        },


        "muscle strain": {
        "leg pain": 3,
        "muscle pain": 2
        },
        

    "viral infection": {
        "fever": 3,
        "fatigue": 2,
        "body pain": 2
    },

    "common cold": {
        "fever": 2,
        "cough": 2,
        "runny nose": 2
    },

    "flu": {
        "fever": 3,
        "body pain": 3,
        "fatigue": 2
    },

    "covid": {
        "fever": 2,
        "dry cough": 2,
        "loss of smell": 4
    },

    "malaria": {
        "fever": 3,
        "chills": 3,
        "sweating": 2
    }
    }

    user_text = user_text.lower()
    results = []

    for disease, symptoms in symptom_map.items():
        score = 0
        max_score = sum(symptoms.values())

        for symptom, weight in symptoms.items():
            if symptom in user_text:
                score += weight

        if score > 0:
            confidence = int((score / max_score) * 90 + 5)
            results.append((disease, confidence))

    if not results:
        return []

    results.sort(key=lambda x: x[1], reverse=True)

    return results[:5]


def check_emergency(user_text):
    emergency_keywords = [
        "chest pain",
        "breathing difficulty",
        "shortness of breath",
        "unconscious",
        "confusion",
        "stroke",
        "heart attack",
        "severe headache",
        "blood vomiting",
        "seizure"
    ]

    user_text = user_text.lower()

    for word in emergency_keywords:
        if word in user_text:
            return True

    return False



# ── Agent ────────────────────────────────────────────────────────────────────
class AIAgent:
    def __init__(self):
        self.tools = {"web_search": WebSearchTool(), "file_operations": FileOperationsTool()}
    def _sys(self):
        td = ""
        for n,t in self.tools.items():
            td += f"\n### {n}\n{t.description}\nParams: {json.dumps(t.get_schema())}\n"
        return ("You are a medical AI triage assistant that provides health guidance based on symptoms, reports, medical knowledge graphs, and retrieved medical documents.\n\nTOOLS:\n" + td +
                '\nTo use a tool output ONLY JSON like: {"tool":"name","params":{"k":"v"}}\n'
                "After the tool result, answer naturally. If no tool needed, answer directly.")
    async def _call(self, messages):
        async with aiohttp.ClientSession() as s:
            async with s.post(f"{OLLAMA_URL}/api/chat",
                json={"model":MODEL_NAME,"messages":messages,"stream":False,
                      "options":{"temperature":0.7,"num_predict":2048}},
                timeout=aiohttp.ClientTimeout(total=120)) as r:
                if r.status != 200: raise Exception(f"Ollama {r.status}: {await r.text()}")
                return (await r.json())["message"]["content"]
    def _parse_tool(self, text):
        s = text.find("{"); e = text.rfind("}") + 1
        if s == -1 or e == 0: return None
        try:
            o = json.loads(text[s:e])
            if "tool" in o and "params" in o: return o
        except: pass
        return None
    async def process(self, message, history=None):
        msgs = [{"role":"system","content":self._sys()}]
        for h in (history or []):
            if h["role"] in ("user","assistant"): msgs.append(h)
        msgs.append({"role":"user","content":message})
        used = []
        for _ in range(4):
            reply = await self._call(msgs)
            tc = self._parse_tool(reply)
            if not tc: return {"response":reply,"tools_used":used}
            name = tc.get("tool","")
            if name not in self.tools: return {"response":reply,"tools_used":used}
            used.append(name)
            result = await self.tools[name].execute(**tc.get("params",{}))
            msgs.append({"role":"assistant","content":reply})
            msgs.append({"role":"user","content":
                f"Tool result for {name}:\n{json.dumps(result,indent=2)}\nNow answer using this."})
        final = await self._call(msgs)
        return {"response":final,"tools_used":used}
    async def check(self):
        try:
            async with aiohttp.ClientSession() as s:
                async with s.get(f"{OLLAMA_URL}/api/tags",
                    timeout=aiohttp.ClientTimeout(total=5)) as r:
                    if r.status == 200:
                        d = await r.json()
                        return any(MODEL_NAME in m["name"] for m in d.get("models",[]))
        except: pass
        return False# ================================

USERS_FILE = "users.json"

def load_users():
    if not os.path.exists(USERS_FILE):
        return {}
    return json.load(open(USERS_FILE))

def save_users(users):
    json.dump(users, open(USERS_FILE,"w"), indent=2)

def hash_password(pw):
    import hashlib
    return hashlib.sha256(pw.encode()).hexdigest()

from fastapi import Query

def get_current_user(token: str = Query(None)):

    users = load_users()

    if not token:
        raise HTTPException(401, "Token missing")

    for username, data in users.items():
        if data.get("token") == token:
            return username

    raise HTTPException(401, "Unauthorized - Please login")
class SignupRequest(BaseModel):
    username: str
    password: str


import re

def analyze_lab_values(text):

    findings = []

    # -----------------------------
    # HbA1c (Diabetes)
    # -----------------------------
    hba1c = re.search(r"HbA1c[:\s]+([\d\.]+)", text, re.IGNORECASE)

    if hba1c:
        value = float(hba1c.group(1))

        if value >= 6.5:
            findings.append(f"HbA1c is high ({value}%) → Diabetes risk")

        elif value >= 5.7:
            findings.append(f"HbA1c is borderline ({value}%) → Prediabetes risk")

    # -----------------------------
    # Blood Pressure
    # -----------------------------
    bp = re.search(r"(\d{2,3})/(\d{2,3})", text)

    if bp:
        systolic = int(bp.group(1))
        diastolic = int(bp.group(2))

        if systolic >= 140 or diastolic >= 90:
            findings.append(f"Blood Pressure is high ({systolic}/{diastolic}) → Hypertension risk")

    # -----------------------------
    # Creatinine (Kidney)
    # -----------------------------
    creatinine = re.search(r"Creatinine[:\s]+([\d\.]+)", text, re.IGNORECASE)

    if creatinine:
        value = float(creatinine.group(1))

        if value > 1.3:
            findings.append(f"Creatinine elevated ({value}) → Kidney function concern")

    # -----------------------------
    # Hemoglobin (Anemia)
    # -----------------------------
    hb = re.search(r"Hemoglobin[:\s]+([\d\.]+)", text, re.IGNORECASE)

    if hb:
        value = float(hb.group(1))

        if value < 12:
            findings.append(f"Hemoglobin low ({value}) → Possible anemia")

    # -----------------------------
    # Cholesterol
    # -----------------------------
    chol = re.search(r"Cholesterol[:\s]+([\d\.]+)", text, re.IGNORECASE)

    if chol:
        value = float(chol.group(1))

        if value > 200:
            findings.append(f"Cholesterol high ({value}) → Heart disease risk")

    # -----------------------------
    # Vitamin D
    # -----------------------------
    vitd = re.search(r"Vitamin D[:\s]+([\d\.]+)", text, re.IGNORECASE)

    if vitd:
        value = float(vitd.group(1))

        if value < 20:
            findings.append(f"Vitamin D deficiency ({value}) → Bone health risk")

    # -----------------------------
    # Platelets
    # -----------------------------
    platelets = re.search(r"Platelets[:\s]+([\d\.]+)", text, re.IGNORECASE)

    if platelets:
        value = float(platelets.group(1))

        if value < 150000:
            findings.append(f"Platelets low ({value}) → Bleeding risk")

        elif value > 450000:
            findings.append(f"Platelets high ({value}) → Clotting risk")

    # -----------------------------
    # TSH (Thyroid)
    # -----------------------------
    tsh = re.search(r"TSH[:\s]+([\d\.]+)", text, re.IGNORECASE)

    if tsh:
        value = float(tsh.group(1))

        if value > 4:
            findings.append(f"TSH elevated ({value}) → Possible hypothyroidism")

        elif value < 0.4:
            findings.append(f"TSH low ({value}) → Possible hyperthyroidism")

    # -----------------------------
    # WBC (Infection)
    # -----------------------------
    wbc = re.search(r"WBC[:\s]+([\d\.]+)", text, re.IGNORECASE)

    if wbc:
        value = float(wbc.group(1))

        if value > 11000:
            findings.append(f"WBC elevated ({value}) → Possible infection")

    # -----------------------------
    # RBC
    # -----------------------------
    rbc = re.search(r"RBC[:\s]+([\d\.]+)", text, re.IGNORECASE)

    if rbc:
        value = float(rbc.group(1))

        if value < 4:
            findings.append(f"RBC low ({value}) → Possible anemia")

    return findings

def adjust_confidence(base_conf, age, known_conditions, disease):
    conf = base_conf

    # Elderly risk boost
    if age >= 60:
        conf += 5

    # Existing disease makes condition worse
    if disease.lower() in [c.lower() for c in known_conditions]:
        conf += 7

    return min(conf, 100)

# ── FastAPI ───────────────────────────────────────────────────────────────────
app    = FastAPI()
agent  = AIAgent()
memory = MemoryManager()
load_medical_data()
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])


# --- authentication routes moved here so `app` exists earlier
class LoginRequest(BaseModel):
    username: str
    password: str
    age: Optional[int] = None
    known_conditions: Optional[List[str]] = []

@app.post("/api/signup")
def signup(req: SignupRequest):
    users = load_users()

    if req.username in users:
        raise HTTPException(400, "User already exists")

    users[req.username] = {"password": hash_password(req.password)}
    save_users(users)
    return {"status": "created"}

@app.post("/api/login")
def login(req: LoginRequest):
    users = load_users()
    if req.username not in users:
        raise HTTPException(401, "Invalid user")
    if users[req.username]["password"] != hash_password(req.password):
        raise HTTPException(401, "Wrong password")
    token = str(uuid.uuid4())
    users[req.username]["token"] = token
    save_users(users)
    # After successful authentication

    profile_data = {
        "age": req.age if req.age else 30,
        "known_conditions": req.known_conditions if req.known_conditions else []
    }

    memory.save_profile(req.username, profile_data)
    return {"token": token, "username": req.username}

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    token: str

class ChatResponse(BaseModel):
    response: str; session_id: str; tools_used: List[str]; timestamp: str


@app.post("/api/profile")
async def save_profile(req: dict):
    username = req.get("username")
    profile = req.get("profile")

    if not username or not profile:
        raise HTTPException(400, "Invalid profile data")

    memory.save_profile(username, profile)

    return {"status": "Profile saved"}

@app.get("/api/health")
async def health():
    ok = await agent.check()
    return {"status":"online","ollama":"connected" if ok else "not connected",
            "model":MODEL_NAME,"ollama_ready":ok}


@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):

    # ================================
    # 🔐 AUTH CHECK
    # ================================
    users = load_users()
    username = None

    for u, data in users.items():
        if data.get("token") == req.token:
            username = u
            break

    if not username:
        raise HTTPException(401, "Unauthorized - Please login")


    # ================================
    # 🧠 SESSION SETUP
    # ================================
    sid = req.session_id or memory.create_session(username)

    history = memory.get_history(username, sid) or []

    if len(history) == 0:
        memory.set_session_name(username, sid, req.message)

    # ================================
    # 🚨 EMERGENCY CHECK (ONLY ONCE)
    # ================================
    if check_emergency(req.message):
        emergency_response = """
🚨 EMERGENCY ALERT

Your symptoms may indicate a serious or life-threatening condition.

🔴 Risk Level: Critical

Please seek immediate medical attention.
Call emergency services or visit the nearest hospital immediately.

⚠️ Disclaimer:
This is AI guidance only. Do not delay professional medical care.
"""

        memory.add_message(username, sid, "user", req.message)
        memory.add_message(
            username, sid, "assistant", emergency_response,
            {"tools_used": ["Emergency Detector"]}
        )

        return ChatResponse(
            response=emergency_response,
            session_id=sid,
            tools_used=["Emergency Detector"],
            timestamp=datetime.now().isoformat()
        )

    # ================================
    # 👤 LOAD PROFILE
    # ================================
    profile = memory.load_profile(username)

    age = 30
    known_conditions = []

    if profile:
        age = profile.get("age", 30)
        known_conditions = profile.get("known_conditions", [])

    # ================================
    # 🧠 SYMPTOM PREDICTION
    # ================================
    prediction_list = predict_disease_from_symptoms(req.message) or []
    

    adjusted_predictions = []

    for disease, conf in prediction_list:
        new_conf = adjust_confidence(conf, age, known_conditions, disease)
        adjusted_predictions.append((disease, new_conf))

    prediction_list = prediction_list[:3]

    # ================================
    # 🏥 TRIAGE RESPONSE (LEVEL-2)
    # ================================
    if prediction_list:

        top_disease, top_confidence = prediction_list[0]

        def categorize_risk(confidence):
            if confidence >= 85:
                return "🔴 Critical"
            elif confidence >= 75:
                return "🟠 High"
            elif confidence >= 50:
                return "🟡 Moderate"
            else:
                return "🟢 Low"

        risk_level = categorize_risk(top_confidence)
        explanation_prompt = f"""
You are a clinical triage AI assistant that provides informational guidance based on symptoms.

Patient Profile:
Age: {age}
Known Medical Conditions: {known_conditions}

Reported Symptoms:
{req.message}

prediction_text = "\n".join(
    [f"{i+1}. {disease.title()} ({conf}%)" for i, (disease, conf) in enumerate(prediction_list)]
)
Predicted Possible Conditions:
{prediction_text}

Instructions:

1. Use the predicted conditions as guidance.
2. Explain the MOST LIKELY condition based on the symptoms.
3. Also list OTHER POSSIBLE conditions that could cause similar symptoms.
4. Consider how age and existing conditions may increase health risk.
5. Categorize overall risk level (Low / Moderate / High / Critical).
6. Provide simple precautions the patient can follow.
7. Clearly mention when medical attention is recommended.
8. Do NOT give a definitive diagnosis — only possible explanations.

Respond EXACTLY in this format:

🩺 Most Likely Condition:
(name + short explanation)

🔍 Other Possible Conditions:
(list 2–3 alternatives with brief reason)

📊 Risk Level:
(Low / Moderate / High / Critical)

🔎 Why This Risk Level:
(explain considering age, symptoms, and history)

💊 Immediate Precautions:
(simple actionable advice)

🏥 When to See a Doctor:
(clear medical guidance)

⚠️ Disclaimer:
This is AI-generated health guidance and not a medical diagnosis.
Consult a qualified healthcare professional for medical advice.
"""

        explanation = await agent.process(explanation_prompt, history)

        conditions_text = "\n".join(
            [f"{i+1}. {d.title()} ({c}%)"
             for i, (d, c) in enumerate(prediction_list)]
        )

        final_response = f"""
🩺 Possible Conditions:
{conditions_text}

📊 Risk Level: {risk_level}

{explanation["response"]}

⚠️ Disclaimer:
This is AI guidance only. Please consult a doctor.
"""

        memory.add_message(username, sid, "user", req.message)
        memory.add_message(
            username, sid, "assistant", final_response,
            {"tools_used": ["Symptom Predictor"]}
        )

        return ChatResponse(
            response=final_response,
            session_id=sid,
            tools_used=["Symptom Predictor"],
            timestamp=datetime.now().isoformat()
        )


# 🟣 KNOWLEDGE GRAPH
# ================================

    user_text = req.message.lower()

    medical_terms = [
    "fever","diabetes","bp","covid","cold",
    "cough","headache","migraine",
    "vomiting","infection",
    "leg pain","muscle pain","joint pain"
]

    kg_response = None

    for term in medical_terms:
        if term in user_text:
            kg_response = query_graph(term.capitalize())
            break

# Only return if KG has valid info
    if kg_response and isinstance(kg_response, str) and "No medical knowledge" not in kg_response:

        memory.add_message(username, sid, "user", req.message)
        memory.add_message(
            username, sid, "assistant", kg_response,
            {"tools_used": ["Medical KG"]}
        )

        return ChatResponse(
            response=kg_response,
            session_id=sid,
            tools_used=["Medical KG"],
            timestamp=datetime.now().isoformat()
        )
    # ================================
    # 🔵 RAG SEARCH
    # ================================
    rag_context = ""

    try:
        rag_results = search_rag(req.message)
        if rag_results and len(rag_results) > 0 and len(rag_results[0]) > 0:
            rag_context = rag_results[0][0]
    except:
        rag_context = ""

    try:
        if rag_context:
            prompt = f"""
Use ONLY this medical context to answer:

{rag_context}

Question:
{req.message}
"""
            response = requests.post(
                f"{OLLAMA_URL}/api/generate",
                json={
                    "model": MODEL_NAME,
                    "prompt": prompt,
                    "stream": False
                }
            )

            data = response.json()

            result_text = ""
            if "response" in data:
                result_text = data["response"]
            elif "message" in data and "content" in data["message"]:
                result_text = data["message"]["content"]
            result = {
                "response": result_text,
                "tools_used": ["RAG"]
            }

        else:
            result = await agent.process(req.message, history)

    except Exception as e:
        raise HTTPException(500, str(e))

    # ================================
    # 💾 SAVE MEMORY
    # ================================
    memory.add_message(username, sid, "user", req.message)
    memory.add_message(
        username, sid, "assistant", result["response"],
        {"tools_used": result.get("tools_used", [])}
    )

    return ChatResponse(
        response=result["response"],
        session_id=sid,
        tools_used=result.get("tools_used", []),
        timestamp=datetime.now().isoformat()
    )


@app.post("/api/upload/summary")
async def upload_summary(file: UploadFile = File(...)):

    os.makedirs("uploads", exist_ok=True)
    path = os.path.join("uploads", file.filename)

    content = await file.read()

    with open(path, "wb") as f:
        f.write(content)

    r = await FileOperationsTool().execute(
        operation="read",
        file_path=path
    )

    s = await agent.process(
        f"Summarize this document in 2 sentences:\n{str(r.get('content',''))[:2000]}"
    )

    return {
        "status": "success",
        "filename": file.filename,
        "size": len(content),
        "summary": s["response"]
    }

@app.get("/api/sessions")
def list_sessions(username: str = Depends(get_current_user)):

    return memory.list_sessions(username)




@app.get("/api/sessions/{sid}/history")
def get_history(sid: str, username: str = Depends(get_current_user)):

    h = memory.get_history(username, sid)

    if h is None:
        raise HTTPException(404, "Not found")

    return {
        "session_id": sid,
        "history": h
    }

@app.delete("/api/sessions/{sid}")
def del_session(sid: str, username: str = Depends(get_current_user)):

    if not memory.delete_session(username, sid):
        raise HTTPException(404, "Not found")

    return {"status": "deleted"}

@app.get("/api/models")
async def models():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{OLLAMA_URL}/api/tags") as r:
                d = await r.json()
                return {"models":[m["name"] for m in d.get("models",[])]}
    except: return {"models":[]}
# ===============================
# 📂 FILE UPLOAD → RAG STORAGE
# ===============================
# store last uploaded report globally
LAST_REPORT = ""

@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):
    global LAST_REPORT

    try:
        os.makedirs("uploads", exist_ok=True)

        file_path = os.path.join("uploads", file.filename)

        content = await file.read()

        with open(file_path, "wb") as f:
            f.write(content)

        extracted_text = ""

        # =========================
        # TEXT FILE
        # =========================
        if file.filename.endswith(".txt"):
            extracted_text = content.decode("utf-8")

        # =========================
        # PDF FILE
        # =========================
        elif file.filename.endswith(".pdf"):

            import pdfplumber

            with pdfplumber.open(file_path) as pdf:

                for page in pdf.pages:

                    text = page.extract_text()

                    if text:
                        extracted_text += text + "\n"

        # =========================
        # IMAGE FILE (OCR)
        # =========================
        elif file.filename.endswith((".png", ".jpg", ".jpeg")):

            import pytesseract
            from PIL import Image

            img = Image.open(file_path)

            extracted_text = pytesseract.image_to_string(img)

        else:
            return {
                "status": "error",
                "message": "Unsupported file format"
            }

        # =========================
        # SAFETY CHECK
        # =========================
        if not extracted_text.strip():

            return {
                "status": "error",
                "message": "No readable text found in the file"
            }

        # Save report snippet for future chat usage
        LAST_REPORT = extracted_text[:8000]

        # =========================
        # LAB VALUE DETECTION
        # =========================
        findings = analyze_lab_values(extracted_text)

        findings_text = "\n".join(findings) if findings else "No abnormal lab values detected."

        # =========================
        # LLM PROMPT
        # =========================
        medical_prompt = f"""
You are an expert medical AI trained to interpret laboratory reports.

Medical Report:
{LAST_REPORT}

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
(list abnormal values)

🩺 Possible Health Risks:
(list possible risks)

💊 Health Advice:
(simple precautions)

🏥 When to Consult a Doctor:
(clear guidance)

⚠️ Disclaimer:
This analysis is AI-generated and not a medical diagnosis.
"""

        # =========================
        # CALL OLLAMA
        # =========================
        response = requests.post(
            f"{OLLAMA_URL}/api/generate",
            json={
                "model": MODEL_NAME,
                "prompt": medical_prompt,
                "stream": False
            },
            timeout=120
        )

        data = response.json()

        result_text = data.get("response") or \
                      data.get("message", {}).get("content", "")

        # =========================
        # FINAL RESPONSE
        # =========================
        return {
            "status": "success",
            "analysis": result_text,
            "lab_findings": findings,
            "summary": result_text
        }

    except Exception as e:

        return {
            "status": "error",
            "message": str(e)
        }
# ── Frontend ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
def index():
    return HTMLResponse(open(os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html"), encoding="utf-8").read())

if __name__ == "__main__":
    print("="*50)
    print("  AI Agent — Ollama Edition (100% Free)")
    print("="*50)
    print(f"\n  Open browser: http://localhost:{PORT}")
    print("  Press CTRL+C to stop\n")
    print("="*50)
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)
