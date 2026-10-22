"""Unit tests for Phase 2 & Problem 8: Template Management System impact tests."""

import pytest
from app.modules.magazine.template_schema import TemplateMetadata, TextCapacity, normalize_template_metadata


def test_template_word_budget_edits_affect_metadata():
    """Verify that editing template word budgets alters the TextCapacity rules."""
    raw_template_v1 = {
        "name": "Custom Test Template",
        "text_capacity": {"max_words": 300, "max_headline_words": 10},
    }
    meta_v1 = TemplateMetadata(
        template_id="custom_test_template",
        name="Custom Test Template",
        text_capacity=TextCapacity.from_raw(raw_template_v1["text_capacity"]),
    )
    assert meta_v1.text_capacity.max_words == 300
    assert meta_v1.text_capacity.max_headline_words == 10

    raw_template_v2 = {
        "name": "Custom Test Template",
        "text_capacity": {"max_words": 600, "max_headline_words": 20},
    }
    meta_v2 = TemplateMetadata(
        template_id="custom_test_template",
        name="Custom Test Template",
        text_capacity=TextCapacity.from_raw(raw_template_v2["text_capacity"]),
    )
    assert meta_v2.text_capacity.max_words == 600
    assert meta_v2.text_capacity.max_headline_words == 20
    assert meta_v2.text_capacity.max_words != meta_v1.text_capacity.max_words


def test_template_section_schema_toggle_affects_supported_content():
    """Verify that toggling sections in template section_schema alters supported_content_types."""
    tmpl_dict = {
        "id": 101,
        "name": "Dynamic Section Template",
        "section_schema": [
            {"key": "article", "section_type": "article", "enabled": True},
            {"key": "research", "section_type": "research", "enabled": False},
        ],
    }
    meta1 = normalize_template_metadata(tmpl_dict)
    assert meta1.supports_content_type("article") is True

    tmpl_dict["section_schema"][1]["enabled"] = True
    meta2 = normalize_template_metadata(tmpl_dict)
    assert meta2.supports_content_type("research") is True
