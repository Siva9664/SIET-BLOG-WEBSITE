"""CLI Script: Prepare, partition, and serialize versioned Magazine Training Dataset (Phase 8).

Run from backend directory with:
    PYTHONPATH=. .venv/bin/python scripts/prepare_magazine_dataset.py --output-dir datasets/magazine_v1.0.0 --version v1.0.0
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import List

from app.modules.datasets.magazine_dataset_generator import MagazineDatasetGenerator
from app.modules.datasets.magazine_dataset_schemas import (
    DatasetExample,
    DatasetSplitConfig,
)


def _write_jsonl(path: Path, examples: List[DatasetExample]) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    hasher = hashlib.sha256()
    with path.open("w", encoding="utf-8") as f:
        for ex in examples:
            line = ex.to_jsonl() + "\n"
            hasher.update(line.encode("utf-8"))
            f.write(line)
    return hasher.hexdigest()


def main():
    parser = argparse.ArgumentParser(description="Prepare SIET Magazine QLoRA Training Dataset")
    parser.add_argument(
        "--source-dir",
        type=str,
        default="uploads",
        help="Source directory containing DOCX/PDF reports and magazines (default: uploads)",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="datasets/magazine_v1.0.0",
        help="Destination directory for versioned JSONL splits and manifest",
    )
    parser.add_argument(
        "--version",
        type=str,
        default="v1.0.0",
        help="Dataset semantic version identifier (e.g. v1.0.0)",
    )
    parser.add_argument("--train-ratio", type=float, default=0.80, help="Train split ratio")
    parser.add_argument("--val-ratio", type=float, default=0.10, help="Validation split ratio")
    parser.add_argument("--test-ratio", type=float, default=0.10, help="Test split ratio")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for deterministic hashing")

    args = parser.parse_args()

    source_dir = Path(args.source_dir)
    output_dir = Path(args.output_dir)

    print(f"================================================================")
    print(f"SIET Magazine QLoRA Training Dataset Preparation (Phase 8)")
    print(f"================================================================")
    print(f"Source Directory: {source_dir.resolve()}")
    print(f"Output Directory: {output_dir.resolve()}")
    print(f"Dataset Version : {args.version}")
    print(f"Split Ratios    : Train={args.train_ratio}, Val={args.val_ratio}, Test={args.test_ratio}")

    split_config = DatasetSplitConfig(
        train_ratio=args.train_ratio,
        val_ratio=args.val_ratio,
        test_ratio=args.test_ratio,
        seed=args.seed,
    )

    generator = MagazineDatasetGenerator(
        dataset_version=args.version,
        split_config=split_config,
    )

    print("\n[1/4] Ingesting documents, magazines, and multi-lab exemplars...")
    examples = generator.generate_all_examples_from_sources(source_dir)
    print(f"  -> Generated {len(examples)} unique, deduplicated instruction examples.")

    print("\n[2/4] Deterministically partitioning examples into splits...")
    train_ex, val_ex, test_ex = generator.partition_examples(examples)
    print(f"  -> Train Split: {len(train_ex)} examples")
    print(f"  -> Val Split  : {len(val_ex)} examples")
    print(f"  -> Test Split : {len(test_ex)} examples")

    print("\n[3/4] Calculating dataset statistics and vocabulary metrics...")
    stats = generator.calculate_statistics(train_ex, val_ex, test_ex)

    print("\n[4/4] Writing JSONL files, manifest, and statistics...")
    train_path = output_dir / "train.jsonl"
    val_path = output_dir / "val.jsonl"
    test_path = output_dir / "test.jsonl"

    train_digest = _write_jsonl(train_path, train_ex)
    val_digest = _write_jsonl(val_path, val_ex)
    test_digest = _write_jsonl(test_path, test_ex)

    manifest = {
        "dataset_name": "siet_magazine_qlora_dataset",
        "dataset_version": args.version,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "total_examples": stats.total_examples,
        "split_counts": stats.split_counts,
        "task_counts": stats.task_counts,
        "files": {
            "train": {"file": "train.jsonl", "count": len(train_ex), "sha256": train_digest},
            "val": {"file": "val.jsonl", "count": len(val_ex), "sha256": val_digest},
            "test": {"file": "test.jsonl", "count": len(test_ex), "sha256": test_digest},
        },
        "config": split_config.model_dump(),
    }

    manifest_path = output_dir / "dataset_manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    stats_path = output_dir / "dataset_statistics.json"
    stats_path.write_text(json.dumps(stats.model_dump(), indent=2), encoding="utf-8")

    print("\nSUCCESS! Dataset prepared cleanly:")
    print(f"  - Train JSONL : {train_path} ({len(train_ex)} lines, sha256: {train_digest[:8]}...)")
    print(f"  - Val JSONL   : {val_path} ({len(val_ex)} lines, sha256: {val_digest[:8]}...)")
    print(f"  - Test JSONL  : {test_path} ({len(test_ex)} lines, sha256: {test_digest[:8]}...)")
    print(f"  - Manifest    : {manifest_path}")
    print(f"  - Statistics  : {stats_path}")
    print(f"\nTask Distribution:")
    for task_name, count in stats.task_counts.items():
        print(f"  * {task_name:<25}: {count}")


if __name__ == "__main__":
    main()
