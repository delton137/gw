"""Add ancestry detection columns to analyses table.

Revision ID: 005_ancestry
Revises: 004_confidence
Create Date: 2026-02-25

Note: Columns now included in 000_create_base_tables. Kept as no-op.
"""

from alembic import op
import sqlalchemy as sa

revision = "005_ancestry"
down_revision = "004_confidence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
