"""Add pipeline_fast_seconds column to analyses.

Revision ID: 026
Revises: 025
"""

import sqlalchemy as sa
from alembic import op

revision = "026"
down_revision = "025"


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column("pipeline_fast_seconds", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analyses", "pipeline_fast_seconds")
