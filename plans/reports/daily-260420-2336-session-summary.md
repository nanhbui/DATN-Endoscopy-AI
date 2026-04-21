# Báo cáo làm việc — 20/04/2026

## Tổng quan

Phiên làm việc tập trung triển khai hệ thống AI nội soi lên **GPU server** (`emie@10.8.0.7`) và sửa toàn bộ luồng từ GStreamer pipeline → YOLO detection → bounding box overlay → hands-free voice workflow.

---

## 1. Triển khai lên GPU Server

### Vấn đề
- `make remote-dev` thất bại vì yêu cầu mật khẩu `sudo` cho `docker compose`
- `REMOTE_DIR` trong Makefile trỏ sai tên thư mục (`~/endoscopy` thay vì `~/DATN_ver0`)
- `uvicorn` không tìm thấy trong PATH

### Đã sửa
| File | Thay đổi |
|------|---------|
| `Makefile` | `REMOTE_DIR := ~/endoscopy` → `~/DATN_ver0` |
| `Makefile` | Bỏ `sudo` khỏi các lệnh `docker compose` |
| `Makefile` | `UVICORN := $(VENV)/bin/uvicorn` → `$(VENV)/bin/python -m uvicorn` |

---

## 2. Cài đặt Python Dependencies

### Vấn đề
- `pyaudio` build fail vì không có `portaudio19-dev` trên server (không có quyền sudo để cài)
- `numpy` conflict: `numpy<2.0.0` mâu thuẫn với `opencv-python` mới hơn
- `python-multipart` thiếu → FastAPI không nhận file upload

### Đã sửa
| File | Thay đổi |
|------|---------|
| `requirements.txt` | Xóa `pyaudio>=0.2.13` |
| `requirements.txt` | `numpy>=1.24.0,<2.0.0` → `numpy>=1.24.0` (bỏ upper bound) |
| `requirements.txt` | Thêm `python-multipart>=0.0.9` |

---

## 3. GStreamer Pipeline

### Vấn đề
- **NVMM buffers**: `uridecodebin`/`decodebin` dùng `nvv4l2decoder` → output là 64-byte NVMM memory handle, không phải pixel data → frame shape sai, reshape crash
- **not-negotiated error**: caps `video/x-raw,format=BGR` bị back-propagate vào `decodebin`, conflict với decoder
- **Invalid small buffers**: Subtitle track trong video cũng chui vào appsink → buffer quá nhỏ, reshape crash với `Fatal: reshape(h*3//2, w) — buffer too small`

### Đã sửa (`pipeline_controller.py`)
```python
# Pipeline mới: dùng avdec_h264 (CPU decoder) thay vì nvv4l2decoder
pipeline_str = 'filesrc location="..." ! qtdemux ! h264parse ! avdec_h264 ! videoconvert ! queue ! appsink'
```
- Bỏ `caps=video/x-raw,format=BGR` khỏi appsink (gây back-propagation)
- Convert format trong Python: detect NV12/I420 → `cv2.cvtColor(yuv, COLOR_YUV2BGR_NV12/I420)`
- Thêm size check: `if len(raw) < h * w: continue` → loại buffer rác (subtitle track)

> **Lưu ý**: Dùng CPU decoder (`avdec_h264`) chứ không phải GPU decoder — GPU vẫn được dùng cho YOLO inference.

---

## 4. YOLO Model

### Vấn đề
- **FP16 dtype mismatch**: Model load FP16 nhưng input tensor FP32 → RuntimeError khi inference

### Đã sửa
```python
try:
    model.half()
    model(dummy, verbose=False, conf=0.99)  # warmup test
    # FP16 OK
except Exception:
    model.float()  # fallback FP32
    model(dummy, verbose=False, conf=0.99)
```

---

## 5. Bounding Box

### Vấn đề
- **Bbox không hiển thị**: `FRAME_W/H` trong frontend set sai → tọa độ normalize sai
- **Bbox quá nhỏ**: Model detect tổn thương nhỏ, bbox chiếm < 5% frame
- **Bbox quá to / tràn màn hình**: Padding 40% áp dụng cả cho bbox lớn

### Đã sửa
| Vị trí | Sửa |
|--------|-----|
| `AnalysisContext.tsx` | `FRAME_W = 1920`, `FRAME_H = 1080` (match frame size thực) |
| `pipeline_controller.py` | Thêm 15% padding **chỉ** khi bbox < 20% diện tích frame |

```python
if (_bw * _bh) / (_fw * _fh) < 0.20:
    _pad_x, _pad_y = _bw * 0.15, _bh * 0.15
    xyxy = [max(0.0, _x1-_pad_x), ...]
```

---

## 6. Session Management

### Vấn đề
- Khi backend restart, frontend nhận `ERROR: Session not found` → loop lỗi vô hạn, không reset

### Đã sửa (`AnalysisContext.tsx`)
```tsx
case "ERROR":
  if (evt.data.message?.includes("Session not found")) {
    wsRef.current?.disconnect();
    setIsConnected(false);
    setPipelineState("IDLE");
    setVideoId(null);
  }
```

---

## 7. Backend Health Check

### Vấn đề
- Khi backend offline, frontend không báo gì → user không biết lý do phân tích không chạy

### Đã sửa (`page.tsx`)
- Thêm health check `GET /health` mỗi 10s
- Hiển thị banner đỏ khi backend không kết nối được

---

## 8. Hands-Free Voice Workflow

### Vấn đề chính
> "khi detect được rồi thì mic detect giọng nói lại không bật / mà nếu có bật và transcript được thì lại không nhận biết được tình huống để auto chọn Bỏ Qua hay Giải thích thêm"

**Root cause:**
1. `startListening()` chỉ được gọi khi user click "Bắt đầu AI"
2. Khi video được upload → pipeline auto-start (`PLAYING`) → button "Bắt đầu AI" bị **disable** (`isPlaying=true`) → mic không bao giờ được bật
3. Không có cơ chế tự bật mic khi state chuyển sang `PAUSED_WAITING_INPUT`

### Đã sửa (`page.tsx`)

**Fix 1** — Auto-start khi upload/live connect:
```tsx
await uploadAndConnect(file, setUploadProgress);
if (voiceSupported) startListening(); // ← thêm dòng này
```

**Fix 2** — Auto-restart khi detection dừng pipeline:
```tsx
useEffect(() => {
  if (pipelineState === 'PAUSED_WAITING_INPUT' && voiceSupported && !isVoiceListening) {
    startListening();
  }
}, [pipelineState, voiceSupported, isVoiceListening, startListening]);
```

> Intent routing (`BO_QUA` → `ignoreDetection()`, `GIAI_THICH` → `explainMore()`) đã đúng từ trước — chỉ thiếu mic được bật.

---

## 9. Voice Error Handling

### Vấn đề
- `no-speech`: Chrome tự timeout khi không nghe thấy âm thanh → bắn `onerror` với `error: "no-speech"` → UI hiện "Lỗi mic: no-speech" gây hiểu nhầm
- `InvalidStateError`: Chrome đôi khi bắn `onend` khi recognition vẫn đang chạy → `restart()` bị gọi → crash với `InvalidStateError: recognition has already started`

### Đã sửa (`use-voice-control.ts`)
```ts
// Bỏ qua no-speech và aborted — là normal behavior của Chrome
if (event.error === "no-speech" || event.error === "aborted") return;

// Bỏ qua InvalidStateError khi restart
} catch (e) {
  if (!(e instanceof DOMException && e.name === "InvalidStateError")) {
    console.warn("[VoiceControl] restart failed:", e);
  }
}
```

---

## Files đã thay đổi

| File | Loại thay đổi |
|------|--------------|
| `Makefile` | Config: remote dir, uvicorn path, bỏ sudo |
| `requirements.txt` | Deps: bỏ pyaudio, fix numpy, thêm multipart |
| `src/backend/pipeline/pipeline_controller.py` | Core: GStreamer pipeline, YOLO FP16 fallback, bbox padding |
| `frontend/context/AnalysisContext.tsx` | Fix: FRAME_W/H, session-not-found reset |
| `frontend/app/workspace/page.tsx` | Feature: health check banner, auto-start mic, PAUSED effect |
| `frontend/hooks/use-voice-control.ts` | Fix: no-speech false error, InvalidStateError on restart |

**Commit:** `fccd95a` — pushed to `origin/main`

---

## Trạng thái hiện tại

- Backend chạy trên GPU server (port 8001), YOLO dùng CUDA FP32
- Frontend chạy local, kết nối remote backend
- Detection + bounding box hoạt động đúng
- Voice workflow: mic tự bật khi upload + tự bật lại khi detection → đang test

## Câu hỏi chưa giải quyết

- Docker trên GPU server cần `sudo` nhưng `emie` không có password sudo → nếu cần rebuild Docker image phải nhờ admin
- Frontend port 3000 chưa chạy trên server (chỉ BE port 8001) — nếu cần deploy full stack cần giải quyết vấn đề Docker permission
