"""
Template-Driven AI College Magazine Generation Pipeline.

Orchestrates the full flow:
Source document
    ↓
Document parser
    ↓
Story/event segmentation
    ↓
Fact extraction
    ↓
RAG/context
    ↓
Qwen3-14B structured generation
    ↓
Fact validation
    ↓
Photo association validation
    ↓
Template/layout planning (SIET_DEFAULT_V1)
    ↓
Renderer
    ↓
Visual validation
    ↓
PDF Output
"""

from __future__ import annotations

import os
import re
import io
import json
import fitz  # PyMuPDF
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
from PIL import Image

from app.core.logging import logger
from app.infrastructure.ai.manager import AIServiceManager, get_ai_service
from app.infrastructure.ai.constants import DEFAULT_STRICT_GROUNDING_INSTRUCTION
from app.infrastructure.ai.schemas import StructuredMagazineStoryContent
from app.modules.magazine.templates.siet_default_v1 import get_siet_default_v1_template
from app.modules.magazine.templates.template_schema import MagazineTemplateSpec, PageTypeSpec
from app.modules.magazine.advanced_validator import (
    AdvancedMagazineValidator,
    MagazineValidationReport,
    PageValidationResult,
)


def _hex_to_rgb(hex_str: str) -> Tuple[float, float, float]:
    """Converts a hex color code to a normalized PyMuPDF RGB tuple."""
    h = hex_str.lstrip("#")
    if len(h) == 3:
        h = "".join([c * 2 for c in h])
    try:
        r = int(h[0:2], 16) / 255.0
        g = int(h[2:4], 16) / 255.0
        b = int(h[4:6], 16) / 255.0
        return (r, g, b)
    except Exception:
        return (0.0, 0.0, 0.0)


def _normalize_font_name(font_name: Optional[str]) -> str:
    """Normalizes font name string into valid standard PyMuPDF base 14 font identifiers."""
    if not font_name:
        return "helv"
    f = font_name.lower().strip()
    mapping = {
        "helv": "helv",
        "helvetica": "helv",
        "helv-bold": "hebo",
        "helvetica-bold": "hebo",
        "hebo": "hebo",
        "helv-oblique": "heit",
        "helvetica-oblique": "heit",
        "heit": "heit",
        "times": "tiro",
        "times-roman": "tiro",
        "tiro": "tiro",
        "times-bold": "tibo",
        "tibo": "tibo",
        "tiit": "tiit",
        "times-italic": "tiit",
        "tibi": "tibi",
        "times-bolditalic": "tibi",
        "courier": "cour",
        "cour": "cour",
        "cobo": "cobo",
    }
    return mapping.get(f, "helv")


class MagazineGenerationPipeline:
    """
    Template-driven AI College Magazine Generation Pipeline using Qwen3-14B and SIET_DEFAULT_V1.
    """

    def __init__(
        self,
        ai_service: Optional[AIServiceManager] = None,
        template_spec: Optional[MagazineTemplateSpec] = None,
    ):
        self.ai_service = ai_service or get_ai_service()
        self.template = template_spec or get_siet_default_v1_template()
        self.validator = AdvancedMagazineValidator(self.template)

    # -------------------------------------------------------------------------
    # 1. Document Parsing & Story Segmentation
    # -------------------------------------------------------------------------
    def parse_source_document(self, text_or_path: str) -> List[Dict[str, Any]]:
        """
        Parses source document or raw text and segments it into distinct event/story blocks.
        """
        content = text_or_path
        if os.path.exists(text_or_path):
            p = Path(text_or_path)
            if p.suffix.lower() == ".pdf":
                doc = fitz.open(str(p))
                pages = [doc[i].get_text("text") for i in range(len(doc))]
                content = "\n\n---\n\n".join(pages)
            else:
                content = p.read_text(encoding="utf-8", errors="replace")

        # Split by dividers or major headings
        raw_chunks = re.split(r"\n\s*(?:---|===|_{3,})\s*\n", content)
        chunks = [c.strip() for c in raw_chunks if c.strip()]
        if not chunks:
            chunks = [content.strip()]

        stories = []
        for idx, chunk in enumerate(chunks, start=1):
            lines = [l.strip() for l in chunk.splitlines() if l.strip()]
            first_line = lines[0] if lines else f"Story {idx}"
            headline = re.sub(r"^#+\s*", "", first_line).strip()

            # Classify story type
            c_lower = chunk.lower()
            if any(k in c_lower for k in ["won", "prize", "winner", "gold medal", "champion"]):
                s_type = "achievement_victory"
                p_type = "achievement_victory"
            elif any(k in c_lower for k in ["workshop", "hands-on", "bootcamp"]):
                s_type = "workshop"
                p_type = "workshop"
            elif any(k in c_lower for k in ["seminar", "webinar", "guest lecture", "invited talk"]):
                s_type = "seminar"
                p_type = "seminar"
            elif any(k in c_lower for k in ["project", "capstone", "prototype"]):
                s_type = "project"
                p_type = "project"
            elif any(k in c_lower for k in ["faculty", "fdp", "professor"]):
                s_type = "faculty_activity"
                p_type = "faculty_activity"
            elif any(k in c_lower for k in ["student club", "nss", "sports"]):
                s_type = "student_activity"
                p_type = "student_activity"
            else:
                s_type = "event"
                p_type = "event"

            stories.append({
                "story_id": f"story_{idx}",
                "story_type": s_type,
                "target_page_type": p_type,
                "headline_hint": headline,
                "source_text": chunk,
                "attached_photos": [],
            })

        return stories

    # -------------------------------------------------------------------------
    # 2. Photo Association (Strict Event Isolation)
    # -------------------------------------------------------------------------
    def associate_event_photos(
        self,
        stories: List[Dict[str, Any]],
        event_photos_map: Dict[str, List[str]],
    ) -> List[Dict[str, Any]]:
        """
        Binds photos strictly to their source events.
        Guarantees that Event A never receives Event B's photos.
        """
        for story in stories:
            s_id = story.get("story_id")
            if s_id in event_photos_map:
                story["attached_photos"] = list(event_photos_map[s_id])
        return stories

    # -------------------------------------------------------------------------
    # 3. Qwen3-14B Structured Generation
    # -------------------------------------------------------------------------
    async def generate_structured_story(
        self,
        story: Dict[str, Any],
        department: str = "Campus General",
        admin_instructions: Optional[str] = None,
    ) -> StructuredMagazineStoryContent:
        """
        Calls Qwen3-14B (via AIServiceManager) to produce polished, publication-ready
        editorial content strictly grounded in the source text.
        """
        photo_count = len(story.get("attached_photos", []))

        prompt = f"""You are the editorial intelligence assistant for the SIET College Magazine.

SOURCE CONTEXT:
\"\"\"
{story.get('source_text', '')}
\"\"\"

METADATA & CONSTRAINTS:
- Department / Lab: {department}
- Story Type: {story.get('story_type', 'event')}
- Target Page Type: {story.get('target_page_type', 'event')}
- Available Attached Photos: {photo_count}
{f"- LAB ADMIN INSTRUCTIONS: {admin_instructions}" if admin_instructions else ""}

TASK:
Produce structured magazine-ready content:
1. Section name (e.g. Department News, Technical Symposia, Campus Life, Achievements).
2. Story type matching source.
3. Headline (compelling, publication-ready, strictly grounded).
4. Optional subheadline.
5. Polished body article (attractive and engaging tone, but 100% grounded in facts; zero invented names or dates).
6. Short TOC summary (max 25 words).
7. Photo captions (one per attached photo, max 15 words each, factual).
8. Keywords / tags.
9. Page type and layout intent.
10. Recommended image count (based on available photos).
11. Optional decorative/3D asset category (trophy_3d, tech_circuit, robotics_icon, diploma_ribbon, none).

Return ONLY valid structured output conforming to the requested schema."""

        try:
            result = await self.ai_service.generate_structured(
                prompt=prompt,
                schema=StructuredMagazineStoryContent,
                system_instruction=DEFAULT_STRICT_GROUNDING_INSTRUCTION,
            )
            return result
        except Exception as e:
            logger.warning(f"[Pipeline] LLM generation failed ({e}). Falling back to deterministic grounded generator.")
            return self._fallback_deterministic_story(story, department)

    def _fallback_deterministic_story(
        self, story: Dict[str, Any], department: str
    ) -> StructuredMagazineStoryContent:
        """Deterministic grounded fallback when live LLM is unavailable."""
        headline = story.get("headline_hint") or "SIET Campus Event"
        body = story.get("source_text") or "Campus event report."
        photo_count = len(story.get("attached_photos", []))
        p_type = story.get("target_page_type", "event")

        captions = [
            f"Participants during {headline[:30]} at SIET." for _ in range(photo_count)
        ]

        return StructuredMagazineStoryContent(
            section="Campus News",
            story_type=story.get("story_type", "event"),
            headline=headline,
            subheadline=f"{department} Department Spotlight",
            polished_body=body,
            short_summary=headline[:60],
            photo_captions=captions,
            keywords=[story.get("story_type", "event"), department],
            page_type=p_type,
            layout_intent="text_and_image" if photo_count <= 2 else "image_grid",
            recommended_image_count=min(photo_count, 2) if photo_count > 0 else 0,
            decorative_asset_category="none",
        )

    # -------------------------------------------------------------------------
    # 4. Template & Layout Planning
    # -------------------------------------------------------------------------
    def plan_magazine_pages(
        self,
        issue_title: str,
        department: str,
        structured_stories: List[Tuple[Dict[str, Any], StructuredMagazineStoryContent]],
    ) -> List[Dict[str, Any]]:
        """
        Maps structured stories to configuration-driven template pages.
        Constructs Cover, Contents, Story Pages, and Closing Colophon.
        """
        pages = []
        page_num = 1

        # 1. Cover Page
        cover_spec = self.template.get_page_spec("cover")
        pages.append({
            "page_number": page_num,
            "page_type": "cover",
            "page_spec": cover_spec,
            "headline": issue_title,
            "subheadline": f"Official Digest • {department}",
            "body": f"A comprehensive showcase of academic excellence, innovation, and victories at {department}.",
            "attached_photos": [],
            "captions": [],
            "story_id": "cover_page",
        })
        page_num += 1

        # 2. Table of Contents
        contents_spec = self.template.get_page_spec("contents")
        toc_lines = []
        for idx, (raw_s, content) in enumerate(structured_stories, start=3):
            toc_lines.append(f"Page {idx}  •  {content.headline} ({content.story_type.replace('_', ' ').title()})")

        pages.append({
            "page_number": page_num,
            "page_type": "contents",
            "page_spec": contents_spec,
            "headline": "Table of Contents & Highlights",
            "subheadline": f"{department} Publication",
            "body": "\n".join(toc_lines),
            "attached_photos": [],
            "captions": [],
            "story_id": "contents_page",
        })
        page_num += 1

        # 3. Individual Story Pages
        for raw_s, content in structured_stories:
            # Match page type from content or fallback
            p_type = content.page_type if content.page_type in self.template.supported_page_types else "event"
            page_spec = self.template.get_page_spec(p_type)

            # Enforce photo limits defined by page type
            avail_photos = raw_s.get("attached_photos", [])
            max_imgs = page_spec.maximum_images
            selected_photos = avail_photos[:max_imgs]

            pages.append({
                "page_number": page_num,
                "page_type": p_type,
                "page_spec": page_spec,
                "headline": content.headline,
                "subheadline": content.subheadline,
                "body": content.polished_body,
                "attached_photos": selected_photos,
                "captions": content.photo_captions[:len(selected_photos)],
                "story_id": raw_s.get("story_id"),
                "decorative_asset_category": content.decorative_asset_category,
            })
            page_num += 1

        # 4. Closing Page
        closing_spec = self.template.get_page_spec("closing_page")
        pages.append({
            "page_number": page_num,
            "page_type": "closing_page",
            "page_spec": closing_spec,
            "headline": "In Pursuit of Technical Excellence",
            "subheadline": "Sri Shakthi Institute of Engineering & Technology",
            "body": f"Published by {department}, SIET Coimbatore.\nFor editorial queries and contributions, contact the department lab admin.",
            "attached_photos": [],
            "captions": [],
            "story_id": "closing_page",
        })

        return pages

    # -------------------------------------------------------------------------
    # 5. Deterministic PDF Rendering
    # -------------------------------------------------------------------------
    def render_magazine_pdf(
        self,
        planned_pages: List[Dict[str, Any]],
        output_pdf_path: str,
    ) -> str:
        """
        Renders planned magazine pages into a PDF using PyMuPDF and template geometry.
        """
        os.makedirs(os.path.dirname(os.path.abspath(output_pdf_path)), exist_ok=True)
        doc = fitz.open()

        for page_data in planned_pages:
            page_spec: PageTypeSpec = page_data.get("page_spec") or self.template.get_page_spec(page_data.get("page_type", "event"))
            page_num = page_data.get("page_number", 1)

            w_pt = page_spec.width_pt
            h_pt = page_spec.height_pt
            page = doc.new_page(width=w_pt, height=h_pt)

            # 1. Background Fill
            bg_color = _hex_to_rgb(self.template.background_color)
            page.draw_rect(fitz.Rect(0, 0, w_pt, h_pt), color=None, fill=bg_color)

            # 2. Outer Frame Border
            m = page_spec.margins
            frame = fitz.Rect(m["left"], m["top"], w_pt - m["right"], h_pt - m["bottom"])
            primary_rgb = _hex_to_rgb(self.template.primary_color)
            page.draw_rect(frame, color=primary_rgb, width=0.75)

            # 3. Render Text Regions
            headline = page_data.get("headline", "") or ""
            subheadline = page_data.get("subheadline", "") or ""
            body = page_data.get("body", "") or ""

            for t_reg in page_spec.text_regions:
                rect = fitz.Rect(t_reg.x_pt, t_reg.y_pt, t_reg.x_pt + t_reg.width_pt, t_reg.y_pt + t_reg.height_pt)
                txt_color = _hex_to_rgb(t_reg.color_hex)
                font_name = _normalize_font_name(t_reg.font_family)
                f_size = t_reg.font_size_max

                align_code = fitz.TEXT_ALIGN_LEFT
                if t_reg.align == "center":
                    align_code = fitz.TEXT_ALIGN_CENTER
                elif t_reg.align == "justify":
                    align_code = fitz.TEXT_ALIGN_JUSTIFY

                if t_reg.role == "headline":
                    page.insert_textbox(rect, headline, fontsize=f_size, fontname=font_name, color=txt_color, align=align_code)
                elif t_reg.role == "subheadline":
                    page.insert_textbox(rect, subheadline, fontsize=f_size, fontname=font_name, color=txt_color, align=align_code)
                elif t_reg.role == "body":
                    page.insert_textbox(rect, body, fontsize=f_size, fontname=font_name, color=txt_color, align=align_code)
                elif t_reg.role == "header":
                    header_txt = f"SIET MAGAZINE — PAGE {page_num}"
                    page.insert_textbox(rect, header_txt, fontsize=8.0, fontname="hebo", color=primary_rgb, align=align_code)
                elif t_reg.role == "footer":
                    footer_txt = f"SIET AI College Magazine • Page {page_num}"
                    page.insert_textbox(rect, footer_txt, fontsize=8.0, fontname="helv", color=_hex_to_rgb("#6B7280"), align=align_code)

            # 4. Render Image Regions
            attached_photos = page_data.get("attached_photos", [])
            for idx, img_reg in enumerate(page_spec.image_regions):
                rect = fitz.Rect(img_reg.x_pt, img_reg.y_pt, img_reg.x_pt + img_reg.width_pt, img_reg.y_pt + img_reg.height_pt)
                if idx < len(attached_photos):
                    photo_path = attached_photos[idx]
                    if os.path.exists(photo_path):
                        try:
                            page.insert_image(rect, filename=photo_path, keep_proportion=True)
                        except Exception as e:
                            logger.warning(f"Failed to insert image {photo_path}: {e}")
                    else:
                        # Placeholder box if file path doesn't exist on disk
                        page.draw_rect(rect, color=primary_rgb, fill=_hex_to_rgb("#E5E7EB"))
                        page.insert_textbox(rect, f"[Photo: {os.path.basename(photo_path)}]", fontsize=9.0, color=_hex_to_rgb("#374151"), align=fitz.TEXT_ALIGN_CENTER)
                else:
                    # Optional slot without image: draw subtle background or decorative tint
                    if img_reg.role == "badge":
                        page.draw_rect(rect, color=primary_rgb, fill=_hex_to_rgb("#FEF3C7"))
                        page.insert_textbox(rect, "[SIET SEAL]", fontsize=10.0, color=primary_rgb, align=fitz.TEXT_ALIGN_CENTER)

            # 5. Render Captions
            captions = page_data.get("captions", [])
            for idx, cap_reg in enumerate(page_spec.caption_regions):
                if idx < len(captions):
                    rect = fitz.Rect(cap_reg.x_pt, cap_reg.y_pt, cap_reg.x_pt + cap_reg.width_pt, cap_reg.y_pt + cap_reg.height_pt)
                    page.insert_textbox(rect, captions[idx], fontsize=cap_reg.font_size, color=_hex_to_rgb(cap_reg.color_hex), align=fitz.TEXT_ALIGN_LEFT)

        doc.save(output_pdf_path)
        doc.close()
        return output_pdf_path

    # -------------------------------------------------------------------------
    # 6. Full End-to-End Execution
    # -------------------------------------------------------------------------
    async def generate_magazine(
        self,
        source_text_or_path: str,
        department: str,
        issue_title: str,
        event_photos_map: Optional[Dict[str, List[str]]] = None,
        admin_instructions: Optional[str] = None,
        output_pdf_path: str = "output/magazine.pdf",
    ) -> Tuple[List[Dict[str, Any]], MagazineValidationReport, str]:
        """
        Executes end-to-end generation from raw input to validated PDF.
        """
        # Step 1: Parse & Segment
        stories = self.parse_source_document(source_text_or_path)

        # Step 2: Associate Photos (Strict Event Isolation)
        if event_photos_map:
            stories = self.associate_event_photos(stories, event_photos_map)

        # Step 3: Structured Generation for each story
        structured_stories = []
        source_stories_by_id = {}
        for s in stories:
            content = await self.generate_structured_story(s, department, admin_instructions)
            structured_stories.append((s, content))
            source_stories_by_id[s["story_id"]] = s

        # Step 4: Plan Pages with Template SIET_DEFAULT_V1
        planned_pages = self.plan_magazine_pages(issue_title, department, structured_stories)

        # Step 5: Validate Pages (10-point validation)
        report = self.validator.validate_magazine(
            pages=planned_pages,
            source_stories_by_id=source_stories_by_id,
            all_event_photos_map=event_photos_map,
        )

        # Step 6: Render to PDF
        pdf_path = self.render_magazine_pdf(planned_pages, output_pdf_path)

        return planned_pages, report, pdf_path

    # -------------------------------------------------------------------------
    # 7. Single-Page Re-plan / Regeneration
    # -------------------------------------------------------------------------
    async def regenerate_page(
        self,
        page_data: Dict[str, Any],
        source_story: Dict[str, Any],
        department: str,
        admin_instructions: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Regenerates and re-plans ONLY a single affected page when validation flags issues,
        without regenerating the entire magazine.
        """
        logger.info(f"[Pipeline] Regenerating page {page_data.get('page_number')} (story: {source_story.get('story_id')})")
        updated_content = await self.generate_structured_story(source_story, department, admin_instructions)

        p_type = updated_content.page_type if updated_content.page_type in self.template.supported_page_types else page_data.get("page_type", "event")
        page_spec = self.template.get_page_spec(p_type)

        avail_photos = source_story.get("attached_photos", [])
        selected_photos = avail_photos[:page_spec.maximum_images]

        page_data.update({
            "page_type": p_type,
            "page_spec": page_spec,
            "headline": updated_content.headline,
            "subheadline": updated_content.subheadline,
            "body": updated_content.polished_body,
            "attached_photos": selected_photos,
            "captions": updated_content.photo_captions[:len(selected_photos)],
            "decorative_asset_category": updated_content.decorative_asset_category,
        })
        return page_data
