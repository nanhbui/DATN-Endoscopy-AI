"""whisper_transcriber.py — Transcribe audio bytes → Vietnamese text via faster-whisper.

Accepts raw audio in any browser-native format (WebM/OPUS, WAV, MP4).
faster-whisper delegates decoding to ffmpeg, so no manual conversion is needed.
Loads the model once; subsequent calls reuse the same instance.
"""

from __future__ import annotations

import io
import tempfile
import os
from pathlib import Path
from typing import Optional


class WhisperTranscriber:
    """Singleton wrapper around faster-whisper for audio bytes → transcript."""

    _instance: Optional["WhisperTranscriber"] = None

    def __new__(cls, model_size: str = "base") -> "WhisperTranscriber":
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._loaded = False
            cls._instance._model_size = model_size
        return cls._instance

    def _load(self) -> None:
        if self._loaded:
            return
        from faster_whisper import WhisperModel
        try:
            import ctranslate2
            device = "cuda" if ctranslate2.get_cuda_device_count() > 0 else "cpu"
        except Exception:
            device = "cpu"
        compute_type = "float16" if device == "cuda" else "int8"
        print(f"[Whisper] Loading model '{self._model_size}' on {device} ({compute_type})")
        self._model = WhisperModel(self._model_size, device=device, compute_type=compute_type)
        self._loaded = True
        print("[Whisper] Model ready")

    def transcribe(self, audio_bytes: bytes) -> str:
        """Transcribe raw audio bytes to Vietnamese text.

        Args:
            audio_bytes: Raw audio in any format supported by ffmpeg (WebM, WAV, MP4…).

        Returns:
            Transcribed text string, or empty string if nothing was detected.
        """
        self._load()

        # Write to a temp file — faster-whisper/ffmpeg need a seekable source
        suffix = ".webm"
        with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as f:
            f.write(audio_bytes)
            tmp_path = f.name

        try:
            segments, _ = self._model.transcribe(
                tmp_path,
                language="vi",
                beam_size=1,                       # greedy → fast for short commands
                vad_filter=True,                   # Silero VAD: filter silence/noise
                condition_on_previous_text=False,  # avoid hallucination carry-over
                initial_prompt=(                   # bias toward clinical commands
                    "nhầm rồi bỏ qua sai không phải false positive "
                    "giải thích phân tích chi tiết tại sao "
                    "đúng rồi xác nhận chuẩn ok được"
                ),
            )
            return " ".join(seg.text for seg in segments).strip()
        finally:
            os.unlink(tmp_path)
