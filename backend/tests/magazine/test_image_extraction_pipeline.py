"""
Automated Regression Test Suite for Magazine Image Extraction, Event Photo Association,
Headline Overflow Prevention, and Factual Grounding.
"""

import io
import os
import pytest
import pymupdf  # fitz
from PIL import Image
from typing import Dict, Any

from app.modules.magazine.event_segmenter import (
    extract_pdf_pages_and_assets,
    segment_pdf_events,
    group_events_into_editorial_stories,
)
from app.modules.magazine.generation_pipeline import MagazineGenerationPipeline
from app.infrastructure.ai.schemas import StructuredMagazineStoryContent


def test_independent_pdf_inspection_achievements_in_ai_lab():
    """
    Independent PDF inspection test proving that Acheivements in AI LAB.pdf
    contains zero event photos and exactly one institutional header banner.
    """
    pdf_path = "/home/techpark-9/Downloads/Acheivements in AI LAB.pdf"
    if not os.path.exists(pdf_path):
        pytest.skip(f"Test file {pdf_path} not found.")

    doc = pymupdf.open(pdf_path)
    assert len(doc) == 5, f"Expected 5 pages, found {len(doc)}"

    # Check image xrefs across all pages
    image_xrefs = set()
    for page in doc:
        for img in page.get_images(full=True):
            image_xrefs.add(img[0])

    # Exactly 1 unique image in the entire PDF (xref 8)
    assert len(image_xrefs) == 1, f"Expected 1 unique image, found {len(image_xrefs)}"
    xref = list(image_xrefs)[0]
    base_img = doc.extract_image(xref)

    # Verify it is the wide letterhead banner (1122x172)
    assert base_img["width"] == 1122
    assert base_img["height"] == 172
    aspect_ratio = base_img["width"] / base_img["height"]
    assert aspect_ratio > 6.0, f"Expected wide banner aspect ratio, got {aspect_ratio}"

    # Verify its placement on all pages is at the top header (y0 < 50)
    for page in doc:
        rects = page.get_image_rects(xref)
        assert len(rects) >= 1
        assert rects[0].y0 < 50, f"Expected header placement at top, got y0={rects[0].y0}"

    # Test parser behavior
    with open(pdf_path, "rb") as f:
        file_bytes = f.read()

    pages_data, masthead_url, all_extracted_images = extract_pdf_pages_and_assets(file_bytes)
    assert masthead_url is not None, "Masthead banner must be identified"
    assert len(all_extracted_images) == 1, "Expected 1 extracted banner image"
    assert all_extracted_images[0]["is_masthead"] is True

    # Total event photos across all pages must be 0
    event_photos = [p for p_info in pages_data for p in p_info["photos"] if not p.get("is_masthead")]
    assert len(event_photos) == 0, "Document must have 0 event photos"

    doc.close()


def test_synthetic_pdf_image_extraction_and_event_binding():
    """
    Tests that a PDF with actual event photos extracts the photos and binds them
    strictly to their respective events without cross-association or leakage.
    """
    # Create in-memory PDF with 2 events and 2 distinct photos
    doc = pymupdf.open()

    # Create dummy image bytes
    def make_img(color):
        img = Image.new("RGB", (300, 200), color=color)
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()

    img_red_bytes = make_img("red")
    img_blue_bytes = make_img("blue")

    # Page 1: Event A + Red Image
    p1 = doc.new_page(width=595, height=842)
    p1.insert_text((72, 100), "Competition: Autonomous Robotics Challenge\nParticipant: Alice (II CSE)\nAchievement: Won First Prize", fontsize=12)
    p1.insert_image(pymupdf.Rect(72, 200, 372, 400), stream=img_red_bytes)

    # Page 2: Event B + Blue Image
    p2 = doc.new_page(width=595, height=842)
    p2.insert_text((72, 100), "Competition: Cloud Computing Symposium\nParticipant: Bob (III IT)\nAchievement: Published Research Paper", fontsize=12)
    p2.insert_image(pymupdf.Rect(72, 200, 372, 400), stream=img_blue_bytes)

    pdf_bytes = doc.write()
    doc.close()

    # Run event segmentation
    mag_source = segment_pdf_events(pdf_bytes, filename="test_events.pdf")
    assert len(mag_source.events) == 2
    assert len(mag_source.extracted_images) == 2

    ev1 = mag_source.events[0]
    ev2 = mag_source.events[1]

    # Verify Event 1 has exactly 1 photo and Event 2 has exactly 1 photo
    assert len(ev1.photos) == 1, f"Expected 1 photo for ev1, got {len(ev1.photos)}"
    assert len(ev2.photos) == 1, f"Expected 1 photo for ev2, got {len(ev2.photos)}"

    # Verify strict photo isolation (no shared URLs)
    url1 = ev1.photos[0]["url"]
    url2 = ev2.photos[0]["url"]
    assert url1 != url2, "Photos must have distinct URLs"

    # Test story grouping preserves isolation
    stories = group_events_into_editorial_stories(events=mag_source.events)
    assert len(stories) == 2
    assert len(stories[0]["attached_photos"]) == 1
    assert len(stories[1]["attached_photos"]) == 1
    assert stories[0]["attached_photos"][0] != stories[1]["attached_photos"][0]


def test_headline_overflow_and_numeric_sanitization():
    """
    Verifies that headline overflow (> 14 words) is condensed cleanly,
    unsupported numbers like 'Top 75' are replaced with 'World Rank #73',
    and underdense bodies (< 50 words) are expanded with grounded facts.
    """
    pipeline = MagazineGenerationPipeline()

    # 1. Headline Condensing
    long_h = "Nitish R. G Secures AI Internship at Movvr Pvt. Ltd., Ranks in Top 50 at Sarvam AI Buildathon"
    condensed = pipeline._condense_headline(long_h, max_words=14, source_text="Internship at Movvr and Sarvam Top 50")
    assert len(condensed.split()) <= 14
    assert "Movvr" in condensed

    # 2. Number Sanitization
    source_text = "Achievement: secured World Rank #73 in HackerRank Orchestrate."
    bad_headline = "World Rank #1 in SQL Challenge and Top 75 in AI Agent Competition"
    clean_headline = pipeline._sanitize_grounded_numbers(bad_headline, source_text)
    assert "75" not in clean_headline
    assert "73" in clean_headline

    # 3. Underdense Body Expansion
    short_body = "Shreekumar secured first place in the Next.js UI/UX Hackathon and attended an interview."
    sidd_source = (
        "Competition: Next.js UI/UX Hackathon\n"
        "Java Package Development for AI Applications\n"
        "Prabhu Siddarth A V developed SIDD-AI, a lightweight Java SDK for AI applications."
    )
    expanded_body = pipeline._expand_body_if_underdense(short_body, sidd_source, min_words=50)
    assert len(expanded_body.split()) >= 50
    assert "SIDD-AI" in expanded_body
