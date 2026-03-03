"""Add effect_summary column to snp_trait_associations.

Short curated label (e.g. "Higher Alzheimer's risk", "Blue eyes")
for display in the My SNPs table instead of generic risk_level badges.

Revision ID: 029
Revises: 028
"""

import sqlalchemy as sa
from alembic import op

revision = "029"
down_revision = "028"


def upgrade() -> None:
    op.add_column(
        "snp_trait_associations",
        sa.Column("effect_summary", sa.String(120), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("snp_trait_associations", "effect_summary")
