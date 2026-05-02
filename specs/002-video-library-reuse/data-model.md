# Data Model: Video Library & Reuse

**Phase 1 output** | Branch: `002-video-library-reuse` | Date: 2026-05-01

## Storage Layout

```
data/
├── library/
│   ├── index.json          # Metadata index (array of LibraryEntry)
│   └── <library_id>.<ext>  # Permanent video files
└── uploads/                # Existing ephemeral uploads (unchanged)
```

`index.json` is written atomically: write to `index.json.tmp` then `rename()`.

---

## Entities

### LibraryEntry (index.json element)

```json
{
  "library_id": "a1b2c3d4e5f6",
  "filename": "colonoscopy-session-01.mp4",
  "size_bytes": 524288000,
  "uploaded_at": "2026-05-01T14:56:00+07:00",
  "sha256_prefix": "e3b0c44298fc1c149afb",
  "path": "data/library/a1b2c3d4e5f6.mp4"
}
```

| Field | Type | Description |
|-------|------|-------------|
| `library_id` | `str` (12-char hex) | Stable unique identifier for this video |
| `filename` | `str` | Original filename supplied by the client |
| `size_bytes` | `int` | File size in bytes |
| `uploaded_at` | `str` (ISO 8601) | Upload timestamp with timezone |
| `sha256_prefix` | `str` (hex) | SHA-256 of first 4 MB — used for deduplication |
| `path` | `str` | Server-relative path to the video file |

**Validation rules**:
- `library_id` must be unique in the index
- `sha256_prefix` + `size_bytes` pair must be unique (dedup key)
- `filename` must have a video-compatible extension (`.mp4`, `.mov`, `.avi`, `.mkv`, `.webm`)
- `size_bytes` must be > 0

**State transitions**: A `LibraryEntry` has no explicit state field. Active-use tracking is derived at runtime from `_sessions` (in-memory): an entry is "in-use" if any live session's `video_path` resolves to its `path`.

---

### Session (existing, extended)

No schema change. A session created from a library video stores an absolute `Path` in `video_path`, identical to today's upload flow. The distinction is: library paths start with `LIBRARY_DIR`, upload paths with `UPLOAD_DIR`. The WS teardown cleanup guard already relies on this prefix difference.

```python
_sessions[video_id] = {
    "controller": None,
    "video_path": Path("/abs/path/to/data/library/<library_id>.mp4"),  # NEW: from library
    "confirmed_detections": [],
    "library_id": "a1b2c3d4e5f6",  # NEW: set when session comes from library, None otherwise
}
```

The `library_id` field in session enables the active-use check in `DELETE /library/{library_id}`.

---

## Index File Operations

| Operation | Behaviour |
|-----------|-----------|
| Read list | Load and parse `index.json`; return empty list if file absent |
| Add entry | Append to array; atomic write via temp-file rename |
| Delete entry | Filter out by `library_id`; atomic write |
| Dedup check | Scan for matching `sha256_prefix` + `size_bytes` before writing a new entry |
