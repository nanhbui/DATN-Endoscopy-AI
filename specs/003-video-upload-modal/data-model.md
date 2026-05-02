# Data Model: Video Source Selection Modal

**Branch**: `003-video-upload-modal` | **Date**: 2026-05-02

Pure frontend refactor — no new backend entities or API changes. This document describes the component state model and prop interfaces.

---

## Component State Model

### VideoSourceModal (new component)

| State field | Type | Initial | Description |
|-------------|------|---------|-------------|
| `isUploading` | `boolean` | `false` | True while XHR upload is in progress |
| `uploadProgress` | `number` | `0` | 0–100, drives LinearProgress inside modal |
| `uploadError` | `string \| null` | `null` | Inline error message for unsupported type / server error |
| `saveToLibrary` | `boolean` | `false` | US4 toggle — when true, routes to `POST /library/upload` |

Modal open/close state lives in the **parent** (`workspace/page.tsx`) as `isSourceModalOpen: boolean`.

### workspace/page.tsx — state changes

| State field | Before | After |
|-------------|--------|-------|
| `sourceMode` | `'file' \| 'live' \| 'library'` | `'video' \| 'live'` |
| `isSourceModalOpen` | *(new)* | `boolean`, default `false` |

All other state (`videoFile`, `videoUrl`, `isUploading`, etc.) remains unchanged.

---

## Prop Interfaces

### VideoSourceModal

```typescript
interface VideoSourceModalProps {
  open: boolean;
  onClose: () => void;
  onUploadStart: (file: File) => void;      // called when file selected, passes file to parent
  onUploadProgress: (pct: number) => void;  // drives parent upload progress state
  onSessionStart: () => void;               // called after library selection starts session
}
```

### VideoLibraryPanel (modified)

```typescript
interface VideoLibraryPanelProps {
  onSelect: (libraryId: string) => void;
  showUploadButton?: boolean;   // default: true — hide when rendered inside modal
}
```

---

## Workspace Source Mode State Transitions

```
IDLE (sourceMode='video')
  ├─ user clicks upload trigger → isSourceModalOpen=true
  │   ├─ user selects file → upload starts → modal stays open (progress shown)
  │   │   └─ upload done → modal closes, session starts (sourceMode stays 'video')
  │   ├─ user clicks library row → session starts → modal closes
  │   └─ user dismisses modal → isSourceModalOpen=false (no change)
  └─ user clicks live → sourceMode='live'

ACTIVE SESSION (isConnected=true)
  └─ upload trigger button disabled — modal cannot be opened
```

---

## No backend model changes

All backend entities (`LibraryEntry`, session `library_id` field) are unchanged from spec 002. The modal reuses all existing API endpoints:

- `GET /library` — library list on modal open
- `POST /upload` — session-only upload (default upload path)
- `POST /library/upload` — library-save upload (US4, when toggle is on)
- `POST /sessions/from-library/{id}` — start session from library
