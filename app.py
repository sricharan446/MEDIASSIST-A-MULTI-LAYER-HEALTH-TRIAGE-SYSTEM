"""
AI Agent - Single Server using Ollama (FREE & Local)
Run: python app.py   then open http://localhost:8000
"""
from knowledge_graph.graph import query_graph
from rag.rag_engine import search_rag
from fastapi import FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import json, os, uuid, csv, aiohttp, uvicorn
from datetime import datetime
from pathlib import Path
from bs4 import BeautifulSoup
from abc import ABC, abstractmethod
from fastapi import UploadFile, File
import shutil
import os
from rag.rag_engine import add_document_to_rag
import requests

OLLAMA_URL  = os.getenv("OLLAMA_URL",  "http://localhost:11434")
MODEL_NAME  = os.getenv("MODEL_NAME",  "llama3.2")
PORT        = int(os.getenv("PORT",    "8000"))
MEMORY_PATH = os.getenv("MEMORY_PATH", "/tmp/agent_memory")

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
        self.path = Path(MEMORY_PATH)
        self.path.mkdir(parents=True, exist_ok=True)
    def _f(self, sid): return self.path / f"{sid}.json"
    def create_session(self):
        sid = str(uuid.uuid4())
        json.dump({
            "id": sid,
            "name": "New Chat",
            "created_at": datetime.now().isoformat(),
            "last_activity": datetime.now().isoformat(),
        "messages": []
        },
    open(self._f(sid),"w"), indent=2)
        return sid
    def set_session_name(self, sid, name):
        d = self._load(sid)
        if not d:
            return
        d["name"] = name[:40]
        json.dump(d, open(self._f(sid), "w"), indent=2)

    def add_message(self, sid, role, content, meta=None):
        d = self._load(sid) or {"id":sid,"created_at":datetime.now().isoformat(),
                                 "last_activity":datetime.now().isoformat(),"messages":[]}
        msg = {"role":role,"content":content,"timestamp":datetime.now().isoformat()}
        if meta: msg["metadata"] = meta
        d["messages"].append(msg)
        d["last_activity"] = datetime.now().isoformat()
        d["messages"] = d["messages"][-50:]
        json.dump(d, open(self._f(sid),"w"), indent=2)
    def get_history(self, sid):
        d = self._load(sid)
        if not d: return None
        return [{"role":m["role"],"content":m["content"]} for m in d["messages"]]
    def list_sessions(self):
        out = []
        for f in self.path.glob("*.json"):
            try:
                d = json.load(open(f))
                out.append({
                    "id": d["id"],
                    "name": d.get("name", "New Chat"),
                    "created_at": d["created_at"],
                    "last_activity": d["last_activity"],
                    "message_count": len(d["messages"])
                })
            except:
                pass
        return sorted(out, key=lambda x: x["last_activity"], reverse=True)
    def delete_session(self, sid):
        f = self._f(sid)
        if f.exists(): f.unlink(); return True
        return False
    def _load(self, sid):
        f = self._f(sid)
        if not f.exists(): return None
        try: return json.load(open(f))
        except: return None

# ── Agent ────────────────────────────────────────────────────────────────────
class AIAgent:
    def __init__(self):
        self.tools = {"web_search": WebSearchTool(), "file_operations": FileOperationsTool()}
    def _sys(self):
        td = ""
        for n,t in self.tools.items():
            td += f"\n### {n}\n{t.description}\nParams: {json.dumps(t.get_schema())}\n"
        return ("You are a helpful AI assistant with tools.\n\nTOOLS:\n" + td +
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
        return False

# ── FastAPI ───────────────────────────────────────────────────────────────────
app    = FastAPI()
agent  = AIAgent()
memory = MemoryManager()
app.add_middleware(CORSMiddleware, allow_origins=["*"],
                   allow_methods=["*"], allow_headers=["*"])

class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatResponse(BaseModel):
    response: str; session_id: str; tools_used: List[str]; timestamp: str

@app.get("/api/health")
async def health():
    ok = await agent.check()
    return {"status":"online","ollama":"connected" if ok else "not connected",
            "model":MODEL_NAME,"ollama_ready":ok}

@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    sid = req.session_id or memory.create_session()
    history = memory.get_history(sid) or []

    # ================================
    # 🟣 KNOWLEDGE GRAPH PRIORITY
    # ================================
    user_text = req.message.lower()
    kg_node = None

    if "python" in user_text:
        kg_node = "Python"
    elif "fastapi" in user_text:
        kg_node = "FastAPI"
    elif "rag" in user_text:
        kg_node = "RAG"
    elif "ollama" in user_text:
        kg_node = "Ollama"
    elif "chromadb" in user_text:
        kg_node = "ChromaDB"

    if kg_node:
        kg_response = query_graph(kg_node)

        memory.add_message(sid, "user", req.message)
        memory.add_message(sid, "assistant", kg_response, {"tools_used": ["Knowledge Graph"]})
        # auto name chat from first message
        if len(history) == 0:
            memory.set_session_name(sid, req.message[:30])


        return ChatResponse(
            response=kg_response,
            session_id=sid,
            tools_used=["Knowledge Graph"],
            timestamp=datetime.now().isoformat()
        )

    # ================================
    # 🔵 RAG SEARCH
    # ================================
    rag_context = ""
    try:
        rag_results = search_rag(req.message)
        if rag_results and len(rag_results[0]) > 0:
            rag_context = rag_results[0][0]
    except:
        rag_context = ""

    try:
        # 🔥 IF DOCUMENT FOUND → DIRECT LLM (no tools)
        if rag_context:
            prompt = f"""
You are an AI assistant. Answer using only this context.

Context:
{rag_context}

Question:
{req.message}
"""

            response = requests.post(
                "http://localhost:11434/api/generate",
                json={
                    "model": "llama3",
                    "prompt": prompt,
                    "stream": False
                }
            )

            result_text = response.json()["response"]

            result = {
                "response": result_text,
                "tools_used": ["RAG"]
            }

        else:
            # 🟢 Normal agent if no KG or RAG
            result = await agent.process(req.message, history)

    except Exception as e:
        err = str(e)
        if "Connection refused" in err or "Connect call failed" in err:
            raise HTTPException(503, "Ollama is not running. Type: ollama serve")
        raise HTTPException(500, err)

    # ================================
    # 💾 SAVE MEMORY
    # ================================
    memory.add_message(sid, "user", req.message)
    memory.add_message(sid, "assistant", result["response"], {"tools_used": result["tools_used"]})

    return ChatResponse(
        response=result["response"],
        session_id=sid,
        tools_used=result["tools_used"],
        timestamp=datetime.now().isoformat()
    )



@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...)):

    os.makedirs("uploads", exist_ok=True)
    file_path = os.path.join("uploads", file.filename)

    # 🔥 IMPORTANT: read file properly
    content = await file.read()

    with open(file_path, "wb") as f:
        f.write(content)

    # now send to RAG
    message = add_document_to_rag(file_path)

    return {"message": message}




@app.get("/api/sessions")
def list_sessions(): return memory.list_sessions()

@app.get("/api/sessions/{sid}/history")
def get_history(sid):
    h = memory.get_history(sid)
    if h is None: raise HTTPException(404,"Not found")
    return {"session_id":sid,"history":h}

@app.delete("/api/sessions/{sid}")
def del_session(sid):
    if not memory.delete_session(sid): raise HTTPException(404,"Not found")
    return {"status":"deleted"}

@app.post("/api/upload")
async def upload(file: UploadFile = File(...)):
    path = f"/tmp/{file.filename}"
    content = await file.read()
    open(path,"wb").write(content)
    r = await FileOperationsTool().execute(operation="read",file_path=path)
    s = await agent.process(f"Summarize in 2 sentences:\n{str(r.get('content',''))[:2000]}")
    return {"status":"success","filename":file.filename,
            "size":len(content),"summary":s["response"]}

@app.get("/api/models")
async def models():
    try:
        async with aiohttp.ClientSession() as s:
            async with s.get(f"{OLLAMA_URL}/api/tags") as r:
                d = await r.json()
                return {"models":[m["name"] for m in d.get("models",[])]}
    except: return {"models":[]}

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
