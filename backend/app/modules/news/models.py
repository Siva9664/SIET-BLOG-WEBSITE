from datetime import datetime
from enum import Enum as PyEnum

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin
from app.shared.types.content import ContentStatus


class DepartmentEnum(str, PyEnum):
    AI_ML = "ai-ml"
    CYBERSECURITY = "cybersecurity"
    PCB_ELECTRONICS = "pcb-electronics"
    VLSI_SEMICONDUCTOR = "vlsi-semiconductor"
    ROBOTICS = "robotics"
    AR_VR_XR = "ar-vr-xr"
    IOT = "iot"


class Source(Base, BaseModelMixin):
    __tablename__ = "sources"

    name: Mapped[str] = mapped_column(String(150), nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False, default="ai-ml")
    feed_type: Mapped[str] = mapped_column(String(20), nullable=False, default="rss")  # rss | api
    feed_url: Mapped[str] = mapped_column(String(500), unique=True, index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_success_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class Category(Base, BaseModelMixin):
    __tablename__ = "categories"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)
    department_code: Mapped[str] = mapped_column(String(50), nullable=False)


class Subcategory(Base, BaseModelMixin):
    __tablename__ = "subcategories"

    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, index=True, nullable=False)


class SyncLog(Base, BaseModelMixin):
    __tablename__ = "sync_logs"

    run_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    duration_seconds: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    sources_checked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    articles_discovered: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    articles_new: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    articles_duplicate: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    articles_failed: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default="success", nullable=False)  # success | partial | failed
    log_details: Mapped[dict | None] = mapped_column(JSON, nullable=True)


class StoryCoverage(Base, BaseModelMixin):
    __tablename__ = "story_coverage"

    news_id: Mapped[int] = mapped_column(ForeignKey("news.id", ondelete="CASCADE"), index=True, nullable=False)
    source_name: Mapped[str] = mapped_column(String(150), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False)
    title: Mapped[str] = mapped_column(String(300), nullable=False)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    news_item: Mapped["News"] = relationship("News", back_populates="coverage_entries")


class News(Base, BaseModelMixin):
    __tablename__ = "news"

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    slug: Mapped[str] = mapped_column(String(350), unique=True, index=True, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    excerpt: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # AI Enrichment & Explanation Layers
    simple_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    detailed_sections: Mapped[list | None] = mapped_column(JSON, nullable=True)  # List of {heading: str, paragraphs: list[str]}
    content_depth: Mapped[str] = mapped_column(String(20), default="summary_only", nullable=False)  # full | summary_only

    content_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    detailed_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    key_points: Mapped[list | None] = mapped_column(JSON, nullable=True)  # List of strings
    technical_details: Mapped[str | None] = mapped_column(Text, nullable=True)
    why_it_matters: Mapped[str | None] = mapped_column(Text, nullable=True)
    student_relevance: Mapped[str | None] = mapped_column(Text, nullable=True)

    # Department & Subcategory taxonomy
    department: Mapped[str] = mapped_column(String(50), nullable=False, default="ai-ml")
    subcategory: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tags_list: Mapped[list | None] = mapped_column(JSON, nullable=True)  # List of tag strings

    # Multi-source Story Clustering & Verification
    coverage_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    verification_status: Mapped[str] = mapped_column(String(30), default="single_source", nullable=False)  # single_source | confirmed
    coverage_entries: Mapped[list["StoryCoverage"]] = relationship("StoryCoverage", back_populates="news_item", cascade="all, delete-orphan", lazy="selectin")

    # Source & Attribution
    source_id: Mapped[int | None] = mapped_column(ForeignKey("sources.id", ondelete="SET NULL"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(500), unique=True, index=True, nullable=True)
    canonical_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source_name: Mapped[str | None] = mapped_column(String(150), nullable=True)
    author: Mapped[str | None] = mapped_column(String(150), nullable=True)

    # Media & Images
    image_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    image_caption: Mapped[str | None] = mapped_column(String(300), nullable=True)
    featured_image_id: Mapped[int | None] = mapped_column(ForeignKey("media.id"), nullable=True)

    # Timestamps & Hashing
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    fetched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    content_hash: Mapped[str | None] = mapped_column(String(64), index=True, nullable=True)

    # Duplicate tracking
    duplicate_of_id: Mapped[int | None] = mapped_column(ForeignKey("news.id", ondelete="SET NULL"), nullable=True)
    processing_status: Mapped[str] = mapped_column(String(20), default="processed", nullable=False)

    # Archiving
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False, index=True)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Legacy fields compat
    status: Mapped[ContentStatus] = mapped_column(Enum(ContentStatus, name="contentstatus"), default=ContentStatus.PUBLISHED, nullable=False)
    domain_id: Mapped[int | None] = mapped_column(ForeignKey("domains.id"), nullable=True)
    author_id: Mapped[int | None] = mapped_column(ForeignKey("users.id"), nullable=True)
