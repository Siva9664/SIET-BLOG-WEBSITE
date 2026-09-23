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
import uuid
import fitz  # PyMuPDF
from typing import Any, Dict, List, Optional, Tuple

from app.core.logging import logger
from app.modules.magazine.templates.siet_default_v1.models import (
    PageTypeConfig,
    RegionRole,
    RegionSpec,
)


from app.modules.magazine.templates.siet_default_v1.config import build_siet_default_v1_template


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


def _clean_text_for_pdf(text: str) -> str:
    """Sanitizes text to WinAnsi compatible characters for standard PyMuPDF fonts."""
    if not text:
        return ""
    replacements = {
        "•": "-",
        "—": "--",
        "–": "-",
        "“": '"',
        "”": '"',
        "‘": "'",
        "’": "'",
        "★": "*",
        "☆": "*",
        "✓": "v",
        "✔": "v",
        "₹": "Rs. ",
        "…": "...",
        "\u00a0": " ",
        "\u200b": "",
        "\u200c": "",
        "\u200d": "",
        "\ufeff": "",
    }
    for old, new in replacements.items():
        text = text.replace(old, new)
    return text


def _insert_text_autofit(
    page: fitz.Page,
    rect: fitz.Rect,
    text: str,
    fontname: str,
    fontsize: float,
    color: Tuple[float, float, float],
    align: int,
    min_fontsize: float = 6.0,
) -> float:
    """Inserts text into a rect, scaling font size down smoothly if it exceeds boundaries."""
    txt = _clean_text_for_pdf(text)
    if not txt.strip():
        return 0.0
    fs = float(fontsize)
    while fs >= min_fontsize:
        rc = page.insert_textbox(rect, txt, fontsize=fs, fontname=fontname, color=color, align=align)
        if rc >= 0:
            return rc
        fs -= 0.5
    return page.insert_textbox(rect, txt, fontsize=min_fontsize, fontname=fontname, color=color, align=align)


class SIETDefaultV1Renderer:
    """
    Renders planned SIET_DEFAULT_V1 page dictionaries into publication-ready PDF pages.
    """

    def __init__(self, template=None):
        self.template = template or build_siet_default_v1_template()
        self.generated_previews: List[str] = []

    def render_magazine_to_pdf(
        self,
        planned_pages: List[Dict[str, Any]],
        output_pdf_path: str,
    ) -> str:
        """
        Renders an ordered list of planned magazine page dictionaries into a PDF file.
        """
        os.makedirs(os.path.dirname(output_pdf_path) or ".", exist_ok=True)
        os.makedirs("uploads/magazines/previews", exist_ok=True)
        doc = fitz.open()

        page_preview_paths: List[str] = []
        primary_rgb = _hex_to_rgb("#8B0000")  # SIET Deep Crimson
        secondary_rgb = _hex_to_rgb("#1A365D")  # SIET Academic Navy
        canvas_bg_rgb = _hex_to_rgb("#FDFBF7")  # Editorial Cream Canvas
        muted_gray_rgb = _hex_to_rgb("#6B7280")  # Folio Gray

        for page_data in planned_pages:
            page_num = page_data.get("page_number", 1)
            p_cfg: Optional[PageTypeConfig] = page_data.get("page_config")
            if not p_cfg:
                p_type_key = str(page_data.get("page_type", "event"))
                if p_type_key == "closing_page":
                    p_type_key = "closing"
                elif p_type_key == "achievement_victory":
                    p_type_key = "achievement"
                p_cfg = self.template.page_types.get(p_type_key) or self.template.page_types.get("event")

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
                    folio_text = f"{page_num}   SIET COLLEGE MAGAZINE   -   SPRING 2026   siet.ac.in"
                    align_code = fitz.TEXT_ALIGN_LEFT
                else:
                    folio_text = f"siet.ac.in   SPRING 2026   -   SIET COLLEGE MAGAZINE   {page_num}"
                    align_code = fitz.TEXT_ALIGN_RIGHT

                folio_rect = fitz.Rect(36.0, folio_y, width_pt - 36.0, folio_y + 16.0)
                _insert_text_autofit(page, folio_rect, folio_text, "helv", 8.0, muted_gray_rgb, align_code)

            # 4. Render Regions
            if p_cfg:
                body_text = page_data.get("body", "") or ""
                attached_photos = page_data.get("attached_photos", [])
                right_sidebars = [r for r in p_cfg.regions if r.role == RegionRole.SIDEBAR and r.x_pt >= 350.0]
                has_right_sidebar = len(right_sidebars) > 0
                left_sidebars = [r for r in p_cfg.regions if r.role == RegionRole.SIDEBAR and r.x_pt < 350.0]

                # Collect body columns if multiple exist
                body_regions = [r for r in p_cfg.regions if r.role == RegionRole.BODY]
                body_parts: List[str] = []

                # If page has 0 photos and a right sidebar exists, allocate full body text
                # to the primary editorial column (left of sidebar)
                if not attached_photos and has_right_sidebar:
                    body_parts = [body_text]
                elif len(body_regions) > 1 and body_text:
                    paragraphs = [p.strip() for p in body_text.split("\n\n") if p.strip()]
                    if len(paragraphs) >= len(body_regions):
                        chunk_size = len(paragraphs) // len(body_regions)
                        for i in range(len(body_regions)):
                            start_idx = i * chunk_size
                            end_idx = (i + 1) * chunk_size if i < len(body_regions) - 1 else len(paragraphs)
                            body_parts.append("\n\n".join(paragraphs[start_idx:end_idx]))
                    else:
                        words = body_text.split()
                        words_per_col = max(1, len(words) // len(body_regions))
                        for i in range(len(body_regions)):
                            start_w = i * words_per_col
                            end_w = (i + 1) * words_per_col if i < len(body_regions) - 1 else len(words)
                            body_parts.append(" ".join(words[start_w:end_w]))
                elif len(body_regions) == 1:
                    body_parts = [body_text]

                body_col_idx = 0

                for reg in p_cfg.regions:
                    rect = fitz.Rect(reg.x_pt, reg.y_pt, reg.x_pt + reg.width_pt, reg.y_pt + reg.height_pt)

                    # Adapt positions if page has 0 photos
                    if not attached_photos and page_data.get("page_type") not in {"cover", "contents", "closing", "closing_page"}:
                        pt_name = p_cfg.page_type.value if hasattr(p_cfg.page_type, "value") else str(p_cfg.page_type)
                        if has_right_sidebar:
                            pass
                        elif pt_name == "victory":
                            if reg.role == RegionRole.PULL_QUOTE:
                                rect = fitz.Rect(reg.x_pt, 155.0, reg.x_pt + reg.width_pt, 285.0)
                            elif reg.role == RegionRole.SIDEBAR:
                                rect = fitz.Rect(reg.x_pt, 305.0, reg.x_pt + reg.width_pt, 770.0)
                        elif left_sidebars and reg.role == RegionRole.SIDEBAR:
                            rect = fitz.Rect(reg.x_pt, 145.0, reg.x_pt + reg.width_pt, 770.0)

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

                    content_rect = fitz.Rect(rect.x0 + 4.0, rect.y0 + 4.0, rect.x1 - 4.0, rect.y1 - 4.0)

                    if reg.role == RegionRole.HEADLINE:
                        if reg.region_key == "cover_masthead":
                            txt = "SIET AI RESEARCH LAB"
                        else:
                            txt = page_data.get("headline", "") or ""
                        _insert_text_autofit(page, rect, txt, f_name, f_size, txt_color, align_code)

                    elif reg.role == RegionRole.SUBHEADLINE:
                        txt = page_data.get("subheadline", "") or ""
                        _insert_text_autofit(page, rect, txt, f_name, f_size, txt_color, align_code)

                    elif reg.role == RegionRole.SECTION_LABEL:
                        txt = page_data.get("section_label", "") or reg.region_key.replace("_", " ").upper()
                        _insert_text_autofit(page, content_rect, txt, f_name, f_size, txt_color, align_code)

                    elif reg.role == RegionRole.METADATA:
                        txt = page_data.get("metadata", "") or ""
                        _insert_text_autofit(page, content_rect, txt, f_name, f_size, txt_color, align_code)

                    elif reg.role == RegionRole.PULL_QUOTE:
                        txt = page_data.get("pull_quote") or f'"{page_data.get("subheadline", "")}"'
                        page.draw_line(fitz.Point(rect.x0, rect.y0), fitz.Point(rect.x1, rect.y0), color=primary_rgb, width=1.0)
                        page.draw_line(fitz.Point(rect.x0, rect.y1), fitz.Point(rect.x1, rect.y1), color=primary_rgb, width=1.0)
                        quote_inner = fitz.Rect(rect.x0, rect.y0 + 6.0, rect.x1, rect.y1 - 6.0)
                        _insert_text_autofit(page, quote_inner, txt, f_name, f_size, txt_color, fitz.TEXT_ALIGN_CENTER)

                    elif reg.role == RegionRole.SIDEBAR:
                        txt = page_data.get("sidebar", "") or ""
                        _insert_text_autofit(page, content_rect, txt, f_name, f_size, txt_color, align_code)

                    elif reg.role == RegionRole.BODY:
                        if not attached_photos and page_data.get("page_type") not in {"cover", "contents", "closing", "closing_page"}:
                            if has_right_sidebar:
                                if body_col_idx == 0:
                                    sb_left = min(sb.x_pt for sb in right_sidebars)
                                    body_rect = fitz.Rect(36.0, 155.0, sb_left - 15.0, 770.0)
                                    part_txt = body_text
                                    body_col_idx += 1
                                    _insert_text_autofit(page, body_rect, part_txt, f_name, f_size, txt_color, fitz.TEXT_ALIGN_JUSTIFY)
                                else:
                                    body_col_idx += 1
                                    continue
                            else:
                                part_txt = body_parts[body_col_idx] if body_col_idx < len(body_parts) else ""
                                body_col_idx += 1
                                if rect.y0 > 300.0:
                                    body_rect = fitz.Rect(rect.x0, 155.0, rect.x1, 790.0)
                                else:
                                    body_rect = rect
                                _insert_text_autofit(page, body_rect, part_txt, f_name, f_size, txt_color, align_code)
                        else:
                            part_txt = body_parts[body_col_idx] if body_col_idx < len(body_parts) else ""
                            body_col_idx += 1
                            _insert_text_autofit(page, rect, part_txt, f_name, f_size, txt_color, align_code)

                # 5. Render Image Slots with strict event photo isolation and adaptive grid
                captions = page_data.get("captions", [])
                active_slots: List[fitz.Rect] = []

                if len(attached_photos) == 2 and len(p_cfg.image_slots) == 1:
                    hero_slot = p_cfg.image_slots[0]
                    gap = 10.0
                    w = (hero_slot.width_pt - gap) / 2.0
                    active_slots.append(fitz.Rect(hero_slot.x_pt, hero_slot.y_pt, hero_slot.x_pt + w, hero_slot.y_pt + hero_slot.height_pt))
                    active_slots.append(fitz.Rect(hero_slot.x_pt + w + gap, hero_slot.y_pt, hero_slot.x_pt + hero_slot.width_pt, hero_slot.y_pt + hero_slot.height_pt))
                elif len(attached_photos) == 3 and len(p_cfg.image_slots) <= 2:
                    hero_slot = p_cfg.image_slots[0]
                    gap = 8.0
                    w_left = hero_slot.width_pt * 0.58
                    h_half = (hero_slot.height_pt - gap) / 2.0
                    active_slots.append(fitz.Rect(hero_slot.x_pt, hero_slot.y_pt, hero_slot.x_pt + w_left, hero_slot.y_pt + hero_slot.height_pt))
                    active_slots.append(fitz.Rect(hero_slot.x_pt + w_left + gap, hero_slot.y_pt, hero_slot.x_pt + hero_slot.width_pt, hero_slot.y_pt + h_half))
                    active_slots.append(fitz.Rect(hero_slot.x_pt + w_left + gap, hero_slot.y_pt + h_half + gap, hero_slot.x_pt + hero_slot.width_pt, hero_slot.y_pt + hero_slot.height_pt))
                else:
                    for slot in p_cfg.image_slots:
                        active_slots.append(fitz.Rect(slot.x_pt, slot.y_pt, slot.x_pt + slot.width_pt, slot.y_pt + slot.height_pt))

                for idx, slot_rect in enumerate(active_slots):
                    if idx < len(attached_photos):
                        raw_photo = attached_photos[idx]
                        if isinstance(raw_photo, dict):
                            photo_path = raw_photo.get("disk_path") or raw_photo.get("url") or ""
                        else:
                            photo_path = str(raw_photo)
                        disk_path = photo_path
                        if not os.path.exists(disk_path):
                            clean = photo_path.lstrip("/")
                            if os.path.exists(clean):
                                disk_path = clean
                            elif os.path.exists(os.path.join("backend", clean)):
                                disk_path = os.path.join("backend", clean)

                        if os.path.exists(disk_path):
                            try:
                                page.insert_image(slot_rect, filename=disk_path, keep_proportion=True)
                            except Exception as e:
                                logger.warning(f"Failed to render image {disk_path}: {e}")
                        else:
                            page.draw_rect(slot_rect, color=primary_rgb, fill=_hex_to_rgb("#E5E7EB"), width=0.75)
                            base_name = os.path.basename(photo_path)
                            _insert_text_autofit(page, slot_rect, f"[Photo: {base_name}]", "helv", 9.0, _hex_to_rgb("#374151"), fitz.TEXT_ALIGN_CENTER)

                        # Render associated caption
                        cap_txt = captions[idx] if idx < len(captions) else f"Photo {idx + 1}"
                        cap_y = min(slot_rect.y1 + 3.0, height_pt - 30.0)
                        cap_rect = fitz.Rect(slot_rect.x0, cap_y, slot_rect.x1, cap_y + 16.0)
                        _insert_text_autofit(page, cap_rect, cap_txt, "helv", 8.0, _hex_to_rgb("#4B5563"), fitz.TEXT_ALIGN_LEFT)
                    else:
                        if page_data.get("page_type") == "cover":
                            # Dignified institutional crest & seal for cover without hero photo
                            emblem_rect = fitz.Rect(120.0, 180.0, width_pt - 120.0, 500.0)
                            page.draw_rect(emblem_rect, color=primary_rgb, fill=_hex_to_rgb("#FFFBEB"), width=1.5)
                            inner_emblem = fitz.Rect(emblem_rect.x0 + 6.0, emblem_rect.y0 + 6.0, emblem_rect.x1 - 6.0, emblem_rect.y1 - 6.0)
                            page.draw_rect(inner_emblem, color=primary_rgb, fill=None, width=0.5)
                            emblem_txt = (
                                "SRI SHAKTHI\n"
                                "INSTITUTE OF ENGINEERING & TECHNOLOGY\n\n"
                                "* * *\n"
                                "[ INSTITUTIONAL HERALDIC CREST ]\n"
                                "* * *\n\n"
                                "COLLEGE OF AUTONOMOUS EXCELLENCE\n"
                                "DEPARTMENT OF ARTIFICIAL INTELLIGENCE & DATA SCIENCE\n"
                                "COIMBATORE, TAMIL NADU"
                            )
                            _insert_text_autofit(page, inner_emblem, emblem_txt, "hebo", 11.0, primary_rgb, fitz.TEXT_ALIGN_CENTER)
                        else:
                            # 0 photos attached: text-first editorial layout - do not fabricate images
                            pass

            # Generate high-resolution preview PNG for web reader
            pix = page.get_pixmap(dpi=150)
            img_name = f"render_p{page_num}_{uuid.uuid4().hex[:6]}.png"
            img_path = os.path.join("uploads/magazines/previews", img_name)
            pix.save(img_path)
            page_preview_paths.append(img_path)

        doc.save(output_pdf_path)
        doc.close()
        self.generated_previews = page_preview_paths
        return output_pdf_path

    def render_magazine_with_previews(
        self,
        planned_pages: List[Dict[str, Any]],
        output_pdf_path: str,
    ) -> Dict[str, Any]:
        """Renders PDF and returns path, page count, and preview images list."""
        pdf_path = self.render_magazine_to_pdf(planned_pages, output_pdf_path)
        return {
            "pdf_path": pdf_path,
            "total_pages": len(planned_pages),
            "page_previews": self.generated_previews,
        }

