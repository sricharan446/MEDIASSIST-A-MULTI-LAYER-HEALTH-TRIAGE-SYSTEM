"""
MediAssist - AI Health Triage System using Google Gemini API
Run: python app.py   then open http://mediassist.local

ORIGINAL FIXES (v1):
  1. KG now passes results through Gemini for a proper explanation
  2. Words not in KG fall through correctly to RAG → AI Agent
  3. agent.process() now accepts and uses `model` parameter
  4. Added /api/logout route — token invalidated server-side
  5. MAX_SESSIONS = 50 enforced in create_session()
  6. gemini_client wrapped in asyncio.to_thread() — non-blocking

FEATURES ADDED (v2):
  7. DISEASE_MEDICATIONS dict — medication cards for all 15 diseases
  8. format_medication_card() — name, composition, dosage, PharmEasy link
  9. GEMINI_MEDICAL_SYSTEM_PROMPT — dynamic medication section for all responses
 10. Symptom predictor appends medication card for top predicted disease
 11. Blood Pressure added as named biomarker in analyze_lab_values()
 12. Symptom map expanded from 9 → 15 diseases

NEW IMPROVEMENTS (v3 — applied to actual project zip):
 13. /api/profile now verifies token — fixes auth bypass vulnerability
 14. FileOperationsTool path restricted to safe dirs — fixes path traversal
 15. Emergency keywords expanded from 11 → 21 — adds paralysis, overdose etc.
 16. Session history capped at 50 messages — prevents unbounded file growth
 17. list_sessions now includes last_activity timestamp — improves frontend UX
 18. Symptom flood guard — if >5 diseases trigger, route to Gemini directly
 19. .env MODEL_NAME fixed — was gemini-1.5-flash, updated to gemini-2.5-flash-lite
 20. Empty-username ghost account in users.json prevented at signup
 21. get_history returns last 20 messages only for Gemini context (not all)
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
import urllib.parse
from dotenv import load_dotenv
load_dotenv(override=True)
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)
from datetime import datetime
from pathlib import Path
from typing import List, Optional, Dict, Any
from abc import ABC, abstractmethod

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
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
MODEL_NAME     = os.getenv("MODEL_NAME", "gemini-2.5-flash-lite")   # FIX 19
PORT           = int(os.getenv("PORT", "8000"))

if not GEMINI_API_KEY:
    raise RuntimeError("GEMINI_API_KEY is not set. Please add it to your .env file.")

gemini_client = genai.Client(
    api_key=GEMINI_API_KEY
)

USER_REPORTS: Dict[str, Dict] = {}
MAX_SESSIONS = 50
_users_lock: asyncio.Lock = None  # Created lazily on first use (avoids DeprecationWarning in Python 3.10+)

# FIX 14: Only these directories may be read by the FileOperationsTool
ALLOWED_READ_DIRS = ["medical_data", "uploads", "memory"]


# ── Medication Database ───────────────────────────────────────────────────────
DISEASE_MEDICATIONS: Dict[str, Dict] = {
    "common cold": {
        "medicines": [
            {
                "name": "Cetirizine 10mg",
                "type": "Antihistamine tablet",
                "composition": "Cetirizine Hydrochloride 10mg",
                "dosage": "1 tablet once daily at night",
                "duration": "3–5 days",
                "purpose": "Relieves runny nose, sneezing, watery eyes",
                "buy_url": "https://pharmeasy.in/search/all?name=cetirizine+10mg"
            },
            {
                "name": "Paracetamol 500mg",
                "type": "Antipyretic / Analgesic",
                "composition": "Paracetamol (Acetaminophen) 500mg",
                "dosage": "1–2 tablets every 4–6 hours as needed",
                "duration": "Until fever/pain subsides (max 3 days)",
                "purpose": "Reduces fever and body ache",
                "buy_url": "https://pharmeasy.in/search/all?name=paracetamol+500mg"
            }
        ]
    },
    "flu": {
        "medicines": [
            {
                "name": "Oseltamivir 75mg (Tamiflu)",
                "type": "Antiviral capsule",
                "composition": "Oseltamivir Phosphate 75mg",
                "dosage": "1 capsule twice daily with food",
                "duration": "5 days — start within 48 hrs of symptom onset",
                "purpose": "Reduces duration and severity of influenza",
                "buy_url": "https://pharmeasy.in/search/all?name=oseltamivir+75mg"
            },
            {
                "name": "Paracetamol 650mg",
                "type": "Antipyretic",
                "composition": "Paracetamol 650mg",
                "dosage": "1 tablet every 6 hours",
                "duration": "Until fever subsides",
                "purpose": "Controls high fever and body ache in flu",
                "buy_url": "https://pharmeasy.in/search/all?name=paracetamol+650mg"
            }
        ]
    },
    "covid": {
        "medicines": [
            {
                "name": "Paracetamol 650mg",
                "type": "Antipyretic",
                "composition": "Paracetamol 650mg",
                "dosage": "1 tablet every 6 hours",
                "duration": "As needed — under doctor supervision",
                "purpose": "Manages COVID fever and body ache",
                "buy_url": "https://pharmeasy.in/search/all?name=paracetamol+650mg"
            },
            {
                "name": "Vitamin D3 + Zinc Supplement",
                "type": "Immune support supplement",
                "composition": "Cholecalciferol (Vitamin D3) + Zinc Sulphate",
                "dosage": "As directed on pack (typically once daily)",
                "duration": "2–4 weeks",
                "purpose": "Supports immune system during COVID recovery",
                "buy_url": "https://pharmeasy.in/search/all?name=vitamin+d3+zinc"
            }
        ]
    },
    "diabetes": {
        "medicines": [
            {
                "name": "Metformin 500mg",
                "type": "Oral antidiabetic tablet",
                "composition": "Metformin Hydrochloride 500mg",
                "dosage": "1 tablet twice daily with meals",
                "duration": "Long-term — do not stop without doctor advice",
                "purpose": "Controls blood sugar levels in Type 2 Diabetes",
                "buy_url": "https://pharmeasy.in/search/all?name=metformin+500mg"
            }
        ]
    },
    "hypertension": {
        "medicines": [
            {
                "name": "Amlodipine 5mg",
                "type": "Calcium channel blocker tablet",
                "composition": "Amlodipine Besylate 5mg",
                "dosage": "1 tablet once daily (morning)",
                "duration": "Long-term — do not stop without doctor advice",
                "purpose": "Lowers high blood pressure",
                "buy_url": "https://pharmeasy.in/search/all?name=amlodipine+5mg"
            }
        ]
    },
    "migraine": {
        "medicines": [
            {
                "name": "Sumatriptan 50mg",
                "type": "Triptan / Antimigraine tablet",
                "composition": "Sumatriptan Succinate 50mg",
                "dosage": "1 tablet at onset of migraine; repeat after 2 hrs if needed",
                "duration": "As needed (max 2 tablets per 24 hrs)",
                "purpose": "Relieves migraine headache and associated nausea",
                "buy_url": "https://pharmeasy.in/search/all?name=sumatriptan+50mg"
            },
            {
                "name": "Naproxen 500mg",
                "type": "NSAID / Anti-inflammatory",
                "composition": "Naproxen Sodium 500mg",
                "dosage": "1 tablet twice daily with food",
                "duration": "2–3 days during migraine episode",
                "purpose": "Reduces migraine pain and inflammation",
                "buy_url": "https://pharmeasy.in/search/all?name=naproxen+500mg"
            }
        ]
    },
    "viral infection": {
        "medicines": [
            {
                "name": "Paracetamol 500mg + Vitamin C 500mg",
                "type": "Antipyretic + Immune support",
                "composition": "Paracetamol 500mg | Ascorbic Acid 500mg",
                "dosage": "Paracetamol every 6 hrs; Vitamin C once daily",
                "duration": "5–7 days",
                "purpose": "Manages fever and supports immune recovery",
                "buy_url": "https://pharmeasy.in/search/all?name=paracetamol+vitamin+c"
            }
        ]
    },
    "malaria": {
        "medicines": [
            {
                "name": "Artemether + Lumefantrine (Coartem)",
                "type": "Antimalarial combination tablet",
                "composition": "Artemether 20mg + Lumefantrine 120mg",
                "dosage": "4 tablets twice daily for 3 days (with food)",
                "duration": "3 days — must complete the full course",
                "purpose": "Kills malaria parasite (Plasmodium falciparum)",
                "buy_url": "https://pharmeasy.in/search/all?name=artemether+lumefantrine"
            }
        ]
    },
    "dengue fever": {
        "medicines": [
            {
                "name": "Paracetamol 650mg",
                "type": "Antipyretic tablet",
                "composition": "Paracetamol 650mg",
                "dosage": "1 tablet every 6 hours",
                "duration": "Until fever subsides — under strict doctor supervision",
                "purpose": "Reduces high fever in dengue. ⚠️ AVOID Ibuprofen and Aspirin",
                "buy_url": "https://pharmeasy.in/search/all?name=paracetamol+650mg"
            },
            {
                "name": "ORS Sachets (Oral Rehydration Salts)",
                "type": "Rehydration solution",
                "composition": "Sodium Chloride + Potassium Chloride + Sodium Citrate + Glucose",
                "dosage": "1 sachet dissolved in 1 litre water — sip throughout the day",
                "duration": "Until fever and weakness subside",
                "purpose": "Prevents dehydration, critical in dengue management",
                "buy_url": "https://pharmeasy.in/search/all?name=ors+sachet"
            }
        ]
    },
    "muscle strain": {
        "medicines": [
            {
                "name": "Diclofenac 50mg + Paracetamol 500mg",
                "type": "NSAID + Analgesic combination tablet",
                "composition": "Diclofenac Sodium 50mg + Paracetamol 500mg",
                "dosage": "1 tablet twice daily after meals",
                "duration": "3–5 days",
                "purpose": "Reduces muscle pain and inflammation",
                "buy_url": "https://pharmeasy.in/search/all?name=diclofenac+paracetamol"
            },
            {
                "name": "Volini / Diclofenac Gel (Topical)",
                "type": "Topical NSAID gel",
                "composition": "Diclofenac Diethylamine 1.16% w/w",
                "dosage": "Apply a thin layer on the affected area 3–4 times daily",
                "duration": "5–7 days",
                "purpose": "Directly relieves muscle pain and stiffness at the site",
                "buy_url": "https://pharmeasy.in/search/all?name=diclofenac+gel"
            }
        ]
    },
    "anxiety": {
        "medicines": [
            {
                "name": "Escitalopram 10mg",
                "type": "SSRI antidepressant / anxiolytic tablet",
                "composition": "Escitalopram Oxalate 10mg",
                "dosage": "1 tablet once daily in the morning",
                "duration": "Long-term — do not stop abruptly, taper under doctor guidance",
                "purpose": "Reduces anxiety, panic attacks, and generalised anxiety disorder",
                "buy_url": "https://pharmeasy.in/search/all?name=escitalopram+10mg"
            },
            {
                "name": "Clonazepam 0.5mg (short-term only)",
                "type": "Benzodiazepine / Anti-anxiety",
                "composition": "Clonazepam 0.5mg",
                "dosage": "0.5mg once or twice daily as needed (short-term only)",
                "duration": "2–4 weeks maximum — strictly under doctor prescription",
                "purpose": "Fast-acting relief of acute anxiety and panic",
                "buy_url": "https://pharmeasy.in/search/all?name=clonazepam+0.5mg"
            }
        ]
    },
    "anemia": {
        "medicines": [
            {
                "name": "Ferrous Sulphate 200mg",
                "type": "Iron supplement tablet",
                "composition": "Ferrous Sulphate 200mg (65mg elemental iron)",
                "dosage": "1 tablet once daily on an empty stomach",
                "duration": "3–6 months — under doctor guidance",
                "purpose": "Treats iron-deficiency anaemia",
                "buy_url": "https://pharmeasy.in/search/all?name=ferrous+sulphate+200mg"
            },
            {
                "name": "Vitamin B12 (Methylcobalamin 500mcg)",
                "type": "Vitamin B12 supplement tablet",
                "composition": "Methylcobalamin 500mcg",
                "dosage": "1 tablet once daily",
                "duration": "3 months or as advised by doctor",
                "purpose": "Treats B12-deficiency anaemia and nerve damage",
                "buy_url": "https://pharmeasy.in/search/all?name=methylcobalamin+500mcg"
            }
        ]
    },
    "gastroenteritis": {
        "medicines": [
            {
                "name": "ORS Sachets (Oral Rehydration Salts)",
                "type": "Rehydration solution",
                "composition": "Sodium Chloride + Potassium Chloride + Sodium Citrate + Glucose",
                "dosage": "1 sachet dissolved in 1 litre water — sip throughout the day",
                "duration": "Until diarrhoea / vomiting stops",
                "purpose": "Prevents and treats dehydration from diarrhoea and vomiting",
                "buy_url": "https://pharmeasy.in/search/all?name=ors+sachet"
            },
            {
                "name": "Ondansetron 4mg",
                "type": "Antiemetic tablet / dissolvable strip",
                "composition": "Ondansetron Hydrochloride 4mg",
                "dosage": "1 tablet every 8 hours for nausea / vomiting",
                "duration": "1–2 days",
                "purpose": "Controls nausea and vomiting",
                "buy_url": "https://pharmeasy.in/search/all?name=ondansetron+4mg"
            },
            {
                "name": "Racecadotril 100mg",
                "type": "Antidiarrhoeal tablet",
                "composition": "Racecadotril 100mg",
                "dosage": "1 tablet three times daily before meals",
                "duration": "3–5 days",
                "purpose": "Reduces severity and duration of acute diarrhoea",
                "buy_url": "https://pharmeasy.in/search/all?name=racecadotril+100mg"
            }
        ]
    },
    "asthma": {
        "medicines": [
            {
                "name": "Salbutamol Inhaler 100mcg (Ventolin)",
                "type": "Short-acting bronchodilator (reliever inhaler)",
                "composition": "Salbutamol Sulfate 100mcg per actuation",
                "dosage": "1–2 puffs as needed during an attack",
                "duration": "As needed (rescue inhaler — not for daily preventive use)",
                "purpose": "Rapidly opens airways during an asthma attack",
                "buy_url": "https://pharmeasy.in/search/all?name=salbutamol+inhaler"
            },
            {
                "name": "Budesonide 200mcg Inhaler",
                "type": "Inhaled corticosteroid (preventer inhaler)",
                "composition": "Budesonide 200mcg per actuation",
                "dosage": "1–2 puffs twice daily (morning and night)",
                "duration": "Long-term preventive — do not stop without doctor advice",
                "purpose": "Reduces airway inflammation and prevents asthma attacks",
                "buy_url": "https://pharmeasy.in/search/all?name=budesonide+inhaler"
            }
        ]
    },
    "urinary tract infection": {
        "medicines": [
            {
                "name": "Nitrofurantoin 100mg",
                "type": "Antibiotic capsule",
                "composition": "Nitrofurantoin Monohydrate / Macrocrystals 100mg",
                "dosage": "1 capsule twice daily with food",
                "duration": "5–7 days — complete the full course",
                "purpose": "Treats bacterial urinary tract infection",
                "buy_url": "https://pharmeasy.in/search/all?name=nitrofurantoin+100mg"
            },
            {
                "name": "Phenazopyridine 200mg (Uristat)",
                "type": "Urinary analgesic tablet",
                "composition": "Phenazopyridine Hydrochloride 200mg",
                "dosage": "1 tablet three times daily after meals",
                "duration": "2 days (pain relief only — not an antibiotic)",
                "purpose": "Relieves burning, urgency, and discomfort during urination",
                "buy_url": "https://pharmeasy.in/search/all?name=phenazopyridine"
            }
        ]
    }
}


def format_medication_card(disease: str, quantity: int = 1) -> str:
    """Return a formatted Markdown medication card for the given disease name with quantity support."""
    key  = disease.lower().strip()
    meds = DISEASE_MEDICATIONS.get(key)
    if not meds:
        return ""
    lines = [
        f"\n\n---\n## 💊 Suggested Medications for {disease.title()}\n",
        "> ⚠️ **Disclaimer:** These are commonly used medications for reference only. "
        "**Always consult a qualified doctor before taking any medication.** "
        "Some of these may require a prescription.\n"
    ]
    for med in meds["medicines"]:
        lines.append(f"### 🔹 {med['name']}")
        lines.append(f"- **Type:** {med['type']}")
        lines.append(f"- **Composition:** {med['composition']}")
        lines.append(f"- **Dosage:** {med['dosage']}")
        lines.append(f"- **Duration:** {med['duration']}")
        lines.append(f"- **Purpose:** {med['purpose']}")
        # Build pharmacy links — correct URL patterns for each site
        med_name     = med['name'].replace("+", " ").split("(")[0].strip()
        encoded_name = urllib.parse.quote_plus(med_name)
        pharmeasy_link = f"https://pharmeasy.in/search/all?name={encoded_name}"
        lines.append(f"- **🛒 Buy on 1mg (Tata):** [Click to order]({pharmeasy_link})")
        lines.append("")
    return "\n".join(lines)


GEMINI_MEDICAL_SYSTEM_PROMPT = """You are MediAssist, an intelligent AI health triage assistant.

When answering about any disease, condition, or health query, you MUST always end your
response with a medication section in EXACTLY this Markdown format:

---
## 💊 Suggested Medications
> ⚠️ *General reference only. Always consult a doctor before taking any medication.*

### 🔹 [Medicine Name and Strength]
- **Type:** [tablet / capsule / syrup / inhaler / gel / etc.]
- **Composition:** [active ingredient(s) and strength]
- **Dosage:** [how much and how often]
- **Duration:** [how long to take it]
- **Purpose:** [what it treats in this context]
- **🛒 Buy on PharmEasy:** [https://pharmeasy.in/search/all?name=medicine+name+url+encoded]

Repeat the block above for each relevant medicine (maximum 3 medicines).
If the condition requires prescription-only medicines, clearly state that a prescription is needed.
"""



# ── Practo Specialist Mapping ─────────────────────────────────────────────
DISEASE_SPECIALTY: dict = {
    "diabetes":                "endocrinologist",
    "hypertension":            "cardiologist",
    "migraine":                "neurologist",
    "muscle strain":           "orthopedist",
    "viral infection":         "general-physician",
    "common cold":             "general-physician",
    "flu":                     "general-physician",
    "covid":                   "general-physician",
    "malaria":                 "general-physician",
    "anxiety":                 "psychiatrist",
    "anemia":                  "hematologist",
    "gastroenteritis":         "gastroenterologist",
    "asthma":                  "pulmonologist",
    "urinary tract infection": "urologist",
    "urinary infection":       "urologist",
    "dengue fever":            "general-physician",
    "dengue":                  "general-physician",
}

EMERGENCY_SPECIALTY: dict = {
    "chest pain":           "cardiologist",
    "heart attack":         "cardiologist",
    "no pulse":             "cardiologist",
    "stroke":               "neurologist",
    "severe headache":      "neurologist",
    "paralysis":            "neurologist",
    "unable to move":       "neurologist",
    "seizure":              "neurologist",
    "breathing difficulty": "pulmonologist",
    "shortness of breath":  "pulmonologist",
    "can't breathe":        "pulmonologist",
    "cannot breathe":       "pulmonologist",
    "unconscious":          "general-physician",
    "collapsed":            "general-physician",
    "fainting":             "general-physician",
    "blood vomiting":       "gastroenterologist",
    "severe bleeding":      "general-physician",
    "overdose":             "general-physician",
    "poisoning":            "general-physician",
    "anaphylaxis":          "dermatologist",
    "allergic reaction":    "dermatologist",
    "choking":              "general-physician",
    "suicidal":             "psychiatrist",
}

# Display names for the button label
SPECIALTY_DISPLAY: dict = {
    "cardiologist":       "Cardiologist",
    "neurologist":        "Neurologist",
    "orthopedist":        "Orthopedic Specialist",
    "general-physician":  "General Physician",
    "psychiatrist":       "Psychiatrist",
    "hematologist":       "Hematologist",
    "gastroenterologist": "Gastroenterologist",
    "pulmonologist":      "Pulmonologist",
    "urologist":          "Urologist",
    "endocrinologist":    "Endocrinologist",
    "dermatologist":      "Dermatologist",
}


def build_practo_url(specialty_slug: str, city: str = "hyderabad") -> str:
    """Build a direct Practo doctor listing URL — practo.com/{city}/{specialty-slug}"""
    return f"https://www.practo.com/{city}/{specialty_slug}"

# ── Gemini call with retry ────────────────────────────────────────────────────
async def gemini_generate(model: str, contents: str, temperature: float = 0.7,
                          max_tokens: int = 2048) -> str:
    """Call Gemini (non-blocking) with up to 3 retries on 429/503 errors."""
    last_err = None
    for attempt in range(3):
        try:
            def _sync_call():
                return gemini_client.models.generate_content(
                    model=model,
                    contents=contents,
                    config=types.GenerateContentConfig(
                        temperature=temperature,
                        max_output_tokens=max_tokens,
                    )
                )
            response = await asyncio.to_thread(_sync_call)
            return response.text
        except Exception as e:
            last_err = e
            msg = str(e).lower()
            if any(x in msg for x in ["429", "503", "rate", "quota", "unavailable"]):
                wait = 2 ** attempt
                logger.warning(f"Gemini error (attempt {attempt+1}): {e}. Retrying in {wait}s...")
                await asyncio.sleep(wait)
            else:
                break
    raise last_err


# ── Medical Data Loader ───────────────────────────────────────────────────────
def load_medical_data():
    folder = "medical_data"
    if not os.path.exists(folder):
        return
    for file in os.listdir(folder):
        if file.endswith(".txt"):
            path = os.path.join(folder, file)
            add_document_to_rag(path)
            print(f"Loaded: {file}")


# ── Symptom Prediction ────────────────────────────────────────────────────────
def predict_disease_from_symptoms(user_text: str) -> List[tuple]:
    """Score symptoms against known disease patterns. Returns top 5 matches."""
    if not user_text:
        return []
    symptom_map = {
        "diabetes":                {"urination": 3, "thirst": 3, "fatigue": 2, "blurred vision": 2},
        "hypertension":            {"chest pain": 3, "dizziness": 2, "headache": 1},
        "migraine":                {"light sensitivity": 3, "nausea": 2, "headache": 1},
        "muscle strain":           {"leg pain": 3, "muscle pain": 2},
        "viral infection":         {"fever": 3, "fatigue": 2, "body pain": 2},
        "common cold":             {"fever": 2, "cough": 2, "runny nose": 2},
        "flu":                     {"fever": 3, "body pain": 3, "fatigue": 2},
        "covid":                   {"fever": 2, "dry cough": 2, "loss of smell": 4},
        "malaria":                 {"fever": 3, "chills": 3, "sweating": 2},
        "anxiety":                 {"palpitations": 3, "sweating": 2, "shortness of breath": 2, "dizziness": 1},
        "anemia":                  {"fatigue": 3, "dizziness": 2, "pale skin": 3, "weakness": 2},
        "gastroenteritis":         {"nausea": 3, "vomiting": 3, "diarrhea": 3, "stomach pain": 2},
        "asthma":                  {"wheezing": 4, "shortness of breath": 3, "cough": 2},
        "urinary tract infection": {"burning urination": 4, "frequent urination": 3, "lower back pain": 2},
        "dengue fever":            {"fever": 3, "rash": 3, "joint pain": 3, "headache": 2},
    }

    def symptom_present(text: str, symptom: str) -> bool:
        idx = text.find(symptom)
        if idx == -1:
            return False
        context = text[max(0, idx - 30):idx]
        # Conjunction reset: only check the segment after the last conjunction
        # so "no fever but fatigue" correctly detects fatigue
        for conj in [" but ", ", but ", " and ", ", and ", " however ", ", however "]:
            parts = context.rsplit(conj, 1)
            if len(parts) > 1:
                context = parts[-1]
                break
        negations = ["no ", "not ", "without ", "don't have ", "do not have "]
        return not any(neg in context for neg in negations)

    text_lower = user_text.lower()
    results = []
    for disease, symptoms in symptom_map.items():
        score     = 0
        max_score = sum(symptoms.values())
        for symptom, weight in symptoms.items():
            if symptom_present(text_lower, symptom):
                score += weight
        if score > 0:
            confidence = int((score / max_score) * 90 + 5)
            results.append((disease, confidence))

    results.sort(key=lambda x: x[1], reverse=True)
    return results[:5]


def adjust_confidence(base_conf: int, age: int, known_conditions: list, disease: str) -> int:
    conf = base_conf
    if age >= 60:
        conf += 5
    if disease.lower() in [c.lower() for c in known_conditions]:
        conf += 7
    return min(conf, 100)


# FIX 15: Expanded emergency keywords from 11 → 21
def check_emergency(user_text: str) -> bool:
    """Detect life-threatening symptom keywords."""
    if not user_text:
        return False
    emergency_keywords = [
        # Original 11
        "chest pain", "breathing difficulty", "shortness of breath",
        "unconscious", "stroke", "heart attack",
        "severe headache", "blood vomiting", "seizure",
        "can't breathe", "cannot breathe", "no pulse",
        # New additions (FIX 15)
        "paralysis", "unable to move", "fainting", "collapsed",
        "suicidal", "overdose", "poisoning",
        "anaphylaxis", "allergic reaction", "severe bleeding", "choking",
    ]
    text_lower = user_text.lower()
    return any(kw in text_lower for kw in emergency_keywords)


# ── Lab Value Analyzer ────────────────────────────────────────────────────────
def analyze_lab_values(text: str) -> List[str]:
    """Extract and flag abnormal lab values from report text."""
    findings = []
    checks = [
        (r"HbA1c[:\s]+([\d\.]+)",      lambda v: f"HbA1c is high ({v}%) → Diabetes risk" if v >= 6.5
                                                  else (f"HbA1c borderline ({v}%) → Prediabetes risk" if v >= 5.7 else None)),
        (r"Creatinine[:\s]+([\d\.]+)",  lambda v: f"Creatinine elevated ({v}) → Kidney concern" if v > 1.3 else None),
        (r"Hemoglobin[:\s]+([\d\.]+)",  lambda v: f"Hemoglobin low ({v}) → Possible anemia" if v < 12 else None),
        (r"Cholesterol[:\s]+([\d\.]+)", lambda v: f"Cholesterol high ({v}) → Heart disease risk" if v > 200 else None),
        (r"Vitamin D[:\s]+([\d\.]+)",   lambda v: f"Vitamin D deficiency ({v}) → Bone health risk" if v < 20 else None),
        (r"TSH[:\s]+([\d\.]+)",         lambda v: f"TSH elevated ({v}) → Possible hypothyroidism" if v > 4
                                                  else (f"TSH low ({v}) → Possible hyperthyroidism" if v < 0.4 else None)),
        (r"WBC[:\s]+([\d\.]+)",         lambda v: f"WBC elevated ({v}) → Possible infection" if v > 11000 else None),
        (r"RBC[:\s]+([\d\.]+)",         lambda v: f"RBC low ({v}) → Possible anemia" if v < 4 else None),
        (r"Platelets[:\s]+([\d\.]+)",   lambda v: f"Platelets low ({v}) → Bleeding risk" if v < 150000
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

    # Blood pressure — named label and raw numeric pattern
    bp = re.search(r"(?:Blood Pressure|BP)[:\s]*(\d{2,3})/(\d{2,3})|(\d{2,3})/(\d{2,3})", text, re.IGNORECASE)
    if bp:
        sys_val  = int(bp.group(1) or bp.group(3))
        dias_val = int(bp.group(2) or bp.group(4))
        if sys_val >= 140 or dias_val >= 90:
            findings.append(f"Blood Pressure high ({sys_val}/{dias_val}) → Hypertension risk")
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
            soup    = BeautifulSoup(html, "html.parser")
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
        except Exception:
            return {"success": False, "error": "Web search unavailable", "results": []}


class FileOperationsTool(BaseTool):
    def __init__(self):
        super().__init__()
        self.description = "Read, analyze, and search files in the medical_data and uploads directories"

    def get_schema(self):
        return {
            "operation": "read|analyze|search",
            "file_path": "string (must be inside medical_data/ or uploads/)",
            "search_term": "string (for search)"
        }

    # FIX 14: Path traversal protection
    def _is_safe_path(self, fp: str) -> bool:
        """Return True only if fp resolves inside an allowed directory."""
        try:
            resolved = Path(fp).resolve()
            for allowed in ALLOWED_READ_DIRS:
                if str(resolved).startswith(str(Path(allowed).resolve())):
                    return True
        except Exception:
            pass
        return False

    async def execute(self, operation: str, **kw) -> Dict[str, Any]:
        try:
            if operation == "read":    return await self._read(kw.get("file_path"))
            if operation == "analyze": return await self._analyze(kw.get("file_path"))
            if operation == "search":  return await self._search(kw.get("file_path"), kw.get("search_term", ""))
            return {"success": False, "error": f"Operation '{operation}' not allowed"}
        except Exception:
            return {"success": False, "error": "File operation failed"}

    async def _read(self, fp):
        if not fp: return {"success": False, "error": "No file path provided"}
        if not self._is_safe_path(fp):
            return {"success": False, "error": "Access denied: path outside allowed directories"}
        p = Path(fp)
        if not p.exists(): return {"success": False, "error": f"File not found: {fp}"}
        try:
            if p.suffix == ".json":
                with open(p) as _f:
                    c = json.load(_f)
            elif p.suffix == ".csv":
                with open(p) as f:
                    c = list(csv.DictReader(f))[:100]
            else:
                c = open(p, encoding="utf-8", errors="ignore").read()[:8000]
            return {"success": True, "content": c, "size": p.stat().st_size}
        except Exception:
            return {"success": False, "error": "File read failed"}

    async def _analyze(self, fp):
        r = await self._read(fp)
        if not r.get("success"): return r
        c = str(r.get("content", ""))
        return {"success": True, "analysis": {"lines": len(c.split("\n")), "words": len(c.split()), "chars": len(c)}}

    async def _search(self, fp, term):
        if not term: return {"success": False, "error": "No search term provided"}
        r = await self._read(fp)
        if not r.get("success"): return r
        lines   = str(r.get("content", "")).split("\n")
        matches = [{"line": i + 1, "content": l.strip()}
                   for i, l in enumerate(lines) if term.lower() in l.lower()]
        return {"success": True, "matches": matches[:30], "count": len(matches)}


# ── Memory Manager ────────────────────────────────────────────────────────────
class MemoryManager:
    def __init__(self):
        self.base_path = Path("memory")
        self.base_path.mkdir(exist_ok=True)

    def _user_path(self, username: str) -> Path:
        p = self.base_path / username
        p.mkdir(exist_ok=True)
        return p

    def _session_file(self, username: str, sid: str) -> Path:
        return self._user_path(username) / f"{sid}.json"

    def create_session(self, username: str) -> str:
        existing = self.list_sessions(username)
        if len(existing) >= MAX_SESSIONS:
            oldest = sorted(existing, key=lambda x: x.get("created", ""))
            for old in oldest[:len(existing) - MAX_SESSIONS + 1]:
                self.delete_session(username, old["id"])
        sid  = str(uuid.uuid4())
        data = {"id": sid, "user": username, "created_at": datetime.now().isoformat(),
                "name": "New Chat", "messages": []}
        with open(self._session_file(username, sid), "w") as f:
            json.dump(data, f, indent=2)
        return sid

    def set_session_name(self, username: str, sid: str, name: str):
        fpath = self._session_file(username, sid)
        if not fpath.exists(): return
        with open(fpath) as _f:
            data = json.load(_f)
        data["name"] = name[:40]
        with open(fpath, "w") as f:
            json.dump(data, f, indent=2)

    def add_message(self, username: str, sid: str, role: str, content: str, meta: dict = None):
        fpath = self._session_file(username, sid)
        if not fpath.exists(): return
        with open(fpath) as _f:
            data = json.load(_f)
        msg  = {"role": role, "content": content, "time": datetime.now().isoformat()}
        if meta:
            msg["meta"] = meta
        data["messages"].append(msg)
        # FIX 16: Cap stored messages at 50 to prevent unbounded file growth
        if len(data["messages"]) > 50:
            data["messages"] = data["messages"][-50:]
        with open(fpath, "w") as f:
            json.dump(data, f, indent=2)

    def get_history(self, username: str, sid: str) -> List[dict]:
        fpath = self._session_file(username, sid)
        if not fpath.exists(): return []
        with open(fpath) as _f:
            data = json.load(_f)
        # FIX 21: Return only last 20 messages as Gemini context (not full history)
        msgs = data.get("messages", [])[-20:]
        return [{"role": m["role"], "content": m["content"]} for m in msgs]

    def list_sessions(self, username: str) -> List[dict]:
        sessions = []
        for f in self._user_path(username).glob("*.json"):
            if f.name in ("profile.json", "last_report.json"): continue
            try:
                with open(f) as _jf:
                    d = json.load(_jf)
                if "id" not in d: continue
                msgs = d.get("messages", [])
                # FIX 17: Include last_activity timestamp from last message
                last_activity = msgs[-1]["time"] if msgs else d.get("created_at", "")
                sessions.append({
                    "id":            d["id"],
                    "name":          d.get("name", "New Chat"),
                    "message_count": len(msgs),
                    "created":       d.get("created_at"),
                    "last_activity": last_activity,   # NEW
                })
            except Exception:
                continue
        return sorted(sessions, key=lambda x: x.get("last_activity", ""), reverse=True)

    def save_profile(self, username: str, profile_data: dict):
        fpath = self._user_path(username) / "profile.json"
        with open(fpath, "w") as f:
            json.dump(profile_data, f, indent=2)

    def load_profile(self, username: str) -> Optional[dict]:
        fpath = self._user_path(username) / "profile.json"
        if not fpath.exists(): return None
        with open(fpath) as _f:
            return json.load(_f)

    def delete_session(self, username: str, sid: str) -> bool:
        fpath = self._session_file(username, sid)
        if fpath.exists():
            fpath.unlink()
            return True
        return False

    def save_report(self, username: str, report: dict):
        fpath = self._user_path(username) / "last_report.json"
        with open(fpath, "w") as f:
            json.dump(report, f, indent=2)

    def load_report(self, username: str):
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
            GEMINI_MEDICAL_SYSTEM_PROMPT +
            "\n\nTOOLS:\n" + tool_docs +
            '\nTo use a tool respond ONLY with JSON: {"tool":"name","params":{"key":"value"}}\n'
            "After receiving tool results, answer naturally including the medication section. "
            "If no tool is needed, answer directly and always include the medication section."
        )

    async def _call(self, messages: List[dict], model: str = None) -> str:
        active_model = model or MODEL_NAME
        conversation = f"System: {self._sys()}\n\n"
        for msg in messages:
            if msg["role"] == "system":
                continue
            elif msg["role"] == "user":
                conversation += f"User: {msg['content']}\n\n"
            elif msg["role"] == "assistant":
                conversation += f"Assistant: {msg['content']}\n\n"
        conversation += "Assistant:"

        def _sync_call():
            return gemini_client.models.generate_content(
                model=active_model,
                contents=conversation,
                config=types.GenerateContentConfig(temperature=0.7, max_output_tokens=2048)
            )
        response = await asyncio.to_thread(_sync_call)
        return response.text

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

    async def process(self, message: str, history: List[dict] = None, model: str = None) -> dict:
        msgs = [{"role": "system", "content": self._sys()}]
        for h in (history or []):
            if h["role"] in ("user", "assistant"):
                msgs.append(h)
        msgs.append({"role": "user", "content": message})

        used_tools = []
        for _ in range(4):
            reply     = await self._call(msgs, model=model)
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

        final = await self._call(msgs, model=model)
        return {"response": final, "tools_used": used_tools}

    async def check(self) -> bool:
        try:
            def _sync_ping():
                return gemini_client.models.generate_content(model=MODEL_NAME, contents="ping")
            r = await asyncio.to_thread(_sync_ping)
            return bool(r.text)
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
    global _users_lock
    if _users_lock is None:
        _users_lock = asyncio.Lock()
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
app    = FastAPI(title="MediAssist API")
agent  = AIAgent()
memory = MemoryManager()
load_medical_data()

app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])


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
    message: str = ""
    session_id: Optional[str] = None
    token: str
    model: Optional[str] = None

class ChatResponse(BaseModel):
    response: str
    session_id: str
    tools_used: List[str]
    timestamp: str
    show_hospital_finder: bool = False
    practo_url: str = ""

class ProfileRequest(BaseModel):
    token: str          # FIX 13: token required for auth
    profile: dict


# ── Auth Routes ───────────────────────────────────────────────────────────────
@app.post("/api/signup")
async def signup(req: SignupRequest):
    # FIX 20: Reject empty username
    if not req.username or not req.username.strip():
        raise HTTPException(400, "Username cannot be empty.")
    if not re.match(r'^[a-zA-Z0-9_]{3,32}$', req.username):
        raise HTTPException(400, "Username must be 3-32 chars: letters, numbers, underscores only.")
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
    token                       = str(uuid.uuid4())
    users[req.username]["token"] = token
    await save_users(users)
    memory.save_profile(req.username, {
        "age": req.age or 30,
        "known_conditions": req.known_conditions or []
    })
    return {"token": token, "username": req.username}

@app.post("/api/logout")
async def logout(token: str = Query(None)):
    if not token:
        return {"status": "ok"}
    users = await load_users()
    for username, data in users.items():
        if data.get("token") == token:
            users[username].pop("token", None)
            await save_users(users)
            break
    return {"status": "logged out"}


# ── Profile — FIX 13: Token auth enforced ────────────────────────────────────
@app.post("/api/profile")
async def save_profile_endpoint(req: ProfileRequest):
    # Verify token belongs to the user before saving
    username = await get_current_user(token=req.token)
    if not req.profile:
        raise HTTPException(400, "Invalid profile data")
    memory.save_profile(username, req.profile)
    return {"status": "Profile saved"}


# ── Health ────────────────────────────────────────────────────────────────────
@app.get("/api/health")
async def health():
    ok = await agent.check()
    return {
        "status":        "online",
        "gemini":        "connected" if ok else "not connected",
        "model":         MODEL_NAME,
        "gemini_ready":  ok
    }


# ── Models ────────────────────────────────────────────────────────────────────
@app.get("/api/models")
async def list_models():
    return {"models": [
        "gemini-2.5-flash-lite",
        "gemini-1.5-flash",
        "gemini-2.0-flash",
    ]}


# ── Sessions ──────────────────────────────────────────────────────────────────
@app.get("/api/sessions")
async def list_sessions(username: str = Depends(get_current_user)):
    return memory.list_sessions(username)

@app.get("/api/sessions/{sid}/history")
async def get_history(sid: str, username: str = Depends(get_current_user)):
    # FIX: get_history() returns [] for both missing session and empty session.
    # Check file existence directly to distinguish 404 from empty history.
    if not memory._session_file(username, sid).exists():
        raise HTTPException(404, "Session not found")
    h = memory.get_history(username, sid)
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
    users    = await load_users()
    username = next((u for u, d in users.items() if d.get("token") == req.token), None)
    if not username:
        raise HTTPException(401, "Unauthorized — please login")

    # ── Input validation ──
    if not req.message or not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    req.message = req.message.strip()
    if len(req.message) > 2000:
        raise HTTPException(400, "Message too long (max 2000 characters).")

    active_model = req.model if req.model else MODEL_NAME

    # ── Session ──
    sid     = req.session_id or memory.create_session(username)
    history = memory.get_history(username, sid) or []
    if not history:
        memory.set_session_name(username, sid, req.message)

    # ── Emergency Check ──
    if check_emergency(req.message):
        emg_lower   = req.message.lower()
        emg_slug    = next((slug for kw, slug in EMERGENCY_SPECIALTY.items() if kw in emg_lower), "general-physician")
        emg_display = SPECIALTY_DISPLAY.get(emg_slug, "General Physician")
        emg_practo_url = build_practo_url(emg_slug)
        emergency_response = (
            "🚨 EMERGENCY ALERT\n\n"
            "Your symptoms may indicate a serious or life-threatening condition.\n\n"
            "🔴 Risk Level: Critical\n\n"
            "Please seek immediate medical attention.\n"
            "Call emergency services (112 / 911) or go to the nearest hospital NOW.\n\n"
            f"🩺 **Recommended Specialist:** {emg_display}\n\n"
            "📍 **Finding nearby hospitals for you…**\n\n"
            "⚠️ Disclaimer: This is AI guidance only. Do not delay professional medical care."
        )
        memory.add_message(username, sid, "user", req.message)
        memory.add_message(username, sid, "assistant", emergency_response,
                           {"tools_used": ["Emergency Detector"]})
        return ChatResponse(response=emergency_response, session_id=sid,
                            tools_used=["Emergency Detector"],
                            show_hospital_finder=True,
                            practo_url=emg_practo_url,
                            timestamp=datetime.now().isoformat())

    # ── Uploaded Report Context ──
    report_keywords = ["report", "result", "findings", "uploaded", "my file", "summarise",
                       "summarize", "lab", "test", "scan", "document", "analysis", "blood test",
                       "what does", "explain my", "tell me about my"]
    user_report = USER_REPORTS.get(username) or memory.load_report(username)
    if user_report and any(kw in req.message.lower() for kw in report_keywords):
        prompt = (
            f"You are a medical AI assistant. The user has uploaded a medical report.\n\n"
            f"Uploaded Report ({user_report['filename']}):\n{user_report['text']}\n\n"
            f"User question: {req.message}\n\n"
            "Answer specifically based on the uploaded report. Reference actual values where relevant."
        )
        try:
            text   = await gemini_generate(active_model, prompt)
            result = {"response": text, "tools_used": ["Uploaded Report"]}
        except Exception as e:
            logger.error(f"Gemini report error: {e}")
            raise HTTPException(500, "AI service temporarily unavailable. Please try again.")
        memory.add_message(username, sid, "user", req.message)
        memory.add_message(username, sid, "assistant", result["response"],
                           {"tools_used": result["tools_used"]})
        return ChatResponse(response=result["response"], session_id=sid,
                            tools_used=result["tools_used"],
                            practo_url=build_practo_url("general-physician"),
                            timestamp=datetime.now().isoformat())
    profile          = memory.load_profile(username) or {}
    age              = profile.get("age", 30)
    known_conditions = profile.get("known_conditions", [])

    # ── Symptom Prediction ──
    prediction_list = predict_disease_from_symptoms(req.message)
    # FIX 18: Flood guard — check raw match count BEFORE capping to 3
    # predict() caps at 5 internally, so >5 raw matches means all 5 scored
    raw_match_count = len(prediction_list)
    prediction_list = [
        (disease, adjust_confidence(conf, age, known_conditions, disease))
        for disease, conf in prediction_list
    ]
    prediction_list.sort(key=lambda x: x[1], reverse=True)
    prediction_list = prediction_list[:3]

    # Flood guard: if 5 diseases all scored simultaneously, likely a manipulated/
    # symptom-stuffed input — skip predictor and fall through to Gemini directly
    if raw_match_count <= 4 and prediction_list:
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

        explanation_prompt = f"""You are a clinical triage AI assistant providing informational health guidance.

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
(explain considering age, symptoms, and known conditions)

💊 Immediate Precautions:
(simple actionable advice)

🏥 When to See a Doctor:
(clear medical guidance)

⚠️ Disclaimer: This is AI-generated health guidance, not a medical diagnosis. Please consult a qualified healthcare professional."""

        explanation     = await agent.process(explanation_prompt, history, model=active_model)
        conditions_text = "\n".join(
            [f"{i+1}. {d.title()} ({c}%)" for i, (d, c) in enumerate(prediction_list)]
        )
        med_card = format_medication_card(top_disease)

        final_response = (
            f"🩺 Possible Conditions:\n{conditions_text}\n\n"
            f"📊 Risk Level: {risk_level}\n\n"
            f"{explanation['response']}"
            f"{med_card}"
        )
        memory.add_message(username, sid, "user", req.message)
        memory.add_message(username, sid, "assistant", final_response,
                           {"tools_used": ["Symptom Predictor"]})
        symptom_slug    = DISEASE_SPECIALTY.get(top_disease.lower(), "general-physician")
        symptom_display = SPECIALTY_DISPLAY.get(symptom_slug, "General Physician")
        return ChatResponse(response=final_response, session_id=sid,
                            tools_used=["Symptom Predictor"],
                            practo_url=build_practo_url(symptom_slug),
                            timestamp=datetime.now().isoformat())

    # ── Knowledge Graph ──
    medical_terms = [
        # Disease names
        "diabetes", "hypertension", "migraine", "muscle strain", "viral infection",
        "common cold", "flu", "influenza", "covid", "covid-19", "malaria",
        "anxiety", "anemia", "anaemia", "gastroenteritis", "asthma",
        "urinary tract infection", "uti", "dengue", "dengue fever",
        # General conditions
        "acidity", "gerd", "heartburn", "acid reflux", "thyroid",
        "hypothyroidism", "hyperthyroidism", "kidney", "kidney stone",
        "kidney failure", "liver", "jaundice", "hepatitis", "fatty liver",
        "cholesterol", "heart disease", "heart attack", "psoriasis", "eczema", "acne",
        # Symptoms
        "fever", "cough", "cold", "headache", "bp", "blood pressure",
        "fatigue", "dizziness", "nausea", "vomiting", "diarrhea",
        "chest pain", "shortness of breath", "wheezing", "rash", "itching",
        "joint pain", "leg pain", "muscle pain", "back pain", "lower back pain",
        "palpitations", "sweating", "chills", "swelling", "weakness",
        "pale skin", "blurred vision", "frequent urination", "burning urination",
        "loss of smell", "loss of taste", "runny nose", "sneezing", "sore throat",
        "stomach pain", "bloating", "weight gain", "weight loss", "hair loss",
        # Biomarkers / tests
        "hba1c", "creatinine", "hemoglobin", "haemoglobin", "tsh",
        "wbc", "rbc", "platelets", "sgpt", "sgot", "bilirubin",
        "ldl", "hdl", "triglycerides",
        # Medicines
        "metformin", "insulin", "paracetamol", "cetirizine", "salbutamol",
        "omeprazole", "amlodipine", "sumatriptan", "diclofenac", "ibuprofen",
        "nitrofurantoin", "artemether", "oseltamivir", "escitalopram",
        "ferrous sulphate", "levothyroxine", "atorvastatin", "rosuvastatin",
        "ondansetron", "budesonide",
    ]
    user_text_lower = req.message.lower()
    kg_parts        = []
    seen_nodes      = set()
    for term in medical_terms:
        if term in user_text_lower:
            kg_resp = query_graph(term.title())
            if (kg_resp
                    and isinstance(kg_resp, str)
                    and "No medical knowledge" not in kg_resp
                    and kg_resp not in seen_nodes):
                kg_parts.append(kg_resp)
                seen_nodes.add(kg_resp)

    if kg_parts:
        kg_context = "\n\n".join(kg_parts)
        kg_prompt  = (
            f"{GEMINI_MEDICAL_SYSTEM_PROMPT}\n\n"
            f"Use the following medical knowledge graph facts to answer the user's question "
            f"with a helpful, clear explanation.\n\n"
            f"Knowledge Graph Facts:\n{kg_context}\n\n"
            f"User Question: {req.message}\n\n"
            f"Provide a concise, informative medical response. "
            f"Then add the medication section as instructed above."
        )
        try:
            kg_response = await gemini_generate(active_model, kg_prompt)
            result      = {"response": kg_response, "tools_used": ["Medical KG"]}
        except Exception as e:
            logger.error(f"Gemini KG error: {e}")
            result = None

        if result:
            memory.add_message(username, sid, "user", req.message)
            memory.add_message(username, sid, "assistant", result["response"],
                               {"tools_used": result["tools_used"]})
            return ChatResponse(response=result["response"], session_id=sid,
                                tools_used=result["tools_used"],
                                practo_url=build_practo_url("general-physician"),
                                timestamp=datetime.now().isoformat())

    # ── RAG Search ──
    rag_context = ""
    try:
        rag_results = search_rag(req.message)
        if rag_results and rag_results[0]:
            rag_context = rag_results[0][0]
    except Exception:
        rag_context = ""

    try:
        if rag_context:
            prompt = (
                f"{GEMINI_MEDICAL_SYSTEM_PROMPT}\n\n"
                f"Use this medical context to answer the question.\n\n"
                f"Context:\n{rag_context}\n\n"
                f"Question: {req.message}\n\n"
                "If the context does not contain a relevant answer, answer from general knowledge. "
                "Always end with the medication section as instructed above."
            )
            text   = await gemini_generate(active_model, prompt)
            result = {"response": text, "tools_used": ["RAG"]}
        else:
            result = await agent.process(req.message, history, model=active_model)
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
        practo_url=build_practo_url("general-physician"),
        timestamp=datetime.now().isoformat()
    )


# ── File Upload ───────────────────────────────────────────────────────────────
@app.post("/api/upload")
async def upload_file(file: UploadFile = File(...), token: str = Query(None)):
    upload_username = None
    if token:
        users           = await load_users()
        upload_username = next((u for u, d in users.items() if d.get("token") == token), None)

    try:
        os.makedirs("uploads", exist_ok=True)
        ts        = datetime.now().strftime("%Y%m%d_%H%M%S")
        raw_name  = os.path.basename(file.filename or "upload")
        stem      = Path(raw_name).stem
        ext       = Path(raw_name).suffix.lower()
        safe_stem = re.sub(r"[^\w\-]", "_", stem)[:60]
        safe_name = f"{safe_stem}_{ts}{ext}" if safe_stem else f"upload_{ts}{ext}"
        file_path = os.path.join("uploads", safe_name)
        content   = await file.read()
        if len(content) > 10 * 1024 * 1024:
            return {"status": "error", "message": "File too large. Maximum 10MB."}
        with open(file_path, "wb") as f:
            f.write(content)

        extracted_text = ""
        fname          = file.filename.lower()

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
            return {"status": "error", "message": f"Unsupported file format: {file.filename}"}

        if not extracted_text.strip():
            return {"status": "error", "message": "No readable text found in the file"}

        report_text = extracted_text[:8000]

        if upload_username:
            report_obj = {"text": report_text, "filename": file.filename}
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

⚠️ Disclaimer: This analysis is AI-generated and not a medical diagnosis. Consult a doctor."""

        try:
            analysis = await gemini_generate(MODEL_NAME, medical_prompt)
        except Exception as e:
            logger.error(f"Gemini upload error: {e}")
            return {"status": "error", "message": "AI analysis temporarily unavailable. Report saved — ask about it in chat."}

        return {"status": "success", "analysis": analysis, "lab_findings": findings, "summary": analysis}

    except Exception as e:
        logger.error(f"Upload error: {e}")
        return {"status": "error", "message": "Upload failed. Please try again."}


# ── Nearby Hospitals ─────────────────────────────────────────────────────────
@app.get("/api/nearby-hospitals")
async def nearby_hospitals(lat: float = Query(...), lng: float = Query(...), city: str = Query(None)):
    """
    Returns hospital finder links for the given coordinates and city name.
    No external API key needed — uses Google Maps, Practo, Justdial deep search URLs.
    """
    lat_s = f"{lat:.6f}"
    lng_s = f"{lng:.6f}"

    # Use city name if provided, otherwise use coordinates
    location_str = urllib.parse.quote_plus(city) if city and city != "Your Location" else urllib.parse.quote_plus(f"{lat_s},{lng_s}")
    city_display = city if city and city != "Your Location" else f"{lat_s}, {lng_s}"

    links = {
        "google_maps": {
            "name": "Google Maps",
            "emoji": "🗺️",
            "url": f"https://www.google.com/maps/search/hospitals/@{lat_s},{lng_s},14z",
            "desc": "View hospitals on map with directions",
        },
        "google_search": {
            "name": "Google Search",
            "emoji": "🔍",
            "url": f"https://www.google.com/search?q=hospitals+in+{location_str}" if city and city != "Your Location" else f"https://www.google.com/search?q=hospitals+near+me",
            "desc": "Search for nearby hospitals",
        },
        "practo": {
            "name": "Practo",
            "emoji": "🏥",
            "url": f"https://www.practo.com/search/doctors?results_type=doctor&q=%5B%7B%22word%22%3A%22general+physician%22%2C%22autocompleted%22%3Atrue%2C%22category%22%3A%22subspeciality%22%7D%5D&city={location_str}",
            "desc": "Book nearby general physician appointments",
        },
        "justdial": {
            "name": "Justdial",
            "emoji": "📞",
            "url": f"https://www.justdial.com/{city.replace(' ', '-') if city and city != 'Your Location' else 'India'}/Hospitals",
            "desc": "Find hospitals with ratings & phone numbers",
        },
    }

    return {
        "lat": lat,
        "lng": lng,
        "city": city_display,
        "links": links,
        "maps_embed_url": f"https://maps.google.com/maps?q=hospitals+near+me&ll={lat_s},{lng_s}&z=14&output=embed",
    }


# ── Pharmacy Order Intent ─────────────────────────────────────────────────────
@app.get("/api/pharmacy-links")
async def pharmacy_links(medicine: str = Query(...), strips: int = Query(1)):
    """
    Returns pharmacy order links for the given medicine name and strip count.
    """
    query = urllib.parse.quote_plus(medicine)
    return {
        "medicine": medicine,
        "strips": strips,
        "links": {
            "pharmeasy": {
                "name": "PharmEasy",
                "emoji": "🟣",
                "url": f"https://pharmeasy.in/search/all?name={query}",
                "desc": "Fast delivery · Trusted pharmacy",
            },
            "1mg": {
                "name": "1mg (Tata)",
                "emoji": "🔴",
                "url": f"https://www.1mg.com/search/all?name={query}",
                "desc": "Doctor consults + medicines",
            },
            "netmeds": {
                "name": "Netmeds",
                "emoji": "🟢",
                "url": f"https://www.netmeds.com/catalogsearch/result/all?q={query}",
                "desc": "Pan-India delivery",
            },
        },
    }


# ── Frontend ──────────────────────────────────────────────────────────────────
@app.get("/", response_class=HTMLResponse)
async def index():
    html_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "index.html")
    with open(html_path, encoding="utf-8") as f:
        return HTMLResponse(f.read())


# ── Entry Point ───────────────────────────────────────────────────────────────
if __name__ == "__main__":
    print("=" * 50)
    print("  MediAssist — Google Gemini Edition")
    print("=" * 50)
    print(f"\n  Model  : {MODEL_NAME}")
    print(f"  Browser: http://localhost:{PORT}")
    print("  Stop   : CTRL+C\n")
    print("=" * 50)
    uvicorn.run("app:app", host="0.0.0.0", port=PORT, reload=False)