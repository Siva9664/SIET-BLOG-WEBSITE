import json

import pytest

from app.modules.datasets.fact_extraction import (
    build_training_example,
    finalize_examples,
    parse_candidate_facts,
    select_review_examples,
)


def _candidate_record() -> dict:
    facts = parse_candidate_facts(
        json.dumps(
            {
                "facts": [
                    {
                        "subject": "The AI Lab",
                        "predicate": "hosted",
                        "object": "42 students",
                        "qualifiers": {},
                        "fact_type": "quantity",
                        "evidence": "The AI Lab hosted 42 students.",
                    }
                ]
            }
        ),
        "The AI Lab hosted 42 students.",
    )
    return {
        "id": "chunk-one",
        "source": {
            "text": "The AI Lab hosted 42 students.",
            "provenance": {"filename": "report.html", "page_number": 1},
        },
        "candidate_facts": facts,
        "generation": {"model": "gemini-test"},
    }


def test_candidate_fact_parser_rejects_unsupported_evidence():
    facts = parse_candidate_facts(
        json.dumps(
            {
                "facts": [
                    {
                        "subject": "The AI Lab",
                        "predicate": "won",
                        "object": "an award",
                        "evidence": "The AI Lab won an award.",
                    }
                ]
            }
        ),
        "The AI Lab hosted 42 students.",
    )
    assert facts == []


def test_review_selection_is_deterministic_and_marks_decisions_pending():
    candidates = [_candidate_record() | {"id": f"chunk-{index}"} for index in range(4)]

    reviews = select_review_examples(candidates, fraction=0.25)

    assert len(reviews) == 1
    assert reviews[0]["review"]["status"] == "pending"
    assert reviews[0]["review"]["fact_decisions"][0]["decision"] == "pending"


def test_finalize_requires_spot_check_then_builds_chat_jsonl_example():
    candidate = _candidate_record()
    review = select_review_examples([candidate])[0]

    with pytest.raises(ValueError, match="completed reviews"):
        finalize_examples([candidate], [review])

    review["review"]["status"] = "completed"
    review["review"]["fact_decisions"][0]["decision"] = "accept"
    examples = finalize_examples([candidate], [review])

    assert len(examples) == 1
    assert examples[0]["metadata"]["review_status"] == "spot_checked"
    assert json.loads(examples[0]["messages"][1]["content"])["facts"][0]["object"] == "42 students"


def test_build_training_example_marks_non_sampled_examples():
    example = build_training_example(_candidate_record())

    assert example["metadata"]["review_status"] == "not_sampled"
