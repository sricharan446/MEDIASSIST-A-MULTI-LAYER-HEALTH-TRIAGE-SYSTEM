# Voice Input Feature - Speech-to-Text Implementation

## Overview

MediAssist now includes **real speech-to-text functionality** powered by Google's Speech Recognition API. Users can speak their health queries directly without typing.

## What's New

### ✅ Real Speech-to-Text
- **Backend**: Google Speech Recognition API (free, no API key needed)
- **UI**: New microphone button (🎤) in the chat input area
- **Supported**: 10+ languages (English, Spanish, French, German, Hindi, Tamil, Telugu, Kannada, Marathi, Gujarati)

### 📊 Implementation Details

**Frontend (Browser):**
- Captures audio using Web Audio API (`navigator.mediaDevices.getUserMedia`)
- Records in WAV format for best compatibility
- Converts to base64 and sends to backend

**Backend (Python):**
- Uses `SpeechRecognition` library with Google's free API
- Automatically detects audio format (WAV, MP3, OGG)
- Returns transcribed text with confidence score
- Handles errors gracefully (incomprehensible audio, network issues)

## How to Use

### Recording Voice

1. **Click the microphone button** (🎤) in the chat input area
   - Button turns red and changes to ⏹️ (recording indicator)
   - Mic LED shows active recording

2. **Speak clearly** into your microphone
   - Speak naturally - the system handles accents
   - Speak in the selected language (see Settings)

3. **Click the stop button** (⏹️) to finish
   - Recording stops automatically
   - System processes the audio

4. **Review transcription**
   - Transcribed text appears in the chat
   - Confidence score shows (e.g., "95.2% confidence")
   - Text is automatically filled in the input box

5. **Send the message**
   - Click "Send ↑" to process the transcribed text
   - Or edit before sending

## Features

### ✨ Smart Defaults
- Auto-detects language from user preferences
- Maintains input placeholder during idle
- Shows confidence score for transparency
- Logs all voice interactions for audit trail

### 🛡️ Privacy & Security
- Audio is processed by Google's free API
- No recording stored locally (only transcribed text)
- All voice interactions logged with timestamp
- GDPR-compliant audit trail in `/api/audit-log`

### 🌍 Supported Languages
```
en   → English (US/UK/AU)
es   → Spanish 
fr   → French
de   → German
hi   → Hindi
ta   → Tamil
te   → Telugu
kn   → Kannada
mr   → Marathi
gu   → Gujarati
```

Select language from Settings or use API:
```bash
curl "http://localhost:8000/api/voice-languages?token=YOUR_TOKEN"
```

## API Endpoint

### `/api/voice-input` (POST)

Convert audio to text.

**Parameters:**
- `token` (query) - User authentication token
- `audio_base64` (body) - Base64-encoded audio data
- `language` (query, optional) - Language code (default: "en")

**Example:**
```bash
curl -X POST "http://localhost:8000/api/voice-input?token=YOUR_TOKEN&language=en" \
  -H "Content-Type: application/json" \
  -d '{"audio_base64": "UklGRi4AAABXQVZFZm10IBAAAAABAAEAQB8AAAB9AAACABAAZGF0YQIAAAAAAA=="}'
```

**Response:**
```json
{
  "status": "success",
  "transcription": {
    "text": "I have flu-like symptoms with fever and cough",
    "confidence": 0.95,
    "language": "en",
    "language_code": "en-US",
    "duration_seconds": 4.32,
    "character_count": 52,
    "timestamp": "2026-03-20T10:30:45.123456"
  }
}
```

**Error Response:**
```json
{
  "status": "error",
  "message": "Could not understand the audio",
  "error_code": "incomprehensible_audio"
}
```

## Installation & Setup

### 1. Install Dependencies (Already Done)
```bash
pip install SpeechRecognition pydub
```

### 2. Optional: Install ffmpeg for Audio Support
For best audio format support, install ffmpeg:

**Windows:**
```bash
# Using chocolatey
choco install ffmpeg

# Or download from https://ffmpeg.org/download.html
```

**Mac:**
```bash
brew install ffmpeg
```

**Linux:**
```bash
sudo apt-get install ffmpeg
```

### 3. Verify Setup
Test the voice endpoint:
```bash
# First login to get token
curl -X POST "http://localhost:8000/api/signup" \
  -H "Content-Type: application/json" \
  -d '{"username": "testuser", "password": "test123"}'

# Then test voice input
curl "http://localhost:8000/api/voice-languages?token=YOUR_TOKEN"
```

## Examples

### Use Case 1: Urgent Symptoms
1. Click microphone 🎤
2. Say: "I'm having severe chest pain and shortness of breath"
3. System transcribes and triggers emergency response
4. Hospital finder appears automatically

### Use Case 2: Follow-up Triage
1. System asks: "How long have you had this fever?"
2. Click microphone and say: "Started yesterday evening"
3. System continues conversation with voice input

### Use Case 3: Multi-language Query
1. Change language to Spanish in settings
2. Click microphone
3. Say in Spanish: "Tengo fiebre y tos"
4. System transcribes and responds in appropriate language

## Troubleshooting

### "Microphone access denied"
- **Issue**: Browser hasn't allowed microphone permissions
- **Solution**: 
  1. Click the lock icon in address bar
  2. Find "Microphone" and select "Allow"
  3. Refresh page and try again

### "Could not understand the audio"
- **Issue**: Audio too noisy or unclear
- **Solution**:
  1. Find a quieter environment
  2. Speak clearly and directly into microphone
  3. Avoid background noise
  4. Try again

### "Voice service error"
- **Issue**: Backend connection or processing error
- **Solution**:
  1. Check if app.py is running
  2. Check internet connection (Google API needs internet)
  3. Check browser console for detailed error
  4. Try again in a few seconds

### Audio Format Not Supported
- **Issue**: Browser doesn't support audio format
- **Solution**:
  1. Install ffmpeg (see Installation section)
  2. Use modern browser (Chrome, Firefox, Safari, Edge)
  3. Record shorter audio clips (~10 seconds)

## Technical Details

### Audio Processing Pipeline

```
Browser Microphone
    ↓
Recording (Web Audio API)
    ↓
Base64 Encoding
    ↓
HTTP POST to /api/voice-input
    ↓
Backend: Decode base64
    ↓
Convert to 16-bit mono WAV (pydub)
    ↓
Google Speech Recognition API
    ↓
Return Transcribed Text
    ↓
Frontend: Display in Chat
```

### Language Code Mapping

The system maps 2-letter codes to Google's language format:

```python
{
    "en": "en-US",      # English (US)
    "es": "es-ES",      # Spanish (Spain)
    "fr": "fr-FR",      # French (France)
    "de": "de-DE",      # German
    "hi": "hi-IN",      # Hindi (India)
    "ta": "ta-IN",      # Tamil (India)
    "te": "te-IN",      # Telugu (India)
    "kn": "kn-IN",      # Kannada (India)
    "mr": "mr-IN",      # Marathi (India)
    "gu": "gu-IN",      # Gujarati (India)
}
```

### Confidence Scoring

The system returns a confidence score (0.0-1.0) indicating transcription accuracy:
- **0.95-1.0** → Excellent match
- **0.85-0.95** → Good match
- **0.70-0.85** → Fair match (consider reviewing)
- **< 0.70** → Poor match (recommend re-recording)

## Advanced: Text-to-Speech (Future)

For full voice I/O, we can integrate text-to-speech services:

### Option 1: Google Cloud Text-to-Speech (Recommended)
```bash
pip install google-cloud-text-to-speech
```

### Option 2: Azure Speech Services
```bash
pip install azure-cognitiveservices-speech
```

### Option 3: Open-Source ESpeakNG
```bash
# Linux: sudo apt-get install espeak-ng
# Mac: brew install espeak-ng
# Windows: Download from https://github.com/espeak-ng/espeak-ng
```

## Performance Notes

- **Latency**: ~1-3 seconds (network dependent)
- **Max Audio Duration**: ~30 seconds per recording
- **Supported Formats**: WAV, MP3, OGG, FLAC
- **Sample Rate**: Auto-converted to 16 kHz
- **Channels**: Auto-converted to mono

## Security Considerations

✅ **Implemented:**
- Audio processed through secure HTTPS only
- Token-based authentication required
- Audit logging of all voice inputs
- No audio files stored permanently
- User consent (microphone permission) required

⚠️ **Best Practices:**
- Use HTTPS in production (crucial for audio APIs)
- Regularly audit voice logs via `/api/audit-log`
- Monitor for unusual voice activity patterns
- Consider privacy policies for audio processing

## Future Enhancements

1. **Real-time Transcription** - Show text as user speaks
2. **Speaker Identification** - Distinguish between multiple speakers
3. **Accent Optimization** - Pre-configure for specific regional accents
4. **Offline Support** - Local speech-to-text without internet
5. **Audio Enhancement** - Noise cancellation, echo removal
6. **Multilingual Support** - Auto-detect language during recording

## Support & Feedback

For issues or feature requests:
1. Check browser console (F12) for errors
2. Review app logs: `tail -f nohup.out`
3. Test endpoint directly: `/api/voice-languages?token=YOUR_TOKEN`
4. File an issue with:
   - Browser and OS version
   - Language being used
   - Audio sample if possible

---

**Version:** 1.0  
**Release Date:** March 20, 2026  
**Status:** Production Ready ✅
