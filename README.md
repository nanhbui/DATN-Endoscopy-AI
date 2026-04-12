# Endoscopy AI Pipeline

An AI-assisted gastrointestinal endoscopy video analysis system with real-time lesion detection, hands-free voice control, and LLM-powered clinical insights.

---

## Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Features](#features)
- [Project Structure](#project-structure)
- [Tech Stack](#tech-stack)
- [Getting Started](#getting-started)
- [Running the System](#running-the-system)
- [WebSocket API](#websocket-api)
- [Voice Commands](#voice-commands)
- [Training & Dataset](#training--dataset)
- [Configuration](#configuration)

---

## Overview

This system processes gastrointestinal endoscopy videos (pre-recorded or live RTSP/V4L2 streams), detects mucosal lesions using a fine-tuned YOLO model, and provides an interactive **hands-free, voice-first** workflow for endoscopists.

When a lesion is detected:
1. The pipeline **pauses** automatically
2. The microphone **activates** — the doctor speaks naturally in Vietnamese
3. **Whisper STT** transcribes the command on the GPU
4. The **Intent Classifier** routes to `BO_QUA` (ignore), `GIAI_THICH` (explain), or `XAC_NHAN` (confirm)
5. If explain: a **Medical LLM** (GPT-4o-mini) streams a clinical classification + checklist
6. The pipeline **resumes** after the doctor responds

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        React Frontend                           │
│  Next.js 16 · MUI · Framer Motion · WebSocket client           │
│  Workspace (video + bbox overlay) · Dashboard · Report          │
└────────────────────────┬───────────────┬────────────────────────┘
                         │ WebSocket     │ REST (upload / connect)
┌────────────────────────▼───────────────▼────────────────────────┐
│                  FastAPI Backend  :8001                          │
│  POST /upload          → session registry                        │
│  POST /stream/connect  → live RTSP/V4L2 session                 │
│  WS   /ws/analysis/{id}→ bidirectional event channel            │
│  POST /voice/command   → Whisper STT + Intent Classifier        │
└────────────────────────┬────────────────────────────────────────┘
                         │ multiprocessing (spawn)
┌────────────────────────▼────────────────────────────────────────┐
│              GStreamer Pipeline Subprocess                        │
│  filesrc / rtspsrc / v4l2src                                     │
│  → avdec_h264 → videoconvert → appsink                          │
│  → YOLO (ultralytics, daday.pt) → frame quality filter          │
│  → Smart Ignore (IoU check) → detection events                  │
└─────────────────────────────────────────────────────────────────┘
```

> GStreamer and YOLO/CUDA run in an **isolated subprocess** to prevent GLib-thread / CUDA deadlock when used with uvloop.

---

## Features

| Feature | Description |
|---|---|
| **Real-time detection** | YOLO inference every 3rd diagnostic frame (`FRAME_STEP=3`) |
| **Frame quality filter** | Skips scope-insertion frames, dark frames, and low-variance cards |
| **Smart Ignore memory** | IoU-based deduplication — same lesion not re-flagged in same session |
| **Voice control** | MediaRecorder → Whisper STT on GPU → Vietnamese intent classification |
| **LLM insights** | Streamed GPT-4o-mini: Paris classification + actionable checklist |
| **Live stream support** | RTSP URL or V4L2 device in addition to video file upload |
| **Detection report** | Session report with frame thumbnails, timestamps, confidence |
| **Hands-free design** | No keyboard/mouse required during endoscopy procedure |

---

## Project Structure

```
.
├── frontend/                    # Next.js 16 web interface
│   ├── app/
│   │   ├── page.tsx             # Dashboard with session summary + report table
│   │   ├── workspace/page.tsx   # Video analysis workspace
│   │   └── report/page.tsx      # Full session report with detection cards
│   ├── context/AnalysisContext.tsx  # Global state (WS + pipeline state)
│   ├── hooks/use-voice-control.ts   # MediaRecorder → Whisper intent hook
│   └── lib/ws-client.ts             # WebSocket + upload/stream helpers
│
├── src/
│   ├── backend/
│   │   ├── api/
│   │   │   ├── endoscopy_ws_server.py   # FastAPI app (main entry point)
│   │   │   └── voice_api.py             # POST /voice/command endpoint
│   │   └── pipeline/
│   │       └── pipeline_controller.py   # GStreamer subprocess + state machine
│   │
│   ├── voice/
│   │   ├── intent_classifier.py    # Keyword-based Vietnamese intent routing
│   │   ├── whisper_transcriber.py  # Web API: audio bytes → transcript (WebM/WAV)
│   │   ├── whisper_listener.py     # Desktop: continuous PyAudio + VAD streaming
│   │   └── voice_controller.py     # Desktop: orchestrates listener + classifier
│   │
│   └── frame_skipping/
│       ├── frame_skipper.py   # FAISS-based negative pattern store (persistent)
│       └── faiss_store.py     # NegativeFrameStore — CLIP embedding index
│
├── scripts/
│   ├── preprocess_hyperkvasir.py      # HyperKvasir → YOLO dataset format
│   ├── generate_instruction_pairs.py  # HyperKvasir → LLaVA VQA pairs
│   ├── train_llava_lora.py            # LLaVA-Med LoRA fine-tuning
│   ├── gpu_yolo_server.py             # GPU server: receive UDP stream + YOLO
│   ├── deploy_and_run.sh              # Server deployment script
│   └── stream_to_server.sh            # Stream local video to GPU server via UDP
│
├── requirements.txt             # Python dependencies
├── SYSTEM_REQUIREMENTS.md       # Full system specification
└── TECHNICAL_DESIGN.md          # Architecture design document
```

---

## Tech Stack

### Backend
| Component | Technology |
|---|---|
| API server | FastAPI + uvicorn (asyncio) |
| Video processing | GStreamer 1.0 (subprocess isolation) |
| Object detection | YOLO via ultralytics (`daday.pt` — gastroscopy model) |
| Speech-to-text | faster-whisper (GPU, Vietnamese) |
| LLM | OpenAI GPT-4o-mini (streaming) |
| Vector similarity | FAISS (negative pattern deduplication) |

### Frontend
| Component | Technology |
|---|---|
| Framework | Next.js 16 + React 19 |
| UI | MUI v5 + shadcn/ui + Framer Motion |
| Voice capture | MediaRecorder API (WebM/OPUS chunks) |
| Realtime comms | Native WebSocket |

---

## Getting Started

### Prerequisites

- Python 3.10+
- Node.js 18+
- GStreamer 1.0 with `gst-plugins-good`, `gst-plugins-bad`, `gst-libav`
- NVIDIA GPU recommended (CUDA 11.8+) — CPU fallback available
- ffmpeg (for Whisper audio decoding)

### Backend Setup

```bash
# Create virtual environment
python -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Configure environment
cp src/backend/api/.env.example src/backend/api/.env
# Edit .env and add your OPENAI_API_KEY
```

### Frontend Setup

```bash
cd frontend
npm install
```

---

## Running the System

### 1. Start the Backend

```bash
source .venv/bin/activate
cd src/backend/api
uvicorn endoscopy_ws_server:app --host 0.0.0.0 --port 8001 --reload
```

### 2. Start the Frontend

```bash
cd frontend
npm run dev
# Opens at http://localhost:3000
```

### 3. Using the Workspace

**File mode (batch):**
1. Navigate to `/workspace`
2. Drag & drop or select a video file (MP4, MOV, AVI, MKV)
3. Upload completes → GStreamer pipeline starts → video plays automatically
4. When a lesion is detected, the pipeline pauses and the action bar appears

**Live stream mode:**
1. Toggle to "Trực tiếp" in the workspace header
2. Enter an RTSP URL (`rtsp://...`) or V4L2 device path (`/dev/video0`)
3. Click "Kết nối & Bắt đầu"

---

## WebSocket API

**Endpoint:** `ws://localhost:8001/ws/analysis/{video_id}`

### Server → Client Events

| Event | Payload | Description |
|---|---|---|
| `STATE_CHANGE` | `{ state }` | Pipeline state update |
| `DETECTION_FOUND` | `{ frame_index, timestamp_ms, location, lesion, frame_b64 }` | New lesion detected |
| `LLM_CHUNK` | `{ chunk }` | Streaming LLM response token |
| `LLM_DONE` | `{}` | LLM response complete |
| `VIDEO_FINISHED` | `{ detections: [...] }` | End of stream summary |
| `ERROR` | `{ message }` | Pipeline error |

### Client → Server Actions

| Action | Effect |
|---|---|
| `ACTION_IGNORE` | Mark detection as false positive, resume pipeline |
| `ACTION_EXPLAIN` | Trigger LLM explanation for current detection |
| `ACTION_RESUME` | Resume pipeline after explanation |

### Pipeline States

```
IDLE → PLAYING → PAUSED_WAITING_INPUT → PROCESSING_LLM → PLAYING → ... → EOS_SUMMARY
```

---

## Voice Commands

The system uses a **two-channel voice approach**:

| Mode | Mechanism | Use case |
|---|---|---|
| **Web (primary)** | Browser MediaRecorder → `POST /voice/command` → Whisper GPU | During analysis sessions via the web UI |
| **Desktop (standalone)** | PyAudio + VAD → `WhisperListener` → `VoiceController` | Direct integration without browser |

### Recognized Vietnamese Intents

| Intent | Example phrases | Action |
|---|---|---|
| `BO_QUA` | "bỏ qua", "sai rồi", "không phải", "cho qua" | Ignore detection, resume |
| `GIAI_THICH` | "giải thích", "phân tích", "xem nào", "là gì" | Stream LLM clinical insight |
| `XAC_NHAN` | "đúng rồi", "xác nhận", "lưu lại" | Confirm detection (no auto action) |
| `KIEM_TRA_LAI` | "kiểm tra lại", "chạy lại", "xem lại" | Re-analyze current frame |

---

## Training & Dataset

### HyperKvasir Preprocessing

```bash
# Download hyper-kvasir-labeled-images.zip → data/raw/
python scripts/preprocess_hyperkvasir.py
# Output: data/hyperkvasir_yolo/ (YOLO format, 80/20 train/val split)
```

### LLaVA Instruction Pair Generation

```bash
python scripts/generate_instruction_pairs.py
# Output: data/llava_finetune/train.json (ShareGPT VQA format)
```

### LLaVA-Med LoRA Fine-tuning

```bash
bash scripts/run_gpu_training.sh
# or directly:
python scripts/train_llava_lora.py
```

---

## Configuration

### Backend `.env` (`src/backend/api/.env`)

```env
OPENAI_API_KEY=sk-...
OPENAI_MODEL=gpt-4o-mini

# Optional overrides
ENDOSCOPY_UPLOAD_DIR=/path/to/uploads   # default: data/uploads/
ENDOSCOPY_MODEL=/path/to/model.pt       # default: sample_code/endocv_2024/model_yolo/daday.pt
PIPELINE_DIR=/path/to/pipeline          # default: src/backend/pipeline/
```

### Frontend `.env.local` (`frontend/.env.local`)

```env
NEXT_PUBLIC_API_BASE=http://localhost:8001
```

### Key Pipeline Constants (`pipeline_controller.py`)

| Constant | Default | Description |
|---|---|---|
| `CONFIDENCE_THRESHOLD` | `0.50` | Minimum YOLO confidence to trigger detection |
| `SKIP_INITIAL_FRAMES` | `90` | Frames skipped at start (~3s at 30fps) |
| `FRAME_STEP` | `3` | Run inference every Nth frame |

---

## YOLO Model

The primary detection model is `daday.pt` — a custom-trained YOLOv8 model for gastroscopy:

| Class ID | Label | Description |
|---|---|---|
| 3 | `3_Viem_da_day_HP_am` | Gastritis, H. pylori negative |
| 4 | `4_Viem_da_day_HP_duong` | Gastritis, H. pylori positive |
| 6 | `6_Ung_thu_da_day` | Gastric cancer |

A fallback to `yolov8n.pt` (COCO pretrained) is used if the primary model is not found.

---

## Development

```bash
# Frontend type check
cd frontend && npx tsc --noEmit

# Frontend dev server
cd frontend && npm run dev

# Backend with hot reload
uvicorn endoscopy_ws_server:app --reload --port 8001
```
