# Feature Specification: Video Source Selection Modal

**Feature Branch**: `003-video-upload-modal`
**Created**: 2026-05-02
**Status**: Draft
**Input**: Replace the video library tab with a unified popup modal that appears when clicking "Tải video lên để phân tích", containing both upload-new and reuse-from-library options.

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Open Source Selection Modal (Priority: P1)

A clinician clicks the primary "Tải video lên để phân tích" button on the workspace and a full-screen overlay popup appears. The popup has two clearly separated sections: "Tải video mới" (upload a new file) and "Chọn từ thư viện" (pick a previously uploaded video). The existing tab-based toggle that separated File / Live / Library is replaced by this modal; "Live stream" becomes a separate button unrelated to the modal.

**Why this priority**: This is the entry point for all video analysis sessions. Replacing the tab UI with a modal is the core UX change requested. Without it, nothing else in this feature ships.

**Independent Test**: Open the workspace page — there is no "Thư viện" tab in the toggle. Click the video upload button — a modal dialog opens showing both the upload area and the library list side by side (or stacked). Closing the modal returns to the idle workspace.

**Acceptance Scenarios**:

1. **Given** the workspace is idle, **When** the user clicks the video upload trigger button, **Then** a modal dialog opens that covers the video area with two sections visible.
2. **Given** the modal is open, **When** the user presses Escape or clicks outside the modal, **Then** the modal closes and the workspace returns to its previous state.
3. **Given** the modal is open, **When** the user clicks the close (×) button, **Then** the modal closes immediately.

---

### User Story 2 — Upload New Video via Modal (Priority: P1)

Inside the modal, the "Tải video mới" section contains a file-drop zone / file picker identical in function to the current upload area. The user selects or drags a video file, a progress bar appears inside the modal, and when upload + analysis starts the modal closes automatically.

**Why this priority**: Upload is the primary existing flow — the modal must not break it. Shares P1 priority with opening the modal because together they form the complete replacement of the existing upload flow.

**Independent Test**: Open modal → drag-and-drop a video file into the upload zone → progress bar appears → modal closes → analysis session starts in the workspace.

**Acceptance Scenarios**:

1. **Given** the modal is open, **When** the user selects a valid video file, **Then** an upload progress indicator appears inside the modal.
2. **Given** the upload has started, **When** the upload completes, **Then** the modal closes automatically and the analysis session begins in the workspace.
3. **Given** the modal is open, **When** the user drops an unsupported file type, **Then** an inline error message is shown inside the modal without closing it.

---

### User Story 3 — Select Library Video via Modal (Priority: P2)

The "Chọn từ thư viện" section inside the modal lists all previously uploaded library videos (filename, size, upload date). The user clicks a video row and the analysis session starts immediately — the modal closes automatically.

**Why this priority**: This is the core reuse feature that motivated the library. Lower than upload-in-modal only because it builds on the existing library backend.

**Independent Test**: With at least one video in the library, open the modal — the library list is visible. Click a library video row — the modal closes and the analysis session starts without any file upload.

**Acceptance Scenarios**:

1. **Given** the modal is open and the library has at least one video, **When** the library section is visible, **Then** each video entry shows filename, size, and upload date.
2. **Given** the library section is visible, **When** the user clicks a video row, **Then** the modal closes and the analysis session starts using that video.
3. **Given** the modal is open and the library is empty, **Then** the library section shows an empty state message prompting the user to upload a video first.

---

### User Story 4 — Upload to Library via Modal (Priority: P3)

Inside the modal, there is an "Lưu vào thư viện" option (could be a checkbox or a dedicated upload-to-library button). When chosen, the video is saved permanently and appears in future library lists.

**Why this priority**: Nice-to-have enhancement inside the modal. The standalone library upload button from spec 002 already covers this flow; the modal just needs a path to it.

**Independent Test**: Open modal → upload a video with "Lưu vào thư viện" selected → close modal → reopen modal → video appears in the library section.

**Acceptance Scenarios**:

1. **Given** the modal is open, **When** the user uploads a video with the library-save option selected, **Then** the video is saved permanently and appears in the library section on subsequent modal opens.
2. **Given** a duplicate video is uploaded via the library-save option, **Then** an inline message informs the user the video already exists and no duplicate is created.

---

### Edge Cases

- What happens when the library fetch fails on modal open? → Show inline error in the library section; the upload section remains functional.
- What happens if the user starts an upload and then closes the modal? → The upload is cancelled and the workspace stays idle.
- What happens when the modal is opened while an analysis session is already active? → The modal button is disabled or hidden during an active session.
- What if the library is loading slowly (network delay)? → The library section shows a loading spinner while the upload section is already usable.

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The workspace MUST provide a single trigger button/area that opens the source selection modal when clicked, replacing the current tab-toggle approach for file and library sources.
- **FR-002**: The modal MUST display two sections: a file upload section and a library section, both visible without scrolling on typical screen sizes.
- **FR-003**: The modal MUST close automatically when the user successfully starts an analysis session (via upload or library selection).
- **FR-004**: The modal MUST close when the user presses Escape, clicks the backdrop outside the modal, or clicks a dedicated close button.
- **FR-005**: The upload section inside the modal MUST support file selection via click (file picker) and drag-and-drop, with an upload progress indicator.
- **FR-006**: The library section inside the modal MUST show all saved videos with filename, size, and upload date, loaded on modal open.
- **FR-007**: Clicking a library video row MUST start the analysis session and close the modal without requiring any additional confirmation.
- **FR-008**: The library section MUST show an empty state message when no videos are saved.
- **FR-009**: The modal trigger button MUST be disabled/hidden while an analysis session is active to prevent accidental interruption.
- **FR-010**: The live stream source (camera / RTSP) MUST remain accessible without going through the modal — it stays as a separate control on the workspace.
- **FR-011**: If the library section fails to load, an inline error MUST appear in that section only; the upload section MUST remain fully functional.

### Key Entities

- **SourceSelectionModal**: The overlay dialog containing both upload and library sections; opened by user action, closed on session-start or explicit dismiss.
- **UploadSection**: The area within the modal for selecting and uploading a new video file; mirrors existing upload UX but contained within the modal.
- **LibrarySection**: The area within the modal listing saved library videos; reuses the `VideoLibraryPanel` list logic from spec 002.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users can go from clicking the trigger button to starting a video analysis session in under 3 clicks for both new uploads and library reuse.
- **SC-002**: The modal opens and the library list is visible within 1 second on the clinical network.
- **SC-003**: 100% of the existing upload and library-reuse flows work through the modal without any backend changes.
- **SC-004**: The workspace has no "Thư viện" tab in the source toggle after this change — one fewer interaction mode to learn.
- **SC-005**: The modal is dismissible at any point (Escape, backdrop click, ×) without side effects on workspace state.

## Assumptions

- The live stream / camera source toggle remains outside the modal and is out of scope for this change.
- The backend library API (`GET /library`, `POST /sessions/from-library/{id}`, `POST /library/upload`) is already implemented (spec 002) and requires no changes.
- The modal replaces the current "Thư viện" third tab entirely; the `VideoLibraryPanel` component is reused inside the modal rather than deleted.
- The delete-from-library flow (spec 002, US3) is accessible from within the library section of the modal.
- Mobile/touch support uses the same modal; no separate mobile layout is required in this spec.
- The modal design follows the existing MUI component library and color palette already in use.
