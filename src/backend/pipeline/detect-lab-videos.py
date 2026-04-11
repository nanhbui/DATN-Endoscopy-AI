#!/usr/bin/env python3
"""Batch detection on lab endoscopy videos.

Usage: python3 detect-lab-videos.py
Reads videos from data/lab/, runs daday.pt, logs detections.
"""

from pathlib import Path
import cv2
import time

_REPO = Path(__file__).resolve().parents[3]
MODEL_PATH = _REPO / "sample_code/endocv_2024/model_yolo/daday.pt"
LAB_DIR = _REPO / "data/lab"
CONF = 0.50
SKIP_FRAMES = 5   # process every Nth frame to speed up


def infer_location(bbox: list, frame_shape: tuple) -> str:
    cy = (bbox[1] + bbox[3]) / 2 / frame_shape[0]
    if cy < 0.33:
        return "Thân vị (corpus)"
    elif cy < 0.66:
        return "Hang vị (antrum)"
    return "Môn vị (pylorus)"


def run(video_path: Path, model) -> list[dict]:
    cap = cv2.VideoCapture(str(video_path))
    if not cap.isOpened():
        print(f"  [WARN] Cannot open {video_path.name}")
        return []

    fps = cap.get(cv2.CAP_PROP_FPS) or 30
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    duration_s = total / fps
    print(f"  {total} frames @ {fps:.0f}fps  ({duration_s:.1f}s)")

    detections = []
    frame_idx = 0
    last_label = None   # suppress consecutive duplicate detections

    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                break

            if frame_idx % SKIP_FRAMES != 0:
                frame_idx += 1
                continue

            results = model(frame, conf=CONF, verbose=False)
            for result in results:
                if result.boxes is None or len(result.boxes) == 0:
                    continue
                for box in result.boxes:
                    if box.conf is None or box.conf.shape[0] == 0:
                        continue
                    conf = float(box.conf[0])
                    cls_id = int(box.cls[0])
                    label = (model.names or {}).get(cls_id, f"class_{cls_id}")
                    xyxy = box.xyxy[0].tolist()
                    ts = frame_idx / fps
                    location = infer_location(xyxy, frame.shape)

                    # Print every detection, but mark if same label persists
                    repeat = " (tiếp)" if label == last_label else ""
                    print(f"  [{ts:6.1f}s | frame {frame_idx:5d}] "
                          f"{label}  conf={conf:.3f}  @ {location}{repeat}")

                    detections.append({
                        "frame": frame_idx,
                        "ts": round(ts, 1),
                        "label": label,
                        "conf": round(conf, 3),
                        "location": location,
                    })
                    last_label = label
                    break   # one detection per frame

            frame_idx += 1
    finally:
        cap.release()

    return detections


def main():
    from ultralytics import YOLO

    print(f"Loading model: {MODEL_PATH}")
    model = YOLO(str(MODEL_PATH))
    print(f"Classes: {model.names}\n")

    videos = sorted(LAB_DIR.glob("*.mp4"))
    if not videos:
        print(f"No mp4 files found in {LAB_DIR}")
        return

    summary = {}
    t_start = time.time()

    for video in videos:
        print(f"\n{'='*60}")
        print(f"Video: {video.name}")
        dets = run(video, model)
        summary[video.name] = dets

    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    total_det = 0
    for vname, dets in summary.items():
        print(f"\n{vname}:")
        if not dets:
            print("  — Không phát hiện tổn thương")
            continue
        by_label: dict[str, list] = {}
        for d in dets:
            by_label.setdefault(d["label"], []).append(d)
        for label, items in by_label.items():
            confs = [x["conf"] for x in items]
            locs = list(dict.fromkeys(x["location"] for x in items))
            print(f"  {label}: {len(items)} lần  conf={min(confs):.2f}-{max(confs):.2f}  "
                  f"vị trí: {', '.join(locs)}")
        total_det += len(dets)

    elapsed = time.time() - t_start
    print(f"\nTotal detections (every {SKIP_FRAMES} frames): {total_det}  |  time: {elapsed:.1f}s")


if __name__ == "__main__":
    main()
