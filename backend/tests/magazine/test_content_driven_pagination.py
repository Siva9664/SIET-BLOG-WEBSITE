"""
Tests for Content-Driven Dynamic Pagination in SIET Magazine Generator.
Verifies Gate 6:
- Input A: 1 event -> minimal page count (cover, contents, story, closing)
- Input B: 3 events -> compact multi-page spread
- Input C: 12 events -> expansive multi-page spread with clustered stories
- Input D: Event with many photos (4+ photos) -> photo-feature / image-grid layout
- Input E: Zero photos -> clean text-first layout with zero photo errors
"""

import pytest
import tempfile
import os
from typing import List, Dict, Any

from app.modules.magazine.event_segmenter import (
    MagazineEvent,
    MagazineSource,
    group_events_into_editorial_stories,
)
from app.modules.magazine.generation_pipeline import MagazineGenerationPipeline
from app.infrastructure.ai.schemas import StructuredMagazineStoryContent


def _make_dummy_event(
    event_id: str,
    title: str,
    words: int = 50,
    photos: List[str] = None,
    page_type: str = "victory",
    page_num: int = 1,
) -> MagazineEvent:
    body = " ".join([f"Word{i}" for i in range(words)]) + " at SIET campus."
    return MagazineEvent(
        event_id=event_id,
        source_page_start=page_num,
        source_page_end=page_num,
        title=title,
        date="August 2026",
        people=["Student Alpha", "Student Beta"],
        organization="SIET",
        achievement_result="First Place",
        facts=[f"Fact about {title}"],
        body_source_text=f"{title}\n\n{body}",
        photos=[{"url": p, "page_number": page_num} for p in (photos or [])],
        confidence=1.0,
        suggested_page_type=page_type,
    )


@pytest.mark.asyncio
async def test_pagination_scales_dynamically_with_event_count():
    pipeline = MagazineGenerationPipeline()

    # 1. Input A: 1 Event
    event_a = [_make_dummy_event("e1", "Single Championship Event", words=60)]
    stories_a = group_events_into_editorial_stories(events=event_a)
    assert len(stories_a) == 1

    structured_a = [
        (
            stories_a[0],
            StructuredMagazineStoryContent(
                section="Victories",
                story_type="victory",
                headline="Single Championship Event",
                subheadline="AI Department Spotlight",
                polished_body=stories_a[0]["source_text"],
                short_summary="Summary of single event",
                photo_captions=[],
                keywords=["victory"],
                page_type="victory",
                layout_intent="text_only",
                recommended_image_count=0,
                decorative_asset_category="none",
            ),
        )
    ]
    pages_a = pipeline.plan_magazine_pages(
        issue_title="Issue A",
        department="AI Lab",
        structured_stories=structured_a,
    )
    # Cover (1) + Contents (1) + Story (1) + Closing (1) = 4 pages
    assert len(pages_a) == 4
    assert pages_a[0]["page_type"] == "cover"
    assert pages_a[1]["page_type"] == "contents"
    assert pages_a[2]["page_type"] == "victory"
    assert pages_a[3]["page_type"] == "closing_page"

    # 2. Input B: 3 Events
    events_b = [
        _make_dummy_event("e1", "Event One", words=40, page_num=1),
        _make_dummy_event("e2", "Event Two", words=40, page_num=1),
        _make_dummy_event("e3", "Event Three", words=40, page_num=2),
    ]
    stories_b = group_events_into_editorial_stories(events=events_b)
    assert 1 <= len(stories_b) <= 3

    structured_b = [
        (
            st,
            StructuredMagazineStoryContent(
                section="Highlights",
                story_type=st["story_type"],
                headline=st["title"],
                subheadline="AI Lab",
                polished_body=st["source_text"],
                short_summary="Story summary",
                photo_captions=[],
                keywords=["hackathon"],
                page_type=st["target_page_type"],
                layout_intent="text_only",
                recommended_image_count=0,
                decorative_asset_category="none",
            ),
        )
        for st in stories_b
    ]
    pages_b = pipeline.plan_magazine_pages(
        issue_title="Issue B",
        department="AI Lab",
        structured_stories=structured_b,
    )
    # 3 stories clustered into 1-2 pages + Cover + Contents + Closing = 4-5 pages
    assert len(pages_b) >= 4
    assert len(pages_b) < 8

    # 3. Input C: 12 Events across multiple pages
    events_c = [
        _make_dummy_event(f"e_{i}", f"Major Hackathon {i}", words=70, page_num=(i // 2) + 1)
        for i in range(12)
    ]
    stories_c = group_events_into_editorial_stories(events=events_c)
    # 12 events of 70 words each (840 words total) must produce at least 5-8 distinct stories
    assert len(stories_c) >= 5

    structured_c = [
        (
            st,
            StructuredMagazineStoryContent(
                section="Competitions",
                story_type=st["story_type"],
                headline=st["title"],
                subheadline="AI Lab",
                polished_body=st["source_text"],
                short_summary="Story summary",
                photo_captions=[],
                keywords=["tech"],
                page_type=st["target_page_type"],
                layout_intent="text_only",
                recommended_image_count=0,
                decorative_asset_category="none",
            ),
        )
        for st in stories_c
    ]
    pages_c = pipeline.plan_magazine_pages(
        issue_title="Issue C",
        department="AI Lab",
        structured_stories=structured_c,
    )
    # Must scale up: Cover + Contents + (>= 5 stories) + Closing >= 8 pages
    assert len(pages_c) >= 8
    assert len(pages_c) > len(pages_a)
    assert len(pages_c) > len(pages_b)


@pytest.mark.asyncio
async def test_pagination_photo_and_zero_photo_adaptation():
    pipeline = MagazineGenerationPipeline()

    # Input D: Many Photos (4 photos attached to an event)
    dummy_photos = [f"/uploads/photo_{i}.jpg" for i in range(4)]
    event_photos = [_make_dummy_event("p1", "Photo Heavy Showcase", words=80, photos=dummy_photos, page_type="victory")]
    stories_photos = group_events_into_editorial_stories(events=event_photos)
    assert len(stories_photos[0]["attached_photos"]) == 4

    structured_photos = [
        (
            stories_photos[0],
            StructuredMagazineStoryContent(
                section="Campus Gallery",
                story_type="victory",
                headline="Photo Heavy Showcase",
                subheadline="SIET Tech Fest",
                polished_body=stories_photos[0]["source_text"],
                short_summary="Summary with 4 photos",
                photo_captions=[f"Caption {i}" for i in range(4)],
                keywords=["gallery"],
                page_type="victory",
                layout_intent="image_grid",
                recommended_image_count=4,
                decorative_asset_category="trophy_3d",
            ),
        )
    ]
    pages_photos = pipeline.plan_magazine_pages(
        issue_title="Photo Issue",
        department="AI Lab",
        structured_stories=structured_photos,
    )
    story_page = pages_photos[2]
    assert len(story_page["attached_photos"]) == 4
    assert len(story_page["captions"]) == 4

    # Input E: Zero Photos
    event_zero = [_make_dummy_event("z1", "Pure Text Research Paper", words=150, photos=[], page_type="project")]
    stories_zero = group_events_into_editorial_stories(events=event_zero)
    assert len(stories_zero[0]["attached_photos"]) == 0

    structured_zero = [
        (
            stories_zero[0],
            StructuredMagazineStoryContent(
                section="Research Papers",
                story_type="project",
                headline="Pure Text Research Paper",
                subheadline="Open Source Engineering",
                polished_body=stories_zero[0]["source_text"],
                short_summary="Summary with 0 photos",
                photo_captions=[],
                keywords=["research"],
                page_type="project",
                layout_intent="text_only",
                recommended_image_count=0,
                decorative_asset_category="none",
            ),
        )
    ]
    pages_zero = pipeline.plan_magazine_pages(
        issue_title="Zero Photo Issue",
        department="AI Lab",
        structured_stories=structured_zero,
    )
    story_page_zero = pages_zero[2]
    assert len(story_page_zero["attached_photos"]) == 0
    assert len(story_page_zero["captions"]) == 0
