"""Pydantic schemas and contracts for the Magazine Training Dataset Pipeline (Phase 8)."""

from __future__ import annotations

import json
from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class DatasetTaskType(str, Enum):
    """The 6 core instruction-tuning tasks for magazine intelligence."""
    RAW_TO_STRUCTURED = "raw_to_structured"
    RAW_TO_HEADLINE = "raw_to_headline"
    RAW_TO_CAPTION = "raw_to_caption"
    SECTION_CLASSIFICATION = "section_classification"
    TEMPLATE_SELECTION = "template_selection"
    PHOTO_SELECTION = "photo_selection"


class DatasetSplit(str, Enum):
    TRAIN = "train"
    VAL = "val"
    TEST = "test"


class DatasetProvenance(BaseModel):
    """Provenance tracking where the source training data originated."""
    source_type: str = Field(description="docx_report, pdf_document, template_library, photo_catalog, or synthetic_exemplar")
    source_ref: str = Field(description="Filename, URL, or identifier")
    page_number: Optional[int] = None
    document_digest: Optional[str] = None
    entity_label: Optional[str] = None
    department_or_lab: Optional[str] = None
    notes: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class DatasetExampleMetadata(BaseModel):
    """Metadata tracking versioning, task type, split, and provenance."""
    id: str
    task: DatasetTaskType
    dataset_version: str = "v1.0.0"
    split: DatasetSplit = DatasetSplit.TRAIN
    provenance: Optional[DatasetProvenance] = None
    content_hash: str
    input_word_count: int = 0
    output_word_count: int = 0
    pii_scrubbed: bool = True

    model_config = ConfigDict(from_attributes=True)


class DatasetExample(BaseModel):
    """
    Standard instruction-tuning example format:
    {
      "instruction": "...",
      "input": "...",
      "output": "...",
      "metadata": { ... }
    }
    """
    instruction: str
    input: str
    output: str
    metadata: Optional[DatasetExampleMetadata | Dict[str, Any]] = None

    model_config = ConfigDict(from_attributes=True)

    def to_jsonl_dict(self) -> Dict[str, Any]:
        """Returns clean dictionary matching alpaca/instruction format with metadata."""
        data = {
            "instruction": self.instruction,
            "input": self.input,
            "output": self.output,
        }
        if self.metadata is not None:
            if hasattr(self.metadata, "model_dump"):
                data["metadata"] = self.metadata.model_dump()
            elif isinstance(self.metadata, dict):
                data["metadata"] = self.metadata
        return data

    def to_jsonl(self) -> str:
        return json.dumps(self.to_jsonl_dict(), ensure_ascii=False)


class DatasetSplitConfig(BaseModel):
    """Configuration for deterministic train/val/test splitting."""
    train_ratio: float = 0.80
    val_ratio: float = 0.10
    test_ratio: float = 0.10
    seed: int = 42

    model_config = ConfigDict(from_attributes=True)


class DatasetStats(BaseModel):
    """Aggregate statistics for a generated dataset version."""
    dataset_version: str
    total_examples: int
    split_counts: Dict[str, int]
    task_counts: Dict[str, int]
    avg_input_words: float
    avg_output_words: float
    max_input_words: int
    max_output_words: int
    unique_sources_count: int
    vocabulary_size: int
    top_terms: List[str] = []
    generated_at: str

    model_config = ConfigDict(from_attributes=True)


class DatasetValidationReport(BaseModel):
    """Comprehensive validation report for a generated dataset version."""
    is_valid: bool
    dataset_version: str
    total_examples: int
    split_counts: Dict[str, int]
    task_counts: Dict[str, int]
    leakage_count: int = 0
    pii_issues_count: int = 0
    invalid_json_count: int = 0
    empty_fields_count: int = 0
    issues: List[str] = []

    model_config = ConfigDict(from_attributes=True)
