"""Add publication_doi column to prs_scores.

Revision ID: 025
Revises: 024
"""

import sqlalchemy as sa
from alembic import op

revision = "025"
down_revision = "024"


def upgrade() -> None:
    op.add_column(
        "prs_scores",
        sa.Column("publication_doi", sa.String(100), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("prs_scores", "publication_doi")
