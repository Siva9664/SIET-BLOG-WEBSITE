#!/usr/bin/env python3
"""
Unit tests for Qwen3 14B QLoRA preparation pipeline.
"""

import unittest
import json
import yaml
from pathlib import Path

from ml.training.qwen.validate_dataset import (
    extract_numbers,
    extract_year_dates,
    validate_grounding,
    split_dataset,
)
from ml.training.qwen.train_qlora import load_config
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


if __name__ == "__main__":
    unittest.main()
