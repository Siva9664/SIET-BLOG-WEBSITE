"""
Unit tests for dataset splitting and cross-document leakage prevention.
Tests:
- Deterministic train/validation/adversarial splits
- Guaranteed zero document-level leakage
- Adversarial hallucination resistance generation
"""

import json
import unittest

from ml.training.magazine.schemas import ExampleRecord
from ml.training.magazine.splitter import DatasetSplitter


class TestSplitterAndLeakage(unittest.TestCase):
    """Test suite for dataset splitting and leakage prevention."""

    def setUp(self):
        self.splitter = DatasetSplitter(val_ratio=0.20, seed=42)

    def _create_dummy_examples(self, doc_id: str, count: int) -> list[ExampleRecord]:
        examples = []
        for i in range(count):
            ex = ExampleRecord(
                messages=[
                    {"role": "system", "content": "You are SIET assistant."},
                    {"role": "user", "content": f"SOURCE CONTEXT:\nDoc {doc_id} story {i}.\n\nTASK: Rewrite."},
                    {"role": "assistant", "content": json.dumps({"headline": f"Story {i}", "body": "Details."})},
                ],
                metadata={
                    "doc_id": doc_id,
                    "page_start": i + 1,
                    "page_end": i + 1,
                    "story_id": f"{doc_id}_s{i}",
                    "task_type": "grounded_rewriting",
                },
            )
            examples.append(ex)
        return examples

    def test_multi_document_zero_leakage(self):
        """Examples from multiple documents must partition whole documents without overlap."""
        all_examples = []
        for d in range(1, 11):  # 10 documents
            all_examples.extend(self._create_dummy_examples(f"mag_vol_{d}", count=5))

        train_ex, val_ex, adv_ex = self.splitter.split(all_examples)

        train_docs = {e.metadata["doc_id"] for e in train_ex}
        val_docs = {e.metadata["doc_id"] for e in val_ex}

        self.assertGreater(len(train_docs), 0)
        self.assertGreater(len(val_docs), 0)

        # STRICT INVARIANT: ZERO OVERLAP BETWEEN TRAIN AND VAL
        overlap = train_docs.intersection(val_docs)
        self.assertEqual(len(overlap), 0, f"Critical document leakage between train and val: {overlap}")

        # Total examples preserved
        self.assertEqual(len(train_ex) + len(val_ex), len(all_examples))
        self.assertGreater(len(adv_ex), 0)

    def test_adversarial_suite_null_fields(self):
        """Adversarial examples must enforce null for missing metadata."""
        examples = self._create_dummy_examples("doc_adv", count=3)
        adv_suite = self.splitter.generate_adversarial_suite(examples)

        self.assertGreater(len(adv_suite), 0)
        for adv in adv_suite:
            self.assertEqual(adv.metadata["task_type"], "adversarial_grounding")
            asst_msg = next(m["content"] for m in adv.messages if m["role"] == "assistant")
            parsed = json.loads(asst_msg)
            # Verify missing fields are null/empty
            self.assertIsNone(parsed["date"])
            self.assertEqual(parsed["people"], [])
            self.assertIsNone(parsed["organization"])
            self.assertIsNone(parsed["achievement_result"])

    def test_leakage_detector_catches_contamination(self):
        """Verify that verify_no_leakage raises ValueError when contamination is injected."""
        train_examples = self._create_dummy_examples("doc_leak", count=2)
        val_examples = self._create_dummy_examples("doc_leak", count=1)  # Same doc in both!

        # Add other clean docs
        train_examples.extend(self._create_dummy_examples("doc_train_only", count=3))
        val_examples.extend(self._create_dummy_examples("doc_val_only", count=3))

        with self.assertRaises(ValueError):
            self.splitter.verify_no_leakage(train_examples, val_examples)


if __name__ == "__main__":
    unittest.main()
