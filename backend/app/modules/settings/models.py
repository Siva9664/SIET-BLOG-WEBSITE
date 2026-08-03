from sqlalchemy import Boolean, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BaseModelMixin


class SiteSettings(Base, BaseModelMixin):
    __tablename__ = "site_settings"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, default=1)
    site_name: Mapped[str] = mapped_column(String(200), nullable=False, default="SIET News")
    credit_line: Mapped[str] = mapped_column(
        Text,
        nullable=False,
        default="AI Research Lab · Sri Shakthi Institute of Engineering and Technology",
    )
    accent_color: Mapped[str] = mapped_column(String(50), nullable=False, default="#0F2B5C")
    newsletter_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    featured_domains: Mapped[str] = mapped_column(
        String(500), nullable=False, default="machine-learning, robotics"
    )
