#!/usr/bin/env python3
"""
SIET Qwen3 14B QLoRA Fine-Tuning Pipeline.

Configured for NVIDIA GeForce RTX 5070 (~12.2 GB physical VRAM).
Uses 4-bit NormalFloat (NF4) BitsAndBytes quantization + PEFT LoRA adapters.
Includes instruction loss masking (loss only on assistant response).
"""

import os
import sys
import yaml
import torch
import argparse
from pathlib import Path
from typing import Dict, Any, List

import bitsandbytes as bnb
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    TrainingArguments,
    Trainer,
    DataCollatorForSeq2Seq,
)
from peft import (
    LoraConfig,
    get_peft_model,
    prepare_model_for_kbit_training,
    TaskType,
)
from datasets import load_dataset


def load_config(config_path: str) -> Dict[str, Any]:
    """Loads configuration from YAML file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def prepare_dataset_for_sft(dataset, tokenizer, max_seq_length: int = 2048):
    """
    Tokenizes ChatML messages and masks out system/user tokens with -100
    so loss is calculated exclusively on the assistant response.
    """
    def preprocess_function(examples):
        input_ids_list = []
        labels_list = []
        attention_mask_list = []

        for messages in examples["messages"]:
            # 1. Text up to generation prompt (system + user)
            prompt_text = tokenizer.apply_chat_template(
                messages[:-1], tokenize=False, add_generation_prompt=True
            )
            prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False)

            # 2. Full text including assistant response
            full_text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False
            )
            full_ids = tokenizer.encode(full_text, add_special_tokens=False)

            # Truncate if exceeds max_seq_length
            if len(full_ids) > max_seq_length:
                full_ids = full_ids[:max_seq_length]

            # Construct labels: mask prompt tokens with -100
            prompt_len = min(len(prompt_ids), len(full_ids))
            labels = [-100] * prompt_len + full_ids[prompt_len:]

            input_ids_list.append(full_ids)
            labels_list.append(labels)
            attention_mask_list.append([1] * len(full_ids))

        return {
            "input_ids": input_ids_list,
            "labels": labels_list,
            "attention_mask": attention_mask_list,
        }

    return dataset.map(
        preprocess_function,
        batched=True,
        remove_columns=dataset.column_names,
        desc="Tokenizing and masking SFT dataset",
    )


def run_tiny_compatibility_test(device: str = "cuda") -> bool:
    """
    Executes an isolated 4-bit BitsAndBytes + PEFT forward and backward pass
    to verify that CUDA kernels, 4-bit quantization, and gradient computation
    function correctly on the RTX 5070 without requiring a full 14B checkpoint.
    """
    print("\n--- Running Isolated QLoRA Compatibility Test ---")
    try:
        # Create a representative linear projection layer with Qwen target dimension
        hidden_size = 5120  # Qwen3 14B hidden size
        intermediate_size = 13824

        class DummyQwenBlock(torch.nn.Module):
            def __init__(self):
                super().__init__()
                self.q_proj = bnb.nn.Linear4bit(
                    hidden_size, hidden_size, bias=False, compute_dtype=torch.bfloat16
                )
                self.v_proj = bnb.nn.Linear4bit(
                    hidden_size, hidden_size, bias=False, compute_dtype=torch.bfloat16
                )
                self.o_proj = bnb.nn.Linear4bit(
                    hidden_size, hidden_size, bias=False, compute_dtype=torch.bfloat16
                )

            def forward(self, x):
                q = self.q_proj(x)
                v = self.v_proj(x)
                return self.o_proj(q + v)

        model = DummyQwenBlock().to(device)

        # Apply LoRA via PEFT
        peft_config = LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules=["q_proj", "v_proj", "o_proj"],
            bias="none",
        )
        peft_model = get_peft_model(model, peft_config)

        # Print parameter counts
        trainable_params, total_params = peft_model.get_nb_trainable_parameters()
        print(f"PEFT Layer Initialized: {trainable_params:,} trainable params ({100 * trainable_params / total_params:.2f}%)")

        # Forward pass with bfloat16 input
        x = torch.randn(1, 16, hidden_size, dtype=torch.bfloat16, device=device)
        output = peft_model(x)
        loss = output.sum()

        # Backward pass
        loss.backward()

        # Optimizer step verification using 8-bit Paged AdamW
        optimizer = bnb.optim.PagedAdamW8bit(peft_model.parameters(), lr=2e-4)
        optimizer.step()
        optimizer.zero_grad()

        print(f"[✓] Tiny QLoRA forward + backward + PagedAdamW8bit pass passed on {torch.cuda.get_device_name(0)}!")
        return True
    except Exception as e:
        print(f"[✗] Compatibility test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def run_dry_run_inspection(config: Dict[str, Any]):
    """
    Performs dry-run configuration inspection:
    - Verifies dataset paths
    - Verifies tokenizer & ChatML template
    - Computes parameter footprint & estimated VRAM
    """
    print("\n=======================================================")
    print("  QWEN3 14B QLORA DRY-RUN CONFIGURATION INSPECTION")
    print("=======================================================")

    model_cfg = config["model"]
    lora_cfg = config["lora"]
    train_cfg = config["training"]
    data_cfg = config["data"]

    print(f"Target Model:           {model_cfg['base_model_name_or_path']}")
    print(f"Quantization:           4-bit NF4 (Double Quant: {model_cfg['bnb_4bit_use_double_quant']})")
    print(f"Compute Dtype:          {model_cfg['bnb_4bit_compute_dtype']}")
    print(f"LoRA Rank (r):          {lora_cfg['r']}")
    print(f"LoRA Alpha:             {lora_cfg['lora_alpha']}")
    print(f"LoRA Target Modules:    {', '.join(lora_cfg['target_modules'])}")
    print(f"Batch Size (Per-Dev):   {train_cfg['per_device_train_batch_size']}")
    print(f"Grad Accumulation:      {train_cfg['gradient_accumulation_steps']} (Effective Batch: {train_cfg['per_device_train_batch_size'] * train_cfg['gradient_accumulation_steps']})")
    print(f"Max Sequence Length:    {train_cfg['max_seq_length']} tokens")
    print(f"Learning Rate:          {train_cfg['learning_rate']}")
    print(f"Optimizer:              {train_cfg['optim']}")
    print(f"Gradient Checkpointing: {train_cfg['gradient_checkpointing']}")

    # VRAM Estimation
    base_params = 14.8e9
    q4_bytes = base_params * 0.5  # 4 bits = 0.5 bytes
    lora_trainable_params = 45e6  # ~45 million params for rank 16 on all linear
    lora_weights_bytes = lora_trainable_params * 2  # bfloat16
    optimizer_states_bytes = lora_trainable_params * 4  # 8-bit adamw states
    activation_estimate = 2.0 * 1024**3  # ~2.0 GB with gradient checkpointing at seq 2048, bs 1

    total_est_bytes = q4_bytes + lora_weights_bytes + optimizer_states_bytes + activation_estimate
    total_est_gb = total_est_bytes / (1024**3)

    print("\n--- Estimated VRAM Requirements ---")
    print(f"  Base Model (4-bit NF4):     ~{q4_bytes / (1024**3):.2f} GB")
    print(f"  LoRA Weights (bfloat16):    ~{lora_weights_bytes / (1024**2):.1f} MB")
    print(f"  Optimizer (8-bit Paged):    ~{optimizer_states_bytes / (1024**2):.1f} MB")
    print(f"  Activation Buffer (bs=1):   ~{activation_estimate / (1024**3):.2f} GB")
    print(f"  Total Estimated Peak VRAM:  ~{total_est_gb:.2f} GB")
    print(f"  Physical VRAM Available:    12.28 GB (RTX 5070)")
    print(f"  VRAM Safety Margin:         ~{12.28 - total_est_gb:.2f} GB Headroom")

    # Verify Tokenizer
    print("\n--- Verifying Tokenizer & Chat Template ---")
    tokenizer = AutoTokenizer.from_pretrained(
        model_cfg["base_model_name_or_path"], trust_remote_code=True
    )
    print(f"  Tokenizer Class: {type(tokenizer).__name__}")
    print(f"  Vocab Size:      {len(tokenizer)}")
    print(f"  Pad Token:       {tokenizer.pad_token} (id {tokenizer.pad_token_id})")
    print(f"  EOS Token:       {tokenizer.eos_token} (id {tokenizer.eos_token_id})")

    # Verify Dataset Files
    print("\n--- Verifying Training Datasets ---")
    for key, path_str in [("Train", data_cfg["train_file"]), ("Val", data_cfg["val_file"])]:
        path = Path(path_str)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                lines = sum(1 for _ in f)
            print(f"  [✓] {key} file exists: {path} ({lines} examples)")
        else:
            print(f"  [!] {key} file NOT found: {path}")

    print("\n[✓] Dry-run configuration verification completed successfully.")


def main():
    parser = argparse.ArgumentParser(description="SIET Qwen3 14B QLoRA Training Pipeline")
    parser.add_argument("--config", default="ml/training/qwen/config.yaml", help="Path to config YAML")
    parser.add_argument("--dry-run", action="store_true", help="Perform configuration inspection without training")
    parser.add_argument("--tiny-test", action="store_true", help="Run tiny forward/backward compatibility test on GPU")
    args = parser.parse_args()

    config = load_config(args.config)

    if args.dry_run:
        run_dry_run_inspection(config)
        return 0

    if args.tiny_test:
        success = run_tiny_compatibility_test(device="cuda" if torch.cuda.is_available() else "cpu")
        return 0 if success else 1

    print("Executing standard fine-tuning preparation run...")
    run_dry_run_inspection(config)
    run_tiny_compatibility_test(device="cuda" if torch.cuda.is_available() else "cpu")
    print("\nTo launch full training in future phases, execute with: python ml/training/qwen/train_qlora.py --train")
    return 0


if __name__ == "__main__":
    sys.exit(main())
