"""smart-ignore-memory.py — Smart Ignore persistence layer.

Implements the "Smart Ignore" logic from SYSTEM_REQUIREMENTS §4:
  1. Frame-drift check: abs(current_frame - ignored_frame) <= ALLOWED_FRAME_DRIFT
  2. IoU check: IoU(current_bbox, ignored_bbox) > IoU_THRESHOLD

Persists per-video ignored detections to a JSON file so the state survives
across sessions (e.g. if the pipeline is restarted mid-video).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

# ── Constants (match SYSTEM_REQUIREMENTS §4) ───────────────────────────────

ALLOWED_FRAME_DRIFT: int = 15   # frames
IOU_THRESHOLD: float = 0.80
IGNORED_DB_DIR: Path = Path("data/ignored_sessions")


# ── IoU helper ─────────────────────────────────────────────────────────────

def _compute_iou(a: list[float], b: list[float]) -> float:
    """Return Intersection-over-Union for two [x_min, y_min, x_max, y_max] boxes."""
    ax1, ay1, ax2, ay2 = a
    bx1, by1, bx2, by2 = b

    inter_x1 = max(ax1, bx1)
    inter_y1 = max(ay1, by1)
    inter_x2 = min(ax2, bx2)
    inter_y2 = min(ay2, by2)

    inter_w = max(0.0, inter_x2 - inter_x1)
    inter_h = max(0.0, inter_y2 - inter_y1)
    intersection = inter_w * inter_h

    area_a = max(0.0, ax2 - ax1) * max(0.0, ay2 - ay1)
    area_b = max(0.0, bx2 - bx1) * max(0.0, by2 - by1)
    union = area_a + area_b - intersection

    return intersection / union if union > 0 else 0.0


# ── SmartIgnoreMemory ────────────────────────────────────────────────────────

class SmartIgnoreMemory:
    """Per-video memory of ignored detections.

    Usage::

        mem = SmartIgnoreMemory(video_id="endoscopy_001")
        if not mem.is_ignored(frame_index=435, bbox=[100, 150, 300, 350]):
            # pause pipeline and show UI
        mem.add(frame_index=435, bbox=[100, 150, 300, 350], label="Ulcer")
    """

    def __init__(self, video_id: str, db_dir: Optional[Path] = None) -> None:
        self.video_id = video_id
        self._db_path = (db_dir or IGNORED_DB_DIR) / f"{video_id}_metadata.json"
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._records: list[dict] = self._load()

    # ── public API ────────────────────────────────────────────────────────

    def is_ignored(self, frame_index: int, bbox: list[float]) -> bool:
        """Return True if this detection matches an ignored record (should NOT pause)."""
        for rec in self._records:
            frame_close = abs(frame_index - rec["frame_index"]) <= ALLOWED_FRAME_DRIFT
            iou_match = _compute_iou(bbox, rec["bbox"]) >= IOU_THRESHOLD
            if frame_close and iou_match:
                return True
        return False

    def add(self, frame_index: int, bbox: list[float], label: str) -> None:
        """Record a user-ignored detection and persist to disk."""
        entry = {"frame_index": frame_index, "bbox": bbox, "label": label}
        self._records.append(entry)
        self._save()

    def clear(self) -> None:
        """Clear all ignored detections for this video."""
        self._records = []
        self._save()

    def all_records(self) -> list[dict]:
        return list(self._records)

    # ── persistence ───────────────────────────────────────────────────────

    def _load(self) -> list[dict]:
        if not self._db_path.exists():
            return []
        try:
            data = json.loads(self._db_path.read_text())
            return data.get("ignored_detections", [])
        except (json.JSONDecodeError, KeyError):
            return []

    def _save(self) -> None:
        payload = {
            "video_id": self.video_id,
            "ignored_detections": self._records,
        }
        self._db_path.write_text(json.dumps(payload, indent=2))
