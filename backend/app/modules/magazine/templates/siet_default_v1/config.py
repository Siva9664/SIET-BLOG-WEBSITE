"""Comprehensive template configuration for SIET_DEFAULT_V1.

Implements all 15 page types:
1. cover
2. contents
3. section_opener
4. event
5. achievement
6. victory
7. project
8. workshop
9. seminar
10. faculty_activity
11. student_activity
12. photo_feature
13. interview
14. news_highlights
15. closing
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
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
from app.modules.magazine.templates.template_schema import (
    CaptionRegionSpec,
    ImageRegionSpec,
    MagazineTemplateSpec,
    PageTypeSpec,
    TextRegionSpec,
)


def _build_standard_typography() -> TypographyHierarchySpec:
    return TypographyHierarchySpec(
        headline=TypographyLevelSpec(
            font_family="times-bold",
            font_size=24.0,
            font_size_min=18.0,
            font_size_max=28.0,
            line_height=1.15,
            color_hex="#8B0000",
            font_weight="bold",
        ),
        subheadline=TypographyLevelSpec(
            font_family="helv",
            font_size=11.5,
            font_size_min=9.5,
            font_size_max=13.0,
            line_height=1.2,
            color_hex="#1A365D",
            font_weight="normal",
        ),
        body=TypographyLevelSpec(
            font_family="times",
            font_size=10.0,
            font_size_min=8.5,
            font_size_max=10.5,
            line_height=1.25,
            color_hex="#1F2937",
            font_weight="normal",
        ),
        section_label=TypographyLevelSpec(
            font_family="helv-bold",
            font_size=8.5,
            line_height=1.0,
            letter_spacing=1.5,
            color_hex="#8B0000",
            font_weight="bold",
            text_transform="uppercase",
        ),
        metadata=TypographyLevelSpec(
            font_family="helv",
            font_size=8.0,
            line_height=1.0,
            color_hex="#6B7280",
            font_weight="normal",
        ),
        pull_quote=TypographyLevelSpec(
            font_family="times-italic",
            font_size=14.0,
            font_size_min=11.0,
            font_size_max=16.0,
            line_height=1.3,
            color_hex="#8B0000",
            font_weight="italic",
        ),
        caption=TypographyLevelSpec(
            font_family="helv",
            font_size=8.0,
            line_height=1.1,
            color_hex="#4B5563",
            font_weight="normal",
        ),
        sidebar_title=TypographyLevelSpec(
            font_family="helv-bold",
            font_size=10.0,
            line_height=1.1,
            color_hex="#1A365D",
            font_weight="bold",
        ),
        sidebar_body=TypographyLevelSpec(
            font_family="helv",
            font_size=8.5,
            line_height=1.2,
            color_hex="#374151",
            font_weight="normal",
        ),
    )


def _build_page_types_dict() -> Dict[str, PageTypeConfig]:
    std_typo = _build_standard_typography()
    pw, ph = 595.28, 841.89
    m_top, m_bot, m_left, m_right = 36.0, 36.0, 36.0, 36.0
    print_w = pw - (m_left + m_right)  # 523.28 pt

    grid_1col = GridSpec(columns=1, column_width=print_w, column_gap=0.0)
    grid_2col = GridSpec(columns=2, column_width=253.64, column_gap=16.0)
    grid_3col = GridSpec(columns=3, column_width=165.09, column_gap=14.0)

    pages: Dict[str, PageTypeConfig] = {}

    # 1. COVER
    pages[PageType.COVER.value] = PageTypeConfig(
        page_type=PageType.COVER,
        display_name="Cover Page",
        description="Authoritative full-bleed magazine cover with masthead, dateline, hero image, and headline.",
        grid=grid_1col,
        columns=1,
        typography_hierarchy=std_typo,
        maximum_image_count=1,
        text_limits={"min_words": 15, "max_words": 50, "max_headline_words": 10},
        regions=[
            RegionSpec(region_key="cover_masthead", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=40.0, width_pt=print_w, height_pt=55.0, font_family="times-bold", font_size_min=24.0, font_size_max=32.0, color_hex="#8B0000", align="center"),
            RegionSpec(region_key="cover_subtitle", role=RegionRole.SUBHEADLINE, x_pt=36.0, y_pt=100.0, width_pt=print_w, height_pt=22.0, font_family="helv", font_size_min=10.0, font_size_max=12.0, color_hex="#1A365D", align="center"),
            RegionSpec(region_key="cover_headline", role=RegionRole.HEADLINE, x_pt=46.0, y_pt=565.0, width_pt=503.28, height_pt=90.0, font_family="times-bold", font_size_min=18.0, font_size_max=24.0, color_hex="#8B0000", align="center"),
            RegionSpec(region_key="cover_blurb", role=RegionRole.BODY, x_pt=56.0, y_pt=660.0, width_pt=483.28, height_pt=45.0, font_family="helv", font_size_min=9.5, font_size_max=11.0, color_hex="#374151", align="center"),
            RegionSpec(region_key="cover_ticker", role=RegionRole.METADATA, x_pt=36.0, y_pt=720.0, width_pt=print_w, height_pt=45.0, font_family="helv-bold", font_size=8.5, color_hex="#1A365D", align="center", background_color_hex="#FEF3C7", border_color_hex="#D97706", border_width=1.0),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="cover_hero_img", role="hero", x_pt=36.0, y_pt=128.0, width_pt=print_w, height_pt=425.0, aspect_ratio="4:3", fit_mode="cover"),
        ],
        optional_decorative_assets={"has_border_frame": True, "border_color": "#8B0000", "background_color": "#FDFBF7"},
    )

    # 2. CONTENTS
    pages[PageType.CONTENTS.value] = PageTypeConfig(
        page_type=PageType.CONTENTS,
        display_name="Table of Contents & Colophon",
        description="Two-column categorical table of contents with right-rail masthead colophon.",
        grid=GridSpec(columns=2, column_width=345.0, column_gap=18.0),
        columns=2,
        typography_hierarchy=std_typo,
        maximum_image_count=1,
        text_limits={"min_words": 60, "max_words": 300, "max_headline_words": 6},
        regions=[
            RegionSpec(region_key="contents_title", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=45.0, width_pt=345.0, height_pt=45.0, font_family="times-bold", font_size_min=20.0, font_size_max=24.0, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="contents_intro", role=RegionRole.SUBHEADLINE, x_pt=36.0, y_pt=95.0, width_pt=345.0, height_pt=30.0, font_family="helv", font_size=10.0, color_hex="#4B5563", align="left"),
            RegionSpec(region_key="contents_list", role=RegionRole.BODY, x_pt=36.0, y_pt=130.0, width_pt=345.0, height_pt=640.0, font_family="times", font_size_min=9.0, font_size_max=10.5, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="contents_masthead_rail", role=RegionRole.SIDEBAR, x_pt=399.0, y_pt=45.0, width_pt=160.28, height_pt=725.0, font_family="helv", font_size=8.5, color_hex="#374151", align="left", background_color_hex="#F9FAFB", border_color_hex="#E5E7EB", border_width=1.0),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="contents_crest_img", role="badge", x_pt=440.0, y_pt=660.0, width_pt=80.0, height_pt=80.0, aspect_ratio="1:1", fit_mode="contain"),
        ],
        optional_decorative_assets={"has_masthead_box": True, "background_color": "#FDFBF7"},
    )

    # 3. SECTION OPENER
    pages[PageType.SECTION_OPENER.value] = PageTypeConfig(
        page_type=PageType.SECTION_OPENER,
        display_name="Section Opener",
        description="Thematic divider page with prominent section banner, drop-cap lead narrative, and preview image.",
        grid=grid_2col,
        columns=2,
        typography_hierarchy=std_typo,
        maximum_image_count=1,
        text_limits={"min_words": 40, "max_words": 220, "max_headline_words": 10},
        regions=[
            RegionSpec(region_key="opener_banner", role=RegionRole.SECTION_LABEL, x_pt=36.0, y_pt=50.0, width_pt=print_w, height_pt=45.0, font_family="helv-bold", font_size=14.0, color_hex="#FFFFFF", align="center", background_color_hex="#8B0000"),
            RegionSpec(region_key="opener_headline", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=105.0, width_pt=print_w, height_pt=55.0, font_family="times-bold", font_size_min=18.0, font_size_max=24.0, color_hex="#1A365D", align="left"),
            RegionSpec(region_key="opener_subhead", role=RegionRole.SUBHEADLINE, x_pt=36.0, y_pt=165.0, width_pt=print_w, height_pt=25.0, font_family="helv", font_size=11.0, color_hex="#4B5563", align="left"),
            RegionSpec(region_key="opener_body_col1", role=RegionRole.BODY, x_pt=36.0, y_pt=450.0, width_pt=253.64, height_pt=320.0, font_family="times", font_size=10.0, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="opener_quote_col2", role=RegionRole.PULL_QUOTE, x_pt=305.64, y_pt=450.0, width_pt=253.64, height_pt=320.0, font_family="times-italic", font_size=13.0, color_hex="#8B0000", align="center"),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="opener_hero_img", role="hero", x_pt=36.0, y_pt=200.0, width_pt=print_w, height_pt=235.0, aspect_ratio="16:9", fit_mode="cover", associated_caption_key="opener_caption"),
        ],
        optional_decorative_assets={"has_header_bar": True, "accent_color": "#8B0000"},
    )

    # 4. EVENT
    pages[PageType.EVENT.value] = PageTypeConfig(
        page_type=PageType.EVENT,
        display_name="Event Report",
        description="Comprehensive campus event page with 2-column narrative, lead photo, and isolated captions.",
        grid=grid_2col,
        columns=2,
        typography_hierarchy=std_typo,
        maximum_image_count=2,
        text_limits={"min_words": 60, "max_words": 350, "max_headline_words": 14},
        regions=[
            RegionSpec(region_key="event_kicker", role=RegionRole.SECTION_LABEL, x_pt=36.0, y_pt=50.0, width_pt=print_w, height_pt=16.0, font_family="helv-bold", font_size=8.5, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="event_headline", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=68.0, width_pt=print_w, height_pt=55.0, font_family="times-bold", font_size_min=16.0, font_size_max=22.0, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="event_meta", role=RegionRole.METADATA, x_pt=36.0, y_pt=126.0, width_pt=print_w, height_pt=18.0, font_family="helv", font_size=8.5, color_hex="#6B7280", align="left"),
            RegionSpec(region_key="event_caption", role=RegionRole.CAPTION, x_pt=36.0, y_pt=405.0, width_pt=print_w, height_pt=18.0, font_family="helv", font_size=8.0, color_hex="#4B5563", align="left"),
            RegionSpec(region_key="event_body_col1", role=RegionRole.BODY, x_pt=36.0, y_pt=430.0, width_pt=253.64, height_pt=340.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="event_body_col2", role=RegionRole.BODY, x_pt=305.64, y_pt=430.0, width_pt=253.64, height_pt=340.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="event_hero_img", role="hero", x_pt=36.0, y_pt=150.0, width_pt=print_w, height_pt=250.0, aspect_ratio="16:9", fit_mode="cover", associated_caption_key="event_caption_1"),
        ],
        optional_decorative_assets={"has_header_bar": True, "has_footer_bar": True},
    )

    # 5. ACHIEVEMENT
    pages[PageType.ACHIEVEMENT.value] = PageTypeConfig(
        page_type=PageType.ACHIEVEMENT,
        display_name="Achievement & Honors",
        description="Distinguished honors showcase with gold accents, trophy badge, cash prize sidebar, and team winner photo.",
        grid=grid_2col,
        columns=2,
        typography_hierarchy=std_typo,
        maximum_image_count=2,
        text_limits={"min_words": 50, "max_words": 300, "max_headline_words": 14},
        regions=[
            RegionSpec(region_key="achieve_banner", role=RegionRole.SECTION_LABEL, x_pt=36.0, y_pt=50.0, width_pt=print_w, height_pt=22.0, font_family="helv-bold", font_size=9.0, color_hex="#D97706", align="left"),
            RegionSpec(region_key="achieve_headline", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=75.0, width_pt=print_w, height_pt=55.0, font_family="times-bold", font_size_min=16.0, font_size_max=22.0, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="achieve_subhead", role=RegionRole.SUBHEADLINE, x_pt=36.0, y_pt=132.0, width_pt=print_w, height_pt=22.0, font_family="helv", font_size=10.5, color_hex="#1A365D", align="left"),
            RegionSpec(region_key="achieve_sidebar", role=RegionRole.SIDEBAR, x_pt=399.0, y_pt=160.0, width_pt=160.28, height_pt=230.0, font_family="helv", font_size=8.5, color_hex="#374151", align="left", background_color_hex="#FEF3C7", border_color_hex="#D97706", border_width=1.0),
            RegionSpec(region_key="achieve_body_col1", role=RegionRole.BODY, x_pt=36.0, y_pt=425.0, width_pt=253.64, height_pt=345.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="achieve_body_col2", role=RegionRole.BODY, x_pt=305.64, y_pt=425.0, width_pt=253.64, height_pt=345.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="achieve_hero_img", role="hero", x_pt=36.0, y_pt=160.0, width_pt=345.0, height_pt=230.0, aspect_ratio="16:9", fit_mode="cover", associated_caption_key="achieve_caption"),
            ImageSlotSpec(slot_key="achieve_trophy_badge", role="badge", x_pt=440.0, y_pt=170.0, width_pt=75.0, height_pt=75.0, aspect_ratio="1:1", fit_mode="contain"),
        ],
        optional_decorative_assets={"badge_type": "trophy_3d", "accent_color": "#D97706"},
    )

    # 6. VICTORY
    pages[PageType.VICTORY.value] = PageTypeConfig(
        page_type=PageType.VICTORY,
        display_name="Championship Victory",
        description="High-octane tournament victory layout with celebratory imagery and stats sidebar.",
        grid=grid_2col,
        columns=2,
        typography_hierarchy=std_typo,
        maximum_image_count=2,
        text_limits={"min_words": 50, "max_words": 300, "max_headline_words": 12},
        regions=[
            RegionSpec(region_key="victory_banner", role=RegionRole.SECTION_LABEL, x_pt=36.0, y_pt=50.0, width_pt=print_w, height_pt=22.0, font_family="helv-bold", font_size=9.0, color_hex="#1A365D", align="left"),
            RegionSpec(region_key="victory_headline", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=75.0, width_pt=print_w, height_pt=60.0, font_family="times-bold", font_size_min=18.0, font_size_max=24.0, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="victory_body_col1", role=RegionRole.BODY, x_pt=36.0, y_pt=430.0, width_pt=253.64, height_pt=340.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="victory_quote_col2", role=RegionRole.PULL_QUOTE, x_pt=305.64, y_pt=430.0, width_pt=253.64, height_pt=140.0, font_family="times-italic", font_size=13.0, color_hex="#8B0000", align="center"),
            RegionSpec(region_key="victory_stats_sidebar", role=RegionRole.SIDEBAR, x_pt=305.64, y_pt=585.0, width_pt=253.64, height_pt=185.0, font_family="helv", font_size=8.5, color_hex="#1F2937", align="left", background_color_hex="#F3F4F6", border_color_hex="#1A365D", border_width=1.0),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="victory_hero_img", role="hero", x_pt=36.0, y_pt=145.0, width_pt=print_w, height_pt=255.0, aspect_ratio="16:9", fit_mode="cover", associated_caption_key="victory_caption"),
        ],
        optional_decorative_assets={"has_gold_ribbon": True},
    )

    # 7. PROJECT
    pages[PageType.PROJECT.value] = PageTypeConfig(
        page_type=PageType.PROJECT,
        display_name="Engineering Project Showcase",
        description="Technical innovation layout featuring architecture diagram, innovator roster, and tech stack sidebar.",
        grid=grid_2col,
        columns=2,
        typography_hierarchy=std_typo,
        maximum_image_count=2,
        text_limits={"min_words": 60, "max_words": 320, "max_headline_words": 14},
        regions=[
            RegionSpec(region_key="project_kicker", role=RegionRole.SECTION_LABEL, x_pt=36.0, y_pt=50.0, width_pt=print_w, height_pt=16.0, font_family="helv-bold", font_size=8.5, color_hex="#1A365D", align="left"),
            RegionSpec(region_key="project_headline", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=68.0, width_pt=print_w, height_pt=55.0, font_family="times-bold", font_size_min=16.0, font_size_max=22.0, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="project_sidebar", role=RegionRole.SIDEBAR, x_pt=399.0, y_pt=135.0, width_pt=160.28, height_pt=240.0, font_family="helv", font_size=8.5, color_hex="#374151", align="left", background_color_hex="#F9FAFB", border_color_hex="#E5E7EB", border_width=1.0),
            RegionSpec(region_key="project_body_col1", role=RegionRole.BODY, x_pt=36.0, y_pt=415.0, width_pt=253.64, height_pt=355.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="project_body_col2", role=RegionRole.BODY, x_pt=305.64, y_pt=415.0, width_pt=253.64, height_pt=355.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="project_hero_img", role="hero", x_pt=36.0, y_pt=135.0, width_pt=345.0, height_pt=240.0, aspect_ratio="16:9", fit_mode="cover", associated_caption_key="project_caption"),
        ],
        optional_decorative_assets={"has_circuit_accent": True},
    )

    # 8. WORKSHOP
    pages[PageType.WORKSHOP.value] = PageTypeConfig(
        page_type=PageType.WORKSHOP,
        display_name="Technical Workshop",
        description="Hands-on workshop layout featuring lab equipment photos, syllabus modules, and student certifications.",
        grid=grid_2col,
        columns=2,
        typography_hierarchy=std_typo,
        maximum_image_count=2,
        text_limits={"min_words": 60, "max_words": 320, "max_headline_words": 14},
        regions=[
            RegionSpec(region_key="ws_kicker", role=RegionRole.SECTION_LABEL, x_pt=36.0, y_pt=50.0, width_pt=print_w, height_pt=16.0, font_family="helv-bold", font_size=8.5, color_hex="#1A365D", align="left"),
            RegionSpec(region_key="ws_headline", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=68.0, width_pt=print_w, height_pt=55.0, font_family="times-bold", font_size_min=16.0, font_size_max=22.0, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="ws_body_col1", role=RegionRole.BODY, x_pt=36.0, y_pt=355.0, width_pt=253.64, height_pt=415.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="ws_sidebar_col2", role=RegionRole.SIDEBAR, x_pt=305.64, y_pt=355.0, width_pt=253.64, height_pt=415.0, font_family="helv", font_size=8.5, color_hex="#374151", align="left", background_color_hex="#F9FAFB", border_color_hex="#1A365D", border_width=1.0),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="ws_img_1", role="grid", x_pt=36.0, y_pt=135.0, width_pt=253.64, height_pt=185.0, aspect_ratio="4:3", fit_mode="cover", associated_caption_key="ws_caption_1"),
            ImageSlotSpec(slot_key="ws_img_2", role="grid", x_pt=305.64, y_pt=135.0, width_pt=253.64, height_pt=185.0, aspect_ratio="4:3", fit_mode="cover", associated_caption_key="ws_caption_2"),
        ],
        optional_decorative_assets={"has_gear_accent": True},
    )

    # 9. SEMINAR
    pages[PageType.SEMINAR.value] = PageTypeConfig(
        page_type=PageType.SEMINAR,
        display_name="Seminar & Invited Lecture",
        description="Keynote lecture layout with speaker portrait, bio sidebar, lecture abstract, and coordinator credits.",
        grid=GridSpec(columns=2, column_width=165.09, column_gap=18.0),
        columns=2,
        typography_hierarchy=std_typo,
        maximum_image_count=1,
        text_limits={"min_words": 60, "max_words": 320, "max_headline_words": 14},
        regions=[
            RegionSpec(region_key="sem_headline", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=50.0, width_pt=print_w, height_pt=55.0, font_family="times-bold", font_size_min=16.0, font_size_max=22.0, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="sem_subhead", role=RegionRole.SUBHEADLINE, x_pt=36.0, y_pt=110.0, width_pt=print_w, height_pt=25.0, font_family="helv", font_size=11.0, color_hex="#1A365D", align="left"),
            RegionSpec(region_key="sem_speaker_bio", role=RegionRole.SIDEBAR, x_pt=36.0, y_pt=350.0, width_pt=165.09, height_pt=420.0, font_family="helv", font_size=8.5, color_hex="#374151", align="left", background_color_hex="#F9FAFB", border_color_hex="#E5E7EB", border_width=1.0),
            RegionSpec(region_key="sem_body_main", role=RegionRole.BODY, x_pt=219.09, y_pt=145.0, width_pt=340.19, height_pt=625.0, font_family="times", font_size=10.0, color_hex="#1F2937", align="left"),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="sem_speaker_portrait", role="portrait", x_pt=36.0, y_pt=145.0, width_pt=165.09, height_pt=190.0, aspect_ratio="1:1", fit_mode="cover", associated_caption_key="sem_caption"),
        ],
        optional_decorative_assets={"has_podium_accent": True},
    )

    # 10. FACULTY ACTIVITY
    pages[PageType.FACULTY_ACTIVITY.value] = PageTypeConfig(
        page_type=PageType.FACULTY_ACTIVITY,
        display_name="Faculty Activity & Research",
        description="Academic research showcase with faculty portrait, publication metrics, research grants, and patents.",
        grid=grid_2col,
        columns=2,
        typography_hierarchy=std_typo,
        maximum_image_count=2,
        text_limits={"min_words": 60, "max_words": 300, "max_headline_words": 14},
        regions=[
            RegionSpec(region_key="fac_kicker", role=RegionRole.SECTION_LABEL, x_pt=36.0, y_pt=50.0, width_pt=print_w, height_pt=16.0, font_family="helv-bold", font_size=8.5, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="fac_headline", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=68.0, width_pt=print_w, height_pt=50.0, font_family="times-bold", font_size_min=16.0, font_size_max=22.0, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="fac_sidebar", role=RegionRole.SIDEBAR, x_pt=230.0, y_pt=130.0, width_pt=329.28, height_pt=200.0, font_family="helv", font_size=8.5, color_hex="#1F2937", align="left", background_color_hex="#F9FAFB", border_color_hex="#1A365D", border_width=1.0),
            RegionSpec(region_key="fac_body_col1", role=RegionRole.BODY, x_pt=36.0, y_pt=360.0, width_pt=253.64, height_pt=410.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="fac_body_col2", role=RegionRole.BODY, x_pt=305.64, y_pt=360.0, width_pt=253.64, height_pt=410.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="fac_portrait", role="portrait", x_pt=36.0, y_pt=130.0, width_pt=175.0, height_pt=200.0, aspect_ratio="4:3", fit_mode="cover", associated_caption_key="fac_caption"),
        ],
        optional_decorative_assets={"has_diploma_accent": True},
    )

    # 11. STUDENT ACTIVITY
    pages[PageType.STUDENT_ACTIVITY.value] = PageTypeConfig(
        page_type=PageType.STUDENT_ACTIVITY,
        display_name="Student Activities & Clubs",
        description="Vibrant 3-column campus life layout with 3-photo gallery and candid student festival coverage.",
        grid=grid_3col,
        columns=3,
        typography_hierarchy=std_typo,
        maximum_image_count=3,
        text_limits={"min_words": 60, "max_words": 350, "max_headline_words": 14},
        regions=[
            RegionSpec(region_key="stud_kicker", role=RegionRole.SECTION_LABEL, x_pt=36.0, y_pt=50.0, width_pt=print_w, height_pt=16.0, font_family="helv-bold", font_size=8.5, color_hex="#1A365D", align="left"),
            RegionSpec(region_key="stud_headline", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=68.0, width_pt=print_w, height_pt=50.0, font_family="times-bold", font_size_min=16.0, font_size_max=22.0, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="stud_body_col1", role=RegionRole.BODY, x_pt=36.0, y_pt=280.0, width_pt=165.09, height_pt=490.0, font_family="times", font_size=9.0, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="stud_body_col2", role=RegionRole.BODY, x_pt=215.09, y_pt=280.0, width_pt=165.09, height_pt=490.0, font_family="times", font_size=9.0, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="stud_body_col3", role=RegionRole.BODY, x_pt=394.18, y_pt=280.0, width_pt=165.09, height_pt=490.0, font_family="times", font_size=9.0, color_hex="#1F2937", align="left"),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="stud_img_1", role="grid", x_pt=36.0, y_pt=130.0, width_pt=165.09, height_pt=125.0, aspect_ratio="4:3", fit_mode="cover", associated_caption_key="stud_caption_1"),
            ImageSlotSpec(slot_key="stud_img_2", role="grid", x_pt=215.09, y_pt=130.0, width_pt=165.09, height_pt=125.0, aspect_ratio="4:3", fit_mode="cover", associated_caption_key="stud_caption_2"),
            ImageSlotSpec(slot_key="stud_img_3", role="grid", x_pt=394.18, y_pt=130.0, width_pt=165.09, height_pt=125.0, aspect_ratio="4:3", fit_mode="cover", associated_caption_key="stud_caption_3"),
        ],
        optional_decorative_assets={"has_cultural_dots": True},
    )

    # 12. PHOTO FEATURE
    pages[PageType.PHOTO_FEATURE.value] = PageTypeConfig(
        page_type=PageType.PHOTO_FEATURE,
        display_name="Photo Feature Gallery",
        description="High-impact photojournalism spread with 4-photo grid, hero image, and detailed descriptive captions.",
        grid=grid_3col,
        columns=3,
        typography_hierarchy=std_typo,
        maximum_image_count=4,
        text_limits={"min_words": 30, "max_words": 150, "max_headline_words": 10},
        regions=[
            RegionSpec(region_key="pf_headline", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=50.0, width_pt=print_w, height_pt=45.0, font_family="times-bold", font_size_min=18.0, font_size_max=24.0, color_hex="#8B0000", align="center"),
            RegionSpec(region_key="pf_intro", role=RegionRole.BODY, x_pt=46.0, y_pt=100.0, width_pt=503.28, height_pt=45.0, font_family="helv", font_size=10.0, color_hex="#374151", align="center"),
            RegionSpec(region_key="pf_bottom_text", role=RegionRole.BODY, x_pt=36.0, y_pt=630.0, width_pt=print_w, height_pt=140.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="pf_hero", role="hero", x_pt=36.0, y_pt=155.0, width_pt=print_w, height_pt=260.0, aspect_ratio="16:9", fit_mode="cover", associated_caption_key="pf_cap_hero"),
            ImageSlotSpec(slot_key="pf_thumb_1", role="grid", x_pt=36.0, y_pt=445.0, width_pt=165.09, height_pt=150.0, aspect_ratio="4:3", fit_mode="cover", associated_caption_key="pf_cap_1"),
            ImageSlotSpec(slot_key="pf_thumb_2", role="grid", x_pt=215.09, y_pt=445.0, width_pt=165.09, height_pt=150.0, aspect_ratio="4:3", fit_mode="cover", associated_caption_key="pf_cap_2"),
            ImageSlotSpec(slot_key="pf_thumb_3", role="grid", x_pt=394.18, y_pt=445.0, width_pt=165.09, height_pt=150.0, aspect_ratio="4:3", fit_mode="cover", associated_caption_key="pf_cap_3"),
        ],
        optional_decorative_assets={"gallery_border": True},
    )

    # 13. INTERVIEW (Austin Chronicle Style)
    pages[PageType.INTERVIEW.value] = PageTypeConfig(
        page_type=PageType.INTERVIEW,
        display_name="Interview & Spotlight Q&A",
        description="Austin Chronicle style interview layout with interviewee portrait, framed pull quote, and bold Q&A dialogue columns.",
        grid=grid_2col,
        columns=2,
        typography_hierarchy=std_typo,
        maximum_image_count=1,
        text_limits={"min_words": 80, "max_words": 380, "max_headline_words": 12},
        regions=[
            RegionSpec(region_key="int_kicker", role=RegionRole.SECTION_LABEL, x_pt=36.0, y_pt=50.0, width_pt=print_w, height_pt=16.0, font_family="helv-bold", font_size=8.5, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="int_headline", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=68.0, width_pt=print_w, height_pt=50.0, font_family="times-bold", font_size_min=16.0, font_size_max=22.0, color_hex="#8B0000", align="left"),
            RegionSpec(region_key="int_subhead", role=RegionRole.SUBHEADLINE, x_pt=36.0, y_pt=122.0, width_pt=print_w, height_pt=25.0, font_family="helv", font_size=10.5, color_hex="#1A365D", align="left"),
            RegionSpec(region_key="int_pull_quote", role=RegionRole.PULL_QUOTE, x_pt=245.0, y_pt=160.0, width_pt=314.28, height_pt=105.0, font_family="times-italic", font_size=13.5, color_hex="#8B0000", align="center", border_color_hex="#8B0000", border_width=1.0),
            RegionSpec(region_key="int_bio_sidebar", role=RegionRole.SIDEBAR, x_pt=245.0, y_pt=275.0, width_pt=314.28, height_pt=105.0, font_family="helv", font_size=8.5, color_hex="#374151", align="left", background_color_hex="#F9FAFB", border_color_hex="#E5E7EB", border_width=1.0),
            RegionSpec(region_key="int_caption", role=RegionRole.CAPTION, x_pt=36.0, y_pt=385.0, width_pt=190.0, height_pt=18.0, font_family="helv", font_size=8.0, color_hex="#4B5563", align="left"),
            RegionSpec(region_key="int_dialogue_col1", role=RegionRole.BODY, x_pt=36.0, y_pt=415.0, width_pt=253.64, height_pt=355.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="int_dialogue_col2", role=RegionRole.BODY, x_pt=305.64, y_pt=415.0, width_pt=253.64, height_pt=355.0, font_family="times", font_size=9.5, color_hex="#1F2937", align="left"),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="int_portrait", role="portrait", x_pt=36.0, y_pt=160.0, width_pt=190.0, height_pt=220.0, aspect_ratio="4:3", fit_mode="cover", associated_caption_key="int_caption"),
        ],
        optional_decorative_assets={"quote_rules": True, "has_accent_frame": True},
    )

    # 14. NEWS / HIGHLIGHTS
    pages[PageType.NEWS_HIGHLIGHTS.value] = PageTypeConfig(
        page_type=PageType.NEWS_HIGHLIGHTS,
        display_name="Campus News & Highlights Digest",
        description="Austin Chronicle style 3-column brief news capsules with date badges, bold lead-in tags, and side calendar.",
        grid=grid_3col,
        columns=3,
        typography_hierarchy=std_typo,
        maximum_image_count=2,
        text_limits={"min_words": 80, "max_words": 400, "max_headline_words": 10},
        regions=[
            RegionSpec(region_key="news_banner", role=RegionRole.SECTION_LABEL, x_pt=36.0, y_pt=50.0, width_pt=print_w, height_pt=32.0, font_family="helv-bold", font_size=11.0, color_hex="#FFFFFF", align="center", background_color_hex="#1A365D"),
            RegionSpec(region_key="news_col1", role=RegionRole.BODY, x_pt=36.0, y_pt=210.0, width_pt=165.09, height_pt=560.0, font_family="times", font_size=9.0, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="news_col2", role=RegionRole.BODY, x_pt=215.09, y_pt=210.0, width_pt=165.09, height_pt=560.0, font_family="times", font_size=9.0, color_hex="#1F2937", align="left"),
            RegionSpec(region_key="news_col3_sidebar", role=RegionRole.SIDEBAR, x_pt=394.18, y_pt=95.0, width_pt=165.09, height_pt=675.0, font_family="helv", font_size=8.5, color_hex="#374151", align="left", background_color_hex="#F9FAFB", border_color_hex="#1A365D", border_width=1.0),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="news_thumb_1", role="grid", x_pt=36.0, y_pt=95.0, width_pt=165.09, height_pt=100.0, aspect_ratio="16:9", fit_mode="cover"),
            ImageSlotSpec(slot_key="news_thumb_2", role="grid", x_pt=215.09, y_pt=95.0, width_pt=165.09, height_pt=100.0, aspect_ratio="16:9", fit_mode="cover"),
        ],
        optional_decorative_assets={"capsule_badges": True},
    )

    # 15. CLOSING
    pages[PageType.CLOSING.value] = PageTypeConfig(
        page_type=PageType.CLOSING,
        display_name="Valedictory Closing & Colophon",
        description="Institutional valedictory page with SIET crest, vision quote, credits, and colophon.",
        grid=grid_1col,
        columns=1,
        typography_hierarchy=std_typo,
        maximum_image_count=1,
        text_limits={"min_words": 30, "max_words": 180, "max_headline_words": 8},
        regions=[
            RegionSpec(region_key="closing_title", role=RegionRole.HEADLINE, x_pt=36.0, y_pt=100.0, width_pt=print_w, height_pt=45.0, font_family="times-bold", font_size_min=18.0, font_size_max=22.0, color_hex="#8B0000", align="center"),
            RegionSpec(region_key="closing_message", role=RegionRole.BODY, x_pt=46.0, y_pt=160.0, width_pt=503.28, height_pt=140.0, font_family="times", font_size_min=10.0, font_size_max=12.0, color_hex="#1F2937", align="center"),
            RegionSpec(region_key="colophon_credits", role=RegionRole.SIDEBAR, x_pt=46.0, y_pt=570.0, width_pt=503.28, height_pt=190.0, font_family="helv", font_size_min=9.0, font_size_max=10.5, color_hex="#4B5563", align="center", background_color_hex="#F9FAFB", border_color_hex="#E5E7EB", border_width=1.0),
        ],
        image_slots=[
            ImageSlotSpec(slot_key="closing_crest_img", role="badge", x_pt=217.64, y_pt=340.0, width_pt=160.0, height_pt=160.0, aspect_ratio="1:1", fit_mode="contain"),
        ],
        optional_decorative_assets={"has_seal": True, "background_color": "#FDFBF7"},
    )

    return pages


def build_siet_default_v1_template() -> SIETDefaultV1Template:
    """Builds and returns the comprehensive SIETDefaultV1Template container."""
    return SIETDefaultV1Template(
        page_types=_build_page_types_dict()
    )


# Static template instance for caching
_TEMPLATE_INSTANCE: Optional[SIETDefaultV1Template] = None
_LEGACY_SPEC_INSTANCE: Optional[MagazineTemplateSpec] = None


def get_siet_default_v1_template() -> MagazineTemplateSpec:
    """
    Returns MagazineTemplateSpec compatible with pipeline & validator,
    fully populated with all 15 page types plus legacy aliases.
    """
    global _LEGACY_SPEC_INSTANCE, _TEMPLATE_INSTANCE
    if _LEGACY_SPEC_INSTANCE is not None:
        return _LEGACY_SPEC_INSTANCE

    rich_template = build_siet_default_v1_template()
    _TEMPLATE_INSTANCE = rich_template

    page_specs_dict: Dict[str, PageTypeSpec] = {}

    for p_key, p_cfg in rich_template.page_types.items():
        # Map RegionSpec to TextRegionSpec
        text_regions: List[TextRegionSpec] = []
        for reg in p_cfg.regions:
            role_val = reg.role.value
            if role_val in {"headline", "subheadline", "body", "sidebar", "section_label", "metadata", "pull_quote"}:
                text_regions.append(
                    TextRegionSpec(
                        region_key=reg.region_key,
                        role=role_val,
                        x_pt=reg.x_pt,
                        y_pt=reg.y_pt,
                        width_pt=reg.width_pt,
                        height_pt=reg.height_pt,
                        max_words=reg.max_words,
                        max_chars=reg.max_chars,
                        font_size_min=reg.font_size_min or 8.5,
                        font_size_max=reg.font_size_max or reg.font_size or 12.0,
                        font_family=reg.font_family or "helv",
                        color_hex=reg.color_hex,
                        align=reg.align,
                    )
                )

        # Map ImageSlotSpec to ImageRegionSpec & CaptionRegionSpec
        image_regions: List[ImageRegionSpec] = []
        caption_regions: List[CaptionRegionSpec] = []

        for slot in p_cfg.image_slots:
            image_regions.append(
                ImageRegionSpec(
                    region_key=slot.slot_key,
                    role=slot.role,
                    x_pt=slot.x_pt,
                    y_pt=slot.y_pt,
                    width_pt=slot.width_pt,
                    height_pt=slot.height_pt,
                    aspect_ratio=slot.aspect_ratio,
                    fit_mode=slot.fit_mode,
                    border_radius=slot.border_radius,
                )
            )
            if slot.associated_caption_key:
                # Deduce caption region position (directly below image)
                cap_y = min(slot.y_pt + slot.height_pt + 3.0, 800.0)
                caption_regions.append(
                    CaptionRegionSpec(
                        region_key=slot.associated_caption_key,
                        associated_image_key=slot.slot_key,
                        x_pt=slot.x_pt,
                        y_pt=cap_y,
                        width_pt=slot.width_pt,
                        height_pt=16.0,
                        max_words=15,
                        font_size=8.0,
                        color_hex="#4B5563",
                    )
                )

        spec = PageTypeSpec(
            page_type=p_key,
            display_name=p_cfg.display_name,
            description=p_cfg.description,
            width_pt=p_cfg.page_dimensions.get("width_pt", 595.28),
            height_pt=p_cfg.page_dimensions.get("height_pt", 841.89),
            margins=p_cfg.margins,
            maximum_images=p_cfg.maximum_image_count,
            headline_limits={
                "max_words": p_cfg.text_limits.get("max_headline_words", 14),
                "max_chars": p_cfg.text_limits.get("max_headline_words", 14) * 8,
            },
            body_limits={
                "min_words": p_cfg.text_limits.get("min_words", 40),
                "max_words": p_cfg.text_limits.get("max_words", 400),
            },
            spacing={
                "paragraph_gap": p_cfg.spacing.paragraph_gap,
                "column_gap": p_cfg.spacing.column_gap,
            },
            alignment=p_cfg.alignment,
            text_regions=text_regions,
            image_regions=image_regions,
            caption_regions=caption_regions,
            decorative_elements=p_cfg.optional_decorative_assets,
        )
        page_specs_dict[p_key] = spec

    # Support legacy aliases
    if "achievement" in page_specs_dict:
        page_specs_dict["achievement_victory"] = page_specs_dict["achievement"]
    if "closing" in page_specs_dict:
        page_specs_dict["closing_page"] = page_specs_dict["closing"]

    _LEGACY_SPEC_INSTANCE = MagazineTemplateSpec(
        template_id=rich_template.template_id,
        name=rich_template.name,
        version=rich_template.version,
        description=rich_template.description,
        supported_page_types=page_specs_dict,
        primary_color=rich_template.theme_tokens.get("primary_color", "#8B0000"),
        secondary_color=rich_template.theme_tokens.get("secondary_color", "#1A365D"),
        background_color=rich_template.theme_tokens.get("neutral_light", "#FDFBF7"),
        text_color=rich_template.theme_tokens.get("neutral_dark", "#1F2937"),
    )
    return _LEGACY_SPEC_INSTANCE
