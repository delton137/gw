"""Add scoring file version tracking to prs_scores.

Revision ID: 033
Revises: 032
"""

from alembic import op
import sqlalchemy as sa

revision = "033"
down_revision = "032"


def upgrade() -> None:
    op.add_column("prs_scores", sa.Column("scoring_file_hash", sa.String(64), nullable=True))
    op.add_column("prs_scores", sa.Column("scoring_file_date", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    op.drop_column("prs_scores", "scoring_file_date")
    op.drop_column("prs_scores", "scoring_file_hash")
