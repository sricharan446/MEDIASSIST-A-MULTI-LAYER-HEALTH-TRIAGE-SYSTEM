from typing import Any, Dict, List, Optional


DEFAULT_PROFILE = {
    "age": 30,
    "known_conditions": [],
    "allergies": [],
    "current_medications": [],
    "pregnancy_status": "unknown",
    "smoking_status": "unknown",
    "alcohol_use": "unknown",
    "past_history": [],
    # New fields for enhanced profile
    "family_history": [],
    "lifestyle_activities": [],
    "dietary_preferences": [],
    "emergency_contact": None,
    "email": None,
    "phone": None,
    "language": "en",
}

ENUM_FIELDS = {
    "pregnancy_status": {"pregnant", "not_pregnant", "unknown", "not_applicable"},
    "smoking_status": {"never", "former", "current", "unknown"},
    "alcohol_use": {"never", "occasional", "regular", "unknown"},
    "language": {"en", "es", "fr", "de", "hi", "ta", "te", "kn"},
}


def _clean_list(value: Optional[Any]) -> List[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = value
    else:
        return []
    cleaned = []
    seen = set()
    for item in parts:
        text = str(item).strip()
        if not text:
            continue
        key = text.lower()
        if key in seen:
            continue
        seen.add(key)
        cleaned.append(text)
    return cleaned


def normalize_profile(profile_data: Optional[Dict[str, Any]], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    profile = dict(DEFAULT_PROFILE)
    if existing:
        profile.update(existing)
    if profile_data:
        profile.update(profile_data)

    age = profile.get("age", DEFAULT_PROFILE["age"])
    try:
        age = int(age)
    except (TypeError, ValueError):
        age = DEFAULT_PROFILE["age"]
    if age < 0 or age > 120:
        age = DEFAULT_PROFILE["age"]
    profile["age"] = age

    for key in ("known_conditions", "allergies", "current_medications", "past_history", "family_history", "lifestyle_activities", "dietary_preferences"):
        profile[key] = _clean_list(profile.get(key))

    for key, allowed in ENUM_FIELDS.items():
        value = str(profile.get(key, DEFAULT_PROFILE[key]) or DEFAULT_PROFILE[key]).strip().lower()
        profile[key] = value if value in allowed else DEFAULT_PROFILE[key]

    # Validate contact fields
    email = profile.get("email", "")
    phone = profile.get("phone", "")
    if email and not isinstance(email, str):
        profile["email"] = None
    if phone and not isinstance(phone, str):
        profile["phone"] = None

    return profile


def profile_from_login(payload: Dict[str, Any], existing: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    return normalize_profile(payload, existing=existing)
