"""
Magazine templates package.
"""

from app.modules.magazine.templates.template_schema import (
    CaptionRegionSpec,
    ImageRegionSpec,
    MagazineTemplateSpec,
    PageTypeSpec,
    TextRegionSpec,
)
from app.modules.magazine.templates.siet_default_v1 import get_siet_default_v1_template

__all__ = [
    "TextRegionSpec",
    "ImageRegionSpec",
    "CaptionRegionSpec",
    "PageTypeSpec",
    "MagazineTemplateSpec",
    "get_siet_default_v1_template",
]
