"""Drop HLA tables — HLA tag SNP screening moved to SNP trait associations.

Revision ID: 023_drop_hla_tables
Revises: 022_gwas_prs_tables
Create Date: 2026-02-28
"""

import sqlalchemy as sa
from alembic import op

revision = "023_drop_hla_tables"
down_revision = "022_gwas_prs_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("user_hla_results")
    op.drop_table("hla_allele_definitions")


def downgrade() -> None:
    op.create_table(
        "hla_allele_definitions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("gene", sa.String(20), nullable=False),
        sa.Column("allele", sa.String(30), nullable=False),
        sa.Column("g_group", sa.String(30), nullable=True),
        sa.Column("sequence_length", sa.Integer(), nullable=True),
        sa.Column("freq_eur", sa.Float(), nullable=True),
        sa.Column("freq_afr", sa.Float(), nullable=True),
        sa.Column("freq_eas", sa.Float(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_hla_allele_gene", "hla_allele_definitions", ["gene"])

    op.create_table(
        "user_hla_results",
        sa.Column("id", sa.UUID(), nullable=False),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("analysis_id", sa.UUID(), nullable=False),
        sa.Column("gene", sa.String(20), nullable=False),
        sa.Column("allele1", sa.String(30), nullable=True),
        sa.Column("allele2", sa.String(30), nullable=True),
        sa.Column("resolution", sa.String(10), nullable=True),
        sa.Column("score", sa.Float(), nullable=True),
        sa.Column("confidence", sa.String(10), nullable=True),
        sa.Column("method", sa.String(30), nullable=True),
        sa.Column("n_variants_in_gene", sa.Integer(), nullable=True),
        sa.Column("n_exonic_variants", sa.Integer(), nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["analysis_id"], ["analyses.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_user_hla_user_analysis", "user_hla_results", ["user_id", "analysis_id"])
