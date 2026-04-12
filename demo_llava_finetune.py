#!/usr/bin/env python3
"""
Demo: LLaVA-Med Finetuning (feat/llava-finetune branch)
"""

import time
import numpy as np

print("=" * 60)
print("🚀 DEMO: LLaVA-Med Finetuning (CPU MODE)")
print("=" * 60)

# ============================================================================
# 1. LLaVA Dataset
# ============================================================================
print("\n[1] LLaVA-Med Dataset - Loading...")
print("    Loading processor and dataset...")

from scripts.train_llava_lora import LLaVADataset, MODEL_ID, DATA_FILE
from transformers import AutoProcessor

processor = AutoProcessor.from_pretrained('llava-hf/llava-1.5-7b-hf', trust_remote_code=True)
dataset = LLaVADataset(DATA_FILE, processor, max_length=512)

print(f"    ✓ Dataset size: {len(dataset)} records")
print(f"    ✓ Model: {MODEL_ID}")
print(f"    ✓ Data file: {DATA_FILE}")

# ============================================================================
# 2. Test first item
# ============================================================================
print("\n[2] Testing first item...")
item = dataset[0]
print(f"    ✓ Input keys: {item.keys()}")
print(f"    ✓ Input IDs shape: {item['input_ids'].shape}")
print(f"    ✓ Attention mask shape: {item['attention_mask'].shape}")
print(f"    ✓ Pixel values shape: {item['pixel_values'].shape}")
print(f"    ✓ Labels shape: {item['labels'].shape}")

# ============================================================================
# 3. Tổng kết
# ============================================================================
print("\n" + "=" * 60)
print("✅ DEMO COMPLETE - LLaVA-Med Dataset working on CPU!")
print("=" * 60)
print("\n📊 Summary:")
print(f"    - Dataset: {len(dataset)} records")
print("    - Model: LLaVA-1.5-7b (4-bit quantization)")
print("    - Ready for finetuning with LoRA")
print("\n💡 Note: Để finetuning nhanh hơn, kết nối GPU server khi có sẵn.")
