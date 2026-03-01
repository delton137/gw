"""Add z_score, ref_mean, ref_std to prs_results for distribution visualizations.

Revision ID: 001_distcurve
Revises: 000_base
Create Date: 2026-02-25

Note: These columns are now included in 000_create_base_tables.
This migration is kept as a no-op to preserve the migration chain.
"""

from alembic import op
import sqlalchemy as sa

revision = "001_distcurve"
down_revision = "000_base"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
