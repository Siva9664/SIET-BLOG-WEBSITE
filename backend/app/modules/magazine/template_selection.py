"""Validated template recommendation for magazine pages."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from typing import Any

from app.core.logging import logger
from app.modules.magazine.llm_provider import call_llm_json
from app.modules.magazine.template_schema import (
    TemplateMetadata,
    infer_page_type,
    normalize_page_type,
    normalize_template_metadata,
)


@dataclass(slots=True)
class ContentProfile:
    text: str
    word_count: int
    section: str | None = None
    department: str | None = None
    lab: str | None = None
    page_type: str = "article"
    content_types: list[str] = field(default_factory=list)
    available_image_count: int = 0

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TemplateValidationResult:
    is_valid: bool
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TemplateRecommendation:
    template_id: str
    page_type: str
    reason: str
    confidence: float
    validation: TemplateValidationResult
    metadata: TemplateMetadata

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["validation"] = self.validation.to_dict()
        data["metadata"] = self.metadata.to_dict()
        return data


def _normalize_text(value: str | None) -> str:
    return (value or "").strip().lower()


def _content_text(content: str | dict[str, Any]) -> str:
    if isinstance(content, str):
        return content.strip()
    keys = [
        "title",
        "headline",
        "magazine_issue_title",
        "description",
        "summary",
        "writeup",
        "writeup_text",
        "body",
        "content",
    ]
    values = [str(content.get(key, "")).strip() for key in keys]
    items = content.get("items")
    if isinstance(items, list):
        values.extend(str(item) for item in items[:10])
    return "\n".join(value for value in values if value)


def build_content_profile(
    content: str | dict[str, Any],
    *,
    section: str | None = None,
    department: str | None = None,
    lab: str | None = None,
    page_type: str | None = None,
    available_photographs: list[dict[str, Any]] | None = None,
) -> ContentProfile:
    """Builds a normalized profile for deterministic template selection."""
    text = _content_text(content)
    if page_type:
        inferred_page_type = normalize_page_type(page_type)
    elif section:
        inferred_page_type = normalize_page_type(section)
    else:
        inferred_page_type = normalize_page_type(infer_page_type(text))

    content_types = {inferred_page_type}
    if section:
        content_types.add(normalize_page_type(section))
    if isinstance(content, dict):
        for raw_type in content.get("content_types", []) or []:
            content_types.add(normalize_page_type(str(raw_type)))
        if content.get("page_type"):
            content_types.add(normalize_page_type(str(content["page_type"])))

    return ContentProfile(
        text=text,
        word_count=len(text.split()),
        section=section,
        department=department,
        lab=lab,
        page_type=inferred_page_type,
        content_types=sorted(content_types),
        available_image_count=len(available_photographs or []),
    )


def validate_template_candidate(
    metadata: TemplateMetadata,
    profile: ContentProfile,
) -> TemplateValidationResult:
    """Rejects candidates that violate declared template metadata."""
    issues: list[str] = []
    warnings: list[str] = []

    requested_types = profile.content_types or [profile.page_type]
    if not any(metadata.supports_content_type(content_type) for content_type in requested_types):
        issues.append(
            "Template does not support requested content types: "
            + ", ".join(requested_types)
        )

    if metadata.page_type and profile.page_type:
        if normalize_page_type(metadata.page_type) != normalize_page_type(profile.page_type):
            if not metadata.supports_content_type(profile.page_type):
                issues.append(
                    f"Template page_type '{metadata.page_type}' does not match "
                    f"requested page_type '{profile.page_type}'."
                )
            else:
                warnings.append(
                    f"Template primary page_type is '{metadata.page_type}', "
                    f"but supports '{profile.page_type}'."
                )

    if metadata.department and profile.department:
        if _normalize_text(metadata.department) != _normalize_text(profile.department):
            issues.append(
                f"Template department '{metadata.department}' does not match "
                f"requested department '{profile.department}'."
            )

    if metadata.lab and profile.lab:
        if _normalize_text(metadata.lab) != _normalize_text(profile.lab):
            issues.append(
                f"Template lab '{metadata.lab}' does not match requested lab '{profile.lab}'."
            )

    if metadata.section and profile.section:
        norm_m_sec = _normalize_text(metadata.section)
        norm_p_sec = _normalize_text(profile.section)
        if norm_m_sec != norm_p_sec and not metadata.supports_content_type(profile.section):
            issues.append(
                f"Template section '{metadata.section}' does not match "
                f"requested section '{profile.section}'."
            )

    min_images = int(metadata.layout_constraints.get("min_images", metadata.image_count or 0))
    max_images = metadata.layout_constraints.get("max_images")
    if profile.available_image_count < min_images:
        issues.append(
            f"Template requires {min_images} image(s), but only "
            f"{profile.available_image_count} real photograph(s) are available."
        )
    if max_images is not None and profile.available_image_count > int(max_images):
        warnings.append(
            f"Template uses at most {max_images} image(s); extra photographs may be assigned elsewhere."
        )

    max_words = metadata.text_capacity.max_words
    if profile.word_count > max_words:
        issues.append(
            f"Content has {profile.word_count} words, exceeding template capacity "
            f"of {max_words} words."
        )
    elif profile.word_count > int(max_words * 0.85):
        warnings.append(
            f"Content is close to template capacity ({profile.word_count}/{max_words} words)."
        )

    return TemplateValidationResult(
        is_valid=not issues,
        issues=issues,
        warnings=warnings,
    )


def _score_template(metadata: TemplateMetadata, profile: ContentProfile) -> tuple[float, list[str]]:
    score = 0.15
    reasons: list[str] = []

    if normalize_page_type(metadata.page_type) == normalize_page_type(profile.page_type):
        score += 0.25
        reasons.append(f"page type matches {profile.page_type}")
    elif metadata.supports_content_type(profile.page_type):
        score += 0.14
        reasons.append(f"template supports {profile.page_type}")

    if profile.section and metadata.section:
        if _normalize_text(profile.section) == _normalize_text(metadata.section):
            score += 0.28
            reasons.append(f"section matches {profile.section}")
        elif metadata.supports_content_type(profile.section):
            score += 0.14
            reasons.append(f"section type {profile.section} is supported")
    elif profile.section and metadata.supports_content_type(profile.section):
        score += 0.12
        reasons.append(f"section type {profile.section} is supported")

    if profile.lab:
        if metadata.lab and _normalize_text(metadata.lab) == _normalize_text(profile.lab):
            score += 0.20
            reasons.append(f"lab matches {profile.lab}")
        elif not metadata.lab:
            score += 0.04
            reasons.append("template is lab-neutral")

    if profile.department:
        if metadata.department and _normalize_text(metadata.department) == _normalize_text(profile.department):
            score += 0.15
            reasons.append(f"department matches {profile.department}")
        elif not metadata.department:
            score += 0.04
            reasons.append("template is department-neutral")

    if profile.available_image_count >= (metadata.image_count or 0):
        score += 0.10
        reasons.append("available photographs satisfy image requirement")

    max_words = metadata.text_capacity.max_words
    if profile.word_count <= max_words:
        fit = 1.0 - (profile.word_count / max(max_words, 1))
        score += max(0.04, min(0.12, 0.12 * fit + 0.04))
        reasons.append("content fits text capacity")

    if metadata.layout_constraints and metadata.layout_constraints.get("is_alternate"):
        score -= 0.05
        reasons.append("template is marked as an alternate layout")

    return min(score, 0.99), reasons


def _llm_candidate_order(
    llm_recommendation: Any,
    templates: list[TemplateMetadata],
) -> list[str]:
    if not isinstance(llm_recommendation, dict):
        return []
    raw_candidates = llm_recommendation.get("candidates") or llm_recommendation.get("templates")
    if raw_candidates is None and llm_recommendation.get("template_id"):
        raw_candidates = [llm_recommendation]
    if not isinstance(raw_candidates, list):
        return []

    known_ids = {template.template_id for template in templates}
    ordered: list[str] = []
    for item in raw_candidates:
        candidate_id = item.get("template_id") if isinstance(item, dict) else item
        candidate_id = str(candidate_id or "").strip()
        if candidate_id in known_ids and candidate_id not in ordered:
            ordered.append(candidate_id)
    return ordered


async def recommend_template(
    *,
    content: str | dict[str, Any],
    templates: list[Any],
    section: str | None = None,
    department: str | None = None,
    lab: str | None = None,
    available_photographs: list[dict[str, Any]] | None = None,
    page_type: str | None = None,
    use_llm_candidates: bool = False,
) -> TemplateRecommendation:
    """
    Selects the best valid template.

    LLM ordering is advisory only. Every candidate still passes deterministic
    metadata validation before it can be selected.
    """
    profile = build_content_profile(
        content,
        section=section,
        department=department,
        lab=lab,
        page_type=page_type,
        available_photographs=available_photographs,
    )
    metadata_items = [normalize_template_metadata(template) for template in templates]
    if not metadata_items:
        raise ValueError("Template library is empty.")

    llm_order: list[str] = []
    if use_llm_candidates:
        try:
            prompt = _build_llm_template_prompt(profile, metadata_items)
            llm_order = _llm_candidate_order(
                await call_llm_json(prompt),
                metadata_items,
            )
        except Exception as error:
            logger.warning("LLM template candidate generation skipped: %s", error)

    recommendations: list[TemplateRecommendation] = []
    for metadata in metadata_items:
        validation = validate_template_candidate(metadata, profile)
        base_score, reasons = _score_template(metadata, profile)
        if metadata.template_id in llm_order:
            base_score = min(0.99, base_score + 0.06)
            reasons.append("LLM also shortlisted this template")
        if not validation.is_valid:
            continue
        if validation.warnings:
            reasons.append("; ".join(validation.warnings))

        recommendations.append(
            TemplateRecommendation(
                template_id=metadata.template_id,
                page_type=metadata.page_type,
                reason=", ".join(reasons) or "highest valid metadata score",
                confidence=round(base_score, 2),
                validation=validation,
                metadata=metadata,
            )
        )

    if not recommendations:
        validation_summaries = []
        for metadata in metadata_items:
            result = validate_template_candidate(metadata, profile)
            validation_summaries.append(
                f"{metadata.template_id}: {'; '.join(result.issues) or 'invalid'}"
            )
        raise ValueError(
            "No template satisfies the requested content constraints. "
            + " | ".join(validation_summaries)
        )

    recommendations.sort(
        key=lambda item: (
            item.confidence,
            1 if item.template_id in llm_order else 0,
            0 if (item.metadata and item.metadata.layout_constraints.get("is_alternate")) else 1,
            1 if (item.metadata and ("showcase" in item.template_id or "spotlight" in item.template_id or "digest" in item.template_id)) else 0,
        ),
        reverse=True,
    )
    return recommendations[0]


def _build_llm_template_prompt(
    profile: ContentProfile,
    templates: list[TemplateMetadata],
) -> str:
    compact_templates = [
        {
            "template_id": template.template_id,
            "name": template.name,
            "department": template.department,
            "lab": template.lab,
            "section": template.section,
            "page_type": template.page_type,
            "supported_content_types": template.supported_content_types,
            "image_count": template.image_count,
            "text_capacity": template.text_capacity.to_dict(),
        }
        for template in templates
    ]
    return f"""Recommend the best magazine page template candidates.

Return only JSON:
{{
  "candidates": [
    {{
      "template_id": "id",
      "page_type": "article",
      "reason": "brief factual reason",
      "confidence": 0.0
    }}
  ]
}}

Content profile:
{json.dumps(profile.to_dict(), indent=2)}

Template library:
{json.dumps(compact_templates, indent=2)}
"""


async def select_template(
    *,
    content: str | dict[str, Any],
    department: str | None = None,
    lab: str | None = None,
    department_or_lab: str | None = None,
    section: str | None = None,
    page_type: str | None = None,
    available_images: list[Any] | None = None,
    candidate_templates: list[Any] | None = None,
    db: Any | None = None,
    use_llm: bool = True,
) -> dict[str, Any]:
    """
    High-level template selection service for labs, departments, and editorial sections.

    Input:
    - content: raw text or structured article/event dictionary
    - department/lab: department or lab name (matched dynamically, no hardcoding)
    - section: section name (e.g. Projects, Events, Student achievements)
    - available_images: list of image objects/dicts or count
    - candidate_templates: explicit template objects, dicts, or template IDs (optional)
    - db: optional SQLAlchemy async session to fetch active MagazineTemplates
    - use_llm: whether to query LLM for candidate advice (backend strictly validates)

    Output:
    {
      "template_id": "...",
      "page_type": "...",
      "confidence": 0.95,
      "reason": "..."
    }
    """
    # Dynamic resolution of department / lab
    if department_or_lab:
        candidate = department_or_lab.strip()
        if not lab and "lab" in candidate.lower():
            lab = candidate
        elif not department:
            department = candidate

    templates_to_use: list[Any] = []

    # 1. Check if candidate_templates were passed
    if candidate_templates:
        if isinstance(candidate_templates, list) and len(candidate_templates) > 0 and isinstance(candidate_templates[0], (int, str)):
            raw_ids = {str(x).strip() for x in candidate_templates}
            if db is not None:
                from app.modules.magazine.models import MagazineTemplate
                from sqlalchemy import select
                try:
                    int_ids = [int(x) for x in raw_ids if x.isdigit()]
                    if int_ids:
                        stmt = select(MagazineTemplate).where(
                            MagazineTemplate.id.in_(int_ids),
                            MagazineTemplate.is_active == True,
                        )
                        db_tmpls = list((await db.execute(stmt)).scalars().all())
                        templates_to_use.extend(db_tmpls)
                except Exception as e:
                    logger.warning(f"Failed to query candidate templates by ID from DB: {e}")

            # Also check standard library by template_id
            from app.modules.magazine.template_library import get_standard_templates
            for std_tmpl in get_standard_templates():
                meta_id = std_tmpl.get("template_metadata", {}).get("template_id")
                if meta_id in raw_ids or str(std_tmpl.get("id")) in raw_ids:
                    if not any(normalize_template_metadata(t).template_id == meta_id for t in templates_to_use):
                        templates_to_use.append(std_tmpl)
        else:
            templates_to_use = list(candidate_templates)

    # 2. If candidates were not explicitly provided, combine active DB templates and standard templates
    if not templates_to_use:
        known_ids = set()
        if db is not None:
            from app.modules.magazine.models import MagazineTemplate
            from sqlalchemy import select
            try:
                stmt = select(MagazineTemplate).where(MagazineTemplate.is_active == True)
                db_tmpls = list((await db.execute(stmt)).scalars().all())
                for t in db_tmpls:
                    templates_to_use.append(t)
                    try:
                        known_ids.add(normalize_template_metadata(t).template_id)
                    except Exception:
                        pass
            except Exception as e:
                logger.warning(f"Could not load templates from DB: {e}")

        # Make standard lab/department templates available alongside DB templates
        from app.modules.magazine.template_library import get_standard_templates
        for std_tmpl in get_standard_templates():
            std_id = std_tmpl.get("template_metadata", {}).get("template_id")
            if std_id not in known_ids:
                templates_to_use.append(std_tmpl)

    # Normalise available images to list
    photos_list: list[dict[str, Any]] = []
    if isinstance(available_images, list):
        for img in available_images:
            if isinstance(img, dict):
                photos_list.append(img)
            else:
                photos_list.append({"id": str(img)})
    elif isinstance(available_images, int):
        photos_list = [{"id": f"img_{i}"} for i in range(available_images)]

    recommendation = await recommend_template(
        content=content,
        templates=templates_to_use,
        section=section,
        department=department,
        lab=lab,
        page_type=page_type,
        available_photographs=photos_list,
        use_llm_candidates=use_llm,
    )

    return {
        "template_id": recommendation.template_id,
        "page_type": recommendation.page_type,
        "confidence": recommendation.confidence,
        "reason": recommendation.reason,
        "metadata": recommendation.metadata.to_dict(),
        "validation": recommendation.validation.to_dict(),
    }


