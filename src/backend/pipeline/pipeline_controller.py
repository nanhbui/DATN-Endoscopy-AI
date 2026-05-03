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
    # Prefer the latest full-scope model; fall back to legacy then generic
    DEFAULT_MODEL = _REPO_ROOT / "models" / "best_train6.pt"
    if not DEFAULT_MODEL.exists():
        DEFAULT_MODEL = _REPO_ROOT / "sample_code/endocv_2024/model_yolo/daday.pt"
    if not DEFAULT_MODEL.exists():
        DEFAULT_MODEL = _REPO_ROOT / "yolov8n.pt"

CONFIDENCE_THRESHOLD = float(_os.environ.get("ENDOSCOPY_CONF", "0.5"))

# Maximum bbox area as fraction of viewport. Only used to drop EGREGIOUS whole-frame
# detections (essentially "this whole image matches the disease"). Default 0.95 keeps
# almost every model output — even relatively wide bboxes are useful information for
# the doctor. Tighten via env var ENDOSCOPY_MAX_BBOX_RATIO if too noisy.
MAX_BBOX_AREA_RATIO = float(_os.environ.get("ENDOSCOPY_MAX_BBOX_RATIO", "0.95"))

# ── StrongSORT Re-ID weights ─────────────────────────────────────────────────
_DEFAULT_REID = _REPO_ROOT / "sample_code/endocv_2024/osnet_x0_25_endocv_30.pt"
REID_WEIGHTS = Path(_os.environ.get("ENDOSCOPY_REID", str(_DEFAULT_REID)))

# Endoscopy viewport width (pixels) — the circular scope view occupies the left
# portion of the 1920-wide frame; the right side is the patient info/thumbnail panel.
# Model was trained on viewport-only crops so we slice before inference.
# x-coords from YOLO on the crop are still valid in full-frame space (origin unchanged).
VIEWPORT_W = 1300  # empirical for 1920×1080; override via env ENDOSCOPY_VIEWPORT_W
VIEWPORT_W = int(_os.environ.get("ENDOSCOPY_VIEWPORT_W", str(VIEWPORT_W)))

# Skip this many frames at the start of every video (scope insertion / title cards).
# 90 frames ≈ 3 s at 30 fps — enough to bypass the title screens of clinical
# recordings without dropping legitimate early detections.
SKIP_INITIAL_FRAMES = int(_os.environ.get("ENDOSCOPY_SKIP_FRAMES", "90"))

# Process every Nth frame — 1 matches sample_code behaviour (best accuracy)
# Set FRAME_STEP=3 in .env on CPU-only servers to avoid multi-hour waits
FRAME_STEP = int(_os.environ.get("FRAME_STEP", "1"))


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
                     reid_weights_str: str = "",
                     gstshark_enabled: bool = False,
                     gstshark_plugin_path: str = "",
                     gstshark_log_dir: str = "/tmp/gst-shark",
                     gstshark_tracers: str = "framerate;proctime;interlatency") -> None:
    """Runs in isolated subprocess: GStreamer decode + YOLO inference + StrongSORT tracking.

    Sends detection/state events to result_q.
    Receives commands from cmd_q: STOP | RESUME | IGNORE:<fi>:<json>
    """
    import numpy as np
    import re as _re

    # Map underscored ASCII back to common Vietnamese diacritic forms — used as a
    # fallback when labels.txt is missing so the doctor never sees raw class names
    # like "3_Viem_da_day_HP_am" in the UI.
    _ASCII_TO_DIACRITIC = {
        "Viem_thuc_quan": "Viêm thực quản",
        "Viem_da_day_HP_am": "Viêm dạ dày HP",
        "Viem_da_day_HP": "Viêm dạ dày HP",
        "Ung_thu_thuc_quan": "Ung thư thực quản",
        "Ung_thu_da_day": "Ung thư dạ dày",
        "Loet_HTT": "Loét hoành tá tràng",
        "Loet_hoanh_ta_trang": "Loét hoành tá tràng",
    }
    _PREFIX_NUM = _re.compile(r"^\d+_")

    def _clean_label(raw: str) -> str:
        s = _PREFIX_NUM.sub("", raw)  # strip leading "N_"
        return _ASCII_TO_DIACRITIC.get(s, s.replace("_", " "))

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
        model.fuse()  # fuse Conv+BN layers → faster inference
        model_names = model.names or {}

        # Override numeric-prefixed class names with clean Vietnamese labels
        _labels_txt = _os.path.join(_os.path.dirname(model_path_str), "labels.txt")
        if _os.path.exists(_labels_txt):
            try:
                with open(_labels_txt, encoding="utf-8") as _lf:
                    _label_lines = [l.strip() for l in _lf if l.strip()]
                model_names = {i: _label_lines[i] for i in range(len(_label_lines)) if i in model_names}
                print(f"[Worker] Labels from labels.txt: {model_names}", flush=True)
            except Exception as _le:
                print(f"[Worker] Labels load failed: {_le}", flush=True)

        dummy = np.zeros((640, 640, 3), dtype=np.uint8)
        # Use FP32 by default to match sample-code accuracy (sample_code/endocv_2024
        # uses fp16=False). FP16 can subtly change feature values and cause the
        # model to pick a different region as the highest-confidence detection.
        # Set ENDOSCOPY_FP16=true to force FP16 for inference speed at potential
        # accuracy cost on this checkpoint.
        _use_fp16 = (_os.environ.get("ENDOSCOPY_FP16", "false").lower() == "true"
                     and torch.cuda.is_available())
        if _use_fp16:
            try:
                model.half()
                model(dummy, verbose=False, conf=0.99)
                print("[Worker] YOLO FP16 (CUDA) — speed mode", flush=True)
            except Exception as fp16_exc:
                print(f"[Worker] FP16 failed ({fp16_exc}), falling back to FP32", flush=True)
                model.float()
                model(dummy, verbose=False, conf=0.99)
                print("[Worker] YOLO FP32 (CUDA fallback)", flush=True)
        else:
            if torch.cuda.is_available():
                model.float()
            model(dummy, verbose=False, conf=0.99)
            dev = "CUDA" if torch.cuda.is_available() else "CPU"
            print(f"[Worker] YOLO FP32 ({dev}) — accuracy mode (matches sample_code)", flush=True)
        print("[Worker] YOLO warm-up done", flush=True)
    except Exception as exc:
        print(f"[Worker] YOLO load/warm-up failed: {exc}", flush=True)

    # ── StrongSORT tracker ────────────────────────────────────────────────
    tracker = None
    try:
        import torch as _torch
        from boxmot.trackers.strongsort.strongsort import StrongSort
        _reid_path = _os.path.join(_os.path.dirname(_os.path.abspath(__file__)), reid_weights_str) if reid_weights_str and not _os.path.isabs(reid_weights_str) else reid_weights_str
        if reid_weights_str and _os.path.exists(reid_weights_str):
            _device = _torch.device("cuda:0" if _torch.cuda.is_available() else "cpu")
            tracker = StrongSort(
                reid_weights=_os.path.abspath(reid_weights_str),
                device=_device,
                half=_torch.cuda.is_available(),
                n_init=1,          # confirm track after 1 hit
                max_age=300,       # keep lost track alive for 300 frames (scope can leave FOV)
                max_iou_dist=0.85, # relaxed vs original 0.7; scope moves but different lesions rarely overlap
                max_cos_dist=0.4,  # relaxed: appearance changes under scope lighting
            )
            print(f"[Worker] StrongSORT tracker ON ({_device})", flush=True)
        else:
            print(f"[Worker] ReID weights not found ({reid_weights_str}), tracker disabled", flush=True)
    except Exception as _te:
        print(f"[Worker] StrongSORT init failed: {_te} — falling back to no tracker", flush=True)

    # Spatial-temporal dedup: suppress same lesion area within a time window.
    # Track-ID-based dedup was fragile: max_age=300 causes the tracker to
    # re-associate returning lesions with old IDs, silently skipping them.
    _DEDUP_WINDOW_MS = int(_os.environ.get("DEDUP_WINDOW_MS", "10000"))  # 10 s
    _DEDUP_IOU = 0.25  # ≥25% overlap = same region
    _reported_history: list[dict] = []  # {ts_ms, bbox (1920×1080 norm), label}

    def _is_recently_reported(ts_ms: int, bbox: list, label: str) -> bool:
        for r in _reported_history:
            if ts_ms - r["ts_ms"] < _DEDUP_WINDOW_MS and r["label"] == label and _iou(r["bbox"], bbox) >= _DEDUP_IOU:
                return True
        return False

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

    # No format caps on appsink — BGR caps cause back-propagation into decodebin and fail.
    # Format conversion to BGR is done in Python after pulling the sample.
    _SCALE = "videoscale ! video/x-raw,width=640 ! videoconvert"
    # No drop=true: back-pressure ensures GStreamer doesn't race past the current frame.
    _SINK_TAIL = "appsink name=sink sync=false max-buffers=4"

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

    # Back-pressure queue: no leaky flag so GStreamer blocks when appsink is full.
    # This prevents GStreamer racing ahead to EOS while Python (YOLO/user input) is paused.
    _QUEUE = "queue max-size-buffers=4 max-size-time=0 max-size-bytes=0"

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
        # Detect codec via ffprobe to pick the right software decoder.
        # Avoids decodebin selecting hardware decoders (nvv4l2decoder) that output
        # NVMM GPU buffers — those cannot be read by buf.map() in Python.
        import subprocess as _sp
        _codec = "h264"  # default
        try:
            _probe = _sp.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0",
                 "-show_entries", "stream=codec_name", "-of", "default=noprint_wrappers=1:nokey=1",
                 _src],
                capture_output=True, text=True, timeout=10,
            )
            _codec = _probe.stdout.strip() or "h264"
        except Exception as _e:
            print(f"[Worker] ffprobe failed ({_e}), assuming h264", flush=True)

        print(f"[Worker] Detected codec: {_codec}", flush=True)
        if _codec == "h264":
            pipeline_str = (
                f'filesrc location="{_src}" ! qtdemux ! h264parse ! avdec_h264 ! videoconvert ! {_QUEUE} ! {_SINK_TAIL}'
            )
        elif _codec == "hevc":
            pipeline_str = (
                f'filesrc location="{_src}" ! qtdemux ! h265parse ! avdec_h265 ! videoconvert ! {_QUEUE} ! {_SINK_TAIL}'
            )
        elif _codec == "mpeg4":
            # qtdemux + explicit software decoder — avoids NVMM buffers on GPU servers
            pipeline_str = (
                f'filesrc location="{_src}" ! qtdemux ! avdec_mpeg4 ! videoconvert ! {_QUEUE} ! {_SINK_TAIL}'
            )
        else:
            pipeline_str = (
                f'filesrc location="{_src}" ! decodebin ! videoconvert ! {_QUEUE} ! {_SINK_TAIL}'
            )

    # Live sources have no blank-frame header — skip the initial-frame filter
    _skip = 0 if is_live else SKIP_INITIAL_FRAMES
    gst_pipeline = Gst.parse_launch(pipeline_str)
    sink = gst_pipeline.get_by_name("sink")
    sink.set_property("emit-signals", False)
    gst_pipeline.set_state(Gst.State.PLAYING)
    # Wait briefly for state transition so pads are fully negotiated before dumping
    gst_pipeline.get_state(Gst.SECOND)
    bus = gst_pipeline.get_bus()
    print("[Worker] GStreamer PLAYING", flush=True)

    # Dump pipeline topology using dot_data (no GST_DEBUG_DUMP_DOT_DIR env needed)
    _dot_dir = _os.environ.get("GST_DEBUG_DUMP_DOT_DIR", "/tmp/gst-dot")
    _os.makedirs(_dot_dir, exist_ok=True)
    try:
        _dot_data = Gst.debug_bin_to_dot_data(gst_pipeline, Gst.DebugGraphDetails.ALL)
        _dot_path = _os.path.join(_dot_dir, "endoscopy_pipeline.dot")
        with open(_dot_path, "w") as _f:
            _f.write(_dot_data)
        print(f"[Worker] Pipeline DOT → {_dot_path}", flush=True)
    except Exception as _dot_exc:
        print(f"[Worker] DOT dump skipped: {_dot_exc}", flush=True)

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

    # ── Viewport detection ─────────────────────────────────────────────────
    # Cache: (x, y, w, h) of bright scope view; None until detected.
    _viewport_cache: list = [None]

    def _detect_viewport(frame: np.ndarray) -> tuple[int, int, int, int]:
        """Auto-detect scope viewport bounds (replaces hardcoded 1300/1920 crop).

        Works for both video formats:
        - Scope-only videos (e.g. endoscope2.mp4) where view is centered
        - Clinical recordings (e.g. NSDD) where view is on left + info panel on right

        Returns (x, y, w, h) of bounding rect around brightest contiguous region.
        Falls back to full frame if detection fails.
        """
        if _viewport_cache[0] is not None:
            return _viewport_cache[0]
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            _, mask = cv2.threshold(gray, 25, 255, cv2.THRESH_BINARY)
            # Morphology to merge close bright regions (handles scope vignette gradient)
            mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, np.ones((15, 15), np.uint8))
            contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            if not contours:
                vp = (0, 0, frame.shape[1], frame.shape[0])
            else:
                largest = max(contours, key=cv2.contourArea)
                x, y, w, h = cv2.boundingRect(largest)
                # Sanity: viewport should be > 30 % of frame area; otherwise fallback
                if w * h < frame.shape[0] * frame.shape[1] * 0.3:
                    vp = (0, 0, frame.shape[1], frame.shape[0])
                else:
                    vp = (x, y, w, h)
            _viewport_cache[0] = vp
            print(f"[Worker] Auto-detected viewport: x={vp[0]} y={vp[1]} w={vp[2]} h={vp[3]} "
                  f"(frame {frame.shape[1]}x{frame.shape[0]})", flush=True)
            return vp
        except Exception as _ve:
            print(f"[Worker] Viewport detection failed: {_ve} — using full frame", flush=True)
            vp = (0, 0, frame.shape[1], frame.shape[0])
            _viewport_cache[0] = vp
            return vp

    def _is_diagnostic_frame(frame: np.ndarray, fi: int) -> bool:
        """Return False for non-diagnostic frames: scope insertion, dark frames, text-only cards."""
        # Skip scope insertion / title cards at the very start
        if fi < _skip:
            return False

        # Evaluate brightness on auto-detected viewport (handles both scope-centered
        # and left-aligned-with-info-panel videos)
        _vx, _vy, _vw, _vh = _detect_viewport(frame)
        gray = cv2.cvtColor(frame[_vy:_vy+_vh, _vx:_vx+_vw], cv2.COLOR_BGR2GRAY)
        h, w = gray.shape

        # Endoscopy viewport is a bright circle on a black border (~60-70% fill).
        # If < 5% of viewport pixels are bright the scope is not yet inserted.
        bright_frac = float(np.sum(gray > 25)) / (h * w)
        if bright_frac < 0.05:
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
            # Crop to scope viewport for the thumbnail; translate full-frame bbox
            # coordinates into viewport-relative coords before drawing the rectangle.
            _vx, _vy, _vw, _vh = _detect_viewport(frame)
            out = frame[_vy:_vy+_vh, _vx:_vx+_vw].copy()
            x1, y1, x2, y2 = map(int, bbox)
            x1, y1 = x1 - _vx, y1 - _vy
            x2, y2 = x2 - _vx, y2 - _vy
            cv2.rectangle(out, (x1, y1), (x2, y2), (0, 255, 255), 3)
            # Scale to max 800px wide to keep payload reasonable
            scale = min(1.0, 800 / max(out.shape[1], out.shape[0]))
            if scale < 1.0:
                out = cv2.resize(out, (int(out.shape[1] * scale), int(out.shape[0] * scale)))
            ok, buf = cv2.imencode(".jpg", out, [cv2.IMWRITE_JPEG_QUALITY, 75])
            if ok:
                return base64.b64encode(buf.tobytes()).decode()
        except Exception:
            pass
        return None

    # ── Main loop ──────────────────────────────────────────────────────────
    confirmed: list[dict] = []
    frame_index = 0
    paused = False
    should_stop = False

    try:
        while True:
            # Drain command queue
            while True:
                try:
                    cmd = cmd_q.get_nowait()
                except Exception:
                    break
                if cmd == "STOP":
                    should_stop = True
                    break
                elif cmd == "RESUME":
                    paused = False
                elif cmd.startswith("IGNORE:"):
                    parts = cmd.split(":", 2)
                    if len(parts) == 3:
                        fi = int(parts[1])
                        data = _json.loads(parts[2])
                        _ignored.append({"fi": fi, "bbox": data["bbox"]})
                    paused = False

            if should_stop:
                break  # graceful — let finally + EOS event run

            if paused:
                time.sleep(0.02)
                continue

            # Pull frame
            sample = sink.emit("try-pull-sample", Gst.SECOND)
            if sample is None:
                msg = bus.timed_pop_filtered(0, Gst.MessageType.EOS | Gst.MessageType.ERROR)
                if msg:
                    if msg.type == Gst.MessageType.ERROR:
                        err, dbg = msg.parse_error()
                        print(f"[Worker] GStreamer ERROR: {err} | {dbg}", flush=True)
                    else:
                        print(f"[Worker] Bus EOS/error: {msg.type}", flush=True)
                    break
                continue

            buf = sample.get_buffer()
            caps = sample.get_caps()
            struct = caps.get_structure(0)
            w = struct.get_value("width")
            h = struct.get_value("height")
            fmt = struct.get_value("format") or "BGR"
            ok, mapinfo = buf.map(Gst.MapFlags.READ)
            if not ok:
                continue
            raw = np.frombuffer(mapinfo.data, dtype=np.uint8).copy()
            buf.unmap(mapinfo)
            # Skip invalid/non-video buffers (subtitle tracks, metadata, etc.)
            min_size = h * w
            if not w or not h or len(raw) < min_size:
                continue
            # Convert any YUV/planar format to BGR for YOLO
            try:
                if fmt == "NV12":
                    yuv = raw[:h * w * 3 // 2].reshape(h * 3 // 2, w)
                    frame = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_NV12)
                elif fmt == "I420":
                    yuv = raw[:h * w * 3 // 2].reshape(h * 3 // 2, w)
                    frame = cv2.cvtColor(yuv, cv2.COLOR_YUV2BGR_I420)
                elif fmt == "RGB":
                    frame = cv2.cvtColor(raw[:h * w * 3].reshape(h, w, 3), cv2.COLOR_RGB2BGR)
                else:
                    frame = raw[:h * w * 3].reshape(h, w, 3)  # assume BGR
            except Exception:
                continue

            # Use GStreamer PTS for accurate timestamp; fall back to frame counter
            pts = buf.pts
            timestamp_ms = int(pts / 1_000_000) if pts != Gst.CLOCK_TIME_NONE else int(frame_index * 1000 / 30)
            if frame_index == SKIP_INITIAL_FRAMES:
                print(f"[Worker] Frame shape: {frame.shape} (h×w×c)", flush=True)
            if model is not None and frame_index % FRAME_STEP == 0 and _is_diagnostic_frame(frame, frame_index):
                try:
                    # Run inference on FULL frame (matches sample-code behaviour
                    # endocv_2024/tracking_yolov8_strongsort.py at line 192) — cropping
                    # to viewport changes YOLO's letterbox padding and can suppress
                    # detections the model would otherwise return on the full frame.
                    # The auto-detected viewport is used only for filtering detections
                    # whose centres fall outside the scope view (e.g. info-panel FPs).
                    _vx, _vy, _vfw, _vfh = _detect_viewport(frame)
                    _fh, _fw = frame.shape[:2]

                    results = model(frame, conf=conf, verbose=False)

                    # ── Build raw detections array for tracker [x1,y1,x2,y2,conf,cls] ──
                    raw_dets = []
                    for result in results:
                        if result.boxes is None:
                            continue
                        for box in result.boxes:
                            if box.conf is None or box.conf.shape[0] == 0:
                                continue
                            _bx1, _by1, _bx2, _by2 = box.xyxy[0].tolist()
                            # Drop detections whose centre is outside the scope viewport
                            # (handles info-panel FPs in clinical recordings).
                            _cx, _cy = (_bx1 + _bx2) / 2, (_by1 + _by2) / 2
                            if not (_vx <= _cx <= _vx + _vfw and _vy <= _cy <= _vy + _vfh):
                                continue
                            raw_dets.append([_bx1, _by1, _bx2, _by2, float(box.conf[0]), int(box.cls[0])])

                    if not raw_dets:
                        frame_index += 1
                        continue

                    dets_np = np.array(raw_dets, dtype=np.float32)

                    # ── Update tracker (or fall back to raw YOLO boxes) ──────────
                    if tracker is not None:
                        tracks = tracker.update(dets_np, frame)  # full frame for ReID
                        # tracks: [x1,y1,x2,y2,track_id,conf,cls,det_ind]
                        if len(tracks) == 0:
                            frame_index += 1
                            continue
                        track_boxes = tracks
                        use_tracker = True
                    else:
                        # No tracker: use raw detections, fake track_id=0
                        track_boxes = [[*d[:4], 0, d[4], d[5], 0] for d in raw_dets]
                        use_tracker = False

                    # Pick the HIGHEST-confidence detection in this frame instead of
                    # the first one — earlier code broke on first iter, which often
                    # picked a noisy low-conf box and dropped the better detection.
                    sorted_tracks = sorted(track_boxes, key=lambda t: float(t[5]), reverse=True)

                    for trk in sorted_tracks:
                        # bbox is in full-frame coords (inference now runs on full frame)
                        _x1, _y1, _x2, _y2 = float(trk[0]), float(trk[1]), float(trk[2]), float(trk[3])
                        track_id = int(trk[4])
                        det_conf  = float(trk[5])
                        cls_id    = int(trk[6])
                        label     = _clean_label(model_names.get(cls_id, f"class_{cls_id}"))

                        if _is_ignored(frame_index, [_x1, _y1, _x2, _y2]):
                            continue

                        # Suppress whole-frame detections (frame-level classification,
                        # e.g. diffuse HP gastritis). Compute area ratio against the
                        # SCOPE VIEWPORT, not the full frame — otherwise videos with an
                        # info panel would always look smaller than they really are.
                        _bw_seg, _bh_seg = _x2 - _x1, _y2 - _y1
                        _area_ratio = (_bw_seg * _bh_seg) / max(_vfw * _vfh, 1)
                        if _area_ratio > MAX_BBOX_AREA_RATIO:
                            print(f"[Worker] Suppressed whole-frame detection "
                                  f"({label} conf={det_conf:.2f} area={_area_ratio*100:.0f}% "
                                  f"> {MAX_BBOX_AREA_RATIO*100:.0f}% of viewport) — "
                                  f"frame-level diagnosis, not a localized lesion", flush=True)
                            continue

                        xyxy = [_x1, _y1, _x2, _y2]

                        # bbox is already in full-frame coords; normalize to 1920×1080
                        # virtual space so the frontend's FRAME_W=1920 / FRAME_H=1080
                        # constants stay correct for any source resolution.
                        _fw_full = frame.shape[1]
                        _fh_full = frame.shape[0]
                        xyxy_norm = [
                            xyxy[0] / _fw_full * 1920,
                            xyxy[1] / _fh_full * 1080,
                            xyxy[2] / _fw_full * 1920,
                            xyxy[3] / _fh_full * 1080,
                        ]

                        # Spatial-temporal dedup
                        if _is_recently_reported(timestamp_ms, xyxy_norm, label):
                            continue

                        print(f"[Worker] Detection track_id={track_id} {label} conf={det_conf:.2f} bbox={[round(v,1) for v in xyxy]}", flush=True)
                        location = _infer_location(xyxy, frame.shape)
                        # _crop_b64 handles full-frame bbox internally (translates to
                        # viewport coords for the thumbnail).
                        thumbnail_b64 = _crop_b64(frame, xyxy)
                        det_data = {
                            "frame_index": frame_index,
                            "timestamp_ms": timestamp_ms,
                            "location": location,
                            "lesion": {
                                "label": label,
                                "confidence": round(det_conf, 4),
                                "bbox": xyxy_norm,  # normalized to 1920×1080
                            },
                            "frame_b64": thumbnail_b64,
                        }
                        _reported_history.append({"ts_ms": timestamp_ms, "bbox": xyxy_norm, "label": label})
                        confirmed.append(det_data)
                        result_q.put({"event": "DETECTION_FOUND", "data": det_data})
                        paused = True
                        break  # one detection per frame (already the best by conf)
                except Exception as exc:
                    print(f"[Worker] YOLO/tracker error frame {frame_index}: {exc}", flush=True)

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

        # Clear GstShark logs so metrics reflect only this session
        if _GSTSHARK_ENABLED:
            import glob as _glob
            for _f in _glob.glob(f"{_GSTSHARK_LOG_DIR}/*.log"):
                try:
                    open(_f, "w").close()
                except OSError:
                    pass

        self._result_q = _mp_ctx.Queue()
        self._cmd_q = _mp_ctx.Queue()
        self._proc = _mp_ctx.Process(
            target=_pipeline_worker,
            args=(str(video_path), str(self._model_path), CONFIDENCE_THRESHOLD,
                  self._result_q, self._cmd_q,
                  str(REID_WEIGHTS),
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
            self._set_state(PipelineState.PLAYING)
        elif action == "ACTION_EXPLAIN":
            self._set_state(PipelineState.PROCESSING_LLM)
            # Pipeline stays paused in subprocess; WS server handles LLM streaming.
        elif action in ("ACTION_RESUME", "ACTION_CONFIRM"):
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
        accumulated: list[dict] = []
        saw_eos = False
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
                accumulated.append(evt["data"])

            # Track confirmed detections
            if evt["event"] == "VIDEO_FINISHED":
                self._confirmed = evt["data"].get("detections", [])
                self._set_state(PipelineState.EOS_SUMMARY)
                saw_eos = True

            self._push_event(evt)

            if evt["event"] == "VIDEO_FINISHED":
                break

        # Safety net: worker died without sending VIDEO_FINISHED (crash, OOM,
        # SIGKILL, STOP race). Synthesize one so the FE always transitions to
        # EOS_SUMMARY and the report popup appears.
        if not saw_eos:
            print(
                f"[Bridge] Worker exited without EOS — synthesizing VIDEO_FINISHED "
                f"with {len(accumulated)} detections",
                flush=True,
            )
            self._confirmed = accumulated
            self._set_state(PipelineState.EOS_SUMMARY)
            self._push_event(_eos_event(accumulated))
