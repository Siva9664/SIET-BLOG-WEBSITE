import os
import uuid
from typing import Any, Dict, List

import fitz  # PyMuPDF


def analyze_template_pdf_visual_blueprint(file_bytes: bytes, filename: str) -> Dict[str, Any]:
    """
    Visual Template Blueprint Analyzer.
    Rasterizes PDF template pages into PNG images and extracts exact point coordinates (x_pt, y_pt, width_pt, height_pt),
    page margins, typography hints, and region roles (hero, feature, card, header, footer, caption).
    """
    doc = fitz.open(stream=file_bytes, filetype="pdf")
    pages_blueprint: List[Dict[str, Any]] = []

    os.makedirs("uploads/magazines/template_pages", exist_ok=True)

    for page_idx in range(len(doc)):
        page_num = page_idx + 1
        page = doc.load_page(page_idx)
        rect = page.rect
        width_pt = round(float(rect.width), 2)
        height_pt = round(float(rect.height), 2)

        # Render page to PNG image
        pix = page.get_pixmap(dpi=150)
        img_filename = f"page_{page_num}_{uuid.uuid4().hex[:6]}.png"
        img_path = os.path.join("uploads/magazines/template_pages", img_filename)
        pix.save(img_path)

        # Extract text blocks & bounding boxes: (x0, y0, x1, y1, text, block_no, block_type)
        blocks = page.get_text("blocks")
        regions: List[Dict[str, Any]] = []

        # Standard margins default
        margin_top = 36.0
        margin_bottom = 36.0
        margin_left = 36.0
        margin_right = 36.0

        if blocks:
            # Find min/max bounds to refine margins
            min_x = min(b[0] for b in blocks)
            min_y = min(b[1] for b in blocks)
            max_x = max(b[2] for b in blocks)
            max_y = max(b[3] for b in blocks)

            margin_left = round(max(18.0, min_x), 2)
            margin_top = round(max(18.0, min_y), 2)
            margin_right = round(max(18.0, width_pt - max_x), 2)
            margin_bottom = round(max(18.0, height_pt - max_y), 2)

        for block_idx, b in enumerate(blocks):
            x0, y0, x1, y1, text_content, block_no, b_type = b[:7]
            b_width = round(float(x1 - x0), 2)
            b_height = round(float(y1 - y0), 2)
            b_x = round(float(x0), 2)
            b_y = round(float(y0), 2)

            if b_width < 10 or b_height < 10:
                continue  # Skip negligible whitespace blocks

            # Determine region role based on vertical positioning and block size
            role = "feature"
            if b_y < margin_top + 40:
                role = "header"
            elif b_y > height_pt - margin_bottom - 50:
                role = "footer"
            elif page_num == 1 and b_y < height_pt * 0.35 and (b_width * b_height) > (width_pt * height_pt * 0.15):
                role = "hero"
            elif b_height < 45:
                role = "caption"
            elif b_width < (width_pt * 0.45):
                role = "card"

            region_key = f"p{page_num}_{role}_{block_idx+1}"
            text_snippet = text_content.strip().replace("\n", " ")[:60]

            regions.append({
                "region_key": region_key,
                "x_pt": b_x,
                "y_pt": b_y,
                "width_pt": b_width,
                "height_pt": b_height,
                "role": role,
                "typography": {
                    "font_family": "serif" if "cover" in text_snippet.lower() else "sans-serif",
                    "font_size_pt": 24.0 if role in ["hero", "header"] else 11.0,
                    "text_sample": text_snippet,
                },
                "color_palette": {
                    "text_color": "#111111",
                    "accent_color": "#8B0000",
                },
            })

        # Fallback default regions if no text blocks detected (e.g. image-only layout)
        if not regions:
            regions = [
                {
                    "region_key": f"p{page_num}_hero_1",
                    "x_pt": margin_left,
                    "y_pt": margin_top,
                    "width_pt": round(width_pt - margin_left - margin_right, 2),
                    "height_pt": round((height_pt - margin_top - margin_bottom) * 0.4, 2),
                    "role": "hero",
                    "typography": {"font_family": "serif", "font_size_pt": 28.0},
                    "color_palette": {"text_color": "#111111", "accent_color": "#8B0000"},
                },
                {
                    "region_key": f"p{page_num}_feature_1",
                    "x_pt": margin_left,
                    "y_pt": round(margin_top + (height_pt * 0.42), 2),
                    "width_pt": round(width_pt - margin_left - margin_right, 2),
                    "height_pt": round((height_pt - margin_top - margin_bottom) * 0.5, 2),
                    "role": "feature",
                    "typography": {"font_family": "sans-serif", "font_size_pt": 11.0},
                    "color_palette": {"text_color": "#111111", "accent_color": "#8B0000"},
                },
            ]

        pages_blueprint.append({
            "page_number": page_num,
            "width_pt": width_pt,
            "height_pt": height_pt,
            "margin_top": margin_top,
            "margin_bottom": margin_bottom,
            "margin_left": margin_left,
            "margin_right": margin_right,
            "rendered_png_path": img_path,
            "regions": regions,
        })

    return {
        "filename": filename,
        "total_pages": len(pages_blueprint),
        "pages": pages_blueprint,
    }
