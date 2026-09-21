"""SIET_DEFAULT_V1 Template Package.

High-density editorial college magazine template system designed from professional
publication standards (Austin Chronicle reference study).
"""

from app.modules.magazine.templates.siet_default_v1.models import (
    GridSpec,
    ImageSlotSpec,
    PageType,
    PageTypeConfig,
    RegionRole,
    RegionSpec,
    SIETDefaultV1Template,
    SpacingSpec,
    TypographyHierarchySpec,
    TypographyLevelSpec,
)
from app.modules.magazine.templates.siet_default_v1.config import (
    build_siet_default_v1_template,
    get_siet_default_v1_template,
)
from app.modules.magazine.templates.siet_default_v1.layout_planner import (
    SIETDefaultV1LayoutPlanner,
)
from app.modules.magazine.templates.siet_default_v1.renderer import (
    SIETDefaultV1Renderer,
)

__all__ = [
    "PageType",
    "RegionRole",
    "GridSpec",
    "TypographyLevelSpec",
    "TypographyHierarchySpec",
    "RegionSpec",
    "ImageSlotSpec",
    "SpacingSpec",
    "PageTypeConfig",
    "SIETDefaultV1Template",
    "build_siet_default_v1_template",
    "get_siet_default_v1_template",
    "SIETDefaultV1LayoutPlanner",
    "SIETDefaultV1Renderer",
]
