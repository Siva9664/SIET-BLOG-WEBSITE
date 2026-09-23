from datetime import datetime, timezone
from typing import TYPE_CHECKING, List, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin

if TYPE_CHECKING:
    from app.modules.auth.models import User
    from app.modules.magazine.models import MagazineTemplate, Magazine


class Lab(Base, BaseModelMixin):
    __tablename__ = "labs"

    name: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    code: Mapped[str] = mapped_column(String(50), unique=True, index=True, nullable=False)
    slug: Mapped[str] = mapped_column(String(150), unique=True, index=True, nullable=False)
    department_id: Mapped[int | None] = mapped_column(ForeignKey("domains.id", ondelete="SET NULL"), nullable=True, index=True)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)

    # Relationships
    memberships: Mapped[List["LabMembership"]] = relationship("LabMembership", back_populates="lab", cascade="all, delete-orphan")
    template_assignments: Mapped[List["TemplateLabAssignment"]] = relationship("TemplateLabAssignment", back_populates="lab", cascade="all, delete-orphan")
    magazines: Mapped[List["Magazine"]] = relationship("Magazine", back_populates="lab")


class LabMembership(Base, BaseModelMixin):
    __tablename__ = "lab_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "lab_id", name="uq_lab_memberships_user_lab"),
    )

    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(50), default="LAB_ADMIN", nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="lab_memberships")
    lab: Mapped["Lab"] = relationship("Lab", back_populates="memberships")


class TemplateLabAssignment(Base, BaseModelMixin):
    __tablename__ = "template_lab_assignments"
    __table_args__ = (
        UniqueConstraint("template_id", "lab_id", name="uq_template_lab_assignments_template_lab"),
    )

    template_id: Mapped[int] = mapped_column(ForeignKey("magazine_templates.id", ondelete="CASCADE"), nullable=False, index=True)
    lab_id: Mapped[int] = mapped_column(ForeignKey("labs.id", ondelete="CASCADE"), nullable=False, index=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    template: Mapped["MagazineTemplate"] = relationship("MagazineTemplate", back_populates="lab_assignments")
    lab: Mapped["Lab"] = relationship("Lab", back_populates="template_assignments")
