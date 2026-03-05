#!/usr/bin/env python3
"""
GStreamer Pipeline Graph Generator

Captures real GStreamer pipeline graphs using GST_DEBUG_DUMP_DOT_DIR.
These show all actual elements, pads, caps negotiations, and internal state.

Usage:
    # Capture from your YOLO pipeline
    python gst_pipeline_graph.py --yolo --camera 0

    # Capture from any pipeline string
    python gst_pipeline_graph.py --pipeline "videotestsrc ! autovideosink"

    # Convert existing .dot files
    python gst_pipeline_graph.py --convert /path/to/dots
"""

import os
import sys
import argparse
import subprocess
import tempfile
import shutil
import time
import signal
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict

# Add parent directory for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


class GstPipelineGraphGenerator:
    """
    Generates real GStreamer pipeline graphs using debug infrastructure.
    """

    def __init__(self, output_dir: str = "./gst_graphs", verbose: bool = False):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.verbose = verbose
        self.dot_dir = None
        self._check_dependencies()

    def _check_dependencies(self):
        """Check for required dependencies."""
        # Check graphviz
        try:
            result = subprocess.run(['dot', '-V'], capture_output=True, text=True)
            self.graphviz_available = True
            if self.verbose:
                print(f"Graphviz: {result.stderr.strip()}")
        except FileNotFoundError:
            self.graphviz_available = False
            print("Warning: Graphviz not installed. Install with: sudo apt install graphviz")

        # Check GStreamer
        try:
            result = subprocess.run(['gst-inspect-1.0', '--version'], capture_output=True, text=True)
            if self.verbose:
                print(f"GStreamer: {result.stdout.split(chr(10))[0]}")
        except FileNotFoundError:
            print("Error: GStreamer not found!")
            sys.exit(1)

    def setup_dot_capture_dir(self) -> str:
        """Create directory for DOT file capture."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.dot_dir = self.output_dir / f"dots_{timestamp}"
        self.dot_dir.mkdir(parents=True, exist_ok=True)
        return str(self.dot_dir)

    def capture_pipeline_graph(self, pipeline_str: str, duration: float = 3.0,
                                name: str = "pipeline") -> List[str]:
        """
        Capture pipeline graph by running gst-launch-1.0 with DOT debug enabled.

        Args:
            pipeline_str: GStreamer pipeline string
            duration: How long to run the pipeline (seconds)
            name: Name prefix for output files

        Returns:
            List of generated DOT file paths
        """
        self.setup_dot_capture_dir()

        env = os.environ.copy()
        env['GST_DEBUG_DUMP_DOT_DIR'] = str(self.dot_dir)

        # Add debug level to trigger graph generation
        env['GST_DEBUG'] = env.get('GST_DEBUG', '') + ',GST_PIPELINE:5'

        print(f"Capturing pipeline graph...")
        print(f"  DOT output: {self.dot_dir}")
        print(f"  Duration: {duration}s")

        try:
            # Run gst-launch with timeout
            cmd = ['gst-launch-1.0', '-v'] + pipeline_str.split(' ! ')
            # Actually we need the raw string
            cmd = f'gst-launch-1.0 {pipeline_str}'

            process = subprocess.Popen(
                cmd,
                shell=True,
                env=env,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE
            )

            # Let it run for duration
            time.sleep(duration)

            # Stop gracefully
            process.send_signal(signal.SIGINT)
            try:
                process.wait(timeout=2)
            except subprocess.TimeoutExpired:
                process.kill()

        except Exception as e:
            print(f"Error running pipeline: {e}")

        # Find generated DOT files
        dot_files = sorted(self.dot_dir.glob("*.dot"))
        print(f"  Generated {len(dot_files)} DOT files")

        return [str(f) for f in dot_files]

    def capture_with_python_gst(self, pipeline_str: str, duration: float = 3.0) -> List[str]:
        """
        Capture pipeline graph using Python GStreamer bindings.
        This spawns a subprocess to ensure GST_DEBUG_DUMP_DOT_DIR is set before GStreamer init.
        """
        self.setup_dot_capture_dir()

        # Create a capture script that runs in subprocess
        capture_script = f'''
import os
import sys
import time

# Set environment BEFORE importing GStreamer
os.environ['GST_DEBUG_DUMP_DOT_DIR'] = "{self.dot_dir}"

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst

Gst.init(None)

pipeline_str = """{pipeline_str}"""
duration = {duration}

try:
    pipeline = Gst.parse_launch(pipeline_str)

    states = [
        ('0_NULL', Gst.State.NULL),
        ('1_READY', Gst.State.READY),
        ('2_PAUSED', Gst.State.PAUSED),
        ('3_PLAYING', Gst.State.PLAYING),
    ]

    for state_name, state in states:
        pipeline.set_state(state)
        ret = pipeline.get_state(5 * Gst.SECOND)  # 5 second timeout

        if ret[0] in (Gst.StateChangeReturn.SUCCESS, Gst.StateChangeReturn.NO_PREROLL):
            Gst.debug_bin_to_dot_file(
                pipeline,
                Gst.DebugGraphDetails.ALL,
                f"pipeline_{{state_name}}"
            )
            print(f"Captured: {{state_name}}")

    if duration > 0:
        print(f"Running for {{duration}}s...")
        time.sleep(duration)
        Gst.debug_bin_to_dot_file(
            pipeline,
            Gst.DebugGraphDetails.ALL,
            "pipeline_4_FINAL"
        )
        print("Captured: 4_FINAL")

    pipeline.set_state(Gst.State.NULL)
    print("Done")

except Exception as e:
    print(f"Error: {{e}}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
'''

        print(f"Capturing pipeline with Python GStreamer...")
        print(f"  DOT output: {self.dot_dir}")

        # Run capture in subprocess
        result = subprocess.run(
            [sys.executable, '-c', capture_script],
            capture_output=True,
            text=True
        )

        if result.stdout:
            for line in result.stdout.strip().split('\n'):
                print(f"  {line}")

        if result.returncode != 0:
            print(f"  Error: {result.stderr}")

        # Find generated files
        dot_files = sorted(self.dot_dir.glob("*.dot"))
        return [str(f) for f in dot_files]

    def capture_yolo_pipeline(self, camera_id: int = 0, duration: float = 5.0,
                               use_plugin: bool = False) -> List[str]:
        """
        Capture graph from the YOLO inference pipeline.

        Args:
            camera_id: Camera device ID
            duration: How long to capture
            use_plugin: Whether to include yoloinference plugin

        Returns:
            List of DOT file paths
        """
        if use_plugin:
            # Try with YOLO plugin
            pipeline_str = (
                f"v4l2src device=/dev/video{camera_id} num-buffers=100 ! "
                "image/jpeg,width=640,height=480,framerate=30/1 ! "
                "jpegdec ! videoconvert ! video/x-raw,format=RGB ! "
                "yoloinference model=yolov8n.torchscript confidence=0.5 annotate=true ! "
                "videoconvert ! autovideosink"
            )
        else:
            # Basic pipeline without YOLO (for testing)
            pipeline_str = (
                f"v4l2src device=/dev/video{camera_id} num-buffers=100 ! "
                "image/jpeg,width=640,height=480,framerate=30/1 ! "
                "jpegdec ! videoconvert ! video/x-raw,format=RGB ! "
                "videoconvert ! autovideosink"
            )

        return self.capture_with_python_gst(pipeline_str, duration)

    def capture_test_pipeline(self, duration: float = 2.0) -> List[str]:
        """Capture graph from a test pipeline (no camera needed)."""
        pipeline_str = (
            "videotestsrc num-buffers=100 ! "
            "video/x-raw,width=640,height=480,framerate=30/1 ! "
            "videoconvert ! "
            "autovideosink"
        )
        return self.capture_with_python_gst(pipeline_str, duration)

    def convert_dot_to_image(self, dot_path: str, output_format: str = "png") -> Optional[str]:
        """Convert DOT file to image using Graphviz."""
        if not self.graphviz_available:
            return None

        dot_path = Path(dot_path)
        output_path = dot_path.parent / f"{dot_path.stem}.{output_format}"

        try:
            cmd = ['dot', f'-T{output_format}', str(dot_path), '-o', str(output_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                if self.verbose:
                    print(f"  Converted: {output_path.name}")
                return str(output_path)
            else:
                print(f"  Error converting {dot_path.name}: {result.stderr}")
                return None

        except Exception as e:
            print(f"  Error: {e}")
            return None

    def convert_all_dots(self, dot_files: List[str], output_format: str = "png") -> List[str]:
        """Convert all DOT files to images."""
        if not self.graphviz_available:
            print("Graphviz not available. Install with: sudo apt install graphviz")
            return []

        print(f"Converting {len(dot_files)} DOT files to {output_format}...")
        images = []

        for dot_path in dot_files:
            img_path = self.convert_dot_to_image(dot_path, output_format)
            if img_path:
                images.append(img_path)

        return images

    def generate_html_viewer(self, image_files: List[str], dot_files: List[str] = None) -> str:
        """Generate HTML viewer for the pipeline graphs."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Read DOT contents for Viz.js rendering
        dot_data = []
        if dot_files:
            for dot_path in dot_files:
                with open(dot_path, 'r') as f:
                    dot_data.append({
                        'name': Path(dot_path).stem,
                        'dot': f.read()
                    })

        import json
        dot_json = json.dumps(dot_data)

        # Generate tabs
        tabs_html = ""
        for i, data in enumerate(dot_data):
            active = "active" if i == 0 else ""
            tabs_html += f'<button class="tab {active}" onclick="showTab({i})">{data["name"]}</button>\n'

        html = f'''<!DOCTYPE html>
<html>
<head>
    <title>GStreamer Pipeline Graph</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #fff;
            min-height: 100vh;
        }}
        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            text-align: center;
        }}
        .header h1 {{ font-size: 1.8em; margin-bottom: 5px; }}
        .header p {{ opacity: 0.8; font-size: 0.9em; }}
        .tabs {{
            display: flex;
            flex-wrap: wrap;
            gap: 5px;
            padding: 15px;
            background: rgba(255,255,255,0.05);
            justify-content: center;
        }}
        .tab {{
            background: rgba(255,255,255,0.1);
            border: none;
            color: #fff;
            padding: 8px 16px;
            border-radius: 20px;
            cursor: pointer;
            font-size: 0.85em;
            transition: all 0.2s;
        }}
        .tab:hover {{ background: rgba(255,255,255,0.2); }}
        .tab.active {{ background: #667eea; }}
        .viewer {{
            padding: 20px;
            display: flex;
            justify-content: center;
        }}
        .graph-container {{
            background: #fff;
            border-radius: 8px;
            padding: 10px;
            overflow: auto;
            max-width: 98vw;
            max-height: 80vh;
        }}
        .graph-container svg {{
            max-width: 100%;
            height: auto;
        }}
        .controls {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            display: flex;
            gap: 8px;
        }}
        .btn {{
            background: rgba(102, 126, 234, 0.9);
            border: none;
            color: #fff;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.2em;
        }}
        .btn:hover {{ background: #764ba2; }}
        .info {{
            text-align: center;
            padding: 10px;
            font-size: 0.8em;
            opacity: 0.5;
        }}
        .loading {{
            text-align: center;
            padding: 50px;
            font-size: 1.2em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>GStreamer Pipeline Graph</h1>
        <p>Real pipeline structure with all pads and caps</p>
    </div>

    <div class="tabs">
        {tabs_html}
    </div>

    <div class="viewer">
        <div class="graph-container" id="graph">
            <div class="loading">Loading Viz.js...</div>
        </div>
    </div>

    <div class="controls">
        <button class="btn" onclick="zoomIn()">+</button>
        <button class="btn" onclick="zoomOut()">-</button>
        <button class="btn" onclick="resetZoom()">↺</button>
    </div>

    <div class="info">
        Generated: {timestamp} | Use +/- to zoom, drag to pan
    </div>

    <script src="https://unpkg.com/@viz-js/viz@3.2.4/lib/viz-standalone.js"></script>
    <script>
        const dotData = {dot_json};
        let currentTab = 0;
        let zoom = 1;
        let viz = null;

        async function init() {{
            viz = await Viz.instance();
            renderGraph(0);
        }}

        function renderGraph(index) {{
            if (!viz || !dotData[index]) return;

            const container = document.getElementById('graph');
            try {{
                const svg = viz.renderSVGElement(dotData[index].dot);
                container.innerHTML = '';
                container.appendChild(svg);
                applyZoom();
            }} catch (e) {{
                container.innerHTML = '<p style="color:red;padding:20px;">Error: ' + e.message + '</p>';
            }}
        }}

        function showTab(index) {{
            currentTab = index;
            document.querySelectorAll('.tab').forEach((t, i) => {{
                t.classList.toggle('active', i === index);
            }});
            renderGraph(index);
        }}

        function zoomIn() {{ zoom = Math.min(zoom * 1.3, 5); applyZoom(); }}
        function zoomOut() {{ zoom = Math.max(zoom / 1.3, 0.2); applyZoom(); }}
        function resetZoom() {{ zoom = 1; applyZoom(); }}

        function applyZoom() {{
            const svg = document.querySelector('#graph svg');
            if (svg) {{
                svg.style.transform = `scale(${{zoom}})`;
                svg.style.transformOrigin = 'top left';
            }}
        }}

        document.addEventListener('keydown', (e) => {{
            if (e.key === '+' || e.key === '=') zoomIn();
            if (e.key === '-') zoomOut();
            if (e.key === '0') resetZoom();
            if (e.key === 'ArrowLeft' && currentTab > 0) showTab(currentTab - 1);
            if (e.key === 'ArrowRight' && currentTab < dotData.length - 1) showTab(currentTab + 1);
        }});

        init();
    </script>
</body>
</html>'''

        output_path = self.output_dir / "pipeline_graph.html"
        with open(output_path, 'w') as f:
            f.write(html)

        return str(output_path)


def main():
    parser = argparse.ArgumentParser(
        description="Generate real GStreamer pipeline graphs",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Test pipeline (no camera needed)
    python gst_pipeline_graph.py --test

    # Capture from camera
    python gst_pipeline_graph.py --camera 0

    # With YOLO plugin
    python gst_pipeline_graph.py --yolo --camera 0

    # Custom pipeline
    python gst_pipeline_graph.py --pipeline "videotestsrc ! autovideosink"

    # Convert existing DOT files
    python gst_pipeline_graph.py --convert /path/to/dots
        """
    )

    parser.add_argument('--test', action='store_true', help='Use test pipeline (no camera)')
    parser.add_argument('--camera', '-c', type=int, default=0, help='Camera device ID')
    parser.add_argument('--yolo', action='store_true', help='Include YOLO inference plugin')
    parser.add_argument('--pipeline', '-p', type=str, help='Custom pipeline string')
    parser.add_argument('--convert', type=str, help='Convert DOT files from directory')
    parser.add_argument('--duration', '-d', type=float, default=3.0, help='Capture duration (seconds)')
    parser.add_argument('--output', '-o', type=str, default='./gst_graphs', help='Output directory')
    parser.add_argument('--format', '-f', type=str, default='png', choices=['png', 'svg', 'pdf'],
                        help='Output image format')
    parser.add_argument('--verbose', '-v', action='store_true', help='Verbose output')
    parser.add_argument('--open', action='store_true', help='Open viewer in browser')

    args = parser.parse_args()

    generator = GstPipelineGraphGenerator(output_dir=args.output, verbose=args.verbose)

    dot_files = []

    if args.convert:
        # Convert existing DOT files
        dot_dir = Path(args.convert)
        dot_files = sorted(str(f) for f in dot_dir.glob("*.dot"))
        if not dot_files:
            print(f"No DOT files found in {args.convert}")
            return 1

    elif args.pipeline:
        # Custom pipeline
        dot_files = generator.capture_with_python_gst(args.pipeline, args.duration)

    elif args.test:
        # Test pipeline
        dot_files = generator.capture_test_pipeline(args.duration)

    elif args.yolo:
        # YOLO pipeline
        dot_files = generator.capture_yolo_pipeline(args.camera, args.duration, use_plugin=True)

    else:
        # Default: camera pipeline without YOLO
        dot_files = generator.capture_yolo_pipeline(args.camera, args.duration, use_plugin=False)

    if not dot_files:
        print("No DOT files generated. Try --test for a simple test pipeline.")
        return 1

    print(f"\nGenerated {len(dot_files)} DOT files:")
    for f in dot_files:
        print(f"  {Path(f).name}")

    # Convert to images
    images = generator.convert_all_dots(dot_files, args.format)

    if images:
        print(f"\nConverted to {len(images)} images")

    # Generate HTML viewer
    html_path = generator.generate_html_viewer(images, dot_files)
    print(f"\nHTML viewer: {html_path}")

    if args.open:
        import webbrowser
        webbrowser.open(f"file://{Path(html_path).absolute()}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
