"""Add trait_prevalence to snp_trait_associations for effect size interpretation.

Revision ID: 002_prevalence
Revises: 001_distcurve
Create Date: 2026-02-25

Note: Column now included in 000_create_base_tables. Kept as no-op.
"""

from alembic import op
import sqlalchemy as sa

revision = "002_prevalence"
down_revision = "001_distcurve"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
