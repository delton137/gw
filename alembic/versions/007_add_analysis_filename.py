"""Add filename column to analyses table.

Revision ID: 007_filename
Revises: 006_snpedia_variants
Create Date: 2026-02-25

Note: Column now included in 000_create_base_tables. Kept as no-op.
"""

from alembic import op
import sqlalchemy as sa

revision = "007_filename"
down_revision = "006_snpedia_variants"
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
