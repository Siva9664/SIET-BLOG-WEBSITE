from datetime import datetime
from enum import Enum
from typing import List

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, BaseModelMixin


class UserRole(str, Enum):
    SUPER_ADMIN = "SUPER_ADMIN"
    LAB_ADMIN = "LAB_ADMIN"
    ADMIN = "ADMIN"          # Legacy — treated as LAB_ADMIN
    EDITOR = "EDITOR"
    AUTHOR = "AUTHOR"


class User(Base, BaseModelMixin):
    __tablename__ = "users"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, index=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(20), default=UserRole.AUTHOR.value, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_login: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Lab membership back-reference (populated by LabMembership model)
    lab_memberships: Mapped[List["LabMembership"]] = relationship(
        "LabMembership", back_populates="user", cascade="all, delete-orphan"
    )

    @property
    def is_super_admin(self) -> bool:
        return str(self.role).upper() == "SUPER_ADMIN"

    @property
    def is_lab_admin(self) -> bool:
        return str(self.role).upper() in ("LAB_ADMIN", "ADMIN")
