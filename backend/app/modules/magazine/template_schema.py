"""Typed template metadata used by recommendation, planning, and rendering."""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any


DEFAULT_PAGE_TYPES = {
    "cover",
    "introduction",
    "article",
    "achievement",
    "project_showcase",
    "event",
    "photo_gallery",
    "research",
    "faculty_achievement",
    "student_achievement",
    "quote",
    "statistics",
    "closing_page",
}


def slugify_identifier(value: str) -> str:
    clean = re.sub(r"[^a-zA-Z0-9]+", "_", value.strip().lower()).strip("_")
    return clean or "template"


def normalize_page_type(value: str | None) -> str:
    clean = slugify_identifier(value or "article")
    aliases = {
        "project": "project_showcase",
        "projects": "project_showcase",
        "project_showcase": "project_showcase",
        "gallery": "photo_gallery",
        "galleries": "photo_gallery",
        "photo_gallery": "photo_gallery",
        "photo": "photo_gallery",
        "photos": "photo_gallery",
        "photograph": "photo_gallery",
        "student": "student_achievement",
        "students": "student_achievement",
        "student_achievement": "student_achievement",
        "student_achievements": "student_achievement",
        "faculty": "faculty_achievement",
        "faculty_achievement": "faculty_achievement",
        "faculty_achievements": "faculty_achievement",
        "achievement": "achievement",
        "achievements": "achievement",
        "department_activity": "article",
        "department_activities": "article",
        "event": "event",
        "events": "event",
        "symposium": "event",
        "workshop": "event",
        "conference": "event",
        "research": "research",
        "research_lab": "research",
        "article": "article",
        "articles": "article",
        "closing": "closing_page",
        "close": "closing_page",
        "closing_page": "closing_page",
    }
    return aliases.get(clean, clean)


def infer_page_type(text: str, default: str = "article") -> str:
    clean = text.lower()
    if any(term in clean for term in ["cover", "issue title"]):
        return "cover"
    if any(term in clean for term in ["gallery", "photograph", "photo"]):
        return "photo_gallery"
    if any(term in clean for term in ["project", "prototype", "showcase"]):
        return "project_showcase"
    if any(term in clean for term in ["achievement", "award", "winner", "honour", "honor"]):
        return "achievement"
    if any(term in clean for term in ["research", "paper", "publication"]):
        return "research"
    if any(term in clean for term in ["quote", "message from"]):
        return "quote"
    if any(term in clean for term in ["statistic", "metrics", "numbers"]):
        return "statistics"
    if any(term in clean for term in ["event", "seminar", "workshop", "symposium"]):
        return "event"
    if any(term in clean for term in ["closing", "credits", "acknowledgement"]):
        return "closing_page"
    if any(term in clean for term in ["intro", "overview", "preface"]):
        return "introduction"
    return default


def _as_list(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    if isinstance(value, (tuple, set)):
        return list(value)
    return [value]


def _as_str_list(value: Any) -> list[str]:
    return [str(item).strip() for item in _as_list(value) if str(item).strip()]


def _as_int(value: Any, default: int) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


@dataclass(slots=True)
class TextCapacity:
    max_words: int = 450
    max_headline_words: int = 14
    max_caption_words: int = 16

    @classmethod
    def from_raw(cls, raw: Any) -> "TextCapacity":
        if isinstance(raw, int):
            return cls(max_words=raw)
        if not isinstance(raw, dict):
            return cls()
        return cls(
            max_words=_as_int(raw.get("max_words") or raw.get("words"), 450),
            max_headline_words=_as_int(raw.get("max_headline_words"), 14),
            max_caption_words=_as_int(raw.get("max_caption_words"), 16),
        )

    def to_dict(self) -> dict[str, int]:
        return asdict(self)


@dataclass(slots=True)
class AspectRatioRequirement:
    region_id: str
    ratio: float
    tolerance: float = 0.2

    @classmethod
    def from_raw(cls, region_id: str, raw: Any) -> "AspectRatioRequirement | None":
        ratio_value = raw.get("ratio") if isinstance(raw, dict) else raw
        if isinstance(ratio_value, str) and ":" in ratio_value:
            left, right = ratio_value.split(":", 1)
            try:
                ratio = float(left) / float(right)
            except (TypeError, ValueError, ZeroDivisionError):
                return None
        else:
            try:
                ratio = float(ratio_value)
            except (TypeError, ValueError):
                return None
        tolerance = raw.get("tolerance", 0.2) if isinstance(raw, dict) else 0.2
        return cls(region_id=region_id, ratio=ratio, tolerance=float(tolerance))

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class TemplateRegionDefinition:
    region_id: str
    type: str  # "image" | "headline" | "body" | "caption" | "pullquote" | "author" | "kicker" | "stats"
    required: bool = True
    max_words: int | None = None
    target_aspect_ratio: float | None = None
    tolerance: float = 0.25
    role: str = "content"

    @classmethod
    def from_raw(cls, raw: Any) -> "TemplateRegionDefinition | None":
        if not isinstance(raw, dict):
            return None
        rid = str(raw.get("region_id") or raw.get("id") or raw.get("name") or "").strip()
        if not rid:
            return None
        rtype = str(raw.get("type") or raw.get("region_type") or "body").strip().lower()
        req = bool(raw.get("required", True))
        max_w = raw.get("max_words")
        max_words = int(max_w) if max_w is not None else None
        tar = raw.get("target_aspect_ratio") or raw.get("aspect_ratio")
        target_aspect_ratio = float(tar) if tar is not None else None
        tol = float(raw.get("tolerance", 0.25))
        role = str(raw.get("role") or rtype).strip().lower()
        return cls(
            region_id=rid,
            type=rtype,
            required=req,
            max_words=max_words,
            target_aspect_ratio=target_aspect_ratio,
            tolerance=tol,
            role=role,
        )

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def default_regions_for_page_type(page_type: str) -> list[TemplateRegionDefinition]:
    """Provides canonical layout regions matching standard editorial page types."""
    pt = normalize_page_type(page_type)
    if pt == "project_showcase":
        return [
            TemplateRegionDefinition(region_id="hero_image", type="image", required=True, target_aspect_ratio=1.5, tolerance=0.35, role="hero"),
            TemplateRegionDefinition(region_id="headline", type="headline", required=True, max_words=14, role="headline"),
            TemplateRegionDefinition(region_id="body", type="body", required=True, max_words=300, role="body"),
            TemplateRegionDefinition(region_id="caption", type="caption", required=False, max_words=20, role="caption"),
        ]
    elif pt in ("student_achievement", "faculty_achievement", "achievement"):
        return [
            TemplateRegionDefinition(region_id="portrait_photo", type="image", required=True, target_aspect_ratio=0.8, tolerance=0.30, role="portrait"),
            TemplateRegionDefinition(region_id="headline", type="headline", required=True, max_words=12, role="headline"),
            TemplateRegionDefinition(region_id="body", type="body", required=True, max_words=220, role="body"),
            TemplateRegionDefinition(region_id="caption", type="caption", required=False, max_words=16, role="caption"),
        ]
    elif pt == "photo_gallery":
        return [
            TemplateRegionDefinition(region_id="headline", type="headline", required=True, max_words=12, role="headline"),
            TemplateRegionDefinition(region_id="gallery_image_1", type="image", required=True, target_aspect_ratio=1.5, tolerance=0.35, role="gallery"),
            TemplateRegionDefinition(region_id="gallery_image_2", type="image", required=True, target_aspect_ratio=1.5, tolerance=0.35, role="gallery"),
            TemplateRegionDefinition(region_id="caption_1", type="caption", required=False, max_words=16, role="caption"),
            TemplateRegionDefinition(region_id="caption_2", type="caption", required=False, max_words=16, role="caption"),
        ]
    else:  # standard article or event
        return [
            TemplateRegionDefinition(region_id="hero_image", type="image", required=False, target_aspect_ratio=1.6, tolerance=0.35, role="hero"),
            TemplateRegionDefinition(region_id="headline", type="headline", required=True, max_words=14, role="headline"),
            TemplateRegionDefinition(region_id="body", type="body", required=True, max_words=450, role="body"),
            TemplateRegionDefinition(region_id="caption", type="caption", required=False, max_words=16, role="caption"),
        ]


@dataclass(slots=True)
class TemplateMetadata:
    template_id: str
    name: str
    department: str | None = None
    lab: str | None = None
    section: str | None = None
    page_type: str = "article"
    style: str | None = None
    supported_content_types: list[str] = field(default_factory=list)
    image_count: int = 0
    text_capacity: TextCapacity = field(default_factory=TextCapacity)
    aspect_ratios: list[AspectRatioRequirement] = field(default_factory=list)
    regions: list[TemplateRegionDefinition] = field(default_factory=list)
    typography: dict[str, Any] = field(default_factory=dict)
    colors: dict[str, Any] = field(default_factory=dict)
    layout_constraints: dict[str, Any] = field(default_factory=dict)
    version: int = 1
    raw: dict[str, Any] = field(default_factory=dict)

    @property
    def department_or_lab(self) -> str | None:
        """Returns the specific lab if configured, otherwise department."""
        return self.lab or self.department

    def supports_content_type(self, content_type: str) -> bool:
        if not self.supported_content_types:
            return True
        normalized = {normalize_page_type(item) for item in self.supported_content_types}
        target = normalize_page_type(content_type)
        if target in normalized:
            return True
        if target in ("student_achievement", "faculty_achievement") and "achievement" in normalized:
            return True
        if target == "achievement" and any("achievement" in x for x in normalized):
            return True
        if "article" in normalized and target in ("article", "department_activities", "overview"):
            return True
        return False

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["department_or_lab"] = self.department_or_lab
        data["text_capacity"] = self.text_capacity.to_dict()
        data["aspect_ratios"] = [item.to_dict() for item in self.aspect_ratios]
        data["regions"] = [item.to_dict() for item in self.regions]
        return data


def _metadata_sources(template: Any) -> tuple[dict[str, Any], dict[str, Any], list[dict[str, Any]]]:
    if isinstance(template, dict):
        top_level = dict(template)
        style_rules = dict(template.get("style_rules") or template.get("style") or {})
        section_schema = list(template.get("section_schema") or template.get("sections") or [])
    else:
        top_level = {
            "id": getattr(template, "id", None),
            "name": getattr(template, "name", ""),
        }
        style_rules = dict(getattr(template, "style_rules", None) or {})
        section_schema = list(getattr(template, "section_schema", None) or [])

    metadata = (
        top_level.get("metadata")
        or top_level.get("template_metadata")
        or style_rules.get("metadata")
        or style_rules.get("template_metadata")
        or {}
    )
    if not isinstance(metadata, dict):
        metadata = {}
    return top_level | metadata, style_rules, section_schema


def normalize_template_metadata(template: Any) -> TemplateMetadata:
    """Builds a complete metadata object from legacy or modern template records."""
    data, style_rules, section_schema = _metadata_sources(template)
    name = str(data.get("name") or "Magazine Template").strip()
    template_id = str(
        data.get("template_id")
        or data.get("template_key")
        or data.get("id")
        or slugify_identifier(name)
    )

    enabled_sections = [
        section
        for section in section_schema
        if isinstance(section, dict) and section.get("enabled", True)
    ]
    section_types = _as_str_list(
        data.get("supported_content_types")
        or data.get("content_types")
        or [section.get("section_type") or section.get("key") for section in enabled_sections]
    )
    section_types = [normalize_page_type(item) for item in section_types]

    labels_text = " ".join(
        str(section.get("label") or section.get("section_type") or section.get("key") or "")
        for section in enabled_sections
    )
    page_type = normalize_page_type(
        data.get("page_type") or infer_page_type(f"{name} {labels_text}")
    )
    if page_type not in section_types:
        section_types.append(page_type)

    aspect_ratio_items: list[AspectRatioRequirement] = []
    raw_ratios = data.get("aspect_ratios") or data.get("aspect_ratio_requirements") or {}
    if isinstance(raw_ratios, dict):
        for region_id, raw_value in raw_ratios.items():
            parsed = AspectRatioRequirement.from_raw(str(region_id), raw_value)
            if parsed:
                aspect_ratio_items.append(parsed)
    elif isinstance(raw_ratios, list):
        for item in raw_ratios:
            if isinstance(item, dict):
                parsed = AspectRatioRequirement.from_raw(
                    str(item.get("region_id") or item.get("region") or "*"),
                    item,
                )
                if parsed:
                    aspect_ratio_items.append(parsed)

    typography = dict(data.get("typography") or style_rules.get("typography") or {})
    colors = dict(data.get("colors") or style_rules.get("colors") or {})
    if "accent_color" in style_rules and "accent_color" not in colors:
        colors["accent_color"] = style_rules["accent_color"]
    if "background_color" in style_rules and "background_color" not in colors:
        colors["background_color"] = style_rules["background_color"]
    if "text_color" in style_rules and "text_color" not in colors:
        colors["text_color"] = style_rules["text_color"]

    constraints = dict(
        data.get("layout_constraints")
        or data.get("constraints")
        or style_rules.get("layout_constraints")
        or {}
    )

    version_val = 1
    if "version" in data:
        version_val = _as_int(data.get("version"), 1)
    elif hasattr(template, "__dict__") and "versions" in template.__dict__ and template.__dict__["versions"]:
        for v in template.__dict__["versions"]:
            if getattr(v, "is_active", True):
                version_val = getattr(v, "version_number", 1)
                break

    dept_val = str(data.get("department")).strip() if data.get("department") else None
    lab_val = str(data.get("lab")).strip() if data.get("lab") else None
    if not dept_val and not lab_val and data.get("department_or_lab"):
        candidate = str(data.get("department_or_lab")).strip()
        if "lab" in candidate.lower():
            lab_val = candidate
        else:
            dept_val = candidate

    raw_regions = data.get("regions") or data.get("template_regions") or constraints.get("regions") or []
    parsed_regions: list[TemplateRegionDefinition] = []
    if isinstance(raw_regions, list):
        for r in raw_regions:
            item = TemplateRegionDefinition.from_raw(r)
            if item:
                parsed_regions.append(item)
    elif isinstance(raw_regions, dict):
        for rid, rdict in raw_regions.items():
            if isinstance(rdict, dict):
                r_copy = dict(rdict)
                r_copy.setdefault("region_id", rid)
                item = TemplateRegionDefinition.from_raw(r_copy)
                if item:
                    parsed_regions.append(item)

    if not parsed_regions:
        parsed_regions = default_regions_for_page_type(page_type)

    return TemplateMetadata(
        template_id=template_id,
        name=name,
        department=dept_val,
        lab=lab_val,
        section=str(data.get("section")).strip() if data.get("section") else None,
        page_type=page_type,
        style=str(data.get("style")).strip() if data.get("style") else style_rules.get("spacing"),
        supported_content_types=section_types,
        image_count=_as_int(data.get("image_count"), 0),
        text_capacity=TextCapacity.from_raw(data.get("text_capacity")),
        aspect_ratios=aspect_ratio_items,
        regions=parsed_regions,
        typography=typography,
        colors=colors,
        layout_constraints=constraints,
        version=version_val,
        raw=data,
    )


def build_default_template_metadata(
    *,
    name: str,
    section_schema: list[dict[str, Any]],
    style_rules: dict[str, Any],
) -> dict[str, Any]:
    """Creates metadata for newly parsed legacy templates."""
    labels_text = " ".join(str(section.get("label", "")) for section in section_schema)
    supported = [
        normalize_page_type(str(section.get("section_type") or section.get("key")))
        for section in section_schema
        if section.get("enabled", True)
    ]
    page_type = infer_page_type(f"{name} {labels_text}")
    if page_type not in supported:
        supported.append(page_type)

    default_regions = [r.to_dict() for r in default_regions_for_page_type(page_type)]

    return {
        "template_id": slugify_identifier(name),
        "name": name,
        "department": None,
        "lab": None,
        "section": None,
        "page_type": page_type,
        "style": style_rules.get("spacing", "editorial"),
        "supported_content_types": supported,
        "image_count": 0,
        "version": 1,
        "regions": default_regions,
        "text_capacity": {
            "max_words": 450,
            "max_headline_words": 14,
            "max_caption_words": 16,
        },
        "aspect_ratios": [],
        "typography": {
            "display": style_rules.get("font_display"),
            "body": style_rules.get("font_body"),
            "utility": style_rules.get("font_util"),
        },
        "colors": {
            "accent_color": style_rules.get("accent_color"),
            "background_color": style_rules.get("background_color"),
            "text_color": style_rules.get("text_color"),
        },
        "layout_constraints": {
            "avoid_overcrowding": True,
            "prevent_text_overflow": True,
            "real_photos_priority": True,
        },
    }
