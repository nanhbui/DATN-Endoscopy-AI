from __future__ import annotations

import asyncio
import json
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Optional

import os as _os
import multiprocessing as _mp

# ── Subprocess spawn context (avoids CUDA fork issues) ────────────────────────
_mp_ctx = _mp.get_context("spawn")

# ── GstShark profiling (optional) ────────────────────────────────────────────
# Set ENABLE_GSTSHARK_PROFILING=true and GSTSHARK_PLUGIN_PATH in .env to enable.
# GstShark tracers write CSV logs to GSTSHARK_LOG_DIR (default: /tmp/gst-shark/).
_GSTSHARK_ENABLED = _os.environ.get("ENABLE_GSTSHARK_PROFILING", "false").lower() == "true"
_GSTSHARK_PLUGIN_PATH = _os.environ.get(
    "GSTSHARK_PLUGIN_PATH",
    str(Path.home() / "DATN_ver0/gst-shark-install/lib/gstreamer-1.0"),
)
_GSTSHARK_LOG_DIR = _os.environ.get("GSTSHARK_LOG_DIR", "/tmp/gst-shark")
# Tracers to activate — framerate, proctime, interlatency, queuelevel, cpuusage
_GSTSHARK_TRACERS = _os.environ.get("GSTSHARK_TRACERS", "framerate;proctime;interlatency")

# ── Default YOLO model path ──────────────────────────────────────────────────
_REPO_ROOT = Path(__file__).resolve().parents[3]

_env_model = _os.environ.get("ENDOSCOPY_MODEL")
if _env_model and Path(_env_model).exists():
    DEFAULT_MODEL = Path(_env_model)
else:
    DEFAULT_MODEL = _REPO_ROOT / "sample_code/endocv_2024/model_yolo/daday.pt"
    if not DEFAULT_MODEL.exists():
        DEFAULT_MODEL = _REPO_ROOT / "yolov8n.pt"

CONFIDENCE_THRESHOLD = 0.65   # higher threshold reduces false positives

# Skip this many frames at the start of every video (scope insertion / title cards)
SKIP_INITIAL_FRAMES = 90   # ≈ 3 s at 30 fps

# Process every Nth frame — set higher on CPU to avoid multi-hour wait
# GPU server: 3 (fast)  |  Local CPU: 30 (1 frame/sec at 30fps)
import os as _os_frame
FRAME_STEP = int(_os_frame.environ.get("FRAME_STEP", "3"))


# ── Pipeline States ──────────────────────────────────────────────────────────

class PipelineState(str, Enum):
    IDLE = "IDLE"
    PLAYING = "PLAYING"
    PAUSED_WAITING_INPUT = "PAUSED_WAITING_INPUT"
    PROCESSING_LLM = "PROCESSING_LLM"
    EOS_SUMMARY = "EOS_SUMMARY"


# ── Event builders ────────────────────────────────────────────────────────────

def _detection_event(frame_index: int, timestamp_ms: int, location: str,
                     label: str, confidence: float, bbox: list[float],
                     frame_b64: Optional[str] = None) -> dict:
    return {
        "event": "DETECTION_FOUND",
        "data": {
            "frame_index": frame_index,
            "timestamp_ms": timestamp_ms,
            "location": location,
            "lesion": {"label": label, "confidence": confidence, "bbox": bbox},
            "frame_b64": frame_b64,
        },
    }

def _eos_event(confirmed_detections: list[dict]) -> dict:
    return {"event": "VIDEO_FINISHED", "data": {"detections": confirmed_detections}}

def _state_event(state: PipelineState) -> dict:
    return {"event": "STATE_CHANGE", "data": {"state": state.value}}


# ── Subprocess worker (GStreamer + YOLO, no asyncio) ──────────────────────────

def _pipeline_worker(video_path_str: str, model_path_str: str, conf: float,
                     result_q: "_mp.Queue[dict]", cmd_q: "_mp.Queue[str]",
                     gstshark_enabled: bool = False,
                     gstshark_plugin_path: str = "",
                     gstshark_log_dir: str = "/tmp/gst-shark",
                     gstshark_tracers: str = "framerate;proctime;interlatency") -> None:
    """Runs in isolated subprocess: GStreamer decode + YOLO inference.

    Sends detection/state events to result_q.
    Receives commands from cmd_q: STOP | RESUME | IGNORE:<fi>:<json>
    """
    import numpy as np

    # ── GstShark env injection (must happen before gi/Gst import) ────────────
    if gstshark_enabled and gstshark_plugin_path:
        import pathlib
        log_dir = pathlib.Path(gstshark_log_dir)
        log_dir.mkdir(parents=True, exist_ok=True)

        existing_plugin_path = _os.environ.get("GST_PLUGIN_PATH", "")
        _os.environ["GST_PLUGIN_PATH"] = (
            f"{gstshark_plugin_path}:{existing_plugin_path}".rstrip(":")
        )
        existing_ld = _os.environ.get("LD_LIBRARY_PATH", "")
        shark_lib = str(pathlib.Path(gstshark_plugin_path).parent)
        _os.environ["LD_LIBRARY_PATH"] = f"{shark_lib}:{existing_ld}".rstrip(":")
        _os.environ["GST_TRACERS"] = gstshark_tracers
        _os.environ["GST_DEBUG"] = "GST_TRACER:7"
        _os.environ["SHARK_FRAMERATE_LOGDIR"] = str(log_dir)
        _os.environ["SHARK_PROCTIME_LOGDIR"] = str(log_dir)
        _os.environ["SHARK_INTERLATENCY_LOGDIR"] = str(log_dir)
        print(f"[Worker] GstShark profiling ON → tracers={gstshark_tracers} log={log_dir}", flush=True)
    import cv2
    import base64
    import json as _json

    # ── YOLO load + GPU warm-up ───────────────────────────────────────────
    model = None
    model_names = {}
    try:
        import torch
        from ultralytics import YOLO
        model = YOLO(model_path_str)
        model_names = model.names or {}

        # Use FP16 on CUDA for ~2x faster inference; fall back to FP32 on CPU.
        if torch.cuda.is_available():
            model.half()
            print("[Worker] YOLO FP16 (CUDA)", flush=True)
        else:
            print("[Worker] YOLO FP32 (CPU)", flush=True)

        # Warm-up at YOLO input size (640px) to fully initialize CUDA kernels.
        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        model(dummy, verbose=False, conf=0.99)
        print("[Worker] YOLO warm-up done", flush=True)
    except Exception as exc:
        print(f"[Worker] YOLO load/warm-up failed: {exc}", flush=True)

    # ── GStreamer pipeline ────────────────────────────────────────────────
    try:
        import gi
        gi.require_version("Gst", "1.0")
        from gi.repository import Gst
        Gst.init(None)
    except Exception as exc:
        result_q.put({"event": "ERROR", "data": {"message": f"GStreamer unavailable: {exc}"}})
        result_q.put(_eos_event([]))
        return

    # Request BGR directly from GStreamer — eliminates all Python format detection.
    # videoscale down to YOLO input size (640px wide) before appsink saves YOLO prep time.
    # max-buffers=4 + drop=true: GStreamer drops stale frames instead of stalling when YOLO is busy.
    _SCALE   = "videoscale ! video/x-raw,width=640,pixel-aspect-ratio=1/1 ! videoconvert"
    _SINK_CAPS = "video/x-raw,format=BGR"
    _SINK_TAIL = f"appsink name=sink sync=false max-buffers=4 drop=true caps={_SINK_CAPS}"

    _src = video_path_str
    is_live = _src.startswith(("rtsp://", "rtp://", "rtmp://")) or _src.startswith("/dev/video")

    # Try NVIDIA hardware decoder first; fall back to software (avdec_h264).
    # nvh264dec offloads decoding to NVDEC engine — frees GPU cores for YOLO.
    def _has_nvdec() -> bool:
        try:
            _test = Gst.ElementFactory.make("nvh264dec", None)
            return _test is not None
        except Exception:
            return False

    _use_nvdec = _has_nvdec()
    _h264dec = "nvh264dec" if _use_nvdec else "avdec_h264"
    print(f"[Worker] H.264 decoder: {_h264dec}", flush=True)

    # Queue with leaky=downstream prevents GStreamer from stalling when appsink is busy.
    _QUEUE = "queue max-size-buffers=4 max-size-time=0 max-size-bytes=0 leaky=downstream"

    if _src.startswith(("rtsp://", "rtp://", "rtmp://")):
        pipeline_str = (
            f'rtspsrc location="{_src}" latency=200 ! '
            f"rtph264depay ! h264parse ! {_h264dec} ! {_QUEUE} ! {_SCALE} ! {_SINK_TAIL}"
        )
    elif _src.startswith("/dev/video"):
        pipeline_str = (
            f'v4l2src device="{_src}" ! {_QUEUE} ! {_SCALE} ! {_SINK_TAIL}'
        )
    else:
        is_live = False
        # decodebin handles any container/codec — more robust than hardcoded qtdemux+h264parse
        pipeline_str = (
            f'filesrc location="{_src}" ! decodebin ! {_QUEUE} ! {_SCALE} ! {_SINK_TAIL}'
        )

    # Live sources have no blank-frame header — skip the initial-frame filter
    _skip = 0 if is_live else SKIP_INITIAL_FRAMES
    gst_pipeline = Gst.parse_launch(pipeline_str)
    sink = gst_pipeline.get_by_name("sink")
    sink.set_property("emit-signals", False)
    gst_pipeline.set_state(Gst.State.PLAYING)
    bus = gst_pipeline.get_bus()
    print("[Worker] GStreamer PLAYING", flush=True)

    # ── Inline ignore memory (no import path issues in subprocess) ─────────
    _ignored: list[dict] = []

    def _iou(a: list, b: list) -> float:
        ix1 = max(a[0], b[0]); iy1 = max(a[1], b[1])
        ix2 = min(a[2], b[2]); iy2 = min(a[3], b[3])
        inter = max(0.0, ix2 - ix1) * max(0.0, iy2 - iy1)
        ua = (a[2]-a[0])*(a[3]-a[1]) + (b[2]-b[0])*(b[3]-b[1]) - inter
        return inter / ua if ua > 0 else 0.0

    def _is_ignored(fi: int, bbox: list) -> bool:
        return any(
            abs(ig["fi"] - fi) <= 15 and _iou(ig["bbox"], bbox) >= 0.8
            for ig in _ignored
        )

    def _infer_location(bbox: list, shape: tuple) -> str:
        cy = (bbox[1] + bbox[3]) / 2 / shape[0]
        if cy < 0.33:
            return "Thân vị"
        elif cy < 0.66:
            return "Hang vị"
        return "Môn vị"

    def _is_diagnostic_frame(frame: np.ndarray, fi: int) -> bool:
        """Return False for non-diagnostic frames: scope insertion, dark frames, text-only cards."""
        # Skip scope insertion / title cards at the very start
        if fi < _skip:
            return False

        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Endoscopy viewport is a bright circle on a black border.
        # If < 15 % of pixels are bright the scope is being inserted/withdrawn.
        bright_frac = float(np.sum(gray > 25)) / (h * w)
        if bright_frac < 0.15:
            return False

        # Center region must have some content (not completely dark center)
        cy, cx = h // 2, w // 2
        rh, rw = h // 6, w // 6
        center_mean = float(gray[cy - rh: cy + rh, cx - rw: cx + rw].mean())
        if center_mean < 18:
            return False

        # Skip near-uniform frames (low variance → washed-out / all-black / all-white)
        if float(gray.std()) < 12:
            return False

        return True

    def _crop_b64(frame: np.ndarray, bbox: list) -> Optional[str]:
        try:
            x1, y1, x2, y2 = map(int, bbox)
            crop = frame[max(0, y1):y2, max(0, x1):x2]
            # Limit thumbnail to 320px on longest side
            h, w = crop.shape[:2]
            if max(h, w) > 320:
                scale = 320 / max(h, w)
                crop = cv2.resize(crop, (int(w * scale), int(h * scale)))
            ok, buf = cv2.imencode(".jpg", crop, [cv2.IMWRITE_JPEG_QUALITY, 80])
            if ok:
                return base64.b64encode(buf.tobytes()).decode()
        except Exception:
            pass
        return None

    # ── Main loop ──────────────────────────────────────────────────────────
    confirmed: list[dict] = []
    frame_index = 0
    paused = False

    try:
        while True:
            # Drain command queue
            while True:
                try:
                    cmd = cmd_q.get_nowait()
                except Exception:
                    break
                if cmd == "STOP":
                    return
                elif cmd == "RESUME":
                    paused = False
                elif cmd.startswith("IGNORE:"):
                    parts = cmd.split(":", 2)
                    if len(parts) == 3:
                        fi = int(parts[1])
                        data = _json.loads(parts[2])
                        _ignored.append({"fi": fi, "bbox": data["bbox"]})
                    paused = False

            if paused:
                time.sleep(0.02)
                continue

            # Pull frame
            sample = sink.emit("try-pull-sample", Gst.SECOND)
            if sample is None:
                msg = bus.timed_pop_filtered(0, Gst.MessageType.EOS | Gst.MessageType.ERROR)
                if msg:
                    print(f"[Worker] Bus EOS/error: {msg.type}", flush=True)
                    break
                continue

            # GStreamer outputs BGR directly (negotiated via caps) — no conversion needed.
            buf = sample.get_buffer()
            caps = sample.get_caps()
            struct = caps.get_structure(0)
            w = struct.get_value("width")
            h = struct.get_value("height")
            ok, mapinfo = buf.map(Gst.MapFlags.READ)
            if not ok:
                continue
            raw = np.frombuffer(mapinfo.data, dtype=np.uint8).copy()
            buf.unmap(mapinfo)
            frame = raw.reshape(h, w, 3)  # already BGR

            # Use GStreamer PTS for accurate timestamp; fall back to frame counter
            pts = buf.pts
            timestamp_ms = int(pts / 1_000_000) if pts != Gst.CLOCK_TIME_NONE else int(frame_index * 1000 / 30)
            if model is not None and frame_index % FRAME_STEP == 0 and _is_diagnostic_frame(frame, frame_index):
                try:
                    results = model(frame, conf=conf, verbose=False)
                    for result in results:
                        if result.boxes is None or len(result.boxes) == 0:
                            continue
                        for box in result.boxes:
                            if box.conf is None or box.conf.shape[0] == 0:
                                continue
                            det_conf = float(box.conf[0])
                            cls_id = int(box.cls[0])
                            label = model_names.get(cls_id, f"class_{cls_id}")
                            xyxy = box.xyxy[0].tolist()

                            if _is_ignored(frame_index, xyxy):
                                continue

                            location = _infer_location(xyxy, frame.shape)
                            thumbnail_b64 = _crop_b64(frame, xyxy)
                            det_data = {
                                "frame_index": frame_index,
                                "timestamp_ms": timestamp_ms,
                                "location": location,
                                "lesion": {
                                    "label": label,
                                    "confidence": round(det_conf, 4),
                                    "bbox": xyxy,
                                },
                                "frame_b64": thumbnail_b64,
                            }
                            confirmed.append(det_data)
                            result_q.put({"event": "DETECTION_FOUND", "data": det_data})
                            paused = True
                            break   # one detection per frame
                        if paused:
                            break
                except Exception as exc:
                    print(f"[Worker] YOLO error frame {frame_index}: {exc}", flush=True)

            frame_index += 1

    except Exception as exc:
        import traceback
        print(f"[Worker] Fatal: {exc}", flush=True)
        traceback.print_exc()
    finally:
        gst_pipeline.set_state(Gst.State.NULL)
        print(f"[Worker] Done. {frame_index} frames, {len(confirmed)} detections.", flush=True)

    result_q.put(_eos_event(confirmed))


# ── PipelineController ────────────────────────────────────────────────────────

class PipelineController:
    """Manages GStreamer+YOLO subprocess for one analysis session.

    Subprocess isolation: GStreamer (GLib threads) + CUDA cannot coexist with
    uvloop/asyncio in the same process — subprocess avoids the deadlock.

    After construction call ``start(video_path)`` to begin.
    Read events from ``events`` (asyncio.Queue).
    Send user actions via ``send_action(action, payload)``.
    """

    def __init__(self, video_id: str, model_path: Path = DEFAULT_MODEL) -> None:
        self.video_id = video_id
        self._model_path = model_path

        # Asyncio event queue consumed by the WS handler
        self.events: asyncio.Queue[dict] = asyncio.Queue()

        # State
        self._state = PipelineState.IDLE
        self._pending: Optional[dict] = None
        self._confirmed: list[dict] = []

        # IPC queues and subprocess
        self._result_q: Optional["_mp.Queue[dict]"] = None
        self._cmd_q: Optional["_mp.Queue[str]"] = None
        self._proc: Optional[_mp.Process] = None
        self._bridge_thread: Optional[threading.Thread] = None
        self._loop: Optional[asyncio.AbstractEventLoop] = None

    # ── Public API ────────────────────────────────────────────────────────

    def set_loop(self, loop: asyncio.AbstractEventLoop) -> None:
        self._loop = loop

    def start(self, video_path: Path) -> None:
        """Spawn subprocess and start bridge thread."""
        if self._proc and self._proc.is_alive():
            return

        self._result_q = _mp_ctx.Queue()
        self._cmd_q = _mp_ctx.Queue()
        self._proc = _mp_ctx.Process(
            target=_pipeline_worker,
            args=(str(video_path), str(self._model_path), CONFIDENCE_THRESHOLD,
                  self._result_q, self._cmd_q,
                  _GSTSHARK_ENABLED, _GSTSHARK_PLUGIN_PATH,
                  _GSTSHARK_LOG_DIR, _GSTSHARK_TRACERS),
            daemon=True,
        )
        self._proc.start()
        self._set_state(PipelineState.PLAYING)

        self._bridge_thread = threading.Thread(
            target=self._bridge_loop, daemon=True
        )
        self._bridge_thread.start()

    def send_action(self, action: str, payload: dict | None = None) -> None:
        """Handle user action from FE."""
        if action == "ACTION_IGNORE" and self._pending:
            det = self._pending
            cmd = (
                f"IGNORE:{det['frame_index']}:"
                + json.dumps({"bbox": det["lesion"]["bbox"], "label": det["lesion"]["label"]})
            )
            if self._cmd_q:
                self._cmd_q.put(cmd)
            self._pending = None
        elif action == "ACTION_EXPLAIN":
            self._set_state(PipelineState.PROCESSING_LLM)
            # Pipeline stays paused in subprocess; WS server handles LLM streaming.
        elif action == "ACTION_RESUME":
            if self._cmd_q:
                self._cmd_q.put("RESUME")
            self._pending = None
            self._set_state(PipelineState.PLAYING)

    def stop(self) -> None:
        """Abort processing."""
        if self._cmd_q:
            try:
                self._cmd_q.put("STOP")
            except Exception:
                pass
        if self._proc and self._proc.is_alive():
            self._proc.terminate()

    # ── Internal ──────────────────────────────────────────────────────────

    def _set_state(self, state: PipelineState) -> None:
        self._state = state
        self._push_event(_state_event(state))

    def _push_event(self, evt: dict) -> None:
        if self._loop:
            try:
                self._loop.call_soon_threadsafe(self.events.put_nowait, evt)
            except RuntimeError:
                pass


    def _bridge_loop(self) -> None:
        """Read subprocess events and forward to asyncio queue."""
        while True:
            if self._proc and not self._proc.is_alive() and (
                self._result_q is None or self._result_q.empty()
            ):
                break
            try:
                evt = self._result_q.get(timeout=0.2)
            except Exception:
                continue

            # Track pending detection for ACTION_IGNORE / ACTION_EXPLAIN
            if evt["event"] == "DETECTION_FOUND":
                self._pending = evt["data"]
                self._state = PipelineState.PAUSED_WAITING_INPUT
                self._push_event(_state_event(PipelineState.PAUSED_WAITING_INPUT))

            # Track confirmed detections
            if evt["event"] == "VIDEO_FINISHED":
                self._confirmed = evt["data"].get("detections", [])
                self._set_state(PipelineState.EOS_SUMMARY)

            self._push_event(evt)

            if evt["event"] == "VIDEO_FINISHED":
                break
