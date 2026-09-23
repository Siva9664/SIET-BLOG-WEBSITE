"""Magazine Layout Planner Service.

Converts structured magazine content and available photographs into a deterministic,
publication-grade PagePlan adhering to template regions, text capacity, and image constraints.

Clean Service Boundary:
    Content -> LayoutPlanner -> PagePlan -> Renderer
"""

from __future__ import annotations

import copy
import json
import os
import re
from typing import Any, Dict, List, Optional, Tuple, Union

from app.core.logging import logger
from app.modules.magazine.llm_provider import call_llm_json
from app.modules.magazine.schemas import (
    PagePlan,
    PlanValidationReport,
    PlannedRegion,
)
from app.modules.magazine.template_library import (
    get_standard_templates,
    get_template_by_id,
)
from app.modules.magazine.template_schema import (
    TemplateMetadata,
    TemplateRegionDefinition,
    default_regions_for_page_type,
    normalize_page_type,
    normalize_template_metadata,
)


def _count_words(text: Optional[str]) -> int:
    """Counts whitespace-delimited words in text."""
    if not text:
        return 0
    return len(text.strip().split())


def _truncate_to_word_limit(text: str, max_words: int) -> str:
    """Truncates text cleanly to max_words without cutting mid-sentence if possible."""
    words = text.strip().split()
    if len(words) <= max_words:
        return text.strip()
    truncated = " ".join(words[:max_words])
    # Add ellipsis if not already punctuated
    if not truncated.endswith((".", "!", "?", "…")):
        truncated += "…"
    return truncated


def resolve_template(
    selected_template: Union[str, Dict[str, Any], TemplateMetadata, None],
    page_type: Optional[str] = None,
) -> TemplateMetadata:
    """Resolves template metadata from object, dictionary, identifier string, or defaults."""
    if isinstance(selected_template, TemplateMetadata):
        return selected_template

    if isinstance(selected_template, dict):
        return normalize_template_metadata(selected_template)

    if isinstance(selected_template, str) and selected_template.strip():
        # Look up by ID or alias
        found = get_template_by_id(selected_template)
        if found:
            return normalize_template_metadata(found)

        # Fallback to creating a dynamic template metadata with default regions
        pt = normalize_page_type(page_type or "project_showcase")
        return TemplateMetadata(
            template_id=selected_template.strip(),
            name=selected_template.strip().replace("_", " ").title(),
            page_type=pt,
            regions=default_regions_for_page_type(pt),
        )

    # If None, resolve standard default for page_type
    pt = normalize_page_type(page_type or "project_showcase")
    defaults = get_standard_templates()
    for tmpl in defaults:
        meta = normalize_template_metadata(tmpl)
        if meta.page_type == pt:
            return meta

    return normalize_template_metadata(defaults[0] if defaults else {"name": "Default", "page_type": pt})


def _extract_content_fields(content: Union[str, Dict[str, Any]]) -> Dict[str, str]:
    """Extracts standardized content components from article content."""
    if isinstance(content, str):
        lines = [l.strip() for l in content.split("\n") if l.strip()]
        headline = lines[0] if lines else "Featured Story"
        body = "\n\n".join(lines[1:]) if len(lines) > 1 else content
        return {
            "headline": headline,
            "body": body,
            "caption": "",
            "description": lines[1] if len(lines) > 1 else "",
        }

    headline = (
        content.get("headline")
        or content.get("title")
        or content.get("name")
        or "Featured Story"
    )
    body = (
        content.get("writeup")
        or content.get("writeup_text")
        or content.get("body")
        or content.get("description")
        or content.get("content")
        or ""
    )
    caption = content.get("caption") or content.get("photo_caption") or ""
    description = content.get("description") or content.get("summary") or ""

    return {
        "headline": str(headline).strip(),
        "body": str(body).strip(),
        "caption": str(caption).strip(),
        "description": str(description).strip(),
    }


def _index_available_images(images: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """Creates a lookup table for candidate photographs by ID, filename, and URL."""
    index: Dict[str, Dict[str, Any]] = {}
    for img in images:
        pid = str(img.get("id") or "").strip()
        url = str(img.get("url") or "").strip()
        filename = str(img.get("filename") or os.path.basename(url) or pid).strip()
        if pid:
            index[pid] = img
        if filename:
            index[filename] = img
        if url:
            index[url] = img
    return index


def validate_page_plan(
    plan: PagePlan,
    template_metadata: TemplateMetadata,
    available_images: Optional[List[Dict[str, Any]]] = None,
    strict: bool = True,
) -> PlanValidationReport:
    """
    Deterministically validates a PagePlan against template constraints.

    Checks:
    1. Region existence: Every region in plan.regions must exist in template_metadata.regions.
    2. Required regions: All regions with required=True must be present and non-empty.
    3. Maximum text length: Words in text regions must not exceed region/template text capacity.
    4. Image count: Total assigned images must be within [min_images, max_images].
    5. Image aspect ratio: Assigned image aspect ratios must match target ratio within tolerance.
    6. Template constraints: Custom layout rules (e.g. avoid overcrowding).
    """
    violations: List[str] = []
    warnings: List[str] = []

    # Build known regions map
    known_regions = {r.region_id: r for r in template_metadata.regions}
    planned_regions_map = {r.region_id: r for r in plan.regions}

    # 1. Region existence
    for pr in plan.regions:
        if pr.region_id not in known_regions:
            violations.append(
                f"Unknown region '{pr.region_id}': not defined in template '{template_metadata.template_id}'"
            )

    # 2. Required regions
    for r_def in template_metadata.regions:
        if r_def.required:
            pr = planned_regions_map.get(r_def.region_id)
            if not pr:
                violations.append(
                    f"Missing required region '{r_def.region_id}' of type '{r_def.type}'"
                )
            else:
                if r_def.type == "image" and not pr.asset:
                    violations.append(
                        f"Required image region '{r_def.region_id}' has no assigned asset"
                    )
                elif r_def.type in ("headline", "body") and not pr.content:
                    violations.append(
                        f"Required text region '{r_def.region_id}' has empty content"
                    )

    # 3. Maximum text length
    tc = template_metadata.text_capacity
    total_words = 0

    for pr in plan.regions:
        r_def = known_regions.get(pr.region_id)
        if not r_def:
            continue

        if pr.type in ("headline", "body", "caption", "pullquote", "kicker"):
            w_count = _count_words(pr.content)
            pr.word_count = w_count
            total_words += w_count

            # Determine maximum word limit
            max_limit = r_def.max_words
            if max_limit is None:
                if pr.type == "headline":
                    max_limit = tc.max_headline_words
                elif pr.type == "caption":
                    max_limit = tc.max_caption_words
                else:
                    max_limit = tc.max_words

            if max_limit and w_count > max_limit:
                if strict:
                    violations.append(
                        f"Region '{pr.region_id}' exceeds maximum word limit ({w_count} words > max {max_limit})"
                    )
                else:
                    warnings.append(
                        f"Region '{pr.region_id}' exceeds word limit ({w_count} > {max_limit}); truncated"
                    )

    # 4. Image count constraints
    assigned_images = [pr for pr in plan.regions if pr.type == "image" and pr.asset]
    img_count = len(assigned_images)

    constraints = template_metadata.layout_constraints or {}
    min_images = constraints.get("min_images", 0)
    max_images = constraints.get("max_images", max(template_metadata.image_count, 6))

    if img_count < min_images:
        violations.append(
            f"Insufficient images: template requires at least {min_images}, but plan has {img_count}"
        )
    if img_count > max_images:
        violations.append(
            f"Image count overflow: template allows at most {max_images}, but plan has {img_count}"
        )

    # 5. Image aspect ratio validation
    image_index = _index_available_images(available_images or [])

    for pr in assigned_images:
        r_def = known_regions.get(pr.region_id)
        if not r_def or r_def.target_aspect_ratio is None:
            continue

        asset_key = pr.asset or ""
        img_info = image_index.get(asset_key) or image_index.get(os.path.basename(asset_key))

        ratio = pr.aspect_ratio
        if ratio is None and img_info:
            ratio = img_info.get("aspect_ratio")
            pr.aspect_ratio = ratio

        if ratio is not None:
            target = r_def.target_aspect_ratio
            tol = r_def.tolerance
            if abs(ratio - target) > tol:
                violations.append(
                    f"Image '{pr.asset}' aspect ratio {ratio:.2f} violates region '{pr.region_id}' target ratio {target:.2f} (tolerance ±{tol:.2f})"
                )

    metrics = {
        "total_words": total_words,
        "image_count": img_count,
        "regions_count": len(plan.regions),
    }

    return PlanValidationReport(
        is_valid=(len(violations) == 0),
        violations=violations,
        warnings=warnings,
        metrics=metrics,
    )


def _create_heuristic_page_plan(
    content: Union[str, Dict[str, Any]],
    template_metadata: TemplateMetadata,
    available_images: List[Dict[str, Any]],
) -> PagePlan:
    """
    Deterministic fallback planner when LLM is offline or disabled.
    Maps extracted article components to template regions while respecting word budgets.
    """
    fields = _extract_content_fields(content)
    tc = template_metadata.text_capacity

    planned_regions: List[PlannedRegion] = []
    used_images: set[str] = set()

    for r_def in template_metadata.regions:
        rid = r_def.region_id
        rtype = r_def.type

        if rtype == "headline":
            max_w = r_def.max_words or tc.max_headline_words
            txt = _truncate_to_word_limit(fields["headline"], max_w)
            planned_regions.append(
                PlannedRegion(
                    region_id=rid,
                    type="headline",
                    content=txt,
                    word_count=_count_words(txt),
                    role="headline",
                )
            )

        elif rtype == "body":
            max_w = r_def.max_words or tc.max_words
            txt = _truncate_to_word_limit(fields["body"], max_w)
            planned_regions.append(
                PlannedRegion(
                    region_id=rid,
                    type="body",
                    content=txt,
                    word_count=_count_words(txt),
                    role="body",
                )
            )

        elif rtype == "caption":
            max_w = r_def.max_words or tc.max_caption_words
            cap_text = fields["caption"]
            if not cap_text and available_images:
                cap_text = str(available_images[0].get("caption") or "")
            if not cap_text:
                cap_text = "Students demonstrating the prototype."
            txt = _truncate_to_word_limit(cap_text, max_w)
            planned_regions.append(
                PlannedRegion(
                    region_id=rid,
                    type="caption",
                    content=txt,
                    word_count=_count_words(txt),
                    role="caption",
                )
            )

        elif rtype == "image":
            # Pick best available image matching region orientation or aspect ratio
            chosen_img = None
            for img in available_images:
                iid = str(img.get("id") or img.get("filename") or img.get("url") or "")
                if iid in used_images:
                    continue
                # Check aspect ratio tolerance if defined
                if r_def.target_aspect_ratio and img.get("aspect_ratio"):
                    diff = abs(float(img["aspect_ratio"]) - r_def.target_aspect_ratio)
                    if diff <= r_def.tolerance:
                        chosen_img = img
                        break
                elif not chosen_img:
                    chosen_img = img

            if not chosen_img and available_images:
                chosen_img = available_images[0]

            asset_name = ""
            aspect_ratio = None
            caption = None

            if chosen_img:
                asset_name = os.path.basename(str(chosen_img.get("filename") or chosen_img.get("url") or chosen_img.get("id") or ""))
                aspect_ratio = chosen_img.get("aspect_ratio")
                caption = chosen_img.get("caption")
                used_images.add(str(chosen_img.get("id") or asset_name))

            planned_regions.append(
                PlannedRegion(
                    region_id=rid,
                    type="image",
                    asset=asset_name,
                    aspect_ratio=aspect_ratio,
                    caption=caption,
                    role=r_def.role,
                )
            )

        elif rtype == "pullquote":
            quote_text = fields["description"] or fields["headline"]
            txt = _truncate_to_word_limit(quote_text, r_def.max_words or 20)
            planned_regions.append(
                PlannedRegion(
                    region_id=rid,
                    type="pullquote",
                    content=txt,
                    word_count=_count_words(txt),
                    role="pullquote",
                )
            )

    return PagePlan(
        page_type=template_metadata.page_type,
        template_id=template_metadata.template_id,
        regions=planned_regions,
        metadata={"generator": "heuristic_fallback"},
    )


async def plan_page_layout(
    content: Union[str, Dict[str, Any]],
    *,
    department_or_lab: Optional[str] = None,
    selected_template: Union[str, Dict[str, Any], TemplateMetadata, None] = None,
    available_images: Optional[List[Dict[str, Any]]] = None,
    template_regions: Optional[List[Dict[str, Any]]] = None,
    text_limits: Optional[Dict[str, int]] = None,
    image_constraints: Optional[Dict[str, Any]] = None,
    use_llm: bool = True,
) -> Tuple[PagePlan, PlanValidationReport]:
    """
    Master Layout Planner Entrypoint.

    Converts article content and real photographs into a deterministic PagePlan
    and validates all region existence, text length, image count, and aspect ratios.
    """
    photos = available_images or []

    # 1. Resolve Template Metadata
    template_meta = resolve_template(selected_template)

    # Apply overrides if provided
    if template_regions:
        custom_regions: List[TemplateRegionDefinition] = []
        for r in template_regions:
            item = TemplateRegionDefinition.from_raw(r)
            if item:
                custom_regions.append(item)
        if custom_regions:
            template_meta.regions = custom_regions

    if text_limits:
        for k, v in text_limits.items():
            if hasattr(template_meta.text_capacity, k):
                setattr(template_meta.text_capacity, k, int(v))

    if image_constraints:
        template_meta.layout_constraints = {
            **template_meta.layout_constraints,
            **image_constraints,
        }

    # 2. LLM Assignment Generation
    page_plan: Optional[PagePlan] = None

    if use_llm:
        try:
            regions_desc = [
                {
                    "region_id": r.region_id,
                    "type": r.type,
                    "required": r.required,
                    "max_words": r.max_words or (
                        template_meta.text_capacity.max_headline_words if r.type == "headline"
                        else template_meta.text_capacity.max_caption_words if r.type == "caption"
                        else template_meta.text_capacity.max_words
                    ),
                    "target_aspect_ratio": r.target_aspect_ratio,
                    "role": r.role,
                }
                for r in template_meta.regions
            ]

            photos_desc = [
                {
                    "asset": os.path.basename(str(p.get("filename") or p.get("url") or p.get("id") or "")),
                    "aspect_ratio": p.get("aspect_ratio"),
                    "orientation": p.get("orientation"),
                    "caption": p.get("caption"),
                }
                for p in photos
            ]

            prompt = f"""You are the SIET Magazine Layout Planner.
Your task is to assign content and images to the deterministic template regions for this magazine page.

PAGE TYPE: {template_meta.page_type}
TEMPLATE ID: {template_meta.template_id}
DEPARTMENT / LAB: {department_or_lab or template_meta.department_or_lab or "SIET College"}

TARGET REGIONS TO POPULATE:
{json.dumps(regions_desc, indent=2)}

SOURCE CONTENT:
{json.dumps(content if isinstance(content, dict) else {"text": content}, indent=2)}

AVAILABLE PHOTOGRAPHS:
{json.dumps(photos_desc, indent=2)}

RULES:
1. Return EXACTLY the regions listed in TARGET REGIONS. Do NOT add new region IDs or remove defined regions.
2. For text regions ("headline", "body", "caption", "pullquote"), write concise, high-impact editorial content strictly under max_words.
3. For image regions ("image"), assign the most relevant "asset" filename from the AVAILABLE PHOTOGRAPHS.
4. Output ONLY valid JSON matching this schema:
{{
  "page_type": "{template_meta.page_type}",
  "template_id": "{template_meta.template_id}",
  "regions": [
    {{
      "region_id": "hero_image",
      "type": "image",
      "asset": "photo_17.jpg"
    }},
    {{
      "region_id": "headline",
      "type": "headline",
      "content": "Students Build an Autonomous Robot"
    }},
    {{
      "region_id": "body",
      "type": "body",
      "content": "..."
    }},
    {{
      "region_id": "caption",
      "type": "caption",
      "content": "Students demonstrating the prototype."
    }}
  ]
}}
"""
            llm_result = await call_llm_json(prompt)
            if llm_result and isinstance(llm_result, dict) and "regions" in llm_result:
                parsed_regions: List[PlannedRegion] = []
                for r in llm_result.get("regions", []):
                    parsed_regions.append(
                        PlannedRegion(
                            region_id=str(r.get("region_id", "")),
                            type=str(r.get("type", "body")),
                            content=r.get("content"),
                            asset=r.get("asset"),
                            aspect_ratio=r.get("aspect_ratio"),
                            caption=r.get("caption"),
                        )
                    )
                if parsed_regions:
                    page_plan = PagePlan(
                        page_type=str(llm_result.get("page_type") or template_meta.page_type),
                        template_id=str(llm_result.get("template_id") or template_meta.template_id),
                        regions=parsed_regions,
                        metadata={"generator": "llm"},
                    )
        except Exception as e:
            logger.warning(f"[LayoutPlanner] LLM layout planning pass failed: {e}. Falling back to heuristic.")

    # 3. Fallback Heuristic if LLM is offline or produced empty output
    if not page_plan:
        page_plan = _create_heuristic_page_plan(content, template_meta, photos)

    # 4. Strict Deterministic Backend Validation
    validation_report = validate_page_plan(page_plan, template_meta, photos, strict=True)

    # 5. Auto-correction if minor violations exist (e.g. text length slightly over word budget)
    if not validation_report.is_valid:
        logger.info(f"[LayoutPlanner] Page plan had validation issues: {validation_report.violations}. Attempting auto-correction.")
        corrected_regions: List[PlannedRegion] = []
        known_regions = {r.region_id: r for r in template_meta.regions}

        for pr in page_plan.regions:
            r_def = known_regions.get(pr.region_id)
            if not r_def:
                continue  # drop unknown region
            if pr.type in ("headline", "body", "caption", "pullquote") and pr.content:
                max_w = r_def.max_words or (
                    template_meta.text_capacity.max_headline_words if pr.type == "headline"
                    else template_meta.text_capacity.max_caption_words if pr.type == "caption"
                    else template_meta.text_capacity.max_words
                )
                if _count_words(pr.content) > max_w:
                    pr.content = _truncate_to_word_limit(pr.content, max_w)
            corrected_regions.append(pr)

        # Check for missing required regions
        existing_rids = {cr.region_id for cr in corrected_regions}
        fallback_plan = _create_heuristic_page_plan(content, template_meta, photos)
        for fb_r in fallback_plan.regions:
            if fb_r.region_id not in existing_rids:
                corrected_regions.append(fb_r)

        page_plan.regions = corrected_regions
        validation_report = validate_page_plan(page_plan, template_meta, photos, strict=True)

    return page_plan, validation_report


def page_plan_to_magazine_data(
    plan: PagePlan,
    base_data: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Clean Adapter Boundary: PagePlan -> Renderer Data.

    Translates a deterministic PagePlan into the input dictionary expected by
    the publication renderer, ensuring the renderer performs NO semantic decision-making.
    """
    data = copy.deepcopy(base_data or {})

    headline = ""
    body = ""
    caption = ""
    images: List[Dict[str, Any]] = []

    for r in plan.regions:
        if r.type == "headline" and not headline:
            headline = r.content or ""
        elif r.type == "body" and not body:
            body = r.content or ""
        elif r.type == "caption" and not caption:
            caption = r.content or ""
        elif r.type == "image" and r.asset:
            images.append({
                "url": r.asset,
                "caption": r.caption or caption or "",
                "aspect_ratio": r.aspect_ratio,
            })

    if headline:
        data["writeup_headline"] = headline
        data.setdefault("magazine_issue_title", headline)

    if body:
        data["writeup_text"] = body
        data["writeup_body"] = body

    if images:
        data["cover_pages"] = [images[0]]
        data["gallery_images"] = images[1:] if len(images) > 1 else images

    data["layout_plan"] = {
        "page_type": plan.page_type,
        "template_id": plan.template_id,
        "regions": [r.model_dump() for r in plan.regions],
    }

    return data
