# Research: Video Library & Reuse

**Phase 0 output** | Branch: `002-video-library-reuse` | Date: 2026-05-01

## Decision 1: Storage backend for library metadata

**Decision**: Filesystem directory + JSON index file (`data/library/index.json`)

**Rationale**: The project has no database (sessions are in-memory, uploads are files). Introducing SQLite or any DB would violate YAGNI. A JSON index is readable by humans, writable atomically with a temp-file rename, and fast enough for the expected scale (tens to low-hundreds of videos). A pure filesystem listing (no index) would require reading file metadata on every list request — slower and harder to enrich with custom fields like `display_name`.

**Alternatives considered**:
- SQLite: unnecessary dependency, overkill for < 1000 entries
- Pure filesystem listing (`os.listdir` + `stat`): no custom metadata, slower on large dirs
- Separate metadata sidecar per file (`.json` next to each `.mp4`): harder to list atomically

---

## Decision 2: Deduplication strategy

**Decision**: SHA-256 of the first 4 MB of the file (fast prefix hash), stored in index. Full-hash collision fallback on exact match.

**Rationale**: Endoscopy videos are large (100 MB–2 GB). Hashing the entire file on every upload is too slow (10–30 s on spinning disk). A prefix hash of 4 MB is computed in < 200 ms and catches the overwhelmingly common case of the exact same file being re-uploaded. If two files share a prefix hash, a filename + size match is used as a secondary check before declaring a duplicate. This avoids false deduplication with near-zero overhead.

**Alternatives considered**:
- Full SHA-256: correct but slow for large videos (10–30 s CPU time)
- Filename-only dedup: fragile — same video can be saved under different names
- No dedup: original problem — duplicate storage

---

## Decision 3: Session creation from library video

**Decision**: New endpoint `POST /sessions/from-library/{library_video_id}` creates an in-memory session pointing at the library file path. Returns the same `{ video_id }` shape as `POST /upload` so the frontend WebSocket flow is unchanged.

**Rationale**: The WebSocket analysis flow (`/ws/analysis/{video_id}`) already accepts any path stored in `_sessions[video_id]["video_path"]`. The library path is a local `Path` object — identical type to what `POST /upload` stores. Reusing the same WS flow means zero change to the pipeline controller, voice commands, or LLM integration.

**Alternatives considered**:
- Modifying `POST /upload` to optionally persist: would mix two concerns (ephemeral vs. permanent upload) in one endpoint
- Passing library path directly to WS connect: would require frontend to know server paths (security risk)

---

## Decision 4: Upload-to-library vs. existing upload endpoint

**Decision**: Add a new `POST /library/upload` endpoint for library uploads. Keep `POST /upload` unchanged for backward compatibility with live-stream session registration.

**Rationale**: `POST /upload` already handles the ephemeral-upload-then-connect workflow. Changing it would risk breaking existing session flows. A dedicated endpoint makes intent explicit and allows independent evolution.

---

## Decision 5: Cleanup guard — prevent library file deletion at WS teardown

**Decision**: In `endoscopy_ws_server.py`, the existing cleanup block (line 365) already guards with `str(video_path).startswith(str(UPLOAD_DIR))`. Library files live in `LIBRARY_DIR` (distinct path), so they are already excluded from deletion by the existing guard — no code change needed for the guard itself. However, we must define `LIBRARY_DIR` as a sibling of `UPLOAD_DIR` (`data/library/`) so the path-prefix check holds.

---

## Decision 6: Frontend library panel placement

**Decision**: Add a third tab `"Thư viện"` to the existing `ToggleButtonGroup` (which currently has "Tải video" / "Trực tiếp"). When selected, the video content area shows the `VideoLibraryPanel` component with a scrollable list of library entries and an "Upload new" button at the top.

**Rationale**: Least invasive UI change — reuses existing tab pattern, avoids a new modal or sidebar. The panel replaces the same 16:9 content area zone that `UploadZone` and `LiveInputZone` use, keeping visual consistency.

**Alternatives considered**:
- Modal dialog: extra click to open, breaks the "always visible" goal in the spec
- Sidebar: layout change too large, risks breaking the current 8:4 grid proportions
