"""Add genes table and ClinVar enrichment columns to snps.

Revision ID: 020_genes_clinvar
Revises: 019_fk_indexes_constraints
Create Date: 2026-02-27
"""

import sqlalchemy as sa
from alembic import op

revision = "020_genes_clinvar"
down_revision = "019_fk_indexes_constraints"
branch_labels = None
depends_on = None


def upgrade():
    # ── 1. Create genes table ─────────────────────────────────────────────
    op.create_table(
        "genes",
        sa.Column("symbol", sa.String(50), primary_key=True),
        sa.Column("name", sa.String(255), nullable=True),
        sa.Column("summary", sa.Text, nullable=True),
        sa.Column("ncbi_gene_id", sa.Integer, nullable=True),
        sa.Column("omim_number", sa.String(20), nullable=True),
        sa.Column("clinvar_total_variants", sa.Integer, nullable=True),
        sa.Column("clinvar_pathogenic_count", sa.Integer, nullable=True),
        sa.Column("clinvar_uncertain_count", sa.Integer, nullable=True),
        sa.Column("clinvar_conflicting_count", sa.Integer, nullable=True),
        sa.Column("clinvar_total_submissions", sa.Integer, nullable=True),
    )

    # ── 2. Add ClinVar enrichment columns to snps ─────────────────────────
    op.add_column("snps", sa.Column("clinvar_submitter_count", sa.Integer, nullable=True))
    op.add_column("snps", sa.Column("clinvar_citation_count", sa.Integer, nullable=True))
    op.add_column("snps", sa.Column("clinvar_pmids", sa.Text, nullable=True))


def downgrade():
    op.drop_column("snps", "clinvar_pmids")
    op.drop_column("snps", "clinvar_citation_count")
    op.drop_column("snps", "clinvar_submitter_count")
    op.drop_table("genes")
