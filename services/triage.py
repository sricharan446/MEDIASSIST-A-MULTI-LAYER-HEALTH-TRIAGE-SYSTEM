import re
from typing import Any, Dict, List, Optional


SYMPTOM_KEYWORDS = {
    "fever": ["fever", "temperature", "chills"],
    "cough": ["cough", "coughing"],
    "headache": ["headache", "migraine"],
    "pain": ["pain", "ache", "soreness", "cramp"],
    "breathing": ["shortness of breath", "breathing", "wheezing"],
    "urination": ["urination", "urinate", "peeing", "thirsty"],
}

QUESTION_LIBRARY = {
    "duration": {
        "question": "How long have you had these symptoms?",
        "placeholder": "e.g. 2 days, since yesterday, 1 week",
    },
    "severity": {
        "question": "How severe are the symptoms right now?",
        "placeholder": "mild, moderate, or severe",
    },
    "temperature": {
        "question": "Do you know your temperature or whether the fever is low/high grade?",
        "placeholder": "e.g. 101 F, high fever, not measured",
    },
    "cough_type": {
        "question": "Is the cough dry or is there mucus/phlegm?",
        "placeholder": "dry / mucus / not sure",
    },
    "pain_location": {
        "question": "Where exactly is the pain located?",
        "placeholder": "e.g. head, throat, chest, stomach, lower back",
    },
    "breathing": {
        "question": "Are you also having shortness of breath, chest tightness, or wheezing?",
        "placeholder": "yes / no / occasionally",
    },
    "urination": {
        "question": "Are you also feeling unusually thirsty or urinating more often than usual?",
        "placeholder": "yes / no / not sure",
    },
}


def extract_symptom_facts(text: str) -> Dict[str, Any]:
    lower = text.lower()
    facts: Dict[str, Any] = {"symptoms": []}
    for name, keywords in SYMPTOM_KEYWORDS.items():
        if any(keyword in lower for keyword in keywords):
            facts["symptoms"].append(name)

    duration_match = re.search(r"\b(\d+\s*(?:hour|hours|day|days|week|weeks|month|months))\b", lower)
    if duration_match:
        facts["duration"] = duration_match.group(1)
    elif "since yesterday" in lower:
        facts["duration"] = "since yesterday"
    elif "today" in lower:
        facts["duration"] = "today"

    severity_match = re.search(r"\b(mild|moderate|severe)\b", lower)
    if severity_match:
        facts["severity"] = severity_match.group(1)

    temp_match = re.search(r"\b(\d{2,3}(?:\.\d+)?)\s*(?:°?\s*[fc])\b", lower)
    if temp_match:
        facts["temperature"] = temp_match.group(0)

    if "dry cough" in lower:
        facts["cough_type"] = "dry"
    elif "mucus" in lower or "phlegm" in lower or "wet cough" in lower:
        facts["cough_type"] = "mucus"

    pain_location = None
    for location in ("chest", "head", "throat", "stomach", "abdomen", "back", "lower back", "leg"):
        if location in lower:
            pain_location = location
            break
    if pain_location:
        facts["pain_location"] = pain_location

    if any(term in lower for term in ("shortness of breath", "wheezing", "chest tightness")):
        facts["breathing"] = "yes"

    if any(term in lower for term in ("frequent urination", "urinating more", "very thirsty", "excessive thirst")):
        facts["urination"] = "yes"

    return facts


def merge_followup_answers(state: Dict[str, Any], message: str) -> Dict[str, Any]:
    merged = dict(state or {})
    working = dict(merged.get("working_facts") or {})
    text = message.strip()

    for line in [part.strip() for part in text.splitlines() if part.strip()]:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        clean_key = key.strip().lower().replace(" ", "_")
        if clean_key in QUESTION_LIBRARY and value.strip():
            working[clean_key] = value.strip()

    merged["working_facts"] = working
    merged["answered_questions"] = [
        question["id"] for question in merged.get("questions", [])
        if working.get(question["id"])
    ]
    return merged


def _question_ids_for(message: str, prediction_list: List[Any], facts: Dict[str, Any]) -> List[str]:
    lower = message.lower()
    question_ids: List[str] = []

    if not facts.get("duration"):
        question_ids.append("duration")
    if not facts.get("severity"):
        question_ids.append("severity")
    if "fever" in facts.get("symptoms", []) and not facts.get("temperature"):
        question_ids.append("temperature")
    if "cough" in facts.get("symptoms", []) and not facts.get("cough_type"):
        question_ids.append("cough_type")
    if "pain" in facts.get("symptoms", []) and not facts.get("pain_location"):
        question_ids.append("pain_location")

    top_disease = prediction_list[0][0].lower() if prediction_list else ""
    if top_disease in {"asthma", "flu", "covid", "common cold"} and "breathing" not in facts:
        question_ids.append("breathing")
    if top_disease == "diabetes" and "urination" not in facts and "diabetes" in lower:
        question_ids.append("urination")

    unique_ids = []
    for question_id in question_ids:
        if question_id not in unique_ids:
            unique_ids.append(question_id)
    return unique_ids[:3]


def maybe_create_followup_state(
    message: str,
    prediction_list: List[Any],
    raw_match_count: int,
    profile: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    if raw_match_count > 4:
        return None

    facts = extract_symptom_facts(message)
    if not facts.get("symptoms"):
        return None

    top_confidence = prediction_list[0][1] if prediction_list else 0
    second_confidence = prediction_list[1][1] if len(prediction_list) > 1 else 0
    close_competition = top_confidence and second_confidence and (top_confidence - second_confidence) < 10
    missing_core = not facts.get("duration") or not facts.get("severity")
    low_confidence = top_confidence and top_confidence < 75

    if not (missing_core or close_competition or low_confidence):
        return None

    question_ids = _question_ids_for(message, prediction_list, facts)
    if not question_ids:
        return None

    return {
        "pending_followup": True,
        "reason": "ambiguous_symptoms" if close_competition or low_confidence else "missing_clinical_detail",
        "original_message": message,
        "working_facts": facts,
        "questions": [
            {
                "id": question_id,
                "question": QUESTION_LIBRARY[question_id]["question"],
                "placeholder": QUESTION_LIBRARY[question_id]["placeholder"],
            }
            for question_id in question_ids
        ],
        "answered_questions": [],
        "profile_snapshot": profile or {},
    }


def needs_more_followup(state: Optional[Dict[str, Any]]) -> bool:
    if not state:
        return False
    working = state.get("working_facts") or {}
    for question in state.get("questions", []):
        if not working.get(question["id"]):
            return True
    return False


def build_followup_prompt(state: Dict[str, Any]) -> str:
    questions = state.get("questions", [])
    lines = [
        "I need a few more details before I finish the assessment.",
        "",
        "Please answer these follow-up questions:",
    ]
    for index, item in enumerate(questions, start=1):
        lines.append(f"{index}. {item['question']}")
    lines.append("")
    lines.append("Reply in the form `field: answer` for each item, or use the inline form below.")
    return "\n".join(lines)


def combine_messages_for_assessment(state: Dict[str, Any], latest_message: str) -> str:
    working = state.get("working_facts") or {}
    details = []
    for key in ("duration", "severity", "temperature", "cough_type", "pain_location", "breathing", "urination"):
        if working.get(key):
            details.append(f"{key.replace('_', ' ').title()}: {working[key]}")
    details_text = "\n".join(details)
    original = state.get("original_message", "").strip()
    return f"{original}\n\nFollow-up details:\n{details_text}\n\nLatest reply: {latest_message.strip()}".strip()
