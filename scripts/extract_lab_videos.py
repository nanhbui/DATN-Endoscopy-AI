"""
Extract frames từ LAB endoscopy videos.

Luồng:
  1. Đọc từng video trong data/lab/
  2. Sample 1 frame/giây (1fps)
  3. Lọc blur (Laplacian variance < threshold)
  4. Lưu vào data/lab_frames/<video_name>/frame_XXXXX.jpg
"""

import cv2
from pathlib import Path

VIDEO_DIR    = Path("data/lab")
OUTPUT_DIR   = Path("data/lab_frames")
SAMPLE_FPS   = 1        # 1 frame/giây
BLUR_THRESH  = 100.0    # Laplacian variance — dưới ngưỡng = ảnh mờ
JPEG_QUALITY = 95


def is_blurry(frame, threshold: float) -> bool:
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    return cv2.Laplacian(gray, cv2.CV_64F).var() < threshold


def extract_video(video_path: Path, out_dir: Path) -> dict:
    out_dir.mkdir(parents=True, exist_ok=True)
    cap = cv2.VideoCapture(str(video_path))

    fps      = cap.get(cv2.CAP_PROP_FPS)
    total    = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    interval = max(1, round(fps / SAMPLE_FPS))

    saved = skipped_blur = frame_idx = 0

    while True:
        ret, frame = cap.read()
        if not ret:
            break
        if frame_idx % interval == 0:
            if is_blurry(frame, BLUR_THRESH):
                skipped_blur += 1
            else:
                fname = out_dir / f"frame_{frame_idx:06d}.jpg"
                cv2.imwrite(str(fname), frame, [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY])
                saved += 1
        frame_idx += 1

    cap.release()
    return {"total": total, "saved": saved, "blur": skipped_blur}


def main():
    videos = sorted(VIDEO_DIR.glob("*.mp4")) + sorted(VIDEO_DIR.glob("*.avi"))
    if not videos:
        print(f"Không tìm thấy video trong {VIDEO_DIR}")
        return

    print(f"Tìm thấy {len(videos)} video\n")
    total_saved = 0

    for video_path in videos:
        out_dir = OUTPUT_DIR / video_path.stem
        print(f"Đang xử lý: {video_path.name} ...")
        stats = extract_video(video_path, out_dir)
        print(f"  Frames: {stats['total']} | Saved: {stats['saved']} | Blur bỏ qua: {stats['blur']}")
        total_saved += stats["saved"]

    print(f"\nTổng frames đã lưu: {total_saved}")
    print(f"Output: {OUTPUT_DIR.resolve()}")


if __name__ == "__main__":
    main()