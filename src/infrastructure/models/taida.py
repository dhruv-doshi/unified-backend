import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import Text, ForeignKey, Uuid, JSON
from src.infrastructure.models.base import Base, TimestampMixin


class TaidaAnalysis(Base, TimestampMixin):
    __tablename__ = "taida_analyses"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    request_json: Mapped[dict] = mapped_column(JSON, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(Text, nullable=False, default="pending")  # pending|completed|failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
