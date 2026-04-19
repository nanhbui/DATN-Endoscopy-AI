"""
Generate LLaVA-format instruction pairs from HyperKvasir using Gemini Flash.

Usage:
    pip install google-genai pillow
    export GEMINI_API_KEY=your_key_here
    python scripts/generate_gemini_captions.py

Output: data/llava_finetune/gemini_captions.json  (ShareGPT format)

Free tier: gemini-2.0-flash → 15 RPM, 1500 req/day → all 10662 images in ~12 hours
Resume-safe: skips images already processed (checkpoint every 50 images).
"""

import json
import os
import sys
import time
from pathlib import Path

from google import genai
from PIL import Image

# ── Config ────────────────────────────────────────────────────────────────────

IMAGE_ROOT = Path("data/raw/hyperkvasir_extracted/labeled-images")
OUTPUT_DIR = Path("data/llava_finetune")
OUTPUT_FILE = OUTPUT_DIR / "gemini_captions.json"

# gemini-2.0-flash: free tier, 15 RPM, 1500 req/day, excellent vision quality
# gemini-2.5-pro-preview-05-06: better quality but stricter quota
GEMINI_MODEL = "gemini-2.0-flash"
MAX_RPM = 14          # stay just under 15 RPM limit
RETRY_DELAYS = [15, 45, 90, 180]   # seconds to wait on 429/5xx

# ── Category descriptions for prompt enrichment ───────────────────────────────

CATEGORY_CONTEXT: dict[str, str] = {
    # Upper GI — anatomical
    "pylorus":              "the pylorus (gastric outlet valve between stomach and duodenum)",
    "retroflex-stomach":    "retroflex stomach view (scope turned back toward the cardia)",
    "z-line":               "the Z-line / squamocolumnar junction (esophago-gastric border)",
    # Upper GI — pathological
    "barretts":             "Barrett's esophagus (intestinal metaplasia of the esophageal mucosa)",
    "barretts-short-segment": "short-segment Barrett's esophagus (<3 cm intestinal metaplasia)",
    "esophagitis-a":        "Los Angeles grade A reflux esophagitis (erosions <5 mm)",
    "esophagitis-b-d":      "Los Angeles grade B–D reflux esophagitis (confluent or circumferential erosions)",
    # Lower GI — anatomical
    "cecum":                "the cecum (most proximal segment of the colon, with appendiceal orifice)",
    "ileum":                "the terminal ileum (seen through the ileocecal valve)",
    "retroflex-rectum":     "retroflex rectal view (scope turned back to inspect the anorectal junction)",
    # Lower GI — pathological
    "hemorrhoids":          "internal hemorrhoids (dilated submucosal veins in the rectum)",
    "polyps":               "colonic or gastric polyp (mucosal protrusion)",
    "ulcerative-colitis-grade-0-1": "ulcerative colitis grade 0–1 (near-normal or mild mucosal changes)",
    "ulcerative-colitis-grade-1":   "ulcerative colitis grade 1 (mild: erythema, decreased vascular pattern)",
    "ulcerative-colitis-grade-1-2": "ulcerative colitis grade 1–2 (mild-to-moderate inflammation)",
    "ulcerative-colitis-grade-2":   "ulcerative colitis grade 2 (moderate: marked erythema, erosions)",
    "ulcerative-colitis-grade-2-3": "ulcerative colitis grade 2–3 (moderate-to-severe inflammation)",
    "ulcerative-colitis-grade-3":   "ulcerative colitis grade 3 (severe: spontaneous bleeding, deep ulcers)",
    # Lower GI — quality
    "bbps-0-1":             "poor bowel preparation (Boston Bowel Preparation Scale 0–1)",
    "bbps-2-3":             "adequate bowel preparation (Boston Bowel Preparation Scale 2–3)",
    "impacted-stool":       "impacted stool obscuring mucosal view",
    # Lower GI — therapeutic
    "dyed-lifted-polyps":   "dyed and lifted polyp ready for endoscopic mucosal resection (EMR)",
    "dyed-resection-margins": "dyed resection margins after endoscopic polyp removal",
}


def build_prompt(category: str, region: str, finding_type: str) -> str:
    ctx = CATEGORY_CONTEXT.get(category, category.replace("-", " "))
    return (
        f"This is a gastrointestinal endoscopy image from the HyperKvasir dataset. "
        f"The image shows {ctx} (region: {region}, type: {finding_type}).\n\n"
        "Please generate a clinically accurate, detailed description of what you see in this image. "
        "Then generate 2 question-answer pairs that a medical student or AI assistant should be able to answer about this image. "
        "Return ONLY valid JSON in this exact format (no markdown, no explanation):\n"
        "{\n"
        '  "description": "...",\n'
        '  "qa_pairs": [\n'
        '    {"question": "...", "answer": "..."},\n'
        '    {"question": "...", "answer": "..."}\n'
        "  ]\n"
        "}"
    )


def call_gemini(client: genai.Client, image_path: Path, prompt: str) -> dict:
    img = Image.open(image_path)
    for attempt, delay in enumerate([0] + RETRY_DELAYS):
        if delay:
            print(f"    retry {attempt}/{len(RETRY_DELAYS)} in {delay}s...", flush=True)
            time.sleep(delay)
        try:
            response = client.models.generate_content(
                model=GEMINI_MODEL,
                contents=[prompt, img],
            )
            text = response.text.strip()
            # Strip markdown code fences if present
            if text.startswith("```"):
                text = text.split("```", 2)[1]
                if text.startswith("json"):
                    text = text[4:]
                text = text.strip()
            return json.loads(text)
        except json.JSONDecodeError as e:
            print(f"    JSON parse error: {e}", flush=True)
            continue
        except Exception as e:
            err = str(e)
            if "429" in err or "quota" in err.lower() or "RESOURCE_EXHAUSTED" in err:
                print(f"    rate limit hit: {err[:120]}", flush=True)
                continue
            elif any(c in err for c in ["500", "502", "503", "ServiceUnavailable"]):
                print(f"    server error: {err[:120]}", flush=True)
                continue
            else:
                print(f"    unexpected error: {err[:200]}", flush=True)
                raise
    raise RuntimeError(f"All retries exhausted for {image_path}")


def to_sharegpt(image_rel: str, parsed: dict) -> dict:
    """Convert Gemini response to ShareGPT / LLaVA format."""
    conversations = []

    # First turn: description
    conversations.append({
        "from": "human",
        "value": f"<image>\nDescribe this endoscopy image in detail."
    })
    conversations.append({
        "from": "gpt",
        "value": parsed["description"]
    })

    # Subsequent QA turns
    for i, qa in enumerate(parsed.get("qa_pairs", [])):
        conversations.append({"from": "human", "value": qa["question"]})
        conversations.append({"from": "gpt", "value": qa["answer"]})

    return {
        "id": Path(image_rel).stem,
        "image": image_rel,
        "conversations": conversations,
    }


def main():
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        print("ERROR: Set GEMINI_API_KEY environment variable")
        print("  Get a free key at: https://aistudio.google.com/apikey")
        sys.exit(1)

    client = genai.Client(api_key=api_key)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # Load existing results for resume support
    existing: dict[str, dict] = {}
    if OUTPUT_FILE.exists():
        with open(OUTPUT_FILE) as f:
            for record in json.load(f):
                existing[record["id"]] = record
        print(f"Resuming — {len(existing)} images already processed")

    # Collect all images
    all_images = sorted(IMAGE_ROOT.rglob("*.jpg")) + sorted(IMAGE_ROOT.rglob("*.png"))
    print(f"Total images: {len(all_images)}")

    results = dict(existing)
    batch_start = time.monotonic()
    batch_count = 0
    processed = 0

    for i, img_path in enumerate(all_images):
        img_id = img_path.stem
        if img_id in results:
            continue   # already done

        # Extract metadata from path
        parts = img_path.relative_to(IMAGE_ROOT).parts
        region = parts[0]          # upper-gi-tract / lower-gi-tract
        finding_type = parts[1] if len(parts) > 2 else "anatomical"
        category = parts[2] if len(parts) > 2 else parts[1]

        img_rel = str(img_path.relative_to(Path(".")))
        prompt = build_prompt(category, region, finding_type)

        print(f"[{i+1}/{len(all_images)}] {category}/{img_path.name}", end=" ", flush=True)

        # Rate limit: 15 RPM → 4 seconds between requests
        elapsed = time.monotonic() - batch_start
        if batch_count >= MAX_RPM:
            wait = max(0, 60.0 - elapsed)
            if wait > 0:
                print(f"\n  Rate limit window — waiting {wait:.1f}s...", flush=True)
                time.sleep(wait)
            batch_start = time.monotonic()
            batch_count = 0

        try:
            parsed = call_gemini(client, img_path, prompt)
            record = to_sharegpt(img_rel, parsed)
            results[img_id] = record
            batch_count += 1
            processed += 1
            print("OK", flush=True)
        except Exception as e:
            print(f"FAILED: {e}", flush=True)
            continue

        # Save checkpoint every 50 images
        if processed % 50 == 0:
            _save(results, OUTPUT_FILE)
            print(f"  Checkpoint saved ({len(results)} total)", flush=True)

    _save(results, OUTPUT_FILE)
    print(f"\nDone. {len(results)} records saved to {OUTPUT_FILE}")


def _save(results: dict, path: Path):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(list(results.values()), f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()
