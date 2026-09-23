"""Comprehensive test suite for Phase 8: MAGAZINE TRAINING DATASET PIPELINE.

Tests:
- PII Sanitization (redacts phones, personal emails, roll numbers, secrets, preserves college entities)
- Example generation for all 6 instruction tasks
- Hash deduplication
- Deterministic train/val/test splitting with strict zero-leakage guarantee
- Dataset statistics calculation
- Dataset directory validation and integrity checks
- End-to-end dataset preparation and validation pipeline
"""

import json
import os
import tempfile
from pathlib import Path
import pytest

from app.modules.datasets.magazine_dataset_generator import MagazineDatasetGenerator
from app.modules.datasets.magazine_dataset_schemas import (
    DatasetExample,
    DatasetExampleMetadata,
    DatasetProvenance,
    DatasetSplit,
    DatasetSplitConfig,
    DatasetTaskType,
)
from app.modules.datasets.pii_sanitizer import (
    detect_pii_issues,
    sanitize_text,
)
from scripts.validate_magazine_dataset import validate_dataset_directory


# ============================================================================
# 1. PII Sanitizer Tests
# ============================================================================

def test_pii_sanitizer_redacts_phones_emails_reg_numbers():
    text = (
        "Student Rahul Sharma (Reg No: 714021104001, roll: 21CS045) can be contacted at "
        "rahul.test@gmail.com or personal phone +91 9876543210. "
        "Secret token sk-123456789012345678901234 was leaked."
    )
    sanitized = sanitize_text(text)

    assert "714021104001" not in sanitized
    assert "21CS045" not in sanitized
    assert "rahul.test@gmail.com" not in sanitized
    assert "9876543210" not in sanitized
    assert "sk-123456789012345678901234" not in sanitized

    assert "[STUDENT_ID_REDACTED]" in sanitized
    assert "[EMAIL_REDACTED]" in sanitized
    assert "[PHONE_REDACTED]" in sanitized
    assert "[SECRET_TOKEN_REDACTED]" in sanitized

    # Audit confirms no remaining PII issues
    issues = detect_pii_issues(sanitized)
    assert len(issues) == 0


def test_pii_sanitizer_preserves_institutional_entities():
    text = (
        "Sri Shakthi Institute of Engineering & Technology (SIET) Autonomous, Coimbatore. "
        "The Artificial Intelligence Lab and IoT Lab hosted the annual technical symposium. "
        "For official inquiries contact info@siet.ac.in on 2026-08-15."
    )
    sanitized = sanitize_text(text)

    assert "Sri Shakthi Institute of Engineering & Technology" in sanitized
    assert "SIET" in sanitized
    assert "Artificial Intelligence Lab" in sanitized
    assert "IoT Lab" in sanitized
    assert "info@siet.ac.in" in sanitized
    assert "2026-08-15" in sanitized


# ============================================================================
# 2. Tasks 1–6 Example Generation Tests
# ============================================================================

def test_make_raw_to_structured_task1():
    generator = MagazineDatasetGenerator(dataset_version="v1.0.0")
    doc_info = {
        "filename": "annual_report.docx",
        "ext": ".docx",
        "text": "The SIET Robotics Symposium featured 30 teams presenting autonomous robot navigation prototypes. Dr. A. Kumar chaired the keynote.",
        "event_name": "SIET Robotics Symposium",
        "event_date": "2026-03-20",
        "digest": "abcdef123456",
    }
    example = generator.make_raw_to_structured_example(doc_info, idx=1)

    assert example is not None
    assert example.metadata.task == DatasetTaskType.RAW_TO_STRUCTURED
    assert "SIET Robotics Symposium" in example.input

    # Output must be valid JSON
    parsed = json.loads(example.output)
    assert "magazine_issue_title" in parsed
    assert "writeup_headline" in parsed
    assert "writeup_text" in parsed
    assert "captions" in parsed
    assert "toc_summary" in parsed


def test_make_raw_to_headline_task2():
    generator = MagazineDatasetGenerator(dataset_version="v1.0.0")
    content = "Researchers at the SIET AI Lab designed a quantized vision transformer achieving 45 FPS on edge TPUs."
    headline = "Quantized Vision Transformer Achieves 45 FPS at SIET AI Lab"

    example = generator.make_raw_to_headline_example(content, headline, idx=2)
    assert example is not None
    assert example.metadata.task == DatasetTaskType.RAW_TO_HEADLINE
    assert example.output == headline
    assert len(example.output.split()) <= 15


def test_make_raw_to_caption_task3():
    generator = MagazineDatasetGenerator(dataset_version="v1.0.0")
    context = "Students assembling the 6-axis collaborative robotic arm in Mechatronics lab."
    caption = "Students performing wrist assembly calibration on 6-DOF robotic manipulator."

    example = generator.make_raw_to_caption_example(context, caption, idx=3)
    assert example is not None
    assert example.metadata.task == DatasetTaskType.RAW_TO_CAPTION
    assert example.output == caption
    assert len(example.output.split()) <= 15


def test_make_section_classification_task4():
    generator = MagazineDatasetGenerator(dataset_version="v1.0.0")
    content = "Undergraduate student team secures first prize at National Smart India Hackathon."
    example = generator.make_section_classification_example(
        content=content,
        expected_section="student_achievement",
        reason="Details student team winning first prize in national competition.",
        idx=4,
    )
    assert example is not None
    assert example.metadata.task == DatasetTaskType.SECTION_CLASSIFICATION
    parsed = json.loads(example.output)
    assert parsed["section"] == "student_achievement"
    assert parsed["confidence"] >= 0.90


def test_make_template_selection_task5():
    generator = MagazineDatasetGenerator(dataset_version="v1.0.0")
    candidates = [
        {"template_id": "ai_lab_project_showcase", "name": "AI Lab Project", "page_type": "project_showcase", "department_or_lab": "AI Lab"},
        {"template_id": "college_events_coverage", "name": "Events", "page_type": "events", "department_or_lab": "College"},
    ]
    example = generator.make_template_selection_example(
        content_summary="AI Lab team demonstrates autonomous robot prototype.",
        department_or_lab="AI Lab",
        section="project_showcase",
        photo_count=2,
        candidates=candidates,
        selected_template_id="ai_lab_project_showcase",
        page_type="project_showcase",
        reason="AI Lab showcase with hero photograph.",
        idx=5,
    )
    assert example is not None
    assert example.metadata.task == DatasetTaskType.TEMPLATE_SELECTION
    parsed = json.loads(example.output)
    assert parsed["template_id"] == "ai_lab_project_showcase"


def test_make_photo_selection_task6():
    generator = MagazineDatasetGenerator(dataset_version="v1.0.0")
    photos = [
        {"filename": "photo_robot.jpg", "tags": ["robot", "field"], "aspect_ratio": "landscape", "quality_score": 95},
        {"filename": "empty_hall.jpg", "tags": ["hall"], "aspect_ratio": "landscape", "quality_score": 70},
    ]
    selected = [
        {"filename": "photo_robot.jpg", "slot": "hero_image", "relevance_score": 0.95, "reason": "Portrays robot prototype."}
    ]
    example = generator.make_photo_selection_example(
        article_text="Demonstration of the autonomous mobile robot.",
        photos=photos,
        selected_photos=selected,
        idx=6,
    )
    assert example is not None
    assert example.metadata.task == DatasetTaskType.PHOTO_SELECTION
    parsed = json.loads(example.output)
    assert len(parsed["selected_photographs"]) == 1
    assert parsed["selected_photographs"][0]["filename"] == "photo_robot.jpg"


# ============================================================================
# 3. Deduplication & Split Isolation Tests
# ============================================================================

def test_hash_deduplication_rejects_duplicate_inputs():
    generator = MagazineDatasetGenerator(dataset_version="v1.0.0")
    content = "Unique content about quantum edge computing algorithms."

    ex1 = generator.make_raw_to_headline_example(content, "Headline 1", idx=1)
    assert ex1 is not None

    # Exact duplicate input for same task should return None
    ex2 = generator.make_raw_to_headline_example(content, "Headline 2", idx=2)
    assert ex2 is None


def test_partition_examples_strict_zero_leakage():
    generator = MagazineDatasetGenerator(
        dataset_version="v1.0.0",
        split_config=DatasetSplitConfig(train_ratio=0.80, val_ratio=0.10, test_ratio=0.10),
    )
    exemplars = generator.generate_exemplar_catalog()
    assert len(exemplars) >= 20

    train_ex, val_ex, test_ex = generator.partition_examples(exemplars)

    assert len(train_ex) > 0
    assert len(val_ex) > 0
    assert len(test_ex) > 0
    assert len(train_ex) + len(val_ex) + len(test_ex) == len(exemplars)

    # STRICT DISJOINTNESS ASSERTIONS
    train_hashes = {e.metadata.content_hash for e in train_ex}
    val_hashes = {e.metadata.content_hash for e in val_ex}
    test_hashes = {e.metadata.content_hash for e in test_ex}

    assert train_hashes.isdisjoint(val_hashes)
    assert train_hashes.isdisjoint(test_hashes)
    assert val_hashes.isdisjoint(test_hashes)


# ============================================================================
# 4. Statistics & Validation Script Tests
# ============================================================================

def test_calculate_statistics_computes_metrics():
    generator = MagazineDatasetGenerator(dataset_version="v1.0.0")
    exemplars = generator.generate_exemplar_catalog()
    train_ex, val_ex, test_ex = generator.partition_examples(exemplars)

    stats = generator.calculate_statistics(train_ex, val_ex, test_ex)

    assert stats.dataset_version == "v1.0.0"
    assert stats.total_examples == len(exemplars)
    assert stats.split_counts["train"] == len(train_ex)
    assert stats.split_counts["val"] == len(val_ex)
    assert stats.split_counts["test"] == len(test_ex)
    assert stats.avg_input_words > 0
    assert stats.avg_output_words > 0
    assert stats.vocabulary_size > 50


def test_validate_dataset_directory_catches_leakage():
    with tempfile.TemporaryDirectory() as tmpdir:
        dir_path = Path(tmpdir)
        # Create intentional overlap between train and val
        duplicate_record = {
            "instruction": "Test instruction",
            "input": "Identical duplicate input text",
            "output": "Test output",
            "metadata": {"task": "raw_to_headline"},
        }
        clean_record = {
            "instruction": "Test instruction 2",
            "input": "Unique text 2",
            "output": "Test output 2",
            "metadata": {"task": "raw_to_headline"},
        }

        (dir_path / "train.jsonl").write_text(json.dumps(duplicate_record) + "\n" + json.dumps(clean_record) + "\n")
        (dir_path / "val.jsonl").write_text(json.dumps(duplicate_record) + "\n")
        (dir_path / "test.jsonl").write_text(json.dumps(clean_record) + "\n")

        report = validate_dataset_directory(dir_path)

        assert report.is_valid is False
        assert report.leakage_count >= 1
        assert any("DATA LEAKAGE" in issue for issue in report.issues)


def test_end_to_end_prepare_and_validate_pipeline():
    with tempfile.TemporaryDirectory() as tmpdir:
        output_dir = Path(tmpdir) / "magazine_v1.0.0"

        generator = MagazineDatasetGenerator(dataset_version="v1.0.0")
        examples = generator.generate_exemplar_catalog()
        train_ex, val_ex, test_ex = generator.partition_examples(examples)

        output_dir.mkdir(parents=True)
        (output_dir / "train.jsonl").write_text("\n".join(e.to_jsonl() for e in train_ex) + "\n")
        (output_dir / "val.jsonl").write_text("\n".join(e.to_jsonl() for e in val_ex) + "\n")
        (output_dir / "test.jsonl").write_text("\n".join(e.to_jsonl() for e in test_ex) + "\n")

        report = validate_dataset_directory(output_dir)

        assert report.is_valid is True
        assert report.total_examples == len(examples)
        assert report.leakage_count == 0
        assert report.pii_issues_count == 0
        assert report.invalid_json_count == 0
        assert len(report.issues) == 0
