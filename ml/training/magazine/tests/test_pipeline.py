"""
End-to-end integration test for MagazineDatasetBuilder pipeline.
Tests full workflow from raw document ingestion through segmentation, photo association,
example generation, deduplication, splitting, validation, and statistics output.
"""

import json
import tempfile
import unittest
import subprocess
from pathlib import Path

from ml.training.magazine.build_dataset import MagazineDatasetBuilder
from ml.training.magazine.tests.test_ingestion import create_synthetic_docx


class TestMagazinePipelineE2E(unittest.TestCase):
    """End-to-end pipeline tests with synthetic documents."""

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.temp_path = Path(self.temp_dir.name)
        self.input_dir = self.temp_path / "raw"
        self.output_dir = self.temp_path / "dataset"

        self.input_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir.mkdir(parents=True, exist_ok=True)

        # Create 2 synthetic source documents to allow train/val document split
        doc1_text = (
            "# TinyML Edge AI Workshop\n\n"
            "Department of Electronics & Communication Engineering conducted a two-day workshop "
            "on July 18, 2026. 85 students participated under Dr. V. Muralidharan."
        )
        create_synthetic_docx(self.input_dir / "magazine_issue_1.docx", text_content=doc1_text, include_image=True)

        doc2_text = (
            "# HackFest 2026 Triumph\n\n"
            "Computer Science students won First Prize with INR 50,000 cash award at HackFest on August 20, 2026."
        )
        create_synthetic_docx(self.input_dir / "magazine_issue_2.docx", text_content=doc2_text, include_image=True)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_full_pipeline_run(self):
        builder = MagazineDatasetBuilder(
            input_path=self.input_dir,
            output_path=self.output_dir,
            val_ratio=0.5,
            seed=42,
            dry_run=False,
        )

        stats, quality_report = builder.run(validate=True, show_stats=True)

        # 1. Verification of outputs
        self.assertTrue(quality_report.passed_all_gates, f"Pipeline quality gates failed: {quality_report.errors}")
        self.assertEqual(stats.total_documents, 2)
        self.assertGreater(stats.total_stories, 0)
        self.assertGreater(stats.total_photos, 0)
        self.assertGreater(stats.examples_total, 0)

        # 2. Check example files
        examples_dir = self.output_dir / "examples"
        for jsonl_name in ["editorial.jsonl", "template.jsonl", "layout.jsonl", "photo.jsonl"]:
            p = examples_dir / jsonl_name
            self.assertTrue(p.exists(), f"Missing example file {jsonl_name}")
            # Ensure each line is valid JSON with ChatML schema
            with open(p, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
                self.assertGreater(len(lines), 0)
                for line in lines:
                    record = json.loads(line)
                    self.assertIn("messages", record)
                    self.assertIn("metadata", record)
                    self.assertGreaterEqual(len(record["messages"]), 2)

        # 3. Check final split files
        final_dir = self.output_dir / "final"
        for split_name in ["train.jsonl", "validation.jsonl", "adversarial.jsonl"]:
            p = final_dir / split_name
            self.assertTrue(p.exists(), f"Missing split file {split_name}")
            with open(p, "r", encoding="utf-8") as f:
                lines = [l.strip() for l in f if l.strip()]
                self.assertGreater(len(lines), 0, f"{split_name} must not be empty")

        # 4. Check stats report files
        self.assertTrue((self.output_dir / "stats.json").exists())
        self.assertTrue((self.output_dir / "stats.md").exists())

    def test_dry_run_does_not_persist(self):
        dry_output = self.temp_path / "dry_output"
        builder = MagazineDatasetBuilder(
            input_path=self.input_dir,
            output_path=dry_output,
            dry_run=True,
        )
        stats, report = builder.run(validate=True, show_stats=False)
        self.assertTrue(report.passed_all_gates)
        # Verify final train.jsonl was not written
        self.assertFalse((dry_output / "final" / "train.jsonl").exists())


if __name__ == "__main__":
    unittest.main()
