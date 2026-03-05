#!/bin/bash
# Script to run capture system with proper virtual environment

echo "========================================="
echo "Starting Product Capture System"
echo "========================================="
echo ""

# Activate virtual environment
echo "[1] Activating virtual environment..."
source .venv/bin/activate

# Check packages
echo "[2] Checking YOLO installation..."
python -c "from ultralytics import YOLO; print('✅ Ultralytics YOLO available')" 2>/dev/null || echo "❌ YOLO not found!"

echo ""
echo "[3] Starting capture system..."
echo "========================================="
echo ""

# Run capture system (disable GStreamer, use pure OpenCV + YOLO)
python src/backend/capture/capture_system.py --angles 3 --no-gstreamer "$@"

# Deactivate on exit
deactivate
