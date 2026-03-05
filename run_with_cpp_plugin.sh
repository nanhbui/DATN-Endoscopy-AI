#!/bin/bash
# Run capture system with C++ GStreamer YOLO plugin

echo "========================================="
echo "Starting Capture System with C++ Plugin"
echo "========================================="
echo ""

# Parse arguments for profiling
PROFILING=false
for arg in "$@"; do
    if [[ "$arg" == "--profile" ]] || [[ "$arg" == "--profiling" ]]; then
        PROFILING=true
        break
    fi
done

# Set GST_PLUGIN_PATH to include our plugin
export GST_PLUGIN_PATH="$(pwd)/gstreamer_plugin_c/build:$GST_PLUGIN_PATH"

# Enable GstShark profiling if requested
if [ "$PROFILING" = true ]; then
    echo "🔥 GstShark profiling ENABLED"
    export GST_TRACERS="framerate;proctime;cpuusage;interlatency"
    export GST_DEBUG_DUMP_DOT_DIR="$(pwd)/gstshark_logs"
    mkdir -p gstshark_logs
fi

# DO NOT set LD_LIBRARY_PATH here - it conflicts with Python PyTorch
# LibTorch will be loaded by the plugin when needed

echo "[1] Activating virtual environment..."
source .venv/bin/activate

echo ""
echo "[2] Checking plugin..."
if gst-inspect-1.0 yoloinference > /dev/null 2>&1; then
    echo "✅ C++ YOLO plugin found"
else
    echo "❌ Plugin not found!"
    echo "Build first: cd gstreamer_plugin_c && ./build.sh"
    exit 1
fi

echo ""
echo "[3] Checking YOLO model..."
if [ -f "yolov8n-seg.torchscript" ]; then
    echo "✅ TorchScript model found"
else
    echo "❌ Model not found!"
    echo "Export first: python export_yolo_torchscript.py"
    exit 1
fi

echo ""
echo "[4] Starting capture system..."
if [ "$PROFILING" = true ]; then
    echo "📊 Profiling logs will be saved to: gstshark_logs/"
fi
echo "========================================="
echo ""

# Run capture system (will use GStreamer with C++ plugin)
cd phase_1
python capture_system.py --angles 3 "$@"

# Deactivate on exit
deactivate

# Generate performance report if profiling enabled
if [ "$PROFILING" = true ]; then
    echo ""
    echo "========================================="
    echo "📊 Generating performance report..."
    echo "========================================="

    cd ..
    python generate_gstshark_report.py --log-dir gstshark_logs

    echo ""
    echo "✅ Profiling complete!"
    echo "📁 Logs: gstshark_logs/"
    echo "📊 Report: gstshark_logs/performance_report_*.json"
fi
