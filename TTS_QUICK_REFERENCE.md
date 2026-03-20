# Text-to-Speech (TTS) Quick Reference

**Status:** ✅ Production Ready | **Provider:** Google Translate TTS (gTTS) | **Cost:** Free

## Quick Start (30 seconds)

### 1. Backend: Generate Audio
```python
from services.voice_handler import voice_handler

# Generate audio
result = voice_handler.generate_voice_output(
    text="Hello, how can I help?",
    language="en"
)

# Response
{
    "audio": "base64_encoded_mp3...",
    "language_code": "en",
    "format": "mp3",
    "estimated_duration": 2.5
}
```

### 2. Frontend: Play Audio
```javascript
// Receive base64 audio from API
const audio = new Audio(`data:audio/mp3;base64,${response.audio}`);
audio.play();
```

### 3. In Chat (Full Flow)
```javascript
// When user clicks "Listen" or auto-play response
async function playResponse(text) {
    const res = await fetch('/api/voice-output', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text, language: 'en'})
    });
    
    const data = await res.json();
    const audio = new Audio(`data:audio/mp3;base64,${data.audio}`);
    audio.play();
}
```

## API Reference

### Endpoint: `POST /api/voice-output`

| Aspect | Value |
|--------|-------|
| **URL** | `/api/voice-output` |
| **Method** | POST |
| **Auth** | Token required |
| **Content-Type** | application/json |

### Request
```json
{
    "text": "Text to convert to speech",
    "language": "en"
}
```

**Parameters:**
- `text` (required): String up to 5000 characters
- `language` (optional): Language code. Default: `"en"`

### Response (Success)
```json
{
    "audio": "SUQzBAAAI1RJVDIAAAcDC...",
    "language_code": "en",
    "language_name": "English",
    "text_length": 25,
    "estimated_duration": 5.2,
    "provider": "gTTS",
    "format": "mp3",
    "truncated": false,
    "metadata": {
        "generation_time_ms": 1250,
        "compression_method": "base64"
    }
}
```

### Response (Error)
```json
{
    "error": "Language 'invalid' not supported",
    "status": "failed",
    "supported_languages": ["en", "es", "fr", "de", "hi", "ta", "te", "kn", "mr", "gu"]
}
```

## Supported Languages

| Language | Code | Example |
|----------|------|---------|
| English | `en` | Hello |
| Spanish | `es` | Hola |
| French | `fr` | Bonjour |
| German | `de` | Guten Tag |
| Hindi | `hi` | नमस्ते |
| Tamil | `ta` | வணக்கம் |
| Telugu | `te` | హలో |
| Kannada | `kn` | ಹಲೋ |
| Marathi | `mr` | नमस्कार |
| Gujarati | `gu` | હેલો |

## Code Examples

### Backend Only
```python
from services.voice_handler import voice_handler

# Simple TTS
audio_data = voice_handler.generate_voice_output("Take your medicine", "en")

# Check if successful
if "error" not in audio_data:
    mp3_audio = audio_data["audio"]  # Base64-encoded MP3
    duration = audio_data["estimated_duration"]
    print(f"Audio ready: {duration}s")
else:
    print(f"Error: {audio_data['error']}")
```

### Frontend Only (with fetch)
```javascript
// Using fetch
async function textToSpeech(text) {
    const response = await fetch('/api/voice-output?token=YOUR_TOKEN', {
        method: 'POST',
        headers: {'Content-Type': 'application/json'},
        body: JSON.stringify({text, language: 'en'})
    });
    
    const data = await response.json();
    
    if (data.error) {
        console.error('TTS Error:', data.error);
        return;
    }
    
    // Play audio
    const audio = new Audio(`data:audio/mp3;base64,${data.audio}`);
    audio.play();
}

// Usage
textToSpeech("The temperature is 39 degrees");
```

### Full Stack (Chat Integration)
```python
# Backend (FastAPI)
@app.post("/api/chat")
async def chat(message: str, language: str = "en", token: str = None):
    # ... triage logic
    response_text = "Your symptoms suggest..."
    
    # Generate voice
    voice_data = voice_handler.generate_voice_output(response_text, language)
    
    return {
        "message": response_text,
        "voice_audio": voice_data["audio"],
        "voice_language": language
    }
```

```javascript
// Frontend (JavaScript)
async function sendMessage(text) {
    const response = await fetch('/api/chat?token=YOUR_TOKEN', {
        method: 'POST',
        body: JSON.stringify({message: text, language: 'en'})
    });
    
    const data = await response.json();
    
    // Display text
    displayMessage(data.message);
    
    // Play audio (if available)
    if (data.voice_audio) {
        const audio = new Audio(`data:audio/mp3;base64,${data.voice_audio}`);
        audio.play();
    }
}
```

## Common Tasks

### Task: Play Response After Chat
```javascript
// Get response from chat API
const chatResponse = await chat("I have a fever");

// Play audio if available
if (chatResponse.voice_audio) {
    playAudio(chatResponse.voice_audio);
}

function playAudio(base64Audio) {
    const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
    audio.addEventListener('ended', () => console.log('👂 Audio finished'));
    audio.play();
}
```

### Task: Add Listen Button to Chat Bubble
```html
<div class="message">
    <p>Your symptoms suggest...</p>
    <button onclick="playThis('base64_audio_here')">
        🔊 Listen
    </button>
</div>

<script>
function playThis(base64Audio) {
    const audio = new Audio(`data:audio/mp3;base64,${base64Audio}`);
    audio.play();
}
</script>
```

### Task: Change Language Dynamically
```javascript
// Get user's language preference
const userLanguage = getCurrentUserLanguage();  // "es", "hi", etc.

// Send TTS request in that language
const ttsResponse = await fetch('/api/voice-output?token=TOKEN', {
    method: 'POST',
    body: JSON.stringify({
        text: "Hola, ¿cómo estás?",
        language: userLanguage
    })
});

const audio = await ttsResponse.json();
playAudio(audio.audio);
```

### Task: Cache Audio to Avoid Regeneration
```python
# Store generated audio in memory
audio_cache = {}

def get_voice_output(text, language):
    cache_key = f"{language}:{hash(text)}"
    
    # Return from cache if exists
    if cache_key in audio_cache:
        return audio_cache[cache_key]
    
    # Generate new audio
    result = voice_handler.generate_voice_output(text, language)
    audio_cache[cache_key] = result["audio"]  # Cache it
    
    return result
```

## Performance Tips

| Tip | Benefit |
|-----|---------|
| **Cache generated audio** | Avoid regenerating same text |
| **Limit text to ~500 chars** | Faster generation |
| **Use base64 in JSON** | Simpler than file transfer |
| **Implement error handling** | Better UX gracefully handle failures |
| **Use user's preferred language** | Better experience |

## Limits & Constraints

| Constraint | Value | Note |
|-----------|-------|------|
| Max text length | 5000 chars | Google API limit |
| Generation time | ~1-2 sec | Depends on text length |
| Audio format | MP3 only | Standard bitrate |
| Required internet | Yes | Cloud API dependency |
| Rate limiting | ~50-100 req/min | Use caching to reduce |
| Cost | Free | Google Translate TTS |

## Troubleshooting

### Audio not playing
```javascript
// Check if data URI is correct
console.log(audioData.substring(0, 30)); // Should start with "SUQz" (MP3 magic)

// Check browser support
if (!('Audio' in window)) {
    console.error('Browser does not support Audio API');
}

// Try with explicit type
const audio = new Audio();
audio.src = `data:audio/mp3;base64,${data.audio}`;
audio.play();
```

### Language not supported
```python
# Check supported languages
result = voice_handler.generate_voice_output("test", "xyz")
if "error" in result:
    print(result["supported_languages"])
    # ["en", "es", "fr", "de", "hi", "ta", "te", "kn", "mr", "gu"]
```

### Network error
```python
# Add retry logic
import time

def generate_with_retry(text, language, retries=3):
    for attempt in range(retries):
        try:
            return voice_handler.generate_voice_output(text, language)
        except Exception as e:
            if attempt < retries - 1:
                time.sleep(2 ** attempt)  # Exponential backoff
            else:
                return {"error": str(e)}
```

## Files & Locations

| File | Purpose |
|------|---------|
| `services/voice_handler.py` | TTS implementation |
| `TEXT_TO_SPEECH_IMPLEMENTATION.md` | Full technical docs |
| `VOICE_FEATURE.md` | Complete voice system guide |
| `VOICE_QUICK_REFERENCE.md` | STT & TTS combined reference |
| `requirements.txt` | Dependencies (gtts, pydub) |

## Related Commands

```bash
# Test TTS directly
curl -X POST "http://localhost:8000/api/voice-output" \
  -H "Content-Type: application/json" \
  -d '{"text": "Test message", "language": "en"}'

# Check installation
python -c "from gtts import gTTS; print('✅ gTTS installed')"

# Generate audio file (for debugging)
python -c "from gtts import gTTS; gTTS('hello', lang='en').save('test.mp3')"
```

## API Response Codes

| Code | Status | Meaning |
|------|--------|---------|
| 200 | Success | Audio generated successfully |
| 400 | Bad Request | Invalid language or text too long |
| 401 | Unauthorized | Token missing or invalid |
| 500 | Server Error | Generation failed (network issue) |

## Version Info

- **TTS Provider:** Google Translate (gTTS)
- **Library Version:** 2.5.4+
- **Added in:** MediAssist v4.1
- **Status:** ✅ Production Ready

## Need Help?

- Check [TEXT_TO_SPEECH_IMPLEMENTATION.md](TEXT_TO_SPEECH_IMPLEMENTATION.md) for detailed docs
- See [VOICE_FEATURE.md](VOICE_FEATURE.md) for complete voice system
- Review `services/voice_handler.py` for source code
