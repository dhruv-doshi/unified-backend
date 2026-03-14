import uuid
from datetime import datetime
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import String, Text, DateTime, Index, JSON
from sqlalchemy.dialects.postgresql import TSVECTOR
from pgvector.sqlalchemy import Vector
from src.infrastructure.models.base import Base, TimestampMixin


class Paper(Base, TimestampMixin):
    """Shared arXiv paper catalog — no user FK, read by anyone."""

    __tablename__ = "papers"
    __table_args__ = (
        Index("ix_papers_search_gin", "search_vector", postgresql_using="gin",
              info={"skip_on_sqlite": True}),
        Index("ix_papers_arxiv_id", "arxiv_id", unique=True),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid.uuid4())
    )
    arxiv_id: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    title: Mapped[str] = mapped_column(Text, nullable=False)
    abstract: Mapped[str] = mapped_column(Text, nullable=False)
    authors: Mapped[list | None] = mapped_column(JSON, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    categories: Mapped[list | None] = mapped_column(JSON, nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    # Full-text search vector (populated by trigger or app)
    search_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)

    # Semantic embedding via pgvector (1536-dim, ada-002 compatible)
    embedding: Mapped[list | None] = mapped_column(Vector(1536), nullable=True)
