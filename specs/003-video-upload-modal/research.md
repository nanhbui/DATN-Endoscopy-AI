# Research: Video Source Selection Modal

**Branch**: `003-video-upload-modal` | **Date**: 2026-05-02

No external research required — all decisions derive from reading the existing codebase (`workspace/page.tsx`, `video-library-panel.tsx`, `ws-client.ts`).

---

## Decision 1: Modal layout — two-column vs. stacked

**Decision**: Two-column (library left ~60%, upload right ~40%) on desktop; single-column stacked on narrow viewports.

**Rationale**: The library list is the primary reuse path and needs more horizontal space to show filename/size/date without truncation. The upload zone is simpler and fits well in a narrower right column. MUI `Grid` with `xs={12} md={7}` / `xs={12} md={5}` split handles responsive collapse automatically.

**Alternatives considered**:
- Tabbed (Upload tab / Library tab): Rejected — requires an extra click to switch; hides library by default which defeats the purpose of the refactor.
- Stacked vertically (upload top, library bottom): Works but wastes vertical space — library gets cut off and needs scroll on smaller screens.

---

## Decision 2: VideoLibraryPanel reuse strategy

**Decision**: Add a `showUploadButton?: boolean` prop to `VideoLibraryPanel` (default `true`). When rendered inside the modal, pass `showUploadButton={false}` to hide the "Tải lên mới" header button. The delete flow, library list, and banners are all reused unchanged.

**Rationale**: One-line prop addition, no logic duplication. The alternative (extracting a separate `LibraryVideoList` component) is over-engineering for a single callsite difference.

**Alternatives considered**:
- Extract `LibraryVideoList` sub-component: More flexible but splits a 297-line component into two files with 80% shared logic — YAGNI.
- Keep VideoLibraryPanel as-is with upload button visible in modal: Confusing UX — two upload paths visible at once.

---

## Decision 3: Upload flow inside modal — session vs. library save

**Decision**: The upload section inside the modal defaults to **session-only upload** (calls existing `uploadAndConnect` via `POST /upload`, not `POST /library/upload`). US4 (P3) adds a "Lưu vào thư viện" toggle that switches to `POST /library/upload` + `POST /sessions/from-library/{id}`. US4 is implemented in Phase 4 and guarded behind the toggle being off by default.

**Rationale**: Matches the existing user mental model — the default upload is ephemeral (session only), the library is opt-in. Avoids breaking the existing upload flow that users already know.

**Alternatives considered**:
- Always save to library on upload: Changes existing behavior without user consent — rejected.
- Remove ephemeral upload entirely: Breaking change for users who don't want to fill disk — rejected.

---

## Decision 4: Workspace sourceMode state simplification

**Decision**: Replace `'file' | 'live' | 'library'` with `'live' | 'video'` where `'video'` covers both uploaded and library-selected sessions. The toggle becomes: `video` (opens modal) | `live` (shows live input zone). Active video sessions (whether from upload or library) render the same `VideoContainer`.

**Rationale**: From the workspace rendering perspective, once a session starts, it doesn't matter whether the video came from an upload or library — the display logic is identical. Collapsing these two modes reduces state branches by 33%.

**Alternatives considered**:
- Keep three-value sourceMode: Works but adds dead code since 'library' and 'file' render identically once session starts.

---

## Decision 5: workspace/page.tsx size — extraction strategy

**Decision**: Extract `UploadZone`, `UploadingProgress`, `LiveInputZone`, `LiveStreamPanel`, `StatusDot` from `workspace/page.tsx` into `video-source-modal.tsx` where they're used, OR keep them in `page.tsx` as local components. Since `UploadZone` and `UploadingProgress` move entirely inside the modal, they should live in `video-source-modal.tsx`. `LiveInputZone`, `LiveStreamPanel`, `StatusDot` stay in `page.tsx`.

**Rationale**: Each component follows its primary callsite. `UploadZone` is never rendered outside the modal after this change, so it belongs with the modal.

**Alternatives considered**:
- Move all subcomponents to `components/`: Premature given small scale; adds import ceremony for no benefit.

---

## Decision 6: Modal open/close trigger points

**Decision**:
- **Opens**: clicking the primary UploadCloud button in the panel header OR the "Chọn file video" CTA in the right sidebar.
- **Closes**: (a) Escape / backdrop click (MUI Dialog default), (b) explicit × button, (c) auto-close on session-start (upload completes or library video selected).
- **Upload-in-progress**: backdrop click and × button are **disabled** while an upload is in progress to prevent accidental cancellation. Escape still works and triggers upload cancellation with confirmation.

**Rationale**: Prevents data loss from accidental modal closure during large video uploads (endoscopy videos can be 500+ MB).
