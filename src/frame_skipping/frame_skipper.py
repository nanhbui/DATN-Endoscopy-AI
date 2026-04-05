"""frame_skipper.py – Smart‑Ignore implementation using FAISS.

The class maintains a FAISS ``IndexFlatIP`` (inner‑product) index that stores
embeddings of frames the doctor has marked as *false‑positive* (intent
``BO_QUA``).  The index is persisted to disk so that subsequent runs of the
pipeline can automatically skip those frames without re‑detecting them.

Typical workflow:
1. Obtain a visual embedding for a frame (e.g. CLIP, LLaVA‑Med vision encoder).
2. Call ``FrameSkipper.is_ignored(embedding)`` – if ``True`` the frame is
   ignored and the detection pipeline can continue without pausing.
3. When the doctor issues a ``BO_QUA`` command, call ``add`` to store the
   embedding together with optional metadata (reason, frame index, timestamp).

Persistence layout (under the same directory as this module):
- ``faiss_negative_patterns.index`` – binary FAISS index file.
- ``faiss_negative_patterns.meta.json`` – list of metadata dictionaries, one
  per stored vector, kept in the same order as the index.

The implementation is deliberately lightweight and has no external vision
dependencies – it only requires ``faiss`` (installed via ``faiss-cpu``) and
``numpy``.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import faiss
import numpy as np

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def _normalize_vectors(vectors: np.ndarray) -> np.ndarray:
    """L2‑normalize a batch of vectors for cosine similarity.

    FAISS ``IndexFlatIP`` computes the inner product.  When vectors are
    normalised to unit length, the inner product equals the cosine similarity
    in the range ``[-1, 1]``.
    """
    # Avoid division by zero – FAISS expects float32.
    norms = np.linalg.norm(vectors, axis=1, keepdims=True)
    norms[norms == 0] = 1.0
    return vectors / norms


class FrameSkipper:
    """Manage a persistent FAISS index of *negative* frame embeddings.

    Parameters
    ----------
    dim : int, optional
        Dimensionality of the embedding vectors.  Default ``512`` works for
        CLIP‑ViT‑B/32 and many LLaVA‑Med vision encoders.
    index_path : str | Path, optional
        Path to the FAISS index file.  If the file does not exist a new index
        will be created.
    meta_path : str | Path, optional
        Path to a JSON file storing optional metadata for each vector.  The
        metadata list is kept in the same order as the vectors in the index.
    similarity_threshold : float, optional
        Cosine similarity threshold above which a query is considered a match.
        The default ``0.85`` follows the requirement in ``SYSTEM_REQUIREMENTS``.
    """

    def __init__(
        self,
        dim: int = 512,
        index_path: str | Path = "faiss_negative_patterns.index",
        meta_path: str | Path = "faiss_negative_patterns.meta.json",
        similarity_threshold: float = 0.85,
    ) -> None:
        self.dim = dim
        self.index_path = Path(index_path)
        self.meta_path = Path(meta_path)
        self.threshold = similarity_threshold

        # Load or create the FAISS index.
        if self.index_path.exists():
            self.index = faiss.read_index(str(self.index_path))
        else:
            self.index = faiss.IndexFlatIP(self.dim)
            # Save an empty index immediately so that the file exists.
            faiss.write_index(self.index, str(self.index_path))

        # Load metadata if present.
        if self.meta_path.exists():
            try:
                with open(self.meta_path, "r", encoding="utf-8") as f:
                    self.metadata: List[Dict[str, Any]] = json.load(f)
            except Exception:
                self.metadata = []
        else:
            self.metadata = []

    # ---------------------------------------------------------------------
    # Persistence helpers
    # ---------------------------------------------------------------------
    def _save(self) -> None:
        """Write the index and metadata to disk.

        FAISS writes the index in a binary format; metadata is stored as JSON.
        """
        # Ensure directory exists.
        self.index_path.parent.mkdir(parents=True, exist_ok=True)
        faiss.write_index(self.index, str(self.index_path))
        with open(self.meta_path, "w", encoding="utf-8") as f:
            json.dump(self.metadata, f, ensure_ascii=False, indent=2)

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------
    def add(self, embedding: np.ndarray, metadata: Optional[Dict[str, Any]] = None) -> None:
        """Add a new negative‑pattern embedding to the index.

        ``embedding`` must be a 1‑D ``float32`` array of length ``self.dim``.
        ``metadata`` is optional auxiliary information (e.g. ``{"reason": "bột trắng", "frame_idx": 123}``).
        """
        if embedding.ndim != 1 or embedding.shape[0] != self.dim:
            raise ValueError(f"Embedding must be 1‑D of size {self.dim}")
        # Normalise to unit length for cosine similarity.
        vec = _normalize_vectors(embedding[np.newaxis, :])
        self.index.add(vec)
        self.metadata.append(metadata or {})
        self._save()

    def is_ignored(self, embedding: np.ndarray, *, threshold: Optional[float] = None) -> bool:
        """Check whether ``embedding`` is similar to any stored negative pattern.

        Returns ``True`` if the maximum cosine similarity exceeds ``threshold``
        (defaulting to ``self.threshold``).  An empty index always returns
        ``False``.
        """
        if self.index.ntotal == 0:
            return False
        if embedding.ndim != 1 or embedding.shape[0] != self.dim:
            raise ValueError(f"Embedding must be 1‑D of size {self.dim}")
        query = _normalize_vectors(embedding[np.newaxis, :])
        distances, _ = self.index.search(query, k=1)  # inner product = cosine
        max_sim = float(distances[0][0])  # distance is similarity because of IP
        th = threshold if threshold is not None else self.threshold
        return max_sim >= th

    # ---------------------------------------------------------------------
    # Convenience utilities
    # ---------------------------------------------------------------------
    def list_patterns(self) -> List[Dict[str, Any]]:
        """Return the stored metadata for all negative patterns.

        The order matches the vectors in the FAISS index.
        """
        return self.metadata.copy()

    def clear(self) -> None:
        """Remove all stored patterns and reset the index.
        """
        self.index.reset()
        self.metadata = []
        self._save()

# ---------------------------------------------------------------------------
# Example usage (executed only when run as a script, not on import).
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Simple demo – generate random embeddings, add a few, then query.
    skipper = FrameSkipper()
    rng = np.random.default_rng(42)
    for i in range(3):
        emb = rng.random(512, dtype="float32")
        skipper.add(emb, {"reason": f"demo-{i}", "frame_idx": i})
    test_emb = rng.random(512, dtype="float32")
    print("Is ignored?", skipper.is_ignored(test_emb))
    print("Stored patterns:", skipper.list_patterns())
"""
