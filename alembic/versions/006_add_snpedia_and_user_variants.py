"""Add snpedia_snps lookup table and user_variants table.

Revision ID: 006_snpedia_variants
Revises: 005_ancestry
Create Date: 2026-02-25

Note: Tables now included in 000_create_base_tables. Kept as no-op.
"""

from alembic import op
import sqlalchemy as sa

revision = "006_snpedia_variants"
down_revision = "005_ancestry"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
