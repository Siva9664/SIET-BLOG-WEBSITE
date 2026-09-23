"""
Automated Test Suite for End-of-Event Photo Association,
Strict Photo Isolation, and Automatic Separate Photo Matching.
"""

import io
import os
import pytest
import pymupdf  # fitz
from PIL import Image
from typing import Dict, Any, List

from app.modules.magazine.event_segmenter import (
    segment_pdf_events,
    group_events_into_editorial_stories,
    MagazineEvent,
    MagazineSource,
)
from app.modules.magazine.photo_associator import PhotoAssociator
from app.modules.magazine.advanced_validator import AdvancedMagazineValidator
from app.modules.magazine.templates.siet_default_v1 import get_siet_default_v1_template
from app.modules.magazine.generation_pipeline import MagazineGenerationPipeline


def _create_synthetic_image(color: str, width: int = 300, height: int = 200) -> bytes:
    img = Image.new("RGB", (width, height), color=color)
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_end_of_event_photo_association_counts():
    """
    Requirement 10: Test that photos placed at the END of each event section
    are strictly associated with the preceding event:
    Event A: 2 photos -> 2 photos
    Event B: 3 photos -> 3 photos
    Event C: 1 photo  -> 1 photo
    Event D: 0 photos -> 0 photos
    """
    doc = pymupdf.open()

    img_red = _create_synthetic_image("red")
    img_green = _create_synthetic_image("green")
    img_blue = _create_synthetic_image("blue")
    img_yellow = _create_synthetic_image("yellow")
    img_purple = _create_synthetic_image("purple")
    img_orange = _create_synthetic_image("orange")

    # Page 1: Event A (with 2 photos at end of section)
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((72, 80), "Competition: Autonomous Robotics Challenge\nParticipant: Alice (II CSE)\nAchievement: Won First Prize", fontsize=12)
    p1.insert_image(pymupdf.Rect(72, 160, 272, 300), stream=img_red)
    p1.insert_image(pymupdf.Rect(300, 160, 500, 300), stream=img_green)

    # Event B (with 3 photos at end of section)
    p1.insert_text((72, 350), "Competition: Cloud Computing Symposium\nParticipant: Bob (III IT)\nAchievement: Best Paper Award", fontsize=12)
    p1.insert_image(pymupdf.Rect(72, 430, 200, 550), stream=img_blue)
    p1.insert_image(pymupdf.Rect(210, 430, 340, 550), stream=img_yellow)
    p1.insert_image(pymupdf.Rect(350, 430, 480, 550), stream=img_purple)

    # Page 2: Event C (with 1 photo at end of section)
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((72, 80), "Competition: National AI Hackathon\nParticipant: Charlie (IV AIML)\nAchievement: Finalist", fontsize=12)
    p2.insert_image(pymupdf.Rect(72, 160, 372, 360), stream=img_orange)

    # Event D (with 0 photos)
    p2.insert_text((72, 420), "Competition: Web Architecture Workshop\nParticipant: Dana (II CSE)\nAchievement: Certified Developer", fontsize=12)

    pdf_bytes = doc.write()
    doc.close()

    # Parse and segment events
    mag_source = segment_pdf_events(pdf_bytes, filename="counts_test.pdf")
    events = mag_source.events

    assert len(events) == 4, f"Expected 4 events, found {len(events)}"

    ev_a = events[0]
    ev_b = events[1]
    ev_c = events[2]
    ev_d = events[3]

    # Verify photo counts match specification
    assert len(ev_a.photos) == 2, f"Event A expected 2 photos, got {len(ev_a.photos)}"
    assert len(ev_b.photos) == 3, f"Event B expected 3 photos, got {len(ev_b.photos)}"
    assert len(ev_c.photos) == 1, f"Event C expected 1 photo, got {len(ev_c.photos)}"
    assert len(ev_d.photos) == 0, f"Event D expected 0 photos, got {len(ev_d.photos)}"

    # Check that confidence records are stored
    for ev in [ev_a, ev_b, ev_c]:
        for ph in ev.photos:
            assert "association" in ph
            assoc = ph["association"]
            assert assoc["association_method"] in ["document_position", "spatial_proximity"]
            assert assoc["confidence"] >= 0.75
            assert len(assoc["evidence"]) > 0

    # Verify photo isolation across events (zero shared photos)
    all_assigned_urls = []
    for ev in events:
        urls = [p["url"] for p in ev.photos]
        all_assigned_urls.extend(urls)
    assert len(all_assigned_urls) == len(set(all_assigned_urls)), "Every assigned photo must be globally unique"


def test_event_without_photos_generates_valid_layout():
    """
    Requirement 7 & 10: Events with 0 photos must generate valid layouts
    without fabricating fake photos, stock images, or AI-generated people.
    """
    template = get_siet_default_v1_template()
    validator = AdvancedMagazineValidator(template)

    # Create page with 0 photos
    page_data = {
        "page_number": 3,
        "page_type": "event",
        "headline": "SIET Students Win National Coding Trophy",
        "subheadline": "Department of Computer Science and Engineering",
        "section_label": "CAMPUS NEWS",
        "metadata": "SIET AI RESEARCH | CAMPUS EVENT",
        "body": (
            "Students from the Department of Computer Science demonstrated exceptional technical acumen "
            "at the National Coding Olympiad. The team solved complex distributed systems problems within "
            "the 24-hour sprint duration, securing high ranks and commendable recognition."
        ),
        "sidebar": "KEY HIGHLIGHTS\n\n• Department: CSE\n• Category: Event\n• Status: Completed",
        "attached_photos": [],  # STRICTLY ZERO PHOTOS
        "captions": [],
        "story_id": "story_no_photos",
    }

    source_story = {
        "story_id": "story_no_photos",
        "source_text": "Students from Computer Science won the National Coding Olympiad after a 24-hour sprint.",
        "attached_photos": [],
    }

    report = validator.validate_page(
        page_data=page_data,
        source_story=source_story,
        all_event_photos_map={"story_no_photos": []},
    )

    assert report.is_valid is True, f"Page without photos must be valid, got issues: {report.issues}"
    assert len(report.photo_issues) == 0
    assert report.quality_score >= 0.90


def test_photo_isolation_cross_event_leakage_rejected():
    """
    Requirement 9: Hard validation rule - A photo belonging to Event A
    must NEVER appear on an Event B page. If detected, validation MUST fail.
    """
    template = get_siet_default_v1_template()
    validator = AdvancedMagazineValidator(template)

    event_photos_map = {
        "story_1_event_a": ["/uploads/photo_a1.png", "/uploads/photo_a2.png"],
        "story_2_event_b": ["/uploads/photo_b1.png"],
    }

    # Simulate Story B maliciously using Photo A1 from Story A
    contaminated_page = {
        "page_number": 4,
        "page_type": "event",
        "headline": "Event B Headline",
        "body": "Valid body text containing sufficient words to pass the editorial limits cleanly.",
        "attached_photos": ["/uploads/photo_a1.png"],  # LEAKED PHOTO FROM STORY A
        "story_id": "story_2_event_b",
    }

    source_story_b = {
        "story_id": "story_2_event_b",
        "source_text": "Event B source text.",
        "attached_photos": ["/uploads/photo_b1.png"],
    }

    result = validator.validate_page(
        page_data=contaminated_page,
        source_story=source_story_b,
        all_event_photos_map=event_photos_map,
    )

    assert result.is_valid is False, "Cross-event photo leakage MUST cause validation failure"
    assert any("CRITICAL PHOTO ISOLATION VIOLATION" in iss for iss in result.photo_issues)

    # Check PhotoAssociator quality gate
    isolation_res = PhotoAssociator.validate_photo_isolation(
        stories=[
            {"story_id": "story_1", "attached_photos": ["/uploads/photo_a1.png"]},
            {"story_id": "story_2", "attached_photos": ["/uploads/photo_a1.png"]},  # Collision
        ]
    )
    assert isolation_res["is_isolated"] is False
    assert len(isolation_res["violations"]) > 0


def test_automatic_separate_photo_matching():
    """
    Requirements 12 & 13: Separately uploaded photos are automatically matched
    to events based on filenames, participant names, and keywords with confidence scores.
    """
    events = [
        MagazineEvent(
            event_id="event_1",
            source_page_start=1,
            source_page_end=1,
            title="HackerRank Orchestrate Global AI Agent Challenge",
            people=["Nitish R. G"],
            organization="HackerRank",
            body_source_text="Nitish R. G secured World Rank #73 in HackerRank Orchestrate.",
        ),
        MagazineEvent(
            event_id="event_2",
            source_page_start=2,
            source_page_end=2,
            title="Sarvam AI Epoch Buildathon",
            people=["Mahibala H"],
            organization="Sarvam AI",
            body_source_text="Mahibala developed Model Context Protocol package.",
        ),
        MagazineEvent(
            event_id="event_3",
            source_page_start=3,
            source_page_end=3,
            title="Frontier Hackathon Colosseum Solana",
            people=["Viswanath N", "Prithic P"],
            organization="Solana Foundation",
            body_source_text="Students entered $250K Pre-Seed Funding Track.",
        ),
    ]

    uploaded_photos = [
        {"id": "p1", "url": "/uploads/p1.jpg", "file_name": "nitish_hackerrank_orchestrate.jpg"},
        {"id": "p2", "url": "/uploads/p2.jpg", "file_name": "sarvam_epoch_team.png"},
        {"id": "p3", "url": "/uploads/p3.jpg", "file_name": "event_3_presentation.jpg"},
        {"id": "p4", "url": "/uploads/p4.jpg", "file_name": "campus_ceremony.jpg"},  # Unlabelled sequential
    ]

    updated_events, associations = PhotoAssociator.match_separate_photos(events, uploaded_photos)

    # Verify event 1 matched nitish photo (HIGH >= 0.90)
    e1_photos = [p["file_name"] for p in updated_events[0].photos]
    assert "nitish_hackerrank_orchestrate.jpg" in e1_photos

    # Verify event 2 matched sarvam photo (HIGH >= 0.90)
    e2_photos = [p["file_name"] for p in updated_events[1].photos]
    assert "sarvam_epoch_team.png" in e2_photos

    # Verify event 3 matched explicit event_3 photo (HIGH >= 0.90)
    e3_photos = [p["file_name"] for p in updated_events[2].photos]
    assert "event_3_presentation.jpg" in e3_photos

    # Verify p4 (unlabelled) is NEVER automatically attached (< 0.75)
    for ev in updated_events:
        assert "campus_ceremony.jpg" not in [p["file_name"] for p in ev.photos]

    # Verify associations list has 4 records
    assert len(associations) == 4
    # Check p4 association is UNMATCHED
    p4_assoc = next(a for a in associations if a["photo_id"] == "p4")
    assert p4_assoc["event_id"] is None
    assert p4_assoc["confidence"] < 0.75


def test_review_mapping_is_authoritative_and_photo_ids_are_unique():
    """A human correction must not be undone by automatic matching at generation time."""
    events = [
        MagazineEvent(
            event_id="event_1",
            source_page_start=1,
            source_page_end=1,
            title="First Event",
            body_source_text="First event source text.",
        ),
        MagazineEvent(
            event_id="event_2",
            source_page_start=2,
            source_page_end=2,
            title="Second Event",
            body_source_text="Second event source text.",
        ),
    ]
    source = MagazineSource(document_title="Test", department="AI Lab", total_pages=2, events=events)
    uploaded = [
        {"id": "photo_1", "url": "/uploads/photo_1.jpg", "file_name": "event_1.jpg"},
        {"id": "photo_2", "url": "/uploads/photo_2.jpg", "file_name": "event_2.jpg"},
    ]

    # The admin deliberately removes photo_1 and moves photo_2 to event_1.
    reviewed = PhotoAssociator.bind_event_photos(
        source,
        user_photo_map={"event_1": [{"id": "photo_2"}]},
        uploaded_photos=uploaded,
    )
    assert [photo["id"] for photo in reviewed.events[0].photos] == ["photo_2"]
    assert reviewed.events[1].photos == []

    with pytest.raises(ValueError, match="only be assigned to one event"):
        PhotoAssociator.bind_event_photos(
            MagazineSource(document_title="Test", department="AI Lab", total_pages=2, events=events),
            user_photo_map={"event_1": [{"id": "photo_1"}], "event_2": [{"id": "photo_1"}]},
            uploaded_photos=uploaded,
        )


def test_docx_stream_parsing_and_end_of_event_photos():
    """
    Requirement 1 & 4: Word (.docx) documents must preserve block order
    and associate trailing photos to the preceding event.
    """
    import docx
    from app.modules.magazine.event_segmenter import segment_docx_events

    doc = docx.Document()

    # Event 1: with trailing photo
    doc.add_heading("Competition: Autonomous Robotics Challenge", level=1)
    doc.add_paragraph("Participants: Alice (II CSE)\nAchievement: Won First Prize")
    p_img1 = doc.add_paragraph()
    img_red = _create_synthetic_image("red")
    p_img1.add_run().add_picture(io.BytesIO(img_red))

    # Event 2: with trailing photo
    doc.add_heading("Competition: Cloud Computing Symposium", level=1)
    doc.add_paragraph("Participants: Bob (III IT)\nAchievement: Best Paper Award")
    p_img2 = doc.add_paragraph()
    img_blue = _create_synthetic_image("blue")
    p_img2.add_run().add_picture(io.BytesIO(img_blue))

    buf = io.BytesIO()
    doc.save(buf)
    docx_bytes = buf.getvalue()

    mag_source = segment_docx_events(docx_bytes, filename="test_doc.docx")
    assert len(mag_source.events) == 2
    assert len(mag_source.events[0].photos) == 1
    assert len(mag_source.events[1].photos) == 1
    assert mag_source.events[0].photos[0]["url"] != mag_source.events[1].photos[0]["url"]
    assert mag_source.events[0].photos[0]["association"]["association_method"] == "document_position"


def test_confidence_threshold_tiers():
    """
    Test strict confidence tiers:
    - >= 0.90: HIGH_CONFIDENCE (auto-attached)
    - 0.75 - 0.89: REVIEW_RECOMMENDED (auto-attached)
    - < 0.75: UNMATCHED (never automatically attached)
    """
    events = [
        MagazineEvent(
            event_id="ev_hack",
            source_page_start=1,
            source_page_end=1,
            title="Global Hackathon Innovation Cup",
            people=["Arun Kumar"],
            organization="TechCorp",
            body_source_text="Arun Kumar won 1st place in Global Hackathon Innovation Cup.",
        )
    ]

    # 1. High confidence photo matching event index and person name
    high_photo = {"id": "p_high", "url": "/uploads/p_high.jpg", "file_name": "ev_hack_arun_kumar.jpg"}
    # 2. Medium/review confidence photo matching person partial name or title keyword
    med_photo = {"id": "p_med", "url": "/uploads/p_med.jpg", "file_name": "innovation_team.jpg"}
    # 3. Low confidence unlabelled photo
    low_photo = {"id": "p_low", "url": "/uploads/p_low.jpg", "file_name": "random_unrelated_photo_123.jpg"}

    # Test high
    evs_h, assoc_h = PhotoAssociator.match_separate_photos([ev.model_copy(deep=True) for ev in events], [high_photo])
    assert len(evs_h[0].photos) == 1
    assert assoc_h[0]["status"] in {"HIGH", "HIGH_CONFIDENCE"}
    assert assoc_h[0]["confidence"] >= 0.90

    # Test low
    evs_l, assoc_l = PhotoAssociator.match_separate_photos([ev.model_copy(deep=True) for ev in events], [low_photo])
    assert len(evs_l[0].photos) == 0
    assert assoc_l[0]["status"] == "UNMATCHED"
    assert assoc_l[0]["confidence"] < 0.75
    assert assoc_l[0]["event_id"] is None


def test_analyze_and_match_api_contract():
    """
    Test the PhotoAssociator.analyze_and_match method contract used by the admin API.
    """
    events = [
        MagazineEvent(
            event_id="ev_1",
            source_page_start=1,
            source_page_end=1,
            title="Autonomous Robotics Challenge",
            people=["Deepak"],
            organization="RoboTech",
            body_source_text="Robotics competition details.",
        ),
        MagazineEvent(
            event_id="ev_2",
            source_page_start=2,
            source_page_end=2,
            title="Cloud Summit 2026",
            people=["Priya"],
            organization="AWS",
            body_source_text="Cloud computing award.",
        ),
    ]

    uploaded_photos = [
        {"id": "p1", "url": "/uploads/p1.jpg", "file_name": "autonomous_robotics_deepak.jpg"},
        {"id": "p2", "url": "/uploads/p2.jpg", "file_name": "unknown_scenery.jpg"},
    ]

    result = PhotoAssociator.analyze_and_match(events, uploaded_photos)

    assert "events" in result
    assert "matched_photos" in result
    assert "unmatched_photos" in result
    assert "stats" in result

    assert result["stats"]["total_events"] == 2
    assert result["stats"]["total_photos"] == 2
    assert result["stats"]["auto_matched"] == 1
    assert result["stats"]["unmatched"] == 1

    # Check matched photos contains p1 with confidence >= 0.90
    assert len(result["matched_photos"]) == 1
    assert result["matched_photos"][0]["id"] == "p1"
    assert result["matched_photos"][0]["status"] in {"HIGH", "HIGH_CONFIDENCE"}

    # Check unmatched photos contains p2
    assert len(result["unmatched_photos"]) == 1
    assert result["unmatched_photos"][0]["id"] == "p2"


def test_adaptive_multi_photo_rendering(tmp_path):
    """
    Test rendering pages with 0 photos, 1 photo, 2 photos, and 3 photos
    using SIETDefaultV1Renderer.
    """
    import fitz
    from app.modules.magazine.templates.siet_default_v1.renderer import SIETDefaultV1Renderer

    # Create dummy image files on disk
    img_path_1 = tmp_path / "img1.png"
    img_path_2 = tmp_path / "img2.png"
    img_path_3 = tmp_path / "img3.png"

    img_bytes = _create_synthetic_image("green")
    img_path_1.write_bytes(img_bytes)
    img_path_2.write_bytes(img_bytes)
    img_path_3.write_bytes(img_bytes)

    pages = [
        # Page 1: 0 photos (editorial layout with sidebar)
        {
            "page_number": 1,
            "page_type": "event",
            "section_label": "AI RESEARCH",
            "headline": "Zero Photo Event Headline",
            "subheadline": "Demonstrating clean layout without photos",
            "body": "Detailed technical report of the achievement that spans multiple sentences cleanly without image dependency.",
            "sidebar": "Highlights:\n- Key finding 1\n- Key finding 2",
            "attached_photos": [],
            "captions": [],
        },
        # Page 2: 1 photo (standard hero layout)
        {
            "page_number": 2,
            "page_type": "event",
            "section_label": "HACKATHON",
            "headline": "Single Photo Event",
            "subheadline": "Hero photo layout",
            "body": "Body text for single photo achievement.",
            "attached_photos": [str(img_path_1)],
            "captions": ["Hero photo caption."],
        },
        # Page 3: 2 photos (adaptive side-by-side grid)
        {
            "page_number": 3,
            "page_type": "event",
            "section_label": "SYMPOSIUM",
            "headline": "Two Photo Event",
            "subheadline": "Side by side photo layout",
            "body": "Body text for two photo achievement.",
            "attached_photos": [str(img_path_1), str(img_path_2)],
            "captions": ["Photo A caption", "Photo B caption"],
        },
        # Page 4: 3 photos (adaptive lead + 2 stacked)
        {
            "page_number": 4,
            "page_type": "event",
            "section_label": "CONFERENCE",
            "headline": "Three Photo Event",
            "subheadline": "Lead plus stacked layout",
            "body": "Body text for three photo achievement.",
            "attached_photos": [str(img_path_1), str(img_path_2), str(img_path_3)],
            "captions": ["Lead photo", "Top side", "Bottom side"],
        },
    ]

    out_pdf = tmp_path / "test_multi_photo.pdf"
    renderer = SIETDefaultV1Renderer()
    res_path = renderer.render_magazine_to_pdf(pages, str(out_pdf))

    assert os.path.exists(res_path)
    doc = fitz.open(res_path)
    assert len(doc) == 4
    doc.close()
