# WS Protocol Contracts: Chatbot LLM Enhancement

**Phase 1 output** | Branch: `004-chatbot-llm-enhancement` | Date: 2026-05-01

Endpoint: `WS /ws/analysis/{video_id}` — unchanged.

---

## New: Client → Server

### ACTION_FOLLOW_UP

Doctor asks a follow-up question about the current detection after initial LLM explain.

```json
{ "action": "ACTION_FOLLOW_UP", "payload": { "text": "Sinh thiết ở đâu?" } }
```

**Precondition**: `conv_history` non-empty (at least one `ACTION_EXPLAIN` completed).
**Ignored if**: `conv_history` is empty — server logs a warning, no response sent.
**Max text length**: 500 characters (server truncates silently if exceeded).

**Server response**: streams `LLM_CHUNK` + `LLM_DONE` — identical shape to existing explain response.

---

## Existing: Server → Client (unchanged shape, extended semantics)

### LLM_CHUNK

```json
{ "event": "LLM_CHUNK", "data": { "chunk": "string" } }
```

Used for both initial explain and follow-up responses. Frontend accumulates into `llmInsight`.

### LLM_DONE

```json
{ "event": "LLM_DONE", "data": {} }
```

Signals end of stream for both initial and follow-up. No behavioral change on frontend.

---

## Existing actions (unchanged)

| Action | Behavior change |
|--------|----------------|
| `ACTION_EXPLAIN` | Now triggers GPT-4o vision call; initialises `conv_history` |
| `ACTION_IGNORE` | Resets `conv_history` (detection discarded) |
| `ACTION_CONFIRM` | Resets `conv_history` (detection confirmed, move on) |
| `ACTION_RESUME` | No change to `conv_history` |

---

## Frontend TypeScript additions (`frontend/lib/ws-client.ts`)

No new HTTP endpoints. Only WS action type extension:

```typescript
// Extend existing OutboundMessage union:
type OutboundMessage =
  | { action: "ACTION_IGNORE" }
  | { action: "ACTION_EXPLAIN" }
  | { action: "ACTION_RESUME" }
  | { action: "ACTION_CONFIRM" }
  | { action: "ACTION_FOLLOW_UP"; payload: { text: string } };  // NEW
```
