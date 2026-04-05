# KẾ HOẠCH TRIỂN KHAI HỆ THỐNG PHÁT HIỆN TỔN THƯƠNG NỘI SOI

## 1. TỔNG QUAN

Hệ thống phát hiện tổn thương nội soi với tích hợp voice control và smart ignore.

### Các branch chính:
- feat/llava-finetune: Tinh chỉnh LLaVA-Med cho y học
- feat/voice-whisper: Xử lý voice command với Whisper + IntentClassifier
- feat/frame-skipping: Bỏ qua frame trùng lặp thông minh
- feat/dataset-preparation: Chuẩn bị dữ liệu HyperKvasir

## 2. KIẾN TRÚC HỆ THỐNG

```
User (Voice) ───► [Whisper] ───► [IntentClassifier] ───► [FrameSkipper]
     │
     └────────────► [LLM Explanation]

[YOLO Detector] ───► [GStreamer Pipeline] ───► [Video Stream]

[FAISS Store] ←→ [Smart Ignore Logic] ←→ [Database]
```

## 3. KẾ HOẠCH TRIỂN KHAI

### Giai đoạn 1: Xây dựng luồng xử lý chính (Tuần 1-2)
- Tích hợp GStreamer pipeline với YOLO detector
- Xây dựng hệ thống voice command với Whisper
- Tích hợp LLM explanation cho các tổn thương được phát hiện

### Giai đoạn 2: Tối ưu Smart Ignore (Tuần 3)
- Xây dựng FAISS vector store để lưu đặc trưng frame bị bỏ qua
- Tích hợp logic so khớp frame tương tự để tránh phát hiện lại

### Giai đoạn 3: Hoàn thiện báo cáo và UI (Tuần 4)
- Tự động tổng hợp báo cáo sau khi video kết thúc
- Tích hợp với frontend để hiển thị kết quả

## 4. CÁC TÍCH HỢP CHÍNH

1. **Voice Command Handling**
   - Branch: feat/voice-whisper
   - Xử lý các intent: BO_QUA (bỏ qua), GIAI_THICH (giải thích thêm)

2. **Frame Skipping Logic**
   - Branch: feat/frame-skipping
   - Dùng FAISS để lưu vector frame đã bỏ qua
   - Không dừng video khi gặp frame đã bỏ qua

3. **LLM Integration**
   - Branch: feat/llava-finetune
   - Gọi LLM để giải thích tổn thương khi có yêu cầu

## 5. KẾT LUẬN

Kế hoạch này giúp triển khai một hệ thống khép kín từ nhận diện voice command đến bỏ qua frame trùng lặp và giải thích tổn thương bằng LLM.