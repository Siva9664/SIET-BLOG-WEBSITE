"""Round-trip regression test: every standard template must normalize cleanly.

For each entry from ``get_standard_templates()`` the chain
``normalize_template_metadata -> _metadata_style_dict -> normalize`` must
not raise. This guards against style-name strings (e.g. ``"modern_tech"``)
being misinterpreted as style-rules dicts.
"""
from __future__ import annotations


def test_standard_templates_normalize_roundtrip() -> None:
    from app.modules.magazine.end_to_end_pipeline import _metadata_style_dict
    from app.modules.magazine.template_library import get_standard_templates
    from app.modules.magazine.template_schema import normalize_template_metadata

    templates = get_standard_templates()
    assert templates, "expected at least one standard template"

    for tmpl in templates:
        meta = normalize_template_metadata(tmpl)
        style = _metadata_style_dict(meta)
        assert isinstance(style, dict)
        # Second normalize must also succeed (round-trip invariant).
        meta2 = normalize_template_metadata(meta)
        assert meta2.template_id == meta.template_id
