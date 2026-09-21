"""
Photo association module for college magazine stories and events.
Strictly preserves event-to-photo grouping, visual page order, and photo IDs.
Flags ambiguous associations as 'uncertain' rather than guessing.
"""

from __future__ import annotations

import re
from typing import List, Dict, Tuple, Optional

from .schemas import DocumentRecord, PageData, PhotoItem, StorySegment, PhotoConfidence


class PhotoAssociator:
    """
    Associates photos extracted from documents with their respective story/event segments.
    Enforces strict grounding: Never invents photo relationships.
    """

    def associate(self, doc: DocumentRecord, stories: List[StorySegment]) -> List[StorySegment]:
        """
        Associates photos from doc.pages with stories based on page provenance,
        order, and contextual cues. Returns updated stories with attached_photos.
        """
        # Map page_number -> photos
        page_photo_map: Dict[int, List[PhotoItem]] = {
            page.page_number: page.photos for page in doc.pages
        }

        # Group stories by page
        stories_by_page: Dict[int, List[StorySegment]] = {}
        for s in stories:
            p_start = s.page_start
            stories_by_page.setdefault(p_start, []).append(s)

        for page_num, photos in page_photo_map.items():
            if not photos:
                continue

            page_stories = stories_by_page.get(page_num, [])

            if len(page_stories) == 1:
                # Deterministic Case 1: Exactly one story on the page
                # In college magazines, all photos on this page belong to this single story.
                story = page_stories[0]
                story.attached_photos = [p.photo_id for p in photos]
                story.photo_confidence = PhotoConfidence.HIGH.value

            elif len(page_stories) > 1:
                # Multi-story page: Attempt grounded matching or flag uncertain
                self._associate_multi_story_page(page_stories, photos)

            else:
                # Zero stories on this page (e.g. photo collage page)
                # Check if previous page story overflowed
                prev_stories = stories_by_page.get(page_num - 1, [])
                if len(prev_stories) == 1:
                    # Single story on previous page overflowed photos to this page
                    prev_story = prev_stories[0]
                    # Append photos if previous story had no photos or explicitly continues
                    if not prev_story.attached_photos:
                        prev_story.attached_photos = [p.photo_id for p in photos]
                        prev_story.photo_confidence = PhotoConfidence.MEDIUM.value
                        prev_story.page_end = page_num
                # Otherwise photos remain unattached to prevent inventing relationships

        return stories

    def _associate_multi_story_page(
        self, stories: List[StorySegment], photos: List[PhotoItem]
    ) -> None:
        """
        Handles multiple stories sharing the same page with extracted photos.
        If photo captions or entities match a story, associates them.
        Otherwise, flags as UNCERTAIN to avoid hallucinating pairings.
        """
        assigned_photo_ids = set()

        for photo in photos:
            matched_story = None
            if photo.caption_hint:
                # Check if caption matches names or keywords from any story
                for s in stories:
                    caption_lower = photo.caption_hint.lower()
                    if any(p.lower() in caption_lower for p in s.people if len(p) > 3):
                        matched_story = s
                        break
                    if s.headline and any(
                        word.lower() in caption_lower
                        for word in s.headline.split()
                        if len(word) > 4
                    ):
                        matched_story = s
                        break

            if matched_story:
                matched_story.attached_photos.append(photo.photo_id)
                assigned_photo_ids.add(photo.photo_id)

        # For remaining unassigned photos:
        unassigned = [p for p in photos if p.photo_id not in assigned_photo_ids]
        if unassigned:
            # Rule: If multiple stories exist and photos cannot be uniquely matched,
            # DO NOT randomly associate. Mark stories as UNCERTAIN.
            for s in stories:
                if not s.attached_photos:
                    s.photo_confidence = PhotoConfidence.UNCERTAIN.value
                    # Note: We do NOT randomly attach photos when uncertain!
