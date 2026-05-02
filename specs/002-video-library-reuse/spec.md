# Feature Specification: Video Library & Reuse

**Feature Branch**: `002-video-library-reuse`  
**Created**: 2026-05-01  
**Status**: Draft  
**Input**: User description: "lưu video upload lên server - dùng lại các video đã upload lên server, chỉnh cả UI để có phần lựa chọn lại video luôn. Hiện tại mỗi lần sử dụng đều phải upload lại một video như nhau, làm tốn disk của server."

## User Scenarios & Testing *(mandatory)*

### User Story 1 - Select Previously Uploaded Video (Priority: P1)

A user opens the application to start an analysis session. Instead of uploading a new video file, they can see a list of videos that have been uploaded to the server in the past. They pick one from the list and proceed directly to processing — no re-upload required.

**Why this priority**: This is the core problem being solved. Eliminating redundant uploads saves server disk space and speeds up the user workflow significantly.

**Independent Test**: Open the video source selection screen, verify the library list appears with at least one previously uploaded entry, click it, and confirm the session starts using that video without any upload step.

**Acceptance Scenarios**:

1. **Given** the server has at least one previously uploaded video, **When** the user opens the video source selection UI, **Then** a browsable list of previously uploaded videos is displayed with enough metadata (name, upload date, file size) to identify each one.
2. **Given** the video library list is visible, **When** the user selects a video from the list, **Then** the system uses that video as the source for the current session without triggering a new upload.
3. **Given** the server has no previously uploaded videos, **When** the user opens the video source selection UI, **Then** the library list shows an empty state with a clear prompt to upload a new video.

---

### User Story 2 - Upload New Video and Save to Library (Priority: P2)

A user uploads a brand-new video file. The system stores it persistently on the server under a recognizable name and makes it available in the library for all future sessions.

**Why this priority**: New uploads must feed the library; without this, the library never grows. It is also the fallback path when no prior video exists.

**Independent Test**: Upload a video, navigate away, return to the selection screen, and confirm the newly uploaded video appears in the library list.

**Acceptance Scenarios**:

1. **Given** the user selects "Upload new video" and provides a valid video file, **When** the upload completes, **Then** the video is saved to the server's persistent video library and immediately appears in the video list.
2. **Given** a video with the same filename already exists in the library, **When** the user uploads a new file with that name, **Then** the system either renames the new entry to avoid collision or prompts the user to confirm overwrite.
3. **Given** the user uploads a file that is not a supported video format, **When** the upload is attempted, **Then** the system rejects the file and shows a clear error message identifying accepted formats.

---

### User Story 3 - Manage Library (Delete Videos) (Priority: P3)

A user with sufficient permissions can remove videos from the library to free up server disk space when videos are no longer needed.

**Why this priority**: Without deletion, disk savings from deduplication will eventually be eroded by accumulating unused videos. Management is needed for long-term storage health.

**Independent Test**: Delete a video from the library list and verify it no longer appears and is no longer accessible for selection.

**Acceptance Scenarios**:

1. **Given** a video exists in the library, **When** the user chooses to delete it, **Then** the video is permanently removed from the list and from server storage.
2. **Given** a video is actively in use by the current session, **When** the user attempts to delete it, **Then** the system prevents deletion and explains why.

---

### Edge Cases

- What happens when the server runs out of disk space during a new upload?
- How does the system behave if a library video file is missing or corrupted on disk (entry exists in list but file is gone)?
- What happens when two users attempt to delete the same video simultaneously?
- How does the UI handle a very large library (50+ videos) — scrolling, pagination, or search?

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: System MUST maintain a persistent library of all videos uploaded to the server, accessible across sessions.
- **FR-002**: System MUST display the video library list in the video source selection UI, showing each video's name, upload date, and file size.
- **FR-003**: Users MUST be able to select any video from the library as the source for the current session without re-uploading.
- **FR-004**: System MUST prevent duplicate storage — if the exact same file is uploaded again, the system MUST detect and reuse the existing entry rather than storing a second copy. Duplicate detection is based on SHA-256 hash of the first 4 MB of file content combined with total file size. Filename alone does NOT determine uniqueness: two files with the same name but different content are stored as separate entries; two files with different names but identical content are treated as duplicates. When a duplicate is detected, the system MUST NOT silently reuse the existing entry without telling the user — the upload response MUST include `"duplicate": true` and the UI MUST display a visible notification (e.g., a banner: "Video này đã có trong thư viện").
- **FR-005**: System MUST allow users to upload new videos that are then automatically added to the persistent library.
- **FR-006**: System MUST allow deletion of videos from the library, with confirmation required before permanent removal.
- **FR-007**: System MUST block deletion of a video that is currently active in an ongoing session. A video is considered "in-use" if at least one active WebSocket session exists whose `library_id` matches the video being deleted. Multiple sessions may reference the same library video simultaneously; deletion is blocked as long as any one of them is active. The 409 response body MUST include a human-readable reason ("Video đang được sử dụng, không thể xóa").
- **FR-008**: System MUST display a clear empty state when the library has no videos.
- **FR-009**: System MUST show an appropriate error when a non-video file is uploaded.
- **FR-010**: System MUST show an appropriate error when upload fails due to insufficient server storage.
- **FR-011**: The existing `POST /upload` ephemeral flow MUST remain unchanged. Videos uploaded via the ephemeral path are deleted from server storage when their session ends and are NOT added to the persistent library. Only `POST /library/upload` persists video files to the library. The two flows are independent and MUST NOT be conflated.

### Key Entities

- **Video Entry**: A record in the video library representing one stored video. Key attributes: unique identifier, original filename, upload timestamp, file size, SHA-256 prefix (dedup key), storage path on server. Status (available / in-use / corrupted) is derived at runtime — not stored — and reflects whether the file exists on disk and whether any active session holds a reference to it. Duration is not stored (out of scope for v1).
- **Session**: An analysis session that references exactly one Video Entry as its source. A session holds a reference to the video; it does not own the video file itself.

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: Users never need to upload the same video twice — 100% of repeat uploads where the file's SHA-256 hash of the first 4 MB and file size match an existing library entry are served from the library without a new upload. Files whose first 4 MB differ from all existing entries are treated as new uploads regardless of visual similarity; this is a known limitation of the prefix-hash dedup strategy.
- **SC-002**: Starting a session using a library video takes under 5 seconds from selection to session ready (vs. waiting for a full upload).
- **SC-003**: Total server disk usage for video storage decreases or stays flat when the same video would previously have been uploaded multiple times in repeated sessions.
- **SC-004**: 90% of users can locate and select a previously uploaded video from the library without assistance on first attempt.
- **SC-005**: The video library UI loads and displays the list within 2 seconds, regardless of how many videos are stored.

## Assumptions

- All users of the system share the same video library (there is no per-user private library). If per-user isolation is needed, that is a future enhancement.
- Supported video formats are the same formats the system already accepts for upload (no new format support is introduced by this feature).
- Videos in the library are intended to be reused across multiple sessions, not single-use; deletion is an explicit manual action.
- The system currently has an upload flow; this feature extends it with a "select from library" alternative path rather than replacing it.
- Mobile responsiveness of the video library UI is desirable but not a hard requirement for this version.
- There is no quota or limit on the number of videos a user can store in the library in this version.
- The server runs as a single-process asyncio application; concurrent HTTP requests (including simultaneous DELETE calls) are serialized by the event loop. A second DELETE on the same `library_id` will receive a 404 (already removed by the first) — no explicit locking is needed. This assumption is invalidated if the server is ever run with multiple workers.
