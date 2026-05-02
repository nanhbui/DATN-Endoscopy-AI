# Pre-Implementation Checklist: Video Library & Reuse

**Purpose**: Lightweight author self-review — validate requirement quality across API, data model, and UI before coding begins
**Created**: 2026-05-01
**Feature**: [spec.md](../spec.md) · [plan.md](../plan.md) · [contracts/api.md](../contracts/api.md) · [data-model.md](../data-model.md)
**Focus**: Full-stack (API + data model + UI) · Mandatory gates on dedup correctness and deletion guard

---

## API Requirement Completeness

- [ ] CHK001 - Is the `GET /library` response shape fully specified, including which fields are returned and which are intentionally withheld (e.g., `path`, `sha256_prefix`)? [Completeness, Contracts §GET /library]
- [ ] CHK002 - Are all failure modes for `POST /library/upload` covered with distinct status codes (400 empty, 415 bad format, 507 disk full)? [Completeness, Contracts §POST /library/upload]
- [ ] CHK003 - Is the `POST /sessions/from-library/{library_id}` response shape (`video_id`, `library_id`, `filename`) documented and consistent with how the frontend calls `WS /ws/analysis/{video_id}`? [Consistency, Contracts §POST /sessions/from-library]
- [ ] CHK004 - Are the response shapes for `DELETE /library/{library_id}` defined for all three outcomes: success (200), not found (404), and in-use conflict (409)? [Completeness, Contracts §DELETE]
- [ ] CHK005 - Are the four new client functions (`listLibraryVideos`, `uploadToLibrary`, `deleteLibraryVideo`, `selectLibraryVideo`) and their TypeScript types fully specified in the contracts? [Completeness, Contracts §Frontend API Client]

---

## Data Model Requirement Clarity

- [ ] CHK006 - Is "exact same file" (FR-004) defined with a specific, testable dedup criterion (e.g., SHA-256 prefix of first 4 MB + file size), rather than left as an ambiguous phrase? [Clarity, Spec §FR-004, Data Model §Decision 2]
- [ ] CHK007 - Is the "corrupted" status listed in Key Entities (`status: available / in-use / corrupted`) reconciled with the data model, which derives status at runtime and stores no status field? [Conflict, Spec §Key Entities, Data Model §Session]
- [ ] CHK008 - Is the atomicity requirement for index writes documented (temp-file rename), and is it specified what happens on a mid-write crash? [Edge Case, Data Model §Index File Operations]
- [ ] CHK009 - Is the dedup secondary check (filename + size on prefix hash collision) specified in the requirements, not only in research notes? [Clarity, Research §Decision 2, Gap]

---

## **⛔ MANDATORY GATE — Dedup Correctness**

- [x] CHK010 - Is "same file uploaded again" operationally defined so that two different videos with the same filename are NOT falsely deduplicated? [Ambiguity, Spec §FR-004] — **RESOLVED**: FR-004 now defines dedup as SHA-256(first 4 MB) + size_bytes; filename has no role in dedup.
- [x] CHK011 - Is there a requirement specifying what the system does when a duplicate is detected — specifically, does it silently return the existing entry, or must it notify the user? [Clarity, Contracts §POST /library/upload `duplicate: true`] — **RESOLVED**: FR-004 now requires `duplicate: true` in response AND a visible UI banner ("Video này đã có trong thư viện"); silent reuse is explicitly forbidden.
- [x] CHK012 - Is SC-001 ("100% of repeat uses served from library") consistent with the prefix-hash dedup strategy, which may miss identical files whose first 4 MB differ? [Consistency, Spec §SC-001, Research §Decision 2] — **RESOLVED**: SC-001 now scoped to prefix-hash matches; the known limitation (files with differing first 4 MB are not deduplicated) is explicitly documented.

---

## **⛔ MANDATORY GATE — Active-Session Deletion Guard**

- [x] CHK013 - Is the active-use detection mechanism specified in requirements (not just in design notes) — specifically, how "in-use" is determined when multiple sessions could reference the same library video? [Clarity, Spec §FR-007, Data Model §Session] — **RESOLVED**: FR-007 now specifies that "in-use" means any active WS session with matching `library_id`; multiple concurrent sessions are accounted for.
- [x] CHK014 - Is the error message shown to the user when deletion is blocked (FR-007 / HTTP 409) specified with enough detail for implementation? [Completeness, Spec §FR-007, Contracts §DELETE] — **RESOLVED**: FR-007 specifies both the HTTP 409 and the exact Vietnamese message ("Video đang được sử dụng, không thể xóa"); contracts/api.md documents the 409 response shape.
- [x] CHK015 - Are concurrent deletion race conditions addressed — specifically, what happens if two users (or two browser tabs) attempt to delete the same library entry simultaneously? [Edge Case, Spec §Edge Cases] — **RESOLVED**: Spec Assumptions now documents that the single-process asyncio event loop serializes concurrent requests; second DELETE gets 404 (already removed). Invalidated only if multi-worker deployment is used.

---

## UI/UX Requirement Clarity

- [x] CHK016 - Does FR-002 ("show name, upload date, file size") match US1 Scenario 1, which also lists "duration" as metadata to identify videos — is "duration" a requirement or optional display? [Conflict, Spec §FR-002 vs §US1] — **RESOLVED**: US1 Scenario 1 updated to "file size" (duration removed); Key Entities updated to exclude duration from LibraryEntry; duration explicitly deferred (not in data model).
- [ ] CHK017 - Is "confirmation required before permanent removal" (FR-006) specified with enough detail — e.g., is it a dialog, an inline confirm button, or a typed confirmation? [Clarity, Spec §FR-006]
- [ ] CHK018 - Is the UI empty-state requirement (FR-008) specific enough: does it define what text or action is shown, or only that "an empty state exists"? [Clarity, Spec §FR-008]
- [ ] CHK019 - Are requirements defined for how the library handles 50+ videos (SC-005 implies 2-second load regardless of count) — is pagination, virtualized scrolling, or search required, or out of scope? [Coverage, Spec §Edge Cases, SC-005]
- [ ] CHK020 - Is the "third tab" UI placement (from research) reflected back in the spec or plan as a requirement, or is UI layout still underspecified? [Gap, Research §Decision 6]

---

## Edge Case Coverage

- [ ] CHK021 - Is the requirement defined for what the UI shows when a library entry exists in the index but its file is missing from disk (corrupted/deleted externally)? [Edge Case, Spec §Edge Cases, Gap]
- [ ] CHK022 - Is the disk-full scenario (FR-010) specified for both the upload response (HTTP 507) and the server-side cleanup (is the partial file removed on failure)? [Completeness, Spec §FR-010, Contracts §POST /library/upload]
- [ ] CHK023 - Is the maximum supported library size (video count or total bytes) documented as in-scope or explicitly deferred? [Scope, Spec §Assumptions]

---

## Dependencies & Assumptions

- [ ] CHK024 - Is the shared-library assumption (all users share one pool) documented clearly enough that a future per-user isolation feature would require a spec amendment, not just a code change? [Assumption, Spec §Assumptions]
- [x] CHK025 - Is it documented that the existing `POST /upload` ephemeral flow and the new `POST /library/upload` flow are independent — specifically, that ephemeral uploads are still deleted at session teardown and NOT added to the library? [Clarity, Research §Decision 4, Gap] — **RESOLVED**: FR-011 added explicitly stating ephemeral path is unchanged, files are deleted at teardown, and the two flows must not be conflated.

---

## Notes

- Items marked `⛔ MANDATORY GATE` must be resolved before implementation begins.
- Items marked `[Gap]` indicate requirements missing from the spec that should be added or explicitly deferred.
- Items marked `[Conflict]` indicate inconsistencies between two sections that must be reconciled.
- Check items off as completed: `[x]`
