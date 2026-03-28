# Hệ Thống Hỗ Trợ Chẩn Đoán Nội Soi Bằng AI với Tương Tác Giọng Nói Tiếng Việt

## 1. Tổng Quan

### 1.1 Mục Đích
Hệ thống hỗ trợ bác sĩ trong quá trình nội soi bằng cách:
- Phát hiện tổn thương thời gian thực bằng YOLO
- Cho phép điều khiển AI bằng giọng nói tiếng Việt (Whisper)
- Cung cấp giải thích lâm sàng bằng Multimodal LLM
- Tự động học để giảm false positive từ phản hồi bác sĩ

### 1.2 Phạm Vi
- Thời gian thực trong ca nội soi
- Hỗ trợ tiếng Việt hoàn toàn
- Closed-loop feedback giữa bác sĩ và AI

---

## 2. Pain Points & Giải Pháp

### 2.1 Pain Point 1: Bác sĩ phải làm 2 việc cùng lúc
**Vấn đề:**
- Trong ca nội soi, bác sĩ vừa điều khiển ống soi vừa phải nhìn màn hình
- Không thể dùng tay thao tác trên máy tính
- Mọi tương tác với hệ thống AI đều bị gián đoạn

**Giải pháp:**
- **Tương tác bằng giọng nói**: Bác sĩ ra lệnh bằng tiếng Việt mà không cần dùng tay
- **Tự động hóa**: Hệ thống tự động phát hiện và cảnh báo, không cần thao tác thủ công

### 2.2 Pain Point 2: False positive gây mất tập trung
**Vấn đề:**
- Các frame bị nhiễu (bọt trắng, ánh sáng phản chiếu, dịch nhầy) bị YOLO phát hiện nhầm là tổn thương
- Cảnh báo liên tục làm bác sĩ mất niềm tin vào hệ thống

**Giải pháp:**
- **Adaptive Frame Skipping**: Cơ chế tự học bỏ qua frame nhiễu dựa trên phản hồi giọng nói
- **Real-time filtering**: Lọc false positive trong thời gian thực khi bác sĩ nói "bỏ qua" hoặc "không phải tổn thương"

### 2.3 Pain Point 3: AI "câm" — detect xong không giải thích
**Vấn đề:**
- Hệ thống hiện tại chỉ vẽ bounding box
- Không đưa ra gợi ý lâm sàng
- Bác sĩ vẫn phải tự phán đoán hoàn toàn

**Giải pháp:**
- **Multimodal LLM**: Cung cấp gợi ý lâm sàng ngắn gọn bằng tiếng Việt theo thời gian thực
- **Giải thích tự động**: Khi phát hiện tổn thương, hệ thống mô tả đặc điểm và gợi ý chẩn đoán

---

## 3. Yêu Cầu Chức Năng

### 3.1 Nhận Diện Giọng Nói (Whisper)
- **FR-01**: Hệ thống phải nhận diện lệnh giọng nói tiếng Việt thời gian thực
- **FR-02**: Hỗ trợ các lệnh cơ bản:
  - "Bỏ qua frame này" / "Không phải tổn thương" (phản hồi false positive)
  - "Gợi ý đi" / "Giải thích xem" (yêu cầu LLM phân tích)
  - "Đánh dấu" / "Lưu lại" (đánh dấu frame quan trọng)
  - "Bắt đầu" / "Dừng lại" (kiểm soát quá trình)
- **FR-03**: Độ trễ nhận diện < 500ms

### 3.2 Phát Hiện Tổn Thương (YOLO)
- **FR-04**: Phát hiện tổn thương thời gian thực với tốc độ ≥ 30 FPS
- **FR-05**: Hiển thị bounding box và confidence score
- **FR-06**: Hỗ trợ nhiều lớp tổn thương (polyp, loét, viêm, khối u, ...)

### 3.3 Adaptive Frame Skipping (Issue #13)
- **FR-07**: Tự động học từ phản hồi giọng nói để nhận diện frame nhiễu
- **FR-08**: Giảm false positive ≥ 50% sau 10 lần phản hồi từ bác sĩ
- **FR-09**: Lưu mô hình học vào database để tái sử dụng cho các ca sau
- **FR-10**: Sử dụng FAISS vector store cho negative pattern DB
- **FR-11**: Embedding model: CLIP ViT-B/32 hoặc vision encoder của LLaVA
- **FR-12**: Similarity threshold: 0.85 (cosine similarity)
- **FR-13**: Snippet: frame hiện tại ± 3 frame (~0.5s)
- **FR-14**: FAISS index: IndexFlatIP (inner product)

### 3.4 Multimodal LLM Gợi Ý Lâm Sàng
- **FR-10**: Phân tích hình ảnh tổn thương và đưa ra gợi ý chẩn đoán
- **FR-11**: Trả lời bằng tiếng Việt, ngắn gọn (≤ 3 câu)
- **FR-12**: Hỗ trợ các loại gợi ý:
  - Đặc điểm hình ảnh (kích thước, hình dạng, màu sắc)
  - Khả năng ác tính/thuận lợi
  - Gợi ý biện pháp tiếp theo (sinh thiết, theo dõi, ...)

### 3.5 Closed-Loop Feedback
- **FR-13**: Ghi nhận phản hồi bác sĩ và cập nhật mô hình thời gian thực
- **FR-14**: Lưu lịch sử tương tác cho mỗi ca nội soi
- **FR-15**: Export báo cáo sau ca (tổn thương phát hiện, phản hồi bác sĩ, kết luận)

---

## 4. Yêu Cầu Phi Chức Năng

### 4.1 Hiệu Năng
- **NFR-01**: Độ trễ tổng thể < 1 giây từ khi capture frame đến khi hiển thị kết quả
- **NFR-02**: Hỗ trợ video độ phân giải tối thiểu 1080p @ 30fps
- **NFR-03**: GPU requirement: NVIDIA RTX 3060 hoặc tương đương

### 4.2 Độ Tin Cậy
- **NFR-04**: Hệ thống hoạt động liên tục ≥ 4 giờ (thời gian trung bình một ca nội soi)
- **NFR-05**: False positive rate < 10% sau khi học từ phản hồi
- **NFR-06**: False negative rate < 5%

### 4.3 Bảo Mật
- **NFR-07**: Mã hóa dữ liệu病 nhân (HIPAA compliant)
- **NFR-08**: Lưu trữ lokal, không upload hình ảnh病 nhân lên cloud
- **NFR-09**: Authentication và authorization cho bác sĩ

### 4.4 Khả Năng Sử Dụng
- **NFR-10**: Giao diện đơn giản, ít thông tin, không gây phân tâm
- **NFR-11**: Hỗ trợ tiếng Việt hoàn toàn (giao diện, giọng nói, văn bản)
- **NFR-12**: Có thể hoạt động offline (không cần internet)

---

## 5. Kiến Trúc Hệ Thống

### 5.1 Các Thành Phần Chính
```
┌─────────────────────────────────────────────────────────────┐
│                    Endoscope Camera                          │
└────────────────────────┬────────────────────────────────────┘
                         │ Video Stream (1080p @ 30fps)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Inference Module                           │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │   YOLO       │  │  Frame       │  │  Adaptive    │       │
│  │  Detector    │  │  Filter      │  │  Learning    │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└────────────────────────┬────────────────────────────────────┘
                         │ Bounding Box + Confidence
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                  Multimodal LLM Module                       │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Vision      │  │  Language    │  │  Vietnamese  │       │
│  │  Encoder     │  │  Generator   │  │  Translator  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└────────────────────────┬────────────────────────────────────┘
                         │ Gợi ý lâm sàng (tiếng Việt)
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                   Voice Interface                            │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐       │
│  │  Whisper     │  │  Command     │  │  TTS         │       │
│  │  STT         │  │  Parser      │  │  (Optional)  │       │
│  └──────────────┘  └──────────────┘  └──────────────┘       │
└────────────────────────┬────────────────────────────────────┘
                         │ Lệnh giọng nói / Phản hồi
                         ▼
┌─────────────────────────────────────────────────────────────┐
│                    Database (MongoDB)                        │
│  - Ca nội soi                                                │
│  - Lịch sử phản hồi                                          │
│  - Mô hình đã học                                            │
└─────────────────────────────────────────────────────────────┘
```

### 5.2 Data Flow
1. **Video Capture**: Endoscope → Frame buffer
2. **Detection**: YOLO → Bounding boxes
3. **Filtering**: Adaptive filter → Loại bỏ false positive
4. **Analysis**: LLM → Gợi ý lâm sàng
5. **Voice Input**: Whisper → Lệnh/phản hồi
6. **Learning**: Update mô hình từ phản hồi
7. **Storage**: MongoDB → Lưu ca nội soi

---

## 6. Tech Stack

### 6.1 Backend
- **Framework**: FastAPI
- **Language**: Python 3.11+
- **Database**: MongoDB
- **API Documentation**: OpenAPI/Swagger

### 6.2 AI/ML
- **Object Detection**: YOLO (Ultralytics)
- **Speech Recognition**: Whisper
- **Multimodal LLM**: LangChain + OpenAI/Gemini
- **Vector Search**: ChromaDB (cho RAG)
- **Computer Vision**: OpenCV

### 6.3 Infrastructure
- **GPU**: NVIDIA (CUDA 11.8+)
- **Container**: Docker (optional)
- **Deployment**: Local server

### 6.4 Libraries (requirements.txt)
```
fastapi>=0.124.4
uvicorn[standard]>=0.38.0
python-dotenv>=1.0.0
pydantic>=2.0.0
opencv-python>=4.8.0
ultralytics>=8.0.0
torch>=2.0.0
torchvision>=0.15.0
whisper>=1.0.0
langchain>=0.1.0
langchain-community>=0.0.10
langchain-openai>=0.0.2
langgraph>=0.0.26
chromadb>=0.4.0
pymongo>=4.0.0
requests>=2.31.0
tavily-python>=0.7.14
tiktoken>=0.5.0
numpy>=1.24.0,<2.0.0
tqdm>=4.66.0
```

---

## 7. So Sánh với Hệ Thống Truyền Thống

| Tiêu Chí | Hệ Thống Truyền Thống | Hệ Thống Đề Xuất |
|----------|----------------------|------------------|
| **Tương tác với AI** | Bàn phím/chuột | Giọng nói tiếng Việt |
| **Xử lý false positive** | Thủ công, sau ca | Real-time, học tự động |
| **Giải thích kết quả** | Không có | LLM gợi ý |
| **Ngôn ngữ hỗ trợ** | Tiếng Anh | Tiếng Việt |
| **Vòng phản hồi** | Một chiều | Hai chiều (closed-loop) |
| **Độ trễ** | > 2s | < 1s |
| **Hoạt động offline** | Không | Có |

---

## 8. Các Bước Triển Khai

### Phase 1: Core Detection (2 tuần)
- [ ] Setup YOLO model cho phát hiện tổn thương
- [ ] Tích hợp FastAPI backend
- [ ] Hiển thị bounding box thời gian thực

### Phase 2: Voice Interface (2 tuần)
- [ ] Tích hợp Whisper cho tiếng Việt
- [ ] Implement command parser
- [ ] Test độ trễ nhận diện giọng nói

### Phase 3: Adaptive Learning (3 tuần)
- [ ] Implement Adaptive Frame Skipping
- [ ] Lưu phản hồi vào MongoDB
- [ ] Train mô hình lọc false positive

### Phase 4: LLM Integration (3 tuần)
- [ ] Tích hợp Multimodal LLM
- [ ] Implement Vietnamese response generation
- [ ] Optimize độ trễ LLM

### Phase 5: Testing & Optimization (2 tuần)
- [ ] Test với data thật từ bệnh viện
- [ ] Fine-tune mô hình
- [ ] Optimize hiệu năng

---

## 9. Rủi Ro & Giảm Nhẹ

| Rủi Ro | Mức Độ | Giảm Nhẹ |
|--------|--------|----------|
| False positive cao | Cao | Adaptive learning + phản hồi bác sĩ |
| Độ trễ giọng nói | Trung bình | Optimize Whisper model (local) |
| LLM không hiểu tiếng Việt | Trung bình | Fine-tune hoặc dùng model tiếng Việt |
| GPU không đủ mạnh | Cao | Optimize model (quantization, pruning) |
| Dữ liệu bệnh nhân | Cao | Mã hóa + lưu lokal |

---

## 10. Success Metrics

- **Accuracy**: ≥ 95% detection rate
- **False Positive Rate**: < 10% sau khi học
- **Latency**: < 1s end-to-end
- **Voice Recognition Accuracy**: ≥ 90% cho tiếng Việt
- **User Satisfaction**: ≥ 4/5 từ bác sĩ thử nghiệm

---

## 11. Tài Liệu Tham Khảo

- YOLOv8 Documentation: https://docs.ultralytics.com/
- Whisper: https://github.com/openai/whisper
- LangChain: https://python.langchain.com/
- FastAPI: https://fastapi.tiangolo.com/
