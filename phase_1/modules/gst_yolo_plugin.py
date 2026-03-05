# Disable Python GStreamer YOLO plugin - use C++ plugin instead
PLUGIN_ENABLED = False

if PLUGIN_ENABLED:
    import gi
    gi.require_version('Gst', '1.0')
    gi.require_version('GstBase', '1.0')
    from gi.repository import Gst, GObject, GstBase
    Gst.init(None)
else:
    # Dummy imports for disabled plugin
    Gst = None
import numpy as np
import cv2
from typing import Optional, Dict, List, Any
import json

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("[WARNING] Ultralytics YOLO not available. Install with: pip install ultralytics")


if PLUGIN_ENABLED:
    # Initialize GStreamer
    Gst.init(None)


if PLUGIN_ENABLED:
    class GstYoloInference(GstBase.BaseTransform):
        # Plugin metadata
        __gstmetadata__ = (
            'YOLO Inference',
            'Filter/Analyzer/Video',
            'Performs YOLO object detection/segmentation on video frames',
            'Product Capture System'
        )

        # Pad templates
        _sink_template = Gst.PadTemplate.new(
            'sink',
            Gst.PadDirection.SINK,
            Gst.PadPresence.ALWAYS,
            Gst.Caps.from_string('video/x-raw,format=RGB')
        )

        _src_template = Gst.PadTemplate.new(
            'src',
            Gst.PadDirection.SRC,
            Gst.PadPresence.ALWAYS,
            Gst.Caps.from_string('video/x-raw,format=RGB')
        )

        # Register pad templates
        __gsttemplates__ = (_sink_template, _src_template)

    # Properties
    __gproperties__ = {
        'model-path': (
            str,
            'Model Path',
            'Path to YOLO model file',
            'yolov8n.pt',
            GObject.ParamFlags.READWRITE
        ),
        'confidence': (
            float,
            'Confidence Threshold',
            'Minimum confidence for detections',
            0.0, 1.0, 0.25,
            GObject.ParamFlags.READWRITE
        ),
        'iou-threshold': (
            float,
            'IOU Threshold',
            'IOU threshold for NMS',
            0.0, 1.0, 0.45,
            GObject.ParamFlags.READWRITE
        ),
        'device': (
            str,
            'Device',
            'Device for inference (cpu, cuda, mps, or auto)',
            'auto',
            GObject.ParamFlags.READWRITE
        ),
        'annotate': (
            bool,
            'Annotate',
            'Draw bounding boxes on output frames',
            True,
            GObject.ParamFlags.READWRITE
        ),
        'emit-metadata': (
            bool,
            'Emit Metadata',
            'Emit detection metadata as GStreamer messages',
            True,
            GObject.ParamFlags.READWRITE
        ),
    }

    def __init__(self):
        """Initialize the YOLO inference element."""
        super().__init__()

        # Properties
        self.model_path = 'yolov8n.pt'
        self.confidence = 0.25
        self.iou_threshold = 0.45
        self.device = 'auto'
        self.annotate = True
        self.emit_metadata = True

        # Internal state
        self.model: Optional[YOLO] = None
        self.frame_count = 0
        self.inference_times = []

        # Set transform properties
        self.set_in_place(False)  # We'll modify the buffer
        self.set_passthrough(False)

    def do_start(self):
        """Called when element starts. Load YOLO model."""
        if not YOLO_AVAILABLE:
            Gst.error(f"YOLO not available. Cannot start inference.")
            return False

        try:
            Gst.info(f"Loading YOLO model: {self.model_path}")

            # Determine device
            if self.device == 'auto':
                import torch
                if torch.cuda.is_available():
                    device = 'cuda'
                elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
                    device = 'mps'
                else:
                    device = 'cpu'
            else:
                device = self.device

            # Load model
            self.model = YOLO(self.model_path)
            self.model.to(device)

            Gst.info(f"YOLO model loaded on device: {device}")
            return True

        except Exception as e:
            Gst.error(f"Failed to load YOLO model: {e}")
            return False

    def do_stop(self):
        """Called when element stops. Cleanup resources."""
        if self.model is not None:
            Gst.info("Releasing YOLO model")
            self.model = None

        # Print statistics
        if self.inference_times:
            avg_time = np.mean(self.inference_times)
            avg_fps = 1.0 / avg_time if avg_time > 0 else 0
            Gst.info(f"Inference statistics: {self.frame_count} frames, "
                    f"avg time: {avg_time*1000:.2f}ms, avg FPS: {avg_fps:.2f}")

        return True

    def do_transform(self, inbuf: Gst.Buffer, outbuf: Gst.Buffer) -> Gst.FlowReturn:
        """
        Transform function - runs YOLO inference on input buffer.

        Args:
            inbuf: Input GStreamer buffer containing video frame
            outbuf: Output GStreamer buffer for annotated frame

        Returns:
            Gst.FlowReturn: GST_FLOW_OK on success, error otherwise
        """
        try:
            # Get video info from caps
            caps = self.sinkpad.get_current_caps()
            if not caps:
                Gst.error("No caps on sink pad")
                return Gst.FlowReturn.ERROR

            struct = caps.get_structure(0)
            width = struct.get_value('width')
            height = struct.get_value('height')

            # Map input buffer to numpy array
            success, map_info = inbuf.map(Gst.MapFlags.READ)
            if not success:
                Gst.error("Failed to map input buffer")
                return Gst.FlowReturn.ERROR

            try:
                # Convert buffer to numpy array (RGB format)
                frame = np.ndarray(
                    shape=(height, width, 3),
                    dtype=np.uint8,
                    buffer=map_info.data
                )

                # Make a copy for modification
                frame_copy = np.copy(frame)

            finally:
                inbuf.unmap(map_info)

            # Run YOLO inference
            import time
            start_time = time.time()

            results = self.model(
                frame_copy,
                conf=self.confidence,
                iou=self.iou_threshold,
                verbose=False
            )[0]

            inference_time = time.time() - start_time
            self.inference_times.append(inference_time)
            self.frame_count += 1

            # Extract detection results
            detections = self._extract_detections(results)

            # Emit metadata as GStreamer message
            if self.emit_metadata and detections:
                self._emit_metadata(detections, inference_time)

            # Annotate frame if requested
            if self.annotate:
                frame_copy = self._annotate_frame(frame_copy, results)

            # Map output buffer and copy annotated frame
            success, map_info = outbuf.map(Gst.MapFlags.WRITE)
            if not success:
                Gst.error("Failed to map output buffer")
                return Gst.FlowReturn.ERROR

            try:
                # Copy annotated frame to output buffer
                out_array = np.ndarray(
                    shape=(height, width, 3),
                    dtype=np.uint8,
                    buffer=map_info.data
                )
                np.copyto(out_array, frame_copy)

            finally:
                outbuf.unmap(map_info)

            return Gst.FlowReturn.OK

        except Exception as e:
            Gst.error(f"Error in transform: {e}")
            import traceback
            traceback.print_exc()
            return Gst.FlowReturn.ERROR

    def _extract_detections(self, results) -> List[Dict[str, Any]]:
        """
        Extract detection information from YOLO results.

        Args:
            results: YOLO result object

        Returns:
            List of detection dictionaries
        """
        detections = []

        if results.boxes is not None:
            boxes = results.boxes.cpu().numpy()

            for i, box in enumerate(boxes):
                detection = {
                    'class_id': int(box.cls[0]),
                    'class_name': results.names[int(box.cls[0])],
                    'confidence': float(box.conf[0]),
                    'bbox': box.xyxy[0].tolist(),  # [x1, y1, x2, y2]
                }

                # Add segmentation mask if available
                if results.masks is not None and i < len(results.masks):
                    mask = results.masks[i].cpu().numpy()
                    detection['has_mask'] = True
                    detection['mask_shape'] = mask.shape
                else:
                    detection['has_mask'] = False

                detections.append(detection)

        return detections

    def _annotate_frame(self, frame: np.ndarray, results) -> np.ndarray:
        """
        Draw bounding boxes and labels on frame.

        Args:
            frame: Input frame (numpy array)
            results: YOLO result object

        Returns:
            Annotated frame
        """
        # Use YOLO's built-in plotting for consistency
        annotated = results.plot()

        # Convert BGR to RGB (YOLO plot returns BGR)
        annotated = cv2.cvtColor(annotated, cv2.COLOR_BGR2RGB)

        return annotated

    def _emit_metadata(self, detections: List[Dict[str, Any]], inference_time: float):
        """
        Emit detection metadata as GStreamer message.

        Args:
            detections: List of detection dictionaries
            inference_time: Time taken for inference (seconds)
        """
        metadata = {
            'frame': self.frame_count,
            'inference_time_ms': inference_time * 1000,
            'num_detections': len(detections),
            'detections': detections
        }

        # Create GStreamer structure
        struct = Gst.Structure.new_from_string(f"yolo-inference")
        struct.set_value('metadata', json.dumps(metadata))

        # Post message on bus
        msg = Gst.Message.new_application(self, struct)
        self.post_message(msg)

    def do_set_property(self, prop: GObject.GParamSpec, value):
        """Set element property."""
        if prop.name == 'model-path':
            self.model_path = value
        elif prop.name == 'confidence':
            self.confidence = value
        elif prop.name == 'iou-threshold':
            self.iou_threshold = value
        elif prop.name == 'device':
            self.device = value
        elif prop.name == 'annotate':
            self.annotate = value
        elif prop.name == 'emit-metadata':
            self.emit_metadata = value

    def do_get_property(self, prop: GObject.GParamSpec):
        """Get element property."""
        if prop.name == 'model-path':
            return self.model_path
        elif prop.name == 'confidence':
            return self.confidence
        elif prop.name == 'iou-threshold':
            return self.iou_threshold
        elif prop.name == 'device':
            return self.device
        elif prop.name == 'annotate':
            return self.annotate
        elif prop.name == 'emit-metadata':
            return self.emit_metadata


    # Register element (inside if PLUGIN_ENABLED block)
    GObject.type_register(GstYoloInference)
else:
    # Dummy class when plugin is disabled
    class GstYoloInference:
        """Dummy class when plugin is disabled"""
        pass


if PLUGIN_ENABLED:
    def plugin_init(plugin):
        """
        Plugin initialization function.
        Called by GStreamer to register elements.
        """
        # Get or register the type
        try:
            gtype = GObject.type_from_name("GstYoloInference")
        except RuntimeError:
            # Type not registered yet, register it
            gtype = GObject.type_register(GstYoloInference)

        # Register the element
        return Gst.Element.register(plugin, "yoloinference", 0, gtype)


    def register_plugin():
        """
        Register the YOLO inference plugin with GStreamer.

        This function should be called to make the plugin available to GStreamer.

        Note: Python GStreamer bindings have limitations with plugin registration.
        This uses a direct element factory registration approach.
        """
        try:
            # Register the GObject type
            try:
                gtype = GObject.type_from_name("GstYoloInference")
            except RuntimeError:
                gtype = GObject.type_register(GstYoloInference)

            # Create a simple plugin and register element
            # This approach bypasses some Python binding limitations
            result = Gst.Plugin.register_static(
                Gst.VERSION_MAJOR,
                Gst.VERSION_MINOR,
                'yoloinference',
                'YOLO inference plugin for GStreamer',
                plugin_init,
                '1.0',
                'MIT',
                'Product Capture System',
                'Product Capture System',
                'https://github.com/yourrepo'
            )

            if not result:
                # Fallback: Try direct registration (Python binding workaround)
                print("[INFO] Trying alternative registration method...")
                # This won't work with parse_launch, but element can be created directly
                return gtype is not None

            return result

        except Exception as e:
            print(f"[ERROR] Plugin registration failed: {e}")
            import traceback
            traceback.print_exc()
            return False
else:
    # Dummy functions when plugin is disabled
    def register_plugin():
        """Dummy register_plugin when plugin is disabled"""
        return False


class GstYoloManager:
    """
    Manager class for GStreamer YOLO plugin integration.
    Supports both Python and C++ YOLO plugins.
    """

    def __init__(self):
        # Initialize GStreamer
        try:
            import gi
            gi.require_version('Gst', '1.0')
            from gi.repository import Gst as GstLib
            GstLib.init(None)
            self.Gst = GstLib
            self.gst_available = True
        except Exception as e:
            print(f"[WARNING] GStreamer not available: {e}")
            self.Gst = None
            self.gst_available = False

        self.pipeline = None
        self.bus = None
        self.appsink = None
        self.plugin_registered = False
        self.detections = []
        self.inference_stats = {'avg_time': 0, 'frame_count': 0}
        self.using_cpp_plugin = False

        # Check if plugin is enabled
        if not PLUGIN_ENABLED:
            print("[INFO] GstYoloManager: Python plugin disabled, will try C++ plugin")

    def _check_cpp_plugin_available(self) -> bool:
        """Check if C++ yoloinference plugin is available."""
        if not self.gst_available:
            return False

        try:
            registry = self.Gst.Registry.get()
            plugin = registry.find_plugin("yoloinference")
            if plugin:
                print(f"[INFO] Found C++ yoloinference plugin: {plugin.get_filename()}")
                return True
        except Exception as e:
            print(f"[DEBUG] C++ plugin check error: {e}")
        return False

    def register_plugin(self) -> bool:
        """Register the YOLO plugin (Python or C++)."""
        # First check for C++ plugin
        if self._check_cpp_plugin_available():
            print("[SUCCESS] C++ yoloinference plugin is available")
            self.using_cpp_plugin = True
            return True

        # Try Python plugin if enabled
        if not PLUGIN_ENABLED:
            print("[INFO] Python plugin disabled, C++ plugin not found")
            return False

        if not self.plugin_registered:
            self.plugin_registered = register_plugin()
            if self.plugin_registered:
                print("[SUCCESS] GStreamer YOLO plugin registered (Python)")
            else:
                print("[ERROR] Failed to register GStreamer YOLO plugin")
        return self.plugin_registered

    def create_pipeline(self, camera_id: int = 0, model_path: str = "yolov8n-seg.pt",
                       confidence: float = 0.25, width: int = 1280, height: int = 720) -> bool:
        """
        Create GStreamer pipeline with YOLO inference.
        Supports both Python (.pt) and C++ (.torchscript) models.

        Args:
            camera_id: Camera device ID
            model_path: Path to YOLO model (.pt for Python, .torchscript for C++)
            confidence: Detection confidence threshold
            width: Frame width
            height: Frame height

        Returns:
            bool: True if pipeline created successfully
        """
        if not self.gst_available:
            print("[ERROR] GStreamer not available")
            return False

        if not self.register_plugin():
            print("[ERROR] No YOLO plugin available (neither C++ nor Python)")
            return False

        try:
            # Determine model path based on plugin type
            if self.using_cpp_plugin:
                # C++ plugin uses TorchScript models
                import os
                if model_path.endswith('.pt'):
                    model_path = model_path.replace('.pt', '.torchscript')

                # Use absolute path for C++ plugin
                if not os.path.isabs(model_path):
                    # Go up to project root: phase_1/modules -> phase_1 -> project_root
                    project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
                    model_path = os.path.join(project_root, model_path)

                print(f"[INFO] Using C++ plugin, model: {model_path}")

                # Create pipeline for C++ plugin
                pipeline_str = (
                    f"v4l2src device=/dev/video{camera_id} ! "
                    f"image/jpeg,width={width},height={height},framerate=30/1 ! "
                    "jpegdec ! videoconvert ! video/x-raw,format=RGB ! "
                    f"yoloinference model={model_path} confidence={confidence} "
                    f"annotate=true ! "
                    "videoconvert ! video/x-raw,format=BGR ! "
                    "appsink name=sink emit-signals=true max-buffers=1 drop=true"
                )
            else:
                # Python plugin
                print(f"[INFO] Using Python plugin, model: {model_path}")
                pipeline_str = (
                    f"v4l2src device=/dev/video{camera_id} ! "
                    f"image/jpeg, width={width}, height={height}, framerate=30/1 ! "
                    "jpegdec ! videoconvert ! video/x-raw,format=RGB ! "
                    f"yoloinference model-path={model_path} confidence={confidence} "
                    f"iou-threshold=0.45 device=auto annotate=true emit-metadata=true ! "
                    "videoconvert ! appsink name=sink emit-signals=true max-buffers=1 drop=true"
                )

            print(f"[INFO] Creating GStreamer pipeline...")
            print(f"[DEBUG] Pipeline: {pipeline_str}")
            self.pipeline = self.Gst.parse_launch(pipeline_str)
            
            # Get the appsink element
            self.appsink = self.pipeline.get_by_name('sink')
            
            # Set up bus for messages
            self.bus = self.pipeline.get_bus()
            self.bus.add_signal_watch()
            
            return True
            
        except Exception as e:
            print(f"[ERROR] Failed to create pipeline: {e}")
            return False
    
    def start_pipeline(self) -> bool:
        """Start the GStreamer pipeline."""
        if not self.gst_available:
            print("[ERROR] GStreamer not available")
            return False

        if not self.pipeline:
            print("[ERROR] No pipeline to start")
            return False

        try:
            ret = self.pipeline.set_state(self.Gst.State.PLAYING)
            if ret == self.Gst.StateChangeReturn.FAILURE:
                print("[ERROR] Failed to start pipeline")
                return False

            print(f"[INFO] GStreamer pipeline started (using {'C++' if self.using_cpp_plugin else 'Python'} plugin)")
            return True

        except Exception as e:
            print(f"[ERROR] Error starting pipeline: {e}")
            import traceback
            traceback.print_exc()
            return False

    def get_frame(self) -> Optional[np.ndarray]:
        """Get annotated frame from the pipeline."""
        if not self.gst_available:
            return None

        if not self.appsink:
            return None

        try:
            # Use emit() for appsink signal-based sample pulling
            sample = self.appsink.emit("pull-sample")
            if sample is None:
                return None

            buffer = sample.get_buffer()
            caps = sample.get_caps()

            # Get frame dimensions
            struct = caps.get_structure(0)
            width = struct.get_value('width')
            height = struct.get_value('height')

            # Map buffer to numpy array
            success, map_info = buffer.map(self.Gst.MapFlags.READ)
            if not success:
                return None

            try:
                # C++ plugin outputs BGR, Python outputs RGB
                frame = np.ndarray(
                    shape=(height, width, 3),
                    dtype=np.uint8,
                    buffer=map_info.data
                ).copy()

                # Convert BGR to RGB if using C++ plugin
                if self.using_cpp_plugin:
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)

                return frame

            finally:
                buffer.unmap(map_info)

        except Exception as e:
            print(f"[ERROR] Error getting frame: {e}")
            return None
    
    def check_messages(self) -> List[Dict[str, Any]]:
        """Check for YOLO detection messages (Python plugin only)."""
        detections = []

        if not self.gst_available or not self.bus:
            return detections

        # C++ plugin doesn't emit metadata yet
        if self.using_cpp_plugin:
            return detections

        try:
            while True:
                msg = self.bus.pop_filtered(self.Gst.MessageType.APPLICATION)
                if msg is None:
                    break

                struct = msg.get_structure()
                if struct and struct.get_name() == 'yolo-inference':
                    metadata_json = struct.get_value('metadata')
                    metadata = json.loads(metadata_json)
                    detections.append(metadata)

                    # Update stats
                    self.inference_stats['frame_count'] = metadata['frame']
                    if metadata['inference_time_ms'] > 0:
                        # Simple moving average
                        if self.inference_stats['avg_time'] == 0:
                            self.inference_stats['avg_time'] = metadata['inference_time_ms']
                        else:
                            self.inference_stats['avg_time'] = (
                                self.inference_stats['avg_time'] * 0.9 +
                                metadata['inference_time_ms'] * 0.1
                            )

        except Exception as e:
            print(f"[ERROR] Error checking messages: {e}")

        return detections

    def stop_pipeline(self):
        """Stop and cleanup the pipeline."""
        if not self.gst_available:
            return

        if self.pipeline:
            try:
                self.pipeline.set_state(self.Gst.State.NULL)
                print("[INFO] GStreamer pipeline stopped")
            except Exception as e:
                print(f"[ERROR] Error stopping pipeline: {e}")

        if self.bus:
            self.bus.remove_signal_watch()

        self.pipeline = None
        self.bus = None
        self.appsink = None


if __name__ == '__main__':
    # Test the plugin
    print("Testing GStreamer YOLO Plugin Manager")
    print("=" * 60)

    if not PLUGIN_ENABLED:
        print("[INFO] Plugin is disabled, cannot run test")
        exit(0)

    manager = GstYoloManager()
    
    if not manager.create_pipeline(camera_id=0):
        print("[ERROR] Failed to create pipeline")
        exit(1)
    
    if not manager.start_pipeline():
        print("[ERROR] Failed to start pipeline")
        exit(1)
    
    print("Press Ctrl+C to stop")
    
    try:
        while True:
            frame = manager.get_frame()
            if frame is not None:
                cv2.imshow('YOLO Detection', cv2.cvtColor(frame, cv2.COLOR_RGB2BGR))
                
            detections = manager.check_messages()
            for detection in detections:
                print(f"[DETECTION] Frame {detection['frame']}: "
                      f"{detection['num_detections']} objects, "
                      f"{detection['inference_time_ms']:.2f}ms")
                
            if cv2.waitKey(1) & 0xFF == ord('q'):
                break
                
    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
        
    finally:
        manager.stop_pipeline()
        cv2.destroyAllWindows()