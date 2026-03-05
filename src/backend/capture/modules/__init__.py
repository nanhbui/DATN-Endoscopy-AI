"""
Modular components for the multi-view product capture system.

This package contains specialized modules for:
- Image processing (segmentation, background removal, super-resolution)
- GStreamer pipeline management with YOLO integration
- GstShark profiling for performance monitoring
- Quality assessment
"""

from .image_processing import ImageProcessor

try:
    from .gstreamer_integration import GStreamerCapture, GStreamerIntegrationMixin
    from .gst_yolo_plugin import GstYoloManager
    GSTREAMER_AVAILABLE = True
except ImportError as e:
    print(f"[WARNING] GStreamer modules not available: {e}")
    GSTREAMER_AVAILABLE = False
    GStreamerCapture = None
    GStreamerIntegrationMixin = None
    GstYoloManager = None

try:
    from .gstshark_profiler import GstSharkProfiler
    GSTSHARK_AVAILABLE = True
except ImportError:
    GSTSHARK_AVAILABLE = False
    GstSharkProfiler = None

__all__ = [
    "ImageProcessor",
    "GSTREAMER_AVAILABLE",
    "GSTSHARK_AVAILABLE",
]

# Add GStreamer components if available
if GSTREAMER_AVAILABLE:
    __all__.extend([
        "GStreamerCapture",
        "GStreamerIntegrationMixin", 
        "GstYoloManager",
    ])

# Add GstShark if available
if GSTSHARK_AVAILABLE:
    __all__.append("GstSharkProfiler")
