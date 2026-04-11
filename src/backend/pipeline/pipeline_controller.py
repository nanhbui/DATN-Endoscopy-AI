"""pipeline_controller.py — GStreamer pipeline state machine.

Architecture (SYSTEM_REQUIREMENTS §2):
  GStreamer (filesrc ! decodebin ! videoconvert ! appsink)
    → frame extracted per YOLO inference
    → detection event pushed to asyncio.Queue
    → FastAPI WS server reads queue and relays to FE

GstPython (gi.repository.Gst) is used when available.
Falls back to OpenCV + YOLO for CPU-only / dev environments.

States (§3):
  IDLE → PLAYING → PAUSED_WAITING_INPUT → PROCESSING_LLM → EOS_SUMMARY
"""

from __future__ import annotations

import asyncio
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Optional

import cv2
import numpy as np

# ── GstPython (optional) ────────────────────────────────────────────────────
try:
    import gi
    gi.require_version("Gst", "1.0")
    from gi.repository import Gst, GLib
    Gst.init(None)
    GST_AVAILABLE = True
except Exception:
    GST_AVAILABLE = False

# ── YOLOv8 (optional) ───────────────────────────────────────────────────────
try:
    from ultralytics import YOLO as _YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False

# ── Project imports ─────────────────────────────────────────────────────────
from smart_ignore_memory import SmartIgnoreMemory   # same package

# ── Default YOLO model path ──────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[3]

# daday.pt — YOLOv8 trained on Vietnamese gastroscopy (stomach only)
# Classes: Viem da day HP am | Viem da day HP duong | Ung thu da day
DEFAULT_MODEL = _REPO_ROOT / "sample_code/endocv_2024/model_yolo/daday.pt"

# Fallback to generic model if daday.pt not found
if not DEFAULT_MODEL.exists():
    DEFAULT_MODEL = _REPO_ROOT / "yolov8n.pt"

CONFIDENCE_THRESHOLD = 0.50   # higher threshold for medical use


# ── Pipeline States ──────────────────────────────────────────────────────────

class PipelineState(str, Enum):
    IDLE = "IDLE"
    PLAYING = "PLAYING"
    PAUSED_WAITING_INPUT = "PAUSED_WAITING_INPUT"
    PROCESSING_LLM = "PROCESSING_LLM"
    EOS_SUMMARY = "EOS_SUMMARY"


# ── Event types sent to WS server ────────────────────────────────────────────

def _detection_event(frame_index: int, timestamp_ms: int, location: str,
                     label: str, confidence: float, bbox: list[float],
                     frame_b64: Optional[str] = None) -> dict:
    """Build DETECTION_FOUND payload (§5.1)."""
    return {
        "event": "DETECTION_FOUND",
        "data": {
            "frame_index": frame_index,
            "timestamp_ms": timestamp_ms,
            "location": location,
            "lesion": {"label": label, "confidence": confidence, "bbox": bbox},
            "frame_b64": frame_b64,  # cropped thumbnail (base64 PNG), may be None
        },
    }


def _eos_event(confirmed_detections: list[dict]) -> dict:
    """Build VIDEO_FINISHED payload (§6)."""
    return {"event": "VIDEO_FINISHED", "data": {"detections": confirmed_detections}}


def _state_event(state: PipelineState) -> dict:
    return {"event": "STATE_CHANGE", "data": {"state": state.value}}


# ── PipelineController ────────────────────────────────────────────────────────

class PipelineController:
    """Manages GStreamer (or OpenCV fallback) pipeline for one analysis session.

    After construction call ``start(video_path)`` to begin.
    Read events from ``events`` (asyncio.Queue).
    Send user actions via ``send_action(action, payload)``.
    """

    def __init__(self, video_id: str, model_path: Path = DEFAULT_MODEL) -> None:
        self.video_id = video_id
        self._model_path = model_path
        self._model = None

        # Asyncio event queue consumed by the WS handler
        self.events: asyncio.Queue[dict] = asyncio.Queue()

        # State machine
        self._state = PipelineState.IDLE
        self._play_event = threading.Event()   # set = playing, clear = paused
        self._stop_event = threading.Event()   # set = abort loop

        # Confirmed detections (user did NOT click Ignore)
        self._confirmed: list[dict] = []

        # Current pending detection (while PAUSED_WAITING_INPUT)
        self._pending: Optional[dict] = None

        # Smart Ignore memory
        self._memory = SmartIgnoreMemory(video_id)

        # Background processing thread
        self._thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ── Public API ────────────────────────────────────────────────────────

    def start(self, video_path: Path) -> None:
        """Launch pipeline processing in a background thread."""
        if self._thread and self._thread.is_alive():
            return
        self._loop = asyncio.get_event_loop()
        self._stop_event.clear()
        self._play_event.set()   # start playing immediately
        self._thread = threading.Thread(
            target=self._run_pipeline,
            args=(video_path,),
            daemon=True,
        )
        self._thread.start()

    def send_action(self, action: str, payload: dict | None = None) -> None:
        """Handle user action from FE (ACTION_IGNORE, ACTION_EXPLAIN, ACTION_RESUME)."""
        if action == "ACTION_IGNORE" and self._pending:
            det = self._pending
            self._memory.add(
                frame_index=det["frame_index"],
                bbox=det["lesion"]["bbox"],
                label=det["lesion"]["label"],
            )
            self._pending = None
            self._resume()
        elif action == "ACTION_EXPLAIN":
            self._set_state(PipelineState.PROCESSING_LLM)
            # LLM call is handled by the WS server; pipeline stays paused.
        elif action == "ACTION_RESUME":
            self._pending = None
            self._resume()

    def stop(self) -> None:
        """Abort processing."""
        self._stop_event.set()
        self._play_event.set()  # unblock thread if paused

    # ── Internal helpers ─────────────────────────────────────────────────

    def _set_state(self, state: PipelineState) -> None:
        self._state = state
        self._push_event(_state_event(state))

    def _resume(self) -> None:
        self._set_state(PipelineState.PLAYING)
        self._play_event.set()

    def _push_event(self, evt: dict) -> None:
        """Thread-safe: schedule queue.put_nowait on the asyncio event loop."""
        if self._loop:
            self._loop.call_soon_threadsafe(self.events.put_nowait, evt)

    # ── Pipeline runners ─────────────────────────────────────────────────

    def _run_pipeline(self, video_path: Path) -> None:
        """Choose GstPython or OpenCV depending on availability."""
        self._set_state(PipelineState.PLAYING)
        if GST_AVAILABLE:
            self._run_gstreamer(video_path)
        else:
            self._run_opencv_fallback(video_path)
        # EOS
        self._set_state(PipelineState.EOS_SUMMARY)
        self._push_event(_eos_event(self._confirmed))

    # ── GStreamer path ─────────────────────────────────────────────────────

    def _run_gstreamer(self, video_path: Path) -> None:
        """GstPython pipeline: filesrc → decodebin → videoconvert → appsink."""
        pipeline_str = (
            f'filesrc location="{video_path}" ! decodebin ! '
            "videoconvert ! video/x-raw,format=BGR ! appsink name=sink "
            "emit-signals=true max-buffers=1 drop=true"
        )
        pipeline = Gst.parse_launch(pipeline_str)
        sink = pipeline.get_by_name("sink")

        frame_index = 0
        frame_holder: list[Optional[np.ndarray]] = [None]

        def _on_new_sample(appsink):
            sample = appsink.emit("pull-sample")
            if not sample:
                return Gst.FlowReturn.ERROR
            buf = sample.get_buffer()
            caps = sample.get_caps()
            struct = caps.get_structure(0)
            w = struct.get_value("width")
            h = struct.get_value("height")
            ok, mapinfo = buf.map(Gst.MapFlags.READ)
            if ok:
                frame_holder[0] = np.frombuffer(mapinfo.data, dtype=np.uint8).reshape(h, w, 3).copy()
                buf.unmap(mapinfo)
            return Gst.FlowReturn.OK

        sink.connect("new-sample", _on_new_sample)
        pipeline.set_state(Gst.State.PLAYING)

        bus = pipeline.get_bus()
        fps = 30
        model = self._get_model()

        try:
            while not self._stop_event.is_set():
                # Wait if paused by detection
                self._play_event.wait()
                if self._stop_event.is_set():
                    break

                # Poll bus for EOS / error
                msg = bus.timed_pop_filtered(
                    0, Gst.MessageType.EOS | Gst.MessageType.ERROR
                )
                if msg:
                    break

                frame = frame_holder[0]
                if frame is not None:
                    frame_holder[0] = None
                    self._process_frame(frame, frame_index, model)
                    frame_index += 1

                time.sleep(1 / fps)
        finally:
            pipeline.set_state(Gst.State.NULL)

    # ── OpenCV fallback path ───────────────────────────────────────────────

    def _run_opencv_fallback(self, video_path: Path) -> None:
        """OpenCV VideoCapture pipeline (CPU fallback)."""
        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return

        fps = cap.get(cv2.CAP_PROP_FPS) or 30
        model = self._get_model()
        frame_index = 0

        try:
            while not self._stop_event.is_set():
                # Pause point: block here until _play_event is set
                self._play_event.wait()
                if self._stop_event.is_set():
                    break

                ret, frame = cap.read()
                if not ret:
                    break

                self._process_frame(frame, frame_index, model)
                frame_index += 1
                time.sleep(1 / fps)
        finally:
            cap.release()

    # ── Per-frame detection ────────────────────────────────────────────────

    def _process_frame(self, frame: np.ndarray, frame_index: int, model) -> None:
        """Run YOLO on one frame; push DETECTION_FOUND + pause if new lesion."""
        if model is None:
            return

        timestamp_ms = int(frame_index * 1000 / 30)

        try:
            results = model(frame, conf=CONFIDENCE_THRESHOLD, verbose=False)
        except Exception:
            return

        for result in results:
            if result.boxes is None:
                continue
            for box in result.boxes:
                conf = float(box.conf[0])
                cls_id = int(box.cls[0])
                label = (model.names or {}).get(cls_id, f"class_{cls_id}")
                xyxy = box.xyxy[0].tolist()   # [x1, y1, x2, y2]

                # Smart Ignore check (§4)
                if self._memory.is_ignored(frame_index, xyxy):
                    continue

                # New, unignored lesion → pause pipeline
                location = self._infer_location(xyxy, frame.shape)
                thumbnail_b64 = self._crop_b64(frame, xyxy)

                evt = _detection_event(
                    frame_index=frame_index,
                    timestamp_ms=timestamp_ms,
                    location=location,
                    label=label,
                    confidence=round(conf, 4),
                    bbox=xyxy,
                    frame_b64=thumbnail_b64,
                )
                self._pending = evt["data"]
                self._play_event.clear()   # ← pause pipeline thread
                self._set_state(PipelineState.PAUSED_WAITING_INPUT)
                self._push_event(evt)
                return   # one detection per frame is enough

    # ── Utilities ─────────────────────────────────────────────────────────

    def _get_model(self):
        """Lazy-load YOLO model once per controller instance."""
        if self._model is not None:
            return self._model
        if not YOLO_AVAILABLE:
            return None
        try:
            self._model = _YOLO(str(self._model_path))
            return self._model
        except Exception as exc:
            print(f"[WARN] YOLO load failed ({exc}), no inference.")
            return None

    @staticmethod
    def _infer_location(bbox: list[float], frame_shape: tuple) -> str:
        """Heuristic anatomical location within the stomach based on bbox position.

        The gastroscopy video convention (from sample_code/endocv_2024):
        - Upper region  → Thân vị (corpus/body)
        - Middle region → Hang vị (antrum)
        - Lower region  → Môn vị (pylorus)
        """
        h, w = frame_shape[:2]
        cy = (bbox[1] + bbox[3]) / 2 / h
        if cy < 0.33:
            return "Thân vị"
        elif cy < 0.66:
            return "Hang vị"
        return "Môn vị"

    @staticmethod
    def _crop_b64(frame: np.ndarray, bbox: list[float]) -> Optional[str]:
        """Return base64-encoded PNG thumbnail of the detection region."""
        try:
            import base64
            x1, y1, x2, y2 = map(int, bbox)
            crop = frame[max(0, y1):y2, max(0, x1):x2]
            ok, buf = cv2.imencode(".png", crop)
            if ok:
                return base64.b64encode(buf.tobytes()).decode()
        except Exception:
            pass
        return None
