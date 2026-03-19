"""
IntentClassifier — Phân loại câu nói của bác sĩ thành intent cụ thể.

Hỗ trợ 4 intent chính:
  FALSE_POSITIVE → bác sĩ báo detect sai (trigger Idea 1 - frame skipping)
  EXPLAIN        → bác sĩ muốn LLM giải thích thêm (trigger Idea 2)
  CHECK_AGAIN    → bác sĩ muốn phân tích lại frame hiện tại
  CONFIRM        → bác sĩ xác nhận detect đúng

Thuật toán: keyword matching có trọng số.
  - Keyword dài hơn (nhiều từ hơn) → confidence cao hơn
  - Không dùng LLM để giữ latency thấp (<5ms)
"""

import re
from enum import Enum
from typing import Tuple


class VoiceIntent(Enum):
    FALSE_POSITIVE = "false_positive"
    EXPLAIN = "explain"
    CHECK_AGAIN = "check_again"
    CONFIRM = "confirm"
    UNKNOWN = "unknown"


# Nhãn tiếng Việt để hiển thị / log
INTENT_LABELS = {
    VoiceIntent.FALSE_POSITIVE: "Bỏ qua (false positive)",
    VoiceIntent.EXPLAIN: "Giải thích thêm",
    VoiceIntent.CHECK_AGAIN: "Kiểm tra lại",
    VoiceIntent.CONFIRM: "Xác nhận đúng",
    VoiceIntent.UNKNOWN: "Không rõ",
}


class IntentClassifier:
    """
    Phân loại text tiếng Việt thành VoiceIntent dùng keyword matching.

    Trả về (intent, confidence) trong đó confidence ∈ [0.0, 1.0].
    Confidence được tính dựa trên độ dài keyword khớp:
      - keyword 1 từ → 0.5
      - keyword 2 từ → 0.7
      - keyword 3+ từ → 0.9
    """

    # Bảng keyword cho từng intent.
    # Liệt kê từ cụ thể → chung để ưu tiên match dài trước.
    _PATTERNS: dict = {
        VoiceIntent.FALSE_POSITIVE: [
            # Câu dài / cụm từ đặc thù (ưu tiên cao)
            "bắt sai rồi",
            "nhận sai rồi",
            "không phải tổn thương",
            "bọt trắng",
            "ánh sáng phản chiếu",
            "dịch nhầy",
            "false positive",
            # Cụm từ 2 từ
            "bỏ qua",
            "loại bỏ",
            "không phải",
            "không đúng",
            "bắt sai",
            "nhận sai",
            # Từ đơn
            "nhầm",
            "sai",
            "bọt",
            "loáng",
        ],
        VoiceIntent.EXPLAIN: [
            "giải thích thêm",
            "nói thêm về",
            "chi tiết hơn",
            "phân tích thêm",
            "thêm thông tin",
            "tại sao lại",
            "vì sao lại",
            # 2 từ
            "giải thích",
            "phân tích",
            "nói thêm",
            "chi tiết",
            # 1 từ
            "tại sao",
            "vì sao",
        ],
        VoiceIntent.CHECK_AGAIN: [
            "kiểm tra lại",
            "phân tích lại",
            "đánh giá lại",
            "xem lại đi",
            "nhìn lại xem",
            "check lại",
            # 2 từ
            "xem lại",
            "nhìn lại",
            "xác nhận",
            # 1 từ
            "kiểm tra",
            "lại",
        ],
        VoiceIntent.CONFIRM: [
            "đúng rồi",
            "chính xác",
            "lưu lại",
            "ghi nhận",
            "xác nhận đúng",
            # 1 từ
            "đúng",
            "chuẩn",
            "ok",
            "được",
        ],
    }

    def classify(self, text: str) -> Tuple[VoiceIntent, float]:
        """
        Phân loại text thành (VoiceIntent, confidence).

        Args:
            text: câu nói đã được Whisper transcribe

        Returns:
            Tuple (intent, confidence). Nếu không khớp → (UNKNOWN, 0.0)
        """
        normalized = self._normalize(text)

        best_intent = VoiceIntent.UNKNOWN
        best_confidence = 0.0

        for intent, keywords in self._PATTERNS.items():
            for keyword in keywords:
                if keyword in normalized:
                    confidence = self._keyword_confidence(keyword)
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_intent = intent

        return best_intent, best_confidence

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _normalize(text: str) -> str:
        """Lowercase, bỏ dấu câu để tăng tỷ lệ match."""
        text = text.lower().strip()
        text = re.sub(r"[^\w\s]", "", text)   # bỏ dấu câu
        text = re.sub(r"\s+", " ", text)       # chuẩn hóa khoảng trắng
        return text

    @staticmethod
    def _keyword_confidence(keyword: str) -> float:
        """
        Tính confidence theo số từ trong keyword:
          1 từ  → 0.5  (có thể false match)
          2 từ  → 0.7
          3+ từ → 0.9  (rất đặc thù)
        """
        word_count = len(keyword.split())
        if word_count == 1:
            return 0.5
        elif word_count == 2:
            return 0.7
        else:
            return 0.9
