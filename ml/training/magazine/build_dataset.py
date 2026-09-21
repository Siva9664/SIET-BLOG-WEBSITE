"""
Scalable Magazine Training Dataset Builder CLI for Qwen3-14B SIET fine-tuning.

Converts real college magazines, reports, and templates into high-quality
supervised training examples with strict source provenance, event-photo grouping,
and zero hallucinations.
"""

from __future__ import annotations

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional

from .schemas import (
    DocumentRecord,
    StorySegment,
    PhotoItem,
    ExampleRecord,
    AdminFeedbackRecord,
    QualityReport,
)
from .ingestion import DocumentIngestion
from .segmenter import StorySegmenter
from .photo_associator import PhotoAssociator
from .example_builder import ExampleBuilder
from .grounding import GroundingAuditor
from .deduplicator import Deduplicator
from .splitter import DatasetSplitter
from .stats import StatsAggregator, DatasetStatistics
from .quality_gates import QualityGateManager


def setup_directory_structure(base_dir: Path) -> Dict[str, Path]:
    """Ensures all standard dataset directories exist."""
    dirs = {
        "raw_magazines": base_dir / "raw" / "magazines",
        "raw_reports": base_dir / "raw" / "reports",
        "raw_templates": base_dir / "raw" / "templates",
        "processed_events": base_dir / "processed" / "events",
        "processed_victories": base_dir / "processed" / "victories",
        "processed_achievements": base_dir / "processed" / "achievements",
        "processed_projects": base_dir / "processed" / "projects",
        "processed_faculty": base_dir / "processed" / "faculty",
        "processed_other": base_dir / "processed" / "other",
        "photos": base_dir / "photos",
        "examples": base_dir / "examples",
        "final": base_dir / "final",
    }
    for d in dirs.values():
        d.mkdir(parents=True, exist_ok=True)
    return dirs


def map_story_type_to_processed_dir(story_type: str, dirs: Dict[str, Path]) -> Path:
    """Maps a story type category to its designated processed subdirectory."""
    mapping = {
        "events": dirs["processed_events"],
        "victories": dirs["processed_victories"],
        "achievements": dirs["processed_achievements"],
        "projects": dirs["processed_projects"],
        "faculty": dirs["processed_faculty"],
    }
    return mapping.get(story_type, dirs["processed_other"])


class MagazineDatasetBuilder:
    """
    End-to-end dataset builder pipeline.
    """

    def __init__(
        self,
        input_path: Path,
        output_path: Path,
        val_ratio: float = 0.15,
        seed: int = 42,
        dry_run: bool = False,
    ):
        self.input_path = Path(input_path)
        self.output_path = Path(output_path)
        self.val_ratio = val_ratio
        self.seed = seed
        self.dry_run = dry_run

        self.dirs = setup_directory_structure(self.output_path)
        self.ingestion = DocumentIngestion(photos_output_dir=self.dirs["photos"] if not dry_run else None)
        self.segmenter = StorySegmenter()
        self.associator = PhotoAssociator()
        self.example_builder = ExampleBuilder()
        self.grounding_auditor = GroundingAuditor()
        self.deduplicator = Deduplicator()
        self.splitter = DatasetSplitter(val_ratio=val_ratio, seed=seed)
        self.quality_manager = QualityGateManager(grounding_auditor=self.grounding_auditor)
        self.stats_aggregator = StatsAggregator()

    def discover_source_files(self) -> List[Path]:
        """Finds all supported documents in input path."""
        supported_exts = {".pdf", ".docx", ".docm", ".txt", ".md", ".json"}
        if self.input_path.is_file():
            return [self.input_path] if self.input_path.suffix.lower() in supported_exts else []

        found = []
        if self.input_path.exists():
            for p in self.input_path.rglob("*"):
                if p.is_file() and p.suffix.lower() in supported_exts:
                    found.append(p)
        return sorted(found)

    def run(self, validate: bool = True, show_stats: bool = True) -> Tuple[DatasetStatistics, QualityReport]:
        print(f"=== SIET Magazine Training Dataset Builder ===")
        print(f"Input:   {self.input_path}")
        print(f"Output:  {self.output_path}")
        print(f"Dry Run: {self.dry_run}\n")

        files = self.discover_source_files()
        print(f"Found {len(files)} source document(s).")

        # 1. Ingestion
        documents: List[DocumentRecord] = []
        all_photos_map: Dict[str, PhotoItem] = {}

        for f in files:
            try:
                doc = self.ingestion.ingest_file(f)
                documents.append(doc)
                for page in doc.pages:
                    for photo in page.photos:
                        all_photos_map[photo.photo_id] = photo
            except Exception as e:
                print(f"[Warning] Skipping {f.name} due to ingestion error: {e}")

        # 2. Segmentation & Photo Association
        all_stories: List[StorySegment] = []
        for doc in documents:
            doc_stories = self.segmenter.segment_document(doc)
            # Associate photos strictly with stories
            doc_stories = self.associator.associate(doc, doc_stories)
            all_stories.extend(doc_stories)

        print(f"Ingested {len(documents)} document(s) across {sum(d.total_pages for d in documents)} page(s).")
        print(f"Segmented {len(all_stories)} distinct story/event block(s).")
        print(f"Extracted {len(all_photos_map)} photo(s).")

        # Save processed stories to disk if not dry_run
        if not self.dry_run:
            for s in all_stories:
                dest_dir = map_story_type_to_processed_dir(s.story_type, self.dirs)
                dest_file = dest_dir / f"{s.story_id}.json"
                dest_file.write_text(json.dumps(s.to_dict(), indent=2), encoding="utf-8")

        # 3. Build SFT Examples
        editorial_examples: List[ExampleRecord] = []
        template_examples: List[ExampleRecord] = []
        layout_examples: List[ExampleRecord] = []
        photo_examples: List[ExampleRecord] = []
        admin_feedback_examples: List[ExampleRecord] = []

        for s in all_stories:
            editorial_examples.extend(self.example_builder.build_editorial_examples(s))
            template_examples.extend(self.example_builder.build_template_examples(s))
            layout_examples.extend(self.example_builder.build_layout_examples(s))
            photo_examples.extend(self.example_builder.build_photo_examples(s, all_photos_map))

        # Check for admin feedback entries
        admin_feedback_dir = self.input_path / "admin_feedback"
        if admin_feedback_dir.exists():
            for fb_file in admin_feedback_dir.glob("*.json"):
                try:
                    data = json.loads(fb_file.read_text(encoding="utf-8"))
                    record = AdminFeedbackRecord.from_dict(data)
                    ex = self.example_builder.build_admin_feedback_example(record)
                    if ex:
                        admin_feedback_examples.append(ex)
                except Exception:
                    pass

        # Write categorized example files if not dry_run
        if not self.dry_run:
            self._write_jsonl(self.dirs["examples"] / "editorial.jsonl", editorial_examples)
            self._write_jsonl(self.dirs["examples"] / "template.jsonl", template_examples)
            self._write_jsonl(self.dirs["examples"] / "layout.jsonl", layout_examples)
            self._write_jsonl(self.dirs["examples"] / "photo.jsonl", photo_examples)
            self._write_jsonl(self.dirs["examples"] / "admin_feedback.jsonl", admin_feedback_examples)

        all_candidate_examples = (
            editorial_examples + template_examples + layout_examples + photo_examples + admin_feedback_examples
        )

        # 4. Deduplication
        unique_examples, dup_count = self.deduplicator.filter_examples(all_candidate_examples)
        print(f"Generated {len(all_candidate_examples)} total example(s), {dup_count} exact duplicate(s) filtered.")

        # 5. Split Dataset (Document-Level Leakage Prevention)
        train_ex, val_ex, adv_ex = self.splitter.split(unique_examples)
        print(f"Splits: Train={len(train_ex)}, Val={len(val_ex)}, Adversarial={len(adv_ex)}")

        # 6. Quality Gates & Validation
        quality_report = self.quality_manager.evaluate(
            examples=unique_examples,
            train_examples=train_ex,
            val_examples=val_ex,
            stories=all_stories,
            duplicate_count=dup_count,
        )

        # 7. Write final dataset files
        if not self.dry_run:
            self._write_jsonl(self.dirs["final"] / "train.jsonl", train_ex)
            self._write_jsonl(self.dirs["final"] / "validation.jsonl", val_ex)
            self._write_jsonl(self.dirs["final"] / "adversarial.jsonl", adv_ex)
            print(f"[✓] Final training files written to {self.dirs['final']}")

        # 8. Compute Statistics
        stats = self.stats_aggregator.compute(
            documents=documents,
            stories=all_stories,
            all_examples=unique_examples,
            train_examples=train_ex,
            val_examples=val_ex,
            adversarial_examples=adv_ex,
            exact_duplicates=dup_count,
            grounding_failures=quality_report.grounding_failed,
        )

        if show_stats:
            print("\n" + stats.to_markdown())

        if not self.dry_run:
            stats_json_path = self.output_path / "stats.json"
            stats_md_path = self.output_path / "stats.md"
            stats_json_path.write_text(json.dumps(stats.to_dict(), indent=2), encoding="utf-8")
            stats_md_path.write_text(stats.to_markdown(), encoding="utf-8")

        # Quality Gate Assessment
        if validate:
            print("\n=== Quality Gate Assessment ===")
            if quality_report.passed_all_gates:
                print("[✓] ALL QUALITY GATES PASSED: Zero grounding failures, zero leakage, valid provenance.")
            else:
                print(f"[!] QUALITY GATE FAILURES ({len(quality_report.errors)} error(s)):")
                for err in quality_report.errors[:10]:
                    print(f"  - {err}")
                if not self.dry_run:
                    print("[!] Please resolve quality issues before using dataset for QLoRA.")

        return stats, quality_report

    def _write_jsonl(self, path: Path, examples: List[ExampleRecord]) -> None:
        with open(path, "w", encoding="utf-8") as f:
            for ex in examples:
                f.write(ex.to_json() + "\n")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scalable Magazine Training Dataset Builder for SIET College Magazine Fine-Tuning"
    )
    parser.add_argument(
        "--input",
        type=str,
        default="ml/datasets/magazine/raw",
        help="Path to input raw documents directory or file",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="ml/datasets/magazine",
        help="Path to output dataset root directory",
    )
    parser.add_argument(
        "--validate",
        action="store_true",
        default=True,
        help="Run strict quality gates and grounding validation (default: True)",
    )
    parser.add_argument(
        "--stats",
        action="store_true",
        default=True,
        help="Generate and print comprehensive dataset statistics report (default: True)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        default=False,
        help="Execute extraction and validation without persisting final dataset files",
    )
    parser.add_argument(
        "--val-ratio",
        type=float,
        default=0.15,
        help="Validation split ratio (default: 0.15)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=42,
        help="Random seed for deterministic splits",
    )
    return parser


def main() -> int:
    parser = build_arg_parser()
    args = parser.parse_args()

    builder = MagazineDatasetBuilder(
        input_path=Path(args.input),
        output_path=Path(args.output),
        val_ratio=args.val_ratio,
        seed=args.seed,
        dry_run=args.dry_run,
    )

    stats, quality_report = builder.run(validate=args.validate, show_stats=args.stats)

    if args.validate and not quality_report.passed_all_gates:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
