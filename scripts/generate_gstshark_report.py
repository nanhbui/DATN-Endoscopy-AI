#!/usr/bin/env python3
"""
Generate GstShark performance report from logs
"""
import os
import sys
import json
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any
import re

class GstSharkReportGenerator:
    """Generate performance reports from GstShark logs"""

    def __init__(self, log_dir: str = "gstshark_logs"):
        self.log_dir = Path(log_dir)
        self.report = {
            "timestamp": datetime.now().isoformat(),
            "summary": {},
            "details": {}
        }

    def parse_framerate_log(self) -> Dict[str, Any]:
        """Parse framerate tracer logs"""
        log_file = self.log_dir / "framerate.log"
        if not log_file.exists():
            return {}

        fps_data = {}
        with open(log_file) as f:
            for line in f:
                # Format: framerate,element=yoloinference,fps=12.5
                match = re.search(r'element=(\w+),fps=([\d.]+)', line)
                if match:
                    element, fps = match.groups()
                    if element not in fps_data:
                        fps_data[element] = []
                    fps_data[element].append(float(fps))

        # Calculate averages
        summary = {}
        for element, fps_list in fps_data.items():
            if fps_list:
                summary[element] = {
                    "avg_fps": sum(fps_list) / len(fps_list),
                    "min_fps": min(fps_list),
                    "max_fps": max(fps_list),
                    "samples": len(fps_list)
                }

        return summary

    def parse_proctime_log(self) -> Dict[str, Any]:
        """Parse processing time tracer logs"""
        log_file = self.log_dir / "proctime.log"
        if not log_file.exists():
            return {}

        time_data = {}
        with open(log_file) as f:
            for line in f:
                # Format: proctime,element=yoloinference,time=78.5ms
                match = re.search(r'element=(\w+),time=([\d.]+)', line)
                if match:
                    element, time_ms = match.groups()
                    if element not in time_data:
                        time_data[element] = []
                    time_data[element].append(float(time_ms))

        # Calculate averages
        summary = {}
        for element, times in time_data.items():
            if times:
                summary[element] = {
                    "avg_time_ms": sum(times) / len(times),
                    "min_time_ms": min(times),
                    "max_time_ms": max(times),
                    "samples": len(times)
                }

        return summary

    def parse_cpuusage_log(self) -> Dict[str, Any]:
        """Parse CPU usage tracer logs"""
        log_file = self.log_dir / "cpuusage.log"
        if not log_file.exists():
            return {}

        cpu_samples = []
        with open(log_file) as f:
            for line in f:
                # Format: cpuusage,process=capture_system,cpu=45.2%
                match = re.search(r'cpu=([\d.]+)', line)
                if match:
                    cpu_samples.append(float(match.group(1)))

        if cpu_samples:
            return {
                "avg_cpu_percent": sum(cpu_samples) / len(cpu_samples),
                "min_cpu_percent": min(cpu_samples),
                "max_cpu_percent": max(cpu_samples),
                "samples": len(cpu_samples)
            }
        return {}

    def parse_interlatency_log(self) -> Dict[str, Any]:
        """Parse interlatency tracer logs"""
        log_file = self.log_dir / "interlatency.log"
        if not log_file.exists():
            return {}

        latency_data = {}
        with open(log_file) as f:
            for line in f:
                # Format: interlatency,from=jpegdec,to=yoloinference,latency=2.1ms
                match = re.search(r'from=(\w+),to=(\w+),latency=([\d.]+)', line)
                if match:
                    from_el, to_el, latency = match.groups()
                    key = f"{from_el}→{to_el}"
                    if key not in latency_data:
                        latency_data[key] = []
                    latency_data[key].append(float(latency))

        # Calculate averages
        summary = {}
        for path, latencies in latency_data.items():
            if latencies:
                summary[path] = {
                    "avg_latency_ms": sum(latencies) / len(latencies),
                    "min_latency_ms": min(latencies),
                    "max_latency_ms": max(latencies),
                    "samples": len(latencies)
                }

        return summary

    def generate_report(self) -> Dict[str, Any]:
        """Generate complete performance report"""
        print("📊 Analyzing GstShark logs...")

        # Parse all logs
        framerate = self.parse_framerate_log()
        proctime = self.parse_proctime_log()
        cpuusage = self.parse_cpuusage_log()
        interlatency = self.parse_interlatency_log()

        # Build report
        self.report["details"] = {
            "framerate": framerate,
            "processing_time": proctime,
            "cpu_usage": cpuusage,
            "interlatency": interlatency
        }

        # Generate summary
        summary = []

        # FPS summary
        if framerate:
            yolo_fps = framerate.get("yoloinference", {})
            if yolo_fps:
                avg_fps = yolo_fps["avg_fps"]
                summary.append(f"🎯 Average FPS: {avg_fps:.1f}")
                self.report["summary"]["avg_fps"] = avg_fps

        # Processing time summary
        if proctime:
            yolo_time = proctime.get("yoloinference", {})
            if yolo_time:
                avg_time = yolo_time["avg_time_ms"]
                summary.append(f"⏱️  YOLO Inference: {avg_time:.1f}ms/frame")
                self.report["summary"]["yolo_time_ms"] = avg_time

        # CPU usage summary
        if cpuusage:
            avg_cpu = cpuusage["avg_cpu_percent"]
            summary.append(f"💻 CPU Usage: {avg_cpu:.1f}%")
            self.report["summary"]["cpu_percent"] = avg_cpu

        self.report["summary"]["text"] = "\n".join(summary)

        return self.report

    def save_report(self, output_file: str = None):
        """Save report to JSON file"""
        if output_file is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            output_file = self.log_dir / f"performance_report_{timestamp}.json"

        output_path = Path(output_file)
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, 'w') as f:
            json.dump(self.report, f, indent=2)

        return output_path

    def print_report(self):
        """Print human-readable report"""
        print("\n" + "="*60)
        print("📊 GSTSHARK PERFORMANCE REPORT")
        print("="*60)

        # Summary
        if self.report["summary"].get("text"):
            print("\n🎯 Summary:")
            print(self.report["summary"]["text"])

        # Framerate details
        framerate = self.report["details"].get("framerate", {})
        if framerate:
            print("\n📈 Framerate by Element:")
            for element, data in framerate.items():
                print(f"  • {element:20s} {data['avg_fps']:6.1f} FPS "
                      f"(min: {data['min_fps']:.1f}, max: {data['max_fps']:.1f})")

        # Processing time details
        proctime = self.report["details"].get("processing_time", {})
        if proctime:
            print("\n⏱️  Processing Time by Element:")
            for element, data in proctime.items():
                print(f"  • {element:20s} {data['avg_time_ms']:6.1f} ms "
                      f"(min: {data['min_time_ms']:.1f}, max: {data['max_time_ms']:.1f})")

        # CPU usage
        cpuusage = self.report["details"].get("cpu_usage", {})
        if cpuusage:
            print(f"\n💻 CPU Usage:")
            print(f"  • Average: {cpuusage['avg_cpu_percent']:.1f}%")
            print(f"  • Range: {cpuusage['min_cpu_percent']:.1f}% - {cpuusage['max_cpu_percent']:.1f}%")

        # Latency
        interlatency = self.report["details"].get("interlatency", {})
        if interlatency:
            print("\n🔗 Inter-Element Latency:")
            for path, data in interlatency.items():
                print(f"  • {path:30s} {data['avg_latency_ms']:6.1f} ms "
                      f"(min: {data['min_latency_ms']:.1f}, max: {data['max_latency_ms']:.1f})")

        print("\n" + "="*60)

def main():
    """Main entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Generate GstShark performance report")
    parser.add_argument("--log-dir", default="gstshark_logs",
                       help="Directory containing GstShark logs")
    parser.add_argument("--output", help="Output JSON file path")
    parser.add_argument("--quiet", action="store_true", help="Don't print report")

    args = parser.parse_args()

    # Check if log directory exists
    if not Path(args.log_dir).exists():
        print(f"❌ Log directory not found: {args.log_dir}")
        print("Run with --profile flag first to generate logs")
        return 1

    # Generate report
    generator = GstSharkReportGenerator(args.log_dir)
    report = generator.generate_report()

    # Save report
    output_path = generator.save_report(args.output)
    print(f"✅ Report saved to: {output_path}")

    # Print report
    if not args.quiet:
        generator.print_report()

    return 0

if __name__ == "__main__":
    sys.exit(main())
