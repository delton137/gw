"""Add confidence interval and coverage quality columns to prs_results.

Revision ID: 004_confidence
Revises: 003_traitmeta
Create Date: 2026-02-25

Note: Columns now included in 000_create_base_tables. Kept as no-op.
"""

from alembic import op
import sqlalchemy as sa

revision = "004_confidence"
down_revision = "003_traitmeta"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
