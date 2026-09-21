#!/usr/bin/env python3
"""
Unit tests for Qwen3 14B QLoRA preparation pipeline.
"""

import unittest
import json
import yaml
from pathlib import Path

import tempfile
import torch
from datasets import Dataset
from transformers import AutoTokenizer

from ml.training.qwen.validate_dataset import (
    extract_numbers,
    extract_year_dates,
    validate_grounding,
    split_dataset,
)
from ml.training.qwen.train_qlora import (
    load_config,
    build_arg_parser,
    check_local_model_availability,
    compute_chunked_loss,
    prepare_dataset_for_sft,
    run_dry_run_inspection,
    run_tiny_compatibility_test,
    run_training,
)
from ml.training.qwen.evaluate import extract_json_response, evaluate_adversarial_case


class TestQLoRAPreparation(unittest.TestCase):
    """Test suite verifying SFT dataset validation, grounding rules, and QLoRA configs."""

    def test_config_validity(self):
        config_path = Path("ml/training/qwen/config.yaml")
        self.assertTrue(config_path.exists(), "config.yaml must exist")
        cfg = load_config(str(config_path))

        self.assertIn("model", cfg)
        self.assertIn("lora", cfg)
        self.assertIn("training", cfg)
        self.assertIn("data", cfg)

        self.assertEqual(cfg["model"]["base_model_name_or_path"], "Qwen/Qwen3-14B")
        self.assertTrue(cfg["model"]["load_in_4bit"])
        self.assertEqual(cfg["lora"]["r"], 16)
        self.assertEqual(cfg["lora"]["lora_alpha"], 32)
        self.assertIn("q_proj", cfg["lora"]["target_modules"])
        self.assertTrue(cfg["training"]["gradient_checkpointing"])

    def test_grounding_audit_valid(self):
        source = "Dr. K. Arunkumar visited SIET on March 14, 2026 with 250 students."
        assistant = json.dumps({
            "title": "Dr. K. Arunkumar at SIET",
            "date": "March 14, 2026",
            "participants": 250
        })
        violations = validate_grounding(source, assistant)
        self.assertEqual(len(violations), 0, f"Expected 0 violations for grounded content, got: {violations}")

    def test_grounding_audit_catches_hallucination(self):
        source = "Students attended a workshop in the lab."
        assistant = json.dumps({
            "title": "Workshop in 2029",
            "participants": 9500
        })
        violations = validate_grounding(source, assistant)
        self.assertGreater(len(violations), 0, "Grounding validator must catch ungrounded year and number")
        violation_text = " ".join(violations)
        self.assertIn("2029", violation_text)
        self.assertIn("9500", violation_text)

    def test_split_dataset_deterministic(self):
        dummy_data = [{"id": i, "content": f"sample_{i}"} for i in range(100)]
        train_a, val_a = split_dataset(dummy_data, val_ratio=0.15, seed=42)
        train_b, val_b = split_dataset(dummy_data, val_ratio=0.15, seed=42)

        self.assertEqual(len(val_a), 15)
        self.assertEqual(len(train_a), 85)
        self.assertEqual(train_a, train_b, "Splits must be 100% deterministic given the same seed")
        self.assertEqual(val_a, val_b)

        # Ensure zero overlap/leakage between train and val
        train_ids = {x["id"] for x in train_a}
        val_ids = {x["id"] for x in val_a}
        self.assertEqual(len(train_ids.intersection(val_ids)), 0, "No data leakage between train and val")

    def test_json_extraction_from_markdown(self):
        raw_markdown = """```json
{
  "magazine_issue_title": "SIET AI Cluster",
  "captions": ["Caption 1"]
}
```"""
        parsed = extract_json_response(raw_markdown)
        self.assertIsNotNone(parsed)
        self.assertEqual(parsed["magazine_issue_title"], "SIET AI Cluster")

    def test_adversarial_eval_detection(self):
        case = {"expected_null_fields": ["speaker", "date"]}
        clean_response = '{"speaker": null, "date": null, "title": "Robotics Session"}'
        res_clean = evaluate_adversarial_case(case, clean_response)
        self.assertTrue(res_clean["passed"])

        hallucinated_response = '{"speaker": "Dr. Unknown", "date": "Jan 1, 2026"}'
        res_hallucinated = evaluate_adversarial_case(case, hallucinated_response)
        self.assertFalse(res_hallucinated["passed"])
        self.assertEqual(len(res_hallucinated["violations"]), 2)

    def test_argument_parsing(self):
        """Verifies CLI argument parsing default and flags."""
        parser = build_arg_parser()

        # Safe default without --train
        args_default = parser.parse_args([])
        self.assertFalse(args_default.train)
        self.assertFalse(args_default.dry_run)
        self.assertFalse(args_default.tiny_test)
        self.assertFalse(args_default.pilot)
        self.assertEqual(args_default.config, "ml/training/qwen/pilot_config.yaml")

        # Explicit --train
        args_train = parser.parse_args(["--train"])
        self.assertTrue(args_train.train)

        # --dry-run
        args_dry = parser.parse_args(["--dry-run"])
        self.assertTrue(args_dry.dry_run)

        # --tiny-test
        args_tiny = parser.parse_args(["--tiny-test"])
        self.assertTrue(args_tiny.tiny_test)

        # Custom config
        args_cfg = parser.parse_args(["--config", "custom.yaml"])
        self.assertEqual(args_cfg.config, "custom.yaml")

    def test_local_model_availability_checks(self):
        """Verifies that missing models fail cleanly without downloading."""
        # Nonexistent Hugging Face repo ID
        is_avail, msg = check_local_model_availability("nonexistent/fake-model-does-not-exist")
        self.assertFalse(is_avail)
        self.assertIn("not found in local cache", msg)

        # Nonexistent local path
        is_avail_dir, msg_dir = check_local_model_availability("/tmp/nonexistent_dummy_model_dir")
        self.assertFalse(is_avail_dir)

        # Check that run_training raises FileNotFoundError on missing model
        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            dummy_cfg = {
                "model": {"base_model_name_or_path": "nonexistent/fake-model"},
                "lora": {"target_modules": ["q_proj"]},
                "training": {"output_dir": "/tmp/test_out"},
                "data": {"train_file": "ml/training/qwen/datasets/pilot_train.jsonl"},
            }
            yaml.dump(dummy_cfg, f)
            tmp_path = f.name

        try:
            with self.assertRaises(FileNotFoundError):
                run_training(tmp_path)
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    def test_pilot_config_construction(self):
        """Verifies pilot configuration values for RTX 5070 QLoRA fine-tuning."""
        pilot_path = Path("ml/training/qwen/pilot_config.yaml")
        self.assertTrue(pilot_path.exists(), "pilot_config.yaml must exist")
        cfg = load_config(str(pilot_path))

        # Model configuration
        self.assertEqual(cfg["model"]["base_model_name_or_path"], "Qwen/Qwen3-14B")
        self.assertTrue(cfg["model"]["load_in_4bit"])
        self.assertEqual(cfg["model"]["bnb_4bit_compute_dtype"], "bfloat16")
        self.assertEqual(cfg["model"]["bnb_4bit_quant_type"], "nf4")
        self.assertTrue(cfg["model"]["bnb_4bit_use_double_quant"])

        # LoRA configuration (all 7 projection matrices)
        expected_modules = {"q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"}
        self.assertEqual(set(cfg["lora"]["target_modules"]), expected_modules)
        self.assertEqual(cfg["lora"]["r"], 16)
        self.assertEqual(cfg["lora"]["lora_alpha"], 32)
        self.assertEqual(cfg["lora"]["lora_dropout"], 0.05)

        # Training hyperparameters
        self.assertEqual(cfg["training"]["per_device_train_batch_size"], 1)
        self.assertEqual(cfg["training"]["gradient_accumulation_steps"], 8)
        self.assertEqual(cfg["training"]["max_seq_length"], 1024)
        self.assertEqual(cfg["training"]["learning_rate"], 0.0002)
        self.assertEqual(cfg["training"]["warmup_ratio"], 0.05)
        self.assertEqual(cfg["training"]["optim"], "paged_adamw_8bit")
        self.assertTrue(cfg["training"]["bf16"])
        self.assertFalse(cfg["training"]["fp16"])
        self.assertTrue(cfg["training"]["gradient_checkpointing"])

        # Data inputs
        self.assertTrue(Path(cfg["data"]["train_file"]).exists(), f"Train file missing: {cfg['data']['train_file']}")
        self.assertTrue(Path(cfg["data"]["val_file"]).exists(), f"Val file missing: {cfg['data']['val_file']}")

    def test_assistant_only_label_masking(self):
        """Verifies assistant-only loss masking and CoT suppression."""
        tokenizer = AutoTokenizer.from_pretrained("Qwen/Qwen3-14B", local_files_only=True)
        raw_samples = {
            "messages": [
                [
                    {"role": "system", "content": "You are SIET bot."},
                    {"role": "user", "content": "Generate headline."},
                    {"role": "assistant", "content": '{"headline": "Grounding Test Passed"}'}
                ]
            ]
        }
        dataset = Dataset.from_dict(raw_samples)
        tokenized = prepare_dataset_for_sft(dataset, tokenizer, max_seq_length=512)

        labels = tokenized[0]["labels"]
        # Prompt tokens must be masked with -100
        self.assertEqual(labels[0], -100)
        self.assertTrue(any(l == -100 for l in labels))

        # Active tokens must exist and decode to assistant content without CoT
        active_tokens = [tok for tok in labels if tok != -100]
        self.assertGreater(len(active_tokens), 0)
        decoded = tokenizer.decode(active_tokens, skip_special_tokens=True)
        self.assertIn("Grounding Test Passed", decoded)
        self.assertNotIn("<think>", decoded)
        self.assertNotIn("</think>", decoded)

        # Verify compute_chunked_loss calculates finite scalar
        dummy_logits = torch.randn(1, len(labels), len(tokenizer), dtype=torch.bfloat16)
        dummy_labels = torch.tensor([labels], dtype=torch.long)
        loss = compute_chunked_loss(dummy_logits, dummy_labels, chunk_size=32)
        self.assertTrue(torch.isfinite(loss))

    def test_dry_run_execution(self):
        """Verifies that run_dry_run_inspection runs without exceptions."""
        cfg = load_config("ml/training/qwen/pilot_config.yaml")
        run_dry_run_inspection(cfg)

    def test_tiny_compatibility_test(self):
        """Verifies isolated QLoRA forward/backward step."""
        dev = "cuda" if torch.cuda.is_available() else "cpu"
        passed = run_tiny_compatibility_test(device=dev)
        self.assertTrue(passed, "Isolated QLoRA compatibility test must pass")


if __name__ == "__main__":
    unittest.main()
