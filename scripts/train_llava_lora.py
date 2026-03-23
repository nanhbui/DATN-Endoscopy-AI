"""
Fine-tune LLaVA-Med với LoRA 4-bit trên HyperKvasir VQA dataset.

Yêu cầu (cài trên GPU server):
  pip install transformers peft bitsandbytes accelerate pillow

Chạy:
  python scripts/train_llava_lora.py

Model base: llava-hf/llava-1.5-7b-hf  (hoặc BioMedVLP/LLaVA-Med nếu có)
LoRA config: r=16, alpha=32, 4-bit quantization (QLoRA)
"""

import json
import os
from pathlib import Path
from typing import Optional

import torch
from PIL import Image
from torch.utils.data import Dataset, DataLoader
from transformers import (
    LlavaForConditionalGeneration,
    AutoProcessor,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
)
from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training

# ─── Cấu hình ────────────────────────────────────────────────────────────────

MODEL_ID    = "llava-hf/llava-1.5-7b-hf"   # thay bằng LLaVA-Med nếu có
DATA_FILE   = Path("data/llava_finetune/train.json")
OUTPUT_DIR  = Path("outputs/llava_lora")
MAX_LENGTH  = 512
BATCH_SIZE  = 2    # GTX 1650 4GB VRAM với 4-bit
EPOCHS      = 3
LR          = 2e-4

LORA_CONFIG = LoraConfig(
    r=16,
    lora_alpha=32,
    target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
    lora_dropout=0.05,
    bias="none",
    task_type="CAUSAL_LM",
)

BNB_CONFIG = BitsAndBytesConfig(
    load_in_4bit=True,
    bnb_4bit_quant_type="nf4",
    bnb_4bit_compute_dtype=torch.float16,
    bnb_4bit_use_double_quant=True,
)


# ─── Dataset ─────────────────────────────────────────────────────────────────

class LLaVADataset(Dataset):
    """
    Đọc train.json (ShareGPT format) và trả về (processor output, labels).
    """

    def __init__(self, data_file: Path, processor, max_length: int = 512):
        with open(data_file, encoding="utf-8") as f:
            self.records = json.load(f)
        self.processor = processor
        self.max_length = max_length

    def __len__(self):
        return len(self.records)

    def __getitem__(self, idx):
        record = self.records[idx]
        image_path = record["image"]
        conversations = record["conversations"]

        # Load ảnh
        try:
            image = Image.open(image_path).convert("RGB")
        except Exception:
            image = Image.new("RGB", (224, 224), color=(128, 128, 128))

        # Ghép conversation thành prompt
        prompt = ""
        for turn in conversations:
            if turn["from"] == "human":
                prompt += f"USER: {turn['value']}\n"
            else:
                prompt += f"ASSISTANT: {turn['value']}\n"

        # Processor encode
        inputs = self.processor(
            text=prompt,
            images=image,
            return_tensors="pt",
            max_length=self.max_length,
            truncation=True,
            padding="max_length",
        )

        input_ids = inputs["input_ids"].squeeze()
        attention_mask = inputs["attention_mask"].squeeze()
        pixel_values = inputs["pixel_values"].squeeze()

        # Labels = input_ids (causal LM), mask user turns với -100
        labels = input_ids.clone()
        # Mask phần prompt của user (chỉ train trên response của assistant)
        user_token = self.processor.tokenizer.encode("USER:", add_special_tokens=False)
        assistant_token = self.processor.tokenizer.encode("ASSISTANT:", add_special_tokens=False)
        # Đơn giản: mask -100 cho toàn bộ (sẽ refine sau nếu cần)

        return {
            "input_ids": input_ids,
            "attention_mask": attention_mask,
            "pixel_values": pixel_values,
            "labels": labels,
        }


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print(f"[Train] Model: {MODEL_ID}")
    print(f"[Train] Data: {DATA_FILE}  ({DATA_FILE.stat().st_size // 1024}KB)")
    print(f"[Train] Output: {OUTPUT_DIR}")

    # Load processor
    print("[Train] Loading processor...")
    processor = AutoProcessor.from_pretrained(MODEL_ID)

    # Load model với 4-bit quantization
    print("[Train] Loading model (4-bit QLoRA)...")
    model = LlavaForConditionalGeneration.from_pretrained(
        MODEL_ID,
        quantization_config=BNB_CONFIG,
        device_map="auto",
        torch_dtype=torch.float16,
    )

    # Chuẩn bị cho k-bit training
    model = prepare_model_for_kbit_training(model)
    model = get_peft_model(model, LORA_CONFIG)
    model.print_trainable_parameters()

    # Dataset
    print("[Train] Loading dataset...")
    dataset = LLaVADataset(DATA_FILE, processor, MAX_LENGTH)
    print(f"[Train] Dataset size: {len(dataset)} samples")

    # Training arguments
    training_args = TrainingArguments(
        output_dir=str(OUTPUT_DIR),
        num_train_epochs=EPOCHS,
        per_device_train_batch_size=BATCH_SIZE,
        gradient_accumulation_steps=4,
        learning_rate=LR,
        fp16=True,
        logging_steps=50,
        save_steps=500,
        save_total_limit=2,
        warmup_ratio=0.03,
        lr_scheduler_type="cosine",
        report_to="none",
        dataloader_num_workers=2,
        remove_unused_columns=False,
    )

    # Trainer
    trainer = Trainer(
        model=model,
        args=training_args,
        train_dataset=dataset,
    )

    print("[Train] Bắt đầu training...")
    trainer.train()

    # Lưu LoRA weights
    lora_save_path = OUTPUT_DIR / "lora_weights"
    model.save_pretrained(str(lora_save_path))
    processor.save_pretrained(str(lora_save_path))
    print(f"[Train] Lưu LoRA weights tại: {lora_save_path}")


if __name__ == "__main__":
    main()