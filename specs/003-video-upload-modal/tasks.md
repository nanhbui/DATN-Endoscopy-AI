# Tasks: Video Source Selection Modal

**Input**: Design documents from `specs/003-video-upload-modal/`
**Prerequisites**: [plan.md](plan.md) · [spec.md](spec.md) · [data-model.md](data-model.md) · [contracts/ui.md](contracts/ui.md) · [research.md](research.md)

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no blocking dependencies)
- **[Story]**: User story label — US1 / US2 / US3 / US4
- Exact file paths included in every task description

---

## Phase 1: Setup

**Purpose**: No new dependencies needed — pure frontend refactor.

*(No setup tasks required)*

---

## Phase 2: Foundational (Blocking Prerequisite)

**Purpose**: `VideoLibraryPanel` must accept a `showUploadButton` prop before it can be embedded inside the modal without showing a redundant upload button.

**⚠️ CRITICAL**: Phase 3 (library section) depends on this.

- [X] T001 Add `showUploadButton?: boolean` prop (default `true`) to the `VideoLibraryPanelProps` interface in `frontend/components/video-library-panel.tsx`; wrap the header upload `MuiButton` and its hidden `<input ref={fileInputRef}>` in a conditional `{showUploadButton !== false && (...)}` block so they are hidden when the panel is rendered inside the modal

**Checkpoint**: `VideoLibraryPanel` renders without the upload button when `showUploadButton={false}` is passed.

---

## Phase 3: User Story 1 — Modal Shell (Priority: P1) 🎯 MVP

**Goal**: The "Thư viện" tab disappears from the workspace toggle. Clicking the video upload area or the right-panel CTA opens a MUI Dialog. The Dialog has a two-column layout (library left, upload right). Escape / backdrop click / × closes it.

**Independent Test**: Open the workspace — no "Thư viện" tab visible in the toggle. Click the video zone — a Dialog with two columns appears. Press Escape — Dialog closes.

- [X] T002 [P] [US1] Create `frontend/components/video-source-modal.tsx` exporting `VideoSourceModal` with props `{ open: boolean; onClose: () => void; onUploadAndConnect: (file: File, onProgress: (pct: number) => void) => Promise<void>; onLibrarySelect: (libraryId: string) => void }`; render a MUI `Dialog maxWidth="md" fullWidth`; header row with title "Chọn nguồn video" and a lucide `X` `IconButton` that calls `onClose`; MUI `Grid` container with left column `xs={12} md={7}` (library placeholder — `<Typography>Thư viện…</Typography>`) and right column `xs={12} md={5}` (upload placeholder — `<Typography>Tải lên…</Typography>`); standard MUI backdrop/Escape behavior calls `onClose` — per contracts/ui.md §VideoSourceModal

- [X] T003 [P] [US1] Modify `frontend/app/workspace/page.tsx`: (a) change `sourceMode` state type from `'file' | 'live' | 'library'` to `'video' | 'live'`, rename all `'file'` references to `'video'`; (b) remove `BookOpen` from lucide imports and the `<ToggleButton value="library">` button plus its `sourceMode === 'library'` render branch; (c) add `const [isSourceModalOpen, setIsSourceModalOpen] = useState(false)`; (d) in the video content area when `!videoUrl` (idle): replace `<UploadZone onFileSelected={handleFileSelected} />` with a click-to-open trigger zone (same visual as UploadZone but `onClick={() => setIsSourceModalOpen(true)}`); (e) update right-panel CTA `onClick` to `setIsSourceModalOpen(true)` instead of spawning a file input; (f) import `VideoSourceModal` and render `<VideoSourceModal open={isSourceModalOpen} onClose={() => setIsSourceModalOpen(false)} onUploadAndConnect={handleUploadAndConnect} onLibrarySelect={handleLibrarySelectFromModal} />` near the bottom of the JSX — per contracts/ui.md §workspace/page.tsx

**Checkpoint**: US1 functional. No Thư viện tab. Clicking the video zone opens the Dialog. Escape closes it.

---

## Phase 4: User Story 2 — Upload Flow in Modal (Priority: P1)

**Goal**: The upload section inside the modal is fully functional: drag-and-drop or click to pick a file, progress bar inside the modal, auto-close and session-start on success.

**Independent Test**: Open modal → drag a valid video file onto the upload zone → LinearProgress fills inside the modal → modal closes → analysis session starts in the workspace.

- [X] T004 [US2] Implement the upload section in the right column of `frontend/components/video-source-modal.tsx`: (a) move the `UploadZone` and `UploadingProgress` component definitions from `frontend/app/workspace/page.tsx` into this file (delete them from page.tsx); (b) add internal state `isUploading: boolean`, `uploadProgress: number`, `uploadError: string | null`; (c) on valid file selected: call `onUploadAndConnect(file, setUploadProgress)` — while in progress render `<UploadingProgress>` inside the column, set `disableEscapeKeyDown` and disable the × button to prevent accidental cancellation; on promise resolve call `onClose()`; (d) on unsupported MIME type (`!file.type.startsWith('video/')`) set `uploadError` and show an inline MUI `Alert severity="error"` — modal stays open — per spec FR-005, research Decision 6

- [X] T005 [US2] Update `frontend/app/workspace/page.tsx`: (a) implement `handleUploadAndConnect` async callback: `URL.createObjectURL(file)` → `setVideoFile(file)` → `setVideoUrl(localUrl)` → `await uploadAndConnect(file, onProgress)` → `setIsSourceModalOpen(false)`; pass as `onUploadAndConnect` prop to `VideoSourceModal`; (b) remove the `UploadZone` and `UploadingProgress` component definitions (now in modal file); (c) the click-to-open trigger zone added in T003 remains; (d) the existing `isUploading` / `uploadProgress` state in page.tsx is no longer needed — remove it

**Checkpoint**: US1 + US2 functional. Upload flow works end-to-end through the modal.

---

## Phase 5: User Story 3 — Library Selection in Modal (Priority: P2)

**Goal**: The left column of the modal shows the full library list. Clicking a row starts the analysis session and the modal closes.

**Independent Test**: With at least one library video on the server, open modal — left column shows the library list with filename/size/date. Click a row — modal closes — session starts.

- [X] T006 [P] [US3] Fill the library section (left column) in `frontend/components/video-source-modal.tsx`: replace the placeholder with `<VideoLibraryPanel showUploadButton={false} onSelect={handleLibrarySelectInternal} />`; implement `handleLibrarySelectInternal(libraryId)` that calls `onLibrarySelect(libraryId)` prop then calls `onClose()`; wrap the `<VideoLibraryPanel>` in a try-catch boundary: if library fetch throws, render an inline MUI `Alert severity="warning"` with "Không thể tải thư viện" in the left column without affecting the upload section — per spec FR-006, FR-007, FR-011

- [X] T007 [P] [US3] Update `frontend/app/workspace/page.tsx`: implement `handleLibrarySelectFromModal` async callback that calls `await selectFromLibrary(libraryId)` then `if (voiceSupported) startListening()` then `setIsSourceModalOpen(false)`; pass it as `onLibrarySelect` prop to `VideoSourceModal`; remove the old `handleLibrarySelect` and its `selectFromLibrary` wiring (replaced by this)

**Checkpoint**: US1 + US2 + US3 functional. Full modal lifecycle works end-to-end.

---

## Phase 6: User Story 4 — Save-to-Library Toggle (Priority: P3)

**Goal**: Upload section gains a "Lưu vào thư viện" checkbox. When checked, the uploaded video is saved permanently and appears in the library for future sessions.

**Independent Test**: Open modal → check "Lưu vào thư viện" → upload a video → close modal → reopen modal → video appears in library list.

- [X] T008 [US4] In `frontend/components/video-source-modal.tsx`: (a) add `saveToLibrary: boolean` state (default `false`); (b) render a MUI `FormControlLabel` + `Checkbox` below the `UploadZone` (hidden during upload): label "Lưu vào thư viện"; (c) when file selected and `saveToLibrary === true`: import `uploadToLibrary` and `selectLibraryVideo` from `@/lib/ws-client`; call `uploadToLibrary(file, setUploadProgress)` instead of `onUploadAndConnect`; on success call `onLibrarySelect(result.library_id)` (which triggers session start via parent); if `result.duplicate === true` show an inline success-variant banner "Video đã có trong thư viện — phiên phân tích bắt đầu" before closing — per spec US4, research Decision 3

**Checkpoint**: All four user stories functional.

---

## Final Phase: Polish & Cross-Cutting

- [X] T009 [P] Clean up `frontend/app/workspace/page.tsx`: remove unused imports (`BookOpen`, `VideoLibraryPanel`, and `UploadCloud` if no remaining usage); remove dead state (`isUploading`, `uploadProgress` if moved to modal); remove dead code from removed library tab branch; verify file is under 200 LOC — per plan.md §Constraints

- [X] T010 [P] Run `npx tsc --noEmit` in `frontend/` and fix all TypeScript errors introduced by new `VideoSourceModal` props, modified `sourceMode` type, `showUploadButton` prop on `VideoLibraryPanel`, and removed state variables in `workspace/page.tsx`

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 2 (Foundational)**: No dependencies — start immediately
- **Phase 3 (US1)**: Depends on Phase 2 — **BLOCKS US3 library section** (needs `showUploadButton` prop)
- **Phase 4 (US2)**: Depends on Phase 3 (T002 modal shell must exist)
- **Phase 5 (US3)**: Depends on Phase 3 (T002 modal shell) and Phase 2 (T001 VideoLibraryPanel prop)
- **Phase 6 (US4)**: Depends on Phase 4 (upload flow must be working) and Phase 5 (library selection must be working)
- **Final Phase**: Depends on all user story phases complete

### User Story Dependencies

- **US1 (P1)**: Only depends on Foundational — core modal shell, no story deps
- **US2 (P1)**: Depends on US1 modal shell existing
- **US3 (P2)**: Depends on US1 modal shell + Foundational `showUploadButton` prop
- **US4 (P3)**: Depends on US2 (upload flow) and US3 (library selection flow)

### Parallel Opportunities

Within Phase 3: T002 (create modal file) and T003 (update workspace page) touch different files — run in parallel.
Within Phase 5: T006 (fill modal library section) and T007 (wire workspace handler) touch different files — run in parallel.
Final Phase: T009 and T010 are fully independent.

---

## Parallel Example: Phase 3 (US1)

```
Parallel batch 1 — independent files:
  Task T002: Create video-source-modal.tsx (new file)
  Task T003: Modify workspace/page.tsx (remove tab, add modal trigger)

Sequential after batch 1:
  Task T004: Implement upload section in video-source-modal.tsx  ← needs T002
  Task T005: Wire upload callbacks in workspace/page.tsx          ← needs T003 + T004
```

---

## Implementation Strategy

### MVP Scope (US1 + US2 only — 5 tasks)

1. Phase 2: T001
2. Phase 3: T002, T003
3. Phase 4: T004, T005
4. **Validate**: No Thư viện tab; video trigger opens modal; upload from modal works end-to-end

### Incremental Delivery

- After MVP: add US3 (T006, T007) → library selection works through modal
- After US3: add US4 (T008) → save-to-library toggle available in upload section
- Final: T009, T010 (cleanup + type safety)

---

## Notes

- No new test files (not requested; manual validation per constitution §IV)
- `VideoLibraryPanel` delete flow (spec 002 US3) is preserved unchanged — the full panel renders inside the modal with delete buttons intact
- The existing `POST /upload`, `GET /library`, `POST /sessions/from-library` backend endpoints are used as-is — zero backend changes
- `UploadZone` and `UploadingProgress` move from `page.tsx` to `video-source-modal.tsx` — not duplicated
