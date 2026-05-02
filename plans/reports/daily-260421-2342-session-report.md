---
name: Daily Session Report – 21/04/2026
description: Bugs fixed in voice control, bbox detection, LLM rendering, and pipeline sensitivity
type: project
---

# Daily Report – 21/04/2026

## 1. Voice Command – Transcript Accumulation (BO_QUA false fire)

**Lỗi:** User nói "bỏ qua đi giải thích thêm" trong một hơi. Chrome `SpeechRecognition` với `continuous=true` tích lũy interim text theo từng từ: `"bỏ qua"` → `"bỏ qua đi"` → `"bỏ qua đi giải thích thêm"`. `quickMatch` match chuỗi đầy đủ → BO_QUA fire liên tục.

**Nguyên nhân:** `lastFiredRef` (string) so sánh toàn bộ chuỗi mới vs chuỗi cũ. Mỗi từ mới tạo ra chuỗi khác → luôn pass check → fire lại.

**Fix:** Thay `lastFiredRef<string>` bằng `lastFiredEndRef<number>` lưu offset đã xử lý. Interim chỉ `quickMatch` trên **delta** (`interim.slice(lastFiredEndRef.current)`). Sau khi fire intent, gọi `recognition.stop()` để flush buffer Chrome; `onend` tự restart sau 300ms với slate sạch.

---

## 2. Voice Command – Từ đơn gây false positive

**Lỗi:** Các từ đơn trong QUICK_KEYWORDS (`"qua"`, `"bỏ"`, `"đúng"`, `"giải"`, `"thích"`) match sai khi user nói câu thường chứa những từ đó.

**Fix:** Xóa tất cả từ đơn phổ biến, chỉ giữ cụm từ rõ ràng: `"bỏ qua"`, `"giải thích"`, `"xác nhận"`, `"đúng rồi"`, v.v.

---

## 3. Bbox Detection – Scale mismatch

**Lỗi:** Model YOLO train trên viewport-only crop nhưng nhận full frame 1920×1080 → bbox chiếm 47–60% frame, sai vị trí, detect overlay thiết bị góc trên phải.

**Nguyên nhân:** Frame đưa thẳng vào model không qua crop → model thấy data distribution khác lúc train.

**Fix:**
- Crop trước inference: `frame_inf = frame[:, :VIEWPORT_W]` với `VIEWPORT_W=1300` (override `ENDOSCOPY_VIEWPORT_W`)
- Circular viewport filter: bỏ detection có center ngoài circle `(cx=640, cy=540, r=520)` → loại overlay NF/LCI ở (1250, 35)
- Bbox clamping: cap 60% mỗi chiều + 2% margin từ cạnh
- Skip oversized bbox > 70% frame area

---

## 4. HMR Rebuild Loop – ws-client deleted module

**Lỗi:** Console spam `[webpack] ws-client deleted module` mỗi khi Next.js HMR rebuild → mic unstable (recognition stop/start liên tục).

**Nguyên nhân:** `await import('@/lib/ws-client')` bên trong `useEffect` tạo circular HMR dependency.

**Fix:** Đổi sang static import ở top file: `import { API_BASE } from '@/lib/ws-client'`.

---

## 5. LLM Output – Markdown không render

**Lỗi:** Backend trả markdown có `**bold**`, `- bullet`, nhưng FE hiển thị raw text xấu.

**Fix:** Thêm `react-markdown` package, wrap LLM output trong `<ReactMarkdown>` component.

---

## 6. Post-LLM Flow – Không có nút confirm/ignore

**Lỗi:** Sau khi LLM giải thích xong, không có UI để doctor confirm hoặc bỏ qua. Pipeline treo ở `PROCESSING_LLM`.

**Fix:**
- `AnalysisContext`: `LLM_DONE` handler set `setPipelineState("PAUSED_WAITING_INPUT")` thay vì chỉ set `isListeningVoice(false)`
- Thêm `confirmDetection()` action gửi `ACTION_CONFIRM` + reset UI về `PLAYING`
- `page.tsx`: sau LLM done, hiển thị [Bỏ qua] + [Xác nhận ✓] thay vì [Giải thích] + [Bỏ qua]

---

## 7. Backend Reconnect – Full page reload

**Lỗi:** Khi BE restart, FE không tự reconnect, user phải reload trang → mất toàn bộ session state.

**Fix:** Yellow banner "Mất kết nối – Đang thử kết nối lại…" với nút "Kết nối lại" thay vì full reload. Detect offline→online bằng `prevBackendReachable` ref.

---

## 8. "Phân tích lại" – Giữ UI cũ

**Lỗi:** Nhấn "Phân tích lại" sau khi BE reload → UI giữ detection/LLM của lần chạy trước.

**Fix:** Gọi `resetAnalysis()` + `setTranscriptLog([])` + `URL.revokeObjectURL(old)` trước khi upload lại.

---

## 9. Detection Sensitivity – Thiếu detection

**Lỗi:** Model bỏ sót nhiều lesion thật.

**Nguyên nhân:** `CONFIDENCE_THRESHOLD = 0.65` quá cao.

**Fix:** Hạ xuống 0.45, env override `ENDOSCOPY_CONF` để tune mà không cần sửa code.

---

## Files thay đổi

| File | Thay đổi |
|------|----------|
| `frontend/hooks/use-voice-control.ts` | Delta-based intent matching, restart-on-fire, tighten keywords |
| `frontend/context/AnalysisContext.tsx` | LLM_DONE → PAUSED_WAITING_INPUT, confirmDetection action |
| `frontend/app/workspace/page.tsx` | ReactMarkdown, reconnect banner, auto-start mic, reset flow |
| `frontend/package.json` | react-markdown dependency |
| `src/backend/pipeline/pipeline_controller.py` | Viewport crop, circular filter, bbox clamp, conf=0.45 |
| `src/backend/api/endoscopy_ws_server.py` | ACTION_CONFIRM in WS protocol doc |

## Commit

`c58dfc9` – `fix: voice dedup, bbox filter, LLM markdown, detection sensitivity`
