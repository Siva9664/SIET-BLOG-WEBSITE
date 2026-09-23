"""Built-in library of intelligent templates for labs, departments, and editorial sections."""

from __future__ import annotations
from typing import Any


STANDARD_TEMPLATES: list[dict[str, Any]] = [
    {
        "name": "AI Lab Project Showcase",
        "template_family": "lab_showcase",
        "page_budget": 1,
        "description": "Two-photo project layout with technical specifications for AI Lab prototypes.",
        "section_schema": [
            {"section_type": "project_showcase", "label": "Project Architecture & Results", "enabled": True}
        ],
        "style_rules": {
            "spacing": "tight",
            "font_display": "Playfair Display",
            "font_body": "Source Serif Pro",
            "font_util": "Inter",
            "accent_color": "#1d4ed8",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "ai_lab_project_showcase",
            "aliases": ["AI_LAB_03", "ai_lab_03"],
            "name": "AI Lab Project Showcase",
            "department": None,  # dynamic matching across any engineering department
            "lab": "AI Lab",
            "section": "Projects",
            "page_type": "project_showcase",
            "supported_content_types": ["project_showcase", "projects", "research", "article"],
            "style": "modern_tech",
            "image_count": 2,
            "text_capacity": {
                "max_words": 300,
                "max_headline_words": 14,
                "max_caption_words": 18,
            },
            "regions": [
                {"region_id": "hero_image", "type": "image", "required": True, "target_aspect_ratio": 1.5, "tolerance": 0.35, "role": "hero"},
                {"region_id": "headline", "type": "headline", "required": True, "max_words": 14, "role": "headline"},
                {"region_id": "body", "type": "body", "required": True, "max_words": 300, "role": "body"},
                {"region_id": "caption", "type": "caption", "required": False, "max_words": 20, "role": "caption"},
            ],
            "layout_constraints": {
                "min_images": 1,
                "max_images": 4,
                "columns": 2,
                "avoid_overcrowding": True,
                "prevent_text_overflow": True,
            },
            "version": 1,
        },
    },
    {
        "name": "IoT Lab Smart Systems",
        "template_family": "lab_showcase",
        "page_budget": 1,
        "description": "Sensor-grid layout highlighting hardware telemetry and embedded architectures.",
        "section_schema": [
            {"section_type": "project_showcase", "label": "IoT Sensor Prototype", "enabled": True}
        ],
        "style_rules": {
            "spacing": "normal",
            "font_display": "Inter",
            "font_body": "Source Serif Pro",
            "font_util": "Inter",
            "accent_color": "#059669",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "iot_lab_smart_systems",
            "name": "IoT Lab Smart Systems",
            "department": None,
            "lab": "IoT Lab",
            "section": "Projects",
            "page_type": "project_showcase",
            "supported_content_types": ["project_showcase", "projects", "iot", "article"],
            "style": "connected_sensor_grid",
            "image_count": 2,
            "text_capacity": {
                "max_words": 320,
                "max_headline_words": 12,
                "max_caption_words": 16,
            },
            "layout_constraints": {
                "min_images": 1,
                "max_images": 3,
                "columns": 2,
                "avoid_overcrowding": True,
            },
            "version": 1,
        },
    },
    {
        "name": "Robotics Lab Autonomous Systems",
        "template_family": "lab_showcase",
        "page_budget": 1,
        "description": "Multi-angle physical robot prototype spread requiring 3 photographs.",
        "section_schema": [
            {"section_type": "project_showcase", "label": "Autonomous Field Demonstration", "enabled": True}
        ],
        "style_rules": {
            "spacing": "tight",
            "font_display": "Playfair Display",
            "font_body": "Source Serif Pro",
            "font_util": "Inter",
            "accent_color": "#ea580c",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "robotics_lab_autonomous_systems",
            "name": "Robotics Lab Autonomous Systems",
            "department": None,
            "lab": "Robotics Lab",
            "section": "Projects",
            "page_type": "project_showcase",
            "supported_content_types": ["project_showcase", "projects", "robotics", "hardware"],
            "style": "industrial_precision",
            "image_count": 3,
            "text_capacity": {
                "max_words": 260,
                "max_headline_words": 12,
                "max_caption_words": 20,
            },
            "layout_constraints": {
                "min_images": 3,
                "max_images": 5,
                "columns": 3,
                "real_photos_priority": True,
            },
            "version": 1,
        },
    },
    {
        "name": "Cyber Security Lab CTF Digest",
        "template_family": "lab_showcase",
        "page_budget": 1,
        "description": "High-contrast technical analysis for hackathons, CTF defenses, and audits.",
        "section_schema": [
            {"section_type": "event", "label": "Security Challenge & Defense", "enabled": True}
        ],
        "style_rules": {
            "spacing": "normal",
            "font_display": "Inter",
            "font_body": "Inter",
            "font_util": "Inter",
            "accent_color": "#0284c7",
            "background_color": "#0f172a",
            "text_color": "#f8fafc",
        },
        "template_metadata": {
            "template_id": "cyber_security_lab_ctf_digest",
            "name": "Cyber Security Lab CTF Digest",
            "department": None,
            "lab": "Cyber Security Lab",
            "section": "Events",
            "page_type": "event",
            "supported_content_types": ["event", "events", "cybersecurity", "workshop"],
            "style": "cyber_terminal_dark",
            "image_count": 1,
            "text_capacity": {
                "max_words": 380,
                "max_headline_words": 14,
                "max_caption_words": 16,
            },
            "layout_constraints": {
                "min_images": 1,
                "max_images": 2,
                "columns": 2,
            },
            "version": 1,
        },
    },
    {
        "name": "Research Lab Publications",
        "template_family": "academic_digest",
        "page_budget": 1,
        "description": "High text-density double-column layout for academic papers and peer citations.",
        "section_schema": [
            {"section_type": "research", "label": "Peer-Reviewed Research Findings", "enabled": True}
        ],
        "style_rules": {
            "spacing": "normal",
            "font_display": "Playfair Display",
            "font_body": "Source Serif Pro",
            "font_util": "Inter",
            "accent_color": "#4338ca",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "research_lab_peer_review",
            "name": "Research Lab Publications",
            "department": None,
            "lab": "Research Lab",
            "section": "Research Lab",
            "page_type": "research",
            "supported_content_types": ["research", "paper", "publication", "article"],
            "style": "academic_formal",
            "image_count": 1,
            "text_capacity": {
                "max_words": 450,
                "max_headline_words": 16,
                "max_caption_words": 20,
            },
            "layout_constraints": {
                "min_images": 0,
                "max_images": 2,
                "columns": 2,
            },
            "version": 1,
        },
    },
    {
        "name": "Department Activities Quarterly Digest",
        "template_family": "academic_digest",
        "page_budget": 1,
        "description": "Comprehensive long-form narrative covering department milestones and symposiums.",
        "section_schema": [
            {"section_type": "article", "label": "Department Milestones & Activities", "enabled": True}
        ],
        "style_rules": {
            "spacing": "normal",
            "font_display": "Playfair Display",
            "font_body": "Source Serif Pro",
            "font_util": "Inter",
            "accent_color": "#0d9488",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "department_activities_digest",
            "name": "Department Activities Quarterly Digest",
            "department": None,  # matches any dynamic department
            "lab": None,
            "section": "Department activities",
            "page_type": "article",
            "supported_content_types": ["department_activities", "article", "newsletter", "overview"],
            "style": "editorial_magazine",
            "image_count": 2,
            "text_capacity": {
                "max_words": 500,
                "max_headline_words": 14,
                "max_caption_words": 18,
            },
            "layout_constraints": {
                "min_images": 1,
                "max_images": 4,
                "columns": 2,
            },
            "version": 1,
        },
    },
    {
        "name": "Student Achievement Spotlight",
        "template_family": "spotlight",
        "page_budget": 1,
        "description": "Hero-framed portrait template celebrating hackathon winners and student competitions.",
        "section_schema": [
            {"section_type": "student_achievement", "label": "Student Honor & Accolades", "enabled": True}
        ],
        "style_rules": {
            "spacing": "loose",
            "font_display": "Playfair Display",
            "font_body": "Inter",
            "font_util": "Inter",
            "accent_color": "#d97706",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "student_achievement_spotlight",
            "name": "Student Achievement Spotlight",
            "department": None,
            "lab": None,
            "section": "Student achievements",
            "page_type": "student_achievement",
            "supported_content_types": ["student_achievement", "achievement", "award", "student"],
            "style": "spotlight_celebratory",
            "image_count": 1,
            "text_capacity": {
                "max_words": 220,
                "max_headline_words": 12,
                "max_caption_words": 16,
            },
            "layout_constraints": {
                "min_images": 1,
                "max_images": 2,
                "columns": 1,
                "avoid_overcrowding": True,
            },
            "version": 1,
        },
    },
    {
        "name": "Faculty Achievement Spotlight",
        "template_family": "spotlight",
        "page_budget": 1,
        "description": "Distinguished academic spotlight for patents, grants, and faculty leadership.",
        "section_schema": [
            {"section_type": "faculty_achievement", "label": "Faculty Honors & Grants", "enabled": True}
        ],
        "style_rules": {
            "spacing": "loose",
            "font_display": "Playfair Display",
            "font_body": "Source Serif Pro",
            "font_util": "Inter",
            "accent_color": "#7c3aed",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "faculty_achievement_spotlight",
            "name": "Faculty Achievement Spotlight",
            "department": None,
            "lab": None,
            "section": "Faculty achievements",
            "page_type": "faculty_achievement",
            "supported_content_types": ["faculty_achievement", "achievement", "award", "faculty"],
            "style": "distinguished_academic",
            "image_count": 1,
            "text_capacity": {
                "max_words": 250,
                "max_headline_words": 14,
                "max_caption_words": 18,
            },
            "layout_constraints": {
                "min_images": 1,
                "max_images": 2,
                "columns": 1,
            },
            "version": 1,
        },
    },
    {
        "name": "Campus & Department Events Feature",
        "template_family": "editorial_feature",
        "page_budget": 1,
        "description": "Two-photo dynamic layout for college symposiums, conferences, and technical workshops.",
        "section_schema": [
            {"section_type": "event", "label": "Symposium & Conference Highlights", "enabled": True}
        ],
        "style_rules": {
            "spacing": "normal",
            "font_display": "Playfair Display",
            "font_body": "Inter",
            "font_util": "Inter",
            "accent_color": "#dc2626",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "campus_event_feature",
            "name": "Campus & Department Events Feature",
            "department": None,
            "lab": None,
            "section": "Events",
            "page_type": "event",
            "supported_content_types": ["event", "events", "symposium", "conference", "workshop"],
            "style": "feature_story",
            "image_count": 2,
            "text_capacity": {
                "max_words": 360,
                "max_headline_words": 14,
                "max_caption_words": 18,
            },
            "layout_constraints": {
                "min_images": 1,
                "max_images": 4,
                "columns": 2,
            },
            "version": 1,
        },
    },
    {
        "name": "Engineering Projects Visual Showcase",
        "template_family": "gallery_grid",
        "page_budget": 1,
        "description": "Multi-image visual grid for team prototypes with concise captions.",
        "section_schema": [
            {"section_type": "project_showcase", "label": "Engineering Capstone Projects", "enabled": True}
        ],
        "style_rules": {
            "spacing": "tight",
            "font_display": "Inter",
            "font_body": "Inter",
            "font_util": "Inter",
            "accent_color": "#0891b2",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "engineering_projects_gallery",
            "name": "Engineering Projects Visual Showcase",
            "department": None,
            "lab": None,
            "section": "Projects",
            "page_type": "project_showcase",
            "supported_content_types": ["projects", "project_showcase", "prototype", "photo_gallery"],
            "style": "grid_modern",
            "image_count": 4,
            "text_capacity": {
                "max_words": 200,
                "max_headline_words": 12,
                "max_caption_words": 16,
            },
            "layout_constraints": {
                "min_images": 3,
                "max_images": 6,
                "columns": 2,
                "min_items": 2,
                "max_items": 4,
                "target_items": 4,
                "real_photos_priority": True,
            },
            "version": 1,
        },
    },
    {
        "name": "Lab Introduction & Research Vision",
        "template_family": "editorial_feature",
        "page_budget": 1,
        "description": "Executive overview spreading department or laboratory leadership vision, infrastructure, and core focus areas.",
        "section_schema": [
            {"section_type": "introduction", "label": "Laboratory Vision & Leadership", "enabled": True}
        ],
        "style_rules": {
            "spacing": "normal",
            "font_display": "Playfair Display",
            "font_body": "Source Serif Pro",
            "font_util": "Inter",
            "accent_color": "#1d4ed8",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "lab_introduction_overview",
            "name": "Lab Introduction & Research Vision",
            "department": None,
            "lab": None,
            "section": "Lab introduction",
            "page_type": "introduction",
            "supported_content_types": ["introduction", "lab_introduction", "overview", "preface", "article"],
            "style": "executive_overview",
            "image_count": 1,
            "text_capacity": {
                "max_words": 380,
                "max_headline_words": 14,
                "max_caption_words": 18,
            },
            "layout_constraints": {
                "min_images": 0,
                "max_images": 2,
                "min_items": 1,
                "max_items": 1,
                "target_items": 1,
                "columns": 2,
            },
            "version": 1,
        },
    },
    {
        "name": "Photo Gallery Mosaic Grid",
        "template_family": "gallery_grid",
        "page_budget": 1,
        "description": "High visual-density spread presenting 6 to 8 real college photographs with technical captions.",
        "section_schema": [
            {"section_type": "photo_gallery", "label": "Laboratory Visual Archive", "enabled": True}
        ],
        "style_rules": {
            "spacing": "tight",
            "font_display": "Inter",
            "font_body": "Inter",
            "font_util": "Inter",
            "accent_color": "#2563eb",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "photo_gallery_grid",
            "name": "Photo Gallery Mosaic Grid",
            "department": None,
            "lab": None,
            "section": "Photo gallery",
            "page_type": "photo_gallery",
            "supported_content_types": ["photo_gallery", "gallery", "photos", "photographs"],
            "style": "mosaic_gallery",
            "image_count": 6,
            "text_capacity": {
                "max_words": 120,
                "max_headline_words": 12,
                "max_caption_words": 16,
            },
            "layout_constraints": {
                "min_images": 3,
                "max_images": 8,
                "min_items": 3,
                "max_items": 8,
                "target_items": 6,
                "columns": 3,
                "real_photos_priority": True,
            },
            "version": 1,
        },
    },
    {
        "name": "Student Achievements Honor Roll",
        "template_family": "spotlight",
        "page_budget": 1,
        "description": "Multi-student achievement spread accommodating 3 to 4 award winners and team recognitions.",
        "section_schema": [
            {"section_type": "student_achievement", "label": "Student Accolades & Trophies", "enabled": True}
        ],
        "style_rules": {
            "spacing": "normal",
            "font_display": "Playfair Display",
            "font_body": "Inter",
            "font_util": "Inter",
            "accent_color": "#d97706",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "student_achievement_grid",
            "name": "Student Achievements Honor Roll",
            "department": None,
            "lab": None,
            "section": "Student achievements",
            "page_type": "student_achievement",
            "supported_content_types": ["student_achievement", "achievement", "awards", "students"],
            "style": "honor_roll_grid",
            "image_count": 3,
            "text_capacity": {
                "max_words": 320,
                "max_headline_words": 12,
                "max_caption_words": 16,
            },
            "layout_constraints": {
                "min_images": 1,
                "max_images": 4,
                "min_items": 2,
                "max_items": 4,
                "target_items": 3,
                "columns": 2,
            },
            "version": 1,
        },
    },
    {
        "name": "AI Lab Prototype Split Showcase",
        "template_family": "lab_showcase",
        "page_budget": 1,
        "description": "Split-column alternate layout for AI Lab projects, supporting visual variety when multiple project pages are rendered.",
        "section_schema": [
            {"section_type": "project_showcase", "label": "AI Architecture & Prototype Breakdown", "enabled": True}
        ],
        "style_rules": {
            "spacing": "tight",
            "font_display": "Playfair Display",
            "font_body": "Source Serif Pro",
            "font_util": "Inter",
            "accent_color": "#1e40af",
            "background_color": "#ffffff",
            "text_color": "#111827",
        },
        "template_metadata": {
            "template_id": "ai_lab_project_split",
            "name": "AI Lab Prototype Split Showcase",
            "department": None,
            "lab": "AI Lab",
            "section": "Projects",
            "page_type": "project_showcase",
            "supported_content_types": ["project_showcase", "projects", "research"],
            "style": "split_column_tech",
            "image_count": 2,
            "text_capacity": {
                "max_words": 340,
                "max_headline_words": 14,
                "max_caption_words": 18,
            },
            "layout_constraints": {
                "min_images": 1,
                "max_images": 3,
                "min_items": 1,
                "max_items": 2,
                "target_items": 2,
                "columns": 2,
                "is_alternate": True,
            },
            "version": 1,
        },
    },
]


def get_standard_templates() -> list[dict[str, Any]]:
    """Returns a fresh copy of all standard template configurations."""
    import copy
    return copy.deepcopy(STANDARD_TEMPLATES)


def get_template_by_id(template_id: str) -> dict[str, Any] | None:
    """Finds a standard template by template_id, slug, or alias."""
    import copy
    clean = str(template_id or "").strip().lower()
    if not clean:
        return None
    # 1. Exact match by template_id, name, or alias
    for tmpl in STANDARD_TEMPLATES:
        meta = tmpl.get("template_metadata") or {}
        tid = str(meta.get("template_id") or "").lower()
        aliases = [str(a).lower() for a in meta.get("aliases", [])]
        name = str(tmpl.get("name") or "").lower()
        if clean in (tid, name) or clean in aliases:
            return copy.deepcopy(tmpl)
    # 2. Substring or prefix match
    for tmpl in STANDARD_TEMPLATES:
        meta = tmpl.get("template_metadata") or {}
        tid = str(meta.get("template_id") or "").lower()
        aliases = [str(a).lower() for a in meta.get("aliases", [])]
        name = str(tmpl.get("name") or "").lower()
        if (clean in tid) or (tid in clean) or (clean in name) or any(clean in a or a in clean for a in aliases):
            return copy.deepcopy(tmpl)
    return None
