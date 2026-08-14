from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, JSON, String, Text
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
