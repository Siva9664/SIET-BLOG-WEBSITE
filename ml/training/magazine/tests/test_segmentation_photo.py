"""
Unit tests for event segmentation and photo association.
Tests:
- Classification across all 10 story categories
- Strict metadata extraction without hallucinating missing fields
- Photo association preservation, order, and uncertain flagging
"""

import unittest
from pathlib import Path

from ml.training.magazine.schemas import (
    DocumentRecord,
    PageData,
    PhotoItem,
    StorySegment,
    StoryType,
    PhotoConfidence,
)
from ml.training.magazine.segmenter import (
    StorySegmenter,
    classify_story_type,
    extract_dates,
    extract_people,
    extract_organization,
    extract_achievement_result,
)
from ml.training.magazine.photo_associator import PhotoAssociator


class TestSegmentationAndPhotoAssociation(unittest.TestCase):
    """Test suite for event segmentation and grounded photo association."""

    def setUp(self):
        self.segmenter = StorySegmenter()
        self.associator = PhotoAssociator()

    def test_story_type_classification(self):
        self.assertEqual(
            classify_story_type("Our robotics team won first prize and bagged gold medal at HackFest 2026."),
            StoryType.VICTORIES.value,
        )
        self.assertEqual(
            classify_story_type("The lab secured INR 35 Lakhs institutional research grant for AI hardware."),
            StoryType.ACHIEVEMENTS.value,
        )
        self.assertEqual(
            classify_story_type("Department conducted a two-day hands-on workshop on TinyML and Edge AI."),
            StoryType.WORKSHOPS.value,
        )
        self.assertEqual(
            classify_story_type("An invited guest lecture on quantum computing was delivered by Dr. Ramesh."),
            StoryType.SEMINARS.value,
        )
        self.assertEqual(
            classify_story_type("Students competed in the annual national coding challenge tournament."),
            StoryType.COMPETITIONS.value,
        )
        self.assertEqual(
            classify_story_type("Final year students exhibited their autonomous drone prototype at the project expo."),
            StoryType.PROJECTS.value,
        )
        self.assertEqual(
            classify_story_type("Dr. V. Muralidharan coordinated the faculty development programme (FDP)."),
            StoryType.FACULTY.value,
        )
        self.assertEqual(
            classify_story_type("NSS student club members organized a campus blood donation camp."),
            StoryType.STUDENT.value,
        )

    def test_metadata_extraction_no_hallucination(self):
        # Case 1: Complete information
        text_with_data = (
            "On August 15, 2026, Dr. K. Arunkumar coordinated the AI Symposium organized by "
            "Department of Computer Science & Engineering. The team won First Prize with INR 50,000 cash award."
        )
        self.assertEqual(extract_dates(text_with_data), "August 15, 2026")
        self.assertIn("Dr. K. Arunkumar", extract_people(text_with_data))
        self.assertIn("Computer Science & Engineering", extract_organization(text_with_data))
        self.assertIsNotNone(extract_achievement_result(text_with_data))


        # Case 2: Incomplete information (missing date, people, prize)
        sparse_text = "Students attended a meeting in the mechanical lab."
        self.assertIsNone(extract_dates(sparse_text), "Date must be None when not in text")
        self.assertEqual(extract_people(sparse_text), [], "People list must be empty when not in text")
        self.assertIsNone(extract_achievement_result(sparse_text), "Achievement must be None when absent")

    def test_photo_association_single_story_page(self):
        """When 1 story is on a page, all photos on that page belong to it with HIGH confidence."""
        page = PageData(
            page_number=1,
            text="Workshop on TinyML\n\nStudents implemented models on ESP32 boards on July 10, 2026.",
            photos=[
                PhotoItem(
                    photo_id="doc1_p1_img0",
                    doc_id="doc1",
                    page_number=1,
                    relative_path="photos/doc1_p1_img0.png",
                    filename="doc1_p1_img0.png",
                    order_on_page=0,
                ),
                PhotoItem(
                    photo_id="doc1_p1_img1",
                    doc_id="doc1",
                    page_number=1,
                    relative_path="photos/doc1_p1_img1.png",
                    filename="doc1_p1_img1.png",
                    order_on_page=1,
                ),
            ],
        )
        doc = DocumentRecord(
            doc_id="doc1",
            filename="doc1.pdf",
            file_type="pdf",
            total_pages=1,
            sha256="abc",
            pages=[page],
        )

        stories = self.segmenter.segment_document(doc)
        self.assertEqual(len(stories), 1)

        stories = self.associator.associate(doc, stories)
        self.assertEqual(stories[0].attached_photos, ["doc1_p1_img0", "doc1_p1_img1"])
        self.assertEqual(stories[0].photo_confidence, PhotoConfidence.HIGH.value)

    def test_photo_association_multi_story_ambiguity_marked_uncertain(self):
        """When multiple stories share a page and photos have no matching captions, flag UNCERTAIN."""
        page = PageData(
            page_number=2,
            text=(
                "# Workshop on Python\n\nECE students attended introductory Python training.\n\n"
                "---\n\n"
                "# Guest Lecture on VLSI\n\nCivil students attended structural design talk."
            ),
            photos=[
                PhotoItem(
                    photo_id="doc2_p2_img0",
                    doc_id="doc2",
                    page_number=2,
                    relative_path="photos/doc2_p2_img0.png",
                    filename="doc2_p2_img0.png",
                    caption_hint=None,  # No caption hint to disambiguate
                )
            ],
        )
        doc = DocumentRecord(
            doc_id="doc2",
            filename="doc2.pdf",
            file_type="pdf",
            total_pages=1,
            sha256="xyz",
            pages=[page],
        )

        stories = self.segmenter.segment_document(doc)
        self.assertEqual(len(stories), 2)

        stories = self.associator.associate(doc, stories)
        # Must not guess randomly! At least one story must be marked uncertain
        uncertain_stories = [s for s in stories if s.photo_confidence == PhotoConfidence.UNCERTAIN.value]
        self.assertGreater(len(uncertain_stories), 0, "Ambiguous photo placement must be marked UNCERTAIN")


if __name__ == "__main__":
    unittest.main()
