from __future__ import annotations

import os
import sys
from pathlib import Path

from loguru import logger

# ── Directories ───────────────────────────────────────────────────────────────
_HERE = Path(__file__).resolve().parent
_LOG_DIR = Path(os.getenv("LOG_DIR", str(_HERE / "logs")))
_LOG_DIR.mkdir(parents=True, exist_ok=True)

_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()

# ── Remove default handler ────────────────────────────────────────────────────
logger.remove()

# ── Console handler (colourised) ─────────────────────────────────────────────
logger.add(
    sys.stderr,
    level=_LEVEL,
    colorize=True,
    format=(
        "<green>{time:HH:mm:ss}</green> | "
        "<level>{level: <8}</level> | "
        "<cyan>{name}</cyan>:<cyan>{line}</cyan> — "
        "<level>{message}</level>"
    ),
)

# ── File handler (JSON, rotating) ────────────────────────────────────────────
logger.add(
    _LOG_DIR / "server.log",
    level="INFO",
    rotation="10 MB",
    retention="7 days",
    compression="gz",
    serialize=True,          # outputs JSON
    backtrace=True,
    diagnose=False,          # disable in prod to avoid leaking locals
)

__all__ = ["logger"]
