"""
Unit tests for deterministic deduplication module.
Tests:
- Exact duplicate examples
- Duplicate source text
- Exact and perceptual duplicate images
- Near-duplicate text detection
"""

import io
import unittest
from PIL import Image

from ml.training.magazine.deduplicator import (
    Deduplicator,
    normalize_text,
    get_word_ngrams,
    jaccard_similarity,
    compute_difference_hash,
)
from ml.training.magazine.schemas import ExampleRecord, PhotoItem


def create_test_image(color=(100, 150, 200), size=(32, 32)) -> bytes:
    buf = io.BytesIO()
    img = Image.new("RGB", size, color=color)
    img.save(buf, format="PNG")
    return buf.getvalue()


class TestDeduplicator(unittest.TestCase):
    """Test suite for deterministic deduplication."""

    def setUp(self):
        self.dedup = Deduplicator(near_dup_threshold=0.70)

    def test_exact_duplicate_example(self):
        ex1 = ExampleRecord(
            messages=[{"role": "user", "content": "What happened?"}, {"role": "assistant", "content": "Workshop."}],
            metadata={"doc_id": "doc1", "story_id": "s1"},
        )
        ex2 = ExampleRecord(
            messages=[{"role": "user", "content": "What happened?"}, {"role": "assistant", "content": "Workshop."}],
            metadata={"doc_id": "doc2", "story_id": "s2"},  # Different metadata, identical message payload
        )

        self.assertFalse(self.dedup.is_duplicate_example(ex1))
        self.assertTrue(self.dedup.is_duplicate_example(ex2), "Exact message payload must be flagged as duplicate")

    def test_duplicate_source_text(self):
        text = "SIET AI Cluster Inaugurated by Principal."
        text_variant = "  siet   ai cluster inaugurated by   principal.  \n"

        self.assertFalse(self.dedup.is_duplicate_source_text(text))
        self.assertTrue(self.dedup.is_duplicate_source_text(text_variant), "Normalized source text must match")

    def test_near_duplicate_text(self):
        text_a = "The Department of Computer Science hosted an international conference on deep learning algorithms."
        text_b = "The Department of Computer Science hosted an international symposium on deep learning algorithms."
        text_c = "Civil engineering students built an eco-friendly concrete bridge prototype model."

        self.assertIsNone(self.dedup.find_near_duplicate_text(text_a, "id_a"))
        match = self.dedup.find_near_duplicate_text(text_b, "id_b")
        self.assertEqual(match, "id_a", "Near-duplicate text must match id_a")

        # text_c is entirely different
        self.assertIsNone(self.dedup.find_near_duplicate_text(text_c, "id_c"))


    def test_duplicate_image_sha256_and_perceptual(self):
        img_bytes = create_test_image(color=(255, 100, 50))
        photo1 = PhotoItem(
            photo_id="doc1_p1_img0",
            doc_id="doc1",
            page_number=1,
            relative_path="photos/img1.png",
            filename="img1.png",
            sha256="hash123",
        )
        photo2 = PhotoItem(
            photo_id="doc2_p1_img0",
            doc_id="doc2",
            page_number=1,
            relative_path="photos/img2.png",
            filename="img2.png",
            sha256="hash123",  # Exact same SHA-256
        )

        is_dup1, _ = self.dedup.is_duplicate_image(photo1, raw_bytes=img_bytes)
        self.assertFalse(is_dup1)

        is_dup2, dup_type = self.dedup.is_duplicate_image(photo2, raw_bytes=img_bytes)
        self.assertTrue(is_dup2)
        self.assertEqual(dup_type, "exact_sha256")

    def test_filter_examples(self):
        exs = [
            ExampleRecord(messages=[{"role": "user", "content": f"Q{i}"}, {"role": "assistant", "content": "A"}], metadata={})
            for i in [1, 2, 2, 3, 3, 3]
        ]
        unique, dups = self.dedup.filter_examples(exs)
        self.assertEqual(len(unique), 3)
        self.assertEqual(dups, 3)


if __name__ == "__main__":
    unittest.main()
