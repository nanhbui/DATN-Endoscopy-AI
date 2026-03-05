#!/usr/bin/env python3
"""
gst-dots-viewer: GStreamer Pipeline Visualization Tool

This tool generates visual representations of GStreamer pipelines by:
1. Capturing DOT graph dumps from GStreamer
2. Converting DOT files to PNG/SVG images
3. Generating interactive HTML visualizations

Usage:
    # Generate visualization from running pipeline
    python gst_dots_viewer.py --capture --output pipeline_viz

    # Convert existing DOT files
    python gst_dots_viewer.py --input /path/to/dots --output visualizations

    # Interactive mode with live pipeline
    python gst_dots_viewer.py --live --camera 0
"""

import os
import sys
import argparse
import subprocess
import tempfile
import shutil
import json
import time
from pathlib import Path
from datetime import datetime
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
import re

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))


@dataclass
class PipelineElement:
    """Represents a GStreamer pipeline element."""
    name: str
    factory: str
    state: str = "NULL"
    properties: Dict[str, Any] = field(default_factory=dict)
    pads: List[str] = field(default_factory=list)


@dataclass
class PipelineGraph:
    """Represents a complete pipeline graph."""
    name: str
    elements: List[PipelineElement]
    links: List[Tuple[str, str, str, str]]  # (src_elem, src_pad, sink_elem, sink_pad)
    timestamp: str = ""
    state: str = "NULL"


class GstDotsViewer:
    """
    GStreamer Pipeline Visualization Tool

    Captures and visualizes GStreamer pipeline graphs using DOT format.
    """

    # Pipeline states for DOT file naming
    STATES = ['NULL', 'READY', 'PAUSED', 'PLAYING']

    # Color scheme for different element types
    ELEMENT_COLORS = {
        'source': '#90EE90',      # Light green
        'sink': '#FFB6C1',        # Light pink
        'filter': '#87CEEB',      # Sky blue
        'decoder': '#DDA0DD',     # Plum
        'encoder': '#F0E68C',     # Khaki
        'convert': '#E6E6FA',     # Lavender
        'queue': '#FAFAD2',       # Light goldenrod
        'tee': '#FFE4B5',         # Moccasin
        'mux': '#D8BFD8',         # Thistle
        'demux': '#B0C4DE',       # Light steel blue
        'default': '#FFFFFF',     # White
    }

    def __init__(self, output_dir: str = None, verbose: bool = False):
        """
        Initialize the GstDotsViewer.

        Args:
            output_dir: Directory for output files (default: ./gst_visualizations)
            verbose: Enable verbose output
        """
        self.output_dir = Path(output_dir) if output_dir else Path("./gst_visualizations")
        self.verbose = verbose
        self.dot_dir = None
        self._temp_dir = None

        # Ensure output directory exists
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Check for graphviz
        self.graphviz_available = self._check_graphviz()

    def _check_graphviz(self) -> bool:
        """Check if Graphviz is installed."""
        try:
            result = subprocess.run(['dot', '-V'], capture_output=True, text=True)
            if self.verbose:
                print(f"Graphviz found: {result.stderr.strip()}")
            return True
        except FileNotFoundError:
            print("Warning: Graphviz not found. Install with: sudo apt install graphviz")
            return False

    def setup_dot_capture(self) -> str:
        """
        Set up environment for capturing DOT graphs from GStreamer.

        Returns:
            Path to the DOT capture directory
        """
        self._temp_dir = tempfile.mkdtemp(prefix="gst_dots_")
        self.dot_dir = self._temp_dir

        # Set environment variable for GStreamer
        os.environ['GST_DEBUG_DUMP_DOT_DIR'] = self.dot_dir

        if self.verbose:
            print(f"DOT capture directory: {self.dot_dir}")
            print("Set GST_DEBUG_DUMP_DOT_DIR environment variable")

        return self.dot_dir

    def cleanup(self):
        """Clean up temporary directories."""
        if self._temp_dir and os.path.exists(self._temp_dir):
            shutil.rmtree(self._temp_dir)
            self._temp_dir = None
            self.dot_dir = None

    def capture_pipeline_dot(self, pipeline, state_name: str = None) -> Optional[str]:
        """
        Capture a DOT graph from a GStreamer pipeline.

        Args:
            pipeline: GStreamer pipeline object
            state_name: Optional name for the state (e.g., 'PLAYING')

        Returns:
            Path to the generated DOT file
        """
        try:
            import gi
            gi.require_version('Gst', '1.0')
            from gi.repository import Gst

            if not self.dot_dir:
                self.setup_dot_capture()

            # Get pipeline name
            pipeline_name = pipeline.get_name() or "pipeline"

            # Generate DOT debug dump
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            state_str = state_name or "capture"

            # GStreamer's debug_bin_to_dot_file function
            Gst.debug_bin_to_dot_file(
                pipeline,
                Gst.DebugGraphDetails.ALL,
                f"{pipeline_name}_{state_str}_{timestamp}"
            )

            # Find the generated file
            dot_files = list(Path(self.dot_dir).glob("*.dot"))
            if dot_files:
                latest_dot = max(dot_files, key=lambda p: p.stat().st_mtime)
                if self.verbose:
                    print(f"Captured DOT file: {latest_dot}")
                return str(latest_dot)

            return None

        except Exception as e:
            print(f"Error capturing pipeline DOT: {e}")
            return None

    def parse_dot_file(self, dot_path: str) -> Optional[PipelineGraph]:
        """
        Parse a DOT file and extract pipeline structure.

        Args:
            dot_path: Path to the DOT file

        Returns:
            PipelineGraph object with parsed data
        """
        try:
            with open(dot_path, 'r') as f:
                content = f.read()

            # Extract graph name
            name_match = re.search(r'digraph\s+"?([^"{\s]+)"?\s*\{', content)
            graph_name = name_match.group(1) if name_match else "pipeline"

            elements = []
            links = []

            # Parse element definitions (nodes)
            # Pattern: "element_name" [label="..."]
            node_pattern = r'"([^"]+)"\s*\[([^\]]+)\]'
            for match in re.finditer(node_pattern, content):
                node_name = match.group(1)
                attrs = match.group(2)

                # Extract label
                label_match = re.search(r'label\s*=\s*"([^"]*)"', attrs)
                label = label_match.group(1) if label_match else node_name

                # Determine element factory from label
                factory = label.split('\\n')[0] if '\\n' in label else label

                elements.append(PipelineElement(
                    name=node_name,
                    factory=factory
                ))

            # Parse links (edges)
            # Pattern: "src" -> "sink" [label="..."]
            edge_pattern = r'"([^"]+)"\s*->\s*"([^"]+)"(?:\s*\[([^\]]*)\])?'
            for match in re.finditer(edge_pattern, content):
                src = match.group(1)
                sink = match.group(2)
                attrs = match.group(3) or ""

                # Extract pad names from label if present
                label_match = re.search(r'label\s*=\s*"([^"]*)"', attrs)
                label = label_match.group(1) if label_match else ""

                src_pad = "src"
                sink_pad = "sink"
                if "->" in label:
                    parts = label.split("->")
                    src_pad = parts[0].strip()
                    sink_pad = parts[1].strip()

                links.append((src, src_pad, sink, sink_pad))

            return PipelineGraph(
                name=graph_name,
                elements=elements,
                links=links,
                timestamp=datetime.now().isoformat()
            )

        except Exception as e:
            print(f"Error parsing DOT file: {e}")
            return None

    def convert_dot_to_image(self, dot_path: str, output_format: str = "png") -> Optional[str]:
        """
        Convert a DOT file to an image using Graphviz.

        Args:
            dot_path: Path to the DOT file
            output_format: Output format ('png', 'svg', 'pdf')

        Returns:
            Path to the generated image file
        """
        if not self.graphviz_available:
            print("Graphviz not available. Cannot convert DOT to image.")
            return None

        try:
            dot_path = Path(dot_path)
            output_path = self.output_dir / f"{dot_path.stem}.{output_format}"

            # Run dot command
            cmd = ['dot', f'-T{output_format}', str(dot_path), '-o', str(output_path)]
            result = subprocess.run(cmd, capture_output=True, text=True)

            if result.returncode == 0:
                if self.verbose:
                    print(f"Generated: {output_path}")
                return str(output_path)
            else:
                print(f"Graphviz error: {result.stderr}")
                return None

        except Exception as e:
            print(f"Error converting DOT to image: {e}")
            return None

    def generate_html_viewer(self, dot_files: List[str], output_name: str = "pipeline_viewer") -> str:
        """
        Generate an interactive HTML viewer for pipeline visualizations.

        Args:
            dot_files: List of DOT file paths
            output_name: Name for the output HTML file

        Returns:
            Path to the generated HTML file
        """
        # Read DOT contents for client-side rendering with Viz.js
        dot_contents = []
        svg_data = []

        for dot_path in dot_files:
            # Read DOT content for Viz.js
            with open(dot_path, 'r') as f:
                dot_content = f.read()
                dot_contents.append({
                    'name': Path(dot_path).stem,
                    'dot': dot_content
                })

            # Also try to convert to SVG for fallback
            svg_path = self.convert_dot_to_image(dot_path, "svg")
            if svg_path:
                with open(svg_path, 'r') as f:
                    svg_content = f.read()
                    svg_match = re.search(r'(<svg[^>]*>.*</svg>)', svg_content, re.DOTALL)
                    if svg_match:
                        svg_data.append({
                            'name': Path(dot_path).stem,
                            'svg': svg_match.group(1)
                        })

        # Generate HTML - prefer Viz.js (client-side) if DOT contents available
        # This works even without Graphviz installed locally
        html_content = self._generate_html_template(svg_data, dot_contents)

        output_path = self.output_dir / f"{output_name}.html"
        with open(output_path, 'w') as f:
            f.write(html_content)

        if self.verbose:
            print(f"Generated HTML viewer: {output_path}")

        return str(output_path)

    def _generate_html_template(self, svg_data: List[Dict], dot_contents: List[Dict] = None) -> str:
        """Generate the HTML template for the viewer."""

        svg_tabs = ""
        svg_content = ""

        # If we have DOT content, use Viz.js for rendering
        if dot_contents:
            for i, data in enumerate(dot_contents):
                active_class = "active" if i == 0 else ""
                svg_tabs += f'''
                    <button class="tab-btn {active_class}" onclick="showTab({i})">{data['name']}</button>
                '''

            dot_data_json = json.dumps(dot_contents)
        else:
            dot_data_json = "[]"

            for i, data in enumerate(svg_data):
                active_class = "active" if i == 0 else ""
                display_style = "block" if i == 0 else "none"

                svg_tabs += f'''
                    <button class="tab-btn {active_class}" onclick="showTab({i})">{data['name']}</button>
                '''

                svg_content += f'''
                    <div class="svg-container" id="svg-{i}" style="display: {display_style}">
                        {data['svg']}
                    </div>
                '''

        return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>GStreamer Pipeline Viewer</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            color: #fff;
        }}

        .header {{
            background: rgba(255,255,255,0.1);
            padding: 20px;
            text-align: center;
            border-bottom: 1px solid rgba(255,255,255,0.1);
        }}

        .header h1 {{
            font-size: 2em;
            margin-bottom: 10px;
        }}

        .header p {{
            opacity: 0.7;
        }}

        .controls {{
            display: flex;
            justify-content: center;
            gap: 10px;
            padding: 20px;
            flex-wrap: wrap;
        }}

        .tab-btn {{
            background: rgba(255,255,255,0.1);
            border: 1px solid rgba(255,255,255,0.2);
            color: #fff;
            padding: 10px 20px;
            border-radius: 8px;
            cursor: pointer;
            transition: all 0.3s ease;
        }}

        .tab-btn:hover {{
            background: rgba(255,255,255,0.2);
        }}

        .tab-btn.active {{
            background: #4CAF50;
            border-color: #4CAF50;
        }}

        .viewer {{
            padding: 20px;
            display: flex;
            justify-content: center;
        }}

        .svg-container {{
            background: #fff;
            border-radius: 12px;
            padding: 20px;
            max-width: 95vw;
            overflow: auto;
            box-shadow: 0 10px 40px rgba(0,0,0,0.3);
        }}

        .svg-container svg {{
            max-width: 100%;
            height: auto;
        }}

        .zoom-controls {{
            position: fixed;
            bottom: 20px;
            right: 20px;
            display: flex;
            gap: 10px;
        }}

        .zoom-btn {{
            background: rgba(255,255,255,0.2);
            border: none;
            color: #fff;
            width: 40px;
            height: 40px;
            border-radius: 50%;
            cursor: pointer;
            font-size: 1.5em;
            transition: all 0.3s ease;
        }}

        .zoom-btn:hover {{
            background: rgba(255,255,255,0.3);
        }}

        .legend {{
            position: fixed;
            bottom: 20px;
            left: 20px;
            background: rgba(0,0,0,0.7);
            padding: 15px;
            border-radius: 8px;
            font-size: 0.85em;
        }}

        .legend-item {{
            display: flex;
            align-items: center;
            margin: 5px 0;
        }}

        .legend-color {{
            width: 20px;
            height: 20px;
            border-radius: 4px;
            margin-right: 10px;
        }}

        .info {{
            text-align: center;
            padding: 10px;
            opacity: 0.6;
            font-size: 0.9em;
        }}
    </style>
</head>
<body>
    <div class="header">
        <h1>GStreamer Pipeline Viewer</h1>
        <p>Interactive visualization of GStreamer pipeline graphs</p>
    </div>

    <div class="controls">
        {svg_tabs}
    </div>

    <div class="viewer">
        {svg_content}
    </div>

    <div class="zoom-controls">
        <button class="zoom-btn" onclick="zoomIn()">+</button>
        <button class="zoom-btn" onclick="zoomOut()">-</button>
        <button class="zoom-btn" onclick="resetZoom()">&#8634;</button>
    </div>

    <div class="legend">
        <div class="legend-item">
            <div class="legend-color" style="background: #90EE90;"></div>
            <span>Source elements</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #FFB6C1;"></div>
            <span>Sink elements</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #87CEEB;"></div>
            <span>Filter/Transform</span>
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #DDA0DD;"></div>
            <span>Decoder</span>
        </div>
    </div>

    <div class="info">
        Generated by gst-dots-viewer | {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    </div>

    <!-- Viz.js for client-side DOT rendering -->
    <script src="https://unpkg.com/@viz-js/viz@3.2.4/lib/viz-standalone.js"></script>

    <script>
        let currentZoom = 1;
        const dotData = {dot_data_json};
        let currentTabIndex = 0;

        // Initialize: render DOT graphs using Viz.js
        async function initViz() {{
            if (dotData.length === 0) return;

            try {{
                const viz = await Viz.instance();

                for (let i = 0; i < dotData.length; i++) {{
                    const container = document.createElement('div');
                    container.className = 'svg-container';
                    container.id = 'svg-' + i;
                    container.style.display = i === 0 ? 'block' : 'none';

                    try {{
                        const svg = viz.renderSVGElement(dotData[i].dot);
                        container.appendChild(svg);
                    }} catch (e) {{
                        container.innerHTML = '<p style="color: red;">Error rendering graph: ' + e.message + '</p><pre>' + dotData[i].dot + '</pre>';
                    }}

                    document.querySelector('.viewer').appendChild(container);
                }}
            }} catch (e) {{
                console.error('Failed to initialize Viz.js:', e);
                document.querySelector('.viewer').innerHTML = '<p style="color: red;">Failed to load Viz.js. Please check your internet connection.</p>';
            }}
        }}

        // Initialize on page load
        if (dotData.length > 0) {{
            document.addEventListener('DOMContentLoaded', initViz);
        }}

        function showTab(index) {{
            currentTabIndex = index;

            // Hide all containers
            document.querySelectorAll('.svg-container').forEach(el => {{
                el.style.display = 'none';
            }});

            // Remove active class from all buttons
            document.querySelectorAll('.tab-btn').forEach(el => {{
                el.classList.remove('active');
            }});

            // Show selected container
            const container = document.getElementById('svg-' + index);
            if (container) {{
                container.style.display = 'block';
            }}

            // Add active class to clicked button
            const buttons = document.querySelectorAll('.tab-btn');
            if (buttons[index]) {{
                buttons[index].classList.add('active');
            }}
        }}

        function zoomIn() {{
            currentZoom = Math.min(currentZoom * 1.2, 3);
            applyZoom();
        }}

        function zoomOut() {{
            currentZoom = Math.max(currentZoom / 1.2, 0.3);
            applyZoom();
        }}

        function resetZoom() {{
            currentZoom = 1;
            applyZoom();
        }}

        function applyZoom() {{
            document.querySelectorAll('.svg-container svg').forEach(svg => {{
                svg.style.transform = `scale(${{currentZoom}})`;
                svg.style.transformOrigin = 'top left';
            }});
        }}

        // Pan functionality
        let isPanning = false;
        let startX, startY, scrollLeft, scrollTop;

        document.querySelectorAll('.svg-container').forEach(container => {{
            container.addEventListener('mousedown', (e) => {{
                isPanning = true;
                startX = e.pageX - container.offsetLeft;
                startY = e.pageY - container.offsetTop;
                scrollLeft = container.scrollLeft;
                scrollTop = container.scrollTop;
                container.style.cursor = 'grabbing';
            }});

            container.addEventListener('mouseleave', () => {{
                isPanning = false;
                container.style.cursor = 'grab';
            }});

            container.addEventListener('mouseup', () => {{
                isPanning = false;
                container.style.cursor = 'grab';
            }});

            container.addEventListener('mousemove', (e) => {{
                if (!isPanning) return;
                e.preventDefault();
                const x = e.pageX - container.offsetLeft;
                const y = e.pageY - container.offsetTop;
                const walkX = (x - startX) * 2;
                const walkY = (y - startY) * 2;
                container.scrollLeft = scrollLeft - walkX;
                container.scrollTop = scrollTop - walkY;
            }});
        }});

        // Keyboard shortcuts
        document.addEventListener('keydown', (e) => {{
            if (e.key === '+' || e.key === '=') zoomIn();
            if (e.key === '-') zoomOut();
            if (e.key === '0') resetZoom();
            if (e.key === 'ArrowLeft' && currentTabIndex > 0) showTab(currentTabIndex - 1);
            if (e.key === 'ArrowRight' && currentTabIndex < dotData.length - 1) showTab(currentTabIndex + 1);
        }});

        // Mouse wheel zoom
        document.querySelector('.viewer').addEventListener('wheel', (e) => {{
            if (e.ctrlKey) {{
                e.preventDefault();
                if (e.deltaY < 0) zoomIn();
                else zoomOut();
            }}
        }});
    </script>
</body>
</html>
'''

    def visualize_pipeline_string(self, pipeline_str: str, output_name: str = "pipeline") -> Dict[str, str]:
        """
        Create visualization from a GStreamer pipeline string.

        Args:
            pipeline_str: GStreamer pipeline description string
            output_name: Base name for output files

        Returns:
            Dictionary with paths to generated files
        """
        try:
            import gi
            gi.require_version('Gst', '1.0')
            from gi.repository import Gst

            # Initialize GStreamer
            if not Gst.is_initialized():
                Gst.init(None)

            # Setup DOT capture
            self.setup_dot_capture()

            # Create pipeline
            pipeline = Gst.parse_launch(pipeline_str)

            results = {}

            # Capture at different states
            for state_name, state in [('NULL', Gst.State.NULL),
                                       ('READY', Gst.State.READY),
                                       ('PAUSED', Gst.State.PAUSED)]:
                pipeline.set_state(state)
                # Wait for state change
                pipeline.get_state(Gst.CLOCK_TIME_NONE)

                dot_path = self.capture_pipeline_dot(pipeline, state_name)
                if dot_path:
                    # Convert to image
                    png_path = self.convert_dot_to_image(dot_path, "png")
                    svg_path = self.convert_dot_to_image(dot_path, "svg")

                    results[state_name] = {
                        'dot': dot_path,
                        'png': png_path,
                        'svg': svg_path
                    }

            # Cleanup pipeline
            pipeline.set_state(Gst.State.NULL)

            # Generate HTML viewer
            dot_files = [r['dot'] for r in results.values() if r.get('dot')]
            if dot_files:
                html_path = self.generate_html_viewer(dot_files, output_name)
                results['html_viewer'] = html_path

            return results

        except Exception as e:
            print(f"Error visualizing pipeline: {e}")
            import traceback
            traceback.print_exc()
            return {}

    def visualize_from_dot_dir(self, dot_dir: str, output_name: str = "pipeline") -> Dict[str, str]:
        """
        Create visualizations from existing DOT files in a directory.

        Args:
            dot_dir: Directory containing DOT files
            output_name: Base name for output files

        Returns:
            Dictionary with paths to generated files
        """
        dot_dir = Path(dot_dir)
        dot_files = list(dot_dir.glob("*.dot"))

        if not dot_files:
            print(f"No DOT files found in {dot_dir}")
            return {}

        results = {'images': [], 'dot_files': []}

        for dot_file in sorted(dot_files):
            png_path = self.convert_dot_to_image(str(dot_file), "png")
            svg_path = self.convert_dot_to_image(str(dot_file), "svg")

            if png_path:
                results['images'].append(png_path)
            results['dot_files'].append(str(dot_file))

        # Generate HTML viewer
        if results['dot_files']:
            html_path = self.generate_html_viewer(results['dot_files'], output_name)
            results['html_viewer'] = html_path

        return results


class LivePipelineVisualizer:
    """
    Real-time pipeline visualization with live updates.
    """

    def __init__(self, viewer: GstDotsViewer):
        self.viewer = viewer
        self.running = False

    def visualize_yolo_pipeline(self, camera_id: int = 0, duration: float = 5.0) -> Dict[str, str]:
        """
        Capture and visualize the YOLO inference pipeline.

        Args:
            camera_id: Camera device ID
            duration: How long to run the pipeline (seconds)

        Returns:
            Dictionary with visualization paths
        """
        try:
            import gi
            gi.require_version('Gst', '1.0')
            from gi.repository import Gst, GLib

            if not Gst.is_initialized():
                Gst.init(None)

            # Setup DOT capture
            self.viewer.setup_dot_capture()

            # Simple test pipeline (without YOLO for basic testing)
            pipeline_str = (
                f"v4l2src device=/dev/video{camera_id} num-buffers=30 ! "
                "image/jpeg,width=640,height=480,framerate=30/1 ! "
                "jpegdec ! videoconvert ! video/x-raw,format=RGB ! "
                "videoconvert ! autovideosink"
            )

            print(f"Creating pipeline: {pipeline_str[:80]}...")
            pipeline = Gst.parse_launch(pipeline_str)

            results = {}

            # Capture NULL state
            dot_path = self.viewer.capture_pipeline_dot(pipeline, "0_NULL")
            if dot_path:
                results['NULL'] = dot_path

            # Set to READY
            pipeline.set_state(Gst.State.READY)
            pipeline.get_state(Gst.CLOCK_TIME_NONE)
            dot_path = self.viewer.capture_pipeline_dot(pipeline, "1_READY")
            if dot_path:
                results['READY'] = dot_path

            # Set to PAUSED
            pipeline.set_state(Gst.State.PAUSED)
            pipeline.get_state(Gst.CLOCK_TIME_NONE)
            dot_path = self.viewer.capture_pipeline_dot(pipeline, "2_PAUSED")
            if dot_path:
                results['PAUSED'] = dot_path

            # Set to PLAYING
            pipeline.set_state(Gst.State.PLAYING)
            pipeline.get_state(Gst.CLOCK_TIME_NONE)
            dot_path = self.viewer.capture_pipeline_dot(pipeline, "3_PLAYING")
            if dot_path:
                results['PLAYING'] = dot_path

            # Run for specified duration
            print(f"Running pipeline for {duration} seconds...")
            time.sleep(duration)

            # Final capture
            dot_path = self.viewer.capture_pipeline_dot(pipeline, "4_FINAL")
            if dot_path:
                results['FINAL'] = dot_path

            # Stop pipeline
            pipeline.set_state(Gst.State.NULL)

            # Generate visualizations
            dot_files = list(results.values())
            final_results = {}

            for name, dot_path in results.items():
                png_path = self.viewer.convert_dot_to_image(dot_path, "png")
                if png_path:
                    final_results[name] = {
                        'dot': dot_path,
                        'png': png_path
                    }

            # Generate HTML viewer
            if dot_files:
                html_path = self.viewer.generate_html_viewer(dot_files, "yolo_pipeline")
                final_results['html_viewer'] = html_path

            return final_results

        except Exception as e:
            print(f"Error in live visualization: {e}")
            import traceback
            traceback.print_exc()
            return {}


def create_sample_pipeline_diagram() -> str:
    """
    Create a sample pipeline diagram without needing GStreamer.
    Useful for documentation and testing.
    """
    dot_content = '''digraph pipeline {
    rankdir=LR;
    node [shape=box, style="rounded,filled", fontname="Arial", fontsize=11];
    edge [fontname="Arial", fontsize=9];

    // Title
    labelloc="t";
    label="GStreamer YOLO Inference Pipeline";
    fontsize=16;
    fontname="Arial Bold";

    // Source
    v4l2src [label="v4l2src\\n/dev/video0", fillcolor="#90EE90"];

    // Decoder
    jpegdec [label="jpegdec", fillcolor="#DDA0DD"];

    // Converters
    videoconvert1 [label="videoconvert\\n(to RGB)", fillcolor="#E6E6FA"];
    videoconvert2 [label="videoconvert\\n(to BGR)", fillcolor="#E6E6FA"];

    // YOLO Plugin
    yoloinference [label="yoloinference\\nmodel=yolov8n.torchscript\\nconfidence=0.6\\nannotate=true", fillcolor="#87CEEB", shape=box3d];

    // Sink
    appsink [label="appsink\\nemit-signals=true", fillcolor="#FFB6C1"];

    // Links
    v4l2src -> jpegdec [label="image/jpeg\\n1920x1080@30fps"];
    jpegdec -> videoconvert1 [label="video/x-raw"];
    videoconvert1 -> yoloinference [label="RGB"];
    yoloinference -> videoconvert2 [label="RGB+annotations"];
    videoconvert2 -> appsink [label="BGR"];
}'''
    return dot_content


def create_detailed_yolo_pipeline_diagram() -> str:
    """
    Create a detailed YOLO pipeline diagram showing internal processing.
    """
    dot_content = '''digraph yolo_pipeline {
    rankdir=TB;
    node [shape=box, style="rounded,filled", fontname="Arial", fontsize=10];
    edge [fontname="Arial", fontsize=8];
    compound=true;

    labelloc="t";
    label="GStreamer YOLO Plugin - Detailed Architecture";
    fontsize=14;
    fontname="Arial Bold";

    // Input stage
    subgraph cluster_input {
        label="Input Stage";
        style="rounded,filled";
        fillcolor="#f0f0f0";

        camera [label="USB Camera\\n/dev/video0", fillcolor="#90EE90", shape=cylinder];
        v4l2src [label="v4l2src\\nV4L2 Source", fillcolor="#90EE90"];
        jpegdec [label="jpegdec\\nJPEG Decoder", fillcolor="#DDA0DD"];
        convert1 [label="videoconvert\\nBGR → RGB", fillcolor="#E6E6FA"];
    }

    // YOLO Processing
    subgraph cluster_yolo {
        label="YOLO Inference Plugin";
        style="rounded,filled";
        fillcolor="#e8f4f8";

        preprocess [label="Preprocess\\nResize 640x640\\nNormalize [0,1]", fillcolor="#FFE4B5"];
        inference [label="LibTorch Inference\\ntorch::jit::Module\\nforward()", fillcolor="#87CEEB", shape=box3d];
        postprocess [label="Post-process\\nNMS (IoU=0.45)\\nMask Generation", fillcolor="#FFE4B5"];
        annotate [label="Annotate\\nDraw BBox\\nDraw Contours", fillcolor="#DDA0DD"];
    }

    // Output stage
    subgraph cluster_output {
        label="Output Stage";
        style="rounded,filled";
        fillcolor="#f0f0f0";

        convert2 [label="videoconvert\\nRGB → BGR", fillcolor="#E6E6FA"];
        appsink [label="appsink\\nPull to Python", fillcolor="#FFB6C1"];
        python [label="Python App\\nQuality Check\\nMongoDB Storage", fillcolor="#FFB6C1", shape=cylinder];
    }

    // Connections
    camera -> v4l2src [label="JPEG stream"];
    v4l2src -> jpegdec [label="image/jpeg\\n1920x1080@30fps"];
    jpegdec -> convert1 [label="video/x-raw\\nBGR"];
    convert1 -> preprocess [label="RGB", lhead=cluster_yolo];

    preprocess -> inference [label="Tensor\\n[1,3,640,640]"];
    inference -> postprocess [label="Detections\\n+ Proto masks"];
    postprocess -> annotate [label="Filtered\\ndetections"];

    annotate -> convert2 [label="Annotated\\nframe", ltail=cluster_yolo];
    convert2 -> appsink [label="BGR"];
    appsink -> python [label="GstBuffer\\n→ numpy"];
}'''
    return dot_content


def create_architecture_diagram() -> str:
    """
    Create an architecture overview diagram.
    """
    dot_content = '''digraph architecture {
    rankdir=TB;
    node [shape=box, style="rounded,filled", fontname="Arial", fontsize=10];
    edge [fontname="Arial", fontsize=8];
    compound=true;

    labelloc="t";
    label="System Architecture Overview";
    fontsize=14;
    fontname="Arial Bold";

    // Python Layer
    subgraph cluster_python {
        label="Python Application Layer";
        style="rounded,filled";
        fillcolor="#e8f4e8";

        capture [label="CaptureSystem\\ncapture_system.py", fillcolor="#90EE90"];
        gst_manager [label="GstYoloManager\\ngst_yolo_plugin.py", fillcolor="#90EE90"];
        quality [label="QualityChecker\\nquality_assessment.py", fillcolor="#90EE90"];
        mongo [label="MongoDB\\nStorage", fillcolor="#90EE90", shape=cylinder];
    }

    // GStreamer Layer
    subgraph cluster_gstreamer {
        label="GStreamer Framework";
        style="rounded,filled";
        fillcolor="#e8e8f4";

        pipeline [label="Gst.Pipeline\\nparse_launch()", fillcolor="#87CEEB"];
        elements [label="Standard Elements\\nv4l2src, jpegdec,\\nvideoconvert, appsink", fillcolor="#87CEEB"];
    }

    // Plugin Layer
    subgraph cluster_plugin {
        label="C++ YOLO Plugin";
        style="rounded,filled";
        fillcolor="#f4e8e8";

        gst_element [label="GstYoloInference\\ngstyoloinference.cpp", fillcolor="#FFB6C1"];
        yolo_runner [label="YoloRunner\\nyolo_runner.cpp", fillcolor="#FFB6C1"];
        libtorch [label="LibTorch\\nTorchScript Model", fillcolor="#FFB6C1", shape=box3d];
    }

    // Hardware
    subgraph cluster_hardware {
        label="Hardware";
        style="rounded,filled";
        fillcolor="#f0f0f0";

        camera_hw [label="USB Camera", fillcolor="#FAFAD2", shape=cylinder];
        turntable [label="Turntable\\n(Optional)", fillcolor="#FAFAD2", shape=cylinder];
    }

    // Connections
    capture -> gst_manager;
    capture -> quality;
    capture -> mongo;

    gst_manager -> pipeline [label="Control"];
    pipeline -> elements;
    elements -> gst_element [label="Buffer"];

    gst_element -> yolo_runner [label="Frame"];
    yolo_runner -> libtorch [label="Inference"];

    camera_hw -> elements [label="V4L2", style=dashed];
    turntable -> capture [label="Serial", style=dashed];
}'''
    return dot_content


def main():
    """Main entry point for the CLI tool."""
    parser = argparse.ArgumentParser(
        description="gst-dots-viewer: GStreamer Pipeline Visualization Tool",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Visualize from existing DOT files
  python gst_dots_viewer.py --input /tmp/gst_dots --output ./visualizations

  # Create sample diagram (no GStreamer needed)
  python gst_dots_viewer.py --sample --output ./visualizations

  # Live capture from camera pipeline
  python gst_dots_viewer.py --live --camera 0 --duration 5

  # Visualize a pipeline string
  python gst_dots_viewer.py --pipeline "videotestsrc ! autovideosink"
        """
    )

    parser.add_argument('--input', '-i', type=str, help='Input directory containing DOT files')
    parser.add_argument('--output', '-o', type=str, default='./gst_visualizations',
                        help='Output directory for visualizations')
    parser.add_argument('--sample', action='store_true', help='Generate sample pipeline diagram')
    parser.add_argument('--live', action='store_true', help='Live capture from running pipeline')
    parser.add_argument('--camera', type=int, default=0, help='Camera ID for live capture')
    parser.add_argument('--duration', type=float, default=5.0, help='Duration for live capture (seconds)')
    parser.add_argument('--pipeline', '-p', type=str, help='GStreamer pipeline string to visualize')
    parser.add_argument('--verbose', '-v', action='store_true', help='Enable verbose output')
    parser.add_argument('--open', action='store_true', help='Open the HTML viewer after generation')

    args = parser.parse_args()

    viewer = GstDotsViewer(output_dir=args.output, verbose=args.verbose)

    results = {}

    if args.sample:
        # Generate multiple sample diagrams
        print("Generating sample pipeline diagrams...")

        diagrams = [
            ("pipeline_simple", create_sample_pipeline_diagram()),
            ("pipeline_detailed", create_detailed_yolo_pipeline_diagram()),
            ("architecture", create_architecture_diagram()),
        ]

        dot_files = []
        for name, dot_content in diagrams:
            dot_path = Path(args.output) / f"{name}.dot"
            dot_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dot_path, 'w') as f:
                f.write(dot_content)
            dot_files.append(str(dot_path))

            # Try to convert to images
            viewer.convert_dot_to_image(str(dot_path), "png")
            viewer.convert_dot_to_image(str(dot_path), "svg")

            print(f"  Created: {name}.dot")

        # Generate combined HTML viewer
        html_path = viewer.generate_html_viewer(dot_files, "gstreamer_pipeline_viewer")

        results = {
            'dot_files': dot_files,
            'html': html_path
        }

        print(f"\nGenerated HTML viewer: {html_path}")
        print("\nOpen the HTML file in a browser to view interactive pipeline diagrams!")

    elif args.input:
        # Visualize from existing DOT files
        print(f"Processing DOT files from: {args.input}")
        results = viewer.visualize_from_dot_dir(args.input)

        print(f"\nGenerated {len(results.get('images', []))} images")
        if results.get('html_viewer'):
            print(f"HTML viewer: {results['html_viewer']}")

    elif args.live:
        # Live capture
        print(f"Starting live capture from camera {args.camera}...")
        live_viz = LivePipelineVisualizer(viewer)
        results = live_viz.visualize_yolo_pipeline(args.camera, args.duration)

        print(f"\nCaptured {len(results)} pipeline states")
        if results.get('html_viewer'):
            print(f"HTML viewer: {results['html_viewer']}")

    elif args.pipeline:
        # Visualize pipeline string
        print(f"Visualizing pipeline: {args.pipeline[:50]}...")
        results = viewer.visualize_pipeline_string(args.pipeline)

        if results.get('html_viewer'):
            print(f"HTML viewer: {results['html_viewer']}")

    else:
        # Default: generate all sample diagrams
        print("No input specified. Generating pipeline visualization diagrams...")
        print("Use --help for more options.\n")

        diagrams = [
            ("pipeline_simple", create_sample_pipeline_diagram()),
            ("pipeline_detailed", create_detailed_yolo_pipeline_diagram()),
            ("architecture", create_architecture_diagram()),
        ]

        dot_files = []
        for name, dot_content in diagrams:
            dot_path = Path(args.output) / f"{name}.dot"
            dot_path.parent.mkdir(parents=True, exist_ok=True)
            with open(dot_path, 'w') as f:
                f.write(dot_content)
            dot_files.append(str(dot_path))
            print(f"  Created: {name}.dot")

        html_path = viewer.generate_html_viewer(dot_files, "gstreamer_pipeline_viewer")
        results = {'html': html_path}

        print(f"\n  HTML viewer: {html_path}")
        print("\nOpen the HTML file in a browser to view interactive pipeline diagrams!")

    # Open in browser if requested
    if args.open and results.get('html_viewer'):
        import webbrowser
        webbrowser.open(f"file://{Path(results['html_viewer']).absolute()}")
    elif args.open and results.get('html'):
        import webbrowser
        webbrowser.open(f"file://{Path(results['html']).absolute()}")

    # Cleanup
    viewer.cleanup()

    return 0


if __name__ == "__main__":
    sys.exit(main())
