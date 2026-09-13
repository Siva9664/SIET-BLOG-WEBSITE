import pytest
from app.modules.magazine.fact_evaluator import (
    evaluate_fact_grounding,
    gate_extracted_facts,
)

SOURCE_PASSAGE = """
SIET INTERNATIONAL ENGINEERING & INNOVATION SYMPOSIUM 2026
Date: August 30, 2026
Location: Main Auditorium & Advanced AI Labs, Sri Shakthi Institute of Engineering and Technology (SIET), Coimbatore.

Executive Overview:
Sri Shakthi Institute of Engineering and Technology hosted the International Engineering & Innovation Symposium 2026.
The event brought together over 350 undergraduate researchers, 40 faculty delegates, and 15 industry keynote speakers.
Opening Keynote was delivered by Dr. S. Sharma (Head of AI & Autonomous Systems at Apex Robotics), who highlighted high-precision neural architecture search for edge robotics.

Key Project Models & Paper Presentations:
1. Team QuadRobo (1st Place Winner, ₹75,000 award): Autonomous quadruped legged robot using real-time spatial vision and low-latency motor microcontrollers.
2. Team VoltGrid (Runner-Up, ₹30,000 award): Smart micro-grid load balancer capable of predicting transformer thermal overloads using quantized edge neural networks.
3. Team NeuralCrop: Handheld diagnostic camera for early plant disease detection operating completely offline.

Jury Remarks:
Dr. S. Sharma commended SIET students for bridging theoretical control theory with robust, field-deployable hardware.
SIET Incubation Cell announced ₹500,000 in seed assistance for patenting and commercial scaling of the top 3 projects.
"""

VALID_FACTS = [
    {
        "subject": "Team QuadRobo",
        "predicate": "awarded",
        "object": "1st Place Winner, ₹75,000 award",
        "evidence": "Team QuadRobo (1st Place Winner, ₹75,000 award): Autonomous quadruped legged robot",
    },
    {
        "subject": "Dr. S. Sharma",
        "predicate": "delivered",
        "object": "Opening Keynote",
        "evidence": "Opening Keynote was delivered by Dr. S. Sharma (Head of AI & Autonomous Systems at Apex Robotics)",
    },
    {
        "subject": "The event",
        "predicate": "brought together",
        "object": "over 350 undergraduate researchers",
        "evidence": "The event brought together over 350 undergraduate researchers, 40 faculty delegates, and 15 industry keynote speakers.",
    },
    {
        "subject": "SIET Incubation Cell",
        "predicate": "announced",
        "object": "₹500,000 in seed assistance",
        "evidence": "SIET Incubation Cell announced ₹500,000 in seed assistance for patenting and commercial scaling of the top 3 projects.",
    },
    {
        "subject": "Symposium Date",
        "predicate": "was held on",
        "object": "August 30, 2026",
        "evidence": "Date: August 30, 2026",
    },
]

CORRUPTED_FACTS = [
    # 1. Altered prize amount
    {
        "subject": "Team QuadRobo",
        "predicate": "awarded",
        "object": "1st Place Winner, ₹150,000 award",
        "evidence": "Team QuadRobo (1st Place Winner, ₹150,000 award): Autonomous quadruped legged robot",
    },
    # 2. Altered team name
    {
        "subject": "Team CyberBot",
        "predicate": "awarded",
        "object": "1st Place Winner, ₹75,000 award",
        "evidence": "Team CyberBot (1st Place Winner, ₹75,000 award): Autonomous quadruped legged robot",
    },
    # 3. Altered keynote speaker name
    {
        "subject": "Dr. K. Patel",
        "predicate": "delivered",
        "object": "Opening Keynote",
        "evidence": "Opening Keynote was delivered by Dr. K. Patel",
    },
    # 4. Altered company name
    {
        "subject": "Dr. S. Sharma",
        "predicate": "headed AI at",
        "object": "Apex Dynamics",
        "evidence": "Dr. S. Sharma (Head of AI & Autonomous Systems at Apex Dynamics)",
    },
    # 5. Altered date (month)
    {
        "subject": "Symposium Date",
        "predicate": "was held on",
        "object": "December 15, 2026",
        "evidence": "Date: December 15, 2026",
    },
    # 6. Altered student attendee count
    {
        "subject": "The event",
        "predicate": "brought together",
        "object": "over 1,200 undergraduate researchers",
        "evidence": "The event brought together over 1,200 undergraduate researchers",
    },
    # 7. Altered faculty delegate count
    {
        "subject": "Faculty delegates",
        "predicate": "attended count was",
        "object": "150 faculty delegates",
        "evidence": "The event brought together over 350 undergraduate researchers, 150 faculty delegates",
    },
    # 8. Altered runner up amount
    {
        "subject": "Team VoltGrid",
        "predicate": "awarded",
        "object": "Runner-Up, ₹90,000 award",
        "evidence": "Team VoltGrid (Runner-Up, ₹90,000 award): Smart micro-grid load balancer",
    },
    # 9. Altered team name (runner up)
    {
        "subject": "Team VoltX",
        "predicate": "awarded",
        "object": "Runner-Up, ₹30,000 award",
        "evidence": "Team VoltX (Runner-Up, ₹30,000 award): Smart micro-grid load balancer",
    },
    # 10. Altered seed grant amount
    {
        "subject": "SIET Incubation Cell",
        "predicate": "announced",
        "object": "₹950,000 in seed assistance",
        "evidence": "SIET Incubation Cell announced ₹950,000 in seed assistance",
    },
]


def test_evaluator_valid_facts():
    for fact in VALID_FACTS:
        res = evaluate_fact_grounding(SOURCE_PASSAGE, fact)
        assert res.is_grounded is True, f"Valid fact was rejected: {fact}, issues: {res.issues}"
        assert res.verdict == "VALID"


def test_evaluator_corrupted_facts_catch_rate():
    caught = 0
    total = len(CORRUPTED_FACTS)

    for fact in CORRUPTED_FACTS:
        res = evaluate_fact_grounding(SOURCE_PASSAGE, fact)
        if not res.is_grounded and res.verdict in ("CORRUPTED", "UNSUPPORTED"):
            caught += 1
            print(f"Caught corruption in '{fact['subject']}': {res.issues}")
        else:
            print(f"MISSED corruption in '{fact['subject']}'!")

    catch_rate = (caught / total) * 100
    print(f"\nDeliberate Corruption Catch Rate: {caught}/{total} ({catch_rate:.1f}%)")
    assert catch_rate >= 85.0, f"Catch rate {catch_rate:.1f}% below 85% requirement"


def test_evaluator_gating_filter():
    mixed_facts = VALID_FACTS + CORRUPTED_FACTS
    accepted, dropped = gate_extracted_facts(SOURCE_PASSAGE, mixed_facts)

    assert len(accepted) == len(VALID_FACTS), f"Expected {len(VALID_FACTS)} accepted, got {len(accepted)}"
    assert len(dropped) == len(CORRUPTED_FACTS), f"Expected {len(CORRUPTED_FACTS)} dropped, got {len(dropped)}"

    for f in dropped:
        assert f["evaluation"]["is_grounded"] is False
        assert f["evaluation"]["verdict"] in ("CORRUPTED", "UNSUPPORTED")
