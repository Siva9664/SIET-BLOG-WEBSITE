"""
Admin Editing Preparation Module for SIET AI College Magazine.

Provides structured methods and backend data structures for Lab Admins to:
- Select and change templates
- Edit headlines, bodies, and captions
- Replace and reorder photos
- Regenerate headlines, paragraphs, captions, or full pages
- Apply natural language layout instructions (e.g. "Make this headline shorter",
  "Use the second photo as the main image", "Give this page more whitespace")
"""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from app.core.logging import logger
from app.modules.magazine.generation_pipeline import MagazineGenerationPipeline


class AdminMagazineEditor:
    """
    Handles granular editorial and layout adjustments by Lab Admins.
    """

    def __init__(self, pipeline: MagazineGenerationPipeline):
        self.pipeline = pipeline

    def select_template(self, magazine_state: Dict[str, Any], template_id: str) -> Dict[str, Any]:
        """Sets active template on magazine state."""
        magazine_state["selected_template_id"] = template_id
        return magazine_state

    def change_template(self, magazine_state: Dict[str, Any], new_template_id: str) -> Dict[str, Any]:
        """Swaps active template and re-evaluates page specs."""
        magazine_state["selected_template_id"] = new_template_id
        logger.info(f"[Admin] Template changed to {new_template_id}")
        return magazine_state

    def edit_headline(self, page_data: Dict[str, Any], new_headline: str) -> Dict[str, Any]:
        """Directly edits page headline."""
        page_data["headline"] = new_headline.strip()
        return page_data

    def edit_body(self, page_data: Dict[str, Any], new_body: str) -> Dict[str, Any]:
        """Directly edits page body text."""
        page_data["body"] = new_body.strip()
        return page_data

    def replace_photo(self, page_data: Dict[str, Any], old_photo_id: str, new_photo_id: str) -> Dict[str, Any]:
        """Replaces a photo on a specific page."""
        photos = page_data.get("attached_photos", [])
        if old_photo_id in photos:
            idx = photos.index(old_photo_id)
            photos[idx] = new_photo_id
            page_data["attached_photos"] = photos
        return page_data

    def reorder_photos(self, page_data: Dict[str, Any], new_order: List[str]) -> Dict[str, Any]:
        """Reorders photos on a page (e.g. making second photo the primary hero)."""
        current_photos = set(page_data.get("attached_photos", []))
        # Ensure only valid photos belonging to this page are kept
        filtered_order = [p for p in new_order if p in current_photos]
        remaining = [p for p in page_data.get("attached_photos", []) if p not in filtered_order]
        page_data["attached_photos"] = filtered_order + remaining
        return page_data

    async def regenerate_headline(
        self,
        page_data: Dict[str, Any],
        source_story: Dict[str, Any],
        instructions: Optional[str] = None,
    ) -> str:
        """Regenerates only the headline with optional editor instruction."""
        prompt = (
            f"SOURCE CONTEXT:\n{source_story.get('source_text', '')}\n\n"
            f"Current Headline: {page_data.get('headline', '')}\n"
            f"Editor Instruction: {instructions or 'Provide an engaging grounded headline under 14 words.'}\n\n"
            "TASK: Output ONLY the new headline text."
        )
        new_headline = await self.pipeline.ai_service.generate_text(prompt)
        cleaned = re.sub(r'^["\']|["\']$', '', new_headline.strip())
        page_data["headline"] = cleaned
        return cleaned

    async def regenerate_paragraph(
        self,
        page_data: Dict[str, Any],
        source_story: Dict[str, Any],
        paragraph_idx: int = 0,
        instructions: Optional[str] = None,
    ) -> str:
        """Regenerates a specific paragraph in the body while preserving surrounding text."""
        paragraphs = page_data.get("body", "").split("\n\n")
        target_para = paragraphs[paragraph_idx] if paragraph_idx < len(paragraphs) else ""

        prompt = (
            f"SOURCE CONTEXT:\n{source_story.get('source_text', '')}\n\n"
            f"Target Paragraph to improve:\n{target_para}\n\n"
            f"Editor Instruction: {instructions or 'Make this paragraph more polished while preserving all facts.'}\n\n"
            "TASK: Output ONLY the improved replacement paragraph."
        )
        improved_para = await self.pipeline.ai_service.generate_text(prompt)
        cleaned = improved_para.strip()

        if paragraph_idx < len(paragraphs):
            paragraphs[paragraph_idx] = cleaned
        else:
            paragraphs.append(cleaned)

        page_data["body"] = "\n\n".join(paragraphs)
        return cleaned

    async def regenerate_caption(
        self,
        page_data: Dict[str, Any],
        photo_id: str,
        source_story: Dict[str, Any],
        instructions: Optional[str] = None,
    ) -> str:
        """Regenerates caption for a specific photo."""
        prompt = (
            f"SOURCE CONTEXT:\n{source_story.get('source_text', '')}\n"
            f"Target Photo ID: {photo_id}\n"
            f"Editor Instruction: {instructions or 'Factual caption under 15 words.'}\n\n"
            "TASK: Output ONLY the single caption line."
        )
        new_caption = await self.pipeline.ai_service.generate_text(prompt)
        cleaned = re.sub(r'^["\']|["\']$', '', new_caption.strip())

        photos = page_data.get("attached_photos", [])
        captions = page_data.get("captions", [])
        if photo_id in photos:
            idx = photos.index(photo_id)
            while len(captions) <= idx:
                captions.append("")
            captions[idx] = cleaned
            page_data["captions"] = captions

        return cleaned

    async def apply_admin_layout_instruction(
        self,
        page_data: Dict[str, Any],
        source_story: Dict[str, Any],
        department: str,
        instruction: str,
    ) -> Dict[str, Any]:
        """
        Interprets natural language layout instructions from Lab Admin and updates the page.
        Examples:
        - "Make this headline shorter."
        - "Use the second photo as the main image."
        - "Give this page more whitespace."
        - "Make the article more attractive but keep all facts."
        - "Make the image larger."
        - "Regenerate this page."
        """
        inst_lower = instruction.lower().strip()

        # Instruction: "Use the second photo as the main image"
        if "second photo" in inst_lower and ("main" in inst_lower or "hero" in inst_lower or "first" in inst_lower):
            photos = page_data.get("attached_photos", [])
            if len(photos) >= 2:
                # Swap 0 and 1
                photos[0], photos[1] = photos[1], photos[0]
                page_data["attached_photos"] = photos
                logger.info("[Admin] Swapped second photo to primary position.")
            return page_data

        # Instruction: "Make this headline shorter"
        if "headline" in inst_lower and ("shorter" in inst_lower or "concise" in inst_lower or "brief" in inst_lower):
            curr_headline = page_data.get("headline", "")
            words = curr_headline.split()
            if len(words) > 8:
                page_data["headline"] = " ".join(words[:7]) + "..."
            else:
                await self.regenerate_headline(page_data, source_story, instructions="Keep headline under 7 words.")
            return page_data

        # Instruction: "Give this page more whitespace"
        if "whitespace" in inst_lower or "breathing room" in inst_lower:
            # Reduce body length by trimming or condensing
            body = page_data.get("body", "")
            sentences = body.split(". ")
            if len(sentences) > 2:
                page_data["body"] = ". ".join(sentences[:2]) + "."
            return page_data

        # Instruction: "Make the image larger" / "hero image"
        if "image larger" in inst_lower or "bigger image" in inst_lower:
            page_data["page_type"] = "photo_feature"
            page_data["page_spec"] = self.pipeline.template.get_page_spec("photo_feature")
            return page_data

        # Instruction: "Regenerate this page" or "Make article more attractive but keep all facts"
        return await self.pipeline.regenerate_page(
            page_data=page_data,
            source_story=source_story,
            department=department,
            admin_instructions=instruction,
        )
