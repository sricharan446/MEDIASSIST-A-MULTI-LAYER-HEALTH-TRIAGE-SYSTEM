# 🎤 Speech-to-Text Quick Reference

## For Users

### How to Use Voice Input

1. **Click the microphone** 🎤 (next to Send button)
2. **Speak clearly** (any supported language)
3. **Click stop** ⏹️ when done
4. **Review the transcription** (appears with confidence score)
5. **Send it** or edit before sending

## For Developers

### What Changed

| File | Change | Type |
|------|--------|------|
| `services/voice_handler.py` | Replaced placeholder with real Google Speech Recognition | Modified |
| `index.html` | Added microphone button + JavaScript recording | Modified |
| `requirements.txt` | Added SpeechRecognition, pydub | Modified |
| `VOICE_FEATURE.md` | Complete documentation | New |
| `SPEECH_TO_TEXT_IMPLEMENTATION.md` | Implementation summary | New |

### Key Functions

**Backend:**
```python
# In services/voice_handler.py
await voice_handler.process_voice_input(audio_base64, language="en")
# Returns: {"status": "success", "transcription": {...}}
```

**Frontend:**
```javascript
// In index.html
toggleVoiceRecording()  // Start/stop recording
// Automatically sends to /api/voice-input
```

### API Endpoint

```
POST /api/voice-input?token=TOKEN&language=en
Content-Type: application/json

{
  "audio_base64": "UklGRi4AAABXQVZFZm10IBAAAAABAAEAQB8AAAB9AAACABAAZGF0YQIAAAAAAA=="
}

Response:
{
  "status": "success",
  "transcription": {
    "text": "I have a fever and cough",
    "confidence": 0.95,
    "language": "en",
    "language_code": "en-US",
    "duration_seconds": 3.5,
    "character_count": 27,
    "timestamp": "2026-03-20T10:30:45.123456"
  }
}
```

### Supported Languages

| Code | Language | Region |
|------|----------|--------|
| en | English | US/UK/AU |
| es | Spanish | Spain |
| fr | French | France |
| de | German | Germany |
| hi | Hindi | India |
| ta | Tamil | South India |
| te | Telugu | South India |
| kn | Kannada | Karnataka |
| mr | Marathi | Maharashtra |
| gu | Gujarati | Gujarat |

### Installation (Already Done)

```bash
pip install SpeechRecognition pydub
# Optional: ffmpeg (for better audio support)
```

### Testing

**Manual Test:**
```bash
# 1. Start app
python app.py

# 2. Browser: http://localhost:8000
# 3. Signup/Login
# 4. Click microphone button 🎤
# 5. Speak: "My head hurts"
# 6. See transcription appear
```

**API Test:**
```bash
curl -X POST "http://localhost:8000/api/voice-input?token=abc&language=en" \
  -H "Content-Type: application/json" \
  -d '{"audio_base64":"UklGRi4AAABXQVZFZM18..."}'
```

### Error Codes

| Code | Meaning | Solution |
|------|---------|----------|
| `incomprehensible_audio` | Couldn't understand speech | Speak louder/clearer |
| `service_error` | API connection failed | Check internet |
| `processing_error` | General error | Check audio format |

### Performance

- **Latency:** 1-3 seconds per transcription
- **Audio Duration Max:** ~30 seconds
- **Supported Formats:** WAV, MP3, OGG, FLAC
- **Sample Rate:** Auto-converted to 16 kHz
- **Channels:** Auto-converted to mono

### Security

✅ Token-based authentication  
✅ Microphone permissions (browser)  
✅ Audit logging  
✅ No audio file storage  
✅ GDPR compliant (`/api/export-data`, `/api/delete-account`)

### Documentation Files

- **VOICE_FEATURE.md** - User guide + troubleshooting
- **SPEECH_TO_TEXT_IMPLEMENTATION.md** - Technical implementation
- **This file** - Quick reference

### Common Issues & Fixes

| Issue | Fix |
|-------|-----|
| "Microphone access denied" | Allow in browser permission popup (lock icon) |
| "Could not understand audio" | Speak clearly in quiet place, try again |
| "Voice service error" | Check internet connection, app.py running |
| Transcription empty | Check microphone is working (test in another app) |
| Text appears but stops | Try shorter audio clips (~10 sec) |

### Next: Optional Text-to-Speech

To add voice output (read responses aloud), integrate:
- Google Cloud Text-to-Speech
- Azure Speech Services  
- AWS Polly

Example:
```python
# In services/voice_handler.py
from google.cloud import texttospeech
# Implementation here
```

---

**Version:** 1.0 | **Status:** ✅ Ready | **Date:** March 20, 2026
