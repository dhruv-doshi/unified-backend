import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Index, Uuid, JSON
from src.infrastructure.models.base import Base, TimestampMixin


class Analysis(Base, TimestampMixin):
    __tablename__ = "analyses"
    __table_args__ = (
        Index("ix_analyses_user_created", "user_id", "created_at"),
        Index("ix_analyses_user_status", "user_id", "status"),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    app_name: Mapped[str] = mapped_column(String(100), nullable=False, default="shoot_right")
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    original_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    thumbnail_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")

    overall_score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    summary_headline: Mapped[str | None] = mapped_column(Text, nullable=True)
    summary_text: Mapped[str | None] = mapped_column(Text, nullable=True)

    metadata_: Mapped[dict | None] = mapped_column("metadata", JSON, nullable=True)
    histogram: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    composition: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    technical: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    color_aesthetic: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    clicking_tips: Mapped[list | None] = mapped_column(JSON, nullable=True)
    editing_tips: Mapped[list | None] = mapped_column(JSON, nullable=True)

    improvement_shot_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvement_shot_explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    improvement_shot_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)

    user: Mapped["User"] = relationship("User", back_populates="analyses")


from src.infrastructure.models.user import User  # noqa: E402
