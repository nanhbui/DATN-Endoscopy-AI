# Implementation Plan: Video Library & Reuse

**Branch**: `002-video-library-reuse` | **Date**: 2026-05-01 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `specs/002-video-library-reuse/spec.md`

## Summary

Add a persistent video library to the endoscopy analysis system so users can reuse previously uploaded videos without re-uploading them each session. Currently `POST /upload` saves to `data/uploads/` and the WebSocket teardown deletes the file immediately. The fix: store library videos in a separate `data/library/` directory with a JSON index, add REST CRUD endpoints, block deletion while in active use, and extend the frontend workspace with a library browser panel that allows selecting an existing video or uploading a new one.

## Technical Context

**Language/Version**: Python 3.10+ (backend), TypeScript / Next.js 16 (frontend)
**Primary Dependencies**: FastAPI + uvicorn (backend); React, MUI, lucide-react (frontend)
**Storage**: Filesystem — `data/library/` for permanent videos; `data/library/index.json` for metadata index; `data/uploads/` retained for ephemeral live-stream sessions
**Testing**: `frontend/tests/home.test.ts` (Playwright); backend manual test with real video required per constitution
**Target Platform**: Linux server (backend), web browser (frontend)
**Project Type**: Web application (FastAPI backend + Next.js frontend)
**Performance Goals**: Library list loads in < 2 s; session creation from library video takes < 5 s
**Constraints**: Must not alter GStreamer subprocess isolation (Principle III); no DB introduced — filesystem only

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-checked after Phase 1 design.*

| Principle | Gate | Status | Notes |
|-----------|------|--------|-------|
| I — Clinical Safety | No change to detection thresholds or frame-skip logic | ✅ PASS | Library feature is purely pre-session video management |
| II — Hands-Free | Library selection is pre-session (mouse OK); active procedure UI unchanged | ✅ PASS | No hands-free interaction is needed during video selection |
| III — Subprocess Isolation | GStreamer subprocess receives `video_path` unchanged; library path is a local Path, same type | ✅ PASS | Only the source of `video_path` changes, not how it's used |
| IV — Session Integrity | Library video path persists across sessions; no file deletion at WS teardown for library paths | ✅ PASS | Need to guard the cleanup block in `endoscopy_ws_server.py:365` |
| V — Observability | All new endpoints must log with loguru: upload, select, delete, access | ✅ PASS | Log library_id, filename, size for each operation |

No violations. Complexity Tracking section not required.

## Project Structure

### Documentation (this feature)

```text
specs/002-video-library-reuse/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── contracts/           # Phase 1 output
│   └── api.md
└── tasks.md             # Phase 2 output (/speckit.tasks — NOT created here)
```

### Source Code (repository root)

```text
backend/
  src/backend/api/
    endoscopy_ws_server.py   # MODIFY: add library endpoints, guard cleanup
    video_library.py         # CREATE: library storage service (index CRUD)

frontend/
  frontend/
    lib/
      ws-client.ts             # MODIFY: add listLibraryVideos, deleteLibraryVideo, selectLibraryVideo
    context/
      AnalysisContext.tsx      # MODIFY: add selectFromLibrary action
    components/
      video-library-panel.tsx  # CREATE: browse / select / delete UI panel
    app/workspace/
      page.tsx                 # MODIFY: integrate VideoLibraryPanel, add library tab
```

**Structure Decision**: Web application layout — backend owns filesystem operations through a new service module; frontend gets a new component that slots into the existing workspace layout.
