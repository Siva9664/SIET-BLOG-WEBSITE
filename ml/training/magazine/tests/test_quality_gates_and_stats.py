"""
Unit tests for quality gate verification and dataset statistics aggregation.
"""

import json
import unittest

from ml.training.magazine.schemas import (
    DocumentRecord,
    PageData,
    PhotoItem,
    StorySegment,
    ExampleRecord,
    QualityReport,
)
from ml.training.magazine.quality_gates import QualityGateManager
from ml.training.magazine.stats import StatsAggregator


class TestQualityGatesAndStats(unittest.TestCase):
    """Test suite for quality gates and statistics calculation."""

    def setUp(self):
        self.quality_manager = QualityGateManager()
        self.stats_aggregator = StatsAggregator()

    def test_quality_gate_passes_for_clean_data(self):
        source = "Event: AI Symposium on August 15, 2026 organized by Department of CSE."
        asst = json.dumps({"headline": "AI Symposium", "date": "August 15, 2026"})

        clean_example = ExampleRecord(
            messages=[
                {"role": "system", "content": "You are SIET assistant."},
                {"role": "user", "content": f"SOURCE CONTEXT:\n{source}\n\nTASK: Generate headline."},
                {"role": "assistant", "content": asst},
            ],
            metadata={
                "doc_id": "clean_doc",
                "story_id": "clean_s1",
                "page_start": 1,
                "task_type": "headline_generation",
            },
        )

        clean_story = StorySegment(
            story_id="clean_s1",
            doc_id="clean_doc",
            story_type="events",
            page_start=1,
            page_end=1,
            headline="AI Symposium",
            body=source,
            attached_photos=["clean_doc_p1_img0"],
        )

        report = self.quality_manager.evaluate(
            examples=[clean_example],
            train_examples=[clean_example],
            val_examples=[],
            stories=[clean_story],
            duplicate_count=0,
        )

        self.assertTrue(report.passed_all_gates, f"Clean data should pass all gates. Errors: {report.errors}")
        self.assertEqual(report.grounding_failed, 0)
        self.assertEqual(report.provenance_missing, 0)

    def test_quality_gate_fails_on_missing_provenance(self):
        bad_example = ExampleRecord(
            messages=[
                {"role": "system", "content": "Sys"},
                {"role": "user", "content": "Prompt"},
                {"role": "assistant", "content": "Ans"},
            ],
            metadata={},  # Empty metadata, missing doc_id, story_id, page_start!
        )

        report = self.quality_manager.evaluate(
            examples=[bad_example],
            train_examples=[bad_example],
            val_examples=[],
            stories=[],
            duplicate_count=0,
        )

        self.assertFalse(report.passed_all_gates)
        self.assertGreater(report.provenance_missing, 0)

    def test_quality_gate_fails_on_photo_misassociation(self):
        story = StorySegment(
            story_id="doc_a_s1",
            doc_id="doc_a",
            story_type="events",
            page_start=1,
            page_end=1,
            headline="Event A",
            body="Text",
            attached_photos=["doc_b_p1_img0"],  # Photo from different document!
        )

        clean_example = ExampleRecord(
            messages=[{"role": "user", "content": "Hi"}, {"role": "assistant", "content": "Hello"}],
            metadata={"doc_id": "doc_a", "story_id": "doc_a_s1", "page_start": 1},
        )

        report = self.quality_manager.evaluate(
            examples=[clean_example],
            train_examples=[clean_example],
            val_examples=[],
            stories=[story],
            duplicate_count=0,
        )

        self.assertFalse(report.passed_all_gates)
        self.assertGreater(report.photo_misassociations, 0)

    def test_stats_aggregator(self):
        doc = DocumentRecord(
            doc_id="doc_stat",
            filename="doc_stat.pdf",
            file_type="pdf",
            total_pages=2,
            sha256="abc",
            pages=[
                PageData(
                    page_number=1,
                    text="Page 1",
                    photos=[
                        PhotoItem(
                            photo_id="doc_stat_p1_img0",
                            doc_id="doc_stat",
                            page_number=1,
                            relative_path="photos/img.png",
                            filename="img.png",
                            sha256="hash_img_1",
                        )
                    ],
                ),
                PageData(page_number=2, text="Page 2", photos=[]),
            ],
        )

        story = StorySegment(
            story_id="doc_stat_s1",
            doc_id="doc_stat",
            story_type="workshops",
            page_start=1,
            page_end=1,
            headline="Workshop",
            body="Text",
            attached_photos=["doc_stat_p1_img0"],
        )

        ex = ExampleRecord(
            messages=[{"role": "user", "content": "Q"}, {"role": "assistant", "content": "A"}],
            metadata={
                "doc_id": "doc_stat",
                "story_id": "doc_stat_s1",
                "page_start": 1,
                "task_type": "headline_generation",
                "category": "workshops",
                "template_id": "template_hero_01",
                "lab_department": "CSE",
            },
        )

        stats = self.stats_aggregator.compute(
            documents=[doc],
            stories=[story],
            all_examples=[ex],
            train_examples=[ex],
            val_examples=[],
            adversarial_examples=[],
            exact_duplicates=0,
            grounding_failures=0,
        )

        self.assertEqual(stats.total_documents, 1)
        self.assertEqual(stats.total_pages, 2)
        self.assertEqual(stats.total_stories, 1)
        self.assertEqual(stats.total_photos, 1)
        self.assertEqual(stats.examples_by_task["headline_generation"], 1)
        self.assertEqual(stats.examples_by_story_type["workshops"], 1)
        self.assertEqual(stats.examples_by_template["template_hero_01"], 1)
        self.assertEqual(stats.examples_by_department["CSE"], 1)

        # Verify markdown output contains key fields
        md = stats.to_markdown()
        self.assertIn("Source Documents", md)
        self.assertIn("Extracted Photos", md)
        self.assertIn("headline_generation", md)


if __name__ == "__main__":
    unittest.main()
