"""Add pharmacogenomics tables for star allele / diplotype inference.

Revision ID: 010_pgx_tables
Revises: 009_file_format
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "010_pgx_tables"
down_revision = "009_file_format"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pgx_gene_definitions",
        sa.Column("gene", sa.String(20), primary_key=True),
        sa.Column("calling_method", sa.String(20), nullable=False),
        sa.Column("tier", sa.Integer, nullable=False),
        sa.Column("default_allele", sa.String(10), nullable=False, server_default="*1"),
        sa.Column("description", sa.Text),
    )

    op.create_table(
        "pgx_star_allele_definitions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("gene", sa.String(20), nullable=False),
        sa.Column("star_allele", sa.String(20), nullable=False),
        sa.Column("rsid", sa.String(20), nullable=False),
        sa.Column("variant_allele", sa.String(10), nullable=False),
        sa.Column("function", sa.String(30), nullable=False),
        sa.Column("activity_score", sa.Float),
        sa.Column("clinical_significance", sa.Text),
        sa.Column("source", sa.String(50)),
    )
    op.create_index("ix_pgx_star_rsid", "pgx_star_allele_definitions", ["rsid"])
    op.create_index("ix_pgx_star_gene_allele", "pgx_star_allele_definitions", ["gene", "star_allele"])

    op.create_table(
        "pgx_diplotype_phenotypes",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("gene", sa.String(20), nullable=False),
        sa.Column("function_pair", sa.String(60), nullable=False),
        sa.Column("phenotype", sa.String(50), nullable=False),
        sa.Column("description", sa.Text),
    )
    op.create_index("ix_pgx_diplo_gene", "pgx_diplotype_phenotypes", ["gene"])

    op.create_table(
        "user_pgx_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("analysis_id", UUID(as_uuid=True), nullable=False),
        sa.Column("gene", sa.String(20), nullable=False),
        sa.Column("diplotype", sa.String(40), nullable=False),
        sa.Column("allele1", sa.String(20), nullable=False),
        sa.Column("allele2", sa.String(20), nullable=False),
        sa.Column("allele1_function", sa.String(30), nullable=False),
        sa.Column("allele2_function", sa.String(30), nullable=False),
        sa.Column("phenotype", sa.String(50), nullable=False),
        sa.Column("activity_score", sa.Float),
        sa.Column("n_variants_tested", sa.Integer, nullable=False),
        sa.Column("n_variants_total", sa.Integer, nullable=False),
        sa.Column("calling_method", sa.String(20), nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("drugs_affected", sa.Text),
        sa.Column("clinical_note", sa.Text),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_user_pgx_user_analysis", "user_pgx_results", ["user_id", "analysis_id"])


def downgrade() -> None:
    op.drop_table("user_pgx_results")
    op.drop_table("pgx_diplotype_phenotypes")
    op.drop_table("pgx_star_allele_definitions")
    op.drop_table("pgx_gene_definitions")
