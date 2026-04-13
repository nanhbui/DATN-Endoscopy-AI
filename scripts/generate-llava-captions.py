"""generate-llava-captions.py — Generate medical captions for endoscopy images using GPT-4o Vision.

Output: data/llava_dataset/metadata.jsonl
Format per line:
  {"image": "images/train/abc.jpg", "conversations": [
    {"from": "human", "value": "<image>\nMô tả tổn thương trong ảnh nội soi này."},
    {"from": "gpt",   "value": "Polyp dạng cuống (Ip), bề mặt đều..."}
  ]}

Usage:
  python scripts/generate-llava-captions.py --images data/hyperkvasir_yolo/images/train
  python scripts/generate-llava-captions.py --images data/hyperkvasir_yolo/images/train --limit 100
"""

from __future__ import annotations

import argparse
import base64
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[1] / "src/backend/api/.env")

# ── Config ────────────────────────────────────────────────────────────────────
PROMPT = (
    "Bạn là bác sĩ nội soi tiêu hóa. Phân tích ảnh nội soi sau và mô tả:\n"
    "1. Loại tổn thương (polyp, viêm loét, xuất huyết, bình thường...)\n"
    "2. Hình dạng và kích thước ước tính\n"
    "3. Phân loại Paris/NICE nếu là polyp\n"
    "4. Vị trí giải phẫu ước tính\n"
    "5. Đề xuất xử lý lâm sàng\n"
    "Trả lời bằng tiếng Việt, ngắn gọn, chuyên nghiệp."
)

HUMAN_QUESTION = "<image>\nMô tả và phân tích tổn thương trong ảnh nội soi này."

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".bmp"}


def encode_image(path: Path) -> str:
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def generate_caption(client: OpenAI, image_path: Path) -> str:
    b64 = encode_image(image_path)
    ext = image_path.suffix.lower().lstrip(".")
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

    response = client.chat.completions.create(
        model="gpt-4o-mini",  # dùng mini để tiết kiệm chi phí
        messages=[
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": PROMPT},
                    {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{b64}", "detail": "low"}},
                ],
            }
        ],
        max_tokens=300,
    )
    return response.choices[0].message.content.strip()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--images", required=True, help="Directory of images")
    parser.add_argument("--output", default="data/llava_dataset", help="Output directory")
    parser.add_argument("--limit", type=int, default=0, help="Max images (0 = all)")
    parser.add_argument("--delay", type=float, default=0.5, help="Delay between API calls (s)")
    args = parser.parse_args()

    client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])

    images_dir = Path(args.images)
    output_dir = Path(args.output)
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "images").mkdir(exist_ok=True)

    images = sorted([p for p in images_dir.rglob("*") if p.suffix.lower() in IMAGE_EXTS])
    if args.limit:
        images = images[: args.limit]

    print(f"Found {len(images)} images → generating captions...")

    out_file = output_dir / "metadata.jsonl"
    done = set()

    # Resume support — skip already processed
    if out_file.exists():
        with open(out_file) as f:
            for line in f:
                entry = json.loads(line)
                done.add(entry["image"])
        print(f"Resuming — {len(done)} already done")

    with open(out_file, "a") as f:
        for i, img_path in enumerate(images):
            rel = str(img_path.relative_to(images_dir.parent))
            if rel in done:
                continue

            try:
                caption = generate_caption(client, img_path)
                entry = {
                    "image": rel,
                    "conversations": [
                        {"from": "human", "value": HUMAN_QUESTION},
                        {"from": "gpt",   "value": caption},
                    ],
                }
                f.write(json.dumps(entry, ensure_ascii=False) + "\n")
                f.flush()
                print(f"[{i+1}/{len(images)}] {img_path.name}: {caption[:60]}...")
                time.sleep(args.delay)
            except Exception as e:
                print(f"  ERROR {img_path.name}: {e}")


if __name__ == "__main__":
    main()
