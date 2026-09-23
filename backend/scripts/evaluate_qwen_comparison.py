"""CLI Script: Head-to-Head Comparison: BASE QWEN vs FINE-TUNED QWEN (Phase 9).

Evaluates on the held-out test split and writes JSON and Markdown benchmark reports.

Run with:
    PYTHONPATH=. .venv/bin/python scripts/evaluate_qwen_comparison.py --test-file datasets/magazine_v1.0.0/test.jsonl --adapter-dir models/siet-qwen-magazine-v1.0.0
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from app.modules.datasets.qwen_evaluator import MagazineQwenEvaluator


def main():
    parser = argparse.ArgumentParser(description="Evaluate Base Qwen vs Fine-Tuned Qwen on held-out test set")
    parser.add_argument(
        "--test-file",
        type=str,
        default="datasets/magazine_v1.0.0/test.jsonl",
        help="Path to held-out test split JSONL",
    )
    parser.add_argument(
        "--adapter-dir",
        type=str,
        default="models/siet-qwen-magazine-v1.0.0",
        help="Path to fine-tuned adapter directory",
    )
    parser.add_argument(
        "--output-file",
        type=str,
        default="models/siet-qwen-magazine-v1.0.0/evaluation_comparison_report.json",
        help="Destination path for evaluation JSON report",
    )

    args = parser.parse_args()
    test_path = Path(args.test_file)
    adapter_path = Path(args.adapter_dir)
    output_path = Path(args.output_file)

    print("================================================================")
    print("SIET Magazine Model Evaluation: BASE QWEN vs FINE-TUNED QWEN")
    print("================================================================")
    print(f"Test Dataset Split: {test_path.resolve()}")
    print(f"Adapter Directory : {adapter_path.resolve()}")

    evaluator = MagazineQwenEvaluator(adapter_path, test_path)
    report = evaluator.evaluate()

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report.model_dump(), indent=2), encoding="utf-8")

    bm = report.base_qwen_metrics
    fm = report.finetuned_qwen_metrics

    print("\nBenchmark Comparison Results (Held-Out Test Set):")
    print("-------------------------------------------------------------------------------------")
    print(f"{'Evaluation Metric':<35} | {'Base Qwen':<15} | {'Fine-Tuned Qwen':<16} | {'Delta':<10}")
    print("-------------------------------------------------------------------------------------")
    print(f"{'JSON Syntax Validity Rate':<35} | {bm.json_validity_rate:>13.1f}% | {fm.json_validity_rate:>14.1f}% | {report.improvements.get('json_validity_rate_gain', 0.0):>+8.1f}%")
    print(f"{'Headline Word Budget Compliance':<35} | {bm.headline_word_budget_compliance:>13.1f}% | {fm.headline_word_budget_compliance:>14.1f}% | {report.improvements.get('headline_compliance_gain', 0.0):>+8.1f}%")
    print(f"{'Caption Word Budget Compliance':<35} | {bm.caption_word_budget_compliance:>13.1f}% | {fm.caption_word_budget_compliance:>14.1f}% | {report.improvements.get('caption_compliance_gain', 0.0):>+8.1f}%")
    print(f"{'Section Classification Accuracy':<35} | {bm.section_classification_accuracy:>13.1f}% | {fm.section_classification_accuracy:>14.1f}% | {report.improvements.get('section_accuracy_gain', 0.0):>+8.1f}%")
    print(f"{'Template Selection Accuracy':<35} | {bm.template_selection_accuracy:>13.1f}% | {fm.template_selection_accuracy:>14.1f}% | {report.improvements.get('template_accuracy_gain', 0.0):>+8.1f}%")
    print(f"{'House Style & Tone Alignment':<35} | {bm.house_style_alignment_score:>13.1f}% | {fm.house_style_alignment_score:>14.1f}% | {fm.house_style_alignment_score - bm.house_style_alignment_score:>+8.1f}%")
    print("-------------------------------------------------------------------------------------")
    print(f"{'OVERALL COMPOSITE SCORE':<35} | {bm.overall_score:>13.1f}% | {fm.overall_score:>14.1f}% | {report.improvements.get('overall_score_gain', 0.0):>+8.1f}%")
    print("-------------------------------------------------------------------------------------")
    print(f"\nSummary: {report.summary}")
    print(f"Report serialized to: {output_path.resolve()}\n")


if __name__ == "__main__":
    main()
