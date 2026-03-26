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
from bs4 import BeautifulSoup
import fitz  # PyMuPDF

from google import genai
from google.genai import types

from knowledge_graph.graph import query_graph
from lab_services import analyze_lab_values, compare_lab_records, extract_lab_metrics, summarize_metric_snapshot
from med_safety import assess_medication_safety, build_safety_summary, check_drug_interactions
from models import ChatRequest, ChatResponse, LoginRequest, ProfileRequest, SignupRequest, ExpertConsultation
from rag.rag_engine import search_rag, add_document_to_rag
from services.profile import normalize_profile, profile_from_login
from services.triage import (
    build_followup_prompt,
    combine_messages_for_assessment,
    maybe_create_followup_state,
    merge_followup_answers,
    needs_more_followup,
)
from services.analytics import add_health_metric, get_health_trends, get_dashboard_summary, generate_health_report
from services.security import security_manager
from services.expert_consultation import expert_manager
from services.language import language_manager

# ── Advanced Prompts and Response Validation ──────────────────────────────────
from prompts.medical_prompts import (
    MEDICAL_REASONING_SYSTEM_PROMPT,
    SYMPTOM_ANALYSIS_PROMPT,
    PatientContext,
    build_symptom_analysis_prompt,
)
from services.response_validator import (
    ResponseValidator,
    process_validated_response,
    create_validator,
)


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
                "buy_url": "https://www.1mg.com/search/all?name=cetirizine+10mg"
            },
            {
                "name": "Paracetamol 500mg",
                "type": "Antipyretic / Analgesic",
                "composition": "Paracetamol (Acetaminophen) 500mg",
                "dosage": "1–2 tablets every 4–6 hours as needed",
                "duration": "Until fever/pain subsides (max 3 days)",
                "purpose": "Reduces fever and body ache",
                "buy_url": "https://www.1mg.com/search/all?name=paracetamol+500mg"
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
                "buy_url": "https://www.1mg.com/search/all?name=oseltamivir+75mg"
            },
            {
                "name": "Paracetamol 650mg",
                "type": "Antipyretic",
                "composition": "Paracetamol 650mg",
                "dosage": "1 tablet every 6 hours",
                "duration": "Until fever subsides",
                "purpose": "Controls high fever and body ache in flu",
                "buy_url": "https://www.1mg.com/search/all?name=paracetamol+650mg"
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
                "buy_url": "https://www.1mg.com/search/all?name=paracetamol+650mg"
            },
            {
                "name": "Vitamin D3 + Zinc Supplement",
                "type": "Immune support supplement",
                "composition": "Cholecalciferol (Vitamin D3) + Zinc Sulphate",
                "dosage": "As directed on pack (typically once daily)",
                "duration": "2–4 weeks",
                "purpose": "Supports immune system during COVID recovery",
                "buy_url": "https://www.1mg.com/search/all?name=vitamin+d3+zinc"
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
                "buy_url": "https://www.1mg.com/search/all?name=metformin+500mg"
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
                "buy_url": "https://www.1mg.com/search/all?name=amlodipine+5mg"
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
                "buy_url": "https://www.1mg.com/search/all?name=sumatriptan+50mg"
            },
            {
                "name": "Naproxen 500mg",
                "type": "NSAID / Anti-inflammatory",
                "composition": "Naproxen Sodium 500mg",
                "dosage": "1 tablet twice daily with food",
                "duration": "2–3 days during migraine episode",
                "purpose": "Reduces migraine pain and inflammation",
                "buy_url": "https://www.1mg.com/search/all?name=naproxen+500mg"
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
                "buy_url": "https://www.1mg.com/search/all?name=paracetamol+vitamin+c"
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
                "buy_url": "https://www.1mg.com/search/all?name=artemether+lumefantrine"
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
                "buy_url": "https://www.1mg.com/search/all?name=paracetamol+650mg"
            },
            {
                "name": "ORS Sachets (Oral Rehydration Salts)",
                "type": "Rehydration solution",
                "composition": "Sodium Chloride + Potassium Chloride + Sodium Citrate + Glucose",
                "dosage": "1 sachet dissolved in 1 litre water — sip throughout the day",
                "duration": "Until fever and weakness subside",
                "purpose": "Prevents dehydration, critical in dengue management",
                "buy_url": "https://www.1mg.com/search/all?name=ors+sachet"
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
                "buy_url": "https://www.1mg.com/search/all?name=diclofenac+paracetamol"
            },
            {
                "name": "Volini / Diclofenac Gel (Topical)",
                "type": "Topical NSAID gel",
                "composition": "Diclofenac Diethylamine 1.16% w/w",
                "dosage": "Apply a thin layer on the affected area 3–4 times daily",
                "duration": "5–7 days",
                "purpose": "Directly relieves muscle pain and stiffness at the site",
                "buy_url": "https://www.1mg.com/search/all?name=diclofenac+gel"
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
                "buy_url": "https://www.1mg.com/search/all?name=escitalopram+10mg"
            },
            {
                "name": "Clonazepam 0.5mg (short-term only)",
                "type": "Benzodiazepine / Anti-anxiety",
                "composition": "Clonazepam 0.5mg",
                "dosage": "0.5mg once or twice daily as needed (short-term only)",
                "duration": "2–4 weeks maximum — strictly under doctor prescription",
                "purpose": "Fast-acting relief of acute anxiety and panic",
                "buy_url": "https://www.1mg.com/search/all?name=clonazepam+0.5mg"
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
                "buy_url": "https://www.1mg.com/search/all?name=ferrous+sulphate+200mg"
            },
            {
                "name": "Vitamin B12 (Methylcobalamin 500mcg)",
                "type": "Vitamin B12 supplement tablet",
                "composition": "Methylcobalamin 500mcg",
                "dosage": "1 tablet once daily",
                "duration": "3 months or as advised by doctor",
                "purpose": "Treats B12-deficiency anaemia and nerve damage",
                "buy_url": "https://www.1mg.com/search/all?name=methylcobalamin+500mcg"
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
                "buy_url": "https://www.1mg.com/search/all?name=ors+sachet"
            },
            {
                "name": "Ondansetron 4mg",
                "type": "Antiemetic tablet / dissolvable strip",
                "composition": "Ondansetron Hydrochloride 4mg",
                "dosage": "1 tablet every 8 hours for nausea / vomiting",
                "duration": "1–2 days",
                "purpose": "Controls nausea and vomiting",
                "buy_url": "https://www.1mg.com/search/all?name=ondansetron+4mg"
            },
            {
                "name": "Racecadotril 100mg",
                "type": "Antidiarrhoeal tablet",
                "composition": "Racecadotril 100mg",
                "dosage": "1 tablet three times daily before meals",
                "duration": "3–5 days",
                "purpose": "Reduces severity and duration of acute diarrhoea",
                "buy_url": "https://www.1mg.com/search/all?name=racecadotril+100mg"
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
                "buy_url": "https://www.1mg.com/search/all?name=salbutamol+inhaler"
            },
            {
                "name": "Budesonide 200mcg Inhaler",
                "type": "Inhaled corticosteroid (preventer inhaler)",
                "composition": "Budesonide 200mcg per actuation",
                "dosage": "1–2 puffs twice daily (morning and night)",
                "duration": "Long-term preventive — do not stop without doctor advice",
                "purpose": "Reduces airway inflammation and prevents asthma attacks",
                "buy_url": "https://www.1mg.com/search/all?name=budesonide+inhaler"
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
                "buy_url": "https://www.1mg.com/search/all?name=nitrofurantoin+100mg"
            },
            {
                "name": "Phenazopyridine 200mg (Uristat)",
                "type": "Urinary analgesic tablet",
                "composition": "Phenazopyridine Hydrochloride 200mg",
                "dosage": "1 tablet three times daily after meals",
                "duration": "2 days (pain relief only — not an antibiotic)",
                "purpose": "Relieves burning, urgency, and discomfort during urination",
                "buy_url": "https://www.1mg.com/search/all?name=phenazopyridine"
            }
        ]
    },

    # ── Cardiovascular ──
    "coronary artery disease": {
        "medicines": [
            {"name": "Aspirin 75mg", "type": "Antiplatelet", "composition": "Aspirin 75mg", "dosage": "1 tablet once daily", "duration": "Long-term — as prescribed", "purpose": "Prevents blood clots and reduces heart attack risk", "buy_url": "https://www.1mg.com/search/all?name=aspirin+75mg"},
            {"name": "Atorvastatin 20mg", "type": "Statin (cholesterol-lowering)", "composition": "Atorvastatin Calcium 20mg", "dosage": "1 tablet once daily at night", "duration": "Long-term — as prescribed", "purpose": "Lowers cholesterol to reduce plaque buildup", "buy_url": "https://www.1mg.com/search/all?name=atorvastatin+20mg"}
        ]
    },
    "heart failure": {
        "medicines": [
            {"name": "Furosemide 40mg", "type": "Loop diuretic", "composition": "Furosemide 40mg", "dosage": "1 tablet once or twice daily", "duration": "As directed by cardiologist", "purpose": "Removes excess fluid to reduce swelling and breathlessness", "buy_url": "https://www.1mg.com/search/all?name=furosemide+40mg"},
            {"name": "Ramipril 5mg", "type": "ACE Inhibitor", "composition": "Ramipril 5mg", "dosage": "1 tablet once daily", "duration": "Long-term — do not stop without doctor advice", "purpose": "Protects heart and improves heart function", "buy_url": "https://www.1mg.com/search/all?name=ramipril+5mg"}
        ]
    },
    "arrhythmia": {
        "medicines": [
            {"name": "Metoprolol 50mg", "type": "Beta-blocker", "composition": "Metoprolol Succinate 50mg", "dosage": "1 tablet once daily", "duration": "Long-term — as prescribed", "purpose": "Controls heart rate and rhythm", "buy_url": "https://www.1mg.com/search/all?name=metoprolol+50mg"}
        ]
    },
    "deep vein thrombosis": {
        "medicines": [
            {"name": "Rivaroxaban 15mg", "type": "Anticoagulant (blood thinner)", "composition": "Rivaroxaban 15mg", "dosage": "1 tablet twice daily with food for 21 days, then 20mg once daily", "duration": "At least 3 months — as directed", "purpose": "Prevents clot growth and new clot formation — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=rivaroxaban+15mg"}
        ]
    },

    # ── Respiratory ──
    "pneumonia": {
        "medicines": [
            {"name": "Amoxicillin 500mg", "type": "Antibiotic", "composition": "Amoxicillin Trihydrate 500mg", "dosage": "1 capsule three times daily", "duration": "7–10 days — complete full course", "purpose": "Treats bacterial pneumonia", "buy_url": "https://www.1mg.com/search/all?name=amoxicillin+500mg"},
            {"name": "Azithromycin 500mg", "type": "Macrolide antibiotic", "composition": "Azithromycin 500mg", "dosage": "1 tablet once daily", "duration": "3–5 days", "purpose": "Treats atypical pneumonia — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=azithromycin+500mg"}
        ]
    },
    "copd": {
        "medicines": [
            {"name": "Tiotropium 18mcg Inhaler", "type": "Long-acting anticholinergic bronchodilator", "composition": "Tiotropium Bromide 18mcg", "dosage": "1 inhalation once daily", "duration": "Long-term maintenance", "purpose": "Opens airways long-term to improve breathing", "buy_url": "https://www.1mg.com/search/all?name=tiotropium+inhaler"},
            {"name": "Salbutamol Inhaler 100mcg", "type": "Short-acting bronchodilator", "composition": "Salbutamol Sulfate 100mcg per actuation", "dosage": "1–2 puffs as needed for breathlessness", "duration": "As needed rescue use", "purpose": "Quick relief of acute breathlessness", "buy_url": "https://www.1mg.com/search/all?name=salbutamol+inhaler"}
        ]
    },
    "bronchitis": {
        "medicines": [
            {"name": "Ambroxol 30mg", "type": "Mucolytic", "composition": "Ambroxol Hydrochloride 30mg", "dosage": "1 tablet three times daily", "duration": "5–7 days", "purpose": "Thins mucus to make coughing easier", "buy_url": "https://www.1mg.com/search/all?name=ambroxol+30mg"},
            {"name": "Dextromethorphan + Guaifenesin Syrup", "type": "Cough suppressant + Expectorant", "composition": "Dextromethorphan + Guaifenesin", "dosage": "10ml every 6–8 hours", "duration": "5–7 days", "purpose": "Suppresses cough and loosens mucus", "buy_url": "https://www.1mg.com/search/all?name=dextromethorphan+guaifenesin"}
        ]
    },

    # ── Gastrointestinal ──
    "gerd": {
        "medicines": [
            {"name": "Pantoprazole 40mg", "type": "Proton Pump Inhibitor", "composition": "Pantoprazole Sodium 40mg", "dosage": "1 tablet once daily before breakfast", "duration": "4–8 weeks, may extend if needed", "purpose": "Reduces stomach acid to heal esophagus", "buy_url": "https://www.1mg.com/search/all?name=pantoprazole+40mg"},
            {"name": "Domperidone 10mg", "type": "Prokinetic", "composition": "Domperidone 10mg", "dosage": "1 tablet three times daily before meals", "duration": "2–4 weeks", "purpose": "Improves stomach emptying, reduces regurgitation", "buy_url": "https://www.1mg.com/search/all?name=domperidone+10mg"}
        ]
    },
    "peptic ulcer": {
        "medicines": [
            {"name": "Omeprazole 20mg", "type": "Proton Pump Inhibitor", "composition": "Omeprazole 20mg", "dosage": "1 capsule once daily before breakfast", "duration": "4–8 weeks", "purpose": "Heals ulcer by reducing stomach acid", "buy_url": "https://www.1mg.com/search/all?name=omeprazole+20mg"},
            {"name": "Sucralfate 1g", "type": "Mucosal protectant", "composition": "Sucralfate 1g", "dosage": "1 tablet four times daily on empty stomach", "duration": "4–8 weeks", "purpose": "Coats and protects ulcer from acid", "buy_url": "https://www.1mg.com/search/all?name=sucralfate+1g"}
        ]
    },
    "irritable bowel syndrome": {
        "medicines": [
            {"name": "Mebeverine 135mg", "type": "Antispasmodic", "composition": "Mebeverine Hydrochloride 135mg", "dosage": "1 tablet three times daily before meals", "duration": "As needed for symptoms", "purpose": "Relieves abdominal cramps and spasms", "buy_url": "https://www.1mg.com/search/all?name=mebeverine+135mg"},
            {"name": "Psyllium Husk (Isabgol)", "type": "Fiber supplement", "composition": "Psyllium husk fiber", "dosage": "1–2 teaspoons in water daily", "duration": "Long-term as needed", "purpose": "Regulates bowel movements", "buy_url": "https://www.1mg.com/search/all?name=isabgol"}
        ]
    },

    # ── Endocrine ──
    "hypothyroidism": {
        "medicines": [
            {"name": "Levothyroxine 50mcg", "type": "Thyroid hormone replacement", "composition": "Levothyroxine Sodium 50mcg", "dosage": "1 tablet once daily on empty stomach (30 min before food)", "duration": "Lifelong — do not stop without doctor advice", "purpose": "Replaces deficient thyroid hormone", "buy_url": "https://www.1mg.com/search/all?name=levothyroxine+50mcg"}
        ]
    },
    "hyperthyroidism": {
        "medicines": [
            {"name": "Methimazole 10mg", "type": "Antithyroid", "composition": "Methimazole 10mg", "dosage": "1 tablet once or twice daily as directed", "duration": "1–2 years typically — doctor monitored", "purpose": "Reduces thyroid hormone production", "buy_url": "https://www.1mg.com/search/all?name=methimazole+10mg"},
            {"name": "Propranolol 40mg", "type": "Beta-blocker", "composition": "Propranolol Hydrochloride 40mg", "dosage": "1 tablet two to three times daily", "duration": "Until thyroid controlled", "purpose": "Controls rapid heartbeat and tremors", "buy_url": "https://www.1mg.com/search/all?name=propranolol+40mg"}
        ]
    },

    # ── Musculoskeletal ──
    "rheumatoid arthritis": {
        "medicines": [
            {"name": "Methotrexate 7.5mg", "type": "DMARD", "composition": "Methotrexate 7.5mg", "dosage": "Once weekly (same day each week)", "duration": "Long-term — requires monitoring", "purpose": "Slows disease progression — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=methotrexate+7.5mg"},
            {"name": "Folic Acid 5mg", "type": "Vitamin supplement", "composition": "Folic Acid 5mg", "dosage": "1 tablet daily (not on methotrexate day)", "duration": "As long as on methotrexate", "purpose": "Reduces methotrexate side effects", "buy_url": "https://www.1mg.com/search/all?name=folic+acid+5mg"}
        ]
    },
    "osteoarthritis": {
        "medicines": [
            {"name": "Paracetamol 650mg", "type": "Analgesic", "composition": "Paracetamol 650mg", "dosage": "1 tablet every 6–8 hours as needed", "duration": "As needed for pain", "purpose": "First-line pain relief for osteoarthritis", "buy_url": "https://www.1mg.com/search/all?name=paracetamol+650mg"},
            {"name": "Glucosamine + Chondroitin", "type": "Joint health supplement", "composition": "Glucosamine Sulfate 500mg + Chondroitin Sulfate 400mg", "dosage": "1 tablet twice daily", "duration": "Long-term — may take weeks to show benefit", "purpose": "Supports joint cartilage health", "buy_url": "https://www.1mg.com/search/all?name=glucosamine+chondroitin"}
        ]
    },
    "gout": {
        "medicines": [
            {"name": "Colchicine 0.5mg", "type": "Anti-gout", "composition": "Colchicine 0.5mg", "dosage": "1 tablet 2–3 times daily during acute attack", "duration": "Until attack resolves (3–5 days)", "purpose": "Reduces inflammation in acute gout attack", "buy_url": "https://www.1mg.com/search/all?name=colchicine+0.5mg"},
            {"name": "Allopurinol 100mg", "type": "Urate-lowering therapy", "composition": "Allopurinol 100mg", "dosage": "1 tablet once daily (start low, increase gradually)", "duration": "Long-term to prevent attacks", "purpose": "Lowers uric acid levels — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=allopurinol+100mg"}
        ]
    },
    "sciatica": {
        "medicines": [
            {"name": "Pregabalin 75mg", "type": "Neuropathic pain medication", "composition": "Pregabalin 75mg", "dosage": "1 capsule twice daily", "duration": "As directed — may be long-term", "purpose": "Relieves nerve pain — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=pregabalin+75mg"},
            {"name": "Diclofenac 50mg", "type": "NSAID", "composition": "Diclofenac Sodium 50mg", "dosage": "1 tablet twice daily after food", "duration": "5–7 days", "purpose": "Reduces inflammation and pain", "buy_url": "https://www.1mg.com/search/all?name=diclofenac+50mg"}
        ]
    },
    "fibromyalgia": {
        "medicines": [
            {"name": "Pregabalin 75mg", "type": "Anticonvulsant/Pain medication", "composition": "Pregabalin 75mg", "dosage": "1 capsule twice daily", "duration": "Long-term as directed", "purpose": "Reduces pain and improves sleep — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=pregabalin+75mg"},
            {"name": "Duloxetine 30mg", "type": "SNRI Antidepressant", "composition": "Duloxetine 30mg", "dosage": "1 capsule once daily", "duration": "Long-term as directed", "purpose": "Treats pain and depression in fibromyalgia — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=duloxetine+30mg"}
        ]
    },

    # ── Neurological ──
    "epilepsy": {
        "medicines": [
            {"name": "Levetiracetam 500mg", "type": "Antiepileptic", "composition": "Levetiracetam 500mg", "dosage": "1 tablet twice daily", "duration": "Long-term — do not stop abruptly", "purpose": "Prevents seizures — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=levetiracetam+500mg"}
        ]
    },
    "vertigo": {
        "medicines": [
            {"name": "Betahistine 16mg", "type": "Antivertigo", "composition": "Betahistine Dihydrochloride 16mg", "dosage": "1 tablet three times daily", "duration": "As prescribed — may be long-term", "purpose": "Improves inner ear blood flow, reduces vertigo", "buy_url": "https://www.1mg.com/search/all?name=betahistine+16mg"},
            {"name": "Meclizine 25mg", "type": "Antihistamine / Antiemetic", "composition": "Meclizine Hydrochloride 25mg", "dosage": "1 tablet once or twice daily", "duration": "As needed for acute episodes", "purpose": "Relieves dizziness and nausea", "buy_url": "https://www.1mg.com/search/all?name=meclizine+25mg"}
        ]
    },

    # ── Mental Health ──
    "depression": {
        "medicines": [
            {"name": "Sertraline 50mg", "type": "SSRI Antidepressant", "composition": "Sertraline Hydrochloride 50mg", "dosage": "1 tablet once daily (morning or night)", "duration": "Long-term — minimum 6-12 months", "purpose": "Treats depression by increasing serotonin — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=sertraline+50mg"}
        ]
    },
    "panic disorder": {
        "medicines": [
            {"name": "Paroxetine 20mg", "type": "SSRI Antidepressant", "composition": "Paroxetine Hydrochloride 20mg", "dosage": "1 tablet once daily", "duration": "Long-term as directed", "purpose": "Prevents panic attacks — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=paroxetine+20mg"}
        ]
    },
    "ptsd": {
        "medicines": [
            {"name": "Sertraline 50mg", "type": "SSRI Antidepressant", "composition": "Sertraline Hydrochloride 50mg", "dosage": "1 tablet once daily", "duration": "Long-term as directed", "purpose": "First-line treatment for PTSD — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=sertraline+50mg"}
        ]
    },
    "bipolar disorder": {
        "medicines": [
            {"name": "Lithium 300mg", "type": "Mood stabilizer", "composition": "Lithium Carbonate 300mg", "dosage": "As directed — requires blood level monitoring", "duration": "Long-term", "purpose": "Stabilizes mood in bipolar disorder — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=lithium+300mg"}
        ]
    },
    "ocd": {
        "medicines": [
            {"name": "Fluoxetine 20mg", "type": "SSRI Antidepressant", "composition": "Fluoxetine Hydrochloride 20mg", "dosage": "1 capsule once daily (may increase to 60-80mg)", "duration": "Long-term as directed", "purpose": "Treats OCD symptoms — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=fluoxetine+20mg"}
        ]
    },

    # ── Dermatological ──
    "eczema": {
        "medicines": [
            {"name": "Hydrocortisone 1% Cream", "type": "Topical corticosteroid", "composition": "Hydrocortisone 1%", "dosage": "Apply thin layer to affected areas twice daily", "duration": "7–14 days (avoid prolonged use)", "purpose": "Reduces inflammation and itching", "buy_url": "https://www.1mg.com/search/all?name=hydrocortisone+cream"},
            {"name": "Cetirizine 10mg", "type": "Antihistamine", "composition": "Cetirizine Hydrochloride 10mg", "dosage": "1 tablet at night", "duration": "As needed for itching", "purpose": "Reduces itching", "buy_url": "https://www.1mg.com/search/all?name=cetirizine+10mg"}
        ]
    },
    "psoriasis": {
        "medicines": [
            {"name": "Clobetasol 0.05% Cream", "type": "High-potency topical corticosteroid", "composition": "Clobetasol Propionate 0.05%", "dosage": "Apply thin layer twice daily", "duration": "2 weeks max — not for face/groin", "purpose": "Reduces inflammation and scaling", "buy_url": "https://www.1mg.com/search/all?name=clobetasol+cream"},
            {"name": "Coal Tar Shampoo/Ointment", "type": "Keratolytic", "composition": "Coal tar solution", "dosage": "Apply to affected areas daily", "duration": "As needed", "purpose": "Slows skin cell growth, reduces scaling", "buy_url": "https://www.1mg.com/search/all?name=coal+tar"}
        ]
    },
    "shingles": {
        "medicines": [
            {"name": "Acyclovir 800mg", "type": "Antiviral", "composition": "Acyclovir 800mg", "dosage": "1 tablet five times daily (every 4 hours while awake)", "duration": "7 days — start within 72 hours of rash", "purpose": "Reduces severity and duration of shingles", "buy_url": "https://www.1mg.com/search/all?name=acyclovir+800mg"},
            {"name": "Gabapentin 300mg", "type": "Neuropathic pain medication", "composition": "Gabapentin 300mg", "dosage": "1 capsule three times daily (increase gradually)", "duration": "As needed for postherpetic neuralgia", "purpose": "Relieves nerve pain after shingles — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=gabapentin+300mg"}
        ]
    },
    "cellulitis": {
        "medicines": [
            {"name": "Cephalexin 500mg", "type": "Antibiotic", "composition": "Cephalexin 500mg", "dosage": "1 capsule four times daily", "duration": "7–14 days — complete full course", "purpose": "Treats bacterial skin infection", "buy_url": "https://www.1mg.com/search/all?name=cephalexin+500mg"}
        ]
    },

    # ── Urological ──
    "kidney stones": {
        "medicines": [
            {"name": "Tamsulosin 0.4mg", "type": "Alpha-blocker", "composition": "Tamsulosin Hydrochloride 0.4mg", "dosage": "1 capsule once daily", "duration": "Until stone passes (2–4 weeks)", "purpose": "Relaxes ureter to help stone pass — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=tamsulosin+0.4mg"},
            {"name": "Diclofenac 50mg", "type": "NSAID", "composition": "Diclofenac Sodium 50mg", "dosage": "1 tablet twice daily after food", "duration": "As needed for pain", "purpose": "Relieves kidney stone pain", "buy_url": "https://www.1mg.com/search/all?name=diclofenac+50mg"}
        ]
    },
    "bph": {
        "medicines": [
            {"name": "Tamsulosin 0.4mg", "type": "Alpha-blocker", "composition": "Tamsulosin Hydrochloride 0.4mg", "dosage": "1 capsule once daily after a meal", "duration": "Long-term", "purpose": "Relaxes prostate and bladder neck muscles — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=tamsulosin+0.4mg"},
            {"name": "Finasteride 5mg", "type": "5-alpha reductase inhibitor", "composition": "Finasteride 5mg", "dosage": "1 tablet once daily", "duration": "Long-term — may take 6 months for full effect", "purpose": "Shrinks enlarged prostate — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=finasteride+5mg"}
        ]
    },
    "interstitial cystitis": {
        "medicines": [
            {"name": "Pentosan Polysulfate 100mg", "type": "Bladder protectant", "composition": "Pentosan Polysulfate Sodium 100mg", "dosage": "1 capsule three times daily", "duration": "Long-term — may take 3-6 months for effect", "purpose": "Coats and protects bladder lining — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=pentosan+polysulfate"}
        ]
    },

    # ── Infectious ──
    "tuberculosis": {
        "medicines": [
            {"name": "Isoniazid 300mg", "type": "Antitubercular", "composition": "Isoniazid 300mg", "dosage": "1 tablet once daily", "duration": "6-9 months as part of combination therapy", "purpose": "Kills TB bacteria — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=isoniazid+300mg"},
            {"name": "Rifampicin 450mg", "type": "Antitubercular", "composition": "Rifampicin 450mg", "dosage": "1 capsule once daily on empty stomach", "duration": "6-9 months as part of combination therapy", "purpose": "Kills TB bacteria — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=rifampicin+450mg"}
        ]
    },
    "typhoid fever": {
        "medicines": [
            {"name": "Azithromycin 500mg", "type": "Macrolide antibiotic", "composition": "Azithromycin 500mg", "dosage": "1 tablet once daily", "duration": "7 days", "purpose": "Treats typhoid fever — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=azithromycin+500mg"},
            {"name": "Ciprofloxacin 500mg", "type": "Fluoroquinolone antibiotic", "composition": "Ciprofloxacin 500mg", "dosage": "1 tablet twice daily", "duration": "7-14 days", "purpose": "Alternative treatment for typhoid — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=ciprofloxacin+500mg"}
        ]
    },
    "chickenpox": {
        "medicines": [
            {"name": "Acyclovir 400mg", "type": "Antiviral", "composition": "Acyclovir 400mg", "dosage": "1 tablet five times daily", "duration": "5-7 days", "purpose": "Reduces severity in high-risk patients", "buy_url": "https://www.1mg.com/search/all?name=acyclovir+400mg"},
            {"name": "Calamine Lotion", "type": "Topical antipruritic", "composition": "Calamine, Zinc Oxide", "dosage": "Apply to itchy areas as needed", "duration": "Until rash resolves", "purpose": "Relieves itching from chickenpox rash", "buy_url": "https://www.1mg.com/search/all?name=calamine+lotion"}
        ]
    },
    "hepatitis b": {
        "medicines": [
            {"name": "Tenofovir 300mg", "type": "Antiviral", "composition": "Tenofovir Disoproxil Fumarate 300mg", "dosage": "1 tablet once daily", "duration": "Long-term — as directed by hepatologist", "purpose": "Suppresses hepatitis B virus — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=tenofovir+300mg"}
        ]
    },
    "hepatitis c": {
        "medicines": [
            {"name": "Sofosbuvir 400mg + Velpatasvir 100mg", "type": "Direct-acting antiviral", "composition": "Sofosbuvir 400mg + Velpatasvir 100mg", "dosage": "1 tablet once daily", "duration": "12 weeks", "purpose": "Cures hepatitis C with >95% success rate — PRESCRIPTION ONLY", "buy_url": "https://www.1mg.com/search/all?name=sofosbuvir+velpatasvir"}
        ]
    },
    "hepatitis a": {
        "medicines": [
            {"name": "ORS (Oral Rehydration Salts)", "type": "Supportive care", "composition": "WHO formula ORS", "dosage": "As needed to maintain hydration", "duration": "Throughout illness", "purpose": "Prevents dehydration — no specific antiviral for Hep A", "buy_url": "https://www.1mg.com/search/all?name=ors+sachets"}
        ]
    }
}


def format_medication_card(disease: str, quantity: int = 1, safety_report: dict = None) -> str:
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
    if safety_report and (safety_report.get("warnings") or safety_report.get("safer_alternatives")):
        lines.append("### ⚠️ Medication Safety Check")
        for warning in build_safety_summary(safety_report):
            lines.append(f"- {warning}")
        lines.append("")
    for med in meds["medicines"]:
        lines.append(f"### 🔹 {med['name']}")
        med_status = (safety_report or {}).get("medication_status", {}).get(med["name"], {})
        if med_status.get("status") == "blocked":
            lines.append("- **Safety:** BLOCKED for your current profile. Do not self-start this without clinician review.")
        elif med_status.get("status") == "caution":
            lines.append("- **Safety:** Use caution. Review the warnings below before considering this medication.")
        else:
            lines.append("- **Safety:** No major profile conflicts detected by the local safety checker.")
        lines.append(f"- **Type:** {med['type']}")
        lines.append(f"- **Composition:** {med['composition']}")
        lines.append(f"- **Dosage:** {med['dosage']}")
        lines.append(f"- **Duration:** {med['duration']}")
        lines.append(f"- **Purpose:** {med['purpose']}")
        for warning in med_status.get("warnings", []):
            lines.append(f"- **Warning:** {warning}")
        # Build the order link using 1mg only
        med_name     = med['name'].replace("+", " ").split("(")[0].strip()
        encoded_name = urllib.parse.quote_plus(med_name)
        order_link = f"https://www.1mg.com/search/all?name={encoded_name}"
        lines.append(f"- [Click to order]({order_link})")
        lines.append("")
    return "\n".join(lines)


GEMINI_MEDICAL_SYSTEM_PROMPT = MEDICAL_REASONING_SYSTEM_PROMPT


# ── Response Validator Initialization ─────────────────────────────────────────
# Extract known diseases and medications for validation
_KNOWN_DISEASES = list(DISEASE_MEDICATIONS.keys())
_KNOWN_MEDICATIONS = []
for _disease_info in DISEASE_MEDICATIONS.values():
    if "medicines" in _disease_info:
        for _med in _disease_info["medicines"]:
            if "name" in _med:
                _KNOWN_MEDICATIONS.append(_med["name"].split()[0])  # First word (drug name)
                _KNOWN_MEDICATIONS.append(_med["name"])              # Full name

# Simple symptom map for validator (extracted from expanded map)
_VALIDATOR_SYMPTOM_MAP = {
    "diabetes": {"urination": 3, "thirst": 3, "fatigue": 2},
    "hypertension": {"chest pain": 3, "dizziness": 2, "headache": 2},
    "migraine": {"headache": 3, "nausea": 2, "light sensitivity": 3},
    "asthma": {"wheezing": 4, "shortness of breath": 3, "cough": 2},
    "pneumonia": {"fever": 3, "cough": 3, "chest pain": 3},
    "gerd": {"heartburn": 4, "regurgitation": 3},
    "anxiety": {"palpitations": 3, "restlessness": 2},
    "depression": {"persistent sadness": 4, "loss of interest": 4},
}

# Initialize the response validator
response_validator = ResponseValidator(
    known_diseases=_KNOWN_DISEASES,
    known_medications=list(set(_KNOWN_MEDICATIONS)),
    symptom_map=_VALIDATOR_SYMPTOM_MAP,
    medication_db=DISEASE_MEDICATIONS
)


def validate_and_process_response(response: str, context: dict = None) -> str:
    """
    Validate AI response for hallucinations and add appropriate warnings.
    Returns processed response with validation warnings if needed.
    """
    try:
        validation = response_validator.validate_response(response, context or {})
        return process_validated_response(response, validation)
    except Exception as e:
        # If validation fails, return original response with generic disclaimer
        logger.error(f"Response validation error: {e}")
        if "consult" not in response.lower() and "disclaimer" not in response.lower():
            response += (
                "\n\n---\n⚠️ **Disclaimer:** This is AI-generated health information. "
                "Always consult a qualified healthcare professional."
            )
        return response


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
    "brain bleed":          "neurologist",
    "brain bleeding":       "neurologist",
    "bleeding in brain":    "neurologist",
    "brain hemorrhage":     "neurologist",
    "brain haemorrhage":    "neurologist",
    "intracranial bleed":   "neurologist",
    "intracranial hemorrhage": "neurologist",
    "intracranial haemorrhage": "neurologist",
    "intracerebral hemorrhage": "neurologist",
    "intracerebral haemorrhage": "neurologist",
    "subarachnoid hemorrhage": "neurologist",
    "subarachnoid haemorrhage": "neurologist",
    "hemorrhagic stroke":   "neurologist",
    "haemorrhagic stroke":  "neurologist",
    "severe headache":      "neurologist",
    "worst headache":       "neurologist",
    "worst headache of my life": "neurologist",
    "paralysis":            "neurologist",
    "unable to move":       "neurologist",
    "slurred speech":       "neurologist",
    "face drooping":        "neurologist",
    "one sided weakness":   "neurologist",
    "seizure":              "neurologist",
    "breathing difficulty": "pulmonologist",
    "difficulty breathing": "pulmonologist",
    "shortness of breath":  "pulmonologist",
    "short breath":         "pulmonologist",
    "breathless":           "pulmonologist",
    "gasping":              "pulmonologist",
    "struggling to breathe": "pulmonologist",
    "not able to breathe":  "pulmonologist",
    "unable to breathe":    "pulmonologist",
    "can't breathe":        "pulmonologist",
    "cannot breathe":       "pulmonologist",
    "blue lips":            "pulmonologist",
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


def build_practo_url(specialty_slug: str, city: str = "") -> str:
    """Build a Google Maps doctor search URL without hard-coding a city."""
    specialty_query = urllib.parse.quote_plus(f"{specialty_slug.replace('-', ' ')} near me")
    return f"https://www.google.com/maps/search/{specialty_query}"


SPECIALTY_KEYWORDS: Dict[str, str] = {
    "diabetes": "endocrinologist",
    "hba1c": "endocrinologist",
    "glucose": "endocrinologist",
    "thyroid": "endocrinologist",
    "tsh": "endocrinologist",
    "hypertension": "cardiologist",
    "blood pressure": "cardiologist",
    "bp": "cardiologist",
    "cholesterol": "cardiologist",
    "heart": "cardiologist",
    "chest pain": "cardiologist",
    "migraine": "neurologist",
    "headache": "neurologist",
    "dizziness": "neurologist",
    "seizure": "neurologist",
    "anxiety": "psychiatrist",
    "palpitations": "psychiatrist",
    "anemia": "hematologist",
    "anaemia": "hematologist",
    "hemoglobin": "hematologist",
    "haemoglobin": "hematologist",
    "asthma": "pulmonologist",
    "wheezing": "pulmonologist",
    "shortness of breath": "pulmonologist",
    "breathing": "pulmonologist",
    "gastroenteritis": "gastroenterologist",
    "stomach pain": "gastroenterologist",
    "vomiting": "gastroenterologist",
    "diarrhea": "gastroenterologist",
    "diarrhoea": "gastroenterologist",
    "urinary tract infection": "urologist",
    "uti": "urologist",
    "burning urination": "urologist",
    "frequent urination": "urologist",
    "kidney": "urologist",
    "urine": "urologist",
    "skin": "dermatologist",
    "rash": "dermatologist",
    "itching": "dermatologist",
    "eczema": "dermatologist",
    "psoriasis": "dermatologist",
    "acne": "dermatologist",
    "muscle strain": "orthopedist",
    "joint pain": "orthopedist",
    "leg pain": "orthopedist",
    "back pain": "orthopedist",
}


NEGATION_TERMS = (
    "no ",
    "not ",
    "without ",
    "don't have ",
    "do not have ",
    "doesn't have ",
    "does not have ",
    "dont have ",
)


def keyword_is_present(text: str, keyword: str) -> bool:
    start = 0
    while True:
        idx = text.find(keyword, start)
        if idx == -1:
            return False

        context = text[max(0, idx - 40):idx]
        for conj in (" but ", ", but ", " and ", ", and ", " however ", ", however "):
            parts = context.rsplit(conj, 1)
            if len(parts) > 1:
                context = parts[-1]
                break

        if not any(neg in context for neg in NEGATION_TERMS):
            return True

        start = idx + len(keyword)


def infer_specialty_slug(message: str, prediction_list: Optional[List[tuple]] = None) -> str:
    """Pick the most relevant specialist based on predicted disease or explicit medical terms."""
    for disease, _confidence in prediction_list or []:
        slug = DISEASE_SPECIALTY.get(str(disease).lower().strip())
        if slug:
            return slug

    text = (message or "").lower()
    for keyword, slug in SPECIALTY_KEYWORDS.items():
        if keyword_is_present(text, keyword):
            return slug

    return "general-physician"


REPORT_TRIGGER_PHRASES = [
    "my report",
    "this report",
    "the report",
    "lab report",
    "blood report",
    "scan report",
    "test report",
    "uploaded report",
    "uploaded file",
    "my file",
    "my lab",
    "my blood test",
    "my test result",
    "my results",
    "report findings",
    "lab findings",
    "explain my report",
    "explain my lab",
    "explain these results",
    "summarize my report",
    "summarise my report",
    "compare with previous report",
    "compare with my previous report",
    "compare my reports",
    "previous report",
]


def should_use_uploaded_report(message: str, has_report: bool) -> bool:
    """Only route to report analysis when the user explicitly refers to an uploaded report/results."""
    if not has_report:
        return False

    text = (message or "").lower().strip()
    if not text:
        return False

    if any(phrase in text for phrase in REPORT_TRIGGER_PHRASES):
        return True

    # Catch common direct questions with "report/results/file" phrasing.
    question_starts = ("what does", "explain", "summarize", "summarise", "compare", "tell me about")
    report_nouns = ("report", "results", "result", "file", "lab", "blood test", "scan", "document")
    return text.startswith(question_starts) and any(noun in text for noun in report_nouns)

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
            if not response or not hasattr(response, 'text') or response.text is None:
                raise RuntimeError("Gemini returned no text in generate_content")
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
        # ── Existing Conditions ──
        "diabetes":                {"urination": 3, "thirst": 3, "fatigue": 2, "blurred vision": 2, "weight loss": 2, "hunger": 2},
        "hypertension":            {"chest pain": 3, "dizziness": 2, "headache": 2, "shortness of breath": 2, "nosebleed": 1},
        "migraine":                {"light sensitivity": 3, "nausea": 2, "headache": 3, "throbbing": 2, "vomiting": 1},
        "muscle strain":           {"leg pain": 3, "muscle pain": 3, "swelling": 2, "stiffness": 2, "limited range": 1},
        "viral infection":         {"fever": 3, "fatigue": 2, "body pain": 2, "sore throat": 1, "headache": 1},
        "common cold":             {"fever": 2, "cough": 2, "runny nose": 3, "sneezing": 2, "sore throat": 2},
        "flu":                     {"fever": 3, "body pain": 3, "fatigue": 2, "chills": 2, "sore throat": 1},
        "covid":                   {"fever": 2, "dry cough": 3, "loss of smell": 4, "loss of taste": 4, "fatigue": 2},
        "malaria":                 {"fever": 3, "chills": 3, "sweating": 2, "headache": 2, "nausea": 1},
        "anxiety":                 {"palpitations": 3, "sweating": 2, "shortness of breath": 2, "dizziness": 2, "restlessness": 2},
        "anemia":                  {"fatigue": 3, "dizziness": 2, "pale skin": 3, "weakness": 2, "cold hands": 1},
        "gastroenteritis":         {"nausea": 3, "vomiting": 3, "diarrhea": 3, "stomach pain": 2, "fever": 1},
        "asthma":                  {"wheezing": 4, "shortness of breath": 3, "cough": 2, "chest tightness": 2},
        "urinary tract infection": {"burning urination": 4, "frequent urination": 3, "lower back pain": 2, "cloudy urine": 2},
        "dengue fever":            {"fever": 3, "rash": 3, "joint pain": 3, "headache": 2, "eye pain": 2},

        # ── Cardiovascular ──
        "coronary artery disease": {"chest pain": 4, "shortness of breath": 3, "fatigue": 2, "arm pain": 3, "jaw pain": 2, "sweating": 2},
        "heart failure":           {"shortness of breath": 4, "swelling": 3, "fatigue": 3, "rapid heartbeat": 2, "cough": 1, "weight gain": 2},
        "arrhythmia":              {"palpitations": 4, "fluttering": 3, "racing heart": 3, "slow heartbeat": 2, "dizziness": 2, "fainting": 2},
        "deep vein thrombosis":    {"leg swelling": 4, "leg pain": 3, "warmth": 2, "redness": 2, "visible veins": 1},
        "stroke":                  {"numbness": 4, "weakness": 4, "confusion": 3, "speech difficulty": 4, "vision problems": 3, "severe headache": 3},

        # ── Respiratory ──
        "pneumonia":               {"fever": 3, "cough": 3, "phlegm": 3, "chest pain": 3, "shortness of breath": 3, "fatigue": 2},
        "copd":                    {"chronic cough": 4, "mucus": 3, "shortness of breath": 4, "wheezing": 3, "chest tightness": 2},
        "bronchitis":              {"cough": 4, "mucus": 3, "fatigue": 2, "shortness of breath": 2, "chest discomfort": 2},
        "tuberculosis":            {"persistent cough": 4, "coughing blood": 4, "weight loss": 3, "night sweats": 3, "fever": 2},
        "pulmonary embolism":      {"sudden shortness of breath": 4, "chest pain": 4, "cough": 2, "rapid heartbeat": 3, "dizziness": 2},

        # ── Gastrointestinal ──
        "gerd":                    {"heartburn": 4, "regurgitation": 3, "difficulty swallowing": 2, "chest pain": 2, "chronic cough": 1},
        "peptic ulcer":            {"burning stomach pain": 4, "bloating": 2, "heartburn": 2, "nausea": 2, "fullness": 2},
        "irritable bowel syndrome":{"abdominal cramping": 4, "bloating": 3, "gas": 2, "diarrhea": 3, "constipation": 3},
        "appendicitis":            {"lower right abdominal pain": 4, "nausea": 3, "vomiting": 2, "loss of appetite": 2, "fever": 2},
        "gallstones":              {"upper right abdominal pain": 4, "back pain": 2, "shoulder pain": 2, "nausea": 2, "vomiting": 1},
        "hepatitis b":             {"fatigue": 3, "jaundice": 4, "abdominal pain": 2, "nausea": 2, "dark urine": 3},
        "hepatitis c":             {"fatigue": 3, "jaundice": 4, "abdominal pain": 2, "joint pain": 2, "dark urine": 3},
        "hepatitis a":             {"fatigue": 3, "jaundice": 4, "nausea": 2, "loss of appetite": 2, "fever": 2},

        # ── Endocrine ──
        "hypothyroidism":          {"fatigue": 4, "weight gain": 3, "cold intolerance": 3, "constipation": 2, "dry skin": 2, "depression": 2},
        "hyperthyroidism":         {"weight loss": 3, "rapid heartbeat": 3, "anxiety": 3, "tremors": 3, "sweating": 2, "heat intolerance": 2},
        "pcos":                    {"irregular periods": 4, "excess hair": 3, "acne": 2, "weight gain": 2, "hair thinning": 2},
        "cushing syndrome":        {"weight gain": 3, "round face": 3, "stretch marks": 3, "thin skin": 2, "fatigue": 2, "high blood pressure": 2},

        # ── Musculoskeletal ──
        "rheumatoid arthritis":    {"joint pain": 4, "joint swelling": 4, "stiffness": 3, "fatigue": 2, "fever": 1},
        "osteoarthritis":          {"joint pain": 4, "stiffness": 3, "tenderness": 2, "loss of flexibility": 2, "grating": 1},
        "osteoporosis":            {"back pain": 3, "loss of height": 3, "stooped posture": 2, "fracture": 4},
        "gout":                    {"intense joint pain": 4, "swelling": 3, "redness": 3, "warmth": 2, "limited motion": 2},
        "fibromyalgia":            {"widespread pain": 4, "fatigue": 4, "cognitive difficulties": 3, "sleep problems": 3, "headaches": 2},
        "sciatica":                {"lower back pain": 4, "leg pain": 4, "numbness": 3, "tingling": 3, "muscle weakness": 2},

        # ── Neurological ──
        "epilepsy":                {"seizures": 4, "convulsions": 4, "staring": 3, "confusion": 3, "loss of consciousness": 3},
        "parkinson disease":       {"tremor": 4, "slowed movement": 4, "rigid muscles": 3, "balance problems": 3, "speech changes": 2},
        "alzheimer disease":       {"memory loss": 4, "confusion": 4, "difficulty planning": 3, "language problems": 3, "mood changes": 2},
        "bell palsy":              {"facial weakness": 4, "facial droop": 4, "drooling": 2, "eye dryness": 2, "headache": 1},
        "vertigo":                 {"spinning": 4, "dizziness": 4, "loss of balance": 3, "nausea": 2, "vomiting": 2},

        # ── Infectious ──
        "typhoid fever":           {"sustained fever": 4, "headache": 3, "weakness": 3, "stomach pain": 2, "constipation": 2},
        "chickenpox":              {"itchy rash": 4, "blisters": 4, "fever": 3, "fatigue": 2, "loss of appetite": 1},
        "measles":                 {"high fever": 3, "cough": 2, "runny nose": 2, "red eyes": 3, "rash": 4},
        "hiv aids":                {"weight loss": 3, "fever": 3, "night sweats": 3, "chronic diarrhea": 3, "swollen lymph nodes": 3},

        # ── Mental Health ──
        "depression":              {"persistent sadness": 4, "loss of interest": 4, "sleep changes": 3, "fatigue": 3, "worthlessness": 3},
        "bipolar disorder":        {"elevated mood": 4, "decreased sleep": 3, "racing thoughts": 3, "depression": 3, "risky behavior": 2},
        "ptsd":                    {"flashbacks": 4, "nightmares": 4, "avoidance": 3, "negative mood": 3, "hyperarousal": 3},
        "ocd":                     {"intrusive thoughts": 4, "compulsive behaviors": 4, "repetitive": 3, "anxiety": 3, "need for order": 2},
        "panic disorder":          {"panic attack": 4, "heart palpitations": 4, "sweating": 3, "trembling": 3, "fear of dying": 3},

        # ── Dermatological ──
        "eczema":                  {"dry skin": 4, "itching": 4, "red patches": 3, "raised bumps": 2, "cracked skin": 2},
        "psoriasis":               {"red patches": 4, "silvery scales": 4, "dry skin": 3, "itching": 2, "thickened nails": 2},
        "cellulitis":              {"spreading redness": 4, "swelling": 3, "tenderness": 3, "warmth": 2, "fever": 2},
        "shingles":                {"painful rash": 4, "blisters": 4, "burning": 3, "tingling": 3, "fever": 2},

        # ── Urological ──
        "kidney stones":           {"severe side pain": 4, "back pain": 3, "pain in waves": 3, "painful urination": 3, "blood in urine": 3},
        "bph":                     {"frequent urination": 4, "urgency": 3, "difficulty starting": 3, "weak stream": 3, "dribbling": 2},
        "interstitial cystitis":   {"bladder pressure": 4, "pelvic pain": 4, "persistent urge": 3, "frequent urination": 3, "pain during intercourse": 2},
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
        *EMERGENCY_SPECIALTY.keys(),
        # Additional clinical red flags that should still trigger emergency routing
        "respiratory distress",
        "stopped breathing",
        "not breathing",
        "can barely breathe",
        "barely breathing",
        "sudden weakness on one side",
        "weakness on one side",
        "sudden confusion",
        "loss of consciousness",
        "vomiting blood",
        "coughing blood",
        "head injury with bleeding",
        "severe head injury",
    ]
    text_lower = user_text.lower()
    return any(keyword_is_present(text_lower, kw) for kw in emergency_keywords)


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
        p.mkdir(parents=True, exist_ok=True)
        return p

    def _session_file(self, username: str, sid: str) -> Path:
        return self._user_path(username) / f"{sid}.json"

    def _read_json(self, path: Path) -> dict:
        with open(path) as f:
            return json.load(f)

    def _write_json(self, path: Path, data: dict):
        with open(path, "w") as f:
            json.dump(data, f, indent=2)

    def create_session(self, username: str) -> str:
        existing = self.list_sessions(username)
        if len(existing) >= MAX_SESSIONS:
            oldest = sorted(existing, key=lambda x: x.get("created", ""))
            for old in oldest[:len(existing) - MAX_SESSIONS + 1]:
                self.delete_session(username, old["id"])
        sid  = str(uuid.uuid4())
        data = {"id": sid, "user": username, "created_at": datetime.now().isoformat(),
                "name": "New Chat", "messages": [], "diagnostic_state": None}
        self._write_json(self._session_file(username, sid), data)
        return sid

    def set_session_name(self, username: str, sid: str, name: str):
        fpath = self._session_file(username, sid)
        if not fpath.exists(): return
        data = self._read_json(fpath)
        data["name"] = name[:40]
        self._write_json(fpath, data)

    def get_session(self, username: str, sid: str) -> Optional[dict]:
        fpath = self._session_file(username, sid)
        if not fpath.exists():
            return None
        data = self._read_json(fpath)
        if "diagnostic_state" not in data:
            data["diagnostic_state"] = None
        return data

    def save_session(self, username: str, sid: str, data: dict):
        self._write_json(self._session_file(username, sid), data)

    def add_message(self, username: str, sid: str, role: str, content: str, meta: dict = None):
        fpath = self._session_file(username, sid)
        if not fpath.exists(): return
        data = self._read_json(fpath)
        msg  = {"role": role, "content": content, "time": datetime.now().isoformat()}
        if meta:
            msg["meta"] = meta
        data["messages"].append(msg)
        # FIX 16: Cap stored messages at 50 to prevent unbounded file growth
        if len(data["messages"]) > 50:
            data["messages"] = data["messages"][-50:]
        self._write_json(fpath, data)

    def get_history(self, username: str, sid: str) -> List[dict]:
        fpath = self._session_file(username, sid)
        if not fpath.exists(): return []
        data = self._read_json(fpath)
        msgs = data.get("messages", [])[-20:]
        return [
            {
                "role": m["role"],
                "content": m["content"],
                "tools_used": (m.get("meta") or {}).get("tools_used", []),
                "sources": (m.get("meta") or {}).get("sources", []),
            }
            for m in msgs
        ]

    def get_message_context(self, username: str, sid: str, exclude_tools: Optional[List[str]] = None) -> List[dict]:
        session = self.get_session(username, sid)
        if not session:
            return []

        messages = session.get("messages", [])[-20:]
        exclude_set = {tool.lower() for tool in (exclude_tools or [])}
        excluded_indexes = set()

        if exclude_set:
            for index, message in enumerate(messages):
                tools_used = {
                    str(tool).lower()
                    for tool in (message.get("meta") or {}).get("tools_used", [])
                }
                if tools_used & exclude_set:
                    excluded_indexes.add(index)
                    if index > 0 and messages[index - 1].get("role") == "user":
                        excluded_indexes.add(index - 1)

        return [
            {"role": item["role"], "content": item["content"]}
            for index, item in enumerate(messages)
            if index not in excluded_indexes
        ]

    def list_sessions(self, username: str) -> List[dict]:
        sessions = []
        for f in self._user_path(username).glob("*.json"):
            if f.name in ("profile.json", "last_report.json", "lab_history.json"): continue
            try:
                d = self._read_json(f)
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
        try:
            fpath = self._user_path(username) / "profile.json"
            self._write_json(fpath, profile_data)
        except OSError:
            logger.warning("Skipping profile save for %s; memory store unavailable", username)

    def load_profile(self, username: str) -> Optional[dict]:
        try:
            fpath = self.base_path / username / "profile.json"
            if not fpath.exists():
                return None
            return self._read_json(fpath)
        except OSError:
            logger.warning("Skipping profile load for %s; memory store unavailable", username)
            return None

    def delete_session(self, username: str, sid: str) -> bool:
        fpath = self._session_file(username, sid)
        if fpath.exists():
            fpath.unlink()
            return True
        return False

    def save_report(self, username: str, report: dict):
        fpath = self._user_path(username) / "last_report.json"
        self._write_json(fpath, report)

    def load_report(self, username: str):
        fpath = self._user_path(username) / "last_report.json"
        if not fpath.exists(): return None
        return self._read_json(fpath)

    def save_lab_record(self, username: str, record: dict):
        fpath = self._user_path(username) / "lab_history.json"
        history = []
        if fpath.exists():
            history = self._read_json(fpath)
            if not isinstance(history, list):
                history = []
        history.append(record)
        history = history[-30:]
        self._write_json(fpath, history)

    def load_lab_history(self, username: str) -> List[dict]:
        fpath = self._user_path(username) / "lab_history.json"
        if not fpath.exists():
            return []
        history = self._read_json(fpath)
        return history if isinstance(history, list) else []

    def get_diagnostic_state(self, username: str, sid: str) -> Optional[dict]:
        session = self.get_session(username, sid)
        if not session:
            return None
        return session.get("diagnostic_state")

    def set_diagnostic_state(self, username: str, sid: str, state: Optional[dict]):
        session = self.get_session(username, sid)
        if not session:
            return
        session["diagnostic_state"] = state
        self.save_session(username, sid, session)


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
        if not response or not hasattr(response, 'text') or response.text is None:
            raise RuntimeError("Gemini returned no text in conversation response")
        return response.text

    def _parse_tool(self, text: str) -> Optional[dict]:
        if not text or not isinstance(text, str):
            return None
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
    existing_profile = memory.load_profile(req.username)
    payload = req.model_dump() if hasattr(req, "model_dump") else req.dict()
    memory.save_profile(req.username, profile_from_login(payload, existing=existing_profile))
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
    existing_profile = memory.load_profile(username)
    memory.save_profile(username, normalize_profile(req.profile, existing=existing_profile))
    return {"status": "Profile saved"}


@app.get("/api/profile")
async def get_profile(username: str = Depends(get_current_user)):
    return {"profile": normalize_profile(memory.load_profile(username))}


@app.get("/api/lab-history")
async def get_lab_history(username: str = Depends(get_current_user)):
    history = memory.load_lab_history(username)
    latest = history[-1] if history else None
    previous = history[-2] if len(history) > 1 else None
    trends = compare_lab_records(latest.get("metrics", []), previous.get("metrics", [])) if latest and previous else []
    return {
        "history": history,
        "latest": latest,
        "trends": trends,
    }


def build_sources(*items: Dict[str, Any]) -> List[Dict[str, Any]]:
    sources = []
    for item in items:
        if not item:
            continue
        sources.append(item)
    return sources


def build_handoff_summary(username: str, sid: str) -> str:
    session = memory.get_session(username, sid)
    if not session:
        raise HTTPException(404, "Session not found")

    profile = normalize_profile(memory.load_profile(username))
    messages = session.get("messages", [])
    user_messages = [m["content"] for m in messages if m.get("role") == "user"]
    assistant_messages = [m for m in messages if m.get("role") == "assistant"]
    latest_assistant = assistant_messages[-1] if assistant_messages else None
    latest_meta = (latest_assistant or {}).get("meta", {})
    latest_tools = latest_meta.get("tools_used", [])
    latest_sources = latest_meta.get("sources", [])

    lab_history = memory.load_lab_history(username)
    latest_lab = lab_history[-1] if lab_history else None
    previous_lab = lab_history[-2] if len(lab_history) > 1 else None
    trend_lines = compare_lab_records(latest_lab.get("metrics", []), previous_lab.get("metrics", [])) if latest_lab and previous_lab else []

    recent_user_summary = user_messages[-3:] if user_messages else []
    latest_response = latest_assistant["content"] if latest_assistant else "No assistant summary available yet."

    lines = [
        "Patient Summary",
        f"User: {username}",
        f"Age: {profile.get('age', 'Unknown')}",
        f"Gender: {profile.get('gender', 'unknown')}",
        f"Known Conditions: {', '.join(profile.get('known_conditions', [])) or 'None recorded'}",
        f"Allergies: {', '.join(profile.get('allergies', [])) or 'None recorded'}",
        f"Current Medications: {', '.join(profile.get('current_medications', [])) or 'None recorded'}",
        f"Pregnancy Status: {profile.get('pregnancy_status', 'unknown')}",
        "",
        "Recent User Inputs:",
    ]
    if recent_user_summary:
        for item in recent_user_summary:
            lines.append(f"- {item}")
    else:
        lines.append("- No recent user messages recorded.")

    lines.extend([
        "",
        "Latest Assistant Assessment:",
        latest_response,
        "",
        f"Pipeline Sources: {', '.join(source.get('label', source.get('type', 'Unknown')) for source in latest_sources) or 'Not recorded'}",
        f"Tools Used: {', '.join(latest_tools) or 'None'}",
    ])

    safety_alerts = latest_meta.get("safety_alerts", [])
    if safety_alerts:
        lines.append("")
        lines.append("Medication Safety Alerts:")
        for alert in safety_alerts:
            lines.append(f"- {alert}")

    if latest_lab:
        lines.append("")
        lines.append(f"Latest Lab Snapshot ({latest_lab.get('filename', 'uploaded report')}):")
        lines.append(latest_lab.get("snapshot", "No structured metrics extracted."))
    if trend_lines:
        lines.append("")
        lines.append("Lab Trend Summary:")
        for trend in trend_lines:
            lines.append(f"- {trend}")

    report = memory.load_report(username)
    if report:
        lines.append("")
        lines.append(f"Last Uploaded Report: {report.get('filename', 'Unknown file')}")

    return "\n".join(lines)


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
    return {
        "session_id": sid,
        "history": h,
        "pending_followup": memory.get_diagnostic_state(username, sid),
    }


@app.get("/api/handoff-summary")
async def get_handoff_summary(session_id: str = Query(...), username: str = Depends(get_current_user)):
    summary = build_handoff_summary(username, session_id)
    return {"session_id": session_id, "summary": summary}

@app.delete("/api/sessions/{sid}")
async def del_session(sid: str, username: str = Depends(get_current_user)):
    if not memory.delete_session(username, sid):
        raise HTTPException(404, "Session not found")
    return {"status": "deleted"}


# ── Chat ──────────────────────────────────────────────────────────────────────
@app.post("/api/chat", response_model=ChatResponse)
async def chat(req: ChatRequest):
    users = await load_users()
    username = next((u for u, d in users.items() if d.get("token") == req.token), None)
    if not username:
        raise HTTPException(401, "Unauthorized — please login")

    if not req.message or not req.message.strip():
        raise HTTPException(400, "Message cannot be empty")
    req.message = req.message.strip()
    if len(req.message) > 2000:
        raise HTTPException(400, "Message too long (max 2000 characters).")

    active_model = req.model if req.model else MODEL_NAME

    sid = req.session_id or memory.create_session(username)
    history = memory.get_message_context(username, sid, exclude_tools=["Uploaded Report"]) or []
    if not history:
        memory.set_session_name(username, sid, req.message)

    if check_emergency(req.message):
        emg_lower   = req.message.lower()
        emg_slug    = next((slug for kw, slug in EMERGENCY_SPECIALTY.items() if keyword_is_present(emg_lower, kw)), "general-physician")
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
        sources = build_sources(
            {"type": "emergency_detector", "label": "Emergency Detector"},
            {"type": "profile", "label": "Structured Profile"},
        )
        memory.set_diagnostic_state(username, sid, None)
        memory.add_message(username, sid, "user", req.message)
        memory.add_message(username, sid, "assistant", emergency_response,
                           {"tools_used": ["Emergency Detector"], "sources": sources})
        return ChatResponse(response=emergency_response, session_id=sid,
                            tools_used=["Emergency Detector"],
                            show_hospital_finder=True,
                            practo_url=emg_practo_url,
                            timestamp=datetime.now().isoformat(),
                            sources=sources)

    pending_followup = memory.get_diagnostic_state(username, sid)
    if pending_followup and pending_followup.get("pending_followup"):
        updated_state = merge_followup_answers(pending_followup, req.message)
        memory.add_message(username, sid, "user", req.message)
        if needs_more_followup(updated_state):
            followup_response = build_followup_prompt(updated_state)
            sources = build_sources(
                {"type": "followup_triage", "label": "Follow-up Triage"},
                {"type": "profile", "label": "Structured Profile"},
            )
            memory.set_diagnostic_state(username, sid, updated_state)
            memory.add_message(
                username,
                sid,
                "assistant",
                followup_response,
                {
                    "tools_used": ["Follow-up Triage"],
                    "followup_questions": updated_state.get("questions", []),
                    "sources": sources,
                },
            )
            return ChatResponse(
                response=followup_response,
                session_id=sid,
                tools_used=["Follow-up Triage"],
                timestamp=datetime.now().isoformat(),
                needs_followup=True,
                followup_questions=updated_state.get("questions", []),
                sources=sources,
            )
        req.message = combine_messages_for_assessment(updated_state, req.message)
        history = memory.get_message_context(username, sid, exclude_tools=["Uploaded Report"]) or []
        memory.set_diagnostic_state(username, sid, None)

    profile = normalize_profile(memory.load_profile(username))
    age = profile.get("age", 30)
    gender = profile.get("gender", "unknown")
    known_conditions = profile.get("known_conditions", [])

    user_report = USER_REPORTS.get(username) or memory.load_report(username)
    if should_use_uploaded_report(req.message, bool(user_report)):
        lab_history = memory.load_lab_history(username)
        latest_record = lab_history[-1] if lab_history else None
        previous_record = lab_history[-2] if len(lab_history) > 1 else None
        trend_context = "No prior report available for trend comparison."
        metrics_context = ""
        if latest_record:
            metrics_context = summarize_metric_snapshot(latest_record.get("metrics", []))
        if latest_record and previous_record:
            trend_lines = compare_lab_records(latest_record.get("metrics", []), previous_record.get("metrics", []))
            if trend_lines:
                trend_context = "\n".join(trend_lines)
        report_specialty = infer_specialty_slug(
            f"{req.message}\n{user_report.get('text', '')}\n{metrics_context}\n{trend_context}"
        )
        prompt = (
            f"You are a medical AI assistant. The user has uploaded a medical report.\n\n"
            f"Uploaded Report ({user_report['filename']}):\n{user_report['text']}\n\n"
            f"Structured Metrics Snapshot:\n{metrics_context or 'No structured metrics extracted.'}\n\n"
            f"Trend Comparison With Previous Report:\n{trend_context}\n\n"
            f"User question: {req.message}\n\n"
            "Answer specifically based on the uploaded report. Reference actual values where relevant. "
            "If the user asks about change over time, explicitly discuss the trend comparison."
        )
        try:
            raw_text = await gemini_generate(active_model, prompt)
            text = validate_and_process_response(raw_text, {"symptoms": req.message})
            result = {"response": text, "tools_used": ["Uploaded Report"]}
        except Exception as e:
            logger.error(f"Gemini report error: {e}")
            raise HTTPException(500, "AI service temporarily unavailable. Please try again.")
        sources = build_sources(
            {"type": "uploaded_report", "label": "Uploaded Report"},
            {"type": "lab_history", "label": "Lab Trend Engine"} if latest_record else None,
            {"type": "profile", "label": "Structured Profile"},
        )
        memory.add_message(username, sid, "user", req.message)
        memory.add_message(username, sid, "assistant", result["response"],
                           {"tools_used": result["tools_used"], "sources": sources})
        return ChatResponse(response=result["response"], session_id=sid,
                            tools_used=result["tools_used"],
                            practo_url=build_practo_url(report_specialty),
                            timestamp=datetime.now().isoformat(),
                            sources=sources)

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

    followup_state = maybe_create_followup_state(req.message, prediction_list, raw_match_count, profile)
    if followup_state:
        followup_response = build_followup_prompt(followup_state)
        sources = build_sources(
            {"type": "followup_triage", "label": "Follow-up Triage"},
            {"type": "symptom_predictor", "label": "Symptom Predictor"},
            {"type": "profile", "label": "Structured Profile"},
        )
        memory.set_diagnostic_state(username, sid, followup_state)
        memory.add_message(username, sid, "user", req.message)
        memory.add_message(
            username,
            sid,
            "assistant",
            followup_response,
            {
                "tools_used": ["Follow-up Triage"],
                "followup_questions": followup_state.get("questions", []),
                "sources": sources,
            },
        )
        return ChatResponse(
            response=followup_response,
            session_id=sid,
            tools_used=["Follow-up Triage"],
            timestamp=datetime.now().isoformat(),
            needs_followup=True,
            followup_questions=followup_state.get("questions", []),
            sources=sources,
        )

    # Flood guard: if 5 diseases all scored simultaneously, likely a manipulated/
    # symptom-stuffed input — skip predictor and fall through to Gemini directly
    if raw_match_count <= 4 and prediction_list:
        top_disease, top_confidence = prediction_list[0]
        medication_data = DISEASE_MEDICATIONS.get(top_disease.lower(), {}).get("medicines", [])
        safety_report = assess_medication_safety(medication_data, profile) if medication_data else {
            "warnings": [],
            "safer_alternatives": [],
            "medication_status": {},
            "blocked_medicines": [],
            "safe": True,
        }
        safety_alerts = build_safety_summary(safety_report)

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
- Gender: {gender.title() if gender else 'Unknown'}
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

        raw_explanation = await agent.process(explanation_prompt, history, model=active_model)
        validated_text = validate_and_process_response(raw_explanation["response"], {"symptoms": req.message})
        explanation = {"response": validated_text, "tools_used": raw_explanation.get("tools_used", [])}
        conditions_text = "\n".join(
            [f"{i+1}. {d.title()} ({c}%)" for i, (d, c) in enumerate(prediction_list)]
        )
        med_card = format_medication_card(top_disease, safety_report=safety_report)

        final_response = (
            f"🩺 Possible Conditions:\n{conditions_text}\n\n"
            f"📊 Risk Level: {risk_level}\n\n"
            f"{explanation['response']}"
            f"{med_card}"
        )
        sources = build_sources(
            {"type": "symptom_predictor", "label": "Symptom Predictor"},
            {"type": "profile", "label": "Structured Profile"},
            {"type": "medication_safety", "label": "Medication Safety"} if safety_alerts else None,
        )
        memory.add_message(username, sid, "user", req.message)
        memory.add_message(username, sid, "assistant", final_response,
                           {
                               "tools_used": ["Symptom Predictor", "Medication Safety"] if safety_alerts else ["Symptom Predictor"],
                               "sources": sources,
                               "safety_alerts": safety_alerts,
                           })
        symptom_slug    = DISEASE_SPECIALTY.get(top_disease.lower(), "general-physician")
        symptom_display = SPECIALTY_DISPLAY.get(symptom_slug, "General Physician")
        return ChatResponse(response=final_response, session_id=sid,
                            tools_used=["Symptom Predictor", "Medication Safety"] if safety_alerts else ["Symptom Predictor"],
                            practo_url=build_practo_url(symptom_slug),
                            timestamp=datetime.now().isoformat(),
                            safety_alerts=safety_alerts,
                            sources=sources)

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
            raw_kg_response = await gemini_generate(active_model, kg_prompt)
            kg_response = validate_and_process_response(raw_kg_response, {"symptoms": req.message})
            result      = {"response": kg_response, "tools_used": ["Medical KG"]}
        except Exception as e:
            logger.error(f"Gemini KG error: {e}")
            result = None

        if result:
            sources = build_sources(
                {"type": "knowledge_graph", "label": "Medical KG"},
                {"type": "profile", "label": "Structured Profile"},
            )
            memory.add_message(username, sid, "user", req.message)
            memory.add_message(username, sid, "assistant", result["response"],
                               {"tools_used": result["tools_used"], "sources": sources})
            return ChatResponse(response=result["response"], session_id=sid,
                                tools_used=result["tools_used"],
                                practo_url=build_practo_url(infer_specialty_slug(req.message, prediction_list)),
                                timestamp=datetime.now().isoformat(),
                                sources=sources)

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
            raw_text = await gemini_generate(active_model, prompt)
            text = validate_and_process_response(raw_text, {"symptoms": req.message})
            result = {"response": text, "tools_used": ["RAG"]}
            sources = build_sources(
                {"type": "rag", "label": "Medical Knowledge Base"},
                {"type": "profile", "label": "Structured Profile"},
            )
        else:
            agent_result = await agent.process(req.message, history, model=active_model)
            validated_response = validate_and_process_response(agent_result["response"], {"symptoms": req.message})
            result = {"response": validated_response, "tools_used": agent_result.get("tools_used", [])}
            sources = build_sources(
                {"type": "gemini_fallback", "label": "Direct Gemini Reasoning"},
                {"type": "profile", "label": "Structured Profile"},
            )
    except Exception as e:
        logger.error(f"Gemini chat error: {e}")
        raise HTTPException(500, "AI service temporarily unavailable. Please try again.")

    memory.add_message(username, sid, "user", req.message)
    memory.add_message(username, sid, "assistant", result["response"],
                       {"tools_used": result.get("tools_used", []), "sources": sources})
    return ChatResponse(
        response=result["response"],
        session_id=sid,
        tools_used=result.get("tools_used", []),
        practo_url=build_practo_url(infer_specialty_slug(req.message, prediction_list)),
        timestamp=datetime.now().isoformat(),
        sources=sources
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
        metrics = extract_lab_metrics(extracted_text)
        findings = analyze_lab_values(extracted_text)
        trend_summary = "No prior report available for comparison."
        metric_snapshot = summarize_metric_snapshot(metrics)

        if upload_username:
            history = memory.load_lab_history(upload_username)
            previous_record = history[-1] if history else None
            if previous_record:
                trend_lines = compare_lab_records(metrics, previous_record.get("metrics", []))
                if trend_lines:
                    trend_summary = "\n".join(trend_lines)
                else:
                    trend_summary = "Comparable values were found, but no significant change was detected."
            report_obj = {
                "text": report_text,
                "filename": file.filename,
                "metrics": metrics,
                "findings": findings,
                "trend_summary": trend_summary,
            }
            USER_REPORTS[upload_username] = report_obj
            memory.save_report(upload_username, report_obj)
            memory.save_lab_record(upload_username, {
                "filename": file.filename,
                "timestamp": datetime.now().isoformat(),
                "metrics": metrics,
                "findings": findings,
                "snapshot": metric_snapshot,
            })

        findings_text = "\n".join(findings) if findings else "No abnormal lab values detected."

        medical_prompt = f"""You are an expert medical AI trained to interpret laboratory reports.

Medical Report:
{report_text}

Structured Metrics:
{metric_snapshot}

Detected Lab Findings:
{findings_text}

Trend Comparison:
{trend_summary}

Instructions:
1. Explain what this report contains.
2. Highlight abnormal or concerning values.
3. Explain what those values mean in simple language.
4. Compare the latest values to the previous report if trend data exists.
5. Suggest possible health risks.
6. Provide general health precautions.

Respond strictly in this format:

🧾 Report Overview:
(short explanation)

⚠️ Abnormal Values Detected:
(list abnormal values, or "None detected" if all normal)

🩺 Possible Health Risks:
(list possible risks)

📈 Trend Summary:
(compare against prior report if available, otherwise say no prior comparison is available)

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

        return {
            "status": "success",
            "analysis": analysis,
            "lab_findings": findings,
            "summary": analysis,
            "trend_summary": trend_summary,
            "metrics": metrics,
        }

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
    Returns the 1mg order link for the given medicine name and strip count.
    """
    query = urllib.parse.quote_plus(medicine)
    return {
        "medicine": medicine,
        "strips": strips,
        "links": {
            "1mg": {
                "name": "1mg",
                "url": f"https://www.1mg.com/search/all?name={query}",
                "label": "Click to order",
            },
        },
    }


# ── New Feature Endpoints (v4) ─────────────────────────────────────────────────

# ────────────────────── MEDICATION INTERACTIONS ───────────────────────────────
@app.post("/api/check-drug-interactions")
async def check_drug_interactions_endpoint(token: str = Query(...), medications: List[str] = Query(...)):
    """Check for drug-drug interactions in a medication list"""
    username = await get_current_user(token)
    
    # Log audit event
    security_manager.log_audit_event(username, "CHECK_DRUG_INTERACTIONS", "medications", details={"meds_count": len(medications)})
    
    interactions = check_drug_interactions(medications)
    return {
        "username": username,
        "medications": medications,
        "interactions": interactions,
        "timestamp": datetime.now().isoformat(),
    }


# ────────────────────── HEALTH ANALYTICS & TRENDS ────────────────────────────
@app.get("/api/health-dashboard")
async def get_health_dashboard(token: str = Query(...)):
    """Get user's health dashboard with metrics and analytics"""
    username = await get_current_user(token)
    
    security_manager.log_audit_event(username, "VIEW_HEALTH_DASHBOARD", "dashboard")
    
    dashboard = get_dashboard_summary(username)
    return {
        "username": username,
        "dashboard": dashboard,
    }


@app.post("/api/health-metric")
async def add_health_metric_endpoint(token: str = Query(...), metric: str = Query(...), 
                                     value: float = Query(...), unit: str = Query(...),
                                     status: str = Query("normal")):
    """Add a health metric to user's analytics"""
    username = await get_current_user(token)
    
    add_health_metric(username, metric, value, unit, status)
    security_manager.log_audit_event(username, "ADD_HEALTH_METRIC", metric, details={"value": value})
    
    return {
        "status": "success",
        "metric": metric,
        "value": value,
        "unit": unit,
        "timestamp": datetime.now().isoformat(),
    }


@app.get("/api/health-trends")
async def get_health_trends_endpoint(token: str = Query(...), metric: str = Query(None), days: int = Query(30)):
    """Get health trends for a specific metric or all metrics"""
    username = await get_current_user(token)
    
    security_manager.log_audit_event(username, "VIEW_HEALTH_TRENDS", "trends")
    
    trends = get_health_trends(username, metric, days)
    return {
        "username": username,
        "trends": trends,
    }


@app.get("/api/health-report")
async def get_health_report_endpoint(token: str = Query(...)):
    """Generate a health report for the user"""
    username = await get_current_user(token)
    
    security_manager.log_audit_event(username, "GENERATE_HEALTH_REPORT", "report")
    
    report = generate_health_report(username)
    return {
        "username": username,
        "report": report,
    }


# ────────────────────── EXPERT CONSULTATION ───────────────────────────────────
@app.get("/api/experts")
async def get_available_experts(token: str = Query(...), category: str = Query("all")):
    """Get list of available experts"""
    username = await get_current_user(token)
    
    security_manager.log_audit_event(username, "VIEW_EXPERTS", "expert_list")
    
    experts = expert_manager.get_available_experts(category)
    return {
        "username": username,
        "experts": experts,
        "count": len(experts),
    }


@app.post("/api/request-consultation")
async def request_consultation(req: ExpertConsultation):
    """Request a consultation with an expert"""
    username = await get_current_user(req.token)
    
    consultation = expert_manager.request_consultation(
        username,
        "dr_001",  # Default to first available doctor
        req.question,
        req.category,
        req.preferred_language or "en"
    )

    security_manager.log_audit_event(username, "REQUEST_CONSULTATION", "consultation", details={"category": req.category})
    
    return {
        "status": "success",
        "consultation": consultation,
    }


@app.get("/api/my-consultations")
async def get_my_consultations(token: str = Query(...)):
    """Get all consultations for the user"""
    username = await get_current_user(token)
    
    consultations = expert_manager.get_consultations(username)
    
    return {
        "username": username,
        "consultations": consultations,
        "count": len(consultations),
    }


@app.post("/api/close-consultation")
async def close_consultation_endpoint(token: str = Query(...), consultation_id: str = Query(...),
                                     rating: int = Query(None), feedback: str = Query(None)):
    """Close a consultation and provide feedback"""
    username = await get_current_user(token)
    
    success = expert_manager.close_consultation(username, consultation_id, rating, feedback)
    
    security_manager.log_audit_event(username, "CLOSE_CONSULTATION", "consultation", details={"rating": rating})
    
    return {
        "status": "success" if success else "failed",
        "consultation_id": consultation_id,
    }


@app.post("/api/schedule-appointment")
async def schedule_appointment(token: str = Query(...), expert_id: str = Query(...),
                              date: str = Query(...), time: str = Query(...), reason: str = Query(...)):
    """Schedule an appointment with an expert"""
    username = await get_current_user(token)
    
    appointment = expert_manager.schedule_appointment(username, expert_id, date, time, reason)

    security_manager.log_audit_event(username, "SCHEDULE_APPOINTMENT", "appointment", details={"date": date, "time": time})
    
    return {
        "status": "success",
        "appointment": appointment,
    }


# ────────────────────── MULTI-LANGUAGE SUPPORT ────────────────────────────────
@app.get("/api/ui-strings")
async def get_ui_strings(language: str = Query("en")):
    """Get UI strings for the specified language"""
    strings = language_manager.get_ui_strings(language)
    
    return {
        "language": language,
        "strings": strings,
    }


@app.get("/api/supported-languages")
async def get_supported_languages():
    """Get list of supported languages"""
    return {
        "languages": language_manager.get_supported_languages(),
    }


# ────────────────────── DATA PRIVACY & SECURITY ───────────────────────────────
@app.get("/api/export-data")
async def export_user_data(token: str = Query(...)):
    """Export all user data for GDPR compliance"""
    username = await get_current_user(token)
    
    exported_data = security_manager.export_user_data(username)
    
    security_manager.log_audit_event(username, "EXPORT_DATA", "gdpr_export")
    
    return {
        "status": "success",
        "data_export": exported_data,
    }


@app.post("/api/delete-account")
async def delete_user_account(token: str = Query(...)):
    """Delete user account and all associated data"""
    username = await get_current_user(token)
    
    # Log before deletion
    security_manager.log_audit_event("admin", "DELETE_ACCOUNT", username, details={"user_deleted": username})
    
    # Delete user data
    success = security_manager.delete_user_data(username)
    
    if success:
        # Invalidate token
        users = await load_users()
        if username in users:
            del users[username]
            await save_users(users)
    
    return {
        "status": "success" if success else "failed",
        "message": "Your account and all associated data have been deleted." if success else "Deletion failed.",
    }


@app.get("/api/audit-log")
async def get_audit_log(token: str = Query(...)):
    """Get user's audit log for security monitoring"""
    username = await get_current_user(token)
    
    audit_log = security_manager.get_audit_log(username)
    
    return {
        "username": username,
        "audit_log": audit_log,
    }


# ────────────────────── ENHANCED PROFILE ──────────────────────────────────────
@app.post("/api/update-profile-extended")
async def update_profile_extended(token: str = Query(...), profile_data: Dict[str, Any] = None):
    """Update extended profile with new fields"""
    username = await get_current_user(token)
    
    if profile_data is None:
        profile_data = {}
    
    # Load existing profile
    profile_file = Path("memory") / username / "profile.json"
    profile = {}
    if profile_file.exists():
        with open(profile_file, "r") as f:
            profile = json.load(f)
    
    # Update with new data
    profile.update(profile_data)
    
    # Normalize and save
    profile = normalize_profile(profile_data, profile)
    
    profile_file.parent.mkdir(parents=True, exist_ok=True)
    with open(profile_file, "w") as f:
        json.dump(profile, f, indent=2)
    
    security_manager.log_audit_event(username, "UPDATE_EXTENDED_PROFILE", "profile")
    
    return {
        "status": "success",
        "profile": profile,
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
