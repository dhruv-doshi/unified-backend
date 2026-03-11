"""initial schema

Revision ID: 001
Revises:
Create Date: 2026-03-10 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '001'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Create users table (no FK dependencies)
    op.create_table(
        'users',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('name', sa.String(255), nullable=False),
        sa.Column('email', sa.String(255), nullable=False),
        sa.Column('hashed_password', sa.String(255), nullable=True),
        sa.Column('image_url', sa.Text(), nullable=True),
        sa.Column('is_verified', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_users_email', 'users', ['email'], unique=True)

    # Create email_verifications table (FK -> users)
    op.create_table(
        'email_verifications',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_email_verifications_token', 'email_verifications', ['token'], unique=True)

    # Create password_resets table (FK -> users)
    op.create_table(
        'password_resets',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(255), nullable=False),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('used_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_password_resets_token', 'password_resets', ['token'], unique=True)

    # Create analyses table (FK -> users)
    op.create_table(
        'analyses',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('app_name', sa.String(100), nullable=False, server_default='shoot_right'),
        sa.Column('filename', sa.String(500), nullable=False),
        sa.Column('original_url', sa.Text(), nullable=True),
        sa.Column('thumbnail_url', sa.Text(), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),
        sa.Column('overall_score', sa.Integer(), nullable=True),
        sa.Column('summary_headline', sa.Text(), nullable=True),
        sa.Column('summary_text', sa.Text(), nullable=True),
        sa.Column('metadata', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('histogram', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('composition', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('technical', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('color_aesthetic', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('clicking_tips', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('editing_tips', postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column('improvement_shot_url', sa.Text(), nullable=True),
        sa.Column('improvement_shot_explanation', sa.Text(), nullable=True),
        sa.Column('improvement_shot_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_analyses_user_created', 'analyses', ['user_id', 'created_at'])
    op.create_index('ix_analyses_user_status', 'analyses', ['user_id', 'status'])


def downgrade() -> None:
    # Drop in reverse dependency order
    op.drop_index('ix_analyses_user_status', table_name='analyses')
    op.drop_index('ix_analyses_user_created', table_name='analyses')
    op.drop_table('analyses')

    op.drop_index('ix_password_resets_token', table_name='password_resets')
    op.drop_table('password_resets')

    op.drop_index('ix_email_verifications_token', table_name='email_verifications')
    op.drop_table('email_verifications')

    op.drop_index('ix_users_email', table_name='users')
    op.drop_table('users')
