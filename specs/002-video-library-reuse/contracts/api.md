# API Contracts: Video Library & Reuse

**Phase 1 output** | Branch: `002-video-library-reuse` | Date: 2026-05-01

All new endpoints are added to `src/backend/api/endoscopy_ws_server.py`.
Existing endpoints (`POST /upload`, `POST /stream/connect`, `GET /session/{id}/detections`, `WS /ws/analysis/{id}`) are **unchanged**.

---

## GET /library

List all videos in the persistent library.

**Request**: No body, no query params.

**Response 200**:
```json
{
  "videos": [
    {
      "library_id": "a1b2c3d4e5f6",
      "filename": "colonoscopy-session-01.mp4",
      "size_bytes": 524288000,
      "uploaded_at": "2026-05-01T14:56:00+07:00"
    }
  ]
}
```

**Notes**: `path` and `sha256_prefix` are internal fields and are NOT exposed in this response.

---

## POST /library/upload

Upload a new video and persist it to the library. Checks for duplicates before writing.

**Request**:
- Content-Type: `application/octet-stream`
- Query param: `filename=<original filename>`
- Body: raw binary video data

**Response 200** (new entry created):
```json
{
  "library_id": "a1b2c3d4e5f6",
  "filename": "colonoscopy-session-01.mp4",
  "size_bytes": 524288000,
  "uploaded_at": "2026-05-01T14:56:00+07:00",
  "duplicate": false
}
```

**Response 200** (duplicate detected — existing entry returned):
```json
{
  "library_id": "existing_id_here",
  "filename": "colonoscopy-session-01.mp4",
  "size_bytes": 524288000,
  "uploaded_at": "2026-04-28T10:00:00+07:00",
  "duplicate": true
}
```

**Response 400**: Empty file body.
**Response 415**: File extension not in allowed list (`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`).
**Response 507**: Server disk space exhausted.

**Notes**: When `duplicate: true`, no new file is written to disk. The temp upload is discarded.

---

## POST /sessions/from-library/{library_id}

Create an analysis session from an existing library video. Returns the same shape as `POST /upload` so the frontend WebSocket flow is identical.

**Request**: No body.

**Response 200**:
```json
{
  "video_id": "session_hex_id",
  "library_id": "a1b2c3d4e5f6",
  "filename": "colonoscopy-session-01.mp4"
}
```

**Response 404**: `library_id` not found in index.

**Notes**: The returned `video_id` is used with `WS /ws/analysis/{video_id}` exactly as today. The session's `video_path` points to the library file — it is not copied.

---

## DELETE /library/{library_id}

Permanently remove a video from the library and from disk.

**Request**: No body.

**Response 200**:
```json
{ "deleted": true, "library_id": "a1b2c3d4e5f6" }
```

**Response 404**: `library_id` not found in index.

**Response 409**: Video is currently in use by an active session.
```json
{
  "detail": "Video is in use by an active session and cannot be deleted."
}
```

**Notes**: Active-use check is done by scanning `_sessions` for any session with matching `library_id`. Deletion is atomic: remove from index first, then `unlink()` the file.

---

## Frontend API Client additions (`frontend/lib/ws-client.ts`)

Three new functions mirroring the backend contracts:

```typescript
listLibraryVideos(): Promise<LibraryVideo[]>
uploadToLibrary(file: File, onProgress?: (pct: number) => void): Promise<LibraryUploadResult>
deleteLibraryVideo(libraryId: string): Promise<void>
selectLibraryVideo(libraryId: string): Promise<{ video_id: string }>
```

`LibraryVideo` shape (frontend type):
```typescript
interface LibraryVideo {
  library_id: string;
  filename: string;
  size_bytes: number;
  uploaded_at: string;   // ISO 8601
}
```

`LibraryUploadResult`:
```typescript
interface LibraryUploadResult {
  library_id: string;
  filename: string;
  size_bytes: number;
  uploaded_at: string;
  duplicate: boolean;
}
```

`AnalysisContext` addition:
```typescript
selectFromLibrary: (libraryId: string) => Promise<void>
```
Calls `selectLibraryVideo(libraryId)` then `connectWs(video_id)` — identical to `uploadAndConnect` after the upload step.
