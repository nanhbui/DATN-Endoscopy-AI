# System Specification: Endoscopy AI Pipeline (Baseline)

**Feature Branch**: `main`
**Created**: 2026-05-01
**Status**: Partially Implemented
**Type**: Baseline — captures full system vision (built + planned)

---

## Overview

AI-assisted gastrointestinal endoscopy video analysis system. Processes pre-recorded or live video streams, detects mucosal lesions using a fine-tuned YOLO model, and provides a **hands-free, voice-first** workflow so endoscopists can interact without touching keyboard/mouse during procedures.

**Primary users**: Gastroenterologists performing endoscopy procedures in Vietnamese clinical settings.

---

## Build Status

| Component | Status |
|---|---|
| GStreamer pipeline (subprocess isolation) | ✅ Built |
| YOLO lesion detection (YOLOv8) | ✅ Built |
| FastAPI WebSocket server | ✅ Built |
| Smart Ignore — IoU deduplication (in-memory, per-session) | ✅ Built |
| Smart Ignore — FAISS negative pattern store (cross-session) | ❌ Not built |
| Voice control — Web Speech API (SpeechRecognition) → server LLM classify | ✅ Built |
| Voice control — faster-whisper audio transcription (legacy endpoint) | ⚠️ Built (not primary path) |
| Intent classifier (keyword-based Vietnamese) | ✅ Built |
| LLM insights (GPT-4o-mini streaming) | ✅ Built |
| Next.js frontend (workspace, dashboard, report) | ✅ Built |
| Frame quality filter (dark/blur rejection) | ✅ Built |
| Docker Compose + structured logging | ✅ Built |
| MongoDB case persistence | ❌ Not built (in-memory only) |
| ChromaDB / RAG for similar case retrieval | ❌ Not built |
| LLaVA-Med fine-tuned local model | ❌ Not built (GPT-4o-mini fallback) |
| CLIP-based adaptive frame filter | ❌ Not built (IoU-only deduplication currently) |
| Object tracking across frames | ❌ Not built |
| TensorRT / DeepStream GPU optimization | ❌ Not built (ultralytics runtime) |
| PDF / export for session report | ❌ Not built |
| Patient ID anonymization | ❌ Not built |
| Response caching for LLM | ❌ Not built |

---

## User Stories

### US1 — Real-time Lesion Detection During Video Playback (P1)

Endoscopist uploads a pre-recorded video. The system plays it and automatically pauses when a lesion is detected, showing the frame with bounding box overlay and lesion label.

**Acceptance Scenarios**:
1. **Given** a valid MP4/MOV file, **When** uploaded and pipeline starts, **Then** video plays and YOLO runs inference every 3rd frame
2. **Given** YOLO confidence ≥ 0.45 (default; override via `ENDOSCOPY_CONF` env var), **When** detection passes Smart Ignore check, **Then** pipeline pauses and `DETECTION_FOUND` event fires with frame, bbox, label, timestamp
3. **Given** same lesion previously ignored, **When** detected again with IoU > 0.8, **Then** pipeline does NOT pause (silent skip)
4. **Given** dark frame / scope-insertion frame, **When** quality filter runs, **Then** frame is skipped without triggering detection

### US2 — Voice-Controlled Response to Detection (P1)

After pipeline pauses on detection, endoscopist speaks a Vietnamese command. System transcribes, classifies intent, and executes without keyboard/mouse.

**Acceptance Scenarios**:
1. **Given** pipeline paused, **When** doctor says "bỏ qua" / "sai rồi" / "không phải", **Then** detection marked false positive and pipeline resumes
2. **Given** pipeline paused, **When** doctor says "giải thích" / "phân tích" / "xem nào", **Then** GPT-4o-mini streams Paris classification + actionable checklist
3. **Given** LLM explanation complete, **When** doctor says "đúng rồi" / "xác nhận", **Then** detection confirmed and pipeline resumes
4. **Given** doctor says "kiểm tra lại", **When** intent classified as `KIEM_TRA_LAI`, **Then** current frame re-analyzed *(intent defined in IntentClassifier but NOT yet wired to WS server or frontend action — gap)*
5. **Given** background noise / irrelevant speech, **When** no matching intent, **Then** system stays paused, no action taken

### US3 — Live Stream Mode (P1)

Endoscopist connects a live RTSP URL or V4L2 device for real-time analysis during an active procedure.

**Acceptance Scenarios**:
1. **Given** valid RTSP URL, **When** "Kết nối & Bắt đầu" clicked, **Then** GStreamer opens stream and detection begins
2. **Given** V4L2 device path (e.g., `/dev/video0`), **When** connected, **Then** local camera stream analyzed in real-time
3. **Given** stream drops, **When** reconnect attempted, **Then** error surfaced via `ERROR` WebSocket event

### US4 — Session Report (P2)

After video finishes or session ends, endoscopist reviews all confirmed detections with frame thumbnails, timestamps, LLM notes.

**Acceptance Scenarios**:
1. **Given** EOS reached, **When** `VIDEO_FINISHED` event fires, **Then** report page shows all confirmed detections as cards
2. **Given** detection card, **When** viewed, **Then** shows: cropped frame thumbnail, timestamp, lesion label, confidence, LLM suggestion
3. **Given** multiple sessions, **When** dashboard viewed, **Then** session list shows date, video name, detection count

### US5 — Persistent Case History (P3 — not built)

All confirmed sessions and detections stored in MongoDB. Doctor can retrieve past cases.

**Acceptance Scenarios**:
1. **Given** session ends with confirmed detections, **When** EOS summary fires, **Then** case saved to MongoDB with full metadata
2. **Given** patient ID, **When** queried, **Then** all past cases returned chronologically
3. **Given** saved case, **When** retrieved, **Then** includes detections, LLM suggestions, voice feedback log

### US6 — Local Medical LLM (P3 — not built)

Replace GPT-4o-mini with a locally-hosted LLaVA-Med fine-tuned on HyperKvasir for offline clinical environments.

**Acceptance Scenarios**:
1. **Given** `LLAVA_MED_ENABLED=true`, **When** explain triggered, **Then** LLaVA-Med 4-bit serves response locally without internet
2. **Given** local model unavailable, **When** explain triggered, **Then** fallback to GPT-4o-mini with warning logged
3. **Given** local model response, **Then** same `ClinicalSuggestion` format as GPT-4o-mini

### US7 — Adaptive Frame Filter with CLIP (P3 — not built)

Replace basic IoU deduplication with CLIP-based visual similarity to catch false positives that look visually identical but have different bboxes.

**Acceptance Scenarios**:
1. **Given** frame marked as false positive by doctor, **When** similar-looking frame detected later, **Then** CLIP cosine similarity > 0.85 triggers silent skip
2. **Given** FAISS index, **When** new negative pattern added, **Then** persisted across sessions
3. **Given** 10+ negative feedbacks, **Then** false positive rate reduces ≥ 50% vs baseline

---

## Requirements

### Functional Requirements

- **FR-001**: System MUST support both batch (file upload) and live (RTSP/V4L2) video input modes
- **FR-002**: System MUST detect lesions using YOLO with configurable confidence threshold (default 0.45; env `ENDOSCOPY_CONF`)
- **FR-003**: System MUST pause pipeline and notify frontend within 100ms of detection
- **FR-004**: System MUST skip frames that fail quality filter (dark, low-variance, scope-insertion)
- **FR-005**: System MUST NOT re-pause for previously ignored detection with IoU > 0.8 within the same session
- **FR-006**: System MUST transcribe Vietnamese speech via browser Web Speech API (SpeechRecognition); ambiguous transcripts fall back to server LLM classify; faster-whisper audio path is legacy/optional
- **FR-007**: System MUST classify transcript into: `BO_QUA`, `GIAI_THICH`, `XAC_NHAN`; `KIEM_TRA_LAI` is defined but not yet wired to any pipeline action
- **FR-008**: System MUST stream LLM response token-by-token to frontend
- **FR-009**: System MUST generate session report with all confirmed detections at EOS
- **FR-010**: System MUST run GStreamer and YOLO in isolated subprocess (no asyncio sharing)
- **FR-011**: System SHOULD persist negative patterns across sessions; currently in-memory only (FAISS implementation pending)
- **FR-012**: System MUST support manual override buttons alongside voice commands
- **FR-013**: LLM response MUST include Paris classification and actionable checklist in Vietnamese

### Non-Functional Requirements

- **NFR-001**: YOLO inference < 30ms per frame on GPU, < 100ms on CPU
- **NFR-002**: Voice intent round-trip (Web Speech API → classify → action) < 500ms; faster-whisper legacy path < 1s
- **NFR-003**: LLM first token < 2 seconds
- **NFR-004**: Video frame rate ≥ 30 FPS at 1080p
- **NFR-005**: FAISS similarity search < 10ms for 1000 patterns *(target for when FAISS is implemented)*
- **NFR-006**: System MUST function without internet (except GPT-4o-mini calls)
- **NFR-007**: No API keys or credentials committed to source control

### Key Entities

- **Session**: one video upload or live stream connection; has ID, state, detections list
- **Detection**: frame_index, timestamp_ms, bbox, lesion_label, confidence, llm_suggestion, feedback
- **NegativePattern**: bbox + frame_index for in-session IoU deduplication; FAISS embedding store planned for cross-session persistence
- **VoiceCommand**: raw_transcript, classified_intent, confidence, timestamp

---

## Success Criteria

- **SC-001**: Endoscopist completes full procedure (upload → detect → voice respond → report) without keyboard
- **SC-002**: False positive re-trigger rate < 5% after doctor ignores a detection
- **SC-003**: Voice intent classification accuracy ≥ 90% on Vietnamese clinical phrases
- **SC-004**: End-to-end detection-to-pause latency < 200ms on GPU hardware
- **SC-005**: Session report renders all confirmed detections with thumbnails within 3 seconds of EOS

---

## Assumptions

- Primary deployment: local GPU server (hospital infrastructure, not cloud)
- GPU: NVIDIA with CUDA 11.8+ (CPU fallback required for testing environments)
- Language: Vietnamese primary; UI labels mix Vietnamese/English acceptable
- Internet required only for GPT-4o-mini calls; all other processing is local
- Video formats: MP4, MOV, AVI, MKV (H.264 encoded)
- `daday.pt` model detects 3 gastric lesion classes: HP-negative gastritis, HP-positive gastritis, gastric cancer
- Patient data anonymization is out of scope for v1 (DATN prototype)

---

## Open Items / Future Enhancements

1. **MongoDB persistence** — currently sessions are in-memory only; data lost on restart
2. **LLaVA-Med local model** — replace GPT-4o-mini for offline clinical environments
3. **CLIP adaptive filter** — replace IoU-only deduplication with visual similarity
4. **TensorRT optimization** — replace ultralytics runtime with DeepStream for production throughput
5. **PDF export** — session report download for medical records
6. **RAG case retrieval** — ChromaDB + similar past cases surfaced alongside LLM suggestion
7. **Object tracking** — track lesion across frames to avoid re-detection of same lesion
8. **Response caching** — cache LLM responses for visually similar frames
9. **Multi-language support** — English UI option for international deployment
