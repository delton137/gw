"""Add enriched annotation columns to snps table.

Revision ID: 008_enrich_snp
Revises: 007_filename
Create Date: 2026-02-25

Note: Columns now included in 000_create_base_tables. Kept as no-op.
"""

from alembic import op
import sqlalchemy as sa

revision = "008_enrich_snp"
down_revision = "007_filename"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
