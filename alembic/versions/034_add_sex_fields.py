"""Add inferred_sex to analyses and target_sex to prs_scores.

inferred_sex: biological sex inferred from chrX heterozygosity at parse time.
target_sex: restricts a PRS score to a specific sex ('male'/'female'). NULL = applicable to all.

Revision ID: 034
Revises: 033
"""

import sqlalchemy as sa
from alembic import op

revision = "034"
down_revision = "033"


def upgrade() -> None:
    op.add_column(
        "analyses",
        sa.Column("inferred_sex", sa.String(10), nullable=True),
    )
    op.add_column(
        "prs_scores",
        sa.Column("target_sex", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("analyses", "inferred_sex")
    op.drop_column("prs_scores", "target_sex")
