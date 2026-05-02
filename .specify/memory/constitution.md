<!--
Sync Impact Report
Version change: 1.0.0 → 1.1.0
Modified sections: Technical Constraints (STT, Deduplication, Frontend voice)
Rationale: Align with actual implementation — Web Speech API is primary STT path,
  FAISS/CLIP deduplication is not yet built (IoU-only in-memory), MediaRecorder not used.
Follow-up TODOs: none
-->

# Endoscopy AI Pipeline Constitution

## Core Principles

### I. Clinical Safety First (NON-NEGOTIABLE)
All detection and voice workflows MUST prioritize correctness over performance.
False negatives (missed lesions) are clinically worse than false positives.
Detection thresholds, frame filtering, and smart-ignore logic MUST be tunable and
conservative by default. Any change to confidence thresholds or frame-skip logic
MUST be validated against a representative dataset before merging.

### II. Hands-Free Interaction
The system MUST be fully operable without keyboard or mouse during an endoscopy
session. Voice commands are the primary interaction channel. The UI MUST present
clear visual feedback for every pipeline state so the endoscopist knows what the
system is doing at all times. No action that requires a mouse click during an
active procedure is acceptable.

### III. Subprocess Isolation
GStreamer video processing and CUDA inference MUST run in an isolated subprocess
(multiprocessing `spawn`). Direct GPU-thread sharing with the asyncio event loop
is forbidden. This isolation prevents GLib-thread / CUDA deadlocks and is
non-negotiable regardless of performance implications.

### IV. Session Integrity
Every detection event, voice command, and LLM response MUST be persisted to the
session record before the pipeline resumes. Detection reports are medical
artifacts — data loss or silent failure is unacceptable. WebSocket events MUST
be acknowledged; undelivered events MUST be retried or surfaced as errors.

### V. Observability
Every significant state transition (IDLE → PLAYING → PAUSED → EOS) MUST be
logged with ISO timestamp, session ID, and frame index. LLM calls MUST log
latency and token counts. Voice commands MUST log the raw transcript alongside
the classified intent. Structured loguru (backend) and Winston (frontend) are
the required logging frameworks.

## Technical Constraints

- **Language**: Python 3.10+ (backend), TypeScript / Next.js 16 (frontend)
- **Video**: GStreamer 1.0 with `gst-plugins-good`, `gst-plugins-bad`, `gst-libav`
- **ML runtime**: ultralytics YOLO (GPU preferred, CPU fallback required)
- **STT**: Browser Web Speech API (SpeechRecognition) is the primary path —
  no server round-trip for transcription. Ambiguous transcripts fall back to
  server LLM classify (`POST /voice/classify`). faster-whisper exists as a
  legacy audio-upload endpoint (`POST /voice/command`) but is NOT the primary path.
- **LLM**: OpenAI GPT-4o-mini streaming; API key via environment variable only —
  NEVER committed to source control
- **Deduplication**: In-memory IoU matching per session (built); FAISS/CLIP-based
  negative pattern store is a planned enhancement, NOT yet implemented.
- **API**: FastAPI + uvicorn; WebSocket endpoint `/ws/analysis/{id}` is the
  primary real-time channel
- **Frontend**: Native WebSocket (no socket.io); Web Speech API (SpeechRecognition)
  for voice — NOT MediaRecorder
- **Models**: `.pt` / `.torchscript` files live in `models/`; not tracked in git
  if >100 MB; always document the training dataset and version in `models/labels.txt`

## Development Workflow

- Feature work starts with a spec under `specs/<FEATURE_ID>/spec.md`
- A plan (`plan.md`) and task list (`tasks.md`) MUST exist before implementation
- All code changes require type-checking to pass (`npx tsc --noEmit` for frontend)
- Backend changes that touch GStreamer or YOLO inference MUST be tested with a
  real video file, not a mock
- No confidential information (API keys, `.env` files, model weights) in git
- Commit messages follow Conventional Commits (`feat:`, `fix:`, `docs:`, etc.)
- Branches: `feat/<slug>`, `fix/<slug>`, `chore/<slug>`

## Governance

This constitution supersedes all other development practices within this project.
Amendments require: (1) written rationale, (2) review by the project lead,
(3) version bump following semver rules, and (4) update of `LAST_AMENDED_DATE`.

All PRs MUST verify compliance with Principles I–V before merge.
Complexity beyond what the current milestone requires is explicitly forbidden
(YAGNI). Use `TECHNICAL_DESIGN.md` and `SYSTEM_REQUIREMENTS.md` as runtime
reference documents.

**Version**: 1.1.0 | **Ratified**: 2026-05-01 | **Last Amended**: 2026-05-01
