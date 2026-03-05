#!/usr/bin/env python3
"""
GPU Server - Receive UDP stream and run YOLO inference
Receives video stream from local machine and processes with GPU YOLO
"""

import cv2
import numpy as np
import time
import argparse
from ultralytics import YOLO


def create_udp_receiver(port: int = 5000) -> cv2.VideoCapture:
    """Create GStreamer pipeline to receive UDP stream"""
    gst_pipeline = (
        f"udpsrc port={port} ! "
        "application/x-rtp,media=video,encoding-name=H264,payload=96 ! "
        "rtph264depay ! "
        "h264parse ! "
        "avdec_h264 ! "
        "videoconvert ! "
        "video/x-raw,format=BGR ! "
        "appsink drop=1"
    )
    
    print(f"[INFO] Starting UDP receiver on port {port}")
    print(f"[INFO] Pipeline: {gst_pipeline}")
    
    cap = cv2.VideoCapture(gst_pipeline, cv2.CAP_GSTREAMER)
    return cap


def main():
    parser = argparse.ArgumentParser(description="GPU YOLO Server - Receive stream and process")
    parser.add_argument("--port", type=int, default=5000, help="UDP port to receive stream")
    parser.add_argument("--model", default="yolov8n-seg.pt", help="YOLO model path")
    parser.add_argument("--conf", type=float, default=0.25, help="Confidence threshold")
    parser.add_argument("--save-video", action="store_true", help="Save processed video")
    parser.add_argument("--headless", action="store_true", help="Run without display")
    args = parser.parse_args()

    print("=" * 60)
    print("GPU YOLO SERVER - Receiving stream from local camera")
    print("=" * 60)

    # Load YOLO model on GPU
    print(f"[INFO] Loading YOLO model: {args.model}")
    model = YOLO(args.model)
    
    # Warmup
    dummy = np.zeros((720, 1280, 3), dtype=np.uint8)
    for _ in range(3):
        model(dummy, verbose=False)
    print("[SUCCESS] YOLO model warmed up on GPU!")

    # Create UDP receiver
    cap = create_udp_receiver(args.port)
    
    if not cap.isOpened():
        print("[ERROR] Failed to open UDP receiver!")
        print("[HINT] Make sure the local machine is streaming:")
        print("       ./stream_to_server.sh 0 10.8.0.7")
        return

    print("[SUCCESS] UDP receiver ready! Waiting for stream...")

    # Video writer for saving
    writer = None
    if args.save_video:
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter('output_gpu.mp4', fourcc, 30, (1280, 720))

    # FPS counter
    fps_start = time.time()
    frame_count = 0
    fps = 0

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                print("[WARN] No frame received, waiting...")
                time.sleep(0.1)
                continue

            # Run YOLO inference
            results = model.track(
                frame,
                persist=True,
                tracker="bytetrack.yaml",
                conf=args.conf,
                verbose=False
            )[0]

            # Draw results on frame
            annotated = results.plot()

            # FPS calculation
            frame_count += 1
            if frame_count % 30 == 0:
                fps = 30 / (time.time() - fps_start)
                fps_start = time.time()

            # Add FPS overlay
            cv2.putText(annotated, f"GPU FPS: {fps:.1f}", (10, 30),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
            
            # Detection count
            num_det = len(results.boxes) if results.boxes else 0
            cv2.putText(annotated, f"Detections: {num_det}", (10, 70),
                       cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)

            # Save video
            if writer:
                writer.write(annotated)

            # Display (unless headless)
            if not args.headless:
                cv2.imshow("GPU YOLO Server", annotated)
                key = cv2.waitKey(1) & 0xFF
                if key == ord('q'):
                    break
            else:
                # Print status periodically
                if frame_count % 100 == 0:
                    print(f"[INFO] Processed {frame_count} frames, FPS: {fps:.1f}, Detections: {num_det}")

    except KeyboardInterrupt:
        print("\n[INFO] Stopping...")

    finally:
        cap.release()
        if writer:
            writer.release()
        cv2.destroyAllWindows()
        print(f"[INFO] Total frames processed: {frame_count}")


if __name__ == "__main__":
    main()
