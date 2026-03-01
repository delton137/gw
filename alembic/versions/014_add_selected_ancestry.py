"""Add selected_ancestry column to analyses table.

Revision ID: 014_selected_ancestry
Revises: 013_hla
"""

from alembic import op
import sqlalchemy as sa

revision = "014_selected_ancestry"
down_revision = "013_hla"


def upgrade() -> None:
    op.add_column("analyses", sa.Column("selected_ancestry", sa.String(3), nullable=True))


def downgrade() -> None:
    op.drop_column("analyses", "selected_ancestry")
