"""Add prs_trait_metadata table for absolute risk conversion.

Revision ID: 003_traitmeta
Revises: 002_prevalence
Create Date: 2026-02-25

Note: Table now included in 000_create_base_tables. Kept as no-op.
"""

from alembic import op
import sqlalchemy as sa

revision = "003_traitmeta"
down_revision = "002_prevalence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
