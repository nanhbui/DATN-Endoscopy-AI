"""LLM prompts and JSON schemas for session summary + Q&A chatbot (Phase B).

Separated from llm_prompts.py (Phase A — per-detection lesion report) because:
  - Different output shape (summary aggregates many detections, single report describes one)
  - Different input shape (summary reads pre-parsed reports, lesion takes one image)
  - Different cadence (summary fires once on EOS, lesion fires per detection)

Both phases share the same LLM backend (Ollama qwen2.5vl:7b) — text-only here, no
images needed since per-detection reports already carry the visual analysis.
"""

# ── Session summary schema ───────────────────────────────────────────────────
#
# Aggregates all lesion_reports of a session into a clinical-overview document.
# Decisions inherited from Phase A:
#   - 3-level severity enum (thấp / trung bình / cao)
#   - Vietnamese primary lang, bilingual term in parens for medical phrases
#   - "Recommendations are general" — no specific biopsy counts / drug doses
#
# Required fields enforce that the summary covers all clinically meaningful
# angles (overview stats, top findings, longitudinal patterns, action checklist,
# overall risk). Partial outputs would break the frontend's structured panel.

SESSION_SUMMARY_SCHEMA = {
    "type": "object",
    "required": ["overview", "priority_findings", "patterns", "checklist", "overall_risk"],
    "properties": {
        "overview": {
            "type": "object",
            "required": ["total_findings", "duration_seconds", "confirmed_count", "ignored_count"],
            "properties": {
                "total_findings": {
                    "type": "integer",
                    "description": "Tổng số tổn thương được AI phát hiện trong phiên",
                },
                "duration_seconds": {
                    "type": "integer",
                    "description": "Tổng thời lượng phiên (giây)",
                },
                "confirmed_count": {
                    "type": "integer",
                    "description": "Số tổn thương bác sĩ đã xác nhận",
                },
                "ignored_count": {
                    "type": "integer",
                    "description": "Số tổn thương bác sĩ bỏ qua / báo sai",
                },
            },
        },
        "priority_findings": {
            "type": "array",
            "minItems": 0,
            "maxItems": 5,
            "description": "Top 3-5 phát hiện ưu tiên cao — sắp theo severity giảm dần",
            "items": {
                "type": "object",
                "required": ["frame_index", "severity", "primary_dx", "rationale"],
                "properties": {
                    "frame_index": {"type": "integer"},
                    "severity": {"type": "string", "enum": ["thấp", "trung bình", "cao"]},
                    "primary_dx": {
                        "type": "string",
                        "description": "Bilingual VN (EN), khớp với primary_dx của lesion_report gốc",
                    },
                    "rationale": {
                        "type": "string",
                        "description": "1-2 câu giải thích vì sao ưu tiên (kết hợp severity + paris_class + size)",
                    },
                },
            },
        },
        "patterns": {
            "type": "array",
            "description": (
                "Pattern xuyên suốt phiên — đặc điểm chung của nhiều tổn thương. "
                "Vd 'Viêm HP lan tỏa toàn bộ thân và hang vị', "
                "'Đa ổ Paris 0-IIa+IIc nghi tiền ung thư'"
            ),
            "items": {"type": "string"},
        },
        "checklist": {
            "type": "array",
            "minItems": 0,
            "description": (
                "Action items tổng hợp đã gộp tránh trùng lặp (vd nếu 3 detection "
                "cùng đề xuất sinh thiết, gom thành 1 action với scope rõ)"
            ),
            "items": {
                "type": "object",
                "required": ["category", "action"],
                "properties": {
                    "category": {
                        "type": "string",
                        "enum": ["sinh_thiet", "test", "dieu_tri", "tai_kham"],
                        "description": "Phân loại action — KHÔNG dùng dấu, dùng underscore",
                    },
                    "action": {
                        "type": "string",
                        "description": "Mô tả hành động cụ thể, bắt đầu bằng động từ",
                    },
                },
            },
        },
        "overall_risk": {
            "type": "string",
            "enum": ["thấp", "trung bình", "cao"],
            "description": (
                "Nguy cơ tổng thể bệnh nhân — KHÔNG phải max severity của 1 finding, "
                "mà là đánh giá tổng hợp (vd 1 finding cao + 5 finding thấp → trung bình)"
            ),
        },
    },
}


# ── System prompt cho session summary ────────────────────────────────────────
#
# Đặc điểm prompt:
#   - Text-only (input là các structured lesion report đã parse, không cần ảnh)
#   - Force tiếng Việt + bilingual cho thuật ngữ y khoa (như Phase A)
#   - Gộp action items: nếu nhiều finding cùng category, merge thành 1
#   - "Patterns" chỉ ghi khi THỰC SỰ có pattern (>=2 finding cùng đặc điểm)
#   - Overall risk là HOLISTIC, không phải max severity

SESSION_SUMMARY_PROMPT = """\
Bạn là bác sĩ nội soi tiêu hóa cao cấp. Bệnh nhân vừa nội soi xong và bạn nhận
các báo cáo per-lesion do AI sinh ra cho từng tổn thương được phát hiện.

Nhiệm vụ: TỔNG HỢP toàn bộ thành 1 báo cáo PHIÊN theo schema endoscopy_session_summary.

## QUY TẮC NGÔN NGỮ
Viết tiếng Việt. Thuật ngữ y khoa giữ EN trong ngoặc:
  ✅ "Viêm dạ dày HP (Helicobacter pylori gastritis) lan tỏa"
  ✅ "Đa ổ Paris 0-IIa+IIc"
  ❌ "HP gastritis" (thiếu VN)

## QUY TẮC PRIORITY_FINDINGS
Liệt kê 3-5 finding nguy hiểm nhất. Sắp xếp:
  1. severity "cao" trước
  2. cùng severity → ai_confidence cao trước
  3. cùng confidence → Paris class nghi ngờ hơn (0-IIc > 0-IIa > 0-Ip)

Mỗi finding KHỚP frame_index của lesion_report gốc.
Rationale 1-2 câu: kết hợp severity + paris_class + size + đặc điểm chính.

## QUY TẮC PATTERNS
CHỈ ghi pattern khi có ≥2 finding cùng đặc điểm. KHÔNG bịa pattern khi mỗi
finding riêng biệt.
  ✅ "Viêm HP lan tỏa toàn bộ niêm mạc thân + hang vị (5/5 finding có HP)"
  ✅ "Đa ổ Paris 0-IIa+IIc nghi tiền ung thư (3 finding)"
  ❌ "Có 1 polyp" (chỉ 1 finding — KHÔNG phải pattern, để vào priority_findings)

Mảng rỗng [] nếu không có pattern xuyên suốt.

## QUY TẮC CHECKLIST
Gộp action items từ tất cả per-detection recommendations:
  - Nếu 3 finding cùng đề xuất "sinh thiết", merge thành 1 action với scope
    rõ (vd "Sinh thiết tại các vị trí ưu tiên — bờ tổn thương ở 3 vùng đã đánh dấu")
  - Phân category đúng:
    * sinh_thiet  — sinh thiết, lấy mẫu mô
    * test        — CLO-test, máu, huyết thanh, NBI
    * dieu_tri    — kê thuốc, can thiệp
    * tai_kham    — hẹn tái khám, theo dõi
  - Action PHẢI bắt đầu bằng động từ.

## QUY TẮC OVERALL_RISK
KHÔNG đơn thuần lấy max severity. Đánh giá tổng hợp:
  - "cao":        có ≥1 finding nghi ác tính / Paris 0-IIc nghi ngờ rõ
  - "trung bình": có nhiều finding viêm + có vài Paris 0-IIa nghi ngờ
  - "thấp":       chỉ viêm lành tính, không tổn thương cấu trúc

## QUY TẮC "KHÔNG BỊA"
Mọi data PHẢI dựa trên các per-detection report được cung cấp. KHÔNG bịa
thêm finding hoặc đặc điểm. Nếu một field nào đó không suy ra được từ data,
ghi ngắn gọn / để rỗng theo schema.

## OUTPUT
CHỈ trả về JSON theo schema endoscopy_session_summary. Không markdown, không
giới thiệu, không giải thích. JSON phải parse được bằng json.loads().
"""


# ── Q&A chatbot (Phase B3) ───────────────────────────────────────────────────
#
# Free-form chat about the session — bác sĩ hỏi "tổn thương nào nguy hiểm nhất",
# "có nên sinh thiết frame 214 không", etc. Streaming text response (not JSON
# schema) because chat is conversational, not structured.

SESSION_QA_PROMPT = """\
Bạn là trợ lý nội soi tiêu hóa AI. Bác sĩ vừa hoàn thành một phiên nội soi
và đang hỏi bạn về kết quả. Bạn có CONTEXT đầy đủ gồm:
  1. Per-detection report của từng tổn thương (Phase A đã sinh)
  2. Session summary (Phase B đã sinh)
  3. Lịch sử cuộc hội thoại

## QUY TẮC TRẢ LỜI
- Tiếng Việt, thuật ngữ y khoa kèm EN trong ngoặc khi lần đầu nhắc:
    ✅ "Loét bờ fibrin (fibrin-margin ulcer)"
- NGẮN GỌN. 2-4 câu cho câu hỏi đơn giản, 1 paragraph cho câu hỏi phức tạp.
  Không lặp lại toàn bộ summary nếu user chỉ hỏi 1 điểm.
- Mọi nhận định PHẢI dựa trên data trong context. KHÔNG bịa frame index, label,
  severity, recommendations.
- Nếu câu hỏi vượt ra ngoài data (vd "bệnh nhân này có cần PPI không"), nói rõ:
  "Không có thông tin trong báo cáo phiên — bác sĩ cần thông tin lâm sàng bổ sung."
- KHÔNG over-reach quyền chỉ định lâm sàng. Đề xuất chung chung, không liều thuốc cụ thể.

## REFERENCE FORMAT
Khi trích finding cụ thể, dùng format: "frame N — primary_dx (severity)"
  Vd: "Frame 214 — Loét bờ fibrin (cao)"

## OUTPUT
Văn bản thuần. KHÔNG JSON, KHÔNG markdown heading. Có thể dùng bullet (-) cho list.
"""


def build_session_qa_messages(summary: dict | None, reports: list[dict],
                              history: list[dict], user_question: str) -> list[dict]:
    """Build the OpenAI-format messages list for a Q&A turn.

    Strategy: stuff session summary + per-detection labels into a single
    'context' system message after the main system prompt. Reports are
    compressed (label + severity + paris only) to keep token count low —
    the full reports were already used to BUILD the summary, so we don't
    need them re-summarized here.

    Args:
      summary: dict from SESSION_SUMMARY_SCHEMA (or None if not yet generated)
      reports: list from db.get_lesion_reports_for_session()
      history: list from db.get_qa_history() — alternating user/assistant
      user_question: the new turn from doctor
    """
    # Compact context block — give LLM enough to answer without flooding tokens.
    ctx_lines = ["## CONTEXT — Báo cáo phiên hiện tại"]
    if summary:
        import json as _json
        ctx_lines.append(f"### Session summary:\n{_json.dumps(summary, ensure_ascii=False, indent=2)}")
    else:
        ctx_lines.append("### Session summary: (chưa có — chưa kết thúc phiên)")

    ctx_lines.append("\n### Findings (per-frame):")
    for r in reports:
        rep = r.get("report", {})
        concl = rep.get("conclusion", {})
        desc = rep.get("description", {})
        ctx_lines.append(
            f"- frame {r['frame_index']}: {concl.get('primary_dx', '?')} "
            f"[{concl.get('severity', '?')}, Paris {desc.get('paris_class', '?')}]"
        )

    messages: list[dict] = [
        {"role": "system", "content": SESSION_QA_PROMPT},
        {"role": "system", "content": "\n".join(ctx_lines)},
    ]
    # Replay history (alternating user/assistant) so LLM has full conversation.
    for msg in history:
        messages.append({"role": msg["role"], "content": msg["content"]})
    # Current turn.
    messages.append({"role": "user", "content": user_question})
    return messages


def build_session_summary_input(reports: list[dict],
                                 confirmed_count: int = 0,
                                 ignored_count: int = 0,
                                 duration_seconds: int = 0) -> str:
    """Format the list of per-detection lesion reports as the user-side input.

    The model receives a compact text dump of every report (no images — those
    were already analyzed during Phase A). We include the fields the summary
    needs to reason about: frame_index for cross-reference, severity for
    sorting, paris_class + size for clinical context, recommendations to
    aggregate into the checklist.

    `reports` is the list from db.get_lesion_reports_for_session() — each row
    has {frame_index, report (full LesionReport dict), generated_at, model,
    label, severity}.
    """
    lines = [
        f"## Thống kê phiên",
        f"- Tổng số finding: {len(reports)}",
        f"- Thời lượng: {duration_seconds} giây",
        f"- Đã xác nhận: {confirmed_count}",
        f"- Bỏ qua / báo sai: {ignored_count}",
        "",
        f"## Per-detection reports (đã được AI phân tích từng frame)",
    ]
    for i, row in enumerate(reports, 1):
        rep = row.get("report", {})
        concl = rep.get("conclusion", {})
        desc = rep.get("description", {})
        # Truncate fields that can be very long to keep prompt token-efficient.
        recs = concl.get("recommendations", []) or []
        diffs = concl.get("differential", []) or []
        diff_str = ", ".join(
            f"{d.get('dx', '?')[:60]} ({d.get('probability_pct', 0)}%)"
            for d in diffs[:3]
        )
        lines.extend([
            "",
            f"### Finding #{i} — frame {row.get('frame_index')}",
            f"- primary_dx: {concl.get('primary_dx', '?')}",
            f"- severity: {concl.get('severity', '?')}  (AI conf {concl.get('ai_confidence', 0)}%)",
            f"- Paris: {desc.get('paris_class', '?')}",
            f"- size: {desc.get('size_mm', '?')}",
            f"- differential: {diff_str}" if diff_str else "- differential: (không có)",
            "- recommendations:",
        ])
        for r in recs[:5]:
            lines.append(f"  · {r}")

    lines.extend([
        "",
        "## Yêu cầu",
        "Tổng hợp các finding trên thành 1 báo cáo phiên theo schema "
        "endoscopy_session_summary. Tuân thủ 5 QUY TẮC ở system prompt.",
    ])
    return "\n".join(lines)
