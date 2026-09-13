# Qwen3 14B SIET Editorial Intelligence QLoRA Training Pipeline

Isolated preparation and fine-tuning suite for adapting local **Qwen3 14B** into the **SIET Editorial Intelligence Adapter** on an **NVIDIA GeForce RTX 5070 (~12.2 GB VRAM)**.

---

## 1. Architectural Role & Grounding Boundary

### The Adapter Teaches:
- **SIET Editorial Style:** Professional, inspirational, and grounded writing for engineering faculty, students, and industry partners.
- **Section Classification:** Sorting raw notes into the 22 magazine categories.
- **Concise Summaries & Headlines:** Action-oriented, specific titles and TOC digests under strict word budgets.
- **Factual Captions:** Concise photo descriptions (<= 15 words) strictly grounded in source notes.
- **Strict Grounding:** Missing information remains null or empty; zero fabrication.

### The Adapter Must NOT Teach:
- Visual template rendering or PDF typesetting (handled by React / PDF renderer).
- Arbitrary graphic design or page layout.
- Facial identity recognition or biometric tagging.
- Guessing or fabricating names, dates, figures, or organizations.
- Replacing the RAG retrieval system.

---

## 2. Directory Structure

```
ml/training/qwen/
├── README.md               # Complete operational runbook & design specification
├── config.yaml             # QLoRA hyperparameters, quantization, and path configs
├── prepare_dataset.py      # Generates structured SFT examples across 22 SIET categories
├── validate_dataset.py     # Grounding audit, duplicate detection, schema & split validator
├── train_qlora.py          # Isolated PEFT QLoRA training engine with 4-bit BitsAndBytes
├── evaluate.py             # Comparative benchmark: Base Qwen3 14B vs Adapter + Adversarial suite
├── datasets/
│   ├── siet_editorial_sft.jsonl  # Full curated dataset
│   ├── train.jsonl               # 85% training split (94 examples)
│   ├── val.jsonl                 # 15% validation split (16 examples)
│   └── adversarial_eval.jsonl    # Missing-information adversarial cases
└── evaluations/
    └── evaluation_report.json    # Structured evaluation metrics and benchmark log
```

---

## 3. Environment & Hardware Profile

- **Virtual Environment:** Root `./.ml-venv` exclusively (`backend/venv` is completely clean).
- **GPU:** NVIDIA GeForce RTX 5070 (12,282.7 MB physical VRAM).
- **PyTorch:** `2.11.0+cu128` with CUDA `12.8`.
- **Quantization:** 4-bit NormalFloat (`NF4`) via `bitsandbytes==0.50.2`.
- **PEFT / LoRA:** `peft==0.20.0` with `accelerate==1.15.0`.

### VRAM Budget Breakdown (RTX 5070 12.28 GB)
- **Base Model (4-bit NF4):** ~6.89 GB
- **LoRA Trainable Parameters ($r=16$):** ~85.8 MB
- **Optimizer States (`paged_adamw_8bit`):** ~171.7 MB
- **Activation Memory Buffer ($BS=1$, $L=2048$):** ~2.00 GB
- **Total Peak VRAM:** **~9.14 GB**
- **Safety Headroom:** **~3.14 GB**

---

## 4. Operational Runbook

### Step 1: Prepare Dataset
Generates SFT examples across all 22 college categories:
```bash
./.ml-venv/bin/python ml/training/qwen/prepare_dataset.py
```

### Step 2: Validate Dataset & Grounding
Performs JSON validation, grounding verification, and generates train/val splits:
```bash
./.ml-venv/bin/python ml/training/qwen/validate_dataset.py --split
```

### Step 3: Run Configuration Dry-Run & Tiny GPU Compatibility Test
Validates tokenizer, ChatML template, LoRA target modules, and executes an isolated 4-bit forward/backward step on the RTX 5070:
```bash
./.ml-venv/bin/python ml/training/qwen/train_qlora.py --dry-run
./.ml-venv/bin/python ml/training/qwen/train_qlora.py --tiny-test
```

### Step 4: Run Grounding & Adversarial Benchmark
Evaluates adversarial missing-information resistance (ensuring absent facts remain null/empty):
```bash
# Offline mock benchmark
./.ml-venv/bin/python ml/training/qwen/evaluate.py --mock

# Live Ollama Qwen3 14B benchmark
./.ml-venv/bin/python ml/training/qwen/evaluate.py
```

---

## 5. Security & Git Hygiene

The following patterns are excluded via `.gitignore` to protect privacy and repository cleanliness:
- `ml/training/qwen/checkpoints/`
- `ml/training/qwen/outputs/`
- `ml/training/qwen/runs/`
- `ml/training/qwen/wandb/`
- `ml/training/qwen/adapters/`
- `ml/training/qwen/.cache/`
- `*.safetensors`, `*.pt`, `*.bin`, `*.onnx`
