# Technical Design Document - Endoscopy AI System

## 1. System Overview

### 1.1 Architecture Pattern
- **Pattern**: Modular Monolith with Event-Driven Components
- **Style**: Real-time streaming pipeline with closed-loop feedback
- **Deployment**: Local server (hospital infrastructure)

### 1.2 Core Components
```
┌─────────────────────────────────────────────────────────────────────┐
│                        Endoscopy AI System                          │
├─────────────────────────────────────────────────────────────────────┤
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐              │
│  │ Video Input  │──│   YOLO       │──│  Detection   │              │
│  │ (GStreamer)  │  │  Detector    │  │  Pipeline    │              │
│  └──────────────┘  └──────────────┘  └──────────────┘              │
│           │                │                │                       │
│           ▼                ▼                ▼                       │
│  ┌──────────────────────────────────────────────────────┐          │
│  │              Adaptive Frame Filter                   │          │
│  │  (FAISS-based negative pattern matching)             │          │
│  └──────────────────────────────────────────────────────┘          │
│                           │                                         │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────┐          │
│  │            Multimodal LLM Analyzer                   │          │
│  │  (LLaVA-Med / GPT-4o Vision)                         │          │
│  └──────────────────────────────────────────────────────┘          │
│                           │                                         │
│           ┌───────────────┴───────────────┐                        │
│           ▼                               ▼                         │
│  ┌──────────────┐                ┌──────────────┐                  │
│  │  Whisper STT │                │   Display    │                  │
│  │  (Vietnamese)│                │   Overlay    │                  │
│  └──────────────┘                └──────────────┘                  │
│           │                               │                         │
│           └───────────────┬───────────────┘                        │
│                           ▼                                         │
│  ┌──────────────────────────────────────────────────────┐          │
│  │              MongoDB + ChromaDB                      │          │
│  │  (Case history, learned patterns, embeddings)        │          │
│  └──────────────────────────────────────────────────────┘          │
└─────────────────────────────────────────────────────────────────────┘
```

---

## 2. Component Specifications

### 2.1 Video Capture Module (`src/backend/capture/`)

**Purpose**: Real-time video ingestion from endoscope camera

**Files**:
- `capture_system.py` - Main capture pipeline
- `gst_shark_profiler.py` - Performance monitoring
- `gstreamer_integration.py` - GStreamer pipeline

**Key Features**:
- GStreamer-based video capture (fallback to OpenCV)
- Frame buffering with ±3 frame snippet storage
- Real-time frame preprocessing (resize, normalize)
- FPS monitoring and profiling

**Interfaces**:
```python
class CaptureSystem:
    def start(self) -> bool
    def stop(self) -> None
    def get_current_frame(self) -> np.ndarray
    def register_detection_callback(self, callback: Callable) -> None
```

**Performance Requirements**:
- Frame rate: ≥ 30 FPS at 1080p
- Latency: < 50ms from capture to buffer
- Memory: < 2GB RAM for video buffer

---

### 2.2 YOLO Detection Module (`src/inference/`)

**Purpose**: Real-time lesion detection and segmentation

**Files**:
- `yolo_detector.py` - YOLO inference wrapper
- `custom_yolo.py` - Custom implementation (TorchScript)
- `model_manager.py` - Model loading and versioning

**Key Features**:
- YOLOv8 segmentation model (`.pt` / `.torchscript`)
- GPU acceleration with CUDA fallback to CPU
- Object tracking across frames
- Confidence threshold filtering (default: 0.25)
- IoU threshold for NMS (default: 0.45)

**Interfaces**:
```python
class YOLODetector:
    def __init__(self, model_path: str, device: str = "cuda")
    def load_model(self) -> bool
    def detect(self, frame: np.ndarray, conf: float = 0.25) -> List[Detection]
    def track(self, frame: np.ndarray, persist: bool = True) -> List[Detection]
```

**Detection Output Format**:
```python
@dataclass
class Detection:
    class_id: int
    confidence: float
    bbox: Tuple[int, int, int, int]  # x1, y1, x2, y2
    mask: Optional[np.ndarray]  # Segmentation mask
    track_id: Optional[int]  # From object tracking
```

**Performance Requirements**:
- Inference time: < 30ms per frame (GPU), < 100ms (CPU)
- Memory: < 4GB VRAM (quantized model)
- Detection accuracy: mAP ≥ 0.85 on HyperKvasir

---

### 2.3 Adaptive Frame Filter (`src/backend/utils/`)

**Purpose**: Real-time false positive reduction using learned patterns

**Files**:
- `adaptive_filter.py` - Main filtering logic
- `faiss_manager.py` - FAISS vector store management
- `negative_pattern_db.py` - Negative pattern storage

**Key Features**:
- FAISS vector store for negative pattern matching
- CLIP ViT-B/32 or LLaVA vision encoder for embeddings
- Similarity threshold: 0.85 (cosine similarity)
- Frame snippet: current frame ± 3 frames (~0.5s window)
- Incremental learning from voice feedback

**Interfaces**:
```python
class AdaptiveFrameFilter:
    def __init__(self, embedding_model: str = "clip_vit_b_32")
    def load_negative_patterns(self, db_path: str) -> None
    def is_false_positive(self, frame: np.ndarray) -> bool
    def add_negative_pattern(self, frame: np.ndarray, reason: str) -> None
    def update_threshold(self, new_threshold: float) -> None
```

**FAISS Index Configuration**:
```python
# Index type: IndexFlatIP (inner product for cosine similarity)
index = faiss.IndexFlatIP(embedding_dim)  # embedding_dim = 512 for CLIP

# Normalization required for cosine similarity
faiss.normalize_L2(embeddings)
```

**Performance Requirements**:
- Similarity search: < 10ms for 1000 patterns
- False positive reduction: ≥ 50% after 10 feedbacks
- Memory: < 500MB for FAISS index

---

### 2.4 Voice Interface Module (`src/voice/`)

**Purpose**: Speech-to-text and command interpretation

**Files**:
- `whisper_handler.py` - Whisper STT integration
- `command_parser.py` - Voice command interpretation
- `voice_feedback_loop.py` - Feedback collection and processing

**Key Features**:
- Whisper model for Vietnamese speech recognition
- Real-time transcription with streaming
- Command classification (skip, explain, mark, start, stop)
- Confidence scoring for voice commands

**Interfaces**:
```python
class WhisperHandler:
    def __init__(self, language: str = "vi", model_size: str = "base")
    def transcribe_audio(self, audio_data: bytes) -> str
    def stream_transcribe(self, audio_stream: Iterator[bytes]) -> Iterator[str]
    def get_confidence(self) -> float
```

```python
class CommandParser:
    def parse(self, text: str) -> VoiceCommand
    def get_confidence(self) -> float
```

**Voice Commands**:
| Command | Vietnamese | Action |
|---------|-----------|--------|
| SKIP | "Bỏ qua", "Không phải tổn thương" | Mark as false positive |
| EXPLAIN | "Gợi ý đi", "Giải thích xem" | Trigger LLM analysis |
| MARK | "Đánh dấu", "Lưu lại" | Save frame to database |
| START | "Bắt đầu", "Bắt đầu ghi" | Start recording |
| STOP | "Dừng lại", "Kết thúc" | Stop recording |

**Performance Requirements**:
- Recognition latency: < 500ms
- Accuracy: ≥ 90% for Vietnamese
- Memory: < 1GB for Whisper model

---

### 2.5 Multimodal LLM Module (`src/backend/rag/`)

**Purpose**: Clinical suggestion generation from detected lesions

**Files**:
- `llm_analyzer.py` - LLM inference wrapper
- `prompt_templates.py` - Prompt engineering
- `response_cache.py` - Response caching

**Key Features**:
- LLaVA-Med fine-tuned on HyperKvasir (LoRA 4-bit)
- Fallback to GPT-4o Vision via API
- Vietnamese response generation
- Response caching for similar frames
- Feedback loop integration

**Interfaces**:
```python
class LLMAnalyzer:
    def __init__(self, model: str = "llava_med_4bit")
    def analyze(self, image: np.ndarray, detection: Detection) -> ClinicalSuggestion
    def explain_more(self, previous_response: str) -> str
    def re_analyze(self, image: np.ndarray, detection: Detection) -> ClinicalSuggestion
```

**Clinical Suggestion Format**:
```python
@dataclass
class ClinicalSuggestion:
    description: str  # Lesion characteristics (≤ 3 sentences)
    malignancy_likelihood: str  # "Thuận lợi", "Nghi ngờ ác tính", "Không xác định"
    next_steps: List[str]  # ["Sinh thiết", "Theo dõi", "Không cần can thiệp"]
    confidence: float
```

**Prompt Template**:
```
Bạn là bác sĩ chuyên khoa tiêu hóa. Hãy phân tích hình ảnh nội soi này:

Hình ảnh cho thấy: {detection_description}

Hãy đưa ra gợi ý lâm sàng ngắn gọn (tối đa 3 câu) bằng tiếng Việt:
1. Đặc điểm hình ảnh
2. Khả năng ác tính/thuận lợi
3. Gợi ý biện pháp tiếp theo

Trả lời:
```

**Performance Requirements**:
- Response time: < 2 seconds per analysis
- Response length: ≤ 3 sentences
- Memory: < 4GB VRAM (4-bit quantized)

---

### 2.6 Database Module (`src/backend/database/`)

**Purpose**: Persistent storage for cases, patterns, and embeddings

**Files**:
- `mongodb_client.py` - MongoDB connection and operations
- `chroma_client.py` - ChromaDB vector store
- `case_repository.py` - Case CRUD operations

**Key Features**:
- MongoDB for structured data (cases, feedback, metadata)
- ChromaDB for vector embeddings (optional, for RAG)
- Automatic indexing and querying
- Data encryption at rest

**Database Schemas**:

**Case Collection**:
```json
{
  "_id": ObjectId,
  "patient_id": "string (anonymized)",
  "start_time": "datetime",
  "end_time": "datetime",
  "detections": [
    {
      "frame_id": "string",
      "timestamp": "datetime",
      "class_id": "int",
      "confidence": "float",
      "bbox": [x1, y1, x2, y2],
      "llm_suggestion": {
        "description": "string",
        "malignancy_likelihood": "string",
        "next_steps": ["string"]
      },
      "feedback": {
        "type": "skip|confirm|explain_more",
        "timestamp": "datetime",
        "voice_command": "string"
      }
    }
  ],
  "summary": {
    "total_detections": "int",
    "false_positives": "int",
    "biopsy_recommended": "int"
  }
}
```

**NegativePattern Collection**:
```json
{
  "_id": ObjectId,
  "embedding": [float],  // 512-dim vector
  "frame_hash": "string",
  "reason": "string (e.g., 'bọt trắng', 'ánh sáng phản chiếu')",
  "created_at": "datetime",
  "usage_count": "int"
}
```

**Interfaces**:
```python
class MongoDBClient:
    def connect(self, uri: str) -> bool
    def save_case(self, case: Case) -> None
    def get_case(self, case_id: str) -> Optional[Case]
    def get_all_cases(self, patient_id: str) -> List[Case]
```

```python
class ChromaClient:
    def __init__(self, persist_dir: str)
    def add_embedding(self, embedding: List[float], metadata: dict) -> str
    def search_similar(self, query_embedding: List[float], k: int = 5) -> List[dict]
```

**Performance Requirements**:
- Write latency: < 100ms per case
- Read latency: < 50ms per query
- Storage: Scalable with compression

---

### 2.7 API Layer (`src/backend/api/`)

**Purpose**: RESTful API for frontend integration

**Files**:
- `main.py` - FastAPI application
- `endpoints.py` - API route handlers
- `schemas.py` - Pydantic models

**Endpoints**:
```
POST   /api/capture/start          - Start video capture
POST   /api/capture/stop           - Stop video capture
GET    /api/capture/status         - Get capture status
POST   /api/detect                 - Run detection on frame
POST   /api/detect/stream          - Real-time detection stream
POST   /api/voice/command          - Process voice command
GET    /api/case/{case_id}         - Get case details
POST   /api/case                   - Save new case
GET    /api/case/list              - List all cases
POST   /api/feedback               - Submit feedback
GET    /api/stats                  - System statistics
```

**API Response Format**:
```json
{
  "success": true,
  "data": {...},
  "message": "string",
  "timestamp": "ISO8601"
}
```

---

## 3. Data Flow

### 3.1 Real-time Detection Pipeline
```
1. Video Capture (GStreamer/OpenCV)
   ↓
2. Frame Preprocessing (resize, normalize)
   ↓
3. YOLO Detection (GPU inference)
   ↓
4. Adaptive Frame Filter (FAISS similarity check)
   ├─ If false positive: Skip, learn from feedback
   └─ If real lesion: Continue
   ↓
5. LLM Analysis (only for confirmed detections)
   ↓
6. Display Overlay (bounding box + suggestion)
   ↓
7. Save to Database (MongoDB)
```

### 3.2 Voice Feedback Loop
```
1. Doctor speaks ("Bỏ qua frame này")
   ↓
2. Whisper STT → Transcription
   ↓
3. Command Parser → SKIP command
   ↓
4. Mark current frame as negative pattern
   ↓
5. Extract embedding (CLIP/Llava vision encoder)
   ↓
6. Add to FAISS negative pattern DB
   ↓
7. Update threshold if needed
   ↓
8. Future similar frames auto-skipped
```

---

## 4. Configuration

### 4.1 Environment Variables (`.env`)
```bash
# YOLO
YOLO_MODEL_PATH=models/yolov8n-seg.pt
YOLO_CONF_THRESHOLD=0.25
YOLO_IOU_THRESHOLD=0.45
YOLO_DEVICE=cuda

# Whisper
WHISPER_MODEL=base
WHISPER_LANGUAGE=vi
WHISPER_TEMPERATURE=0.0

# LLM
LLM_MODEL=llava_med_4bit
LLM_MAX_TOKENS=100
LLM_TEMPERATURE=0.3
OPENAI_API_KEY=... (for GPT-4o fallback)

# Database
MONGODB_URI=mongodb://localhost:27017
CHROMA_PERSIST_DIR=data/chroma

# FAISS
FAISS_DB_PATH=data/faiss_negative_patterns
FAISS_EMBEDDING_MODEL=clip_vit_b_32
FAISS_SIMILARITY_THRESHOLD=0.85

# Performance
GPU_MEMORY_FRACTION=0.8
CACHE_SIZE=100
```

### 4.2 Settings Module (`configs/settings.py`)
Already implemented with all configuration management.

---

## 5. Deployment Architecture

### 5.1 Hardware Requirements
| Component | Minimum | Recommended |
|-----------|---------|-------------|
| GPU | GTX 1650 (4GB) | RTX 3060 (12GB) |
| CPU | 4 cores | 8 cores |
| RAM | 16GB | 32GB |
| Storage | 50GB SSD | 100GB NVMe |
| Network | 1Gbps | 10Gbps |

### 5.2 Software Requirements
- Ubuntu 20.04+ / Windows 10+
- Python 3.11+
- CUDA 11.8+ (for GPU)
- Docker (optional, for containerization)

### 5.3 Deployment Options
1. **Standalone**: All components on single machine
2. **Distributed**: GPU server for inference, CPU for capture/UI
3. **Containerized**: Docker Compose for easy deployment

---

## 6. Testing Strategy

### 6.1 Unit Tests
- YOLO inference accuracy
- Whisper transcription accuracy
- FAISS similarity search
- Database CRUD operations

### 6.2 Integration Tests
- End-to-end detection pipeline
- Voice feedback loop
- API endpoint responses

### 6.3 Performance Tests
- FPS benchmark (GPU vs CPU)
- Latency measurements
- Memory usage profiling

### 6.4 User Acceptance Tests
- Doctor feedback on false positive reduction
- Voice command recognition in noisy environment
- LLM suggestion quality rating

---

## 7. Security & Compliance

### 7.1 Data Privacy
- Patient data anonymization (no real IDs stored)
- Local storage only (no cloud upload)
- Encryption at rest (MongoDB encryption)

### 7.2 Access Control
- Authentication for doctors
- Role-based access (admin, doctor, viewer)
- Audit logging for all operations

### 7.3 Compliance
- HIPAA-compliant data handling
- GDPR considerations (if applicable)
- Hospital IT security policies

---

## 8. Future Enhancements

### Phase 2 (Post-MVP)
- Multi-language support (beyond Vietnamese)
- Advanced LLM fine-tuning on hospital-specific data
- Real-time collaboration (multiple doctors)
- Mobile app for remote viewing
- Automated report generation (PDF export)

### Phase 3 (Research)
- Active learning from doctor feedback
- Cross-hospital model improvement
- Predictive analytics (risk assessment)
- Integration with hospital EMR systems

---

## 9. References

- YOLOv8: https://docs.ultralytics.com/
- Whisper: https://github.com/openai/whisper
- LLaVA-Med: https://github.com/microsoft/LLaVA-Med
- FAISS: https://github.com/facebookresearch/faiss
- FastAPI: https://fastapi.tiangolo.com/
- HyperKvasir Dataset: https://datasets.simula.no/hyper-kvasir/
