from datetime import datetime, timezone
from typing import List, Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin
from app.shared.types.content import ContentStatus, MagazineType


class Magazine(Base, BaseModelMixin):
    __tablename__ = "magazines"

    title: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(300), unique=True, index=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Event-based fields
    event_name: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    event_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True, index=True)

    magazine_type: Mapped[MagazineType] = mapped_column(Enum(MagazineType), default=MagazineType.SPECIAL, nullable=False)
    publication_year: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    issue_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(30), default="draft", nullable=False)  # draft | processing | published | archived | failed
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # 90-day featured priority flag (mirrors news is_archived logic in reverse)
    is_featured: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    featured_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    cover_image_id: Mapped[int | None] = mapped_column(ForeignKey("media.id"), nullable=True)
    pdf_file_id: Mapped[int | None] = mapped_column(ForeignKey("media.id"), nullable=True)

    pdf_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    cover_image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    page_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(Text, nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Structured page sets as JSON arrays of {url, caption?} objects
    # cover_pages: first 2 intro/cover pages uploaded by admin
    # body_pages: event write-up/content pages
    # gallery_images: event photos appended as final gallery section
    cover_pages: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)
    body_pages: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)
    gallery_images: Mapped[list | None] = mapped_column(JSON, default=list, nullable=True)

    # Relationships
    pages: Mapped[list["MagazinePage"]] = relationship(back_populates="magazine", cascade="all, delete-orphan", order_by="MagazinePage.page_number")
    toc_entries: Mapped[list["MagazineTOCEntry"]] = relationship(back_populates="magazine", cascade="all, delete-orphan", order_by="MagazineTOCEntry.page_number")
    achievements: Mapped[list["MagazineAchievement"]] = relationship(back_populates="magazine", cascade="all, delete-orphan")
    project_links: Mapped[list["MagazineProjectLink"]] = relationship(back_populates="magazine", cascade="all, delete-orphan")


class MagazinePage(Base, BaseModelMixin):
    __tablename__ = "magazine_pages"

    magazine_id: Mapped[int] = mapped_column(ForeignKey("magazines.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    image_url: Mapped[str] = mapped_column(String(500), nullable=False)
    extracted_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    magazine: Mapped["Magazine"] = relationship(back_populates="pages")


class MagazineTOCEntry(Base, BaseModelMixin):
    __tablename__ = "magazine_toc_entries"

    magazine_id: Mapped[int] = mapped_column(ForeignKey("magazines.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False)
    heading: Mapped[str] = mapped_column(String(255), nullable=False)

    magazine: Mapped["Magazine"] = relationship(back_populates="toc_entries")


class MagazineAchievement(Base, BaseModelMixin):
    __tablename__ = "magazine_achievements"
    
    magazine_id: Mapped[int] = mapped_column(ForeignKey("magazines.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    magazine: Mapped["Magazine"] = relationship(back_populates="achievements")


class MagazineProjectLink(Base, BaseModelMixin):
    __tablename__ = "magazine_project_links"
    
    magazine_id: Mapped[int] = mapped_column(ForeignKey("magazines.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False)
    
    magazine: Mapped["Magazine"] = relationship(back_populates="project_links")


DEFAULT_SECTION_SCHEMA = [
    {
        "section_type": "cover",
        "label": "Issue Cover & Title",
        "enabled": True,
        "layout_rules": {"show_logo": True, "title_alignment": "center", "cover_image": True}
    },
    {
        "section_type": "editors_note",
        "label": "Editor's Note & Overview",
        "enabled": True,
        "layout_rules": {"columns": 1, "highlight_quote": True}
    },
    {
        "section_type": "featured_story",
        "label": "Featured Research & Writeup",
        "enabled": True,
        "layout_rules": {"columns": 2, "show_subheadings": True, "drop_cap": True}
    },
    {
        "section_type": "events_roundup",
        "label": "Key Events & Proceedings",
        "enabled": True,
        "layout_rules": {"card_grid": True, "show_metrics": True}
    },
    {
        "section_type": "gallery",
        "label": "Event Photo Gallery",
        "enabled": True,
        "layout_rules": {"grid_columns": 3, "caption_max_words": 12}
    },
    {
        "section_type": "closing_ai_news",
        "label": "Latest in AI & Research Digest",
        "enabled": True,
        "layout_rules": {"max_items": 5, "show_source": True, "show_date": True}
    }
]

DEFAULT_STYLE_RULES = {
    "accent_color": "#8B0000",
    "background_color": "#FDFBF7",
    "text_color": "#111111",
    "font_display": "Playfair Display",
    "font_body": "Source Serif Pro",
    "font_util": "Inter",
    "border_style": "classic_thin",
    "spacing": "normal"
}


class MagazineTemplate(Base, BaseModelMixin):
    __tablename__ = "magazine_templates"

    name: Mapped[str] = mapped_column(String(255), nullable=False, default="SIET Standard Issue Template")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    section_schema: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    style_rules: Mapped[dict] = mapped_column(JSON, default=dict, nullable=False)

    versions: Mapped[List["TemplateVersion"]] = relationship("TemplateVersion", back_populates="template", cascade="all, delete-orphan")


class TemplateVersion(Base, BaseModelMixin):
    __tablename__ = "template_versions"

    template_id: Mapped[int] = mapped_column(ForeignKey("magazine_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    version_number: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)

    template: Mapped["MagazineTemplate"] = relationship("MagazineTemplate", back_populates="versions")
    pages: Mapped[List["TemplatePage"]] = relationship("TemplatePage", back_populates="version", cascade="all, delete-orphan")


class TemplatePage(Base, BaseModelMixin):
    __tablename__ = "template_pages"

    version_id: Mapped[int] = mapped_column(ForeignKey("template_versions.id", ondelete="CASCADE"), nullable=False, index=True)
    page_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    width_pt: Mapped[float] = mapped_column(Float, default=595.28, nullable=False)  # A4 width in pt
    height_pt: Mapped[float] = mapped_column(Float, default=841.89, nullable=False) # A4 height in pt
    margin_top: Mapped[float] = mapped_column(Float, default=36.0, nullable=False)
    margin_bottom: Mapped[float] = mapped_column(Float, default=36.0, nullable=False)
    margin_left: Mapped[float] = mapped_column(Float, default=36.0, nullable=False)
    margin_right: Mapped[float] = mapped_column(Float, default=36.0, nullable=False)

    version: Mapped["TemplateVersion"] = relationship("TemplateVersion", back_populates="pages")
    regions: Mapped[List["TemplateRegion"]] = relationship("TemplateRegion", back_populates="page", cascade="all, delete-orphan")


class TemplateRegion(Base, BaseModelMixin):
    __tablename__ = "template_regions"

    page_id: Mapped[int] = mapped_column(ForeignKey("template_pages.id", ondelete="CASCADE"), nullable=False, index=True)
    region_key: Mapped[str] = mapped_column(String(100), nullable=False)
    x_pt: Mapped[float] = mapped_column(Float, nullable=False)
    y_pt: Mapped[float] = mapped_column(Float, nullable=False)
    width_pt: Mapped[float] = mapped_column(Float, nullable=False)
    height_pt: Mapped[float] = mapped_column(Float, nullable=False)
    role: Mapped[str] = mapped_column(String(50), default="feature", nullable=False)  # hero | feature | card | caption | header | footer | sidebar
    typography: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    color_palette: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    page: Mapped["TemplatePage"] = relationship("TemplatePage", back_populates="regions")


