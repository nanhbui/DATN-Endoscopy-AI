# LLM Chatbot Enhancement — Design Doc

**Branch:** main
**Date:** 2026-05-06
**Scope:** Restructure `Giải thích thêm` per-detection + add session-wide summary chatbot

---

## 🎯 Mục tiêu

Nâng cấp LLM workflow từ "chatbot trợ lý chung" thành **2 lớp AI report** mô phỏng workflow bác sĩ thật:

1. **Per-detection structured report** — mỗi tổn thương sinh ra 1 mini-report 3 phần (Kỹ thuật / Mô tả / Kết luận) với LLM phân tích kỹ ảnh
2. **Per-session summary chatbot** — sau khi soi xong, AI đọc toàn bộ detections + phân tích để sinh báo cáo tổng + interactive Q&A

---

## 📋 PART 1 — Per-detection Structured Report

### 1.1. Cấu trúc 3 phần (chuẩn VN medical report)

```
┌─────────────────────────────────────────────────────────────────┐
│  KẾT QUẢ NỘI SOI — TỔN THƯƠNG #3                                │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  📋 KỸ THUẬT                                                    │
│  ────────────                                                   │
│  • Phương pháp: Nội soi dạ dày-tá tràng AI-assisted            │
│  • Thiết bị: Olympus EG-760Z (suy ra từ video metadata)        │
│  • Thời điểm phát hiện: 2 phút 34 giây (frame 4612)            │
│  • Mô hình AI: best_train6 (YOLOv8m, FP16 CUDA)                │
│  • Độ tin cậy phát hiện: 76%                                   │
│                                                                 │
│  🔍 MÔ TẢ                                                       │
│  ────────                                                       │
│  • Vị trí: Bờ cong nhỏ — phần thân vị                          │
│  • Kích thước: ước tính 6–8 mm (so với đường kính scope ~9mm)  │
│  • Hình dạng: Phân loại Paris 0-IIa+IIc                        │
│  • Bề mặt: Sần nhẹ, có vùng lõm trung tâm bờ fibrin            │
│  • Màu sắc: Đỏ không đều, sung huyết quanh viền                │
│  • Bờ tổn thương: Không rõ, có dấu hiệu cứng                   │
│  • Mạch máu bề mặt: Bị che mờ bởi fibrin                       │
│  • Dịch/máu: Không thấy chảy máu tự phát                       │
│                                                                 │
│  💡 KẾT LUẬN                                                    │
│  ────────────                                                   │
│  Chẩn đoán nghi ngờ:  Viêm dạ dày HP có tổn thương khu trú     │
│  Mức độ:              Trung bình → cao (cần loại trừ ung thư)  │
│                                                                 │
│  Chẩn đoán phân biệt (theo thứ tự khả năng):                   │
│   1. Viêm dạ dày HP-positive với loét nông (~60%)              │
│   2. Tổn thương tiền ung thư (intestinal metaplasia)  (~25%)   │
│   3. Ung thư dạ dày sớm type 0-IIa+IIc                (~15%)   │
│                                                                 │
│  Đề xuất xử trí:                                                │
│   ☐ Sinh thiết ≥5 mảnh tại bờ và đáy tổn thương                │
│   ☐ Test CLO tại chỗ phát hiện H. pylori                       │
│   ☐ Chụp ảnh NBI/Chromoendoscopy nếu có thiết bị               │
│   ☐ Hẹn tái khám 6–8 tuần sau điều trị                         │
│   ☐ Cân nhắc EUS nếu nghi ngờ xâm lấn                          │
│                                                                 │
│  Mức độ chắc chắn của AI: 70%                                   │
│  ⚠ Báo cáo này là gợi ý hỗ trợ, không thay thế bác sĩ.        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 1.2. Field-by-field breakdown — nguồn dữ liệu

| Section | Field | Nguồn | Cần LLM? |
|---------|-------|-------|----------|
| **Kỹ thuật** | Phương pháp | Hard-code | ❌ |
| | Thiết bị | OCR từ frame info panel (nếu có) hoặc video metadata | Optional OCR |
| | Thời điểm | Backend `timestamp_ms` | ❌ |
| | Frame index | Backend `frame_index` | ❌ |
| | Model + version | Hard-code config | ❌ |
| | Độ tin cậy detect | Backend `confidence` | ❌ |
| **Mô tả** | Vị trí giải phẫu | Region classifier (đã removed, cần re-add ở Phase 4) | Classifier |
| | **Kích thước** | Vision LLM ước lượng từ bbox + scope reference | ✅ Vision |
| | **Hình dạng (Paris)** | Vision LLM | ✅ Vision |
| | **Bề mặt** | Vision LLM | ✅ Vision |
| | **Màu sắc** | Vision LLM | ✅ Vision |
| | **Bờ tổn thương** | Vision LLM | ✅ Vision |
| | **Mạch máu** | Vision LLM | ✅ Vision |
| | Dịch/máu | Vision LLM | ✅ Vision |
| **Kết luận** | Chẩn đoán nghi ngờ | LLM dựa trên Mô tả + label model | ✅ Vision |
| | Mức độ | LLM scale low/medium/high | ✅ Vision |
| | Differential diagnosis | LLM bắt buộc 3 ranked options | ✅ Vision |
| | Đề xuất xử trí | LLM theo guidelines | ✅ Vision |
| | Confidence của LLM | LLM self-rate | ✅ Vision |

### 1.3. Prompt engineering — cấu trúc JSON output

Force GPT-4o vision return JSON theo schema chuẩn để frontend render structured cards:

```python
RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "endoscopy_lesion_report",
        "schema": {
            "type": "object",
            "required": ["technique", "description", "conclusion"],
            "properties": {
                "technique": {
                    "type": "object",
                    "properties": {
                        "method": {"type": "string"},
                        "device": {"type": "string"},
                        "timestamp_label": {"type": "string"},
                    }
                },
                "description": {
                    "type": "object",
                    "required": ["location", "size_mm", "paris_class", "surface",
                                 "color", "margin", "vascular", "fluid"],
                    "properties": {
                        "location": {"type": "string"},
                        "size_mm": {"type": "string", "description": "ước tính, vd '6-8mm'"},
                        "paris_class": {"type": "string"},
                        "surface": {"type": "string"},
                        "color": {"type": "string"},
                        "margin": {"type": "string"},
                        "vascular": {"type": "string"},
                        "fluid": {"type": "string"}
                    }
                },
                "conclusion": {
                    "type": "object",
                    "required": ["primary_dx", "severity", "differential", "actions", "confidence"],
                    "properties": {
                        "primary_dx": {"type": "string"},
                        "severity": {"type": "string", "enum": ["thấp", "trung bình", "cao"]},
                        "differential": {
                            "type": "array",
                            "minItems": 2,
                            "maxItems": 3,
                            "items": {
                                "type": "object",
                                "properties": {
                                    "diagnosis": {"type": "string"},
                                    "probability_pct": {"type": "integer"}
                                }
                            }
                        },
                        "actions": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "checklist hành động cho bác sĩ"
                        },
                        "confidence": {"type": "integer", "description": "self-rated AI confidence 0-100"}
                    }
                }
            }
        }
    }
}
```

System prompt mới:

```
Bạn là trợ lý nội soi tiêu hóa AI cho bác sĩ Việt Nam. Phân tích ảnh tổn thương
và trả về JSON theo schema endoscopy_lesion_report.

QUAN TRỌNG:
1. Mô tả phải dựa TRÊN ẢNH thật, không bịa nếu không thấy rõ. Nếu không xác định
   được, ghi "Không quan sát rõ" cho field đó.
2. Kích thước ước lượng từ:
   - Đường kính scope tham chiếu (~9-13mm cho EG-760Z)
   - Kích thước nếp gấp dạ dày trung bình
   - Snare/forceps trong ảnh (nếu có)
   Format: "X-Y mm" hoặc "ước tính N mm". Nếu không ước tính được: "không xác định".
3. Bắt buộc liệt kê 2-3 differential diagnoses, ranked theo xác suất giảm dần.
4. Actions phải cụ thể: số mảnh sinh thiết, vị trí, thời gian tái khám.
5. confidence là tự đánh giá AI mức độ chắc chắn — phải honest, không inflate.

Phân loại Paris (bắt buộc áp dụng):
[... existing Paris classification rules ...]
```

### 1.4. Frontend rendering

Thay vì plain markdown trong "LLM Smart Log", render structured cards:

```tsx
<DetectionReport>
  <Section icon="📋" title="Kỹ thuật">
    <KVRow label="Phương pháp" value={r.technique.method} />
    <KVRow label="Thiết bị" value={r.technique.device} />
    <KVRow label="Thời điểm" value={r.technique.timestamp_label} />
    <KVRow label="Độ tin cậy detect" value={`${conf}%`} />
  </Section>

  <Section icon="🔍" title="Mô tả">
    <KVRow label="Vị trí" value={r.description.location} highlight />
    <KVRow label="Kích thước" value={r.description.size_mm} highlight />
    <KVRow label="Phân loại Paris" value={r.description.paris_class} />
    <KVRow label="Bề mặt" value={r.description.surface} />
    {/* ... */}
  </Section>

  <Section icon="💡" title="Kết luận">
    <SeverityBadge level={r.conclusion.severity} />
    <PrimaryDx>{r.conclusion.primary_dx}</PrimaryDx>
    <DifferentialList items={r.conclusion.differential} />
    <ActionChecklist items={r.conclusion.actions} />
    <ConfidenceBar pct={r.conclusion.confidence} />
  </Section>
</DetectionReport>
```

UI improvement so với hiện tại:
- ❌ Trước: 1 wall of markdown text, khó scan
- ✅ Sau: Cards với headers + key-value rows, severity color coded, action checklist clickable (doctor tick off)

### 1.5. WS protocol changes

```typescript
// New event type
| { event: "LLM_STRUCTURED"; data: { report: EndoscopyLesionReport } }
```

Hoặc giữ backward compat: stream JSON như string qua `LLM_CHUNK`, frontend parse khi nhận `LLM_DONE`. Cleaner: dùng OpenAI streaming với `response_format=json_schema` — auto valid JSON, không cần parse mid-stream.

---

## 📋 PART 2 — Per-session Summary Chatbot

### 2.1. Khái niệm

Sau khi soi xong (EOS_SUMMARY hoặc user nhấn "Tạo báo cáo đầy đủ"), 1 LLM call thứ hai đọc TẤT CẢ structured reports → generate session summary + interactive Q&A.

### 2.2. Cấu trúc Session Summary

```
┌─────────────────────────────────────────────────────────────────┐
│  📊 BÁO CÁO TỔNG QUAN — PHIÊN NỘI SOI                           │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  🎯 TÓM TẮT CA SOI                                              │
│  ──────────────────                                             │
│  • Tổng thời gian: 5 phút 12 giây                              │
│  • Vùng đã khảo sát: Thực quản, Dạ dày (toàn bộ), Tá tràng D1  │
│  • Tổng phát hiện AI: 12 (8 confirmed, 3 ignored, 1 pending)   │
│  • Phân bố theo cơ quan:                                        │
│      Thực quản:  2 (1 viêm, 1 nghi ngờ ung thư sớm)            │
│      Dạ dày:     8 (6 viêm HP, 1 polyp Paris 0-Ip, 1 loét)     │
│      Tá tràng:   2 (cả 2 viêm HTT)                             │
│                                                                 │
│  🔥 TỔN THƯƠNG ƯU TIÊN (theo severity)                         │
│  ─────────────────────────────────────                         │
│  1. [CAO]    Tổn thương #5: Paris 0-IIa+IIc tại Hang vị        │
│              → Nghi ngờ ung thư sớm. Sinh thiết KHẨN.          │
│  2. [TB]     Tổn thương #3: Loét HTT 8mm bờ fibrin             │
│              → Loét lành tính khả năng cao, cần theo dõi.      │
│  3. [TB]     Tổn thương #1: Viêm thực quản LA grade B           │
│              → Điều trị PPI 4-8 tuần, tái khám.                │
│                                                                 │
│  🎬 PATTERN PHÂN TÍCH                                           │
│  ─────────────────────                                          │
│  • H. pylori signs: 6/8 phát hiện dạ dày có dấu hiệu HP        │
│    → Khuyến nghị test HP đồng thời + điều trị triệt căn        │
│  • Niêm mạc dạ dày bị viêm lan tỏa, không khu trú              │
│  • Không thấy dấu hiệu xâm lấn sâu (cancer giai đoạn sớm nếu có) │
│                                                                 │
│  📋 CHECKLIST HÀNH ĐỘNG TỔNG HỢP                                │
│  ──────────────────────────────                                 │
│  ☐ Sinh thiết:                                                  │
│     - 5 mảnh tại bờ tổn thương #5 (ưu tiên cao)                │
│     - 2 mảnh hang vị (test HP)                                  │
│     - 2 mảnh thân vị (đánh giá viêm)                            │
│  ☐ Test cận lâm sàng:                                          │
│     - CLO test tại chỗ                                          │
│     - Test thở H. pylori 4 tuần sau (nếu CLO âm)               │
│  ☐ Điều trị (chờ kết quả mô bệnh học):                         │
│     - PPI dose chuẩn × 8 tuần                                   │
│     - Triple therapy nếu HP+                                    │
│  ☐ Hẹn khám lại:                                               │
│     - 4-6 tuần xem kết quả mô bệnh học                          │
│     - Nội soi lại 3 tháng nếu nghi ngờ ung thư                 │
│                                                                 │
│  💬 HỎI ĐÁP VỀ PHIÊN SOI NÀY                                    │
│  ──────────────────────────                                    │
│  > [Input box để doctor chat tiếp]                             │
│  Ví dụ:                                                         │
│   - "Có nên gửi BN này khám oncology không?"                   │
│   - "So sánh tổn thương #3 với #7"                             │
│   - "Đánh giá nguy cơ ung thư tổng thể của BN"                 │
│   - "Sinh thiết ở đâu trước nếu chỉ làm được 5 mảnh?"          │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### 2.3. Workflow

```
[EOS_SUMMARY hoặc user click "Tạo báo cáo đầy đủ"]
         │
         ▼
┌─────────────────────────────────┐
│ Backend collects all detections │
│ + their structured reports      │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│ LLM call 1: Generate summary    │
│ Input: list of structured       │
│        detection reports        │
│ Output: SessionSummary JSON     │
└──────────┬──────────────────────┘
           │
           ▼
┌─────────────────────────────────┐
│ Frontend renders SummaryReport  │
│ + opens chat input              │
└──────────┬──────────────────────┘
           │
           ▼
[User asks question]
           │
           ▼
┌─────────────────────────────────┐
│ LLM call N: Q&A with full       │
│   session context as prompt     │
│ Streaming response              │
└─────────────────────────────────┘
```

### 2.4. Prompt cho session summary

```
Bạn là trợ lý nội soi tiêu hóa AI. Đã hoàn tất 1 ca soi với {N} tổn thương phát hiện.
Đầu vào: list các structured report (mỗi tổn thương 1 JSON 3 phần).

Nhiệm vụ:
1. Tổng hợp số lượng + phân bố theo cơ quan
2. Sắp xếp tổn thương theo severity (priority list)
3. Phát hiện pattern xuyên suốt (vd "viêm lan tỏa", "polyp đa ổ")
4. Tổng hợp checklist hành động (gộp các sinh thiết, tránh trùng lặp)
5. Đánh giá nguy cơ tổng thể: low/medium/high

Output JSON theo schema session_summary_schema.
```

### 2.5. Cross-detection chat — Q&A mode

Sau khi summary xong, user có thể hỏi tiếp. LLM context bao gồm:
- Summary đã sinh
- ALL detection structured reports
- (Optional) user's previous questions trong session

Examples:
- **"So sánh tổn thương #3 với #7"** → LLM đọc 2 reports, side-by-side comparison
- **"Tổn thương nào nguy hiểm nhất?"** → LLM rank theo severity + lý do
- **"BN này có nên đi oncology không?"** → LLM weigh evidence, đưa ra recommend
- **"Sinh thiết theo thứ tự ưu tiên?"** → LLM sort by clinical urgency
- **"Tổn thương #5 có thể là cancer không?"** → LLM detail differential + reasoning

### 2.6. UI mockup

Frontend report page — thêm panel "Session Summary":

```
┌─────────────────────────────────────────────────┐
│  📊 BÁO CÁO TỔNG QUAN PHIÊN              [×]   │
├─────────────────────────────────────────────────┤
│ [Tabs: Tổng quan | Chi tiết | Trò chuyện AI]   │
│                                                 │
│ ─── Tổng quan ───                               │
│  Cards với từng section của summary             │
│  (Tóm tắt, Priority list, Pattern, Checklist)  │
│                                                 │
│ ─── Trò chuyện AI ───                           │
│  ┌─────────────────────────────────────────┐   │
│  │ AI: "Phiên này có 12 phát hiện..."     │   │
│  │ User: "tổn thương 5 nguy hiểm thế nào?"│   │
│  │ AI: [streaming response]                │   │
│  └─────────────────────────────────────────┘   │
│  [Input: "Hỏi AI về phiên này..."]      [Gửi]  │
└─────────────────────────────────────────────────┘
```

---

## 🛠 Technical Implementation

### Storage architecture

```
Session
├── id: "ee224941b567"
├── video_id, source, started_at
├── detections: Detection[]
│   └── Detection
│       ├── frame_index, timestamp_ms, bbox, label, confidence
│       ├── frame_b64
│       └── llm_report?: EndoscopyLesionReport  ← NEW
├── llm_session_summary?: SessionSummary       ← NEW
└── llm_chat_history: ChatMessage[]            ← NEW (for session Q&A)
```

Persistent: localStorage hiện tại đã lưu Session — extend schema để cover các field mới.

### Backend changes

1. **Update `_stream_llm`**: gọi với `response_format=json_schema`, accumulate JSON, send single `LLM_STRUCTURED` event when done
2. **New endpoint `_stream_session_summary`**: trigger khi EOS, gửi `SESSION_SUMMARY_STARTED` + stream `SESSION_SUMMARY_CHUNK` + `SESSION_SUMMARY_DONE`
3. **New action `ACTION_SESSION_QA`**: handle session-level chat
4. **Cache strategy**:
   - Per-detection report: cache by detection_id (per session unique)
   - Session summary: regenerate on demand (không cache vì state thay đổi khi user confirm/ignore)

### Frontend changes

1. **`Detection` type extension**:
   ```typescript
   interface Detection {
     // ... existing
     llmReport?: EndoscopyLesionReport;  // structured report
   }
   ```
2. **`Session` type extension**:
   ```typescript
   interface Session {
     // ... existing
     llmSummary?: SessionSummary;
     llmChatHistory?: ChatMessage[];
   }
   ```
3. **New components**:
   - `<DetectionReportCard>` — render structured 3-section report
   - `<SessionSummaryPanel>` — render summary
   - `<SessionChatInterface>` — Q&A textarea + message list
4. **Update workspace**:
   - DetectionBar + LLM Smart Log → render structured report instead of markdown
   - Action button "Giải thích thêm" → triggers structured report generation
5. **Update report page**:
   - Mỗi session có "Session Summary" tab
   - Mỗi detection có "Chi tiết AI" expandable (hiện structured report)

---

## 📅 Implementation phases

### Phase A — Per-detection structured report (3-4 ngày)

**A1. Backend prompt + schema** (4h)
- Define `endoscopy_lesion_report` JSON schema
- Update `LLM_SYSTEM_PROMPT` for structured output
- Test with sample detections

**A2. Backend streaming** (3h)
- Modify `_stream_llm` to use `response_format=json_schema`
- Stream JSON, send `LLM_STRUCTURED` event on completion
- Update cache to store JSON

**A3. Frontend types + components** (8h)
- Add `EndoscopyLesionReport` types
- Build `<DetectionReportCard>` with 3 sections
- Replace LLM Smart Log text rendering
- Add severity badge, action checklist UI

**A4. Action checklist persistence** (3h)
- User can tick/untick action items
- Save state in detection record
- Show progress on report page

**A5. Testing on sample frames** (4h)
- 10-15 sample detections from lab videos
- Verify LLM returns valid JSON
- Verify all fields populated reasonably

### Phase B — Session summary (2-3 ngày)

**B1. Schema + prompt** (3h)
- Define `session_summary_schema`
- Prompt for cross-detection synthesis

**B2. Backend endpoint** (4h)
- `_stream_session_summary` function
- Trigger on EOS or explicit user request
- Cache for current state, invalidate on confirm/ignore

**B3. Frontend summary panel** (8h)
- New component `<SessionSummaryPanel>`
- Tabs: Tổng quan / Chi tiết / Trò chuyện
- Render structured summary with cards

**B4. Q&A chatbot interface** (6h)
- Chat input + message list
- Stream response from `ACTION_SESSION_QA`
- History persistence

### Phase C — Polish & edge cases (1-2 ngày)

**C1. Error handling** — LLM timeout, malformed JSON, partial response
**C2. Loading states** — skeleton cards, streaming indicators
**C3. Markdown fallback** — for older detections without structured report
**C4. Export to PDF** — session summary printable

---

## 💰 Cost estimation

GPT-4o vision pricing (May 2026):
- Input: ~$2.50 / 1M tokens
- Output: ~$10 / 1M tokens
- Image: ~$0.0017 / 768×768 image

Per-detection structured report:
- Input: image (1) + system prompt (~500 tokens) = ~$0.005
- Output: ~600 tokens JSON = ~$0.006
- **Total: ~$0.01 / detection**

Session summary (10 detections):
- Input: 10 detection JSON contexts (~3000 tokens) + system = ~$0.008
- Output: ~800 tokens summary = ~$0.008
- **Total: ~$0.016 / session**

Q&A follow-up (per question):
- Input: full context (~5000 tokens) = ~$0.013
- Output: ~300 tokens = ~$0.003
- **Total: ~$0.016 / question**

For 1 session with 10 detections + 5 follow-ups:
- 10 × $0.01 = $0.10 detection reports
- 1 × $0.016 = $0.016 session summary
- 5 × $0.016 = $0.08 Q&A
- **Grand total: ~$0.20 per session**

Affordable for medical use. Can drop to $0.05/session with gpt-4o-mini cho follow-up + caching.

---

## ❓ Câu hỏi cần làm rõ trước khi build

1. **Ngôn ngữ output**: chỉ tiếng Việt, hay bilingual VN+EN cho medical terms?
2. **Severity scale**: 3 mức (thấp/trung bình/cao) hay 5 mức (very low → critical)?
3. **Sinh thiết counts**: AI có nên đề xuất số mảnh cụ thể, hay chỉ "vùng cần sinh thiết"?
4. **Disclaimer**: format & wording cho "AI hỗ trợ, không thay thế bác sĩ"?
5. **Persistence scope**: localStorage 10 sessions như hiện tại, hay backend DB cho long-term?
6. **Phase 4 region classifier**: có re-add region classifier để Description.location chính xác? Hoặc dùng heuristic Y-axis tạm?
7. **Multi-language report**: bác sĩ VN có cần option export báo cáo bằng tiếng Anh cho consultation quốc tế?

---

## 🎯 Kỳ vọng outcome

Sau khi triển khai cả 2 parts:

**Workflow doctor:**
1. Upload video → start phân tích
2. AI detect tổn thương → pause video → click "Giải thích thêm"
3. **NEW**: thay vì wall of text, doctor thấy 3-section report card. Scan nhanh: "Mô tả → kích thước 6-8mm, bờ không rõ → Kết luận: nghi ngờ ung thư sớm". Action checklist dễ tick.
4. Resume → AI tiếp tục → 12 phát hiện
5. End session → click "Tạo báo cáo đầy đủ"
6. **NEW**: Session summary hiện ra. Doctor đọc 30 giây → biết ưu tiên tổn thương #5, BN cần sinh thiết khẩn.
7. **NEW**: doctor chat với AI: "tổn thương 5 vs 7 cái nào nguy hiểm hơn?" → AI compare detail trong 5s.
8. Doctor xuất báo cáo → đính kèm ý kiến chuyên môn → gửi BN.

**Time saved:** ước tính 3-5 phút mỗi case so với đọc free-form markdown + tổng hợp manually.

**Trust improved:** structured output + differential + confidence rating → doctor cảm thấy AI là consultant thực sự chứ không phải chatbot generic.

---

## 📚 References

- Paris Classification of superficial neoplastic lesions (Endoscopy 2005)
- WHO ICD-10 codes for stomach pathology
- Hội Tiêu hóa Việt Nam — Hướng dẫn nội soi dạ dày 2021
- JGCA Gastric Cancer Treatment Guidelines (Japanese)
- OpenAI Structured Outputs documentation (response_format=json_schema)

---

## ⚠ Unresolved questions

- Region classifier strategy: re-add Phase 2 model hay implement organ classifier riêng từ scratch?
- Cost optimization: có cần switch sang local Ollama (LLaVA-Med) cho production để giảm cost + privacy?
- Action checklist persistence: integrate với hospital EMR system hay standalone?
- Audit trail: lưu LLM response gốc để legal compliance không?
