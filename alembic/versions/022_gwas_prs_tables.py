"""Add GWAS-hit PRS tables for curated GWAS study scores.

Revision ID: 022_gwas_prs_tables
Revises: 021_user_clinvar_hits
Create Date: 2026-02-28
"""

import sqlalchemy as sa
from alembic import op

revision = "022_gwas_prs_tables"
down_revision = "021_user_clinvar_hits"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # --- gwas_studies ---
    op.create_table(
        "gwas_studies",
        sa.Column("study_id", sa.String(30), primary_key=True),
        sa.Column("trait", sa.String(255), nullable=False),
        sa.Column("reported_trait", sa.String(500)),
        sa.Column("category", sa.String(50)),
        sa.Column("citation", sa.String(500)),
        sa.Column("pmid", sa.String(20)),
        sa.Column("n_snps", sa.Integer),
        sa.Column("value_type", sa.String(10)),
    )

    # --- gwas_associations ---
    op.create_table(
        "gwas_associations",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column(
            "study_id",
            sa.String(30),
            sa.ForeignKey("gwas_studies.study_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("rsid", sa.String(20), nullable=False),
        sa.Column("chrom", sa.String(2)),
        sa.Column("position", sa.Integer),
        sa.Column("position_grch38", sa.Integer),
        sa.Column("risk_allele", sa.String(255), nullable=False),
        sa.Column("beta", sa.Float, nullable=False),
        sa.Column("risk_allele_frequency", sa.Float),
        sa.Column("p_value", sa.Float),
        sa.Column("eur_af", sa.Float),
        sa.Column("afr_af", sa.Float),
        sa.Column("eas_af", sa.Float),
        sa.Column("sas_af", sa.Float),
        sa.Column("amr_af", sa.Float),
    )
    op.create_index(
        "ix_gwas_assoc_study_rsid", "gwas_associations", ["study_id", "rsid"]
    )

    # --- gwas_reference_distributions ---
    op.create_table(
        "gwas_reference_distributions",
        sa.Column(
            "study_id",
            sa.String(30),
            sa.ForeignKey("gwas_studies.study_id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("ancestry_group", sa.String(3), primary_key=True),
        sa.Column("mean", sa.Float, nullable=False),
        sa.Column("std", sa.Float, nullable=False),
    )

    # --- gwas_prs_results ---
    op.create_table(
        "gwas_prs_results",
        sa.Column(
            "id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            primary_key=True,
            server_default=sa.text("gen_random_uuid()"),
        ),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column(
            "analysis_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "study_id",
            sa.String(30),
            sa.ForeignKey("gwas_studies.study_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("raw_score", sa.Float),
        sa.Column("percentile", sa.Float),
        sa.Column("z_score", sa.Float),
        sa.Column("ref_mean", sa.Float),
        sa.Column("ref_std", sa.Float),
        sa.Column("ancestry_group_used", sa.String(3)),
        sa.Column("n_variants_matched", sa.Integer),
        sa.Column("n_variants_total", sa.Integer),
    )
    op.create_index(
        "ix_gwas_prs_user_analysis", "gwas_prs_results", ["user_id", "analysis_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_gwas_prs_user_analysis", table_name="gwas_prs_results")
    op.drop_table("gwas_prs_results")
    op.drop_table("gwas_reference_distributions")
    op.drop_index("ix_gwas_assoc_study_rsid", table_name="gwas_associations")
    op.drop_table("gwas_associations")
    op.drop_table("gwas_studies")
