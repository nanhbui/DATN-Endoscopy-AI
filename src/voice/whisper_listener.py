'''whisper_listener.py – Simple wrapper around Whisper for real‑time speech‑to‑text.

This module provides a minimal `WhisperListener` class used by the
voice‑control pipeline.  It does **not** implement a full streaming API –
that would require asynchronous audio capture and is outside the scope
of the current MVP.  Instead, it offers a convenient `transcribe`
method that accepts raw audio bytes (e.g. a WAV chunk) and returns the
detected text.

The implementation falls back gracefully when the `whisper` package is
unavailable: it returns an empty string and logs a warning.  This keeps
the rest of the system functional even in environments without the
model installed.
'''  # noqa: D400

import logging
from typing import Optional

logger = logging.getLogger(__name__)


class WhisperListener:
    """Thin wrapper around OpenAI Whisper (or a compatible model).

    Parameters
    ----------
    model_size: str, optional
        Whisper model identifier – ``base``, ``small``, ``medium`` or
        ``large``.  The default ``base`` works on CPU with modest memory.
    language: str, optional
        Language code for transcription (``"vi"`` for Vietnamese).
    device: str, optional
        ``"cpu"`` or ``"cuda"``.  If CUDA is unavailable the class will
        automatically fall back to CPU.
    """

    def __init__(self, model_size: str = "base", language: str = "vi", device: str = "cpu") -> None:
        self.model_size = model_size
        self.language = language
        self.device = device
        self._model = self._load_model()

    # ---------------------------------------------------------------------
    # Private helpers
    # ---------------------------------------------------------------------
    def _load_model(self):
        """Attempt to import and load the Whisper model.

        Returns ``None`` if the import fails – the caller must handle the
        ``None`` case.
        """
        try:
            import whisper  # type: ignore
            model = whisper.load_model(self.model_size, device=self.device)
            logger.info("Whisper model %s loaded on %s", self.model_size, self.device)
            return model
        except Exception as exc:  # pragma: no cover – import may be missing
            logger.warning("Whisper not available: %s. Transcription will be a no‑op.", exc)
            return None

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe a short audio clip.

        ``audio_bytes`` should be a WAV/PCM byte string.  If the Whisper
        model is not loaded the method returns an empty string.
        """
        if not self._model:
            return ""
        try:
            # Whisper expects a file‑like object; ``bytes`` works via ``io.BytesIO``
            import io
            audio_io = io.BytesIO(audio_bytes)
            result = self._model.transcribe(audio_io, language=self.language, fp16=False)
            return result.get("text", "").strip()
        except Exception as exc:  # pragma: no cover – runtime errors are rare
            logger.error("Whisper transcription failed: %s", exc)
            return ""
