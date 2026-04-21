"""endoscopy-ws-server.py — FastAPI WebSocket controller for endoscopy pipeline.

Implements SYSTEM_REQUIREMENTS §2 (FastAPI WebSocket middleware):

  POST /upload                   → receive video file, return video_id
  WebSocket /ws/analysis/{id}    → bidirectional channel between FE and pipeline
  GET  /session/{id}/detections  → fetch confirmed detections for report

WebSocket message contract (§5):
  Server → Client:
    DETECTION_FOUND  { data: { frame_index, timestamp_ms, location, lesion, frame_b64 } }
    STATE_CHANGE     { data: { state } }
    LLM_CHUNK        { data: { chunk } }
    LLM_DONE         { data: {} }
    VIDEO_FINISHED   { data: { detections: [...] } }
    ERROR            { data: { message } }

  Client → Server:
    ACTION_IGNORE    {}
    ACTION_EXPLAIN   {}
    ACTION_RESUME    {}
    ACTION_CONFIRM   {}
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
import uuid
from pathlib import Path
from typing import Dict, Optional

from dotenv import load_dotenv
from fastapi import FastAPI, UploadFile, File, WebSocket, WebSocketDisconnect, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from voice_api import router as voice_router

# ── Path setup ───────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve()

# Load .env before importing logger (LOG_LEVEL may be set there)
load_dotenv(_HERE.parent / ".env")

from logger import logger  # noqa: E402 — must come after load_dotenv
_REPO_ROOT = _HERE.parents[3]

# Support running from arbitrary directory (e.g. GPU server deployment)
# PIPELINE_DIR env var overrides default relative path
_PIPELINE_DIR = Path(os.getenv("PIPELINE_DIR", str(_HERE.parents[1] / "pipeline")))
sys.path.insert(0, str(_PIPELINE_DIR))

from pipeline_controller import PipelineController, PipelineState   # noqa: E402

# ── Config ───────────────────────────────────────────────────────────────────
# ENDOSCOPY_UPLOAD_DIR env var overrides default (needed on GPU server)
UPLOAD_DIR = Path(os.getenv("ENDOSCOPY_UPLOAD_DIR", str(_REPO_ROOT / "data" / "uploads")))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
LLM_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
LLM_SYSTEM_PROMPT = (
    "You are an expert gastroenterology assistant analyzing an endoscopy finding. "
    "Respond in Vietnamese. Structure your response with:\n"
    "1. **Phân loại y khoa:** classification suggestion.\n"
    "2. **Checklist cho bác sĩ:** 3-5 actionable steps.\n"
    "Be concise and clinically precise."
)

# ── FastAPI app ───────────────────────────────────────────────────────────────
app = FastAPI(
    title="Endoscopy AI WebSocket Server",
    description="Real-time GStreamer + YOLO + LLM pipeline controller",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(voice_router)

# ── In-memory session registry ───────────────────────────────────────────────
# video_id → { controller, video_path, confirmed_detections }
_sessions: Dict[str, dict] = {}

_openai_client: Optional[AsyncOpenAI] = None


def _get_openai() -> Optional[AsyncOpenAI]:
    global _openai_client
    if _openai_client is None and OPENAI_API_KEY:
        _openai_client = AsyncOpenAI(api_key=OPENAI_API_KEY)
    return _openai_client


# ── REST endpoints ────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "active_sessions": len(_sessions)}


@app.post("/upload")
async def upload_video(file: UploadFile = File(...)):
    """Accept a video file and return a session video_id."""
    ext = Path(file.filename or "video.mp4").suffix
    video_id = uuid.uuid4().hex[:12]
    dest = UPLOAD_DIR / f"{video_id}{ext}"

    contents = await file.read()
    dest.write_bytes(contents)

    _sessions[video_id] = {
        "controller": None,
        "video_path": dest,
        "confirmed_detections": [],
    }
    logger.info("Video uploaded: {} ({:.1f} MB) → session {}", file.filename, len(contents) / 1_048_576, video_id)
    return {"video_id": video_id, "filename": file.filename, "size_bytes": len(contents)}


@app.post("/stream/connect")
async def connect_stream(request: Request):
    """Register a live source (RTSP URL or V4L2 device) and return a session video_id."""
    body = await request.json()
    source = body.get("source", "").strip()
    if not source:
        raise HTTPException(status_code=400, detail="'source' field is required")

    video_id = uuid.uuid4().hex[:12]
    _sessions[video_id] = {
        "controller": None,
        "video_path": source,   # GStreamer will receive this as the source URI
        "confirmed_detections": [],
    }
    logger.info("Live stream registered: {} → session {}", source, video_id)
    return {"video_id": video_id, "source": source}


@app.get("/session/{video_id}/detections")
async def get_detections(video_id: str):
    """Return confirmed detections for the report page."""
    sess = _sessions.get(video_id)
    if not sess:
        raise HTTPException(status_code=404, detail="Session not found")
    ctrl: Optional[PipelineController] = sess["controller"]
    detections = ctrl._confirmed if ctrl else sess["confirmed_detections"]
    return {"video_id": video_id, "detections": detections}


# ── WebSocket endpoint ────────────────────────────────────────────────────────

@app.websocket("/ws/analysis/{video_id}")
async def ws_analysis(websocket: WebSocket, video_id: str):
    """Bidirectional WebSocket between React FE and GStreamer pipeline controller."""
    await websocket.accept()

    sess = _sessions.get(video_id)
    if not sess:
        await websocket.send_json({"event": "ERROR", "data": {"message": "Session not found"}})
        await websocket.close()
        return

    # Create and start pipeline controller
    logger.info("WS connected: session {}", video_id)
    ctrl = PipelineController(video_id=video_id)
    sess["controller"] = ctrl
    ctrl.set_loop(asyncio.get_running_loop())
    ctrl.start(sess["video_path"])

    # Two concurrent tasks: relay pipeline events → FE, and FE actions → pipeline
    async def _relay_events():
        """Forward detection / state events from pipeline queue to FE."""
        while True:
            try:
                evt = await asyncio.wait_for(ctrl.events.get(), timeout=0.1)
            except asyncio.TimeoutError:
                continue
            except asyncio.CancelledError:
                break

            # Track confirmed detections (user did NOT ignore)
            if evt["event"] == "VIDEO_FINISHED":
                sess["confirmed_detections"] = evt["data"]["detections"]

            try:
                await websocket.send_json(evt)
            except Exception:
                break

            if evt["event"] == "VIDEO_FINISHED":
                break

    async def _handle_actions():
        """Receive user actions from FE and dispatch to pipeline controller."""
        while True:
            try:
                raw = await websocket.receive_text()
            except WebSocketDisconnect:
                ctrl.stop()
                break
            except Exception:
                ctrl.stop()
                break

            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            action = msg.get("action", "")

            if action == "ACTION_EXPLAIN":
                # Kick off streaming LLM response before resuming pipeline
                pending = ctrl._pending
                if pending:
                    asyncio.ensure_future(_stream_llm(websocket, pending))
                ctrl.send_action(action)

            else:
                ctrl.send_action(action, msg.get("payload"))

    relay_task = asyncio.ensure_future(_relay_events())
    action_task = asyncio.ensure_future(_handle_actions())

    try:
        done, pending = await asyncio.wait(
            [relay_task, action_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
        for task in pending:
            task.cancel()
    except Exception:
        pass
    finally:
        ctrl.stop()


# ── LLM streaming ─────────────────────────────────────────────────────────────

async def _stream_llm(websocket: WebSocket, detection: dict) -> None:
    """Stream LLM explanation chunks to the FE (§5 LLM Integration)."""
    client = _get_openai()

    location = detection.get("location", "Unknown")
    lesion = detection.get("lesion", {})
    label = lesion.get("label", "Unknown")
    confidence = lesion.get("confidence", 0.0)

    user_prompt = (
        f"Location: {location}. "
        f"Detection: {label}. "
        f"Confidence: {confidence * 100:.0f}%."
    )

    if client is None:
        # No API key — send a canned mock response for dev/demo
        mock = _mock_llm_response(label, location)
        for chunk in mock.split(" "):
            await asyncio.sleep(0.04)
            await websocket.send_json({"event": "LLM_CHUNK", "data": {"chunk": chunk + " "}})
        await websocket.send_json({"event": "LLM_DONE", "data": {}})
        return

    try:
        stream = await client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": LLM_SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            stream=True,
            max_tokens=400,
        )
        async for chunk in stream:
            delta = chunk.choices[0].delta.content or ""
            if delta:
                await websocket.send_json({"event": "LLM_CHUNK", "data": {"chunk": delta}})
        await websocket.send_json({"event": "LLM_DONE", "data": {}})
    except Exception as exc:
        await websocket.send_json({"event": "ERROR", "data": {"message": f"LLM error: {exc}"}})


def _mock_llm_response(label: str, location: str) -> str:
    """Fallback response when OPENAI_API_KEY is not set."""
    return (
        f"**Phân loại y khoa:** Phát hiện phù hợp với {label} tại {location}. "
        "Bờ viền tổn thương không đều, có sung huyết xung quanh. "
        "Cần đối chiếu với triệu chứng lâm sàng và tiền sử bệnh nhân.\n\n"
        "**Checklist cho bác sĩ:**\n"
        "- Xác nhận vị trí giải phẫu chính xác.\n"
        "- Cân nhắc sinh thiết 2-4 mảnh tại rìa tổn thương.\n"
        "- Kiểm tra H. pylori nếu là loét dạ dày.\n"
        "- Ghi nhận kích thước và đặc điểm hình thái vào hồ sơ.\n"
        "- Hẹn tái khám nội soi sau 4-6 tuần nếu điều trị nội khoa."
    )


# ── Entry point ────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("endoscopy-ws-server:app", host="0.0.0.0", port=8001, reload=True)
