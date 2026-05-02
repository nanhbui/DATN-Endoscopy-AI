# Tasks: Chatbot LLM Enhancement

**Input**: Design documents from `specs/004-chatbot-llm-enhancement/`
**Prerequisites**: [plan.md](plan.md) · [spec.md](spec.md) · [research.md](research.md) · [data-model.md](data-model.md) · [contracts/ws-protocol.md](contracts/ws-protocol.md)

## Format: `[ID] [P?] [Story?] Description`

- **[P]**: Can run in parallel (different files, no blocking dependencies)
- **[Story]**: User story label — US1 / US2 / US3
- Exact file paths in every task description

---

## Phase 1: Setup

**Purpose**: Replace single LLM_MODEL constant with two model constants and add missing import.

- [x] T001 Replace `LLM_MODEL` constant with `LLM_MODEL_VISION = os.getenv("OPENAI_MODEL_VISION", "gpt-4o")` and `LLM_MODEL_FOLLOWUP = os.getenv("OPENAI_MODEL_FOLLOWUP", "gpt-4o-mini")` in `src/backend/api/endoscopy_ws_server.py`; remove any remaining reference to the old `LLM_MODEL` variable
- [x] T002 Add `import time` to `src/backend/api/endoscopy_ws_server.py` (required for latency logging in LLM functions)

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: System prompt expansion and session schema extension — both block all user story phases.

⚠️ **CRITICAL**: All user story phases depend on this phase.

- [x] T003 Replace `LLM_SYSTEM_PROMPT` in `src/backend/api/endoscopy_ws_server.py` with the full Paris classification guide (~1500 tokens) per `plan.md §Phase 1b`. The new prompt must include: Paris type definitions (0-Ip, 0-Is, 0-IIa, 0-IIb, 0-IIc, 0-IIa+IIc, 0-III), H. pylori classification guide, lành/ác tính differentiation criteria, and mandatory 3-section response format (Phân loại Paris / Nhận định lâm sàng / Checklist hành động)
- [x] T004 Add `"conv_history": []` and `"llm_cache": {}` fields to **all three** `_sessions[video_id] = {...}` dict initializations in `src/backend/api/endoscopy_ws_server.py` (upload session at ~line 244, stream session at ~line 263, library session at ~line 346) — per `data-model.md §Session`
- [x] T005 [P] Extend `OutboundMessage` type union in `frontend/lib/ws-client.ts` by adding `| { action: "ACTION_FOLLOW_UP"; payload: { text: string } }` — per `contracts/ws-protocol.md §Frontend TypeScript additions`

**Checkpoint**: `_sessions` dicts have `conv_history` and `llm_cache` fields; system prompt has Paris guide; `ACTION_FOLLOW_UP` is a valid TypeScript type.

---

## Phase 3: User Story 1 — Visual Analysis with Paris Classification (Priority: P1) 🎯 MVP

**Goal**: Initial explain sends frame_b64 + metadata to GPT-4o vision; response includes Paris classification.

**Independent Test**: Trigger explain on a detection that has `frame_b64` → LLM response must contain "Phân loại Paris:" with a specific type (e.g., "0-IIb") AND "Checklist hành động:" with at least 2 items.

- [x] T006 [US1] Rewrite `_stream_llm` function signature to `async def _stream_llm(websocket, detection, sess)` in `src/backend/api/endoscopy_ws_server.py`: (1) check `sess["llm_cache"]` cache hit → skip API call; (2) if no API key → call `_mock_llm_response`; (3) build `user_content` as list with `image_url (detail=low)` + text if `frame_b64` present, else string fallback; (4) call `client.chat.completions.create(model=LLM_MODEL_VISION, messages=[system, user_content], stream=True, max_tokens=700)`; (5) accumulate `full_response`; (6) on success: write `sess["conv_history"]` = `[initial_user_turn, assistant_turn]` and write `sess["llm_cache"][cache_key] = full_response` — per `plan.md §Phase 1d` and `data-model.md §LLM Call Matrix`
- [x] T007 [US1] Update `_mock_llm_response` function in `src/backend/api/endoscopy_ws_server.py` to return text matching the new 3-section format: starts with `**Phân loại Paris:** 0-IIb — ...`, then `**Nhận định lâm sàng:** ...`, then `**Checklist hành động:**` with 3 checkbox items — so mock and real responses are structurally identical
- [x] T008 [US1] Update `ACTION_EXPLAIN` branch in `_handle_actions()` in `src/backend/api/endoscopy_ws_server.py`: resolve `sess = _sessions.get(video_id, {})` at the top of `ws_analysis` handler (before task creation), reset `sess["conv_history"] = []` before calling `_stream_llm`, and pass `sess` as third argument to `_stream_llm` — per `plan.md §Phase 1e`

**Checkpoint**: US1 functional. Explain sends image + text to GPT-4o; response has Paris classification; mock response has same structure.

---

## Phase 4: User Story 2 — Follow-up Conversation (Priority: P2)

**Goal**: After initial explain, doctor can ask follow-up questions via voice (UNKNOWN intent) or text; response uses GPT-4o-mini with conversation context, no image re-sent.

**Independent Test**: After initial explain completes, send `ACTION_FOLLOW_UP` with text "Sinh thiết ở đâu?" → server streams a response in < 2 s that references the detection context without re-analyzing the image.

- [x] T009 [US2] Add new `async def _stream_follow_up(websocket, text, sess)` function to `src/backend/api/endoscopy_ws_server.py`: (1) return immediately if `sess["conv_history"]` is empty with `logger.warning`; (2) trim history to `history[:2] + history[-8:]` if `len(history) > 10`; (3) build messages = `[system, *history, {"role":"user","content":text[:500]}]`; (4) call `gpt-4o-mini` with `stream=True, max_tokens=350`; (5) append user + assistant turns to `sess["conv_history"]` after stream — per `plan.md §Phase 1d (_stream_follow_up)` and `data-model.md §ConversationHistory`
- [x] T010 [US2] Add `ACTION_FOLLOW_UP` branch and reset-on-resolve to `_handle_actions()` in `src/backend/api/endoscopy_ws_server.py`: (1) `elif action == "ACTION_FOLLOW_UP": text = msg.get("payload",{}).get("text",""); asyncio.ensure_future(_stream_follow_up(websocket, text, sess))` if text non-empty; (2) add `sess["conv_history"] = []` inside both `ACTION_IGNORE` and `ACTION_CONFIRM` branches — per `plan.md §Phase 1e` and `contracts/ws-protocol.md §Existing actions`
- [x] T011 [P] [US2] Add `followUpChat: (text: string) => void` to `AnalysisContextType` interface and implement as `useCallback` that calls `wsRef.current.send({ action: "ACTION_FOLLOW_UP", payload: { text } })` and resets `llmInsightRef.current = ""; setLlmInsight("")` in `frontend/context/AnalysisContext.tsx`; expose in context value and `useMemo` deps array — per `plan.md §Phase 2b`
- [x] T012 [US2] In `onIntent` callback in `frontend/app/workspace/page.tsx`: add `else if (intent === 'UNKNOWN' && llmInsightRef.current) { followUpChat(transcript); }` branch after the existing `XAC_NHAN` branch; import `followUpChat` from `useAnalysis()`; ensure `llmInsightRef` is accessible in the callback scope — per `plan.md §Phase 2c`

**Checkpoint**: US2 functional. UNKNOWN voice intent after explain routes to follow-up; follow-up uses conversation history; context resets on new detection.

---

## Phase 5: User Story 3 — In-Session Response Cache (Priority: P3)

**Goal**: Same label+location detection in same session returns cached response instantly without API call.

**Independent Test**: Trigger explain on detection A (label X, location Y) → trigger explain on detection B with same label X and location Y → second response appears with no network latency (instant word stream).

- [x] T013 [US3] The cache check and write are already included in T006 (`_stream_llm` rewrite). Verify that: (1) `cache_key = f"{label}:{location}"` is used; (2) cache hit check is the **first** branch (before no-API-key check); (3) cached response streams via `asyncio.sleep(0.02)` per word; (4) cache write occurs only after successful API stream (not on error). If T006 was implemented without cache logic, add both the cache hit check and cache write to `_stream_llm` in `src/backend/api/endoscopy_ws_server.py` — per `data-model.md §LLMCache`

**Checkpoint**: US3 functional. Same label+location in same session → instant cached response; different detection → fresh API call.

---

## Final Phase: Polish & Cross-Cutting

- [x] T014 [P] Verify loguru logging in `src/backend/api/endoscopy_ws_server.py` for all LLM code paths: (1) initial explain: `logger.info("LLM initial explain: model={} latency={:.2f}s tokens_out=~{}", ...)` after stream; (2) follow-up: `logger.info("LLM follow-up: model={} latency={:.2f}s", ...)`; (3) cache hit: `logger.info("LLM cache hit: {}", cache_key)`; (4) fallback (no frame_b64): `logger.warning("LLM fallback text-only: frame_b64 missing for {}", label)` — per constitution §Observability
- [x] T015 Run `npx tsc --noEmit` in `frontend/` directory and fix all TypeScript errors introduced by T005, T011, T012 — per constitution §Development Workflow

---

## Dependencies & Execution Order

### Phase Dependencies

- **Phase 1 (Setup)**: No dependencies — start immediately
- **Phase 2 (Foundational)**: Depends on Phase 1 — **BLOCKS all user story phases**
- **Phase 3 (US1)**: Depends on Phase 2
- **Phase 4 (US2)**: Depends on Phase 2 + Phase 3 (needs `conv_history` populated by US1)
- **Phase 5 (US3)**: Depends on Phase 3 (cache logic inside `_stream_llm`)
- **Final Phase**: Depends on all phases complete

### Parallel Opportunities

- T005 (ws-client.ts) runs in parallel with T003, T004 (different files)
- T011 (AnalysisContext.tsx) runs in parallel with T009, T010 (different files; depends on T005)
- T012 (workspace/page.tsx) runs in parallel with T014 (different files; depends on T011)
- T014 and T015 are fully independent (different tools)

### Backend Sequential Order (same file — must be sequential)

```
T001 → T002 → T003 → T004 → T006 → T007 → T008 → T009 → T010 → T013 → T014
```

---

## Implementation Strategy

### MVP Scope (US1 only — 8 tasks)

1. Phase 1: T001, T002
2. Phase 2: T003, T004, T005
3. Phase 3: T006, T007, T008
4. **Validate**: Explain sends image to GPT-4o; response has Paris classification

### Incremental Delivery

- After MVP: add US2 (T009–T012) → follow-up conversation works
- After US2: validate US3 (T013) → confirm cache already wired in T006
- Final: T014, T015 → observability + type safety

---

## Notes

- T013 is a **verification task** — if T006 was implemented correctly per plan.md, the cache is already there. If not, T013 is the remediation.
- All backend changes are in a single file (`endoscopy_ws_server.py`) — no new Python files created.
- All frontend changes are in existing files — no new TypeScript files created.
- No test files generated (not requested in spec).
