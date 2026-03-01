"""Add status_detail column to analyses table.

Revision ID: 015_status_detail
Revises: 014_add_selected_ancestry
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa

revision = "015_status_detail"
down_revision = "014_selected_ancestry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("analyses", sa.Column("status_detail", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "status_detail")
