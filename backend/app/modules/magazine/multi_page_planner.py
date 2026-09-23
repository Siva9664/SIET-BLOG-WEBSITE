"""Multi-Page Magazine Planning Service.

Automatically determines the required page sequence and page count for a magazine
based on structured content, available photographs, candidate templates,
section ordering, and laboratory/department constraints.

Workflow:
    Structured Content + Photos + Templates + Section Order
    -> MultiPagePlanner
    -> Sequential Page Sequence with Capacities & Layout Alternation
"""

from __future__ import annotations

import copy
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.logging import logger
from app.modules.magazine.schemas import (
    MultiPagePlannedPage,
    MultiPagePlanRequest,
    MultiPagePlanResponse,
)
from app.modules.magazine.template_library import (
    get_standard_templates,
    get_template_by_id,
)
from app.modules.magazine.template_schema import (
    TemplateMetadata,
    normalize_page_type,
    normalize_template_metadata,
)

# Canonical sequential order for college magazines
CANONICAL_SECTION_ORDER = [
    "introduction",
    "project_showcase",
    "student_achievement",
    "achievement",
    "faculty_achievement",
    "event",
    "research",
    "photo_gallery",
    "closing_page",
]

# Standard layout variants to alternate when repeating the same template
LAYOUT_VARIANTS = [
    "standard_hero",
    "split_column",
    "compact_grid",
    "asymmetric_feature",
    "editorial_spread",
]


def _normalize_content_items(
    structured_content: Union[Dict[str, Any], List[Any]],
) -> Dict[str, List[Dict[str, Any]]]:
    """
    Standardizes flexible content inputs into a mapping of {section_page_type: [item_records]}.
    Handles:
      1. Pure numeric count dict: {"projects": 25, "achievements": 18, "photos": 40, "events": 10}
      2. Dict of section lists: {"projects": [...], "achievements": [...], "events": [...]}
      3. Dict with 'sections' subdict: {"department_or_lab": "AI Lab", "sections": {...}}
      4. Flat list of items with 'type' or 'section' fields.
    """
    sections_map: Dict[str, List[Dict[str, Any]]] = {}

    if isinstance(structured_content, dict):
        raw_sections = structured_content.get("sections")
        data_to_parse = raw_sections if isinstance(raw_sections, dict) else structured_content

        for raw_sec_key, raw_val in data_to_parse.items():
            if raw_sec_key in ("department_or_lab", "department", "lab", "title", "metadata"):
                continue

            sec_type = normalize_page_type(raw_sec_key)
            if sec_type == "achievement":
                sec_type = "student_achievement"

            if sec_type not in sections_map:
                sections_map[sec_type] = []

            # Case A: Integer count passed (e.g. {"projects": 25})
            if isinstance(raw_val, int):
                for idx in range(raw_val):
                    sections_map[sec_type].append({
                        "id": f"{sec_type}_{idx + 1:02d}",
                        "title": f"{sec_type.replace('_', ' ').title()} #{idx + 1}",
                        "summary": f"Content item record #{idx + 1} for {sec_type}.",
                        "estimated_words": 120,
                        "photos": [],
                    })

            # Case B: List of items
            elif isinstance(raw_val, list):
                for idx, item in enumerate(raw_val):
                    if isinstance(item, dict):
                        item_copy = dict(item)
                        if "id" not in item_copy:
                            item_copy["id"] = f"{sec_type}_{idx + 1:02d}"
                        if "estimated_words" not in item_copy:
                            text_body = str(item_copy.get("body") or item_copy.get("summary") or item_copy.get("description") or "")
                            item_copy["estimated_words"] = len(text_body.split()) if text_body else 100
                        sections_map[sec_type].append(item_copy)
                    else:
                        sections_map[sec_type].append({
                            "id": f"{sec_type}_{idx + 1:02d}",
                            "title": str(item),
                            "estimated_words": 100,
                            "photos": [],
                        })

            # Case C: Single item dict (e.g. overview or introduction)
            elif isinstance(raw_val, dict):
                item_copy = dict(raw_val)
                if "id" not in item_copy:
                    item_copy["id"] = f"{sec_type}_01"
                text_body = str(item_copy.get("body") or item_copy.get("summary") or item_copy.get("description") or "")
                item_copy["estimated_words"] = len(text_body.split()) if text_body else 180
                sections_map[sec_type].append(item_copy)

    elif isinstance(structured_content, list):
        for idx, item in enumerate(structured_content):
            if isinstance(item, dict):
                raw_type = item.get("type") or item.get("section") or item.get("page_type") or "article"
                sec_type = normalize_page_type(str(raw_type))
                if sec_type not in sections_map:
                    sections_map[sec_type] = []
                item_copy = dict(item)
                if "id" not in item_copy:
                    item_copy["id"] = f"{sec_type}_{idx + 1:02d}"
                text_body = str(item_copy.get("body") or item_copy.get("summary") or item_copy.get("description") or "")
                item_copy["estimated_words"] = len(text_body.split()) if text_body else 100
                sections_map[sec_type].append(item_copy)

    return sections_map


def _normalize_image_pool(available_images: List[Any]) -> List[Dict[str, Any]]:
    """Normalizes candidate images into a standardized list of photo dictionaries."""
    normalized: List[Dict[str, Any]] = []
    for idx, img in enumerate(available_images or []):
        if isinstance(img, dict):
            url = img.get("url") or img.get("local_path") or img.get("filename") or f"photo_{idx + 1}.jpg"
            normalized.append({
                "id": str(img.get("id") or img.get("photo_id") or f"photo_{idx + 1:02d}"),
                "url": url,
                "caption": img.get("caption") or "",
            })
        elif isinstance(img, str):
            normalized.append({
                "id": f"photo_{idx + 1:02d}",
                "url": img,
                "caption": "",
            })
    return normalized


def _find_candidate_templates_for_section(
    section_page_type: str,
    department_or_lab: Optional[str],
    available_templates: List[TemplateMetadata],
    available_image_count: int,
    forced_template_id: Optional[str] = None,
) -> List[Tuple[TemplateMetadata, float]]:
    """
    Finds and ranks candidate templates for a section.
    Scoring factors:
      - Page type compatibility (+100)
      - Explicit admin forced/chosen template match (+500)
      - Exact laboratory affinity match (+80)
      - Department match (+40)
      - Image requirement feasibility (+15 if images available; -30 if strict image shortage)
    """
    ranked: List[Tuple[TemplateMetadata, float]] = []
    norm_section = normalize_page_type(section_page_type)
    target_lab = (department_or_lab or "").strip().lower()

    for tmpl in available_templates:
        score = 0.0

        # Check explicit forced template match
        if forced_template_id:
            clean_forced = str(forced_template_id).strip().lower()
            tid = str(tmpl.template_id or "").strip().lower()
            tname = str(tmpl.name or "").strip().lower()
            if clean_forced in (tid, tname) or clean_forced == tid:
                score += 500.0

        # Check page type match
        if tmpl.page_type == norm_section:
            score += 120.0
        elif tmpl.supports_content_type(norm_section):
            score += 90.0
        elif norm_section in ("project_showcase", "research") and tmpl.page_type in ("project_showcase", "research", "article"):
            score += 50.0
        else:
            continue

        # Exact section slug in template ID bonus
        if norm_section in tmpl.template_id:
            score += 15.0

        # Check lab affinity
        tmpl_lab = (tmpl.lab or "").strip().lower()
        tmpl_dept = (tmpl.department or "").strip().lower()

        if target_lab and tmpl_lab:
            if target_lab in tmpl_lab or tmpl_lab in target_lab:
                score += 80.0
            else:
                # Explicitly belongs to a different lab
                score -= 60.0
        elif target_lab and tmpl_dept:
            if target_lab in tmpl_dept or tmpl_dept in target_lab:
                score += 40.0
            else:
                score -= 20.0
        elif not tmpl.lab and not tmpl.department:
            # Generic institutional template
            score += 20.0

        # Check image availability
        min_imgs = tmpl.layout_constraints.get("min_images", 0)
        if available_image_count >= min_imgs:
            score += 15.0
        else:
            # Downrank if not enough images
            score -= 30.0

        ranked.append((tmpl, score))

    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return ranked


def _extract_template_capacities(tmpl: TemplateMetadata) -> Dict[str, int]:
    """Extracts min_items, max_items, and target_items for a template."""
    constraints = tmpl.layout_constraints or {}
    pt = tmpl.page_type

    # Default item bounds based on layout type
    if pt == "project_showcase":
        default_min, default_max, default_target = 1, 2, 1
        if "gallery" in tmpl.template_id or "grid" in tmpl.template_id:
            default_min, default_max, default_target = 2, 4, 3
    elif pt in ("student_achievement", "faculty_achievement", "achievement"):
        default_min, default_max, default_target = 1, 2, 1
        if "grid" in tmpl.template_id or "roll" in tmpl.template_id:
            default_min, default_max, default_target = 2, 4, 3
    elif pt == "photo_gallery":
        default_min, default_max, default_target = 3, 8, 6
    elif pt == "introduction":
        default_min, default_max, default_target = 1, 1, 1
    elif pt == "event":
        default_min, default_max, default_target = 1, 2, 1
    else:
        default_min, default_max, default_target = 1, 2, 1

    min_items = int(constraints.get("min_items", default_min))
    max_items = int(constraints.get("max_items", default_max))
    target_items = int(constraints.get("target_items", default_target))

    return {
        "min_items": max(1, min_items),
        "max_items": max(min_items, max_items),
        "target_items": max(min_items, min(max_items, target_items)),
    }


def plan_multi_page_magazine(
    structured_content: Union[Dict[str, Any], List[Any]],
    department_or_lab: Optional[str] = None,
    available_images: Optional[List[Any]] = None,
    available_templates: Optional[List[Any]] = None,
    template_constraints: Optional[Dict[str, Any]] = None,
    magazine_section_order: Optional[List[str]] = None,
    max_pages: Optional[int] = None,
    start_page_number: int = 1,
) -> MultiPagePlanResponse:
    """
    Main Multi-Page Planning Entrypoint.

    Converts raw section items, photos, and template capabilities into a sequential
    magazine page plan, preventing overcrowding, avoiding excessive whitespace,
    and ensuring visual variety.
    """
    logger.info(
        f"[MultiPagePlanner] Planning magazine sequence for '{department_or_lab or 'General'}'. "
        f"Start page: {start_page_number}, max_pages limit: {max_pages or 'unlimited'}"
    )

    # 1. Normalize content items by section
    sections_map = _normalize_content_items(structured_content)

    # 2. Normalize candidate image pool
    image_pool = _normalize_image_pool(available_images or [])
    image_pool_idx = 0

    # 3. Resolve template candidate pool
    raw_templates = available_templates or get_standard_templates()
    template_pool: List[TemplateMetadata] = []
    for t in raw_templates:
        if isinstance(t, TemplateMetadata):
            template_pool.append(t)
        elif isinstance(t, dict):
            template_pool.append(normalize_template_metadata(t))
        elif isinstance(t, str):
            resolved = get_template_by_id(t)
            if resolved:
                template_pool.append(normalize_template_metadata(resolved))

    # Guarantee fallback template if pool is completely empty
    if not template_pool:
        standard = get_standard_templates()
        template_pool = [normalize_template_metadata(t) for t in standard]

    # 4. Determine ordered sequence of sections
    active_sections: List[str] = []
    if magazine_section_order:
        for s in magazine_section_order:
            norm_s = normalize_page_type(s)
            if norm_s == "achievement" and "student_achievement" in sections_map:
                norm_s = "student_achievement"
            if norm_s in sections_map and norm_s not in active_sections:
                active_sections.append(norm_s)
            elif norm_s == "photo_gallery" and norm_s not in active_sections:
                active_sections.append(norm_s)
    else:
        for s in CANONICAL_SECTION_ORDER:
            if s in sections_map and s not in active_sections:
                active_sections.append(s)

    # Include any remaining sections in content that were not explicitly listed
    for s in sections_map.keys():
        if s not in active_sections:
            active_sections.append(s)

    # Handle stand-alone photo gallery if photographs exist but no photo gallery section was provided
    if "photo_gallery" not in sections_map and len(image_pool) >= 4 and "photo_gallery" not in active_sections:
        active_sections.append("photo_gallery")
        sections_map["photo_gallery"] = []

    planned_pages: List[MultiPagePlannedPage] = []
    current_page_num = start_page_number
    last_used_template_id: Optional[str] = None
    section_page_counter: Dict[str, int] = {s: 0 for s in active_sections}

    # 5. Pack items into pages section-by-section
    for sec_name in active_sections:
        items = sections_map.get(sec_name, [])
        remaining_items = list(items)

        # Handle special photo gallery section
        if sec_name == "photo_gallery" and not remaining_items:
            # Photos become items for the gallery
            unassigned_photos = image_pool[image_pool_idx:]
            if len(unassigned_photos) >= 3:
                remaining_items = [
                    {"id": p["id"], "title": f"Gallery Photo #{i+1}", "photos": [p["url"]]}
                    for i, p in enumerate(unassigned_photos)
                ]

        if not remaining_items and sec_name != "photo_gallery":
            continue

        item_cursor = 0
        total_items_in_sec = len(remaining_items)

        while item_cursor < total_items_in_sec:
            # Check max_pages constraint
            if max_pages is not None and len(planned_pages) >= max_pages:
                logger.info(f"[MultiPagePlanner] Reached maximum page budget ({max_pages}). Stopping page expansion.")
                break

            items_left = total_items_in_sec - item_cursor
            avail_imgs = max(0, len(image_pool) - image_pool_idx)

            # Find matching candidate templates
            forced_tid = (template_constraints or {}).get("forced_template_id")
            candidate_pairs = _find_candidate_templates_for_section(
                section_page_type=sec_name,
                department_or_lab=department_or_lab,
                available_templates=template_pool,
                available_image_count=avail_imgs,
                forced_template_id=forced_tid,
            )

            # Fallback if no specific templates found
            if not candidate_pairs:
                fallback_meta = template_pool[0]
                candidate_pairs = [(fallback_meta, 1.0)]

            # Selection with layout alternation
            selected_tmpl: TemplateMetadata = candidate_pairs[0][0]

            # If top candidate is identical to last page and alternative exists, alternate!
            if len(candidate_pairs) > 1 and candidate_pairs[0][0].template_id == last_used_template_id:
                # Pick the second best candidate for visual variety
                selected_tmpl = candidate_pairs[1][0]
            else:
                selected_tmpl = candidate_pairs[0][0]

            # If only 1 item remains and candidate is a heavy grid (min_items >= 3),
            # try to find a single-item spotlight/showcase template to avoid excessive whitespace
            if items_left <= 2 and _extract_template_capacities(selected_tmpl)["min_items"] > items_left:
                for alt_tmpl, _ in candidate_pairs:
                    caps = _extract_template_capacities(alt_tmpl)
                    if caps["min_items"] <= items_left:
                        selected_tmpl = alt_tmpl
                        break

            capacities = _extract_template_capacities(selected_tmpl)
            batch_size = min(capacities["max_items"], items_left)

            # Ensure we don't leave 1 lone item stranded if we have e.g. 3 items left and max is 2
            if items_left - batch_size == 1 and batch_size > 1 and items_left > 1:
                # Balance into 2 + 1 or adjust batch size
                batch_size = 2 if capacities["max_items"] >= 2 else 1

            batch = remaining_items[item_cursor : item_cursor + batch_size]
            item_cursor += len(batch)

            # Assign photographs to page
            target_photos_count = selected_tmpl.image_count or 1
            assigned_page_images: List[str] = []

            for itm in batch:
                if itm.get("photos"):
                    assigned_page_images.extend(itm["photos"])

            while len(assigned_page_images) < target_photos_count and image_pool_idx < len(image_pool):
                assigned_page_images.append(image_pool[image_pool_idx]["url"])
                image_pool_idx += 1

            # Determine layout variant (rotates when template is reused)
            page_index_in_section = section_page_counter[sec_name]
            variant_index = page_index_in_section % len(LAYOUT_VARIANTS)
            layout_variant = LAYOUT_VARIANTS[variant_index]

            total_word_count = sum(itm.get("estimated_words", 80) for itm in batch)

            page_plan = MultiPagePlannedPage(
                page_number=current_page_num,
                template_id=selected_tmpl.template_id,
                content_ids=[itm["id"] for itm in batch],
                section=sec_name.replace("_", " ").title(),
                page_type=selected_tmpl.page_type,
                layout_variant=layout_variant,
                assigned_images=assigned_page_images,
                word_count=total_word_count,
                items_count=len(batch),
                metadata={
                    "department_or_lab": department_or_lab,
                    "template_name": selected_tmpl.name,
                    "section_page_index": page_index_in_section + 1,
                    "target_images": target_photos_count,
                    "is_alternate_layout": (selected_tmpl.template_id == last_used_template_id),
                },
            )

            planned_pages.append(page_plan)
            last_used_template_id = selected_tmpl.template_id
            section_page_counter[sec_name] += 1
            current_page_num += 1

    # 6. Compute section summary breakdown
    section_breakdown: Dict[str, int] = {}
    for p in planned_pages:
        sec = p.section or "General"
        section_breakdown[sec] = section_breakdown.get(sec, 0) + 1

    return MultiPagePlanResponse(
        pages=planned_pages,
        total_pages=len(planned_pages),
        section_sequence=[p.section or "" for p in planned_pages],
        section_breakdown=section_breakdown,
        department_or_lab=department_or_lab,
        metadata={
            "allocated_image_count": image_pool_idx,
            "total_available_images": len(image_pool),
            "start_page_number": start_page_number,
        },
    )
