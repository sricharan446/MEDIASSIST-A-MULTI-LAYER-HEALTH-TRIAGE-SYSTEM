import re
from typing import Any, Dict, List, Set


MEDICATION_METADATA = {
    "cetirizine": {"class": "antihistamine", "aliases": ["cetirizine"]},
    "paracetamol": {"class": "analgesic", "aliases": ["paracetamol", "acetaminophen"]},
    "oseltamivir": {"class": "antiviral", "aliases": ["oseltamivir", "tamiflu"]},
    "vitamin d3 + zinc": {"class": "supplement", "aliases": ["vitamin d3", "zinc", "vitamin d3 zinc"]},
    "metformin": {"class": "antidiabetic", "aliases": ["metformin"]},
    "amlodipine": {"class": "antihypertensive", "aliases": ["amlodipine"]},
    "sumatriptan": {"class": "triptan", "aliases": ["sumatriptan"]},
    "naproxen": {"class": "nsaid", "aliases": ["naproxen"]},
    "artemether + lumefantrine": {"class": "antimalarial", "aliases": ["artemether", "lumefantrine", "coartem"]},
    "ors": {"class": "rehydration", "aliases": ["ors", "oral rehydration salts"]},
    "diclofenac": {"class": "nsaid", "aliases": ["diclofenac", "volini"]},
    "escitalopram": {"class": "ssri", "aliases": ["escitalopram"]},
    "clonazepam": {"class": "benzodiazepine", "aliases": ["clonazepam"]},
    "ferrous sulphate": {"class": "iron", "aliases": ["ferrous sulphate", "iron"]},
    "methylcobalamin": {"class": "vitamin_b12", "aliases": ["methylcobalamin", "vitamin b12"]},
    "ondansetron": {"class": "antiemetic", "aliases": ["ondansetron"]},
    "racecadotril": {"class": "antidiarrheal", "aliases": ["racecadotril"]},
    "salbutamol": {"class": "bronchodilator", "aliases": ["salbutamol", "ventolin"]},
    "budesonide": {"class": "steroid", "aliases": ["budesonide"]},
    "nitrofurantoin": {"class": "antibiotic", "aliases": ["nitrofurantoin"]},
    "phenazopyridine": {"class": "urinary_analgesic", "aliases": ["phenazopyridine", "uristat"]},
}

NSAID_CLASS = {"nsaid"}
PREGNANCY_CAUTION_CLASSES = {"nsaid", "benzodiazepine", "triptan"}
BLOOD_THINNERS = {"warfarin", "apixaban", "rivaroxaban", "dabigatran", "heparin", "aspirin", "clopidogrel"}


def _normalize(text: str) -> str:
    text = (text or "").lower()
    text = re.sub(r"\([^)]*\)", " ", text)
    text = re.sub(r"[^a-z0-9+/\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _match_medication_key(text: str) -> str:
    normalized = _normalize(text)
    for key, meta in MEDICATION_METADATA.items():
        for alias in meta["aliases"]:
            if alias in normalized:
                return key
    return normalized.split(" ")[0] if normalized else ""


def _classes_for_med(text: str) -> Set[str]:
    key = _match_medication_key(text)
    meta = MEDICATION_METADATA.get(key, {})
    return {meta.get("class")} if meta.get("class") else set()


def _collect_profile_terms(profile: Dict[str, Any], key: str) -> List[str]:
    return [_normalize(item) for item in profile.get(key, []) if str(item).strip()]


def assess_medication_safety(medicines: List[Dict[str, Any]], profile: Dict[str, Any]) -> Dict[str, Any]:
    allergies = _collect_profile_terms(profile, "allergies")
    current_medications = _collect_profile_terms(profile, "current_medications")
    known_conditions = _collect_profile_terms(profile, "known_conditions") + _collect_profile_terms(profile, "past_history")
    gender = (profile.get("gender") or "unknown").lower()
    pregnancy_status = (profile.get("pregnancy_status") or "unknown").lower()
    if gender == "male":
        pregnancy_status = "not_applicable"
    elif gender in {"other", "prefer_not_to_say", "unknown"} and pregnancy_status == "pregnant":
        pregnancy_status = "unknown"

    warnings: List[str] = []
    blocked_medicines: List[str] = []
    safer_alternatives: List[str] = []
    medication_status: Dict[str, Dict[str, Any]] = {}

    current_med_keys = {_match_medication_key(item) for item in current_medications}
    current_med_classes = set()
    for item in current_medications:
        current_med_classes.update(_classes_for_med(item))

    has_hypertension = any(term in condition for condition in known_conditions for term in ("hypertension", "high blood pressure", "bp"))
    has_kidney_issue = any(term in condition for condition in known_conditions for term in ("kidney", "creatinine", "renal"))
    has_liver_issue = any(term in condition for condition in known_conditions for term in ("liver", "hepatitis", "fatty liver"))
    has_asthma = any("asthma" in condition for condition in known_conditions)
    has_diabetes = any("diabetes" in condition for condition in known_conditions)
    uses_blood_thinner = any(any(agent in med for agent in BLOOD_THINNERS) for med in current_medications)
    uses_bp_meds = any(med in current_med_keys for med in {"amlodipine"})

    for medicine in medicines:
        name = medicine.get("name", "")
        composition = medicine.get("composition", "")
        med_key = _match_medication_key(name + " " + composition)
        med_classes = _classes_for_med(name + " " + composition)
        item_warnings: List[str] = []
        blocked = False

        if any(allergy and (allergy in _normalize(name) or allergy in _normalize(composition) or allergy == med_key) for allergy in allergies):
            item_warnings.append(f"{name} conflicts with an allergy listed in your profile.")
            blocked = True

        if med_key and med_key in current_med_keys:
            item_warnings.append(f"{name} appears to duplicate a medication already listed in your profile.")

        if med_classes & current_med_classes and med_classes:
            item_warnings.append(f"{name} is in the same medication class as a medicine already listed in your profile.")

        if pregnancy_status == "pregnant" and med_classes & PREGNANCY_CAUTION_CLASSES:
            item_warnings.append(f"{name} needs pregnancy-specific medical review before use.")

        if med_classes & NSAID_CLASS:
            if has_hypertension:
                item_warnings.append(f"{name} may worsen blood pressure control.")
            if has_kidney_issue:
                item_warnings.append(f"{name} can be risky with kidney-related concerns.")
            if has_asthma:
                item_warnings.append(f"{name} can trigger symptoms in some people with asthma.")
            if uses_blood_thinner:
                item_warnings.append(f"{name} can increase bleeding risk with blood-thinning medicines.")
            if uses_bp_meds:
                item_warnings.append(f"{name} can reduce the effectiveness of some blood pressure treatments.")
            if not blocked and "Paracetamol" not in safer_alternatives:
                safer_alternatives.append("Paracetamol")

        if med_key == "paracetamol" and has_liver_issue:
            item_warnings.append(f"{name} should be used cautiously with liver-related concerns.")

        if med_key == "clonazepam" and pregnancy_status == "pregnant":
            blocked = True

        if med_key == "budesonide" and has_diabetes:
            item_warnings.append(f"{name} may require extra glucose monitoring in diabetes.")

        if med_key == "nitrofurantoin" and has_kidney_issue:
            item_warnings.append(f"{name} may need dose review if kidney function is reduced.")

        if blocked:
            blocked_medicines.append(name)

        if item_warnings:
            warnings.extend(item_warnings)

        medication_status[name] = {
            "blocked": blocked,
            "warnings": item_warnings,
            "status": "blocked" if blocked else ("caution" if item_warnings else "ok"),
        }

    deduped_warnings = []
    seen = set()
    for warning in warnings:
        if warning in seen:
            continue
        seen.add(warning)
        deduped_warnings.append(warning)

    return {
        "safe": not any(item["blocked"] for item in medication_status.values()),
        "warnings": deduped_warnings,
        "blocked_medicines": blocked_medicines,
        "safer_alternatives": safer_alternatives,
        "medication_status": medication_status,
    }


def build_safety_summary(report: Dict[str, Any]) -> List[str]:
    summary = list(report.get("warnings", []))
    if report.get("safer_alternatives"):
        summary.append("Consider discussing safer alternatives such as: " + ", ".join(report["safer_alternatives"]) + ".")
    return summary


# ── Drug-Drug Interaction Database ────────────────────────────────────────────
DRUG_INTERACTIONS: Dict[str, Dict[str, Dict[str, Any]]] = {
    # NSAIDs interactions
    "naproxen": {
        "metformin": {"severity": "moderate", "type": "caution", "description": "NSAIDs may impair renal function and increase metformin levels"},
        "warfarin": {"severity": "severe", "type": "contraindicated", "description": "Increased bleeding risk — concurrent use requires careful monitoring"},
        "amlodipine": {"severity": "moderate", "type": "caution", "description": "NSAIDs may reduce antihypertensive effect"},
        "methotrexate": {"severity": "severe", "type": "caution", "description": "NSAIDs can increase methotrexate toxicity"},
    },
    "diclofenac": {
        "metformin": {"severity": "moderate", "type": "caution", "description": "NSAIDs may impair renal function"},
        "amlodipine": {"severity": "moderate", "type": "caution", "description": "NSAIDs may reduce antihypertensive effect"},
        "warfarin": {"severity": "severe", "type": "contraindicated", "description": "Increased bleeding risk"},
    },
    # SSRIs interactions
    "escitalopram": {
        "clonazepam": {"severity": "moderate", "type": "caution", "description": "Combined CNS depression — use cautiously"},
        "warfarin": {"severity": "moderate", "type": "caution", "description": "May increase bleeding risk — monitor"},
    },
    # Benzodiazepine interactions
    "clonazepam": {
        "metformin": {"severity": "mild", "type": "monitor", "description": "No direct interaction, but monitor for CNS effects"},
        "escitalopram": {"severity": "moderate", "type": "caution", "description": "Increased CNS depression"},
        "alcohol": {"severity": "severe", "type": "contraindicated", "description": "Severe CNS depression — avoid concurrent use"},
    },
    # Blood thinner interactions
    "warfarin": {
        "aspirin": {"severity": "severe", "type": "caution", "description": "Significantly increased bleeding risk"},
        "naproxen": {"severity": "severe", "type": "contraindicated", "description": "Increased bleeding risk"},
        "escitalopram": {"severity": "moderate", "type": "caution", "description": "May increase bleeding risk"},
    },
    "clopidogrel": {
        "omeprazole": {"severity": "moderate", "type": "caution", "description": "May reduce antiplatelet effect of clopidogrel"},
    },
}


def check_drug_interactions(medications: List[str]) -> Dict[str, Any]:
    """
    Check for drug-drug interactions among provided medications.
    
    Returns:
        Dict with 'interactions', 'warnings', and 'risk_level'
    """
    interactions = []
    warnings = []
    risk_level = "none"
    
    med_keys = []
    for med in medications:
        key = _match_medication_key(med).lower()
        if key:
            med_keys.append(key)
    
    # Check all pairs
    for i, med1_key in enumerate(med_keys):
        for med2_key in med_keys[i + 1:]:
            # Check if interaction exists
            interaction = None
            if med1_key in DRUG_INTERACTIONS and med2_key in DRUG_INTERACTIONS[med1_key]:
                interaction = DRUG_INTERACTIONS[med1_key][med2_key]
            elif med2_key in DRUG_INTERACTIONS and med1_key in DRUG_INTERACTIONS[med2_key]:
                interaction = DRUG_INTERACTIONS[med2_key][med1_key]
            
            if interaction:
                med1_display = medications[med_keys.index(med1_key)] if med1_key in med_keys else med1_key
                med2_display = medications[med_keys.index(med2_key)] if med2_key in med_keys else med2_key
                
                interactions.append({
                    "medication1": med1_display,
                    "medication2": med2_display,
                    "severity": interaction["severity"],
                    "type": interaction["type"],
                    "description": interaction["description"],
                    "recommendation": f"Discuss with your doctor about using {med1_display} and {med2_display} together"
                })
                
                warnings.append(f"[{interaction['severity'].upper()}] {med1_key} + {med2_key}: {interaction['description']}")
                
                # Update risk level
                if interaction["severity"] == "severe":
                    risk_level = "severe"
                elif interaction["severity"] == "moderate" and risk_level != "severe":
                    risk_level = "moderate"
                elif interaction["severity"] == "mild" and risk_level == "none":
                    risk_level = "mild"
    
    return {
        "interactions": interactions,
        "warnings": warnings,
        "risk_level": risk_level,
        "total_interactions": len(interactions),
    }
