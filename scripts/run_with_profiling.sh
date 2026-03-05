#!/bin/bash

# Script để chạy capture system với GstShark profiling enabled
# Sử dụng: ./run_with_profiling.sh

echo "🎯 STARTING CAPTURE SYSTEM WITH GSTSHARK PROFILING"
echo "================================================="

# Activate virtual environment
source .venv/bin/activate

# Set environment variables
export FORCE_GSTREAMER=1
export ENABLE_GSTSHARK_PROFILING=true

# Run với profiling
echo "🔥 Launching with:"
echo "  - REAL YOLO detection"
echo "  - GStreamer pipeline" 
echo "  - GstShark profiling"
echo "  - Real-time monitoring"
echo ""

python src/backend/capture/capture_system.py --profiling "$@"

echo ""
echo "📊 Performance logs saved to: captured_images/gstshark_logs/"
echo "🎊 Profiling session complete!"