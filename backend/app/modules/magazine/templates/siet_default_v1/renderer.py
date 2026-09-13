"""Deterministic PyMuPDF renderer for SIET_DEFAULT_V1 magazine template.

Implements professional publication visual grammar:
- Alternating running folios (even vs. odd page symmetry)
- Multi-column body text distribution
- Upper and lower rule framed pull quotes
- Subtle tinted sidebar cards with stroke borders
- Strict photo isolation with aspect-fit containment
- Muted micro-captions anchored to image slots
"""

from __future__ import annotations

import os
import fitz  # PyMuPDF
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import logger
from app.modules.magazine.templates.siet_default_v1.models import (
    PageTypeConfig,
    RegionRole,
    RegionSpec,
)


def _hex_to_rgb(hex_str: str) -> Tuple[float, float, float]:
    """Converts a hex color code to a normalized PyMuPDF RGB tuple."""
    if not hex_str:
        return (0.0, 0.0, 0.0)
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


def _normalize_font(font_name: Optional[str]) -> str:
    """Normalizes font name string into valid standard PyMuPDF base 14 font identifiers."""
    if not font_name:
        return "helv"
    f = font_name.lower().strip()
    mapping = {
        "helv": "helv",
        "helvetica": "helv",
        "helv-bold": "hebo",
        "hebo": "hebo",
        "helvetica-bold": "hebo",
        "helv-oblique": "heit",
        "heit": "heit",
        "times": "tiro",
        "tiro": "tiro",
        "times-roman": "tiro",
        "times-bold": "tibo",
        "tibo": "tibo",
        "times-italic": "tiit",
        "tiit": "tiit",
        "tibi": "tibi",
        "times-bolditalic": "tibi",
        "cour": "cour",
        "courier": "cour",
    }
    return mapping.get(f, "helv")


class SIETDefaultV1Renderer:
    """
    Renders planned SIET_DEFAULT_V1 page dictionaries into publication-ready PDF pages.
    """

    def render_magazine_to_pdf(
        self,
        planned_pages: List[Dict[str, Any]],
        output_pdf_path: str,
    ) -> str:
        """
        Renders an ordered list of planned magazine page dictionaries into a PDF file.
        """
        os.makedirs(os.path.dirname(output_pdf_path) or ".", exist_ok=True)
        doc = fitz.open()

        primary_rgb = _hex_to_rgb("#8B0000")  # SIET Deep Crimson
        secondary_rgb = _hex_to_rgb("#1A365D")  # SIET Academic Navy
        canvas_bg_rgb = _hex_to_rgb("#FDFBF7")  # Editorial Cream Canvas
        muted_gray_rgb = _hex_to_rgb("#6B7280")  # Folio Gray

        for page_data in planned_pages:
            page_num = page_data.get("page_number", 1)
            p_cfg: PageTypeConfig = page_data.get("page_config")

            width_pt = p_cfg.page_dimensions.get("width_pt", 595.28) if p_cfg else 595.28
            height_pt = p_cfg.page_dimensions.get("height_pt", 841.89) if p_cfg else 841.89

            page = doc.new_page(width=width_pt, height=height_pt)

            # 1. Base Cream Editorial Background Canvas
            page.draw_rect(fitz.Rect(0, 0, width_pt, height_pt), color=None, fill=canvas_bg_rgb)

            # 2. Cover / Decorative Frame (if enabled)
            decor = p_cfg.optional_decorative_assets if p_cfg else {}
            if decor.get("has_border_frame") or page_data.get("page_type") == "cover":
                frame_margin = 20.0
                frame_rect = fitz.Rect(frame_margin, frame_margin, width_pt - frame_margin, height_pt - frame_margin)
                page.draw_rect(frame_rect, color=primary_rgb, width=1.5)
                inner_rect = fitz.Rect(frame_margin + 3.0, frame_margin + 3.0, width_pt - frame_margin - 3.0, height_pt - frame_margin - 3.0)
                page.draw_rect(inner_rect, color=primary_rgb, width=0.5)

            # 3. Running Folio (Alternating Even / Odd Symmetry) for internal editorial pages
            if page_data.get("page_type") not in {"cover", "closing"}:
                is_even = (page_num % 2 == 0)
                folio_y = 818.0
                line_y = 810.0

                # Horizontal hairline above running footer
                page.draw_line(fitz.Point(36.0, line_y), fitz.Point(width_pt - 36.0, line_y), color=_hex_to_rgb("#E5E7EB"), width=0.5)

                if is_even:
                    folio_text = f"{page_num}   SIET COLLEGE MAGAZINE   •   SPRING 2026   siet.ac.in"
                    align_code = fitz.TEXT_ALIGN_LEFT
                else:
                    folio_text = f"siet.ac.in   SPRING 2026   •   SIET COLLEGE MAGAZINE   {page_num}"
                    align_code = fitz.TEXT_ALIGN_RIGHT

                folio_rect = fitz.Rect(36.0, folio_y, width_pt - 36.0, folio_y + 16.0)
                page.insert_textbox(folio_rect, folio_text, fontsize=8.0, fontname="helv", color=muted_gray_rgb, align=align_code)

            # 4. Render Regions
            if p_cfg:
                body_text = page_data.get("body", "") or ""
                # Collect body columns if multiple exist
                body_regions = [r for r in p_cfg.regions if r.role == RegionRole.BODY]
                body_parts: List[str] = []
                if len(body_regions) > 1 and body_text:
                    # Distribute body text evenly across columns
                    paragraphs = [p.strip() for p in body_text.split("\n\n") if p.strip()]
                    if len(paragraphs) >= len(body_regions):
                        chunk_size = len(paragraphs) // len(body_regions)
                        for i in range(len(body_regions)):
                            start_idx = i * chunk_size
                            end_idx = (i + 1) * chunk_size if i < len(body_regions) - 1 else len(paragraphs)
                            body_parts.append("\n\n".join(paragraphs[start_idx:end_idx]))
                    else:
                        # Split by word count roughly
                        words = body_text.split()
                        words_per_col = len(words) // len(body_regions)
                        for i in range(len(body_regions)):
                            start_w = i * words_per_col
                            end_w = (i + 1) * words_per_col if i < len(body_regions) - 1 else len(words)
                            body_parts.append(" ".join(words[start_w:end_w]))
                elif len(body_regions) == 1:
                    body_parts = [body_text]

                body_col_idx = 0

                for reg in p_cfg.regions:
                    rect = fitz.Rect(reg.x_pt, reg.y_pt, reg.x_pt + reg.width_pt, reg.y_pt + reg.height_pt)

                    # Background fill & border stroke
                    if reg.background_color_hex:
                        fill_c = _hex_to_rgb(reg.background_color_hex)
                        stroke_c = _hex_to_rgb(reg.border_color_hex) if reg.border_color_hex else None
                        b_width = reg.border_width or 1.0
                        page.draw_rect(rect, color=stroke_c, fill=fill_c, width=b_width)
                    elif reg.border_color_hex:
                        stroke_c = _hex_to_rgb(reg.border_color_hex)
                        b_width = reg.border_width or 1.0
                        page.draw_rect(rect, color=stroke_c, fill=None, width=b_width)

                    # Typography
                    f_name = _normalize_font(reg.font_family)
                    f_size = reg.font_size_max or reg.font_size or 10.0
                    txt_color = _hex_to_rgb(reg.color_hex)

                    align_code = fitz.TEXT_ALIGN_LEFT
                    if reg.align == "center":
                        align_code = fitz.TEXT_ALIGN_CENTER
                    elif reg.align == "right":
                        align_code = fitz.TEXT_ALIGN_RIGHT
                    elif reg.align == "justify":
                        align_code = fitz.TEXT_ALIGN_JUSTIFY

                    # Inset rect for padded regions
                    content_rect = fitz.Rect(rect.x0 + 4.0, rect.y0 + 4.0, rect.x1 - 4.0, rect.y1 - 4.0)

                    if reg.role == RegionRole.HEADLINE:
                        txt = page_data.get("headline", "") or ""
                        page.insert_textbox(rect, txt, fontsize=f_size, fontname=f_name, color=txt_color, align=align_code)

                    elif reg.role == RegionRole.SUBHEADLINE:
                        txt = page_data.get("subheadline", "") or ""
                        page.insert_textbox(rect, txt, fontsize=f_size, fontname=f_name, color=txt_color, align=align_code)

                    elif reg.role == RegionRole.SECTION_LABEL:
                        txt = page_data.get("section_label", "") or reg.region_key.replace("_", " ").upper()
                        page.insert_textbox(content_rect, txt, fontsize=f_size, fontname=f_name, color=txt_color, align=align_code)

                    elif reg.role == RegionRole.METADATA:
                        txt = page_data.get("metadata", "") or ""
                        page.insert_textbox(content_rect, txt, fontsize=f_size, fontname=f_name, color=txt_color, align=align_code)

                    elif reg.role == RegionRole.PULL_QUOTE:
                        txt = page_data.get("pull_quote") or f"“{page_data.get('subheadline', '')}”"
                        # Austin Chronicle style: upper and lower hairline rules
                        page.draw_line(fitz.Point(rect.x0, rect.y0), fitz.Point(rect.x1, rect.y0), color=primary_rgb, width=1.0)
                        page.draw_line(fitz.Point(rect.x0, rect.y1), fitz.Point(rect.x1, rect.y1), color=primary_rgb, width=1.0)
                        quote_inner = fitz.Rect(rect.x0, rect.y0 + 6.0, rect.x1, rect.y1 - 6.0)
                        page.insert_textbox(quote_inner, txt, fontsize=f_size, fontname=f_name, color=txt_color, align=fitz.TEXT_ALIGN_CENTER)

                    elif reg.role == RegionRole.SIDEBAR:
                        txt = page_data.get("sidebar", "") or ""
                        page.insert_textbox(content_rect, txt, fontsize=f_size, fontname=f_name, color=txt_color, align=align_code)

                    elif reg.role == RegionRole.BODY:
                        part_txt = body_parts[body_col_idx] if body_col_idx < len(body_parts) else ""
                        body_col_idx += 1
                        page.insert_textbox(rect, part_txt, fontsize=f_size, fontname=f_name, color=txt_color, align=align_code)

                # 5. Render Image Slots with strict event photo isolation
                attached_photos = page_data.get("attached_photos", [])
                captions = page_data.get("captions", [])

                for idx, slot in enumerate(p_cfg.image_slots):
                    slot_rect = fitz.Rect(slot.x_pt, slot.y_pt, slot.x_pt + slot.width_pt, slot.y_pt + slot.height_pt)

                    if idx < len(attached_photos):
                        photo_path = attached_photos[idx]
                        if os.path.exists(photo_path):
                            try:
                                page.insert_image(slot_rect, filename=photo_path, keep_proportion=True)
                            except Exception as e:
                                logger.warning(f"Failed to insert photo {photo_path}: {e}")
                        else:
                            # Render placeholder frame with photo filename
                            page.draw_rect(slot_rect, color=primary_rgb, fill=_hex_to_rgb("#E5E7EB"), width=0.75)
                            base_name = os.path.basename(photo_path)
                            page.insert_textbox(slot_rect, f"[Photo: {base_name}]", fontsize=9.0, fontname="helv", color=_hex_to_rgb("#374151"), align=fitz.TEXT_ALIGN_CENTER)

                        # Render associated caption
                        cap_txt = captions[idx] if idx < len(captions) else f"Photo {idx + 1}"
                        cap_y = min(slot.y_pt + slot.height_pt + 3.0, height_pt - 30.0)
                        cap_rect = fitz.Rect(slot.x_pt, cap_y, slot.x_pt + slot.width_pt, cap_y + 16.0)
                        page.insert_textbox(cap_rect, cap_txt, fontsize=8.0, fontname="helv", color=_hex_to_rgb("#4B5563"), align=fitz.TEXT_ALIGN_LEFT)

                    else:
                        # Slot without photo: render decorative seal or subtle background
                        if slot.role == "badge":
                            page.draw_rect(slot_rect, color=secondary_rgb, fill=_hex_to_rgb("#FEF3C7"), width=1.0)
                            page.insert_textbox(slot_rect, "[SIET SEAL]", fontsize=10.0, fontname="hebo", color=secondary_rgb, align=fitz.TEXT_ALIGN_CENTER)

        doc.save(output_pdf_path)
        doc.close()
        return output_pdf_path
