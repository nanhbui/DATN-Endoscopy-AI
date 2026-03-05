"""
Application Settings - Centralized configuration
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load environment variables
load_dotenv(Path(__file__).parent / ".env")

# =============================================================================
# PATHS
# =============================================================================

ROOT_DIR = Path(__file__).parent.parent
SRC_DIR = ROOT_DIR / "src"
MODELS_DIR = ROOT_DIR / "models"
DATA_DIR = ROOT_DIR / "data"
OUTPUTS_DIR = ROOT_DIR / "outputs"
CONFIGS_DIR = ROOT_DIR / "configs"

# =============================================================================
# MODEL SETTINGS
# =============================================================================

YOLO_MODEL_PATH = MODELS_DIR / "yolov8n-seg.pt"
YOLO_TORCHSCRIPT_PATH = MODELS_DIR / "yolov8n-seg.torchscript"

# Detection settings
CONFIDENCE_THRESHOLD = float(os.getenv("CONFIDENCE_THRESHOLD", "0.25"))
IOU_THRESHOLD = float(os.getenv("IOU_THRESHOLD", "0.45"))

# =============================================================================
# CAMERA / VIDEO SETTINGS
# =============================================================================

CAMERA_ID = int(os.getenv("CAMERA_ID", "0"))
CAMERA_WIDTH = int(os.getenv("CAMERA_WIDTH", "1280"))
CAMERA_HEIGHT = int(os.getenv("CAMERA_HEIGHT", "720"))
CAMERA_FPS = int(os.getenv("CAMERA_FPS", "30"))

# =============================================================================
# DATABASE SETTINGS
# =============================================================================

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "endoscopy_ai")

# ChromaDB
CHROMADB_PATH = DATA_DIR / "chromadb"

# =============================================================================
# API SETTINGS
# =============================================================================

API_HOST = os.getenv("API_HOST", "0.0.0.0")
API_PORT = int(os.getenv("API_PORT", "8000"))

# OpenAI
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_EMBEDDING_MODEL = os.getenv("OPENAI_EMBEDDING_MODEL", "text-embedding-3-small")

# LangSmith
LANGCHAIN_API_KEY = os.getenv("LANGCHAIN_API_KEY", "")
LANGCHAIN_TRACING_V2 = os.getenv("LANGCHAIN_TRACING_V2", "false").lower() == "true"
LANGCHAIN_PROJECT = os.getenv("LANGCHAIN_PROJECT", "endoscopy-ai")

# =============================================================================
# MEDICAL SETTINGS
# =============================================================================

# Lesion types for detection
LESION_TYPES = [
    "polyp",
    "ulcer",
    "inflammation",
    "bleeding",
    "tumor",
    "normal",
]

# Anatomical regions (colonoscopy)
COLON_REGIONS = [
    "rectum",
    "sigmoid",
    "descending_colon",
    "splenic_flexure",
    "transverse_colon",
    "hepatic_flexure",
    "ascending_colon",
    "cecum",
    "terminal_ileum",
]

# Quality thresholds
MIN_WITHDRAWAL_TIME_SEC = 360  # 6 minutes recommended
MIN_BBPS_SCORE = 6  # Boston Bowel Prep Scale

# =============================================================================
# OUTPUT SETTINGS
# =============================================================================

CAPTURES_DIR = OUTPUTS_DIR / "captures"
REPORTS_DIR = OUTPUTS_DIR / "reports"

# Ensure output directories exist
CAPTURES_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)
