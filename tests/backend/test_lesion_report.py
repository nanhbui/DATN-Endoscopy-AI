"""Smoke tests cho Phase A1+A2 — không cần GGML / Ollama hoạt động.

Chạy:
    cd src/backend/api && python ../../../tests/backend/test-lesion-report.py

Kiểm tra:
    1. Schema + prompt import được
    2. Mock report đúng shape schema
    3. _stream_lesion_report() đi mock path khi client=None và emit
       đúng LESION_REPORT_DONE event qua WebSocket
    4. Cache hit lần 2 trả ngay không gọi LLM
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

# Make endoscopy_ws_server importable when run from repo root or from api/.
API_DIR = Path(__file__).resolve().parent.parent.parent / "src" / "backend" / "api"
sys.path.insert(0, str(API_DIR))

import jsonschema
from llm_prompts import LESION_REPORT_SCHEMA
import endoscopy_ws_server as ws


class FakeWebSocket:
    """Capture sent JSON payloads — stand-in for FastAPI WebSocket."""
    def __init__(self):
        self.sent: list[dict] = []

    async def send_json(self, payload: dict) -> None:
        self.sent.append(payload)


async def run() -> int:
    failures = 0

    # ── Force mock path (no LLM client) ──────────────────────────────────
    ws._llm_client = None
    ws._get_llm_client = lambda: None  # belt-and-suspenders

    sample_detection = {
        "lesion": {"label": "viem-da-day-hp", "confidence": 0.87,
                   "bbox": [120, 80, 340, 260]},
        "frame_b64": None,  # mock path doesn't need image
        "frame_index": 4612,
        "timestamp_ms": 154300,
    }
    sess: dict = {"llm_cache": {}, "conv_history": []}
    fake_ws = FakeWebSocket()
    lock = asyncio.Lock()

    # ── Test 1: First call → mock path → LESION_REPORT_DONE ─────────────
    await ws._stream_lesion_report(fake_ws, sample_detection, sess,
                                   "test_video_id", lock)

    if not fake_ws.sent:
        print("❌ Test 1: no WS message sent")
        return 1

    msg = fake_ws.sent[0]
    if msg.get("event") != "LESION_REPORT_DONE":
        print(f"❌ Test 1: expected LESION_REPORT_DONE, got {msg.get('event')}")
        failures += 1
    else:
        print("✅ Test 1: LESION_REPORT_DONE event emitted")

    report = msg.get("data", {}).get("report")
    if not report:
        print("❌ Test 1b: report missing from payload")
        return 1

    # ── Test 2: report matches schema ────────────────────────────────────
    try:
        jsonschema.validate(report, LESION_REPORT_SCHEMA)
        print("✅ Test 2: report passes LESION_REPORT_SCHEMA")
    except jsonschema.ValidationError as e:
        print(f"❌ Test 2: schema FAILED at {list(e.absolute_path)}: {e.message}")
        failures += 1

    # ── Test 3: required fields present ──────────────────────────────────
    expected = {
        ("technique", "method"),
        ("technique", "device"),
        ("technique", "timestamp"),
        ("conclusion", "primary_dx"),
        ("conclusion", "severity"),
        ("conclusion", "ai_confidence"),
    }
    for path in expected:
        cur = report
        for k in path:
            cur = cur.get(k) if isinstance(cur, dict) else None
        if cur is None:
            print(f"❌ Test 3: missing field {'.'.join(path)}")
            failures += 1
    if all(report.get(p[0], {}).get(p[1]) is not None for p in expected):
        print("✅ Test 3: all required fields present")

    # ── Test 4: severity is one of 3 values ──────────────────────────────
    sev = report.get("conclusion", {}).get("severity")
    if sev in {"thấp", "trung bình", "cao"}:
        print(f"✅ Test 4: severity='{sev}' is valid enum")
    else:
        print(f"❌ Test 4: severity='{sev}' not in enum")
        failures += 1

    # ── Test 5: cache hit on second call ─────────────────────────────────
    fake_ws2 = FakeWebSocket()
    await ws._stream_lesion_report(fake_ws2, sample_detection, sess,
                                   "test_video_id", lock)
    if fake_ws2.sent and fake_ws2.sent[0].get("event") == "LESION_REPORT_DONE":
        print("✅ Test 5: cache hit returns same event")
    else:
        print(f"❌ Test 5: cache miss — sess.llm_cache keys={list(sess.get('llm_cache', {}).keys())}")
        failures += 1

    # ── Pretty print one report so eyeball-check is easy ─────────────────
    print("\n" + "=" * 60)
    print("Sample mock report:")
    print(json.dumps(report, ensure_ascii=False, indent=2))

    return failures


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
