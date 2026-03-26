"""
Response Validation & Hallucination Detection for MediAssist

This module validates AI-generated medical responses against known facts,
detects potentially harmful advice, and ensures response quality.
"""

import re
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field


@dataclass
class ValidationResult:
    """Result of response validation."""
    is_valid: bool = True
    confidence: float = 1.0
    warnings: List[str] = field(default_factory=list)
    corrections: List[str] = field(default_factory=list)
    flagged_claims: List[str] = field(default_factory=list)
    dangerous_advice: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return {
            "is_valid": self.is_valid,
            "confidence": self.confidence,
            "warnings": self.warnings,
            "corrections": self.corrections,
            "flagged_claims": self.flagged_claims,
            "dangerous_advice": self.dangerous_advice,
        }


class ResponseValidator:
    """
    Validates AI responses for medical accuracy and safety.

    Performs:
    - Disease name verification against known database
    - Medication verification
    - Symptom-disease claim verification
    - Dangerous advice detection
    - Disclaimer enforcement
    """

    # Patterns for dangerous medical advice
    DANGEROUS_PATTERNS = [
        (r"stop\s+taking\s+(?:your\s+)?(?:prescribed\s+)?medication", "Advising to stop prescribed medication without doctor consultation"),
        (r"no\s+need\s+to\s+(?:see|visit|consult)\s+(?:a\s+)?doctor", "Discouraging necessary medical consultation"),
        (r"(?:guaranteed|sure|certain)\s+(?:to\s+)?cure", "Making false cure guarantees"),
        (r"100\s*%\s+(?:effective|safe|works)", "Overstating treatment efficacy"),
        (r"don'?t\s+(?:need|require)\s+(?:any\s+)?(?:medical\s+)?treatment", "Dismissing need for treatment"),
        (r"(?:ignore|dismiss)\s+(?:your\s+)?symptoms?", "Advising to ignore symptoms"),
        (r"self[- ]?medicate\s+with", "Encouraging self-medication"),
        (r"(?:double|triple)\s+(?:your\s+)?(?:the\s+)?dose", "Suggesting dangerous dosage changes"),
        (r"mix(?:ing)?\s+(?:it\s+)?with\s+alcohol", "Suggesting mixing medication with alcohol"),
        (r"(?:this|it)\s+will\s+(?:definitely|certainly)\s+(?:cure|heal|fix)", "Making definitive cure claims"),
    ]

    # Patterns for extracting disease mentions
    DISEASE_EXTRACTION_PATTERNS = [
        r"(?:diagnosed\s+with|suffering\s+from)\s+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)",
        r"(?:condition|disease|disorder|syndrome)(?:\s+called)?\s+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)",
        r"(?:likely|possibly|probably)\s+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)",
        r"(?:indicates?|suggests?)\s+([A-Z][a-z]+(?:\s+[A-Z]?[a-z]+)*)",
    ]

    # Patterns for extracting medication mentions
    MEDICATION_EXTRACTION_PATTERNS = [
        r"🔹\s+([A-Za-z]+(?:\s+[A-Za-z0-9]+)*)",  # From medication cards
        r"(?:take|prescribe|recommend)\s+([A-Z][a-z]+(?:\s+[0-9]+\s*mg)?)",
        r"([A-Z][a-z]+(?:acin|mycin|mab|nib|pril|olol|sartan|statin|prazole))",  # Common drug suffixes
    ]

    # Disclaimer patterns
    DISCLAIMER_PATTERNS = [
        r"consult\s+(?:a\s+)?(?:doctor|physician|healthcare)",
        r"not\s+(?:a\s+)?(?:substitute|replacement)\s+for\s+(?:medical|professional)",
        r"seek\s+(?:medical\s+)?(?:professional|advice)",
        r"(?:medical\s+)?disclaimer",
        r"AI[- ](?:generated|assisted)",
        r"informational\s+purposes?\s+only",
    ]

    def __init__(
        self,
        known_diseases: List[str],
        known_medications: List[str],
        symptom_map: Dict[str, Dict[str, int]],
        medication_db: Optional[Dict] = None,
    ):
        """
        Initialize validator with known medical facts.

        Args:
            known_diseases: List of known disease names
            known_medications: List of known medication names
            symptom_map: Dict mapping diseases to their symptoms
            medication_db: Optional medication database for cross-reference
        """
        # Normalize to lowercase for case-insensitive matching
        self.known_diseases = {d.lower().strip() for d in known_diseases}
        self.known_medications = {m.lower().strip() for m in known_medications}
        self.symptom_map = {k.lower(): {s.lower(): v for s, v in syms.items()}
                           for k, syms in symptom_map.items()}
        self.medication_db = medication_db or {}

        # Build reverse symptom lookup
        self.symptom_to_diseases: Dict[str, Set[str]] = {}
        for disease, symptoms in self.symptom_map.items():
            for symptom in symptoms:
                if symptom not in self.symptom_to_diseases:
                    self.symptom_to_diseases[symptom] = set()
                self.symptom_to_diseases[symptom].add(disease)

    @staticmethod
    def _keyword_is_present(text: str, keyword: str) -> bool:
        negation_terms = (
            "no ",
            "not ",
            "without ",
            "don't have ",
            "do not have ",
            "doesn't have ",
            "does not have ",
            "dont have ",
        )
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

            if not any(neg in context for neg in negation_terms):
                return True

            start = idx + len(keyword)

    def validate_response(self, response: str, context: Optional[Dict] = None) -> ValidationResult:
        """
        Validate an AI response for hallucinations and safety issues.

        Args:
            response: The AI-generated response text
            context: Optional context dict with user query, patient info, etc.

        Returns:
            ValidationResult with confidence score and any issues found
        """
        result = ValidationResult()
        context = context or {}

        # Check 1: Verify mentioned diseases exist in knowledge base
        self._check_diseases(response, result)

        # Check 2: Verify medications exist and are appropriate
        self._check_medications(response, result)

        # Check 3: Detect dangerous advice patterns
        self._check_dangerous_advice(response, result)

        # Check 4: Ensure disclaimer is present
        self._check_disclaimer(response, result)

        # Check 5: Verify symptom-disease claims (if context provided)
        if context.get("symptoms"):
            self._check_symptom_disease_claims(response, context["symptoms"], result)

        # Final validity check
        if result.confidence < 0.6 or len(result.flagged_claims) > 2 or result.dangerous_advice:
            result.is_valid = False

        return result

    def _check_diseases(self, response: str, result: ValidationResult) -> None:
        """Check if mentioned diseases exist in our knowledge base."""
        mentioned_diseases = self._extract_diseases(response)

        for disease in mentioned_diseases:
            disease_lower = disease.lower().strip()
            # Check exact match or partial match
            if not self._disease_exists(disease_lower):
                # Only flag if it looks like a specific disease name
                if len(disease) > 3 and not disease_lower in ["the", "this", "that", "with"]:
                    result.flagged_claims.append(f"Unverified condition: '{disease}'")
                    result.confidence -= 0.08
                    result.warnings.append(
                        f"The condition '{disease}' is not in our verified database. "
                        "Information may need verification."
                    )

    def _check_medications(self, response: str, result: ValidationResult) -> None:
        """Check if mentioned medications are known and appropriate."""
        mentioned_meds = self._extract_medications(response)

        for med in mentioned_meds:
            med_lower = med.lower().strip()
            if not self._medication_exists(med_lower):
                # Only flag if it looks like a medication name
                if len(med) > 3:
                    result.flagged_claims.append(f"Unverified medication: '{med}'")
                    result.confidence -= 0.1
                    result.warnings.append(
                        f"The medication '{med}' is not in our verified database. "
                        "Please verify with a pharmacist or doctor."
                    )

    def _check_dangerous_advice(self, response: str, result: ValidationResult) -> None:
        """Detect potentially harmful medical advice."""
        response_lower = response.lower()

        for pattern, description in self.DANGEROUS_PATTERNS:
            if re.search(pattern, response_lower, re.IGNORECASE):
                result.dangerous_advice.append(description)
                result.confidence -= 0.25
                result.is_valid = False

    def _check_disclaimer(self, response: str, result: ValidationResult) -> None:
        """Ensure response includes appropriate medical disclaimer."""
        response_lower = response.lower()
        has_disclaimer = any(
            re.search(pattern, response_lower, re.IGNORECASE)
            for pattern in self.DISCLAIMER_PATTERNS
        )

        if not has_disclaimer:
            result.corrections.append("Missing medical disclaimer")
            result.confidence -= 0.05

    def _check_symptom_disease_claims(
        self,
        response: str,
        reported_symptoms: str,
        result: ValidationResult
    ) -> None:
        """Verify that symptom-disease correlations mentioned are valid."""
        response_lower = response.lower()
        symptoms_lower = reported_symptoms.lower()

        # Extract symptoms mentioned by user
        user_symptoms = set()
        for symptom in self.symptom_to_diseases:
            if self._keyword_is_present(symptoms_lower, symptom):
                user_symptoms.add(symptom)

        # For each disease mentioned, check if symptoms support it
        mentioned_diseases = self._extract_diseases(response)
        for disease in mentioned_diseases:
            disease_lower = disease.lower()
            if disease_lower in self.symptom_map:
                disease_symptoms = set(self.symptom_map[disease_lower].keys())
                matching = user_symptoms.intersection(disease_symptoms)

                if not matching and user_symptoms:
                    result.warnings.append(
                        f"'{disease}' mentioned but reported symptoms don't strongly match. "
                        "Consider seeking professional evaluation."
                    )
                    result.confidence -= 0.05

    def _extract_diseases(self, text: str) -> List[str]:
        """Extract disease names mentioned in response."""
        diseases = []
        for pattern in self.DISEASE_EXTRACTION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            diseases.extend(matches)

        # Also check for known diseases mentioned directly
        text_lower = text.lower()
        for disease in self.known_diseases:
            if disease in text_lower:
                diseases.append(disease)

        cleaned = []
        seen = set()
        for disease in diseases:
            candidate = str(disease).strip().lower()
            if candidate not in self.known_diseases:
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            cleaned.append(candidate)

        return cleaned

    def _extract_medications(self, text: str) -> List[str]:
        """Extract medication names from response."""
        medications = []
        for pattern in self.MEDICATION_EXTRACTION_PATTERNS:
            matches = re.findall(pattern, text, re.IGNORECASE)
            medications.extend(matches)

        # Also check for known medications mentioned directly
        text_lower = text.lower()
        for med in self.known_medications:
            if med in text_lower:
                medications.append(med)

        return list(set(medications))

    def _disease_exists(self, disease: str) -> bool:
        """Check if disease exists in knowledge base."""
        if disease in self.known_diseases:
            return True
        # Fuzzy match - check if any known disease contains this term
        return any(disease in known or known in disease
                   for known in self.known_diseases)

    def _medication_exists(self, med: str) -> bool:
        """Check if medication exists in knowledge base."""
        if med in self.known_medications:
            return True
        # Fuzzy match
        return any(med in known or known in med
                   for known in self.known_medications)


def process_validated_response(
    response: str,
    validation: ValidationResult,
    add_disclaimer: bool = True
) -> str:
    """
    Process response based on validation confidence level.

    - HIGH (>0.8): Return as-is
    - MEDIUM (0.6-0.8): Add uncertainty markers
    - LOW (<0.6): Add strong caveats

    Args:
        response: Original AI response
        validation: ValidationResult from validator
        add_disclaimer: Whether to append disclaimer if missing

    Returns:
        Processed response with appropriate modifications
    """
    if validation.confidence >= 0.8 and validation.is_valid:
        # High confidence - return with minimal changes
        if "Missing medical disclaimer" in validation.corrections and add_disclaimer:
            response = _append_disclaimer(response)
        return response

    elif validation.confidence >= 0.6:
        # Medium confidence - add uncertainty markers
        response = _add_uncertainty_notice(response, validation)
        if add_disclaimer:
            response = _append_disclaimer(response)
        return response

    else:
        # Low confidence - add strong caveats
        response = _add_low_confidence_warning(response, validation)
        return response


def _add_uncertainty_notice(response: str, validation: ValidationResult) -> str:
    """Add uncertainty notice for medium-confidence responses."""
    notice = "\n\n---\n⚠️ **Note:** "
    if validation.warnings:
        notice += "Some information in this response could not be fully verified against our medical database. "
    notice += "Please consider consulting a healthcare professional for confirmation."

    # Insert before the last disclaimer if present, or at end
    if "Disclaimer" in response:
        parts = response.rsplit("Disclaimer", 1)
        return parts[0] + notice + "\n\n**Disclaimer" + parts[1]
    return response + notice


def _add_low_confidence_warning(response: str, validation: ValidationResult) -> str:
    """Add strong warning for low-confidence responses."""
    warning_parts = [
        "\n\n---",
        "## ⚠️ Important Notice",
        "",
        "**This response has been flagged for review.** Some claims could not be verified:",
        ""
    ]

    if validation.flagged_claims:
        for claim in validation.flagged_claims[:3]:
            warning_parts.append(f"- {claim}")

    if validation.dangerous_advice:
        warning_parts.append("\n**Safety concerns detected:**")
        for advice in validation.dangerous_advice:
            warning_parts.append(f"- ⛔ {advice}")

    warning_parts.extend([
        "",
        "**Please consult a qualified healthcare professional** before acting on this information.",
        "",
        "---",
        "⚠️ **Medical Disclaimer:** This is AI-generated content for informational purposes only. "
        "It is NOT a substitute for professional medical advice, diagnosis, or treatment."
    ])

    return response + "\n".join(warning_parts)


def _append_disclaimer(response: str) -> str:
    """Append standard medical disclaimer if not present."""
    disclaimer_check = ["disclaimer", "consult a doctor", "healthcare professional"]
    response_lower = response.lower()

    if not any(d in response_lower for d in disclaimer_check):
        response += (
            "\n\n---\n⚠️ **Medical Disclaimer:** This is AI-generated health information "
            "for educational purposes only. It is NOT a substitute for professional medical "
            "advice, diagnosis, or treatment. Always consult a qualified healthcare provider "
            "for medical concerns."
        )
    return response


# =============================================================================
# FACTORY FUNCTION
# =============================================================================

def create_validator(
    symptom_map: Dict,
    medication_db: Dict,
    additional_diseases: Optional[List[str]] = None,
    additional_medications: Optional[List[str]] = None
) -> ResponseValidator:
    """
    Factory function to create a ResponseValidator with proper initialization.

    Args:
        symptom_map: SYMPTOM_MAP from app.py
        medication_db: DISEASE_MEDICATIONS from app.py
        additional_diseases: Extra disease names to include
        additional_medications: Extra medication names to include

    Returns:
        Configured ResponseValidator instance
    """
    # Extract disease names from symptom map
    diseases = list(symptom_map.keys())
    if additional_diseases:
        diseases.extend(additional_diseases)

    # Extract medication names from medication database
    medications = []
    for disease_info in medication_db.values():
        if "medicines" in disease_info:
            for med in disease_info["medicines"]:
                if "name" in med:
                    # Extract base medication name (before strength/dosage)
                    med_name = med["name"].split()[0]
                    medications.append(med_name)
                    medications.append(med["name"])  # Also add full name

    if additional_medications:
        medications.extend(additional_medications)

    return ResponseValidator(
        known_diseases=diseases,
        known_medications=medications,
        symptom_map=symptom_map,
        medication_db=medication_db
    )
