"""
VoiceController — Điểm kết nối giữa WhisperListener và IntentClassifier.

Cung cấp interface đơn giản cho phần còn lại của hệ thống:
  - Gọi start() để bắt đầu lắng nghe
  - Đặt callback on_intent để nhận kết quả
  - Gọi stop() để dừng

Callback signature:
  on_intent(intent: VoiceIntent, raw_text: str, confidence: float)
"""

import threading
from typing import Callable, Optional

from .intent_classifier import IntentClassifier, VoiceIntent
from .whisper_listener import WhisperListener


class VoiceController:
    """
    Orchestrates WhisperListener + IntentClassifier.

    Luồng dữ liệu:
      Mic → WhisperListener.on_transcription → _handle_transcription
          → IntentClassifier.classify → on_intent callback
    """

    def __init__(self, model_size: str = "base", language: str = "vi"):
        self.listener = WhisperListener(model_size=model_size, language=language)
        self.classifier = IntentClassifier()
        self._lock = threading.Lock()

        # Callback chính — hệ thống bên ngoài đăng ký callback này
        self.on_intent: Optional[Callable[[VoiceIntent, str, float], None]] = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def start(self):
        """Bắt đầu lắng nghe mic."""
        self.listener.on_transcription = self._handle_transcription
        self.listener.start()
        print("[VoiceController] Sẵn sàng nhận lệnh giọng nói.")

    def stop(self):
        """Dừng lắng nghe."""
        self.listener.stop()
        print("[VoiceController] Đã dừng.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _handle_transcription(self, text: str):
        """
        Nhận text từ Whisper → classify → gọi on_intent.

        Intent UNKNOWN bị lọc ra, không gọi callback,
        để tránh trigger hệ thống với những câu không liên quan.
        """
        intent, confidence = self.classifier.classify(text)

        from .intent_classifier import INTENT_LABELS
        label = INTENT_LABELS[intent]
        print(f"[Voice] '{text}'  →  {label}  (conf: {confidence:.2f})")

        if intent == VoiceIntent.UNKNOWN:
            return

        if self.on_intent:
            with self._lock:
                self.on_intent(intent, text, confidence)


# ------------------------------------------------------------------
# Quick test — chạy trực tiếp để kiểm tra
# ------------------------------------------------------------------

if __name__ == "__main__":
    import time

    def handle_intent(intent: VoiceIntent, text: str, confidence: float):
        print(f"\n>>> INTENT: {intent.value} | confidence={confidence:.2f} | text='{text}'\n")

    controller = VoiceController(model_size="base")
    controller.on_intent = handle_intent
    controller.start()

    print("Nói vào mic để test. Ctrl+C để thoát.\n")
    try:
        while True:
            time.sleep(0.1)
    except KeyboardInterrupt:
        controller.stop()
