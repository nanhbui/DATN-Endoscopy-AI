"""voice_api.py — FastAPI router for voice command processing.

POST /voice/command
  Receives a browser MediaRecorder audio chunk (WebM/OPUS or WAV),
  transcribes it with faster-whisper on the GPU, classifies the intent,
  and returns the action for the frontend to execute.

Typical request from the frontend:
  const form = new FormData();
  form.append('audio', blob, 'chunk.webm');
  await fetch(`${API_BASE}/voice/command`, { method: 'POST', body: form });
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse

# Ensure project root is on sys.path so src.voice imports work
sys.path.insert(0, str(Path(__file__).resolve().parents[3]))

from src.voice.whisper_transcriber import WhisperTranscriber
from src.voice.intent_classifier import IntentClassifier

router = APIRouter()

# Singletons — model loaded once on first request, reused for all subsequent calls
_transcriber = WhisperTranscriber(model_size="base")
_classifier = IntentClassifier()


@router.post("/voice/command", response_class=JSONResponse)
async def voice_command(audio: UploadFile = File(...)):
    """Transcribe audio chunk and return classified voice intent.

    Returns:
        {
          "transcript": "bỏ qua đi",
          "intent": "bo_qua",       # bo_qua | giai_thich | xac_nhan | unknown
          "confidence": 0.7
        }
    """
    try:
        audio_bytes = await audio.read()
        # Run blocking Whisper inference off the event loop thread
        loop = asyncio.get_running_loop()
        transcript = await loop.run_in_executor(None, _transcriber.transcribe, audio_bytes)
        intent, confidence = _classifier.classify(transcript)
        print(f"[Voice] '{transcript}' → {intent.value} ({confidence:.2f})")
        return JSONResponse(content={
            "transcript": transcript,
            "intent": intent.name,          # "BO_QUA" | "GIAI_THICH" | "XAC_NHAN" | "UNKNOWN"
            "confidence": round(confidence, 2),
        })
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Voice processing failed: {exc}",
        )
