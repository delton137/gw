"""Add user_clinvar_hits table for ClinVar cross-referencing in pipeline.

Revision ID: 021_user_clinvar_hits
Revises: 020_genes_clinvar
Create Date: 2026-02-27
"""

import sqlalchemy as sa
from alembic import op

revision = "021_user_clinvar_hits"
down_revision = "020_genes_clinvar"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_clinvar_hits",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column(
            "analysis_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rsid", sa.String(20), nullable=False),
        sa.Column("user_genotype", sa.String(10), nullable=False),
    )
    op.create_index(
        "ix_user_clinvar_user_analysis",
        "user_clinvar_hits",
        ["user_id", "analysis_id"],
    )


def downgrade() -> None:
    op.drop_index("ix_user_clinvar_user_analysis", table_name="user_clinvar_hits")
    op.drop_table("user_clinvar_hits")
