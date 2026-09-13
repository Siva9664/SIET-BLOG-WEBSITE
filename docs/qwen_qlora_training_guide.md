# Qwen QLoRA Fine-Tuning Guide (Phase 9)

This guide documents how to fine-tune open-weight **Qwen** language models using Parameter-Efficient Fine-Tuning (**LoRA / QLoRA**) on the SIET Magazine Editorial Dataset.

---

## 1. Overview & Architecture

The goal of this fine-tuning pipeline is to teach Qwen the editorial voice, tone, word budgets, and publication schemas of the Sri Shakthi Institute of Engineering & Technology (SIET) magazine.

> [!IMPORTANT]
> The language model is **never** asked to physically draw or render layout pixels. Layout geometry and PDF generation remain strictly deterministic in `layout_planner.py` and `renderer.py`.

```
                      datasets/magazine_v1.0.0/
                        ├── train.jsonl
                        ├── val.jsonl
                        └── test.jsonl
                                ↓
┌──────────────────────────────────────────────────────────────────┐
│                   Qwen QLoRA Training Engine                     │
│  - Configurable Base Model (Qwen2.5-0.5B / 1.5B / 7B)            │
│  - PEFT LoRA (r=16, alpha=32, target_modules: q/k/v/o/gate/up)   │
│  - 4-bit NF4 Quantization (GPU) / Float32 (CPU fallback)         │
│  - ChatML Tokenization Formatter                                 │
│  - Checkpoint Rotation & Validation Loss Tracking                │
└──────────────────────────────────────────────────────────────────┘
                                ↓
             models/siet-qwen-magazine-v1.0.0/
               ├── adapter_config.json
               ├── adapter_model.safetensors / .bin
               ├── Modelfile (Ollama ready)
               ├── model_card.json
               └── checkpoint_metadata.json
```

---

## 2. Hardware Configurations: GPU vs CPU

### Option A: GPU (Recommended for Production / 7B Models)
- **Supported Accelerators**: NVIDIA RTX 3090, RTX 4090, A10G, A100, H100.
- **VRAM Requirements**:
  - `Qwen2.5-7B-Instruct` (4-bit QLoRA): **6–8 GB VRAM**
  - `Qwen2.5-1.5B-Instruct` (4-bit QLoRA): **3–4 GB VRAM**
  - `Qwen2.5-0.5B-Instruct` (4-bit QLoRA): **~2 GB VRAM**
- **Prerequisites**:
  - NVIDIA Driver $\ge 535$
  - CUDA $\ge 12.1$
  - `bitsandbytes` (4-bit NormalFloat4 `NF4` quantization with double quantization)
  - `accelerate` and `peft`

### Option B: CPU Fallback (Development, CI/CD, Lightweight Models)
- **Supported Processors**: Standard x86_64 / ARM64 multi-core CPUs.
- **RAM Requirements**: $\ge 16\text{ GB RAM}$.
- **Precision**: Full float32 or bfloat16 without bitsandbytes requirement.
- The pipeline automatically detects when CUDA is unavailable and switches to CPU execution mode with zero crashes.

---

## 3. Step-by-Step Execution

### Step 1: Prepare the Dataset (Phase 8)
Generate the versioned, deduplicated, and sanitized JSONL training splits:
```bash
cd backend
PYTHONPATH=. .venv/bin/python scripts/prepare_magazine_dataset.py \
  --source-dir uploads \
  --output-dir datasets/magazine_v1.0.0 \
  --version v1.0.0
```

Verify integrity and zero data leakage:
```bash
PYTHONPATH=. .venv/bin/python scripts/validate_magazine_dataset.py \
  --dataset-dir datasets/magazine_v1.0.0
```

### Step 2: Launch QLoRA Fine-Tuning
Train the model with configurable hyperparameters:
```bash
PYTHONPATH=. .venv/bin/python scripts/train_qwen_qlora.py \
  --dataset-dir datasets/magazine_v1.0.0 \
  --output-dir models/siet-qwen-magazine-v1.0.0 \
  --base-model "Qwen/Qwen2.5-0.5B-Instruct" \
  --epochs 3 \
  --lr 0.0002 \
  --lora-r 16 \
  --lora-alpha 32 \
  --device auto
```

### Step 3: Run Interactive Inference
Test editorial generation across tasks (headline, caption, classification, template selection, structured content):
```bash
PYTHONPATH=. .venv/bin/python scripts/infer_magazine_qwen.py \
  --adapter-dir models/siet-qwen-magazine-v1.0.0 \
  --task headline \
  --prompt "Students in the AI Lab deployed an autonomous quadruped machine with real-time obstacle avoidance."
```

### Step 4: Run Base vs Fine-Tuned Benchmark Evaluation
Compare Base Qwen vs Fine-Tuned Qwen on the held-out test split (`test.jsonl`):
```bash
PYTHONPATH=. .venv/bin/python scripts/evaluate_qwen_comparison.py \
  --test-file datasets/magazine_v1.0.0/test.jsonl \
  --adapter-dir models/siet-qwen-magazine-v1.0.0
```

---

## 4. Serving with Ollama

The training pipeline automatically exports an Ollama-ready `Modelfile` in the output directory:

```dockerfile
# models/siet-qwen-magazine-v1.0.0/Modelfile
FROM qwen2.5:7b
ADAPTER ./adapter_model.bin
PARAMETER temperature 0.2
PARAMETER top_p 0.9
PARAMETER stop "<|im_end|>"
SYSTEM """You are the official editorial AI for the SIET Engineering Magazine..."""
```

To create and serve the model in your local Ollama daemon:
```bash
ollama create siet-qwen-magazine -f models/siet-qwen-magazine-v1.0.0/Modelfile
ollama run siet-qwen-magazine
```

---

## 5. Integrating with the SIET Backend (Zero Disruption)

The production configuration is **not replaced automatically**. You can enable the fine-tuned model as an optional provider at any time by configuring environment variables:

```bash
# Option 1: Direct Local Fine-Tuned Adapter Provider
MAGAZINE_LLM_PROVIDER=fine_tuned_qwen
MAGAZINE_QWEN_ADAPTER_DIR=models/siet-qwen-magazine-v1.0.0

# Option 2: Served via Ollama
MAGAZINE_LLM_PROVIDER=ollama
MAGAZINE_OLLAMA_MODEL=siet-qwen-magazine
```
