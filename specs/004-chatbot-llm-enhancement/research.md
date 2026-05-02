# Research: Chatbot LLM Enhancement

**Phase 0 output** | Branch: `004-chatbot-llm-enhancement` | Date: 2026-05-01

---

## Decision 1: Vision model — GPT-4o với detail=low

**Decision**: Dùng `gpt-4o` cho initial explain call với image `detail="low"`.

**Rationale**: GPT-4o là model duy nhất trong OpenAI API có vision support + medical reasoning mạnh + Vietnamese. `detail=low` cho image tokens cố định 85 tokens (vs ~765 với `auto`) — endoscopy frame 640px có đặc điểm visual rõ ràng (màu sắc tổn thương, hình dạng bờ viền) không cần tile resolution cao.

**OpenAI vision message format** (exact):
```python
messages=[
    {"role": "system", "content": LLM_SYSTEM_PROMPT},
    {"role": "user", "content": [
        {
            "type": "image_url",
            "image_url": {
                "url": f"data:image/jpeg;base64,{frame_b64}",
                "detail": "low"
            }
        },
        {"type": "text", "text": user_text}
    ]}
]
```

**Cost per initial call** (May 2026, gpt-4o):
- System prompt 1500 tokens × $2.50/1M = $0.00375
- Image 85 tokens × $2.50/1M = $0.000213
- User text ~100 tokens × $2.50/1M = $0.00025
- Output 700 tokens × $10/1M = $0.007
- **Total per call: ~$0.011** (với caching 50% off system prompt sau lần đầu: ~$0.007)

**Alternatives considered**:
- GPT-4o-mini: rẻ hơn ~17x nhưng medical reasoning yếu, Paris classification hay bị generic
- Claude Sonnet 4.6: competitive accuracy, caching tốt hơn (90% discount), nhưng thêm API dependency

---

## Decision 2: Follow-up model — GPT-4o-mini text-only với conversation history

**Decision**: Follow-up questions dùng `gpt-4o-mini` text-only, giữ full conversation history (system + initial turn + prior follow-ups).

**Rationale**: GPT-4o retains image context throughout a conversation — sau initial call có image, các follow-up messages chỉ cần text. GPT-4o-mini đủ mạnh cho Q&A text khi context đã có sẵn từ GPT-4o analysis. Chi phí follow-up: ~$0.0003/call.

**Conversation history structure**:
```python
# Initial: messages = [system, user(image+text), assistant(response)]
# Follow-up 1: messages = [system, user(image+text), assistant(r1), user(text), assistant(r2)]
# Follow-up N: trim nếu > 10 turns (giữ [system, user_initial, assistant_initial, 4 turns gần nhất])
```

**Key insight**: Image chỉ gửi trong turn đầu tiên. GPT-4o-mini nhận conversation history đã có GPT-4o analysis text — nó không cần image để answer follow-up vì analysis đã được encode thành text bởi GPT-4o.

**Cost per follow-up call** (gpt-4o-mini):
- Context ~2000 tokens × $0.15/1M = $0.0003
- Output ~300 tokens × $0.60/1M = $0.00018
- **Total per follow-up: ~$0.0005**

---

## Decision 3: Conversation history storage — in-memory per WS session per detection

**Decision**: Lưu conversation history trong dict `_conv_history` keyed by `video_id` trong `_stream_llm` closure scope (truyền qua reference trong WS handler).

**Rationale**: Sessions đã là in-memory. Conversation history chỉ cần tồn tại trong thời gian một detection được analyze (reset khi detection thay đổi hoặc session kết thúc). Dict simple, không cần persistence.

**Storage**: `conv_history: list[dict]` — OpenAI messages format, khởi tạo khi `ACTION_EXPLAIN` đầu tiên, reset khi detection mới.

---

## Decision 4: In-session response cache

**Decision**: Dict `_llm_cache: dict[str, str]` trong WS session scope, key = `f"{label}:{location}"`.

**Rationale**: Cùng loại tổn thương ở cùng vị trí trong một ca nội soi → response gần như identical. Cache trong session (không cross-session) tránh stale data.

**Streaming cache**: Cached response được "streamed" bằng cách split theo word với `asyncio.sleep(0.02)` — giữ UI behavior nhất quán.

---

## Decision 5: System prompt mở rộng với Paris guide

**Decision**: Expand system prompt từ ~50 tokens lên ~1500 tokens với Paris classification guide đầy đủ.

**Rationale**: >1024 tokens để OpenAI auto-cache (50% discount sau lần gọi đầu). Paris guide trong system prompt đảm bảo FR-013 compliance và cải thiện accuracy classification.

**Cache TTL**: 5 phút mặc định. Trong một ca nội soi bác sĩ thường trigger nhiều explain trong vòng 5 phút → cache hit rate cao.

---

## Decision 6: ACTION_FOLLOW_UP — WS action mới

**Decision**: Thêm action `ACTION_FOLLOW_UP { text: string }` vào WS protocol.

**Rationale**: Cần phân biệt "initial explain" (trigger vision call) và "follow-up question" (trigger text-only call với history). Frontend gửi action này khi UNKNOWN intent xuất hiện sau `LLM_DONE`, hoặc khi bác sĩ submit follow-up input.

**Frontend routing**: Trong `onIntent` callback ở workspace page: khi `intent === 'UNKNOWN'` VÀ `llmInsight` đã có → gọi `followUpChat(transcript)` thay vì ignore.

---

## Decision 7: frame_b64 trong detection dict

**Finding**: `ctrl._pending` đã chứa `frame_b64` (từ `pipeline_controller.py` line 472). Khi `ACTION_EXPLAIN` được nhận, `pending = ctrl._pending` có field `frame_b64`. Không cần thay đổi pipeline.

**_stream_llm nhận**: `detection.get("frame_b64")` — có thể None nếu encode lỗi.
