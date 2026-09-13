"""Prepare, review, and finalize fact-extraction training JSONL datasets.

Run from backend with PYTHONPATH=. and the project virtual environment.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any, Iterable

from app.modules.analysis import analyze_document
from app.modules.datasets.fact_extraction import (
    CandidateGenerationError,
    finalize_examples,
    generate_candidate_facts,
    make_candidate_record,
    select_review_examples,
)
from app.modules.documents.chunker import chunk_document_spans
from app.modules.ingestion import document_to_spans, parse_document


SUPPORTED_SUFFIXES = {".pdf", ".docx", ".pptx", ".html", ".htm", ".txt", ".md"}


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError as error:
            raise ValueError(f"Invalid JSONL in {path} at line {line_number}.") from error
    return records


def _write_jsonl(path: Path, records: Iterable[dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as output:
        for record in records:
            output.write(json.dumps(record, ensure_ascii=False, sort_keys=True))
            output.write("\n")


def _source_files(source_dir: Path) -> list[Path]:
    return sorted(
        path
        for path in source_dir.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_SUFFIXES
    )


def prepare_chunks(
    source_dir: Path,
    *,
    target_chunk_size: int,
    overlap_size: int,
) -> tuple[list[dict[str, Any]], list[str]]:
    """Converts every supported source file into provenance-rich chunks."""
    chunks: list[dict[str, Any]] = []
    failures: list[str] = []
    for path in _source_files(source_dir):
        try:
            file_bytes = path.read_bytes()
            document = parse_document(file_bytes, path.name)
            analysis = analyze_document(document)
            spans = document_to_spans(document)
            document_chunks = chunk_document_spans(
                spans,
                target_chunk_size=target_chunk_size,
                overlap_size=overlap_size,
            )
            source_name = str(path.relative_to(source_dir))
            source_digest = hashlib.sha256(file_bytes).hexdigest()[:16]
            for chunk_index, chunk in enumerate(document_chunks):
                chunk_text = chunk["text"].strip()
                if len(chunk_text) < 40:
                    continue
                chunk_id = hashlib.sha256(
                    (
                        f"{source_digest}:{chunk_index}:{chunk['page_number']}:"
                        f"{chunk['char_start']}:{chunk['char_end']}"
                    ).encode("utf-8")
                ).hexdigest()[:20]
                chunks.append(
                    {
                        "id": f"chunk-{chunk_id}",
                        "text": chunk_text,
                        "provenance": {
                            "filename": source_name,
                            "document_type": document.document_type,
                            "page_number": chunk["page_number"],
                            "section_label": chunk.get("section_label"),
                            "char_start": chunk["char_start"],
                            "char_end": chunk["char_end"],
                            "structure": analysis.summary(),
                        },
                    }
                )
        except Exception as error:
            failures.append(f"{path}: {error}")
    return chunks, failures


async def generate_candidates(
    chunks: list[dict[str, Any]],
    output_path: Path,
    *,
    api_key: str,
    model: str,
) -> tuple[int, list[str]]:
    """Generates one candidate response per chunk and resumes from existing JSONL."""
    existing = _read_jsonl(output_path)
    completed_ids = {record["id"] for record in existing}
    records = list(existing)
    failures: list[str] = []

    for index, chunk in enumerate(chunks, 1):
        if chunk["id"] in completed_ids:
            continue
        try:
            facts = await generate_candidate_facts(
                chunk["text"],
                api_key=api_key,
                model=model,
            )
            records.append(make_candidate_record(chunk, facts, model=model))
            _write_jsonl(output_path, records)
            print(f"[{index}/{len(chunks)}] generated {chunk['id']} ({len(facts)} facts)")
        except CandidateGenerationError as error:
            failures.append(f"{chunk['id']}: {error}")
            print(f"[{index}/{len(chunks)}] failed {chunk['id']}: {error}")
    return len(records), failures


def _split_for_evaluation(
    examples: list[dict[str, Any]]
) -> tuple[list[dict[str, Any]], list[dict[str, Any]], list[dict[str, Any]]]:
    train: list[dict[str, Any]] = []
    validation: list[dict[str, Any]] = []
    evaluation: list[dict[str, Any]] = []
    for example in examples:
        bucket = int(hashlib.sha256(example["id"].encode("utf-8")).hexdigest(), 16) % 100
        if bucket < 80:
            train.append(example)
        elif bucket < 90:
            validation.append(example)
        else:
            evaluation.append(example)
    return train, validation, evaluation


def _cmd_prepare_chunks(args: argparse.Namespace) -> int:
    source_dir = Path(args.source_dir)
    if not source_dir.is_dir():
        raise ValueError(f"Source directory does not exist: {source_dir}")
    chunks, failures = prepare_chunks(
        source_dir,
        target_chunk_size=args.chunk_size,
        overlap_size=args.overlap_size,
    )
    _write_jsonl(Path(args.output), chunks)
    print(f"Prepared {len(chunks)} chunks from {len(_source_files(source_dir))} source files.")
    for failure in failures:
        print(f"FAILED: {failure}")
    return 1 if failures else 0


def _cmd_generate_candidates(args: argparse.Namespace) -> int:
    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY") or ""
    if not api_key:
        raise CandidateGenerationError(
            "Set GEMINI_API_KEY or GOOGLE_API_KEY before generating candidates."
        )
    chunks = _read_jsonl(Path(args.chunks))
    if not chunks:
        raise ValueError("No source chunks were found.")
    count, failures = asyncio.run(
        generate_candidates(
            chunks,
            Path(args.output),
            api_key=api_key,
            model=args.model,
        )
    )
    print(f"Candidate dataset now contains {count} examples.")
    for failure in failures:
        print(f"FAILED: {failure}")
    return 1 if failures else 0


def _cmd_prepare_review(args: argparse.Namespace) -> int:
    candidates = _read_jsonl(Path(args.candidates))
    reviews = select_review_examples(candidates, args.fraction)
    _write_jsonl(Path(args.output), reviews)
    print(
        f"Prepared {len(reviews)} review examples from {len(candidates)} candidates "
        f"({args.fraction:.0%} sample)."
    )
    return 0


def _cmd_finalize(args: argparse.Namespace) -> int:
    candidates = _read_jsonl(Path(args.candidates))
    reviews = _read_jsonl(Path(args.reviews))
    examples = finalize_examples(
        candidates,
        reviews,
        minimum_review_fraction=args.minimum_review_fraction,
    )
    _write_jsonl(Path(args.output), examples)
    train, validation, evaluation = _split_for_evaluation(examples)
    output_dir = Path(args.output).parent
    _write_jsonl(output_dir / "fact_extraction_train.jsonl", train)
    _write_jsonl(output_dir / "fact_extraction_validation.jsonl", validation)
    _write_jsonl(output_dir / "fact_extraction_evaluation.jsonl", evaluation)
    print(
        f"Finalized {len(examples)} examples: {len(train)} train, "
        f"{len(validation)} validation, {len(evaluation)} evaluation."
    )
    return 0


def _cmd_report(args: argparse.Namespace) -> int:
    candidates = _read_jsonl(Path(args.candidates))
    reviews = _read_jsonl(Path(args.reviews)) if args.reviews else []
    completed = sum(
        1
        for review in reviews
        if review.get("review", {}).get("status") == "completed"
    )
    facts = sum(len(record.get("candidate_facts", [])) for record in candidates)
    print(f"Candidate examples: {len(candidates)}")
    print(f"Candidate facts: {facts}")
    print(f"Completed reviews: {completed}/{len(candidates)}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Prepare fact-extraction JSONL data without local model training."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    prepare = subparsers.add_parser("prepare-chunks")
    prepare.add_argument("source_dir")
    prepare.add_argument("--output", required=True)
    prepare.add_argument("--chunk-size", type=int, default=1000)
    prepare.add_argument("--overlap-size", type=int, default=120)
    prepare.set_defaults(func=_cmd_prepare_chunks)

    generate = subparsers.add_parser("generate-candidates")
    generate.add_argument("--chunks", required=True)
    generate.add_argument("--output", required=True)
    generate.add_argument("--model", default="gemini-2.5-flash")
    generate.set_defaults(func=_cmd_generate_candidates)

    review = subparsers.add_parser("prepare-review")
    review.add_argument("--candidates", required=True)
    review.add_argument("--output", required=True)
    review.add_argument("--fraction", type=float, default=0.25)
    review.set_defaults(func=_cmd_prepare_review)

    finalize = subparsers.add_parser("finalize")
    finalize.add_argument("--candidates", required=True)
    finalize.add_argument("--reviews", required=True)
    finalize.add_argument("--output", required=True)
    finalize.add_argument("--minimum-review-fraction", type=float, default=0.25)
    finalize.set_defaults(func=_cmd_finalize)

    report = subparsers.add_parser("report")
    report.add_argument("--candidates", required=True)
    report.add_argument("--reviews")
    report.set_defaults(func=_cmd_report)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
