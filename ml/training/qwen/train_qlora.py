#!/usr/bin/env python3
"""
SIET Qwen3 14B QLoRA Fine-Tuning Pipeline.

Configured for NVIDIA GeForce RTX 5070 (~12.2 GB physical VRAM).
Uses 4-bit NormalFloat (NF4) BitsAndBytes quantization + PEFT LoRA adapters.
Includes instruction loss masking (loss only on assistant response; no CoT training).
Enforces offline/cached model verification (local_files_only=True) to prevent remote downloads.

CLI Options:
  --train:           Execute QLoRA fine-tuning training run
  --dry-run:         Configuration inspection without GPU loading
  --tiny-test:       Isolated CUDA 4-bit + PEFT compatibility test
  --pilot:           Alias for --train (runs training using configured dataset)
  --verify-adapter:  Loads trained adapter and verifies inference
"""

import os
import sys
import time
import json
import yaml
import torch
import httpx
import argparse
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional

import bitsandbytes as bnb
import bitsandbytes.backends.cuda.ops as bnb_ops
from torch.utils.data import DataLoader
from transformers import (
    AutoTokenizer,
    AutoModelForCausalLM,
    BitsAndBytesConfig,
    DataCollatorForSeq2Seq,
    get_cosine_schedule_with_warmup,
)
from peft import (
    LoraConfig,
    PeftModel,
    get_peft_model,
    TaskType,
)
from datasets import load_dataset

# Patch bitsandbytes on Blackwell sm_120 (RTX 5070) to use custom 4-bit kernel
# instead of dequantizing weights to float16 buffers during forward/backward.
bnb_ops._gemm_4bit_use_custom_fn = lambda *args, **kwargs: True
bnb_ops._gemm_4bit_use_custom_cuda = lambda *args, **kwargs: True


def load_config(config_path: str) -> Dict[str, Any]:
    """Loads configuration from YAML file."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def unload_ollama(base_url: str = "http://localhost:11434", model: str = "qwen3:14b"):
    """Frees Ollama VRAM before starting PyTorch QLoRA training."""
    try:
        url = f"{base_url}/api/generate"
        with httpx.Client(timeout=10.0) as client:
            resp = client.post(url, json={"model": model, "keep_alive": 0})
            if resp.status_code == 200:
                print(f"[Ollama] Successfully unloaded {model} from GPU VRAM.")
    except Exception as e:
        print(f"[Ollama] Notice: Could not send unload request ({e}); proceeding.")


def check_local_model_availability(model_name_or_path: str) -> Tuple[bool, str]:
    """
    Checks if model files and tokenizer exist locally without network access.
    Returns (True, "OK message") if available, or (False, "reason") if missing/incomplete.
    """
    local_p = Path(model_name_or_path)
    if local_p.is_dir():
        has_config = (local_p / "config.json").exists()
        has_weights = (
            any(local_p.glob("*.safetensors"))
            or any(local_p.glob("*.bin"))
            or (local_p / "model.safetensors.index.json").exists()
        )
        if not has_config:
            return False, f"config.json missing in directory: {model_name_or_path}"
        if not has_weights:
            return False, f"No model weights found in directory: {model_name_or_path}"
        return True, "Found in local directory"

    try:
        from transformers.utils.hub import try_to_load_from_cache
        config_file = try_to_load_from_cache(model_name_or_path, "config.json")
        if not config_file or not isinstance(config_file, str) or not Path(config_file).exists():
            return False, f"config.json not found in local cache for '{model_name_or_path}'"

        index_file = try_to_load_from_cache(model_name_or_path, "model.safetensors.index.json")
        if index_file and isinstance(index_file, str) and Path(index_file).exists():
            with open(index_file, "r", encoding="utf-8") as f:
                index_data = json.load(f)
            weight_shards = set(index_data.get("weight_map", {}).values())
            base_dir = Path(index_file).parent
            missing = [s for s in weight_shards if not (base_dir / s).exists()]
            if missing:
                return False, f"Incomplete weights in cache. Missing shards: {missing}"
            return True, f"All {len(weight_shards)} weight shards found in local cache"
        else:
            single_weights = try_to_load_from_cache(model_name_or_path, "model.safetensors")
            if single_weights and isinstance(single_weights, str) and Path(single_weights).exists():
                return True, "model.safetensors found in local cache"
            return False, f"Neither model.safetensors.index.json nor model.safetensors found in cache for '{model_name_or_path}'"
    except Exception as e:
        return False, f"Error checking local cache: {e}"


def compute_chunked_loss(logits: torch.Tensor, labels: torch.Tensor, chunk_size: int = 64) -> torch.Tensor:
    """
    Computes cross-entropy loss in chunks over active (non -100) tokens to prevent
    VRAM spikes on large-vocabulary models (Qwen vocab size 151,669).
    """
    shift_logits = logits[..., :-1, :].contiguous()
    shift_labels = labels[..., 1:].contiguous()
    mask = shift_labels != -100
    active_logits = shift_logits[mask]
    active_labels = shift_labels[mask]

    num_tokens = max(1, active_labels.numel())
    total_loss = 0.0
    for i in range(0, active_labels.numel(), chunk_size):
        c_logits = active_logits[i : i + chunk_size]
        c_labels = active_labels[i : i + chunk_size]
        total_loss = total_loss + torch.nn.functional.cross_entropy(c_logits, c_labels, reduction="sum")
    return total_loss / num_tokens


def prepare_dataset_for_sft(dataset, tokenizer, max_seq_length: int = 1024):
    """
    Tokenizes ChatML messages and masks out system, user, and CoT tokens with -100
    so loss is calculated exclusively on the assistant response.
    """
    def preprocess_function(examples):
        input_ids_list = []
        labels_list = []
        attention_mask_list = []

        for messages in examples["messages"]:
            # Full text including assistant response
            full_text = tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=False
            )

            # Mask out everything up to the actual assistant response content (including <think>...</think>)
            if "</think>" in full_text:
                idx = full_text.find("</think>") + len("</think>")
                while idx < len(full_text) and full_text[idx] in ("\n", " "):
                    idx += 1
                prompt_text = full_text[:idx]
            else:
                prompt_text = tokenizer.apply_chat_template(
                    messages[:-1], tokenize=False, add_generation_prompt=True
                )

            prompt_ids = tokenizer.encode(prompt_text, add_special_tokens=False)
            full_ids = tokenizer.encode(full_text, add_special_tokens=False)

            # Truncate if exceeds max_seq_length
            if len(full_ids) > max_seq_length:
                full_ids = full_ids[:max_seq_length]

            # Construct labels: mask prompt and CoT tokens with -100
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
        hidden_size = 5120  # Qwen3 14B hidden size

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

        peft_config = LoraConfig(
            r=16,
            lora_alpha=32,
            lora_dropout=0.05,
            target_modules=["q_proj", "v_proj", "o_proj"],
            bias="none",
        )
        peft_model = get_peft_model(model, peft_config)

        trainable_params, total_params = peft_model.get_nb_trainable_parameters()
        print(f"PEFT Layer Initialized: {trainable_params:,} trainable params ({100 * trainable_params / total_params:.2f}%)")

        x = torch.randn(1, 16, hidden_size, dtype=torch.bfloat16, device=device)
        output = peft_model(x)
        loss = output.sum()
        loss.backward()

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
    """Performs dry-run configuration inspection."""
    print("\n=======================================================")
    print("  QWEN3 14B QLORA DRY-RUN CONFIGURATION INSPECTION")
    print("=======================================================")

    model_cfg = config["model"]
    lora_cfg = config["lora"]
    train_cfg = config["training"]
    data_cfg = config["data"]

    print(f"Target Model:           {model_cfg['base_model_name_or_path']}")
    print(f"Quantization:           4-bit NF4 (Double Quant: {model_cfg.get('bnb_4bit_use_double_quant', True)})")
    print(f"Compute Dtype:          {model_cfg.get('bnb_4bit_compute_dtype', 'bfloat16')}")
    print(f"LoRA Rank (r):          {lora_cfg['r']}")
    print(f"LoRA Alpha:             {lora_cfg['lora_alpha']}")
    print(f"LoRA Target Modules:    {', '.join(lora_cfg['target_modules'])}")
    print(f"Batch Size (Per-Dev):   {train_cfg['per_device_train_batch_size']}")
    print(f"Grad Accumulation:      {train_cfg['gradient_accumulation_steps']} (Effective Batch: {train_cfg['per_device_train_batch_size'] * train_cfg['gradient_accumulation_steps']})")
    print(f"Max Sequence Length:    {train_cfg['max_seq_length']} tokens")
    print(f"Learning Rate:          {train_cfg['learning_rate']} (Warmup Ratio: {train_cfg.get('warmup_ratio', 0.05)})")
    print(f"Optimizer:              {train_cfg['optim']}")
    print(f"Gradient Checkpointing: {train_cfg['gradient_checkpointing']}")

    # VRAM Estimation
    base_params = 14.8e9
    q4_bytes = base_params * 0.5
    lora_trainable_params = 45e6
    lora_weights_bytes = lora_trainable_params * 2
    optimizer_states_bytes = lora_trainable_params * 4
    activation_estimate = 2.0 * 1024**3

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

    print("\n--- Verifying Local Model Cache ---")
    is_avail, cache_msg = check_local_model_availability(model_cfg["base_model_name_or_path"])
    print(f"  Local Status:    {'[✓] Available' if is_avail else '[!] Incomplete / Missing'}")
    print(f"  Details:         {cache_msg}")

    print("\n--- Verifying Tokenizer & Chat Template ---")
    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_cfg["base_model_name_or_path"],
            trust_remote_code=model_cfg.get("trust_remote_code", True),
            local_files_only=True,
        )
        print(f"  Tokenizer Class: {type(tokenizer).__name__}")
        print(f"  Vocab Size:      {len(tokenizer)}")
        print(f"  Pad Token:       {tokenizer.pad_token} (id {tokenizer.pad_token_id})")
        print(f"  EOS Token:       {tokenizer.eos_token} (id {tokenizer.eos_token_id})")
    except Exception as e:
        print(f"  [!] Tokenizer offline check notice: {e}")

    print("\n--- Verifying Training Datasets ---")
    for key, path_str in [("Train", data_cfg.get("train_file")), ("Val", data_cfg.get("val_file"))]:
        if not path_str:
            continue
        path = Path(path_str)
        if path.exists():
            with open(path, "r", encoding="utf-8") as f:
                lines = sum(1 for _ in f)
            print(f"  [✓] {key} file exists: {path} ({lines} examples)")
        else:
            print(f"  [!] {key} file NOT found: {path}")

    print("\n[✓] Dry-run configuration verification completed successfully.")


def run_training(config_path: str = "ml/training/qwen/pilot_config.yaml") -> Dict[str, Any]:
    """
    Executes QLoRA fine-tuning with full telemetry tracking.
    Enforces local_files_only=True and checks local model availability before running.
    """
    print("\n=======================================================")
    print("  SIET QWEN3 14B QLORA TRAINING RUN")
    print("=======================================================")

    config = load_config(config_path)
    model_cfg = config["model"]
    lora_cfg = config["lora"]
    train_cfg = config["training"]
    data_cfg = config["data"]

    # 1. Verify Local Model Availability (Fail-fast before GPU operations)
    base_model_id = model_cfg["base_model_name_or_path"]
    is_available, status_msg = check_local_model_availability(base_model_id)
    if not is_available:
        print(f"\n[ERROR] Model '{base_model_id}' is not available locally:")
        print(f"  {status_msg}")
        print("\nPer safety rules, automatic remote downloading is disabled.")
        print("To download the model files locally before training, run:")
        print(f"  huggingface-cli download {base_model_id}\n")
        raise FileNotFoundError(f"Local model files for {base_model_id} not found: {status_msg}")

    # Set CUDA allocation config to prevent memory fragmentation
    os.environ["PYTORCH_CUDA_ALLOC_CONF"] = "expandable_segments:True"

    # Hardware & Configuration Telemetry
    device_name = torch.cuda.get_device_name(0) if torch.cuda.is_available() else "cpu"
    total_vram_gb = (torch.cuda.get_device_properties(0).total_memory / (1024**3)) if torch.cuda.is_available() else 0.0
    print(f"Device:                 {device_name} ({total_vram_gb:.2f} GB physical VRAM)")
    print(f"Base Model:             {base_model_id}")
    print(f"Quantization:           4-bit NF4 (Double Quant: {model_cfg.get('bnb_4bit_use_double_quant', True)})")
    print(f"Compute Dtype:          {model_cfg.get('bnb_4bit_compute_dtype', 'bfloat16')}")
    print(f"LoRA Target Modules:    {', '.join(lora_cfg['target_modules'])}")
    print(f"LoRA Rank / Alpha:      r={lora_cfg['r']}, alpha={lora_cfg['lora_alpha']}, dropout={lora_cfg['lora_dropout']}")
    print(f"Batch Size (Per-Dev):   {train_cfg['per_device_train_batch_size']}")
    print(f"Grad Accumulation:      {train_cfg['gradient_accumulation_steps']} (Effective Batch Size: {train_cfg['per_device_train_batch_size'] * train_cfg['gradient_accumulation_steps']})")
    print(f"Max Sequence Length:    {train_cfg['max_seq_length']} tokens")
    print(f"Learning Rate:          {train_cfg['learning_rate']} (Cosine Scheduler, Warmup Ratio: {train_cfg.get('warmup_ratio', 0.05)})")
    print(f"Optimizer:              {train_cfg['optim']}")
    print(f"Gradient Checkpointing: {train_cfg['gradient_checkpointing']}")

    # 2. Free Ollama VRAM and Reset Peak Memory Stats
    unload_ollama()
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        torch.cuda.reset_peak_memory_stats()
        # Pre-initialize cuBLAS context & internal workspace in clean VRAM
        _ = torch.matmul(torch.zeros((16, 16), device="cuda"), torch.zeros((16, 16), device="cuda"))
        initial_vram_gb = torch.cuda.memory_allocated() / (1024**3)
        print(f"Initial GPU Allocated VRAM: {initial_vram_gb:.3f} GB")

    # 3. Load Tokenizer (Local files only)
    print(f"\nLoading Tokenizer from local cache: {base_model_id}...")
    tokenizer = AutoTokenizer.from_pretrained(
        base_model_id,
        trust_remote_code=model_cfg.get("trust_remote_code", True),
        local_files_only=True,
    )
    if tokenizer.pad_token is None:
        tokenizer.pad_token = tokenizer.eos_token

    # 4. Model Loading with 4-bit BitsAndBytes (Local files only)
    print("Configuring 4-bit BitsAndBytes NF4 Quantization...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=model_cfg.get("load_in_4bit", True),
        bnb_4bit_quant_type=model_cfg.get("bnb_4bit_quant_type", "nf4"),
        bnb_4bit_compute_dtype=getattr(torch, model_cfg.get("bnb_4bit_compute_dtype", "bfloat16")),
        bnb_4bit_use_double_quant=model_cfg.get("bnb_4bit_use_double_quant", True),
    )

    print(f"Loading base model {base_model_id} in 4-bit NF4 into {device_name} (offline mode)...")
    start_load_time = time.time()
    model = AutoModelForCausalLM.from_pretrained(
        base_model_id,
        quantization_config=bnb_config,
        device_map={"": 0} if torch.cuda.is_available() else "auto",
        dtype=getattr(torch, model_cfg.get("dtype", model_cfg.get("torch_dtype", "bfloat16"))),
        trust_remote_code=model_cfg.get("trust_remote_code", True),
        local_files_only=True,
    )
    model.config.use_cache = False
    load_duration = time.time() - start_load_time
    loaded_vram_gb = (torch.cuda.memory_allocated() / (1024**3)) if torch.cuda.is_available() else 0.0
    print(f"Base model loaded in {load_duration:.1f}s. Resident VRAM: {loaded_vram_gb:.2f} GB")

    # 5. Apply PEFT LoRA
    print("Applying PEFT LoRA configuration...")
    for p in model.parameters():
        p.requires_grad = False

    if train_cfg.get("gradient_checkpointing", True):
        if hasattr(model, "enable_input_require_grads"):
            model.enable_input_require_grads()
        else:
            def make_inputs_require_grad(module, input, output):
                output.requires_grad_(True)
            model.get_input_embeddings().register_forward_hook(make_inputs_require_grad)
        model.gradient_checkpointing_enable(gradient_checkpointing_kwargs={"use_reentrant": False})

    peft_config = LoraConfig(
        r=lora_cfg["r"],
        lora_alpha=lora_cfg["lora_alpha"],
        lora_dropout=lora_cfg["lora_dropout"],
        bias=lora_cfg.get("bias", "none"),
        task_type=TaskType.CAUSAL_LM,
        target_modules=lora_cfg["target_modules"],
    )
    peft_model = get_peft_model(model, peft_config)
    peft_model.train()
    trainable_params, total_params = peft_model.get_nb_trainable_parameters()
    print(f"PEFT LoRA Attached:     {trainable_params:,} trainable params ({100 * trainable_params / total_params:.2f}%)")

    # 6. Load Datasets
    train_file = data_cfg["train_file"]
    val_file = data_cfg.get("val_file")
    print(f"\nLoading training dataset from: {train_file}...")
    raw_train = load_dataset("json", data_files={"train": train_file})["train"]
    print(f"Training dataset samples count: {len(raw_train)}")

    tokenized_train = prepare_dataset_for_sft(
        raw_train, tokenizer, max_seq_length=train_cfg.get("max_seq_length", 1024)
    )

    raw_val = None
    val_dataloader = None
    if val_file and Path(val_file).exists():
        print(f"Loading validation dataset from: {val_file}...")
        raw_val = load_dataset("json", data_files={"val": val_file})["val"]
        print(f"Validation dataset samples count: {len(raw_val)}")
        tokenized_val = prepare_dataset_for_sft(
            raw_val, tokenizer, max_seq_length=train_cfg.get("max_seq_length", 1024)
        )
        data_collator_val = DataCollatorForSeq2Seq(
            tokenizer=tokenizer,
            pad_to_multiple_of=8,
            return_tensors="pt",
            padding=True,
        )
        val_dataloader = DataLoader(
            tokenized_val,
            batch_size=train_cfg.get("per_device_eval_batch_size", 1),
            collate_fn=data_collator_val,
            shuffle=False,
        )

    data_collator = DataCollatorForSeq2Seq(
        tokenizer=tokenizer,
        pad_to_multiple_of=8,
        return_tensors="pt",
        padding=True,
    )

    # 7. Training Pipeline Setup
    output_dir = Path(train_cfg["output_dir"])
    output_dir.mkdir(parents=True, exist_ok=True)

    dataloader = DataLoader(
        tokenized_train,
        batch_size=train_cfg["per_device_train_batch_size"],
        collate_fn=data_collator,
        shuffle=True,
    )
    optimizer = bnb.optim.PagedAdamW8bit(
        peft_model.parameters(),
        lr=train_cfg["learning_rate"],
        weight_decay=train_cfg.get("weight_decay", 0.01),
    )
    gradient_accumulation_steps = train_cfg["gradient_accumulation_steps"]
    total_steps = (len(dataloader) + gradient_accumulation_steps - 1) // gradient_accumulation_steps * train_cfg["num_train_epochs"]

    warmup_ratio = train_cfg.get("warmup_ratio", 0.05)
    warmup_steps = int(total_steps * warmup_ratio) if warmup_ratio else train_cfg.get("warmup_steps", 0)
    lr_scheduler = get_cosine_schedule_with_warmup(
        optimizer,
        num_warmup_steps=warmup_steps,
        num_training_steps=max(1, total_steps),
    )

    # 8. Training Loop
    print(f"\nStarting training pass ({len(tokenized_train)} samples, {gradient_accumulation_steps} accum steps, {total_steps} global steps)...")
    start_train_time = time.time()
    peft_model.train()
    optimizer.zero_grad()

    epoch_loss = 0.0
    global_step = 0
    accumulated_loss = 0.0

    for step, batch in enumerate(dataloader):
        input_ids = batch["input_ids"].to("cuda")
        attention_mask = batch.get("attention_mask", None)
        if attention_mask is not None:
            attention_mask = attention_mask.to("cuda")
        labels = batch["labels"].to("cuda")

        with torch.amp.autocast("cuda", dtype=torch.bfloat16):
            outputs = peft_model(input_ids=input_ids, attention_mask=attention_mask)
            logits = outputs.logits
            batch_loss = compute_chunked_loss(logits, labels)
            loss = batch_loss / gradient_accumulation_steps

        loss.backward()
        accumulated_loss += loss.item() * gradient_accumulation_steps

        if (step + 1) % gradient_accumulation_steps == 0 or (step + 1) == len(dataloader):
            optimizer.step()
            lr_scheduler.step()
            optimizer.zero_grad()
            global_step += 1
            step_divisor = gradient_accumulation_steps if (step + 1) % gradient_accumulation_steps == 0 else ((step + 1) % gradient_accumulation_steps)
            avg_step_loss = accumulated_loss / step_divisor
            current_lr = lr_scheduler.get_last_lr()[0]
            peak_vram_now = (torch.cuda.max_memory_allocated() / (1024**3)) if torch.cuda.is_available() else 0.0
            print(f"  Step {global_step}/{total_steps} | Loss: {avg_step_loss:.4f} | LR: {current_lr:.6f} | Peak Allocated VRAM: {peak_vram_now:.2f} GB")
            epoch_loss += accumulated_loss
            accumulated_loss = 0.0

    train_duration = time.time() - start_train_time
    avg_train_loss = epoch_loss / len(dataloader)

    # 9. Validation Evaluation
    eval_loss = None
    if val_dataloader is not None:
        print(f"\n--- Running Evaluation on {len(raw_val)} Validation Samples ---")
        peft_model.eval()
        val_loss_total = 0.0
        val_batches = 0
        with torch.no_grad():
            for val_batch in val_dataloader:
                v_input_ids = val_batch["input_ids"].to("cuda")
                v_mask = val_batch.get("attention_mask", None)
                if v_mask is not None:
                    v_mask = v_mask.to("cuda")
                v_labels = val_batch["labels"].to("cuda")
                with torch.amp.autocast("cuda", dtype=torch.bfloat16):
                    v_outputs = peft_model(input_ids=v_input_ids, attention_mask=v_mask)
                    v_loss = compute_chunked_loss(v_outputs.logits, v_labels)
                val_loss_total += v_loss.item()
                val_batches += 1
        eval_loss = val_loss_total / max(1, val_batches)
        print(f"  [✓] Validation Loss (eval_loss): {eval_loss:.4f}")

    peak_vram_gb = (torch.cuda.max_memory_allocated() / (1024**3)) if torch.cuda.is_available() else 0.0
    reserved_vram_gb = (torch.cuda.memory_reserved() / (1024**3)) if torch.cuda.is_available() else 0.0

    print(f"\n[✓] Training finished in {train_duration:.2f}s!")
    print(f"  Global Steps:         {global_step}")
    print(f"  Average Train Loss:   {avg_train_loss:.4f}")
    if eval_loss is not None:
        print(f"  Evaluation Loss:      {eval_loss:.4f}")
    print(f"  Peak Allocated VRAM:  {peak_vram_gb:.2f} GB")
    print(f"  Peak Reserved VRAM:   {reserved_vram_gb:.2f} GB")

    # 10. Save LoRA Adapter & Telemetry Metadata
    print(f"\nSaving LoRA adapter weights to: {output_dir}...")
    peft_model.save_pretrained(str(output_dir))
    tokenizer.save_pretrained(str(output_dir))

    adapter_files = [f.name for f in output_dir.iterdir() if f.is_file()]
    adapter_size_mb = sum(f.stat().st_size for f in output_dir.iterdir() if f.is_file()) / (1024**2)

    metadata = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "base_model": base_model_id,
        "device": device_name,
        "train_dataset": train_file,
        "train_samples": len(raw_train),
        "val_dataset": val_file,
        "val_samples": len(raw_val) if raw_val is not None else 0,
        "train_steps": global_step,
        "train_duration_sec": train_duration,
        "training_loss": avg_train_loss,
        "eval_loss": eval_loss,
        "peak_vram_gb": peak_vram_gb,
        "reserved_vram_gb": reserved_vram_gb,
        "adapter_size_mb": adapter_size_mb,
        "adapter_files": adapter_files,
        "adapter_path": str(output_dir),
        "config": {
            "learning_rate": train_cfg["learning_rate"],
            "lora_rank": lora_cfg["r"],
            "lora_alpha": lora_cfg["lora_alpha"],
            "target_modules": lora_cfg["target_modules"],
            "max_seq_length": train_cfg["max_seq_length"],
            "batch_size": train_cfg["per_device_train_batch_size"],
            "gradient_accumulation_steps": train_cfg["gradient_accumulation_steps"],
            "optim": train_cfg["optim"],
        },
    }

    metadata_path = output_dir / "training_metadata.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(metadata, f, indent=2)

    print(f"Adapter saved: {adapter_size_mb:.2f} MB across {len(adapter_files)} files.")
    print(f"Metadata written to: {metadata_path}")

    return metadata


def run_pilot_training(config_path: str = "ml/training/qwen/pilot_config.yaml") -> Dict[str, Any]:
    """Alias to run_training for backward compatibility."""
    return run_training(config_path)


def verify_adapter_inference(adapter_dir: str = "ml/training/qwen/checkpoints/pilot") -> bool:
    """Verifies that the saved LoRA adapter can be loaded and perform inference without error."""
    print("\n=======================================================")
    print("  VERIFYING LORA ADAPTER INFERENCE & RELOAD")
    print("=======================================================")

    adapter_path = Path(adapter_dir)
    if not (adapter_path / "adapter_config.json").exists():
        print(f"[!] Adapter directory does not exist or lacks adapter_config.json: {adapter_path}")
        return False

    with open(adapter_path / "adapter_config.json", "r") as f:
        adapter_cfg = json.load(f)
    base_model_name = adapter_cfg.get("base_model_name_or_path", "Qwen/Qwen3-14B")

    print(f"Loading Base Model: {base_model_name} (local files only)...")
    bnb_config = BitsAndBytesConfig(
        load_in_4bit=True,
        bnb_4bit_quant_type="nf4",
        bnb_4bit_compute_dtype=torch.bfloat16,
        bnb_4bit_use_double_quant=True,
    )
    tokenizer = AutoTokenizer.from_pretrained(str(adapter_path), trust_remote_code=True, local_files_only=True)
    base_model = AutoModelForCausalLM.from_pretrained(
        base_model_name,
        quantization_config=bnb_config,
        device_map={"": 0} if torch.cuda.is_available() else "auto",
        dtype=torch.bfloat16,
        trust_remote_code=True,
        local_files_only=True,
    )

    print(f"Attaching LoRA Adapter from {adapter_path}...")
    model = PeftModel.from_pretrained(base_model, str(adapter_path))
    model.eval()

    test_prompt = [
        {"role": "system", "content": "You are the editorial intelligence assistant for SIET. Never invent names, dates, or numbers."},
        {"role": "user", "content": "SOURCE CONTEXT:\nStudents held a robotics trial in the mechanical lab.\n\nTASK:\nGenerate headline and summary."},
    ]
    formatted = tokenizer.apply_chat_template(test_prompt, tokenize=False, add_generation_prompt=True)
    inputs = tokenizer(formatted, return_tensors="pt").to("cuda" if torch.cuda.is_available() else "cpu")

    print("Generating response from Adapter...")
    start_time = time.time()
    with torch.no_grad():
        outputs = model.generate(
            **inputs,
            max_new_tokens=150,
            temperature=0.2,
            top_p=0.9,
            pad_token_id=tokenizer.pad_token_id,
            eos_token_id=tokenizer.eos_token_id,
        )
    latency = time.time() - start_time
    response_tokens = outputs[0][inputs["input_ids"].shape[1]:]
    text = tokenizer.decode(response_tokens, skip_special_tokens=True)

    print(f"[✓] Adapter Generation Successful in {latency:.2f}s!")
    print(f"Generated text snippet:\n{text[:300]}")
    return True


def build_arg_parser() -> argparse.ArgumentParser:
    """Constructs CLI argument parser."""
    parser = argparse.ArgumentParser(description="SIET Qwen3 14B QLoRA Training Pipeline")
    parser.add_argument("--config", default="ml/training/qwen/pilot_config.yaml", help="Path to config YAML")
    parser.add_argument("--train", action="store_true", help="Execute QLoRA fine-tuning training run")
    parser.add_argument("--dry-run", action="store_true", help="Perform configuration inspection without training")
    parser.add_argument("--tiny-test", action="store_true", help="Run tiny forward/backward compatibility test on GPU")
    parser.add_argument("--pilot", action="store_true", help="Run pilot training pass (alias for --train with pilot config)")
    parser.add_argument("--verify-adapter", action="store_true", help="Verify saved adapter loading and inference")
    return parser


def main():
    parser = build_arg_parser()
    args = parser.parse_args()

    if args.dry_run:
        config = load_config(args.config)
        run_dry_run_inspection(config)
        return 0

    if args.tiny_test:
        success = run_tiny_compatibility_test(device="cuda" if torch.cuda.is_available() else "cpu")
        return 0 if success else 1

    if args.verify_adapter:
        success = verify_adapter_inference()
        return 0 if success else 1

    if args.train or args.pilot:
        meta = run_training(args.config)
        return 0

    # Safe default: Dry-run and tiny compatibility test
    config = load_config(args.config)
    run_dry_run_inspection(config)
    run_tiny_compatibility_test(device="cuda" if torch.cuda.is_available() else "cpu")
    print("\n--------------------------------------------------------------------------------")
    print("[SAFE MODE] Configuration and hardware compatibility checks completed.")
    print("Training was NOT started. To launch actual QLoRA fine-tuning, pass '--train':")
    print(f"  ./.ml-venv/bin/python ml/training/qwen/train_qlora.py --train --config {args.config}")
    print("--------------------------------------------------------------------------------")
    return 0


if __name__ == "__main__":
    sys.exit(main())
