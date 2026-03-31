"""add scribe enhancements columns

Revision ID: 003
Revises: 002
Create Date: 2026-03-30 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add title column for session display name
    op.add_column(
        "scribe_sessions",
        sa.Column("title", sa.String(255), nullable=True),
    )

    # Add doctor_notes_json column for MCQ answers
    op.add_column(
        "scribe_sessions",
        sa.Column("doctor_notes_json", postgresql.JSON, nullable=True),
    )

    # Add transcription_segments column for audit trail
    op.add_column(
        "scribe_sessions",
        sa.Column("transcription_segments", postgresql.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("scribe_sessions", "transcription_segments")
    op.drop_column("scribe_sessions", "doctor_notes_json")
    op.drop_column("scribe_sessions", "title")
