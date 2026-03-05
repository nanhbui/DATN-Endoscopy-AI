"""
GStreamer-based capture system integration.
Provides enhanced capture system using GStreamer YOLO plugin for better performance.
"""

import cv2
import numpy as np
from typing import Optional, List, Dict, Any, Tuple
import json
import time
from pathlib import Path

from .gst_yolo_plugin import GstYoloManager


class GStreamerCapture:
    """
    Enhanced capture system using GStreamer YOLO plugin.
    Provides optimized video processing with hardware acceleration.
    """
    
    def __init__(self, 
                 camera_id: int = 0, 
                 model_path: str = "yolov8n-seg.pt",
                 confidence: float = 0.25,
                 width: int = 1280,
                 height: int = 720):
        """
        Initialize GStreamer-based capture system.
        
        Args:
            camera_id: Camera device ID
            model_path: Path to YOLO model
            confidence: Detection confidence threshold
            width: Frame width
            height: Frame height
        """
        self.camera_id = camera_id
        self.model_path = model_path
        self.confidence = confidence
        self.width = width
        self.height = height
        
        # Initialize GStreamer manager
        self.gst_manager = GstYoloManager()
        
        # State tracking
        self.is_active = False
        self.current_frame = None
        self.current_detections = []
        self.frame_count = 0
        self.inference_stats = {'avg_time': 0, 'total_frames': 0}
        
        # Fallback to OpenCV if GStreamer fails
        self.fallback_cap = None
        self.use_fallback = False
    
    def initialize(self) -> bool:
        """
        Initialize the capture system.
        
        Returns:
            bool: True if initialization successful
        """
        print("[INFO] Initializing GStreamer YOLO capture system...")
        
        # Try to create GStreamer pipeline
        if self.gst_manager.create_pipeline(
            camera_id=self.camera_id,
            model_path=self.model_path,
            confidence=self.confidence,
            width=self.width,
            height=self.height
        ):
            if self.gst_manager.start_pipeline():
                self.is_active = True
                print("[SUCCESS] GStreamer pipeline active")
                return True
            else:
                print("[WARNING] GStreamer pipeline failed to start, trying fallback...")
        
        # Fallback to OpenCV
        return self._initialize_fallback()
    
    def _initialize_fallback(self) -> bool:
        """Initialize OpenCV fallback capture."""
        print("[INFO] Initializing OpenCV fallback...")
        
        try:
            # Try GStreamer pipeline first
            gst_pipeline = (
                f"v4l2src device=/dev/video{self.camera_id} ! "
                f"image/jpeg, width={self.width}, height={self.height}, framerate=30/1 ! "
                "jpegdec ! videoconvert ! appsink"
            )
            
            self.fallback_cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
            if self.fallback_cap.isOpened():
                ret, _ = self.fallback_cap.read()
                if ret:
                    self.use_fallback = True
                    self.is_active = True
                    print("[SUCCESS] OpenCV with GStreamer backend active")
                    return True
            
            # Pure OpenCV fallback
            if self.fallback_cap:
                self.fallback_cap.release()
            
            self.fallback_cap = cv2.VideoCapture(self.camera_id)
            self.fallback_cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.fallback_cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            
            if self.fallback_cap.isOpened():
                ret, _ = self.fallback_cap.read()
                if ret:
                    self.use_fallback = True
                    self.is_active = True
                    print("[SUCCESS] OpenCV fallback active")
                    return True
                    
        except Exception as e:
            print(f"[ERROR] Fallback initialization failed: {e}")
        
        print("[ERROR] All capture methods failed")
        return False
    
    def read_frame(self) -> Tuple[bool, Optional[np.ndarray], List[Dict[str, Any]]]:
        """
        Read frame and get detections.
        
        Returns:
            Tuple[bool, Optional[np.ndarray], List[Dict]]: (success, frame, detections)
        """
        if not self.is_active:
            return False, None, []
        
        detections = []
        
        if self.use_fallback:
            # OpenCV fallback mode
            ret, frame = self.fallback_cap.read()
            if not ret:
                return False, None, []
                
            self.current_frame = frame
            return True, frame, []  # No detections in fallback mode
        
        else:
            # GStreamer mode with YOLO
            frame = self.gst_manager.get_frame()
            if frame is None:
                return False, None, []
            
            # Check for new detections
            new_detections = self.gst_manager.check_messages()
            if new_detections:
                self.current_detections = new_detections[-1]  # Get latest
                detections = self.current_detections.get('detections', [])
                
                # Update stats
                self.inference_stats = self.gst_manager.inference_stats
                
            self.current_frame = frame
            self.frame_count += 1
            
            return True, frame, detections
    
    def get_current_detections(self) -> List[Dict[str, Any]]:
        """Get current frame detections."""
        if self.use_fallback:
            return []
        return self.current_detections.get('detections', []) if self.current_detections else []
    
    def get_inference_stats(self) -> Dict[str, float]:
        """Get inference performance statistics."""
        if self.use_fallback:
            return {'avg_time': 0, 'avg_fps': 0, 'total_frames': self.frame_count}
        
        stats = self.inference_stats.copy()
        stats['avg_fps'] = 1000.0 / stats['avg_time'] if stats['avg_time'] > 0 else 0
        stats['total_frames'] = self.frame_count
        return stats
    
    def capture_image(self, save_path: Optional[str] = None) -> Tuple[bool, Optional[np.ndarray], Dict[str, Any]]:
        """
        Capture current frame with metadata.
        
        Args:
            save_path: Optional path to save image
            
        Returns:
            Tuple[bool, Optional[np.ndarray], Dict]: (success, frame, metadata)
        """
        ret, frame, detections = self.read_frame()
        if not ret or frame is None:
            return False, None, {}
        
        metadata = {
            'timestamp': time.time(),
            'frame_count': self.frame_count,
            'detections': detections,
            'inference_stats': self.get_inference_stats(),
            'capture_method': 'gstreamer' if not self.use_fallback else 'opencv'
        }
        
        if save_path:
            try:
                # Convert RGB to BGR for OpenCV saving
                save_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) if not self.use_fallback else frame
                cv2.imwrite(save_path, save_frame)
                metadata['saved_path'] = save_path
            except Exception as e:
                print(f"[ERROR] Failed to save image: {e}")
                metadata['save_error'] = str(e)
        
        return True, frame, metadata
    
    def set_confidence(self, confidence: float):
        """Update confidence threshold."""
        self.confidence = confidence
        # Note: For runtime change, we'd need to recreate the pipeline
        # This would require stopping and restarting

    def get_frame(self) -> Optional[np.ndarray]:
        """
        Get frame (convenience method).

        Returns:
            Frame or None if failed
        """
        ret, frame, _ = self.read_frame()
        return frame if ret else None

    def stop_pipeline(self):
        """Stop the pipeline (convenience method)."""
        self.release()

    def release(self):
        """Release capture resources."""
        self.is_active = False

        if not self.use_fallback and self.gst_manager:
            self.gst_manager.stop_pipeline()

        if self.fallback_cap:
            self.fallback_cap.release()
            self.fallback_cap = None

        print("[INFO] GStreamer capture system released")


class GStreamerIntegrationMixin:
    """
    Mixin class to add GStreamer capabilities to existing capture system.
    Can be mixed into the existing CaptureSystem class.
    """
    
    def _initialize_gstreamer_capture(self):
        """Initialize GStreamer-based capture."""
        self.gst_capture = GStreamerCapture(
            camera_id=self.camera_id,
            model_path=self.model_name,
            confidence=0.25,  # Default, will be updated during inference
            width=1280,
            height=720
        )
        
        return self.gst_capture.initialize()
    
    def _read_gstreamer_frame(self):
        """Read frame using GStreamer capture."""
        if hasattr(self, 'gst_capture') and self.gst_capture.is_active:
            return self.gst_capture.read_frame()
        return False, None, []
    
    def _get_gstreamer_detections(self):
        """Get current detections from GStreamer."""
        if hasattr(self, 'gst_capture'):
            return self.gst_capture.get_current_detections()
        return []
    
    def _release_gstreamer(self):
        """Release GStreamer resources."""
        if hasattr(self, 'gst_capture'):
            self.gst_capture.release()


def test_gstreamer_capture():
    """Test the GStreamer capture system."""
    print("Testing GStreamer Capture System")
    print("=" * 50)
    
    capture = GStreamerCapture()
    
    if not capture.initialize():
        print("[ERROR] Failed to initialize capture")
        return False
    
    print("Press 'q' to quit, 's' to capture, 'c' to show stats")
    
    frame_count = 0
    try:
        while True:
            ret, frame, detections = capture.read_frame()
            
            if ret and frame is not None:
                # Convert to BGR for display
                display_frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR) if not capture.use_fallback else frame
                
                # Add info overlay
                info_text = f"Frame: {frame_count}, Detections: {len(detections)}"
                cv2.putText(display_frame, info_text, (10, 30), 
                           cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                
                if detections:
                    stats = capture.get_inference_stats()
                    stats_text = f"Avg: {stats['avg_time']:.1f}ms, FPS: {stats['avg_fps']:.1f}"
                    cv2.putText(display_frame, stats_text, (10, 60), 
                               cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                
                cv2.imshow('GStreamer Capture Test', display_frame)
                frame_count += 1
            
            key = cv2.waitKey(1) & 0xFF
            if key == ord('q'):
                break
            elif key == ord('s'):
                ret, frame, metadata = capture.capture_image(f"test_capture_{frame_count}.jpg")
                if ret:
                    print(f"[INFO] Captured image with {len(metadata.get('detections', []))} detections")
                    print(f"[INFO] Method: {metadata.get('capture_method')}")
            elif key == ord('c'):
                stats = capture.get_inference_stats()
                print(f"[STATS] Frames: {stats['total_frames']}, "
                      f"Avg time: {stats['avg_time']:.2f}ms, "
                      f"Avg FPS: {stats['avg_fps']:.2f}")
                
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    
    finally:
        capture.release()
        cv2.destroyAllWindows()
    
    return True


if __name__ == '__main__':
    test_gstreamer_capture()