import os
import uuid
from typing import Any, Dict, List

import fitz  # PyMuPDF


def _hex_to_rgb(hex_str: str) -> tuple[float, float, float]:
    """Converts a hex color code (#RGB or #RRGGBB) to a normalized PyMuPDF RGB tuple."""
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


def render_magazine_pdf_from_blueprint(
    blueprint: Dict[str, Any],
    content: Dict[str, Any],
    output_pdf_path: str,
) -> Dict[str, Any]:
    """
    Phase 5 Deterministic PDF Renderer.
    Renders RAG-grounded magazine content directly into blueprint coordinate region bounding boxes
    (x_pt, y_pt, width_pt, height_pt) using PyMuPDF drawing primitives. Automatically scales font sizes to prevent text clipping.
    """
    doc = fitz.open()
    os.makedirs(os.path.dirname(output_pdf_path), exist_ok=True)
    os.makedirs("uploads/magazines/previews", exist_ok=True)

    bp_pages = blueprint.get("pages", [])
    if not bp_pages:
        # Default single A4 page blueprint fallback
        bp_pages = [{
            "page_number": 1,
            "width_pt": 595.28,
            "height_pt": 841.89,
            "margins": {"top": 36.0, "bottom": 36.0, "left": 36.0, "right": 36.0},
            "regions": [
                {"region_key": "p1_hero_1", "role": "hero", "x_pt": 36.0, "y_pt": 36.0, "width_pt": 523.28, "height_pt": 150.0},
                {"region_key": "p1_feature_1", "role": "feature", "x_pt": 36.0, "y_pt": 200.0, "width_pt": 523.28, "height_pt": 580.0},
            ]
        }]

    title = content.get("magazine_issue_title", "SIET Magazine Digest 2026")
    description = content.get("description", "")
    writeup_text = content.get("writeup_text", "")
    headline = content.get("writeup_headline", title)
    captions = content.get("captions", [])
    toc_summary = content.get("toc_summary", "")

    page_preview_paths: List[str] = []

    for page_idx, bp_page in enumerate(bp_pages):
        page_num = bp_page.get("page_number", page_idx + 1)
        width_pt = bp_page.get("width_pt", 595.28)
        height_pt = bp_page.get("height_pt", 841.89)

        page = doc.new_page(width=width_pt, height=height_pt)

        # Draw Background (#FDFBF7)
        page.draw_rect(fitz.Rect(0, 0, width_pt, height_pt), color=None, fill=_hex_to_rgb("#FDFBF7"))

        # Draw Decorative Frame Line
        m = bp_page.get("margins", {"top": 36, "bottom": 36, "left": 36, "right": 36})
        frame_rect = fitz.Rect(m["left"], m["top"], width_pt - m["right"], height_pt - m["bottom"])
        page.draw_rect(frame_rect, color=_hex_to_rgb("#8B0000"), width=0.75)

        regions = bp_page.get("regions", [])
        for reg in regions:
            role = reg.get("role", "feature")
            x_pt = reg.get("x_pt", 36.0)
            y_pt = reg.get("y_pt", 36.0)
            w_pt = reg.get("width_pt", 500.0)
            h_pt = reg.get("height_pt", 100.0)

            rect = fitz.Rect(x_pt, y_pt, x_pt + w_pt, y_pt + h_pt)

            if role == "header":
                header_text = f"SIET MAGAZINE — ISSUE 2026  |  PAGE {page_num}"
                page.insert_textbox(rect, header_text, fontsize=9.0, fontname="helv", color=_hex_to_rgb("#8B0000"), align=fitz.TEXT_ALIGN_LEFT)

            elif role == "footer":
                footer_text = f"Grounded AI Issue  •  {toc_summary[:60]}"
                page.insert_textbox(rect, footer_text, fontsize=8.0, fontname="helv", color=_hex_to_rgb("#555555"), align=fitz.TEXT_ALIGN_CENTER)

            elif role == "hero":
                # Draw hero background box
                page.draw_rect(rect, color=_hex_to_rgb("#8B0000"), fill=_hex_to_rgb("#8B0000"))
                hero_inner = fitz.Rect(x_pt + 10, y_pt + 10, x_pt + w_pt - 10, y_pt + h_pt - 10)
                hero_text = f"{title.upper()}\n\n{description[:180]}"
                page.insert_textbox(hero_inner, hero_text, fontsize=14.0, fontname="times-bold", color=_hex_to_rgb("#FFFFFF"), align=fitz.TEXT_ALIGN_LEFT)

            elif role == "feature":
                feature_text = f"{headline}\n\n{writeup_text}"
                # Calculate optimal font size to prevent overflow
                font_size = 10.0
                if len(feature_text) > 1200:
                    font_size = 8.5
                elif len(feature_text) > 600:
                    font_size = 9.5

                res_code = page.insert_textbox(rect, feature_text, fontsize=font_size, fontname="times-roman", color=_hex_to_rgb("#111111"), align=fitz.TEXT_ALIGN_LEFT)
                if res_code < 0:  # Text overflowed, truncate with ellipsis
                    truncated = feature_text[: int(len(feature_text) * 0.75)] + "..."
                    page.insert_textbox(rect, truncated, fontsize=font_size, fontname="times-roman", color=_hex_to_rgb("#111111"), align=fitz.TEXT_ALIGN_LEFT)

            elif role == "card":
                card_text = description if description else title
                page.draw_rect(rect, color=_hex_to_rgb("#CCCCCC"), fill=_hex_to_rgb("#FFFFFF"))
                card_inner = fitz.Rect(x_pt + 8, y_pt + 8, x_pt + w_pt - 8, y_pt + h_pt - 8)
                page.insert_textbox(card_inner, card_text[:200], fontsize=9.0, fontname="helv", color=_hex_to_rgb("#222222"), align=fitz.TEXT_ALIGN_LEFT)

            elif role == "caption":
                cap_text = captions[0] if captions else "Event highlight photograph."
                page.insert_textbox(rect, cap_text[:80], fontsize=8.5, fontname="tiro", color=_hex_to_rgb("#666666"), align=fitz.TEXT_ALIGN_LEFT)

        # Save Preview PNG
        pix = page.get_pixmap(dpi=150)
        img_name = f"render_p{page_num}_{uuid.uuid4().hex[:6]}.png"
        img_path = os.path.join("uploads/magazines/previews", img_name)
        pix.save(img_path)
        page_preview_paths.append(img_path)

    doc.save(output_pdf_path)
    doc.close()

    return {
        "pdf_path": output_pdf_path,
        "total_pages": len(bp_pages),
        "page_previews": page_preview_paths,
    }
