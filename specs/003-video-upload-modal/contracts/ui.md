# UI Contracts: Video Source Selection Modal

**Branch**: `003-video-upload-modal` | **Date**: 2026-05-02

---

## VideoSourceModal Component

**File**: `frontend/components/video-source-modal.tsx`
**Export**: `VideoSourceModal` (named export)

### Props

```typescript
interface VideoSourceModalProps {
  open: boolean;
  onClose: () => void;
  onUploadStart: (file: File) => void;
  onUploadProgress: (pct: number) => void;
  onSessionStart: () => void;
}
```

### Behavior Contracts

| Trigger | Expected behavior |
|---------|------------------|
| `open=true` | Dialog renders; library list fetch begins |
| `open=false` | Dialog unmounts; in-flight library fetch is ignored |
| File selected (valid type) | Calls `onUploadStart(file)`, shows progress bar, disables backdrop/× close |
| Upload progress updates | Calls `onUploadProgress(pct)` (0–100) |
| Upload complete | Calls `onSessionStart()`, then parent closes modal via `onClose()` |
| Library row clicked | Calls `selectFromLibrary(libraryId)`, calls `onSessionStart()`, parent closes modal |
| Escape / backdrop click (no upload in progress) | Calls `onClose()` |
| Escape / backdrop click (upload in progress) | Upload is aborted; calls `onClose()` |
| Unsupported file type dropped | Shows inline error in upload section; modal stays open |

### Layout Contract

```
┌─────────────────────────────────────────────────────────┐
│  [×]                   Chọn nguồn video                  │
├────────────────────────────┬────────────────────────────┤
│  Thư viện video  (md:7)    │  Tải video mới  (md:5)     │
│  ┌──────────────────────┐  │  ┌──────────────────────┐  │
│  │  video row …         │  │  │  UploadZone (drag)   │  │
│  │  video row …         │  │  │                      │  │
│  │  (empty state)       │  │  │  [progress bar]      │  │
│  └──────────────────────┘  │  │  [error message]     │  │
│                            │  └──────────────────────┘  │
│                            │  ☐ Lưu vào thư viện (P3)   │
└────────────────────────────┴────────────────────────────┘
```

- Max width: `960px`; max height: `80vh`
- On `xs`/`sm` screens: two-column collapses to single-column (library above, upload below)
- MUI `Dialog` with `maxWidth="md" fullWidth`

---

## VideoLibraryPanel Component (modified)

**File**: `frontend/components/video-library-panel.tsx`
**Change**: Add optional `showUploadButton` prop

```typescript
interface VideoLibraryPanelProps {
  onSelect: (libraryId: string) => void;
  showUploadButton?: boolean;  // default: true
}
```

### Behavior Contract

| `showUploadButton` | Effect |
|-------------------|--------|
| `true` (default) | Existing behavior — "Tải lên mới" button visible in panel header |
| `false` | "Tải lên mới" button and hidden file input are not rendered; all other behavior unchanged |

---

## workspace/page.tsx (modified)

### Removed controls

- `<ToggleButton value="library">` — removed entirely
- `sourceMode === 'library'` render branch — removed
- Import of `BookOpen` (lucide-react) — removed if no other use

### Added controls

- `isSourceModalOpen: boolean` state
- `<VideoSourceModal open={isSourceModalOpen} ... />` rendered at the page root
- Upload trigger (UploadZone click / right-panel CTA) → `setIsSourceModalOpen(true)` instead of file picker

### sourceMode simplification

```typescript
// Before
const [sourceMode, setSourceMode] = useState<'file' | 'live' | 'library'>('file');

// After
const [sourceMode, setSourceMode] = useState<'video' | 'live'>('video');
```

### Upload trigger button (right sidebar)

When `!videoUrl` and `sourceMode === 'video'`:

```
<MuiButton onClick={() => setIsSourceModalOpen(true)}>
  Chọn hoặc tải video
</MuiButton>
```

Button is **disabled** when `pipelineState !== 'IDLE'`.

---

## No new API contracts

All backend endpoints are unchanged. See `specs/002-video-library-reuse/contracts/api.md` for the full API spec.
