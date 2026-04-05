"""voice_api.py – FastAPI endpoints for voice command processing.

Provides a single POST endpoint `/voice/command` that receives an audio file
(in any common format, e.g. WAV, MP3) and returns the detected intent and the
corresponding response message (skip confirmation or LLM explanation).

The endpoint uses the existing `VoiceController` implementation located in
`src/voice/voice_controller.py`.  The controller is instantiated once at module
import time – this is cheap because the Whisper model is lazy‑loaded inside the
wrapper.

Typical request from the frontend (React) looks like:
```js
const form = new FormData();
form.append('audio', fileBlob);
await fetch('/voice/command', {method: 'POST', body: form});
```

The response schema mirrors the internal `VoiceIntent` enum but is returned as
plain strings for simplicity.
"""

from fastapi import APIRouter, UploadFile, File, HTTPException, status
from fastapi.responses import JSONResponse

# Import the controller – the path is relative to the repository root.
# Adding the project root to `sys.path` is already done in `api_server.py`,
# but we repeat it here to be safe when this module is imported directly.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # project root

from src.voice.voice_controller import VoiceController, VoiceIntent

router = APIRouter()

# Initialise a singleton controller.  Whisper will load the model on first use.
_controller = VoiceController()


@router.post("/voice/command", response_class=JSONResponse)
async def voice_command(audio: UploadFile = File(...)):
    """Process an uploaded audio chunk and return the detected intent.

    Parameters
    ----------
    audio: UploadFile
        The raw audio file sent by the client.
    """
    if not audio.content_type.startswith("audio/"):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Uploaded file is not an audio type"
        )
    try:
        # Read the entire file into memory – audio chunks are small (<1 MB).
        audio_bytes = await audio.read()
        intent, response_msg = _process(audio_bytes)
        return JSONResponse(
            status_code=status.HTTP_200_OK,
            content={
                "intent": intent.value,
                "intent_label": intent.name,
                "message": response_msg,
            },
        )
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice processing failed: {exc}"
        )


def _process(audio_bytes: bytes):
    """Delegate to the shared `VoiceController`.

    Returns a tuple ``(VoiceIntent, str)`` where the string is the UI message.
    """
    return _controller.process_audio(audio_bytes)
