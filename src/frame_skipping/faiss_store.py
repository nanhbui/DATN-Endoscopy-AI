"""
NegativeFrameStore — Lưu trữ embedding của các frame bị bác sĩ đánh dấu "nhầm".

Luồng:
  1. Bác sĩ nói "nhầm rồi" → VoiceController gọi on_intent(BO_QUA)
  2. Frame hiện tại được encode bằng CLIP → embedding vector
  3. Vector được thêm vào FAISS index
  4. Các frame tiếp theo: tính cosine similarity → nếu vượt threshold → skip

Sử dụng CLIP ViT-B/32 để encode (512-dim), FAISS IndexFlatIP (inner product = cosine khi đã normalize).
"""

from __future__ import annotations

import numpy as np
from pathlib import Path
from typing import Optional


class NegativeFrameStore:
    """
    FAISS index lưu embedding của các false-positive frames.

    Args:
        dim:            Chiều của embedding vector (512 cho CLIP ViT-B/32)
        similarity_threshold: Ngưỡng cosine similarity để skip frame (0.0–1.0)
        index_path:     Đường dẫn lưu/load FAISS index (optional)
    """

    DIM = 512  # CLIP ViT-B/32 output dimension

    def __init__(
        self,
        dim: int = DIM,
        similarity_threshold: float = 0.85,
        index_path: Optional[str] = None,
    ):
        import faiss  # lazy import

        self.dim = dim
        self.similarity_threshold = similarity_threshold
        self.index_path = Path(index_path) if index_path else None

        # IndexFlatIP: inner product (= cosine similarity nếu vector đã L2-normalize)
        self.index = faiss.IndexFlatIP(dim)
        self._count = 0

        if self.index_path and self.index_path.exists():
            self.load(str(self.index_path))
            print(f"[FAISS] Đã load {self._count} negative frames từ {self.index_path}")
        else:
            print(f"[FAISS] Khởi tạo index mới (dim={dim}, threshold={similarity_threshold})")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def add(self, embedding: np.ndarray) -> int:
        """
        Thêm một embedding vào store.

        Args:
            embedding: numpy array shape (dim,) hoặc (1, dim), dtype float32

        Returns:
            Tổng số negative frames hiện có
        """
        vec = self._prepare(embedding)
        self.index.add(vec)
        self._count += 1
        if self.index_path:
            self.save(str(self.index_path))
        return self._count

    def should_skip(self, embedding: np.ndarray) -> tuple[bool, float]:
        """
        Kiểm tra frame có nên bị skip không.

        Returns:
            (should_skip, max_similarity)
            should_skip = True nếu frame giống một negative frame đã lưu
        """
        if self._count == 0:
            return False, 0.0

        vec = self._prepare(embedding)
        distances, _ = self.index.search(vec, k=1)
        max_sim = float(distances[0][0])
        return max_sim >= self.similarity_threshold, max_sim

    @property
    def count(self) -> int:
        return self._count

    def save(self, path: str):
        import faiss
        faiss.write_index(self.index, path)

    def load(self, path: str):
        import faiss
        self.index = faiss.read_index(path)
        self._count = self.index.ntotal

    def reset(self):
        import faiss
        self.index = faiss.IndexFlatIP(self.dim)
        self._count = 0
        print("[FAISS] Đã xóa toàn bộ negative frames.")

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _prepare(embedding: np.ndarray) -> np.ndarray:
        """Chuẩn hóa về shape (1, dim) float32 và L2-normalize."""
        vec = np.array(embedding, dtype=np.float32).reshape(1, -1)
        norm = np.linalg.norm(vec, axis=1, keepdims=True)
        norm = np.where(norm == 0, 1.0, norm)
        return vec / norm