"""add scribe, paper, and taida tables

Revision ID: 002
Revises: 001
Create Date: 2026-03-13 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "002"
down_revision = "001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Enable pgvector extension
    op.execute("CREATE EXTENSION IF NOT EXISTS vector")

    # scribe_sessions
    op.create_table(
        "scribe_sessions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("type", sa.String(20), nullable=False),
        sa.Column("input_text", sa.Text, nullable=False),
        sa.Column("result_json", postgresql.JSON, nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("app_name", sa.String(100), nullable=False, server_default="med_scribe"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_scribe_sessions_user_id", "scribe_sessions", ["user_id"])

    # papers
    op.create_table(
        "papers",
        sa.Column("id", sa.String(36), primary_key=True, nullable=False),
        sa.Column("arxiv_id", sa.String(50), nullable=False, unique=True),
        sa.Column("title", sa.Text, nullable=False),
        sa.Column("abstract", sa.Text, nullable=False),
        sa.Column("authors", postgresql.JSON, nullable=True),
        sa.Column("url", sa.Text, nullable=False),
        sa.Column("categories", postgresql.JSON, nullable=True),
        sa.Column("published_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("search_vector", postgresql.TSVECTOR, nullable=True),
        sa.Column("embedding", sa.Text, nullable=True),  # stored as vector type via raw SQL
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
    )
    op.create_index("ix_papers_arxiv_id", "papers", ["arxiv_id"], unique=True)
    op.create_index(
        "ix_papers_search_gin",
        "papers",
        ["search_vector"],
        postgresql_using="gin",
    )

    # Alter embedding column to actual vector type after extension is enabled
    op.execute("ALTER TABLE papers ALTER COLUMN embedding TYPE vector(1536) USING embedding::vector(1536)")

    # taida_analyses
    op.create_table(
        "taida_analyses",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("request_json", postgresql.JSON, nullable=False),
        sa.Column("result_json", postgresql.JSON, nullable=True),
        sa.Column("status", sa.Text, nullable=False, server_default="pending"),
        sa.Column("error_message", sa.Text, nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_taida_analyses_user_id", "taida_analyses", ["user_id"])


def downgrade() -> None:
    op.drop_table("taida_analyses")
    op.drop_table("papers")
    op.drop_table("scribe_sessions")
    op.execute("DROP EXTENSION IF EXISTS vector")
