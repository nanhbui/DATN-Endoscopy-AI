"""frame_skipper_api.py – FastAPI router exposing the Smart Ignore FAISS utilities.

Endpoints
---------
* ``POST /frame_skipper/add`` – add a new negative‑pattern embedding.
  Expected JSON payload:
  ```json
  {
    "embedding": [0.12, 0.34, ...],
    "metadata": {"reason": "bột trắng", "frame_idx": 123}
  }
  ```
* ``GET /frame_skipper/check`` – query whether an embedding should be ignored.
  Query parameter ``embedding`` is a comma‑separated list of floats.
  Returns ``{"ignored": true}`` if similarity exceeds the configured threshold.
* ``GET /frame_skipper/list`` – list stored metadata for debugging.
* ``POST /frame_skipper/clear`` – clear all stored patterns (dev utility).

The router is imported and included in ``api_server.py`` (or can be mounted
separately).  It uses the ``FrameSkipper`` class defined in
``src/frame_skipping/frame_skipper.py`` which persists its index on disk.
"""

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Optional

# Ensure the project root is on sys.path (mirrors what api_server does).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))  # project root

from src.frame_skipping.frame_skipper import FrameSkipper

router = APIRouter()

# Singleton skipper – loaded once at import time.
_skipper = FrameSkipper()


class AddPatternRequest(BaseModel):
    embedding: List[float] = Field(..., description="Embedding vector (list of floats)")
    metadata: Optional[Dict[str, Any]] = Field(None, description="Optional metadata for the pattern")


@router.post("/frame_skipper/add", status_code=status.HTTP_201_CREATED)
def add_pattern(req: AddPatternRequest):
    """Add a new negative pattern to the FAISS index.

    The embedding is converted to a NumPy ``float32`` array before insertion.
    """
    import numpy as np
    try:
        vec = np.array(req.embedding, dtype="float32")
        _skipper.add(vec, req.metadata)
        return {"success": True, "message": "Pattern added"}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@router.get("/frame_skipper/check")
def check_pattern(embedding: str = Query(..., description="Comma‑separated list of floats")):
    """Return whether the provided embedding matches a stored negative pattern.

    ``embedding`` query param example: ``?embedding=0.1,0.2,0.3,...``
    """
    import numpy as np
    try:
        vec = np.fromstring(embedding, sep=",", dtype="float32")
        ignored = _skipper.is_ignored(vec)
        return {"ignored": ignored}
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.get("/frame_skipper/list")
def list_patterns():
    """Return stored metadata for all negative patterns (debug endpoint)."""
    return {"patterns": _skipper.list_patterns()}


@router.post("/frame_skipper/clear")
def clear_patterns():
    """Clear all stored patterns – useful during development/testing."""
    _skipper.clear()
    return {"success": True, "message": "All patterns cleared"}
