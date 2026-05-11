"""SQLite persistence for lesion reports (Phase A — decision 5B).

Why SQLite (not Postgres / Redis):
  - Single-server deployment, low write rate (~1 report / 5s)
  - Zero ops overhead — file-based, no daemon
  - Sufficient for thesis / pilot stage; swap to Postgres later if multi-tenant

Why sync sqlite3 (not aiosqlite) here:
  - One INSERT per ~5 seconds — blocking the event loop for ~1ms is invisible
  - Avoids adding aiosqlite dep just for save_lesion_report
  - If write contention ever shows up, switch to asyncio.to_thread()

Schema in this module is INTENTIONALLY minimal (lesion_reports only).
Sessions / detections / qa_messages tables are deferred to Phase B —
no point creating empty tables for Phase A; YAGNI applies.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Optional

from loguru import logger

# DB lives next to other persistent data (uploads, library) — keeps the
# server self-contained for backup/move purposes.
_DB_PATH = Path(__file__).parent / "data" / "endoscopy.db"

_LESION_REPORTS_DDL = """
CREATE TABLE IF NOT EXISTS lesion_reports (
    session_id    TEXT NOT NULL,
    frame_index   INTEGER NOT NULL,
    report_json   TEXT NOT NULL,
    generated_at  INTEGER NOT NULL,   -- unix epoch ms
    model         TEXT,                -- e.g. 'qwen2.5vl:7b' | 'gpt-4o'
    label         TEXT,                -- detected lesion label (denormalized for query convenience)
    severity      TEXT,                -- thấp / trung bình / cao (denormalized for filtering)
    PRIMARY KEY (session_id, frame_index)
)
"""

_INDEX_DDL = "CREATE INDEX IF NOT EXISTS idx_lesion_session ON lesion_reports(session_id)"


def _connect() -> sqlite3.Connection:
    """Open a fresh connection. Caller must close. Each call sets pragmas
    that matter for our access pattern (WAL = better concurrent reads)."""
    _DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(_DB_PATH, timeout=5.0)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db() -> None:
    """Create the lesion_reports table if missing. Safe to call repeatedly."""
    try:
        with _connect() as conn:
            conn.execute(_LESION_REPORTS_DDL)
            conn.execute(_INDEX_DDL)
        logger.info("SQLite DB ready at {}", _DB_PATH)
    except sqlite3.Error as e:
        logger.error("init_db failed: {}", e)


def save_lesion_report(session_id: str, frame_index: int, report: dict,
                       model: str, generated_at_ms: int) -> bool:
    """Persist one structured lesion report. Returns True on success.

    Uses INSERT OR REPLACE on the (session_id, frame_index) primary key —
    if the same detection is re-explained, the latest report wins. That's
    the right behavior since 'Giải thích lại' should overwrite, not append.
    """
    try:
        label = report.get("conclusion", {}).get("primary_dx", "")[:200]
        severity = report.get("conclusion", {}).get("severity", "")
        with _connect() as conn:
            conn.execute(
                """INSERT OR REPLACE INTO lesion_reports
                   (session_id, frame_index, report_json, generated_at, model, label, severity)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (session_id, frame_index, json.dumps(report, ensure_ascii=False),
                 generated_at_ms, model, label, severity),
            )
        return True
    except sqlite3.Error as e:
        logger.error("save_lesion_report failed (session={}, frame={}): {}",
                     session_id, frame_index, e)
        return False


def get_lesion_reports_for_session(session_id: str) -> list[dict]:
    """Fetch all reports for a session, ordered by frame_index. Returns list
    of dicts with keys: frame_index, report (parsed JSON), generated_at, model.

    Used by Phase B session-summary chatbot — reads back all per-detection
    reports to feed into the summary prompt."""
    try:
        with _connect() as conn:
            cur = conn.execute(
                """SELECT frame_index, report_json, generated_at, model, label, severity
                   FROM lesion_reports WHERE session_id = ?
                   ORDER BY frame_index ASC""",
                (session_id,),
            )
            rows = cur.fetchall()
        return [
            {"frame_index": r[0], "report": json.loads(r[1]),
             "generated_at": r[2], "model": r[3],
             "label": r[4], "severity": r[5]}
            for r in rows
        ]
    except sqlite3.Error as e:
        logger.error("get_lesion_reports_for_session failed: {}", e)
        return []


def db_path() -> Path:
    """Exposed for tests / health checks that need the on-disk location."""
    return _DB_PATH
