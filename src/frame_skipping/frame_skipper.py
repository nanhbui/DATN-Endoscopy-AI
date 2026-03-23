"""
FrameSkipper — Kết nối VoiceController với NegativeFrameStore.

Nhận frame (numpy BGR từ OpenCV) + tín hiệu voice intent BO_QUA
→ encode bằng CLIP → lưu/query FAISS → quyết định skip hay không.
"""

from __future__ import annotations

import numpy as np
from typing import Optional, Callable

from .faiss_store import NegativeFrameStore


class FrameSkipper:
    """
    Adaptive Frame Skipping dựa trên voice feedback của bác sĩ.

    Sử dụng:
        skipper = FrameSkipper()

        # Khi bác sĩ nói "nhầm rồi":
        skipper.add_negative(current_frame)

        # Trước khi gửi frame lên YOLO:
        if skipper.should_skip(frame):
            continue
    """

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        index_path: Optional[str] = None,
        on_skip: Optional[Callable[[float], None]] = None,
    ):
        """
        Args:
            similarity_threshold: Cosine similarity tối thiểu để skip (0.0–1.0)
            index_path:           Path lưu FAISS index persistent
            on_skip:              Callback khi frame bị skip: on_skip(similarity)
        """
        self.store = NegativeFrameStore(
            similarity_threshold=similarity_threshold,
            index_path=index_path,
        )
        self.on_skip = on_skip
        self._clip_model = None
        self._clip_preprocess = None
        self._device = None

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add_negative(self, frame: np.ndarray):
        """
        Thêm frame hiện tại vào negative store (bác sĩ báo false positive).

        Args:
            frame: numpy array BGR (H, W, 3) từ OpenCV
        """
        embedding = self._encode(frame)
        count = self.store.add(embedding)
        print(f"[FrameSkipper] Thêm negative frame #{count} vào FAISS store.")

    def should_skip(self, frame: np.ndarray) -> bool:
        """
        Kiểm tra frame có nên bị skip không.

        Args:
            frame: numpy array BGR (H, W, 3)

        Returns:
            True nếu frame tương tự một false-positive đã biết
        """
        embedding = self._encode(frame)
        skip, similarity = self.store.should_skip(embedding)

        if skip:
            print(f"[FrameSkipper] Skip frame — similarity={similarity:.3f}")
            if self.on_skip:
                self.on_skip(similarity)

        return skip

    @property
    def negative_count(self) -> int:
        return self.store.count

    def reset(self):
        """Xóa toàn bộ negative frames (dùng khi bắt đầu ca nội soi mới)."""
        self.store.reset()

    # ------------------------------------------------------------------
    # Internal — CLIP encoding
    # ------------------------------------------------------------------

    def _get_clip(self):
        """Lazy load CLIP model."""
        if self._clip_model is None:
            import torch
            import clip  # pip install git+https://github.com/openai/CLIP.git

            self._device = "cuda" if torch.cuda.is_available() else "cpu"
            self._clip_model, self._clip_preprocess = clip.load(
                "ViT-B/32", device=self._device
            )
            self._clip_model.eval()
            print(f"[FrameSkipper] CLIP loaded on {self._device}")
        return self._clip_model, self._clip_preprocess

    def _encode(self, frame: np.ndarray) -> np.ndarray:
        """
        Encode frame BGR → CLIP embedding (512-dim float32).
        """
        import torch
        from PIL import Image

        model, preprocess = self._get_clip()

        # BGR → RGB → PIL → CLIP preprocess
        rgb = frame[:, :, ::-1]
        pil_img = Image.fromarray(rgb.astype(np.uint8))
        img_tensor = preprocess(pil_img).unsqueeze(0).to(self._device)

        with torch.no_grad():
            embedding = model.encode_image(img_tensor)
            embedding = embedding.cpu().numpy().astype(np.float32).squeeze()

        return embedding