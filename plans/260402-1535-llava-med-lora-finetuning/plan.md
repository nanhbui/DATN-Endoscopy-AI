# LLaVA-Med LoRA 4-bit Fine-tuning Plan

## Context Links
- [SYSTEM_REQUIREMENTS.md](../SYSTEM_REQUIREMENTS.md)
- [TECHNICAL_DESIGN.md](../TECHNICAL_DESIGN.md)
- [demo_llava_finetune.py](../demo_llava_finetune.py)
- [deploy_llava_gpu.py](../deploy_llava_gpu.py)
- [scripts/run_gpu_training.sh](../scripts/run_gpu_training.sh)

## Overview
- **Priority**: High
- **Current Status**: Planned
- **Brief Description**: Fine‑tune LLaVA‑Med model using LoRA 4‑bit quantization on the HyperKvasir dataset to generate Vietnamese medical insights from endoscopy images.

## Key Insights
- LLaVA‑Med is pre‑trained on medical images and text; LoRA reduces memory usage by ~70%.
- Must support Vietnamese output as required by `SYSTEM_REQUIREMENTS.md`.
- Training must be compatible with NVIDIA RTX 3060+ GPUs (12 GB VRAM).

## Requirements
### Functional Requirements
- Fine‑tune LLaVA‑Med on HyperKvasir with instruction pairs.
- Output responses in Vietnamese.
- Maintain inference speed < 2 s per image.
- Save fine‑tuned weights to `models/llava_med_lora_4bit/`.

### Non‑functional Requirements
- Training must fit within 12 GB VRAM (4‑bit LoRA).
- Use Hugging Face Transformers + PEFT.
- Train for ≤ 5 epochs.
- Log training metrics (loss, accuracy).

## Architecture
- **Input**: Image + Vietnamese instruction (e.g., "Mô tả tổn thương này").
- **Model**: LLaVA‑Med (`llava-hf/llava-1.5-7b-hf`).
- **Adapter**: LoRA (r=8, alpha=16).
- **Output**: Vietnamese medical explanation.
- **Training**: Single GPU, batch size = 2, gradient accumulation = 4.

## Related Code Files
- **Modify**: `demo_llava_finetune.py`, `deploy_llava_gpu.py`, `scripts/run_gpu_training.sh`
- **Create**: `models/llava_med_lora_4bit/`, `data/hyperkvasir_lora_pairs.json`
- **Delete**: None

## Implementation Steps
1. Verify `demo_llava_finetune.py` loads LLaVA‑Med correctly.
2. Load HyperKvasir dataset and convert to instruction format (JSON).
3. Initialise model with `bitsandbytes` 4‑bit quantisation.
4. Apply LoRA adapter using PEFT.
5. Configure training arguments: batch_size=2, gradient_accumulation_steps=4, learning_rate=2e‑4.
6. Train for 5 epochs with a validation split.
7. Save adapter weights to `models/llava_med_lora_4bit/`.
8. Test inference with `demo_llava_finetune.py`.

## Todo List
- [ ] Load HyperKvasir dataset
- [ ] Convert to instruction format
- [ ] Initialise 4‑bit quantised model
- [ ] Apply LoRA adapter
- [ ] Configure training arguments
- [ ] Train model
- [ ] Save adapter weights
- [ ] Test inference

## Success Criteria
- Training loss decreases below 1.5.
- Validation accuracy > 85 % on Vietnamese response quality.
- Inference time < 2 s on RTX 3060.
- Model outputs are in Vietnamese and medically accurate.

## Risk Assessment
- **Risk**: Out‑of‑memory during training
  - **Mitigation**: Use 4‑bit quantisation + gradient accumulation.
- **Risk**: Poor Vietnamese output quality
  - **Mitigation**: Use Vietnamese instruction pairs in training data.
- **Risk**: Training duration too long
  - **Mitigation**: Limit to 5 epochs; monitor loss curve.

## Security Considerations
- No sensitive patient data is used.
- All data stored locally.
- No external API calls during training.

## Next Steps
- After fine‑tuning: integrate with `src/backend/rag/llm_analyzer.py`.
- Update `TECHNICAL_DESIGN.md` with new model path.
- Create test script for Vietnamese response quality.
