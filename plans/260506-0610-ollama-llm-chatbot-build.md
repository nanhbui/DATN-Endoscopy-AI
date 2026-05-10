# Ollama LLM Chatbot — Build Plan

**Date:** 2026-05-06
**Branch:** main
**Supersedes design exploration:** [260506-0530-llm-chatbot-enhancement.md](260506-0530-llm-chatbot-enhancement.md)
**Stack decision:** Ollama + Qwen2.5-VL 7B (self-hosted on GPU server `emie@10.8.0.7`)

---

## ✅ Decisions locked in

Từ câu trả lời của user `1B 2A 3B 4C 5B 6C 7B`:

| # | Decision | Implication |
|---|----------|-------------|
| **1B** | Bilingual: term y khoa giữ EN | Vd `"Viêm dạ dày HP (Helicobacter pylori gastritis)"`, `"Phân loại Paris 0-IIa+IIc"` |
| **2A** | 3 mức severity | `thấp` / `trung bình` / `cao` |
| **3B** | Sinh thiết chung chung | Vd `"Khu vực cần sinh thiết"` thay `"5 mảnh tại bờ"` — không over-reach quyền lâm sàng |
| **4C** | Disclaimer banner + footer | Banner top mỗi report + footer ngắn ở action area |
| **5B** | Backend database | SQLite trên GPU server, không phụ thuộc localStorage |
| **6C** | Bỏ field "Vị trí" | Không cần region classifier, schema đơn giản hơn |
| **7B** | Không export EN | Single-language (VN) report only |

---

## 🏗 Architecture

### LLM backend stack

```
┌────────────────────────────────────────────────────────┐
│  Frontend (Next.js)                                    │
│  - Detection report cards                              │
│  - Session summary panel + Q&A chat                    │
└─────────────────┬──────────────────────────────────────┘
                  │ WebSocket (existing)
                  ▼
┌────────────────────────────────────────────────────────┐
│  FastAPI backend (endoscopy_ws_server.py)              │
│  - _stream_llm()           ← per-detection structured  │
│  - _stream_session_summary() ← NEW                     │
│  - _stream_session_qa()    ← NEW                       │
│  - SQLite persistence      ← NEW                       │
└─────────────────┬──────────────────────────────────────┘
                  │ HTTP localhost:11434/v1 (OpenAI-compat)
                  ▼
┌────────────────────────────────────────────────────────┐
│  Ollama runtime (on GPU server)                        │
│  - Qwen2.5-VL 7B (vision + text)                       │
│  - ~5GB VRAM                                           │
│  - 0.5-1s/request                                      │
└────────────────────────────────────────────────────────┘
```

### Why Qwen2.5-VL 7B (not LLaVA-Med)?

| Capability | Qwen2.5-VL 7B | LLaVA-Med |
|------------|--------------|-----------|
| Vision | ✅ | ✅ |
| Vietnamese | ✅ Khá | ❌ EN-focused |
| JSON schema output | ✅ | ❌ |
| Object detection / boundary | ✅ | ❌ |
| Medical knowledge | Khá | ✅ Sâu hơn |

→ Chọn Qwen2.5-VL: support JSON output (cần cho structured report), Vietnamese tốt hơn. Trade-off: medical accuracy thua LLaVA-Med ~5%, nhưng có thể fine-tune sau.

### Why SQLite (not Postgres / Redis)?

- Project hiện tại single-server, no clustering
- Sessions count ~hundreds, không cần horizontal scale
- Embedded DB → no extra service
- Backup = copy 1 file
- Đủ cho thesis, dễ migrate Postgres sau

---

## 📋 PART 1 — Per-detection Structured Report

### 1.1. JSON Schema (final)

```python
LESION_REPORT_SCHEMA = {
    "type": "object",
    "required": ["technique", "description", "conclusion"],
    "properties": {
        "technique": {
            "type": "object",
            "required": ["method", "device", "timestamp"],
            "properties": {
                "method": {"type": "string"},
                "device": {"type": "string"},
                "timestamp": {"type": "string"}
            }
        },
        "description": {
            "type": "object",
            "required": ["size_mm", "paris_class", "surface", "color", "margin", "vascular", "fluid"],
            "properties": {
                # NOTE: bỏ "location" theo decision 6C
                "size_mm": {
                    "type": "string",
                    "description": "Ước tính kích thước hoặc 'Không xác định'"
                },
                "paris_class": {
                    "type": "string",
                    "description": "Vd '0-IIa+IIc'"
                },
                "surface": {"type": "string"},
                "color": {"type": "string"},
                "margin": {"type": "string"},
                "vascular": {"type": "string"},
                "fluid": {"type": "string"}
            }
        },
        "conclusion": {
            "type": "object",
            "required": ["primary_dx", "severity", "differential", "recommendations", "ai_confidence"],
            "properties": {
                "primary_dx": {
                    "type": "string",
                    "description": "Bilingual: VN (EN). Vd 'Viêm dạ dày HP (Helicobacter pylori gastritis)'"
                },
                "severity": {
                    "type": "string",
                    "enum": ["thấp", "trung bình", "cao"]   # decision 2A
                },
                "differential": {
                    "type": "array",
                    "minItems": 2,
                    "maxItems": 3,
                    "items": {
                        "type": "object",
                        "required": ["dx", "probability_pct"],
                        "properties": {
                            "dx": {"type": "string", "description": "Bilingual"},
                            "probability_pct": {"type": "integer", "minimum": 0, "maximum": 100}
                        }
                    }
                },
                "recommendations": {
                    # decision 3B: chung chung, không số mảnh cụ thể
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Vd 'Khu vực cần sinh thiết để loại trừ ung thư', không nêu số mảnh"
                },
                "ai_confidence": {
                    "type": "integer",
                    "minimum": 0,
                    "maximum": 100,
                    "description": "AI tự đánh giá độ tin cậy"
                }
            }
        }
    }
}
```

### 1.2. System prompt (Vietnamese, bilingual hint)

```python
LESION_REPORT_PROMPT = """
Bạn là trợ lý nội soi tiêu hóa AI cho bác sĩ Việt Nam. Phân tích ảnh tổn thương
endoscopy và trả về báo cáo có cấu trúc theo schema JSON.

## QUY TẮC NGÔN NGỮ (BẮT BUỘC)
Viết bằng tiếng Việt, NHƯNG giữ nguyên thuật ngữ y khoa tiếng Anh trong ngoặc:
  ✅ "Viêm dạ dày HP (Helicobacter pylori gastritis)"
  ✅ "Phân loại Paris 0-IIa+IIc (Paris classification)"
  ✅ "Loét bờ fibrin (fibrin-margin ulcer)"
  ❌ "Helicobacter pylori gastritis" (thiếu phần VN)
  ❌ "Viêm dạ dày HP" (thiếu phần EN cho thuật ngữ)

## QUY TẮC KÍCH THƯỚC
Ước lượng từ:
- Đường kính scope tham chiếu (~9-13mm cho EG-760Z)
- So với nếp gấp dạ dày (~3-5mm)
- Snare/forceps trong ảnh (nếu có)
Format: "X-Y mm" hoặc "ước tính N mm". Không xác định được thì ghi "Không xác định".

## QUY TẮC KHUYẾN NGHỊ
KHÔNG đề xuất số mảnh sinh thiết cụ thể. Chỉ ghi vùng/hành động chung:
  ✅ "Khu vực cần sinh thiết để loại trừ ung thư"
  ✅ "Cân nhắc test CLO tại chỗ"
  ❌ "Sinh thiết 5 mảnh tại bờ" (over-reach)

## QUY TẮC SEVERITY
Chỉ 3 mức: "thấp" | "trung bình" | "cao"

## QUY TẮC DIFFERENTIAL
Bắt buộc 2-3 chẩn đoán phân biệt, sắp xếp theo xác suất giảm dần. Tổng = 100%.

## PHÂN LOẠI PARIS (BẮT BUỘC ÁP DỤNG)
[... Paris classification rules ...]

## DẤU HIỆU H. PYLORI
- HP-negative: niêm mạc bình thường hoặc viêm nhẹ
- HP-positive: viêm xung huyết, nốt lymphoid, vết trợt nông
- Gastric cancer: tổn thương Paris 0-IIc / 0-IIa+IIc / 0-III

Trả về JSON theo schema. Không thêm text khác ngoài JSON.
"""
```

### 1.3. Backend implementation outline

```python
# endoscopy_ws_server.py

import os
from openai import AsyncOpenAI

LLM_BACKEND = os.getenv("LLM_BACKEND", "openai")  # "openai" | "ollama"
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434/v1")
OLLAMA_MODEL = os.getenv("OLLAMA_MODEL", "qwen2.5vl:7b")

def _get_llm_client():
    if LLM_BACKEND == "ollama":
        return AsyncOpenAI(api_key="ollama", base_url=OLLAMA_BASE_URL)
    return AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))

def _llm_model_name():
    return OLLAMA_MODEL if LLM_BACKEND == "ollama" else LLM_MODEL_VISION

async def _stream_lesion_report(websocket, detection, sess, ws_lock):
    """Replaces _stream_llm — generates structured 3-section report."""
    client = _get_llm_client()
    img_b64 = detection["frame_b64"]
    label = detection["lesion"]["label"]
    confidence = detection["lesion"]["confidence"]

    user_msg = (
        f"Tổn thương phát hiện: {label} (conf={confidence*100:.0f}%).\n"
        f"Phân tích ảnh và trả về structured report theo schema."
    )

    messages = [
        {"role": "system", "content": LESION_REPORT_PROMPT},
        {"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{img_b64}"}},
            {"type": "text", "text": user_msg}
        ]}
    ]

    # Both Ollama (Qwen2.5+) and OpenAI support response_format
    response = await client.chat.completions.create(
        model=_llm_model_name(),
        messages=messages,
        response_format={"type": "json_schema",
                         "json_schema": {"name": "lesion_report", "schema": LESION_REPORT_SCHEMA}},
        stream=False,        # JSON schema needs full response
        max_tokens=1500,
    )

    raw_json = response.choices[0].message.content
    report = json.loads(raw_json)

    # Persist to DB
    db_save_lesion_report(sess["video_id"], detection["frame_index"], report)

    # Send to frontend
    await websocket.send_json({
        "event": "LESION_REPORT_DONE",
        "data": {"detection_frame_index": detection["frame_index"], "report": report}
    })
```

### 1.4. Frontend rendering

New component `<LesionReportCard>` thay cho free-form markdown:

```tsx
// frontend/components/lesion-report-card.tsx
interface LesionReport {
  technique: { method: string; device: string; timestamp: string };
  description: {
    size_mm: string; paris_class: string; surface: string;
    color: string; margin: string; vascular: string; fluid: string;
  };
  conclusion: {
    primary_dx: string;
    severity: 'thấp' | 'trung bình' | 'cao';
    differential: { dx: string; probability_pct: number }[];
    recommendations: string[];
    ai_confidence: number;
  };
}

export function LesionReportCard({ report }: { report: LesionReport }) {
  return (
    <Box>
      {/* DECISION 4C — top banner disclaimer */}
      <DisclaimerBanner />

      <Section icon="📋" title="Kỹ thuật">
        <KVRow label="Phương pháp" value={report.technique.method} />
        <KVRow label="Thiết bị"   value={report.technique.device} />
        <KVRow label="Thời điểm"  value={report.technique.timestamp} />
      </Section>

      <Section icon="🔍" title="Mô tả">
        <KVRow label="Kích thước"     value={report.description.size_mm} highlight />
        <KVRow label="Phân loại Paris" value={report.description.paris_class} />
        <KVRow label="Bề mặt"          value={report.description.surface} />
        <KVRow label="Màu sắc"         value={report.description.color} />
        <KVRow label="Bờ tổn thương"   value={report.description.margin} />
        <KVRow label="Mạch máu"        value={report.description.vascular} />
        <KVRow label="Dịch / Máu"      value={report.description.fluid} />
      </Section>

      <Section icon="💡" title="Kết luận">
        <SeverityBadge level={report.conclusion.severity} />
        <PrimaryDx>{report.conclusion.primary_dx}</PrimaryDx>

        <Subsection title="Chẩn đoán phân biệt">
          {report.conclusion.differential.map((d, i) => (
            <DifferentialRow key={i} dx={d.dx} pct={d.probability_pct} />
          ))}
        </Subsection>

        <Subsection title="Khuyến nghị">
          {report.conclusion.recommendations.map((r, i) => (
            <RecommendationItem key={i}>{r}</RecommendationItem>
          ))}
        </Subsection>

        <ConfidenceBar pct={report.conclusion.ai_confidence} />
      </Section>

      {/* DECISION 4C — footer disclaimer */}
      <DisclaimerFooter />
    </Box>
  );
}

function DisclaimerBanner() {
  return (
    <Box sx={{ bgcolor: '#FEF3C7', border: '1px solid #FCD34D', p: 1.5, mb: 2 }}>
      <Typography sx={{ fontSize: '0.8rem', color: '#78350F' }}>
        ⚠ Báo cáo này là gợi ý hỗ trợ từ AI. <strong>Không thay thế đánh giá của bác sĩ chuyên khoa</strong>.
        Mọi quyết định lâm sàng (sinh thiết, điều trị) phải được bác sĩ phê duyệt.
      </Typography>
    </Box>
  );
}

function DisclaimerFooter() {
  return (
    <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled', textAlign: 'center', mt: 2 }}>
      Powered by Qwen2.5-VL · AI confidence ≠ medical certainty
    </Typography>
  );
}
```

---

## 📋 PART 2 — Session Summary + Q&A Chatbot

### 2.1. Session Summary Schema

```python
SESSION_SUMMARY_SCHEMA = {
    "type": "object",
    "required": ["overview", "priority_findings", "patterns", "checklist", "overall_risk"],
    "properties": {
        "overview": {
            "type": "object",
            "required": ["total_findings", "duration_seconds", "confirmed_count", "ignored_count"],
            "properties": {
                "total_findings": {"type": "integer"},
                "duration_seconds": {"type": "integer"},
                "confirmed_count": {"type": "integer"},
                "ignored_count": {"type": "integer"}
            }
        },
        "priority_findings": {
            "type": "array",
            "description": "Top 3-5 phát hiện ưu tiên cao theo severity",
            "items": {
                "type": "object",
                "required": ["frame_index", "severity", "primary_dx", "rationale"],
                "properties": {
                    "frame_index": {"type": "integer"},
                    "severity": {"type": "string", "enum": ["thấp", "trung bình", "cao"]},
                    "primary_dx": {"type": "string"},
                    "rationale": {"type": "string", "description": "1-2 câu giải thích vì sao ưu tiên"}
                }
            }
        },
        "patterns": {
            "type": "array",
            "description": "Pattern xuyên suốt phiên (vd 'viêm HP lan tỏa', 'polyp đa ổ')",
            "items": {"type": "string"}
        },
        "checklist": {
            "type": "array",
            "description": "Action items tổng hợp, đã gộp tránh trùng lặp",
            "items": {
                "type": "object",
                "required": ["category", "action"],
                "properties": {
                    "category": {"type": "string", "enum": ["sinh_thiet", "test", "dieu_tri", "tai_kham"]},
                    "action": {"type": "string"}
                }
            }
        },
        "overall_risk": {
            "type": "string",
            "enum": ["thấp", "trung bình", "cao"],
            "description": "Đánh giá nguy cơ tổng thể của bệnh nhân"
        }
    }
}
```

### 2.2. Q&A Chat (free-form)

```python
async def _stream_session_qa(websocket, question, sess, ws_lock):
    """Free-form chat about the session — text-only, fast model."""
    detection_summaries = [
        f"#{i}: {d['lesion']['label']} ({d['lesion']['confidence']*100:.0f}%) tại {d['timestamp_ms']/1000:.0f}s"
        for i, d in enumerate(sess["confirmed_detections"])
    ]
    context = "\n".join(detection_summaries)

    messages = [
        {"role": "system", "content": SESSION_QA_PROMPT},
        {"role": "user", "content": (
            f"PHIÊN NỘI SOI ĐÃ HOÀN TẤT.\n"
            f"Tổng phát hiện: {len(sess['confirmed_detections'])}\n"
            f"Danh sách:\n{context}\n\n"
            f"Báo cáo tổng quan: {json.dumps(sess.get('llm_summary', {}), ensure_ascii=False)}\n\n"
            f"Câu hỏi: {question}"
        )}
    ]

    # Streaming
    stream = await _get_llm_client().chat.completions.create(
        model=_llm_model_name(),
        messages=messages,
        stream=True,
        max_tokens=600,
    )
    async for chunk in stream:
        delta = chunk.choices[0].delta.content or ""
        if delta:
            await websocket.send_json({"event": "QA_CHUNK", "data": {"chunk": delta}})
    await websocket.send_json({"event": "QA_DONE", "data": {}})
```

---

## 💾 Database schema (SQLite, decision 5B)

```sql
-- File: /home/emie/DATN_ver0/data/endoscopy.db (on remote GPU server)

CREATE TABLE sessions (
    id            TEXT PRIMARY KEY,
    video_id      TEXT NOT NULL,
    name          TEXT,
    source        TEXT,                      -- upload | live | library
    started_at    INTEGER NOT NULL,          -- unix ms
    ended_at      INTEGER,
    metadata_json TEXT                        -- {device, scope_id, ...}
);

CREATE TABLE detections (
    session_id    TEXT NOT NULL,
    frame_index   INTEGER NOT NULL,
    timestamp_ms  INTEGER NOT NULL,
    label         TEXT,
    confidence    REAL,
    bbox_json     TEXT,                       -- {x, y, w, h} normalized
    bbox_thumb_json TEXT,                     -- viewport-relative %
    frame_b64     TEXT,                       -- base64 image
    status        TEXT,                       -- detected | confirmed | ignored | analyzed
    PRIMARY KEY (session_id, frame_index),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE lesion_reports (
    session_id    TEXT NOT NULL,
    frame_index   INTEGER NOT NULL,
    report_json   TEXT NOT NULL,              -- LesionReport schema
    generated_at  INTEGER NOT NULL,           -- unix ms
    model         TEXT,                        -- qwen2.5vl:7b | gpt-4o
    PRIMARY KEY (session_id, frame_index),
    FOREIGN KEY (session_id, frame_index) REFERENCES detections(session_id, frame_index) ON DELETE CASCADE
);

CREATE TABLE session_summaries (
    session_id    TEXT PRIMARY KEY,
    summary_json  TEXT NOT NULL,
    generated_at  INTEGER NOT NULL,
    model         TEXT,
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE TABLE qa_messages (
    session_id    TEXT NOT NULL,
    sequence      INTEGER NOT NULL,
    role          TEXT,                        -- user | assistant
    content       TEXT,
    created_at    INTEGER NOT NULL,
    PRIMARY KEY (session_id, sequence),
    FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
);

CREATE INDEX idx_detections_session ON detections(session_id);
CREATE INDEX idx_qa_session ON qa_messages(session_id);
```

API endpoints mới:

```
GET  /sessions                        — list all sessions (replaces localStorage)
GET  /sessions/{id}                   — full session detail
GET  /sessions/{id}/detections        — all detections + reports
GET  /sessions/{id}/qa                — chat history
POST /sessions/{id}/qa                — send new question (returns streaming WS)
DELETE /sessions/{id}                 — delete session
```

Frontend: thay `loadSessions()` từ localStorage → fetch from `/sessions`.

---

## 🚀 Implementation phases

### Phase 0 — Setup Ollama (30 phút)

```bash
# On remote GPU server emie@10.8.0.7
ssh emie@10.8.0.7

# Install Ollama
curl -fsSL https://ollama.com/install.sh | sh

# Pull Qwen2.5-VL 7B (~5GB Q4 quantized)
ollama pull qwen2.5vl:7b

# Verify
curl http://localhost:11434/api/tags
ollama run qwen2.5vl:7b "test"

# Configure backend env
cd ~/DATN_ver0
echo "LLM_BACKEND=ollama" >> src/backend/api/.env
echo "OLLAMA_BASE_URL=http://localhost:11434/v1" >> src/backend/api/.env
echo "OLLAMA_MODEL=qwen2.5vl:7b" >> src/backend/api/.env
```

### Phase A — Per-detection report (3-4 ngày)

- **A1** (4h): Add `LESION_REPORT_SCHEMA`, `LESION_REPORT_PROMPT` to backend
- **A2** (3h): Implement `_stream_lesion_report()`, replace `_stream_llm()`
- **A3** (4h): SQLite setup — `lesion_reports` table + persistence layer
- **A4** (8h): Frontend `<LesionReportCard>` component with 3 sections
- **A5** (3h): `<DisclaimerBanner>`, `<DisclaimerFooter>` components
- **A6** (3h): Replace ReactMarkdown LLM Smart Log with structured card
- **A7** (4h): Test with 15-20 sample detections, tune prompt

### Phase B — Session summary + Q&A (2-3 ngày)

- **B1** (4h): `SESSION_SUMMARY_SCHEMA` + prompt
- **B2** (3h): Backend `_stream_session_summary()` triggered on EOS
- **B3** (3h): Backend `_stream_session_qa()` for follow-up
- **B4** (8h): Frontend `<SessionSummaryPanel>` with tabs (Overview / Detail / Chat)
- **B5** (5h): `<SessionChatInterface>` — input box, message list, streaming render
- **B6** (3h): SQLite — `session_summaries`, `qa_messages` tables
- **B7** (3h): Migration: localStorage → backend API for session list

### Phase C — Polish (1-2 ngày)

- **C1** (3h): Error handling — Ollama down, malformed JSON, timeout
- **C2** (3h): Loading skeletons, streaming progress indicators
- **C3** (4h): Backward compat — older detections without structured report (markdown fallback)
- **C4** (4h): Export PDF — full session report (gộp summary + all detection reports)
- **C5** (2h): Backend health check `/health/ollama`

---

## 🧪 Testing plan

### Unit tests (Phase A)
- LLM JSON output passes schema validation
- Severity always in enum
- Differential probabilities sum ≤ 100
- Bilingual format detected (regex check VN + EN)

### Integration tests
- 15 lab video frames covering: viêm thực quản, HP gastritis, ung thư dạ dày, loét HTT
- Compare GPT-4o vs Ollama Qwen output for same frames
- Tune prompt until Qwen achieves >75% match with GPT-4o on key fields

### User acceptance (manual)
- Doctor reviews 5 sample reports
- Feedback on: kích thước accuracy, differential ranking, recommendation phrasing
- Iterate prompt 2-3 lần dựa trên feedback

---

## 🔧 Migration path (OpenAI → Ollama)

Keep both backends behind env flag:

```python
LLM_BACKEND = os.getenv("LLM_BACKEND", "ollama")   # default ollama
```

Switching:
- `LLM_BACKEND=ollama` → free, fast, on-prem
- `LLM_BACKEND=openai` → fallback if Ollama down OR cần accuracy cao

Frontend không biết backend nào — chỉ nhận structured event payload identical.

Migration steps:
1. Phase A xong: test cả 2 backends, default Ollama
2. Run side-by-side 1 tuần — log accuracy comparisons
3. Nếu Ollama đủ tốt → permanent default
4. Nếu Ollama yếu → hybrid (vision = OpenAI, text = Ollama)

---

## 📊 Expected outcomes

### Doctor UX flow

1. Upload video → analyze
2. AI detects lesion → pause → click **"Giải thích thêm"**
3. **NEW**: 3-section structured card hiện ra trong ~1s (vs 2-3s GPT-4o):
   - 📋 Kỹ thuật (auto-fill)
   - 🔍 Mô tả (Qwen vision analysis với bilingual terms)
   - 💡 Kết luận (severity badge, differential, recommendations checklist)
4. Doctor scan nhanh → tick recommendations đã làm → resume
5. End session → click **"Tạo báo cáo đầy đủ"**
6. **NEW**: Session summary panel với 3 tabs:
   - Tổng quan (priority findings, patterns, checklist)
   - Chi tiết (list all detection cards)
   - Trò chuyện AI (Q&A free-form)
7. Doctor hỏi tiếp: "tổn thương 5 vs 7 cái nào nguy hiểm hơn?"
8. AI streaming response trong 0.5-1s
9. Export PDF → đính vào EMR

### Performance targets

| Metric | Target | Achievable với Qwen2.5-VL 7B local |
|--------|--------|-----------------------------------|
| Lesion report latency | <2s | ✅ ~1s |
| Session summary latency | <3s | ✅ ~2s |
| Q&A response start | <1s | ✅ ~0.5s |
| Cost per session | <$0.05 | ✅ $0 |
| Privacy compliance | BN data not leaving server | ✅ |

---

## ⚠ Risks & mitigations

| Risk | Likelihood | Impact | Mitigation |
|------|-----------|--------|-----------|
| Qwen2.5-VL 7B hallucinate Vietnamese medical terms | Medium | Medium | Prompt engineering + few-shot examples; fallback OpenAI if confidence <60% |
| GPU server downtime | Low | High | Health check endpoint; auto-fallback to OpenAI |
| JSON schema not respected by Qwen | Low | Medium | Use `format=json` Ollama option + retry on parse failure |
| Database migration complexity | Medium | Low | Keep localStorage as cache layer initially, sync to DB async |
| Ollama updates breaking compatibility | Low | Low | Pin Ollama version; document upgrade procedure |
| Privacy: where is patient frame_b64 stored? | High | High | Document retention policy; hash-based dedup; encrypted DB option |

---

## ❓ Câu hỏi còn mở (cần làm rõ trước Phase A)

1. **Disclaimer wording chính xác**: bạn có template từ Bộ Y Tế không? Hay tự draft?
2. **Sessions retention**: lưu vĩnh viễn hay auto-cleanup sau N ngày?
3. **Data export format**: PDF only hay cả JSON / DICOM-SR?
4. **Ollama fallback**: nếu Ollama down 3 lần liên tiếp, có auto-switch sang OpenAI không (cần API key dự phòng)?
5. **Multi-tenant**: 1 BV nhiều BS → cần auth + per-user session list không?

---

## 📚 References

- [Ollama OpenAI compatibility docs](https://github.com/ollama/ollama/blob/main/docs/openai.md)
- [Qwen2.5-VL technical report](https://qwenlm.github.io/blog/qwen2.5-vl/)
- [Paris Classification of superficial lesions, Endoscopy 2005](https://pubmed.ncbi.nlm.nih.gov/16261560/)
- [JSON Schema with structured outputs — OpenAI docs](https://platform.openai.com/docs/guides/structured-outputs)
- Previous design exploration: [260506-0530-llm-chatbot-enhancement.md](./260506-0530-llm-chatbot-enhancement.md)
