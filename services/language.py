"""
Multi-Language Support Module
Provides language translations and localization
"""

from typing import Dict, Any, Optional


# Translation dictionary for UI strings
TRANSLATIONS = {
    "en": {
        "welcome": "Welcome to MediAssist",
        "chat_placeholder": "Ask me about your symptoms...",
        "upload_report": "Upload Lab Report",
        "medication_reminder": "Medication Reminder",
        "health_dashboard": "Health Dashboard",
        "emergency_alert": "Emergency Alert",
        "consult_expert": "Consult an Expert",
        "voice_input": "Voice Input",
        "logout": "Logout",
        "profile_settings": "Profile Settings",
        "health_trends": "Health Trends",
        "notifications": "Notifications",
    },
    "es": {
        "welcome": "Bienvenido a MediAssist",
        "chat_placeholder": "Pregúntame sobre tus síntomas...",
        "upload_report": "Cargar Informe de Laboratorio",
        "medication_reminder": "Recordatorio de Medicamento",
        "health_dashboard": "Panel de Salud",
        "emergency_alert": "Alerta de Emergencia",
        "consult_expert": "Consultar a un Experto",
        "voice_input": "Entrada de Voz",
        "logout": "Cerrar Sesión",
        "profile_settings": "Configuración de Perfil",
        "health_trends": "Tendencias de Salud",
        "notifications": "Notificaciones",
    },
    "fr": {
        "welcome": "Bienvenue à MediAssist",
        "chat_placeholder": "Parlez-moi de vos symptômes...",
        "upload_report": "Télécharger un Rapport de Laboratoire",
        "medication_reminder": "Rappel de Médicament",
        "health_dashboard": "Tableau de Bord Santé",
        "emergency_alert": "Alerte d'Urgence",
        "consult_expert": "Consulter un Expert",
        "voice_input": "Entrée Vocale",
        "logout": "Déconnexion",
        "profile_settings": "Paramètres du Profil",
        "health_trends": "Tendances de Santé",
        "notifications": "Notifications",
    },
    "de": {
        "welcome": "Willkommen bei MediAssist",
        "chat_placeholder": "Erzählen Sie mir von Ihren Symptomen...",
        "upload_report": "Laborbericht hochladen",
        "medication_reminder": "Medikamentenerinnerung",
        "health_dashboard": "Gesundheits-Dashboard",
        "emergency_alert": "Notfallerkennung",
        "consult_expert": "Experten konsultieren",
        "voice_input": "Spracheingabe",
        "logout": "Abmelden",
        "profile_settings": "Profileinstellungen",
        "health_trends": "Gesundheitstrends",
        "notifications": "Benachrichtigungen",
    },
    "hi": {
        "welcome": "MediAssist में आपका स्वागत है",
        "chat_placeholder": "मुझे अपने लक्षणों के बारे में बताएं...",
        "upload_report": "लैब रिपोर्ट अपलोड करें",
        "medication_reminder": "दवा की याद दिलाएं",
        "health_dashboard": "स्वास्थ्य डैशबोर्ड",
        "emergency_alert": "आपातकालीन सतर्कता",
        "consult_expert": "विशेषज्ञ से परामर्श लें",
        "voice_input": "वॉयस इनपुट",
        "logout": "लॉगआउट",
        "profile_settings": "प्रोफाइल सेटिंग",
        "health_trends": "स्वास्थ्य प्रवृत्तियां",
        "notifications": "सूचनाएं",
    },
}


class LanguageManager:
    """Manages language translations and localization"""
    
    def __init__(self):
        self.supported_languages = list(TRANSLATIONS.keys())
    
    def get_translation(self, language: str, key: str, default: str = "") -> str:
        """Get translation for a key in specified language"""
        if language not in TRANSLATIONS:
            language = "en"  # Default to English
        
        return TRANSLATIONS[language].get(key, default or key)
    
    def translate_response(self, response_text: str, target_language: str) -> Dict[str, Any]:
        """
        Translate a response to target language
        This would use Gemini API for full translation in production
        """
        if target_language == "en":
            return {
                "original": response_text,
                "translated": response_text,
                "language": target_language,
            }
        
        # In production, use Gemini or Google Cloud Translation API
        return {
            "original": response_text,
            "translated": f"[Translated to {target_language}] {response_text}",
            "language": target_language,
        }
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages"""
        return {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "hi": "Hindi",
        }
    
    def get_ui_strings(self, language: str) -> Dict[str, str]:
        """Get all UI strings for a language"""
        if language not in TRANSLATIONS:
            language = "en"
        
        return TRANSLATIONS[language]
    
    def format_date_locale(self, date_string: str, language: str = "en") -> str:
        """Format date according to language locale"""
        # Simple date formatting based on locale
        locale_formats = {
            "en": "%Y-%m-%d",  # YYYY-MM-DD
            "es": "%d/%m/%Y",  # DD/MM/YYYY
            "fr": "%d/%m/%Y",  # DD/MM/YYYY
            "de": "%d.%m.%Y",  # DD.MM.YYYY
            "hi": "%d-%m-%Y",  # DD-MM-YYYY
        }
        
        return date_string  # Simplified version
    
    def format_number_locale(self, number: float, language: str = "en") -> str:
        """Format number according to language locale"""
        locale_separators = {
            "en": (".", ","),      # 1,234.56
            "es": (",", "."),      # 1.234,56
            "fr": (",", " "),      # 1 234,56
            "de": (",", "."),      # 1.234,56
            "hi": (",", "."),      # 12,34,567.89
        }
        
        decimal_sep, thousand_sep = locale_separators.get(language, (".", ","))
        
        # Format number
        formatted = f"{number:.2f}"
        parts = formatted.split(".")
        
        # Add thousand separators
        integer_part = parts[0]
        if len(integer_part) > 3:
            # Add separators every 3 digits from right
            integer_part = thousand_sep.join(
                [integer_part[max(0, i-3):i] for i in range(len(integer_part), 0, -3)][::-1]
            )
        
        return f"{integer_part}{decimal_sep}{parts[1]}"


# Global language manager instance
language_manager = LanguageManager()
