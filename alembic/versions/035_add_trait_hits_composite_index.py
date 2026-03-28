"""Add composite index on user_snp_trait_hits(user_id, analysis_id).

Revision ID: 035
Revises: 034
Create Date: 2026-03-26
"""

from alembic import op

revision = "035"
down_revision = "034"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_user_snp_trait_user_analysis",
        "user_snp_trait_hits",
        ["user_id", "analysis_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_snp_trait_user_analysis", table_name="user_snp_trait_hits")
