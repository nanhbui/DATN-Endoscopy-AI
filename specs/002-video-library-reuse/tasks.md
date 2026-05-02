# Tasks: Video Library & Reuse

**Input**: Design documents from `specs/002-video-library-reuse/`
**Prerequisites**: [plan.md](plan.md) · [spec.md](spec.md) · [data-model.md](data-model.md) · [contracts/api.md](contracts/api.md) · [research.md](research.md)

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no blocking dependencies)
- **[Story]**: User story label — US1 / US2 / US3
- Exact file paths included in every task description

---

## Phase 1: Setup

**Purpose**: Create the library storage directory and shared TypeScript types — no logic yet.

- [x] T001 Define `LIBRARY_DIR = Path(os.getenv("ENDOSCOPY_LIBRARY_DIR", str(_REPO_ROOT / "data" / "library")))` constant and call `LIBRARY_DIR.mkdir(parents=True, exist_ok=True)` at startup in `src/backend/api/endoscopy_ws_server.py`
- [x] T002 [P] Define TypeScript interfaces `LibraryVideo` and `LibraryUploadResult` (per contracts/api.md §Frontend API Client) in `frontend/lib/ws-client.ts`

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: The `VideoLibrary` service module and session schema extension must be complete before any endpoint or UI work can begin.

**⚠️ CRITICAL**: All user story phases depend on this phase.

- [x] T003 Create `src/backend/api/video_library.py` implementing the `VideoLibrary` class with: `load_index() -> list[dict]`, `save_index(entries)` (atomic temp-file rename), `list_videos() -> list[dict]`, `compute_sha256_prefix(path: Path) -> str` (SHA-256 of first 4 MB), `find_duplicate(sha256_prefix: str, size_bytes: int) -> dict | None`, `add_entry(entry: dict)`, `remove_entry(library_id: str)` — per data-model.md §LibraryEntry and §Index File Operations
- [x] T004 Import `VideoLibrary` and instantiate a module-level `_library = VideoLibrary(LIBRARY_DIR)` in `src/backend/api/endoscopy_ws_server.py`; add `"library_id": str | None` field to all `_sessions[video_id]` dictionaries (set to `None` for upload sessions, `library_id` for library sessions) — per data-model.md §Session

**Checkpoint**: `video_library.py` importable, `_library` object created at server start, index file written on first use.

---

## Phase 3: User Story 1 — Select Previously Uploaded Video (Priority: P1) 🎯 MVP

**Goal**: User can open the library panel, see a list of previously uploaded videos, and start a session from one — no upload required.

**Independent Test**: With at least one entry in `data/library/index.json`, open the workspace, switch to the "Thư viện" tab, click a video — the analysis session starts without any file upload.

- [x] T005 [P] [US1] Implement `GET /library` endpoint returning `{"videos": [...]}` (fields: `library_id`, `filename`, `size_bytes`, `uploaded_at`) via `_library.list_videos()` in `src/backend/api/endoscopy_ws_server.py` — per contracts/api.md §GET /library
- [x] T006 [P] [US1] Implement `POST /sessions/from-library/{library_id}` endpoint: look up entry in index (404 if missing), create `_sessions[video_id]` with `video_path = Path(entry["path"])` and `library_id = library_id`, return `{"video_id": ..., "library_id": ..., "filename": ...}` in `src/backend/api/endoscopy_ws_server.py` — per contracts/api.md §POST /sessions/from-library
- [x] T007 [P] [US1] Add `listLibraryVideos(): Promise<LibraryVideo[]>` and `selectLibraryVideo(libraryId: string): Promise<{video_id: string}>` functions to `frontend/lib/ws-client.ts` — per contracts/api.md §Frontend API Client
- [x] T008 [US1] Add `selectFromLibrary: (libraryId: string) => Promise<void>` action to `AnalysisContextType` interface, implement it by calling `selectLibraryVideo(libraryId)` then `connectWs(video_id)`, and expose it in the context value in `frontend/context/AnalysisContext.tsx`
- [x] T009 [US1] Create `frontend/components/video-library-panel.tsx` exporting `VideoLibraryPanel` component: fetches library list on mount via `listLibraryVideos()`, renders a scrollable list of entries (filename, size, upload date), handles empty state (FR-008), calls `onSelect(libraryId)` prop when a video is clicked — uses MUI components consistent with existing workspace UI
- [x] T010 [US1] Add `"library"` as a third value to the existing `ToggleButtonGroup` in `frontend/app/workspace/page.tsx`; when `sourceMode === "library"` render `<VideoLibraryPanel onSelect={handleLibrarySelect} />` in the video content area; implement `handleLibrarySelect` to call `selectFromLibrary(libraryId)` from `useAnalysis()`

**Checkpoint**: US1 fully functional. Library tab visible, list loads, selecting a video starts WS analysis session.

---

## Phase 4: User Story 2 — Upload New Video and Save to Library (Priority: P2)

**Goal**: User uploads a new video file; it is persisted permanently to the library and immediately appears in the list for future sessions.

**Independent Test**: Upload a new video via the library panel's "Upload new" button, navigate away from the page and back, switch to the "Thư viện" tab — the uploaded video appears in the list.

- [x] T011 [US2] Implement `POST /library/upload` endpoint in `src/backend/api/endoscopy_ws_server.py`: receive raw binary body (same pattern as `POST /upload`), compute SHA-256 prefix, call `_library.find_duplicate()`, if duplicate return existing entry with `"duplicate": true` and discard temp file; otherwise save to `LIBRARY_DIR / f"{library_id}{ext}"`, call `_library.add_entry()`, return new entry with `"duplicate": false`; raise 400 on empty body, 415 on unsupported extension, 507 on `OSError` with errno ENOSPC — per contracts/api.md §POST /library/upload
- [x] T012 [P] [US2] Add `uploadToLibrary(file: File, onProgress?: (pct: number) => void): Promise<LibraryUploadResult>` to `frontend/lib/ws-client.ts` using same XHR streaming pattern as existing `uploadVideo()` — per contracts/api.md §Frontend API Client
- [x] T013 [US2] Add an "Tải video mới lên thư viện" button and upload flow to `VideoLibraryPanel` in `frontend/components/video-library-panel.tsx`: trigger hidden file input, call `uploadToLibrary()` with progress state, show upload progress bar, on success refresh the library list and show a brief success/duplicate banner — reuse existing `UploadingProgress` component style from workspace page

**Checkpoint**: US1 + US2 functional. New uploads persist and appear without re-upload in future sessions.

---

## Phase 5: User Story 3 — Manage Library / Delete Videos (Priority: P3)

**Goal**: User can permanently delete a library video with a confirmation step; deletion is blocked when the video is in active use.

**Independent Test**: Click delete on a library entry, confirm the dialog, verify the entry disappears from the list and cannot be selected again. Attempt to delete a video while its session is active — verify a blocking error message is shown.

- [x] T014 [US3] Implement `DELETE /library/{library_id}` endpoint in `src/backend/api/endoscopy_ws_server.py`: return 404 if not in index; scan `_sessions` for any session where `sess["library_id"] == library_id` and return 409 with `"Video is in use by an active session"` if found; otherwise call `_library.remove_entry(library_id)`, `unlink()` the file, return `{"deleted": true, "library_id": ...}` — per contracts/api.md §DELETE /library
- [x] T015 [P] [US3] Add `deleteLibraryVideo(libraryId: string): Promise<void>` to `frontend/lib/ws-client.ts`; throw a typed error with `status: 409` on conflict response — per contracts/api.md §Frontend API Client
- [x] T016 [US3] Add a delete icon button to each library entry row in `VideoLibraryPanel` in `frontend/components/video-library-panel.tsx`: on click show an inline confirmation prompt ("Xóa vĩnh viễn?"); on confirm call `deleteLibraryVideo()`, refresh list on 200; on 409 show an inline error message "Video đang được sử dụng, không thể xóa" — per spec FR-006, FR-007

**Checkpoint**: All three user stories functional. Full library lifecycle (list → select → upload → delete) works end-to-end.

---

## Final Phase: Polish & Cross-Cutting

- [x] T017 [P] Add loguru logging to every `VideoLibrary` method in `src/backend/api/video_library.py`: log `library_id`, `filename`, and `size_bytes` on add/remove; log `"duplicate detected: {library_id}"` on dedup hit; log warnings on index write failure — per constitution §Observability
- [x] T018 [P] Verify the WS session teardown cleanup guard in `src/backend/api/endoscopy_ws_server.py` (line ~365): confirm `str(video_path).startswith(str(UPLOAD_DIR))` correctly excludes `LIBRARY_DIR` paths, add an inline comment explaining the guard — per research.md §Decision 5
- [x] T019 Run `npx tsc --noEmit` in `frontend/` and fix all TypeScript errors introduced by new interfaces and component props

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all user story phases**
- **Phase 3 (US1)**: Depends on Phase 2
- **Phase 4 (US2)**: Depends on Phase 2 (can run in parallel with Phase 3 for T011/T012)
- **Phase 5 (US3)**: Depends on Phase 2 (can run in parallel with Phase 3/4 for T014/T015)
- **Final Phase**: Depends on all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Only depends on Foundational phase — no story dependencies
- **US2 (P2)**: Only depends on Foundational phase — extends the library panel already created in US1
- **US3 (P3)**: Only depends on Foundational phase — extends the library panel further

### Parallel Opportunities

Within Phase 2: T003 and T004 can overlap (write service first, then wire it in).
Within Phase 3: T005, T006, T007 can all run in parallel (separate files).
Within Phase 4: T011 (backend) and T012 (frontend client) can run in parallel.
Within Phase 5: T014 (backend) and T015 (frontend client) can run in parallel.
Final Phase: T017, T018, T019 are fully independent.

---

## Parallel Example: Phase 3 (US1)

```
Parallel batch 1 — independent files:
  Task T005: GET /library endpoint in endoscopy_ws_server.py
  Task T006: POST /sessions/from-library endpoint in endoscopy_ws_server.py
  Task T007: listLibraryVideos + selectLibraryVideo in ws-client.ts

Sequential after batch 1:
  Task T008: selectFromLibrary action in AnalysisContext.tsx  ← needs T007
  Task T009: VideoLibraryPanel component                      ← needs T008
  Task T010: Workspace page integration                       ← needs T009
```

---

## Implementation Strategy

### MVP Scope (US1 Only — 8 tasks)

1. Phase 1: T001, T002
2. Phase 2: T003, T004
3. Phase 3: T005 → T010
4. **Validate**: Library tab visible, list loads from index, selecting video starts session

### Incremental Delivery

- After MVP: add US2 (T011–T013) → users can grow the library via the UI
- After US2: add US3 (T014–T016) → users can manage disk space
- Final: T017–T019 (polish, observability, type safety)

---

## Notes

- No new test files generated (not requested in spec; backend changes require real-video test per constitution §IV but that is a manual validation step)
- `VideoLibraryPanel` is built incrementally: read-only list (US1) → upload button (US2) → delete button (US3)
- The existing `POST /upload` and ephemeral session flow are untouched throughout
- Commit after each checkpoint using conventional commits (`feat:`, `fix:`)
