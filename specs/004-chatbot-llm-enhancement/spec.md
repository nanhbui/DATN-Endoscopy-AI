# Feature Specification: Chatbot LLM Enhancement

**Feature Branch**: `004-chatbot-llm-enhancement`
**Created**: 2026-05-01
**Status**: Draft
**Input**: User description: "Upgrade chatbot LLM từ text-only GPT-4o-mini sang GPT-4o vision với Paris classification, hybrid follow-up pattern, conversation memory, và in-session response caching."

---

## Overview

Nâng cấp luồng giải thích AI trong hệ thống nội soi từ text-only (chỉ nhận label + confidence) sang visual analysis (nhận trực tiếp hình ảnh frame phát hiện tổn thương), đồng thời bổ sung khả năng hội thoại follow-up và caching để tối ưu chi phí.

**Primary users**: Bác sĩ nội tiêu hóa đang thực hiện ca nội soi.

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Visual Analysis với Paris Classification (Priority: P1)

Bác sĩ yêu cầu giải thích sau khi hệ thống phát hiện tổn thương. Thay vì chỉ nhận nhận xét chung dựa trên tên label, bác sĩ nhận được phân tích trực quan từ hình ảnh thực tế của tổn thương kèm phân loại Paris chính xác.

**Why this priority**: Đây là giá trị cốt lõi — LLM hiện tại "mù" (không thấy ảnh). Việc bổ sung visual analysis là thay đổi có impact lâm sàng lớn nhất.

**Independent Test**: Trigger giải thích trên một detection có frame_b64 → response phải chứa Paris classification (0-Is/Ip/IIa/IIb/IIc/IIa+IIc/III) dựa trên đặc điểm hình ảnh, không chỉ dựa trên tên label.

**Acceptance Scenarios**:

1. **Given** pipeline dừng tại detection có frame_b64, **When** bác sĩ yêu cầu giải thích, **Then** response bao gồm Paris classification với mô tả đặc điểm hình thái (màu sắc, bờ viền, kích thước ước tính)
2. **Given** response được tạo, **When** bác sĩ đọc kết quả, **Then** thấy đủ 3 phần: Phân loại Paris, Nhận định lâm sàng (nguy cơ), Checklist hành động
3. **Given** detection không có frame_b64 (edge case), **When** giải thích được yêu cầu, **Then** hệ thống fallback sang text-only analysis với label + location, không crash
4. **Given** API key không hợp lệ hoặc timeout, **When** giải thích được yêu cầu, **Then** mock response được trả về với đầy đủ cấu trúc

---

### User Story 2 — Follow-up Hội Thoại (Priority: P2)

Sau khi nhận giải thích ban đầu, bác sĩ có thể hỏi thêm câu hỏi cụ thể về tổn thương (vị trí sinh thiết, nguy cơ ác tính, phân biệt với polyp lành tính, v.v.) mà không cần giải thích lại từ đầu.

**Why this priority**: Follow-up questions là hành vi tự nhiên trong lâm sàng. Không có context thì mỗi câu hỏi phải gửi lại toàn bộ ảnh và prompt → tốn kém và chậm.

**Independent Test**: Sau initial explain, bác sĩ gõ/nói "sinh thiết ở đâu?" → response tham chiếu đến tổn thương đã phân tích (không phân tích lại từ đầu), trả lời nhanh hơn lần đầu.

**Acceptance Scenarios**:

1. **Given** initial explain đã hoàn tất, **When** bác sĩ gửi follow-up question, **Then** response tham chiếu phân tích trước đó và trả lời câu hỏi cụ thể
2. **Given** follow-up question, **When** response được tạo, **Then** thời gian phản hồi ngắn hơn initial explain (không gửi lại ảnh)
3. **Given** bác sĩ chuyển sang detection mới, **When** giải thích được yêu cầu, **Then** conversation history được reset, không mix context giữa các detection
4. **Given** UNKNOWN intent từ voice (không khớp BO_QUA/XAC_NHAN/KIEM_TRA_LAI), **When** pipeline đang ở trạng thái đã có initial explain, **Then** transcript được route tới follow-up chatbot thay vì bị bỏ qua

---

### User Story 3 — In-Session Response Caching (Priority: P3)

Trong một session, cùng label và vị trí anatomical đã được giải thích → reuse response thay vì gọi API lại. Hữu ích khi cùng loại tổn thương xuất hiện nhiều lần trong một ca nội soi.

**Why this priority**: Tiết kiệm chi phí API, giảm latency cho lần thứ hai trở đi. Ít rủi ro nhất vì là optimization thuần tuý.

**Independent Test**: Trigger explain trên detection A (label X, location Y) → trigger explain trên detection B có cùng label X và location Y → lần hai response xuất hiện tức thì (không có network delay).

**Acceptance Scenarios**:

1. **Given** detection mới có label + location trùng với detection đã giải thích trước đó trong cùng session, **When** giải thích được yêu cầu, **Then** response được trả về từ cache, không gọi API
2. **Given** cached response được trả về, **When** bác sĩ nhìn UI, **Then** response xuất hiện giống hệt response trực tiếp (streamed hoặc instant — cả hai chấp nhận được)
3. **Given** session kết thúc (EOS hoặc disconnect), **When** session mới bắt đầu, **Then** cache từ session cũ không áp dụng

---

### Edge Cases

- Frame_b64 không có (detection từ live stream có độ trễ cao, hoặc encode lỗi) → fallback text-only
- API timeout sau 10 giây → fallback mock response, log warning
- Follow-up question quá dài (>500 chars từ voice transcription lỗi) → truncate và warn
- Conversation history quá lớn (>10 turns) → giữ initial turn + 5 turns gần nhất để tránh context overflow
- Cùng bác sĩ mở 2 tab cùng lúc → mỗi WebSocket session có conversation history độc lập

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: Khi bác sĩ yêu cầu giải thích, hệ thống PHẢI gửi frame_b64 của detection kèm metadata (label, confidence, location) tới LLM để phân tích trực quan.
- **FR-002**: LLM response PHẢI bao gồm Paris classification (0-Is, 0-Ip, 0-IIa, 0-IIb, 0-IIc, 0-IIa+IIc, 0-III) dựa trên đặc điểm hình ảnh quan sát được.
- **FR-003**: LLM response PHẢI có cấu trúc 3 phần: (1) Phân loại Paris với mô tả hình thái, (2) Nhận định nguy cơ lâm sàng, (3) Checklist hành động 3-5 mục.
- **FR-004**: Hệ thống PHẢI hỗ trợ follow-up questions sau initial explain cho cùng một detection mà không gửi lại hình ảnh.
- **FR-005**: Conversation history PHẢI được reset khi chuyển sang detection mới hoặc session kết thúc.
- **FR-006**: Khi không có frame_b64, hệ thống PHẢI fallback sang text-only analysis mà không crash hoặc trả về lỗi cho người dùng.
- **FR-007**: Hệ thống PHẢI cache response theo (label, vị trí anatomical) trong phạm vi session hiện tại.
- **FR-008**: UNKNOWN voice intent khi pipeline đang ở trạng thái post-explain PHẢI được route tới follow-up chatbot thay vì bị bỏ qua.
- **FR-009**: LLM response PHẢI được stream token-by-token tới frontend (không thay đổi so với hiện tại).

### Non-Functional Requirements

- **NFR-001**: Initial explain (vision call) first token < 3 giây.
- **NFR-002**: Follow-up response first token < 2 giây (text-only, nhỏ hơn vision call).
- **NFR-003**: Cache lookup < 5ms.
- **NFR-004**: Conversation history không được vượt quá 10 turns; nếu vượt, tự động trim giữ initial + 5 turns gần nhất.

### Key Entities

- **ConversationTurn**: `{role: "user"|"assistant", content: str|list}` — một lượt hội thoại; content là list khi có image (initial), string khi text-only (follow-up).
- **ConversationSession**: Danh sách `ConversationTurn[]` gắn với một detection cụ thể; được tạo mới khi detection thay đổi.
- **LLMCache**: Dict in-memory `{cache_key: response_text}` scoped per WebSocket session; cache_key = `"{label}:{anatomical_location}"`.

---

## Success Criteria *(mandatory)*

- **SC-001**: 100% response chứa Paris classification khi frame_b64 có sẵn — bác sĩ không cần hỏi thêm về loại tổn thương.
- **SC-002**: Follow-up questions nhận response trong vòng 2 giây (vs 3-5 giây của initial vision call).
- **SC-003**: Chi phí API giảm ≥ 60% so với baseline (gọi vision call cho mọi request) nhờ follow-up text-only + caching.
- **SC-004**: Zero crash khi frame_b64 vắng mặt — fallback hoạt động 100%.
- **SC-005**: Bác sĩ có thể hỏi tối thiểu 3 follow-up questions về cùng một detection mà không mất context.

---

## Assumptions

- `OPENAI_MODEL` env var sẽ được đổi từ `gpt-4o-mini` sang `gpt-4o` để có vision support; fallback mock vẫn hoạt động khi không có API key.
- `detail=low` cho image token đủ chất lượng cho endoscopy frame 640px — endoscopy có đặc điểm visual rõ ràng (màu sắc, hình dạng bờ viền) không cần high-resolution token.
- UNKNOWN intent routing (FR-008) chỉ áp dụng khi `pipelineState === 'PROCESSING_LLM'` hoặc sau khi `LLM_DONE` — không áp dụng khi pipeline đang PLAYING.
- In-session cache là in-memory dict, không persist giữa các session — phù hợp với thiết kế hiện tại (sessions đã là in-memory).
- System prompt mở rộng (~1500 tokens với Paris guide) sẽ được OpenAI auto-cache sau lần gọi đầu tiên trong session.
- Không thay đổi giao diện người dùng — chỉ cải thiện chất lượng và khả năng của phần response text.
