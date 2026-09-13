"""Isolated unit tests for SigLIP evaluation suite.
Ensures benchmark dataset integrity, environment auditing, and vector math.
Does not alter production backend tests.
"""

from pathlib import Path
import shutil
import sys
import tempfile
import unittest
from pathlib import Path
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent))
from dataset import CATEGORIES, load_benchmark_dataset
from benchmark import audit_environment, extract_features


class TestSigLIPEvaluation(unittest.TestCase):
    def test_benchmark_categories_count_and_structure(self):
        """Verify all 10 college event categories are defined with ground truth and distractors."""
        self.assertEqual(len(CATEGORIES), 10)
        required_keys = {"id", "name", "ground_truth", "distractors"}
        for cat in CATEGORIES:
            self.assertTrue(required_keys.issubset(cat.keys()))
            self.assertGreater(len(cat["ground_truth"]), 10)
            self.assertGreaterEqual(len(cat["distractors"]), 3)

    def test_benchmark_dataset_generation_and_loading(self):
        """Verify synthetic benchmark dataset creates valid images and items on disk."""
        tmp_dir = Path(tempfile.mkdtemp())
        try:
            items = load_benchmark_dataset(tmp_dir)
            self.assertEqual(len(items), 10)
            for item in items:
                self.assertTrue(Path(item.image_filename).exists())
                self.assertEqual(len(item.candidate_texts), len(item.distractor_texts) + 1)
                self.assertEqual(item.candidate_texts[0], item.ground_truth_text)
        finally:
            shutil.rmtree(tmp_dir)

    def test_audit_environment(self):
        """Verify hardware environment audit produces expected schema."""
        audit = audit_environment()
        self.assertIn("python_version", audit)
        self.assertIn("pytorch_version", audit)
        self.assertIn("cuda_available", audit)
        self.assertIn("device_name", audit)
        self.assertIn("total_vram_gb", audit)

    def test_extract_features_mock(self):
        """Verify extract_features extracts tensor from simulated output."""
        class MockOutput:
            pooler_output = torch.randn(2, 768)

        class MockModel:
            def get_image_features(self, **kwargs):
                return MockOutput()

        self.assertEqual(extract_features(MockModel(), {}, is_image=True).shape, (2, 768))


if __name__ == "__main__":
    unittest.main()
