"""Pydantic schemas and metadata contracts for Qwen QLoRA Fine-Tuning Pipeline (Phase 9)."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field


class LoRAHyperparameters(BaseModel):
    """Configuration for Low-Rank Adaptation (LoRA / QLoRA)."""
    r: int = Field(default=16, description="LoRA attention rank")
    lora_alpha: int = Field(default=32, description="LoRA alpha scaling parameter")
    lora_dropout: float = Field(default=0.05, description="LoRA dropout rate")
    target_modules: List[str] = Field(
        default=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj", "up_proj", "down_proj"],
        description="Transformer module names to attach LoRA adapters to",
    )
    bias: Literal["none", "all", "lora_only"] = Field(default="none")
    task_type: str = Field(default="CAUSAL_LM")

    model_config = ConfigDict(from_attributes=True)


class TrainingRunConfig(BaseModel):
    """Complete configuration for a QLoRA/LoRA fine-tuning run."""
    base_model: str = Field(default="Qwen/Qwen2.5-0.5B-Instruct", description="Base model name or HuggingFace ID")
    dataset_dir: str = Field(default="datasets/magazine_v1.0.0", description="Directory with train.jsonl, val.jsonl, test.jsonl")
    output_dir: str = Field(default="models/siet-qwen-magazine-v1.0.0", description="Destination directory for adapter checkpoints")
    model_version: str = Field(default="v1.0.0", description="Version string for the fine-tuned model")
    
    # Hyperparameters
    epochs: int = Field(default=3, description="Total training epochs")
    learning_rate: float = Field(default=2e-4, description="Peak learning rate with AdamW")
    batch_size: int = Field(default=2, description="Per-device batch size")
    gradient_accumulation_steps: int = Field(default=4, description="Gradient accumulation steps")
    warmup_ratio: float = Field(default=0.05, description="Fraction of steps for linear warmup")
    weight_decay: float = Field(default=0.01, description="AdamW weight decay")
    max_seq_length: int = Field(default=512, description="Maximum token sequence length")
    
    # Quantization & Precision
    use_qlora: bool = Field(default=True, description="Enable 4-bit NF4 quantization on CUDA")
    bits: int = Field(default=4, description="Quantization bit-depth (4 for QLoRA, 8 or 16 for standard)")
    fp16: bool = Field(default=False, description="Use FP16 mixed precision")
    bf16: bool = Field(default=False, description="Use BF16 mixed precision")
    
    # Execution & Checkpoints
    device: Literal["cuda", "cpu", "auto"] = Field(default="auto")
    logging_steps: int = Field(default=10)
    save_steps: int = Field(default=50)
    eval_steps: int = Field(default=50)
    seed: int = Field(default=42, description="Random seed for reproducibility")
    
    lora: LoRAHyperparameters = Field(default_factory=LoRAHyperparameters)

    model_config = ConfigDict(from_attributes=True)


class TaskEvaluationScore(BaseModel):
    """Score breakdown for a specific evaluation task."""
    task_name: str
    sample_count: int
    metric_name: str
    score: float
    details: Dict[str, Any] = Field(default_factory=dict)

    model_config = ConfigDict(from_attributes=True)


class ComparisonMetrics(BaseModel):
    """Head-to-head comparison metrics between Base Qwen and Fine-Tuned Qwen."""
    json_validity_rate: float = Field(description="Percentage of structured JSON outputs that parse cleanly (0-100)")
    headline_word_budget_compliance: float = Field(description="Percentage of headlines <= 15 words (0-100)")
    caption_word_budget_compliance: float = Field(description="Percentage of captions <= 15 words (0-100)")
    section_classification_accuracy: float = Field(description="Section classification accuracy on held-out test (0-100)")
    template_selection_accuracy: float = Field(description="Template selection accuracy on held-out test (0-100)")
    house_style_alignment_score: float = Field(description="SIET editorial tone alignment score (0-100)")
    overall_score: float = Field(description="Weighted overall score (0-100)")

    model_config = ConfigDict(from_attributes=True)


class BenchmarkComparisonReport(BaseModel):
    """Full benchmark report comparing Base Qwen vs Fine-Tuned Qwen on held-out test split."""
    test_dataset: str
    test_sample_count: int
    base_model_name: str
    finetuned_model_name: str
    base_qwen_metrics: ComparisonMetrics
    finetuned_qwen_metrics: ComparisonMetrics
    improvements: Dict[str, float] = Field(default_factory=dict)
    summary: str
    evaluated_at: str

    model_config = ConfigDict(from_attributes=True)


class ModelCard(BaseModel):
    """Versioned model metadata and provenance documentation."""
    model_name: str
    model_version: str
    base_model: str
    dataset_version: str
    training_timestamp: str
    training_loss: float
    validation_loss: float
    hyperparameters: Dict[str, Any]
    evaluation_summary: Dict[str, Any]
    hardware_specs: Dict[str, Any]
    ollama_modelfile_snippet: str

    model_config = ConfigDict(from_attributes=True)
