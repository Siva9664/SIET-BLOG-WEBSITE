"""Automated test suite for Phase 9: QWEN QLORA FINE-TUNING PIPELINE.

Tests:
- LoRA and TrainingRun configuration contracts
- ChatML prompt template formatting
- Trainer checkpoint generation, loss tracking, and model card serialization
- Inference engine word limit compliance and structured JSON generation
- Benchmark evaluation comparing Base Qwen vs Fine-Tuned Qwen
- Optional FineTunedQwenProvider integration in llm_provider.py
"""

import json
import os
import tempfile
from pathlib import Path
import pytest

from app.modules.datasets.qwen_evaluator import (
    BaseQwenBaseline,
    MagazineQwenEvaluator,
)
from app.modules.datasets.qwen_inference import QwenMagazineInference
from app.modules.datasets.qwen_trainer import (
    QwenLoRATrainer,
    format_chatml_prompt,
    train_qwen_lora,
)
from app.modules.datasets.training_schemas import (
    LoRAHyperparameters,
    ModelCard,
    TrainingRunConfig,
)
from app.modules.magazine.llm_provider import (
    FineTunedQwenProvider,
    get_llm_config,
    get_provider,
)


# ============================================================================
# 1. Configuration & Formatting Tests
# ============================================================================

def test_training_schemas_and_hyperparameters():
    lora = LoRAHyperparameters(r=16, lora_alpha=32, lora_dropout=0.05)
    assert lora.r == 16
    assert lora.lora_alpha == 32
    assert "q_proj" in lora.target_modules

    cfg = TrainingRunConfig(
        base_model="Qwen/Qwen2.5-0.5B-Instruct",
        dataset_dir="datasets/magazine_v1.0.0",
        output_dir="models/test_qwen",
        epochs=2,
        learning_rate=3e-4,
        lora=lora,
    )
    assert cfg.epochs == 2
    assert cfg.learning_rate == 3e-4
    assert cfg.output_dir == "models/test_qwen"


def test_chatml_prompt_formatting():
    inst = "Generate a headline for this article."
    inp = "AI Lab students won first place in robotics."
    out = "AI Lab Students Win First Place"

    formatted = format_chatml_prompt(inst, inp, out)

    assert "<|im_start|>system" in formatted
    assert "<|im_end|>" in formatted
    assert "<|im_start|>user" in formatted
    assert "AI Lab students won first place" in formatted
    assert "<|im_start|>assistant" in formatted
    assert "AI Lab Students Win First Place" in formatted


# ============================================================================
# 2. Training Engine & Checkpoint Tests
# ============================================================================

def test_qwen_trainer_generates_checkpoints_and_model_card():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        dataset_dir = tmp_path / "dataset"
        dataset_dir.mkdir()
        output_dir = tmp_path / "output_model"

        # Create minimal valid train.jsonl and val.jsonl
        train_record = {
            "instruction": "Generate headline",
            "input": "SIET robotics team demo",
            "output": "SIET Robotics Team Demonstrates Mobile Prototype",
        }
        (dataset_dir / "train.jsonl").write_text(json.dumps(train_record) + "\n")
        (dataset_dir / "val.jsonl").write_text(json.dumps(train_record) + "\n")

        cfg = TrainingRunConfig(
            base_model="Qwen/Qwen2.5-0.5B-Instruct",
            dataset_dir=str(dataset_dir),
            output_dir=str(output_dir),
            model_version="v1.0.0-test",
            epochs=2,
            batch_size=1,
            gradient_accumulation_steps=1,
            device="cpu",
        )

        model_card = train_qwen_lora(cfg)

        assert isinstance(model_card, ModelCard)
        assert model_card.model_version == "v1.0.0-test"
        assert model_card.training_loss > 0
        assert model_card.validation_loss > 0

        # Verify saved artifacts on disk
        assert (output_dir / "adapter_config.json").exists()
        assert (output_dir / "adapter_model.bin").exists()
        assert (output_dir / "model_card.json").exists()
        assert (output_dir / "Modelfile").exists()
        assert (output_dir / "training_args.json").exists()
        assert (output_dir / "checkpoint_metadata.json").exists()

        # Check Modelfile snippet
        modelfile_text = (output_dir / "Modelfile").read_text()
        assert "FROM Qwen/Qwen2.5-0.5B-Instruct" in modelfile_text
        assert "ADAPTER" in modelfile_text


# ============================================================================
# 3. Inference Engine Tests
# ============================================================================

def test_qwen_inference_engine_headline_and_caption_word_limits():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = QwenMagazineInference(tmpdir)

        # Headline
        head = engine.generate(
            instruction="Generate a headline for this article.",
            input_text="Students from the Department of Artificial Intelligence deployed a state-of-the-art vision model on edge hardware for automated robotics inspection.",
        )
        assert len(head.split()) <= 15
        assert isinstance(head, str) and len(head) > 5

        # Caption
        cap = engine.generate(
            instruction="Generate a photograph caption.",
            input_text="Event: SIET AI Hackathon 2026. Context: Students demonstrating project prototype.",
        )
        assert len(cap.split()) <= 15
        assert "engaged" in cap or "proceedings" in cap or "SIET" in cap


def test_qwen_inference_engine_structured_tasks_produce_valid_json():
    with tempfile.TemporaryDirectory() as tmpdir:
        engine = QwenMagazineInference(tmpdir)

        # Section classification
        sec_out = engine.generate(
            instruction="Classify this content into a magazine section.",
            input_text="SIET student team wins national first prize and cash award at Smart India Hackathon.",
        )
        sec_parsed = json.loads(sec_out)
        assert sec_parsed["section"] == "student_achievement"
        assert sec_parsed["confidence"] >= 0.90

        # Template selection
        tmpl_out = engine.generate(
            instruction="Select the best template for this content.",
            input_text="AI Lab robotics autonomous machine navigation.",
        )
        tmpl_parsed = json.loads(tmpl_out)
        assert tmpl_parsed["template_id"] == "ai_lab_project_showcase"
        assert tmpl_parsed["page_type"] == "project_showcase"

        # Photo selection
        photo_out = engine.generate(
            instruction="Select the best photographs for this article.",
            input_text="Robotics article. Available: photo_robot.jpg, photo_hardware.png",
        )
        photo_parsed = json.loads(photo_out)
        assert "selected_photographs" in photo_parsed
        assert len(photo_parsed["selected_photographs"]) >= 1


# ============================================================================
# 4. Evaluation Benchmark: Base Qwen vs Fine-Tuned Qwen
# ============================================================================

def test_base_vs_finetuned_evaluator_metrics_computation():
    with tempfile.TemporaryDirectory() as tmpdir:
        tmp_path = Path(tmpdir)
        test_file = tmp_path / "test.jsonl"
        adapter_dir = tmp_path / "adapter"
        adapter_dir.mkdir()

        # Create diverse test set
        test_samples = [
            {"instruction": "Generate headline", "input": "AI research update", "output": "AI Research Breakthrough Announced"},
            {"instruction": "Generate caption", "input": "Event: Fest 2026", "output": "Students participating in annual fest."},
            {"instruction": "Classify section", "input": "Hackathon prize won", "output": json.dumps({"section": "student_achievement"})},
            {"instruction": "Select template", "input": "AI Lab demo", "output": json.dumps({"template_id": "ai_lab_project_showcase"})},
        ]
        test_file.write_text("\n".join(json.dumps(s) for s in test_samples) + "\n")

        evaluator = MagazineQwenEvaluator(adapter_dir, test_file)
        report = evaluator.evaluate()

        assert report.test_sample_count == 4
        assert report.finetuned_qwen_metrics.overall_score >= report.base_qwen_metrics.overall_score
        assert report.finetuned_qwen_metrics.headline_word_budget_compliance == 100.0
        assert report.finetuned_qwen_metrics.caption_word_budget_compliance == 100.0
        assert report.improvements["overall_score_gain"] >= 0.0


# ============================================================================
# 5. Optional Provider Integration Tests
# ============================================================================

@pytest.mark.asyncio
async def test_finetuned_qwen_provider_resolution():
    cfg = get_llm_config(provider="fine_tuned_qwen")
    assert cfg.provider == "fine_tuned_qwen"

    provider = get_provider(provider="fine_tuned_qwen")
    assert isinstance(provider, FineTunedQwenProvider)

    # Test generation through provider interface
    output = await provider.generate(prompt="Students win hackathon prize")
    assert isinstance(output, str)
    assert len(output) > 0
