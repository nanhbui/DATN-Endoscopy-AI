#!/usr/bin/env python3
"""
Benchmark: GPU vs CPU Performance for YOLO + GStreamer Pipeline
================================================================
So sánh hiệu năng xử lý YOLO trên GPU vs CPU
"""

import cv2
import numpy as np
import time
import sys
import argparse
from pathlib import Path

try:
    import torch
    TORCH_AVAILABLE = True
except ImportError:
    TORCH_AVAILABLE = False
    print("[WARNING] PyTorch not available")

try:
    from ultralytics import YOLO
    YOLO_AVAILABLE = True
except ImportError:
    YOLO_AVAILABLE = False
    print("[WARNING] Ultralytics YOLO not available")


def get_system_info():
    """Get system information"""
    print("\n" + "="*60)
    print("SYSTEM INFORMATION")
    print("="*60)
    
    if TORCH_AVAILABLE:
        print(f"PyTorch version: {torch.__version__}")
        print(f"CUDA available: {torch.cuda.is_available()}")
        if torch.cuda.is_available():
            print(f"CUDA version: {torch.version.cuda}")
            print(f"GPU: {torch.cuda.get_device_name(0)}")
            print(f"GPU Memory: {torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GB")
    else:
        print("PyTorch: Not available")
    
    # CPU info
    try:
        with open('/proc/cpuinfo', 'r') as f:
            for line in f:
                if 'model name' in line:
                    print(f"CPU: {line.split(':')[1].strip()}")
                    break
    except:
        pass
    
    print("="*60 + "\n")


def benchmark_yolo(model, device, num_frames=50, warmup=5, resolution=(1280, 720)):
    """
    Benchmark YOLO inference on specified device
    
    Args:
        model: YOLO model
        device: 'cuda' or 'cpu'
        num_frames: Number of frames to test
        warmup: Warmup frames (not counted)
        resolution: Frame resolution (width, height)
    
    Returns:
        Dictionary with benchmark results
    """
    width, height = resolution
    
    # Move model to device
    if device == 'cuda' and torch.cuda.is_available():
        model.to('cuda')
        device_name = torch.cuda.get_device_name(0)
    else:
        model.to('cpu')
        device_name = "CPU"
        device = 'cpu'
    
    print(f"\n{'='*50}")
    print(f"Benchmarking on: {device_name}")
    print(f"Resolution: {width}x{height}")
    print(f"Frames: {num_frames} (+ {warmup} warmup)")
    print('='*50)
    
    # Generate random test frames
    test_frames = [np.random.randint(0, 255, (height, width, 3), dtype=np.uint8) 
                   for _ in range(num_frames + warmup)]
    
    # Warmup
    print("Warming up...", end=" ", flush=True)
    for i in range(warmup):
        _ = model(test_frames[i], verbose=False)
    
    # Clear GPU cache if using CUDA
    if device == 'cuda':
        torch.cuda.synchronize()
        torch.cuda.empty_cache()
    
    print("Done!")
    
    # Benchmark
    latencies = []
    detection_counts = []
    
    print("Running benchmark...")
    start_total = time.perf_counter()
    
    for i in range(num_frames):
        frame = test_frames[warmup + i]
        
        # Sync GPU before timing
        if device == 'cuda':
            torch.cuda.synchronize()
        
        start = time.perf_counter()
        results = model(frame, verbose=False)
        
        # Sync GPU after inference
        if device == 'cuda':
            torch.cuda.synchronize()
        
        elapsed = (time.perf_counter() - start) * 1000  # ms
        latencies.append(elapsed)
        
        # Count detections
        num_det = len(results[0].boxes) if results[0].boxes is not None else 0
        detection_counts.append(num_det)
        
        # Progress
        if (i + 1) % 10 == 0:
            print(f"  Frame {i+1}/{num_frames}: {elapsed:.2f}ms")
    
    total_time = time.perf_counter() - start_total
    
    # Calculate statistics
    latencies = np.array(latencies)
    
    results = {
        'device': device,
        'device_name': device_name,
        'resolution': f"{width}x{height}",
        'num_frames': num_frames,
        'total_time_s': total_time,
        'avg_latency_ms': np.mean(latencies),
        'std_latency_ms': np.std(latencies),
        'min_latency_ms': np.min(latencies),
        'max_latency_ms': np.max(latencies),
        'p50_latency_ms': np.percentile(latencies, 50),
        'p95_latency_ms': np.percentile(latencies, 95),
        'p99_latency_ms': np.percentile(latencies, 99),
        'fps': num_frames / total_time,
        'avg_detections': np.mean(detection_counts),
    }
    
    return results


def benchmark_with_gstreamer(model, device, num_frames=50, warmup=5, camera_id=0):
    """
    Benchmark YOLO with real GStreamer camera input
    """
    # Try to open camera with GStreamer
    gst_pipeline = (
        f"v4l2src device=/dev/video{camera_id} ! "
        f"image/jpeg, width=1280, height=720, framerate=30/1 ! "
        "jpegdec ! videoconvert ! appsink"
    )
    
    cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
    
    if not cap.isOpened():
        print(f"[WARNING] GStreamer pipeline failed, trying V4L2...")
        cap = cv2.VideoCapture(camera_id, cv2.CAP_V4L2)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 1280)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 720)
    
    if not cap.isOpened():
        print("[ERROR] Cannot open camera!")
        return None
    
    # Get actual resolution
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Move model to device
    if device == 'cuda' and torch.cuda.is_available():
        model.to('cuda')
        device_name = torch.cuda.get_device_name(0)
    else:
        model.to('cpu')
        device_name = "CPU"
        device = 'cpu'
    
    print(f"\n{'='*50}")
    print(f"GStreamer + YOLO Benchmark on: {device_name}")
    print(f"Camera Resolution: {width}x{height}")
    print(f"Frames: {num_frames} (+ {warmup} warmup)")
    print('='*50)
    
    # Warmup
    print("Warming up...", end=" ", flush=True)
    for i in range(warmup):
        ret, frame = cap.read()
        if ret:
            _ = model(frame, verbose=False)
    
    if device == 'cuda':
        torch.cuda.synchronize()
    print("Done!")
    
    # Benchmark
    latencies = []
    capture_times = []
    inference_times = []
    
    print("Running benchmark...")
    start_total = time.perf_counter()
    
    for i in range(num_frames):
        # Measure capture time
        cap_start = time.perf_counter()
        ret, frame = cap.read()
        cap_time = (time.perf_counter() - cap_start) * 1000
        
        if not ret:
            print(f"[WARNING] Failed to read frame {i}")
            continue
        
        capture_times.append(cap_time)
        
        # Sync GPU before timing
        if device == 'cuda':
            torch.cuda.synchronize()
        
        # Measure inference time
        inf_start = time.perf_counter()
        results = model(frame, verbose=False)
        
        if device == 'cuda':
            torch.cuda.synchronize()
        
        inf_time = (time.perf_counter() - inf_start) * 1000
        inference_times.append(inf_time)
        
        # Total latency
        latencies.append(cap_time + inf_time)
        
        if (i + 1) % 10 == 0:
            print(f"  Frame {i+1}/{num_frames}: capture={cap_time:.1f}ms, inference={inf_time:.1f}ms")
    
    total_time = time.perf_counter() - start_total
    cap.release()
    
    # Calculate statistics
    results = {
        'device': device,
        'device_name': device_name,
        'resolution': f"{width}x{height}",
        'num_frames': len(latencies),
        'total_time_s': total_time,
        'avg_capture_ms': np.mean(capture_times),
        'avg_inference_ms': np.mean(inference_times),
        'avg_total_ms': np.mean(latencies),
        'min_latency_ms': np.min(latencies),
        'max_latency_ms': np.max(latencies),
        'fps': len(latencies) / total_time,
    }
    
    return results


def print_comparison(cpu_results, gpu_results):
    """Print comparison table"""
    print("\n" + "="*70)
    print("📊 BENCHMARK COMPARISON: GPU vs CPU")
    print("="*70)
    
    if gpu_results is None:
        print("[WARNING] GPU benchmark not available")
        gpu_results = {k: 'N/A' for k in cpu_results.keys()}
    
    # Header
    print(f"{'Metric':<30} {'CPU':>15} {'GPU':>15} {'Speedup':>10}")
    print("-"*70)
    
    metrics = [
        ('Average Latency (ms)', 'avg_latency_ms'),
        ('Std Dev (ms)', 'std_latency_ms'),
        ('Min Latency (ms)', 'min_latency_ms'),
        ('Max Latency (ms)', 'max_latency_ms'),
        ('P50 Latency (ms)', 'p50_latency_ms'),
        ('P95 Latency (ms)', 'p95_latency_ms'),
        ('P99 Latency (ms)', 'p99_latency_ms'),
        ('FPS', 'fps'),
    ]
    
    for name, key in metrics:
        cpu_val = cpu_results.get(key, 'N/A')
        gpu_val = gpu_results.get(key, 'N/A')
        
        if isinstance(cpu_val, (int, float)) and isinstance(gpu_val, (int, float)):
            if 'Latency' in name or 'Std' in name:
                # Lower is better for latency
                speedup = cpu_val / gpu_val if gpu_val > 0 else 0
                speedup_str = f"{speedup:.1f}x ⚡" if speedup > 1 else f"{speedup:.1f}x"
            else:
                # Higher is better for FPS
                speedup = gpu_val / cpu_val if cpu_val > 0 else 0
                speedup_str = f"{speedup:.1f}x ⚡" if speedup > 1 else f"{speedup:.1f}x"
            
            print(f"{name:<30} {cpu_val:>15.2f} {gpu_val:>15.2f} {speedup_str:>10}")
        else:
            print(f"{name:<30} {str(cpu_val):>15} {str(gpu_val):>15} {'N/A':>10}")
    
    print("-"*70)
    
    # Summary
    if isinstance(cpu_results.get('fps'), (int, float)) and isinstance(gpu_results.get('fps'), (int, float)):
        speedup = gpu_results['fps'] / cpu_results['fps']
        print(f"\n🚀 GPU is {speedup:.1f}x FASTER than CPU!")
        print(f"   CPU: {cpu_results['fps']:.1f} FPS ({cpu_results['avg_latency_ms']:.1f}ms/frame)")
        print(f"   GPU: {gpu_results['fps']:.1f} FPS ({gpu_results['avg_latency_ms']:.1f}ms/frame)")
        
        # Real-time capability
        print(f"\n📹 Real-time capability (30 FPS target):")
        cpu_realtime = "✅ YES" if cpu_results['fps'] >= 30 else "❌ NO"
        gpu_realtime = "✅ YES" if gpu_results['fps'] >= 30 else "❌ NO"
        print(f"   CPU: {cpu_realtime} ({cpu_results['fps']:.1f} FPS)")
        print(f"   GPU: {gpu_realtime} ({gpu_results['fps']:.1f} FPS)")


def main():
    parser = argparse.ArgumentParser(description="Benchmark GPU vs CPU for YOLO + GStreamer")
    parser.add_argument("--frames", type=int, default=50, help="Number of frames to benchmark")
    parser.add_argument("--warmup", type=int, default=5, help="Warmup frames")
    parser.add_argument("--model", default="yolov8n-seg.pt", help="YOLO model path")
    parser.add_argument("--width", type=int, default=1280, help="Frame width")
    parser.add_argument("--height", type=int, default=720, help="Frame height")
    parser.add_argument("--camera", type=int, default=-1, help="Camera ID (-1 for synthetic frames)")
    parser.add_argument("--cpu-only", action="store_true", help="Only test CPU")
    parser.add_argument("--gpu-only", action="store_true", help="Only test GPU")
    
    args = parser.parse_args()
    
    # Print system info
    get_system_info()
    
    if not YOLO_AVAILABLE:
        print("[ERROR] YOLO not available. Install with: pip install ultralytics")
        sys.exit(1)
    
    # Load model
    print(f"Loading YOLO model: {args.model}")
    model_path = Path(args.model)
    
    if not model_path.exists():
        # Try in models directory
        alt_path = Path("models") / args.model
        if alt_path.exists():
            model_path = alt_path
        else:
            print(f"[WARNING] Model not found at {args.model}, downloading...")
    
    model = YOLO(str(model_path))
    print(f"Model loaded: {model_path}")
    
    resolution = (args.width, args.height)
    
    # Benchmark based on mode
    cpu_results = None
    gpu_results = None
    
    if args.camera >= 0:
        # Real camera benchmark
        print("\n📹 Using real camera input with GStreamer")
        
        if not args.gpu_only:
            print("\n--- CPU Benchmark ---")
            cpu_results = benchmark_with_gstreamer(model, 'cpu', args.frames, args.warmup, args.camera)
        
        if not args.cpu_only and torch.cuda.is_available():
            print("\n--- GPU Benchmark ---")
            gpu_results = benchmark_with_gstreamer(model, 'cuda', args.frames, args.warmup, args.camera)
    else:
        # Synthetic frames benchmark
        print("\n🎲 Using synthetic frames (no camera)")
        
        if not args.gpu_only:
            print("\n--- CPU Benchmark ---")
            cpu_results = benchmark_yolo(model, 'cpu', args.frames, args.warmup, resolution)
        
        if not args.cpu_only and torch.cuda.is_available():
            print("\n--- GPU Benchmark ---")
            gpu_results = benchmark_yolo(model, 'cuda', args.frames, args.warmup, resolution)
        elif not args.cpu_only:
            print("\n[WARNING] CUDA not available, skipping GPU benchmark")
    
    # Print comparison
    if cpu_results and gpu_results:
        print_comparison(cpu_results, gpu_results)
    elif cpu_results:
        print("\n📊 CPU Results:")
        for k, v in cpu_results.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.2f}")
            else:
                print(f"  {k}: {v}")
    elif gpu_results:
        print("\n📊 GPU Results:")
        for k, v in gpu_results.items():
            if isinstance(v, float):
                print(f"  {k}: {v:.2f}")
            else:
                print(f"  {k}: {v}")
    
    print("\n" + "="*70)
    print("Benchmark complete!")
    print("="*70)


if __name__ == "__main__":
    main()
