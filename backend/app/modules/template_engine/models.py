from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, JSON, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base, BaseModelMixin


class DocxTemplateBlueprint(Base, BaseModelMixin):
    __tablename__ = "docx_template_blueprints"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    source_document_id: Mapped[Optional[int]] = mapped_column(ForeignKey("source_documents.id", ondelete="SET NULL"), nullable=True, index=True)
    blueprint_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    is_confirmed: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False)
