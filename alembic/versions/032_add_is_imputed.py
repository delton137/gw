"""Add is_imputed column to analyses.

Revision ID: 032
Revises: 031
"""

from alembic import op
import sqlalchemy as sa

revision = "032"
down_revision = "031"


def upgrade() -> None:
    op.add_column("analyses", sa.Column("is_imputed", sa.Boolean(), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "is_imputed")
