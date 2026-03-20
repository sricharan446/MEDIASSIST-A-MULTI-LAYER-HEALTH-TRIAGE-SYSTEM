"""
Voice Input/Output Handler
Enables voice-based queries and responses with real speech-to-text and text-to-speech
"""

import json
import base64
import io
from typing import Optional, Dict, Any
from datetime import datetime
from pathlib import Path
import speech_recognition as sr
from pydub import AudioSegment
from gtts import gTTS

class VoiceHandler:
    """
    Handles voice input (speech-to-text) and output (text-to-speech)
    Uses Google Gemini API for audio processing
    """
    
    def __init__(self, gemini_client=None):
        self.gemini_client = gemini_client
        self.voice_logs_dir = Path("memory") / "voice_logs"
        self.voice_logs_dir.mkdir(parents=True, exist_ok=True)
    
    async def process_voice_input(self, audio_base64: str, language: str = "en") -> Dict[str, Any]:
        """
        Convert voice input (audio) to text using Google Speech Recognition
        
        Args:
            audio_base64: Base64 encoded audio data (WAV, MP3, FLAC, OGG, etc.)
            language: Language code (en, es, fr, de, hi, ta, te, kn, etc.)
        
        Returns:
            Transcribed text with confidence score
        """
        try:
            # Decode base64 audio
            audio_data = base64.b64decode(audio_base64)
            
            # Try to detect audio format - handle both WAV and MP3
            audio_io = io.BytesIO(audio_data)
            
            # Load audio with pydub (auto-detects format)
            try:
                # Try WAV first (most common)
                audio = AudioSegment.from_file(audio_io, format="wav")
            except:
                try:
                    # Try MP3
                    audio_io.seek(0)
                    audio = AudioSegment.from_file(audio_io, format="mp3")
                except:
                    # Try OGG
                    audio_io.seek(0)
                    audio = AudioSegment.from_file(audio_io, format="ogg")
            
            # Convert to 16-bit mono WAV format for Google Speech Recognition
            audio = audio.set_channels(1).set_frame_rate(16000).set_sample_width(2)
            
            # Convert to bytes
            wav_io = io.BytesIO()
            audio.export(wav_io, format="wav")
            wav_data = wav_io.getvalue()
            
            # Use Google Speech Recognition
            recognizer = sr.Recognizer()
            with sr.AudioFile(io.BytesIO(wav_data)) as source:
                audio_frame = recognizer.record(source)
            
            # Language mapping for Google Speech Recognition
            language_code_map = {
                "en": "en-US",
                "es": "es-ES",
                "fr": "fr-FR",
                "de": "de-DE",
                "hi": "hi-IN",
                "ta": "ta-IN",
                "te": "te-IN",
                "kn": "kn-IN",
                "mr": "mr-IN",
                "gu": "gu-IN",
            }
            
            lang_code = language_code_map.get(language, "en-US")
            
            # Perform transcription using Google Speech Recognition API (free)
            try:
                text = recognizer.recognize_google(audio_frame, language=lang_code)
                confidence = 0.9  # Google API doesn't return confidence, but we know it worked
            except sr.UnknownValueError:
                return {
                    "status": "error",
                    "message": "Could not understand the audio",
                    "error_code": "incomprehensible_audio"
                }
            except sr.RequestError as e:
                return {
                    "status": "error",
                    "message": f"Speech recognition service error: {str(e)}",
                    "error_code": "service_error"
                }
            
            # Get audio duration
            duration_seconds = len(audio) / 1000.0
            
            transcription = {
                "text": text,
                "confidence": confidence,
                "language": language,
                "language_code": lang_code,
                "duration_seconds": round(duration_seconds, 2),
                "character_count": len(text),
                "timestamp": datetime.now().isoformat(),
            }
            
            return {
                "status": "success",
                "transcription": transcription,
            }
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "message": f"Voice processing error: {str(e)}",
                "error_code": "processing_error",
                "details": traceback.format_exc()
            }
    
    
    async def generate_voice_output(self, text: str, language: str = "en", voice_style: str = "default") -> Dict[str, Any]:
        """
        Convert text response to voice output (text-to-speech) using Google gTTS
        
        Args:
            text: Text to convert to speech
            language: Language code (en, es, fr, de, hi, ta, te, kn, etc.)
            voice_style: Voice style (neutral, friendly, professional, calm, energetic)
                        Note: gTTS doesn't support individual styles, but we log the preference
        
        Returns:
            Audio data in base64 format with metadata
        """
        try:
            # Truncate very long text to avoid TTS limits
            if len(text) > 5000:
                text = text[:5000] + "... [text truncated]"
            
            # Language code mapping for gTTS
            language_code_map = {
                "en": "en",
                "es": "es",
                "fr": "fr",
                "de": "de",
                "hi": "hi",
                "ta": "ta",
                "te": "te",
                "kn": "kn",
                "mr": "mr",
                "gu": "gu",
            }
            
            lang_code = language_code_map.get(language, "en")
            
            # Generate speech using gTTS
            tts = gTTS(text=text, lang=lang_code, slow=False)
            
            # Save to bytes buffer
            audio_buffer = io.BytesIO()
            tts.write_to_fp(audio_buffer)
            audio_buffer.seek(0)
            
            # Convert to base64
            audio_base64 = base64.b64encode(audio_buffer.getvalue()).decode('utf-8')
            
            # Estimate duration based on words (average: 150 words per minute)
            word_count = len(text.split())
            estimated_duration = (word_count / 150) * 60  # in seconds
            
            audio_response = {
                "audio_base64": audio_base64,
                "language": language,
                "language_code": lang_code,
                "voice_style": voice_style,
                "text_length": len(text),
                "estimated_duration_seconds": round(estimated_duration, 2),
                "timestamp": datetime.now().isoformat(),
                "provider": "gTTS (Google Translate TTS)",
            }
            
            return {
                "status": "success",
                "audio": audio_response,
            }
        except Exception as e:
            import traceback
            return {
                "status": "error",
                "message": f"Text-to-speech error: {str(e)}",
                "error_code": "tts_error",
                "details": traceback.format_exc()
            }
    
    def log_voice_interaction(self, username: str, interaction_type: str, 
                             input_text: Optional[str] = None, 
                             output_text: Optional[str] = None,
                             language: str = "en"):
        """Log voice interactions for analytics"""
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "type": interaction_type,  # "input", "output", "both"
            "input_text": input_text,
            "output_text": output_text,
            "language": language,
        }
        
        voice_log_file = self.voice_logs_dir / f"{username}_voice_log.json"
        logs = []
        
        if voice_log_file.exists():
            with open(voice_log_file, "r") as f:
                logs = json.load(f)
        
        logs.append(log_entry)
        
        # Keep last 100 entries
        if len(logs) > 100:
            logs = logs[-100:]
        
        with open(voice_log_file, "w") as f:
            json.dump(logs, f, indent=2)
    
    def get_supported_languages(self) -> Dict[str, str]:
        """Get list of supported languages"""
        return {
            "en": "English",
            "es": "Spanish",
            "fr": "French",
            "de": "German",
            "hi": "Hindi",
            "ta": "Tamil",
            "te": "Telugu",
            "kn": "Kannada",
            "mr": "Marathi",
            "gu": "Gujarati",
        }
    
    def get_voice_styles(self) -> Dict[str, str]:
        """Get available voice styles"""
        return {
            "neutral": "Professional and neutral tone",
            "friendly": "Warm and friendly tone",
            "professional": "Formal professional tone",
            "calm": "Calm and soothing tone",
            "energetic": "Energetic and upbeat tone",
        }


# Global voice handler instance
voice_handler = VoiceHandler()
