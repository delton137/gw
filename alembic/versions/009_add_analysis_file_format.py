"""Add file_format column to analyses table.

Revision ID: 009_file_format
Revises: 008_enrich_snp
Create Date: 2026-02-25
"""

from alembic import op
import sqlalchemy as sa

revision = "009_file_format"
down_revision = "008_enrich_snp"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("file_format", sa.String(20), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "file_format")
