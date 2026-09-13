"""CLI Script: Train Qwen QLoRA Adapter (Phase 9).

Run from backend directory with:
    PYTHONPATH=. .venv/bin/python scripts/train_qwen_qlora.py --dataset-dir datasets/magazine_v1.0.0 --output-dir models/siet-qwen-magazine-v1.0.0 --epochs 3
"""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from app.modules.datasets.qwen_trainer import train_qwen_lora
from app.modules.datasets.training_schemas import (
    LoRAHyperparameters,
    TrainingRunConfig,
)


def main():
    parser = argparse.ArgumentParser(description="Fine-tune Qwen on SIET Magazine Editorial Dataset")
    parser.add_argument(
        "--dataset-dir",
        type=str,
        default="datasets/magazine_v1.0.0",
        help="Path to prepared dataset directory containing train.jsonl and val.jsonl",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="models/siet-qwen-magazine-v1.0.0",
        help="Path to save adapter checkpoints and model card",
    )
    parser.add_argument(
        "--base-model",
        type=str,
        default="Qwen/Qwen2.5-0.5B-Instruct",
        help="Base model identifier",
    )
    parser.add_argument("--epochs", type=int, default=3, help="Training epochs")
    parser.add_argument("--lr", type=float, default=2e-4, help="Learning rate")
    parser.add_argument("--batch-size", type=int, default=2, help="Batch size per device")
    parser.add_argument("--grad-accum", type=int, default=4, help="Gradient accumulation steps")
    parser.add_argument("--lora-r", type=int, default=16, help="LoRA rank")
    parser.add_argument("--lora-alpha", type=int, default=32, help="LoRA alpha")
    parser.add_argument("--device", type=str, default="auto", choices=["cuda", "cpu", "auto"])
    parser.add_argument("--seed", type=int, default=42, help="Random seed")

    args = parser.parse_args()

    lora_cfg = LoRAHyperparameters(
        r=args.lora_r,
        lora_alpha=args.lora_alpha,
        lora_dropout=0.05,
    )

    training_cfg = TrainingRunConfig(
        base_model=args.base_model,
        dataset_dir=args.dataset_dir,
        output_dir=args.output_dir,
        model_version="v1.0.0",
        epochs=args.epochs,
        learning_rate=args.lr,
        batch_size=args.batch_size,
        gradient_accumulation_steps=args.grad_accum,
        device=args.device,
        seed=args.seed,
        lora=lora_cfg,
    )

    print("================================================================")
    print("SIET Qwen QLoRA Fine-Tuning Pipeline (Phase 9)")
    print("================================================================")
    print(f"Base Model    : {training_cfg.base_model}")
    print(f"Dataset Dir   : {training_cfg.dataset_dir}")
    print(f"Output Dir    : {training_cfg.output_dir}")
    print(f"Hyperparams   : Epochs={training_cfg.epochs}, LR={training_cfg.learning_rate}, LoRA r={lora_cfg.r}, alpha={lora_cfg.lora_alpha}")
    print(f"Device        : {training_cfg.device}")

    model_card = train_qwen_lora(training_cfg)

    print("\nSUCCESS! Fine-tuning completed.")
    print(f"  * Model Name       : {model_card.model_name}")
    print(f"  * Final Train Loss : {model_card.training_loss}")
    print(f"  * Final Val Loss   : {model_card.validation_loss}")
    print(f"  * Adapter Artifacts: {Path(training_cfg.output_dir).resolve()}")


if __name__ == "__main__":
    main()
