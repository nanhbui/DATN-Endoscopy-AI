# Data Model: Chatbot LLM Enhancement

**Phase 1 output** | Branch: `004-chatbot-llm-enhancement` | Date: 2026-05-01

---

## New Entities

### ConversationHistory (in-memory, per WS session per detection)

```python
# Keyed by video_id in WS handler scope
# Reset on: new detection, ACTION_IGNORE, ACTION_CONFIRM, WS disconnect
conv_history: list[dict]  # OpenAI messages format

# Example after initial explain:
[
  {"role": "user", "content": [
      {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64,...", "detail": "low"}},
      {"type": "text", "text": "Phát hiện: HP-positive gastritis (87%) tại Hang vị. Phân tích tổn thương."}
  ]},
  {"role": "assistant", "content": "**Phân loại Paris:** 0-IIb..."}
]

# After follow-up turn appended:
[
  ...,
  {"role": "user", "content": "Sinh thiết ở đâu?"},
  {"role": "assistant", "content": "Nên lấy 2-4 mảnh tại rìa tổn thương..."}
]
```

**Validation rules**:
- Max 10 turns (index 0 = initial user turn with image, index 1 = initial assistant); trim to `[turn_0, turn_1] + last_4_pairs` nếu vượt
- `role` ∈ `{"user", "assistant"}` — system prompt không lưu vào history (gửi riêng)
- Initial user turn PHẢI có `content` dạng list (image + text); follow-up user turns có `content` dạng string

---

### LLMCache (in-memory, per WS session)

```python
# Keyed by f"{label}:{anatomical_location}"
# Cleared on: WS disconnect / session teardown
llm_cache: dict[str, str]

# Example:
{
  "HP-positive gastritis:Hang vị": "**Phân loại Paris:** 0-IIb...",
  "Gastric cancer:Thân vị": "**Phân loại Paris:** 0-Is..."
}
```

**Cache key format**: `f"{lesion_label}:{location}"` — exact string match, case-sensitive.

**Cache miss**: Proceed with API call. **Cache hit**: Stream cached response with `asyncio.sleep(0.02)` per word.

---

## Extended Entities

### Session (existing, extended)

```python
_sessions[video_id] = {
    "controller": ...,
    "video_path": ...,
    "confirmed_detections": [],
    "library_id": None,
    # NEW:
    "conv_history": [],      # list[dict] — OpenAI messages, reset per detection
    "llm_cache": {},         # dict[str, str] — response cache, cleared on disconnect
}
```

---

## WS Protocol Extensions

### New Client → Server action

```json
{ "action": "ACTION_FOLLOW_UP", "payload": { "text": "string" } }
```

**Trigger**: Frontend sends when doctor asks a follow-up question after `LLM_DONE`.
**Constraint**: Only valid after at least one `ACTION_EXPLAIN` has been processed (conv_history non-empty). If received with empty history → ignored with warning log.

### Existing events (unchanged)

`LLM_CHUNK` and `LLM_DONE` events are reused for both initial explain and follow-up responses — frontend doesn't need to distinguish.

---

## LLM Call Matrix

| Trigger | Model | Message format | Image sent |
|---------|-------|---------------|------------|
| `ACTION_EXPLAIN` (first time, frame_b64 available) | `gpt-4o` | `[system, user(image+text)]` | ✅ detail=low |
| `ACTION_EXPLAIN` (frame_b64 missing) | `gpt-4o` | `[system, user(text only)]` | ❌ fallback |
| `ACTION_EXPLAIN` (cache hit) | — | — (cached) | ❌ |
| `ACTION_FOLLOW_UP` | `gpt-4o-mini` | `[system, *conv_history, user(text)]` | ❌ |
