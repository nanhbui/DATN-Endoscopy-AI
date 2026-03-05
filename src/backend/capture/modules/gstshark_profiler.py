
import os
import re
import subprocess
import time
import psutil
import json
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any
from datetime import datetime
from collections import defaultdict
import threading


class GstSharkProfiler:
    """
    GstShark performance profiler for GStreamer pipelines.

    Provides real-time monitoring of:
    - Processing time per element
    - FPS and frame drops
    - CPU/Memory usage
    - Latency through pipeline
    - Buffer statistics
    """

    def __init__(
        self,
        output_dir: str = "./gstshark_logs",
        enable_tracers: Optional[List[str]] = None,
        auto_start: bool = True
    ):
        """
        Initialize GstShark profiler.

        Args:
            output_dir: Directory to store performance logs
            enable_tracers: List of GstShark tracers to enable
                           (None = use defaults)
            auto_start: Automatically start profiling on initialization
        """
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Default tracers if not specified
        if enable_tracers is None:
            self.tracers = [
                "framerate",      # FPS measurement
                "proctime",       # Processing time per element
                "interlatency",   # Latency between elements
                "cpuusage",       # CPU usage per element
                "scheduling",     # Thread scheduling
                "graphic",        # Generate performance graphs
                "bitrate"         # Data throughput
            ]
        else:
            self.tracers = enable_tracers

        # Session tracking
        self.session_id = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.session_dir = self.output_dir / self.session_id
        self.session_dir.mkdir(exist_ok=True)

        # Performance data storage
        self.metrics = {
            "fps": [],
            "latency": [],
            "cpu_usage": [],
            "processing_time": {},
            "buffer_stats": [],
            "frame_drops": 0
        }

        # Monitoring thread
        self.monitoring_thread = None
        self.monitoring_active = False
        self.pipeline_pid = None

        # CPU/Memory monitoring
        self.process = None
        self.baseline_cpu = psutil.cpu_percent(interval=1)
        self.baseline_memory = psutil.virtual_memory().percent

        print(f"[GstShark] Initialized profiler")
        print(f"[GstShark] Session ID: {self.session_id}")
        print(f"[GstShark] Output directory: {self.session_dir}")
        print(f"[GstShark] Enabled tracers: {', '.join(self.tracers)}")

        if auto_start:
            self.start_profiling()

    def start_profiling(self) -> None:
        """
        Start GstShark profiling by setting environment variables.
        """
        # Set GstShark environment variables
        os.environ["GST_DEBUG"] = "GST_TRACER:7"
        os.environ["GST_TRACERS"] = ";".join(self.tracers)
        os.environ["GST_DEBUG_FILE"] = str(self.session_dir / "gst_debug.log")

        # Individual tracer outputs
        os.environ["GST_SHARK_LOCATION"] = str(self.session_dir)
        os.environ["GST_SHARK_FILE_PREFIX"] = f"gstshark_{self.session_id}"

        print(f"[GstShark] Profiling started")
        print(f"[GstShark] Debug log: {os.environ['GST_DEBUG_FILE']}")

    def stop_profiling(self) -> None:
        """
        Stop GstShark profiling and generate reports.
        """
        # Unset environment variables
        for key in ["GST_DEBUG", "GST_TRACERS", "GST_DEBUG_FILE",
                    "GST_SHARK_LOCATION", "GST_SHARK_FILE_PREFIX"]:
            if key in os.environ:
                del os.environ[key]

        print(f"[GstShark] Profiling stopped")

        # Generate reports
        self.generate_report()

    def attach_to_pipeline(self, pipeline_pid: int) -> None:
        """
        Attach profiler to a running GStreamer pipeline process.

        Args:
            pipeline_pid: Process ID of the GStreamer pipeline
        """
        try:
            self.pipeline_pid = pipeline_pid
            self.process = psutil.Process(pipeline_pid)
            print(f"[GstShark] Attached to pipeline PID: {pipeline_pid}")

            # Start monitoring thread
            self.start_monitoring()

        except psutil.NoSuchProcess:
            print(f"[ERROR] Process {pipeline_pid} not found")

    def start_monitoring(self) -> None:
        """
        Start background thread for real-time monitoring.
        """
        if self.monitoring_thread is not None:
            print("[WARN] Monitoring already active")
            return

        self.monitoring_active = True
        self.monitoring_thread = threading.Thread(
            target=self._monitor_loop,
            daemon=True
        )
        self.monitoring_thread.start()
        print("[GstShark] Real-time monitoring started")

    def stop_monitoring(self) -> None:
        """
        Stop background monitoring thread.
        """
        self.monitoring_active = False
        if self.monitoring_thread:
            self.monitoring_thread.join(timeout=2.0)
            self.monitoring_thread = None
        print("[GstShark] Real-time monitoring stopped")

    def _monitor_loop(self) -> None:
        """
        Background monitoring loop (runs in separate thread).
        """
        sample_interval = 0.5  # 500ms
        last_sample_time = time.time()

        while self.monitoring_active:
            current_time = time.time()

            if current_time - last_sample_time >= sample_interval:
                self._collect_metrics()
                last_sample_time = current_time

            time.sleep(0.1)  # Sleep briefly to avoid busy-waiting

    def _collect_metrics(self) -> None:
        """
        Collect current performance metrics.
        """
        if self.process is None:
            return

        try:
            # CPU usage
            cpu_percent = self.process.cpu_percent(interval=0.1)
            self.metrics["cpu_usage"].append({
                "timestamp": time.time(),
                "cpu_percent": cpu_percent,
                "num_threads": self.process.num_threads()
            })

            # Memory usage
            mem_info = self.process.memory_info()
            memory_mb = mem_info.rss / (1024 * 1024)

            # Store in buffer stats for now
            self.metrics["buffer_stats"].append({
                "timestamp": time.time(),
                "memory_mb": memory_mb,
                "cpu_percent": cpu_percent
            })

        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

    def parse_framerate_log(self) -> Dict[str, Any]:
        """
        Parse GstShark framerate tracer output.

        Returns:
            Dictionary with FPS statistics
        """
        framerate_file = self.session_dir / f"gstshark_{self.session_id}_framerate.log"

        if not framerate_file.exists():
            return {"avg_fps": 0, "samples": []}

        fps_samples = []

        try:
            with open(framerate_file, 'r') as f:
                for line in f:
                    # Parse format: "element_name fps=XX.XX"
                    match = re.search(r'fps=([0-9.]+)', line)
                    if match:
                        fps = float(match.group(1))
                        fps_samples.append(fps)

            avg_fps = sum(fps_samples) / len(fps_samples) if fps_samples else 0

            return {
                "avg_fps": avg_fps,
                "min_fps": min(fps_samples) if fps_samples else 0,
                "max_fps": max(fps_samples) if fps_samples else 0,
                "samples": fps_samples,
                "sample_count": len(fps_samples)
            }

        except Exception as e:
            print(f"[ERROR] Failed to parse framerate log: {e}")
            return {"avg_fps": 0, "samples": []}

    def parse_proctime_log(self) -> Dict[str, Any]:
        """
        Parse GstShark processing time tracer output.

        Returns:
            Dictionary with processing time per element
        """
        proctime_file = self.session_dir / f"gstshark_{self.session_id}_proctime.log"

        if not proctime_file.exists():
            return {"elements": {}}

        element_times = defaultdict(list)

        try:
            with open(proctime_file, 'r') as f:
                for line in f:
                    # Parse format: "element_name time=XXXX ns"
                    match = re.search(r'(\w+).*?time=([0-9]+)', line)
                    if match:
                        element = match.group(1)
                        time_ns = int(match.group(2))
                        time_ms = time_ns / 1_000_000  # Convert to ms
                        element_times[element].append(time_ms)

            # Calculate statistics per element
            result = {"elements": {}}
            for element, times in element_times.items():
                result["elements"][element] = {
                    "avg_time_ms": sum(times) / len(times),
                    "min_time_ms": min(times),
                    "max_time_ms": max(times),
                    "total_time_ms": sum(times),
                    "sample_count": len(times)
                }

            return result

        except Exception as e:
            print(f"[ERROR] Failed to parse proctime log: {e}")
            return {"elements": {}}

    def parse_interlatency_log(self) -> Dict[str, Any]:
        """
        Parse GstShark interlatency tracer output.

        Returns:
            Dictionary with latency between elements
        """
        interlatency_file = self.session_dir / f"gstshark_{self.session_id}_interlatency.log"

        if not interlatency_file.exists():
            return {"latencies": {}}

        latencies = defaultdict(list)

        try:
            with open(interlatency_file, 'r') as f:
                for line in f:
                    # Parse format: "from_element->to_element time=XXXX ns"
                    match = re.search(r'(\w+)->(\w+).*?time=([0-9]+)', line)
                    if match:
                        from_elem = match.group(1)
                        to_elem = match.group(2)
                        time_ns = int(match.group(3))
                        time_ms = time_ns / 1_000_000

                        key = f"{from_elem}->{to_elem}"
                        latencies[key].append(time_ms)

            # Calculate statistics
            result = {"latencies": {}}
            for path, times in latencies.items():
                result["latencies"][path] = {
                    "avg_latency_ms": sum(times) / len(times),
                    "min_latency_ms": min(times),
                    "max_latency_ms": max(times),
                    "sample_count": len(times)
                }

            return result

        except Exception as e:
            print(f"[ERROR] Failed to parse interlatency log: {e}")
            return {"latencies": {}}

    def parse_cpuusage_log(self) -> Dict[str, Any]:
        """
        Parse GstShark CPU usage tracer output.

        Returns:
            Dictionary with CPU usage per element
        """
        cpuusage_file = self.session_dir / f"gstshark_{self.session_id}_cpuusage.log"

        if not cpuusage_file.exists():
            return {"elements": {}}

        element_cpu = defaultdict(list)

        try:
            with open(cpuusage_file, 'r') as f:
                for line in f:
                    # Parse format: "element_name cpu=XX.XX%"
                    match = re.search(r'(\w+).*?cpu=([0-9.]+)', line)
                    if match:
                        element = match.group(1)
                        cpu_percent = float(match.group(2))
                        element_cpu[element].append(cpu_percent)

            # Calculate statistics
            result = {"elements": {}}
            for element, cpu_values in element_cpu.items():
                result["elements"][element] = {
                    "avg_cpu_percent": sum(cpu_values) / len(cpu_values),
                    "max_cpu_percent": max(cpu_values),
                    "sample_count": len(cpu_values)
                }

            return result

        except Exception as e:
            print(f"[ERROR] Failed to parse cpuusage log: {e}")
            return {"elements": {}}

    def get_current_metrics(self) -> Dict[str, Any]:
        """
        Get current performance metrics snapshot.

        Returns:
            Dictionary with current metrics
        """
        metrics = {
            "timestamp": datetime.now().isoformat(),
            "session_id": self.session_id
        }

        # CPU usage
        if self.metrics["cpu_usage"]:
            recent_cpu = self.metrics["cpu_usage"][-10:]  # Last 10 samples
            metrics["cpu"] = {
                "current": recent_cpu[-1]["cpu_percent"] if recent_cpu else 0,
                "avg": sum(s["cpu_percent"] for s in recent_cpu) / len(recent_cpu) if recent_cpu else 0,
                "num_threads": recent_cpu[-1]["num_threads"] if recent_cpu else 0
            }

        # Memory usage
        if self.metrics["buffer_stats"]:
            recent_mem = self.metrics["buffer_stats"][-10:]
            metrics["memory"] = {
                "current_mb": recent_mem[-1]["memory_mb"] if recent_mem else 0,
                "avg_mb": sum(s["memory_mb"] for s in recent_mem) / len(recent_mem) if recent_mem else 0
            }

        return metrics

    def generate_report(self) -> Dict[str, Any]:
        """
        Generate comprehensive performance report.

        Returns:
            Dictionary with full performance analysis
        """
        print("[GstShark] Generating performance report...")

        report = {
            "session_id": self.session_id,
            "timestamp": datetime.now().isoformat(),
            "output_directory": str(self.session_dir),
            "tracers_used": self.tracers,
            "performance": {}
        }

        # Parse all tracer logs
        report["performance"]["framerate"] = self.parse_framerate_log()
        report["performance"]["processing_time"] = self.parse_proctime_log()
        report["performance"]["latency"] = self.parse_interlatency_log()
        report["performance"]["cpu_usage"] = self.parse_cpuusage_log()

        # Add collected metrics
        if self.metrics["cpu_usage"]:
            cpu_samples = [s["cpu_percent"] for s in self.metrics["cpu_usage"]]
            report["performance"]["overall_cpu"] = {
                "avg_percent": sum(cpu_samples) / len(cpu_samples),
                "max_percent": max(cpu_samples),
                "min_percent": min(cpu_samples),
                "sample_count": len(cpu_samples)
            }

        if self.metrics["buffer_stats"]:
            mem_samples = [s["memory_mb"] for s in self.metrics["buffer_stats"]]
            report["performance"]["overall_memory"] = {
                "avg_mb": sum(mem_samples) / len(mem_samples),
                "max_mb": max(mem_samples),
                "min_mb": min(mem_samples)
            }

        # Save report to JSON
        report_file = self.session_dir / "performance_report.json"
        with open(report_file, 'w') as f:
            json.dump(report, f, indent=2)

        print(f"[GstShark] Report saved to: {report_file}")

        # Print summary
        self._print_summary(report)

        return report

    def _print_summary(self, report: Dict[str, Any]) -> None:
        """
        Print performance summary to console.

        Args:
            report: Performance report dictionary
        """
        print("\n" + "="*70)
        print("GSTSHARK PERFORMANCE SUMMARY")
        print("="*70)

        # FPS
        fps_data = report["performance"].get("framerate", {})
        if fps_data.get("avg_fps"):
            print(f"\n📊 FRAMERATE:")
            print(f"   Average FPS: {fps_data['avg_fps']:.2f}")
            print(f"   Min FPS: {fps_data['min_fps']:.2f}")
            print(f"   Max FPS: {fps_data['max_fps']:.2f}")

        # Processing Time
        proctime_data = report["performance"].get("processing_time", {})
        if proctime_data.get("elements"):
            print(f"\n⏱️  PROCESSING TIME (Top 5 slowest elements):")
            elements = proctime_data["elements"]
            sorted_elements = sorted(
                elements.items(),
                key=lambda x: x[1]["avg_time_ms"],
                reverse=True
            )[:5]

            for elem, stats in sorted_elements:
                print(f"   {elem}: {stats['avg_time_ms']:.2f}ms avg "
                      f"(min: {stats['min_time_ms']:.2f}ms, max: {stats['max_time_ms']:.2f}ms)")

        # Latency
        latency_data = report["performance"].get("latency", {})
        if latency_data.get("latencies"):
            print(f"\n🔄 INTER-ELEMENT LATENCY:")
            for path, stats in list(latency_data["latencies"].items())[:5]:
                print(f"   {path}: {stats['avg_latency_ms']:.2f}ms avg")

        # CPU Usage
        cpu_data = report["performance"].get("overall_cpu", {})
        if cpu_data:
            print(f"\n💻 CPU USAGE:")
            print(f"   Average: {cpu_data['avg_percent']:.2f}%")
            print(f"   Peak: {cpu_data['max_percent']:.2f}%")

        # Memory
        mem_data = report["performance"].get("overall_memory", {})
        if mem_data:
            print(f"\n🧠 MEMORY USAGE:")
            print(f"   Average: {mem_data['avg_mb']:.2f} MB")
            print(f"   Peak: {mem_data['max_mb']:.2f} MB")

        print("\n" + "="*70)
        print(f"Full report: {self.session_dir / 'performance_report.json'}")
        print("="*70 + "\n")

    def __enter__(self):
        """Context manager entry."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit - cleanup."""
        self.stop_monitoring()
        self.stop_profiling()


# Utility function for quick profiling
def profile_gstreamer_pipeline(
    pipeline_pid: int,
    duration_seconds: int = 30,
    output_dir: str = "./gstshark_logs"
) -> Dict[str, Any]:
    """
    Profile a GStreamer pipeline for a specified duration.

    Args:
        pipeline_pid: Process ID of GStreamer pipeline
        duration_seconds: How long to profile (seconds)
        output_dir: Where to save logs

    Returns:
        Performance report dictionary
    """
    with GstSharkProfiler(output_dir=output_dir) as profiler:
        profiler.attach_to_pipeline(pipeline_pid)

        print(f"[GstShark] Profiling for {duration_seconds} seconds...")
        time.sleep(duration_seconds)

        return profiler.generate_report()
