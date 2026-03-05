"""
GStreamer pipeline created with code (not parse_launch)
This allows using Python YOLO plugin
"""
import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GObject
import numpy as np
import cv2

# Import the YOLO plugin
from gst_yolo_plugin import GstYoloInference, register_plugin

Gst.init(None)


class GStreamerYOLOPipeline:
    """
    GStreamer pipeline with YOLO created via code (not parse_launch).
    This works with Python plugins.
    """

    def __init__(self, camera_id=0, model_path="yolov8n-seg.pt",
                 width=1280, height=720, confidence=0.25):
        self.camera_id = camera_id
        self.model_path = model_path
        self.width = width
        self.height = height
        self.confidence = confidence

        self.pipeline = None
        self.appsink = None
        self.yolo_element = None

    def create_pipeline(self):
        """Create GStreamer pipeline using code (not parse_launch)."""
        print("[INFO] Creating GStreamer pipeline with code...")

        # Register YOLO plugin
        if not register_plugin():
            print("[ERROR] Failed to register YOLO plugin")
            return False

        # Create pipeline
        self.pipeline = Gst.Pipeline.new("yolo-pipeline")

        # Create elements
        try:
            # Video source
            source = Gst.ElementFactory.make("v4l2src", "source")
            source.set_property("device", f"/dev/video{self.camera_id}")

            # JPEG decoder
            jpegdec = Gst.ElementFactory.make("jpegdec", "decoder")

            # Video convert
            convert1 = Gst.ElementFactory.make("videoconvert", "convert1")

            # YOLO inference (Python plugin!)
            self.yolo_element = GstYoloInference()  # Direct instantiation!
            self.yolo_element.set_property("model-path", self.model_path)
            self.yolo_element.set_property("confidence", self.confidence)
            self.yolo_element.set_property("annotate", True)
            self.yolo_element.set_property("emit-metadata", True)

            # Convert back
            convert2 = Gst.ElementFactory.make("videoconvert", "convert2")

            # App sink
            self.appsink = Gst.ElementFactory.make("appsink", "sink")
            self.appsink.set_property("emit-signals", True)
            self.appsink.set_property("max-buffers", 1)
            self.appsink.set_property("drop", True)

            # Add all elements to pipeline
            elements = [source, jpegdec, convert1, self.yolo_element,
                       convert2, self.appsink]

            for elem in elements:
                if not self.pipeline.add(elem):
                    print(f"[ERROR] Failed to add {elem.get_name()}")
                    return False

            # Set caps for source
            caps_filter = Gst.ElementFactory.make("capsfilter", "filter")
            caps = Gst.Caps.from_string(
                f"image/jpeg,width={self.width},height={self.height},framerate=30/1"
            )
            caps_filter.set_property("caps", caps)
            self.pipeline.add(caps_filter)

            # Link elements: source -> caps -> decoder -> convert1
            if not source.link(caps_filter):
                print("[ERROR] Failed to link source -> caps")
                return False
            if not caps_filter.link(jpegdec):
                print("[ERROR] Failed to link caps -> jpegdec")
                return False
            if not jpegdec.link(convert1):
                print("[ERROR] Failed to link jpegdec -> convert1")
                return False

            # Set RGB caps after convert1
            rgb_caps_filter = Gst.ElementFactory.make("capsfilter", "rgb_filter")
            rgb_caps = Gst.Caps.from_string("video/x-raw,format=RGB")
            rgb_caps_filter.set_property("caps", rgb_caps)
            self.pipeline.add(rgb_caps_filter)

            if not convert1.link(rgb_caps_filter):
                print("[ERROR] Failed to link convert1 -> rgb_caps")
                return False

            # Link to YOLO element
            if not rgb_caps_filter.link_pads(None, self.yolo_element, "sink"):
                print("[ERROR] Failed to link rgb_caps -> yolo")
                return False

            # Link YOLO -> convert2 -> appsink
            if not self.yolo_element.link_pads("src", convert2, None):
                print("[ERROR] Failed to link yolo -> convert2")
                return False
            if not convert2.link(self.appsink):
                print("[ERROR] Failed to link convert2 -> appsink")
                return False

            print("[SUCCESS] GStreamer pipeline created with YOLO!")
            return True

        except Exception as e:
            print(f"[ERROR] Failed to create pipeline: {e}")
            import traceback
            traceback.print_exc()
            return False

    def start(self):
        """Start the pipeline."""
        if not self.pipeline:
            return False

        ret = self.pipeline.set_state(Gst.State.PLAYING)
        if ret == Gst.StateChangeReturn.FAILURE:
            print("[ERROR] Failed to start pipeline")
            return False

        print("[SUCCESS] GStreamer pipeline started!")
        return True

    def get_frame(self):
        """Get frame from pipeline."""
        if not self.appsink:
            return None

        sample = self.appsink.try_pull_sample(Gst.SECOND)
        if not sample:
            return None

        buffer = sample.get_buffer()
        caps = sample.get_caps()

        struct = caps.get_structure(0)
        width = struct.get_value('width')
        height = struct.get_value('height')

        success, map_info = buffer.map(Gst.MapFlags.READ)
        if not success:
            return None

        try:
            frame = np.ndarray(
                shape=(height, width, 3),
                dtype=np.uint8,
                buffer=map_info.data
            ).copy()
            return frame
        finally:
            buffer.unmap(map_info)

    def stop(self):
        """Stop the pipeline."""
        if self.pipeline:
            self.pipeline.set_state(Gst.State.NULL)
            print("[INFO] Pipeline stopped")


def test_pipeline():
    """Test the code-based pipeline."""
    print("="*60)
    print("Testing GStreamer + YOLO Pipeline (Code-based)")
    print("="*60)

    pipeline = GStreamerYOLOPipeline(
        camera_id=0,
        model_path="yolov8n-seg.pt",
        confidence=0.25
    )

    if not pipeline.create_pipeline():
        print("[ERROR] Failed to create pipeline")
        return False

    if not pipeline.start():
        print("[ERROR] Failed to start pipeline")
        return False

    print("\nPress Ctrl+C to stop")
    print("="*60)

    try:
        frame_count = 0
        while True:
            frame = pipeline.get_frame()
            if frame is not None:
                # Convert RGB to BGR for display
                display = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

                cv2.putText(display, f"Frame: {frame_count}", (10, 30),
                           cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

                cv2.imshow('GStreamer + YOLO', display)
                frame_count += 1

            if cv2.waitKey(1) & 0xFF == ord('q'):
                break

    except KeyboardInterrupt:
        print("\n[INFO] Interrupted by user")
    finally:
        pipeline.stop()
        cv2.destroyAllWindows()

    return True


if __name__ == '__main__':
    test_pipeline()
