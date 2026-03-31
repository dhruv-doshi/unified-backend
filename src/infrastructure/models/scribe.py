import uuid
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, ForeignKey, Uuid, JSON
from src.infrastructure.models.base import Base, TimestampMixin


class ScribeSession(Base, TimestampMixin):
    __tablename__ = "scribe_sessions"

    id: Mapped[uuid.UUID] = mapped_column(Uuid(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # "summarize" | "generate"
    input_text: Mapped[str] = mapped_column(Text, nullable=False)
    result_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="pending")  # pending|completed|failed
    app_name: Mapped[str] = mapped_column(String(100), nullable=False, default="med_scribe")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    title: Mapped[str | None] = mapped_column(String(255), nullable=True)  # User-editable session name
    doctor_notes_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # MCQ answers
    transcription_segments: Mapped[dict | None] = mapped_column(JSON, nullable=True)  # Audit trail
