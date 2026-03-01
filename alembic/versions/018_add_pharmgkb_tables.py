"""Add PharmGKB clinical annotations, allele phenotypes, and FDA labels tables.

Revision ID: 018_pharmgkb_tables
Revises: 017_n_systems
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa

revision = "018_pharmgkb_tables"
down_revision = "017_n_systems"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pgx_clinical_annotations",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pharmgkb_id", sa.String(20), nullable=False),
        sa.Column("gene", sa.String(20), nullable=False),
        sa.Column("drug_name", sa.String(200), nullable=False),
        sa.Column("drug_pharmgkb_id", sa.String(20), nullable=True),
        sa.Column("evidence_level", sa.String(5), nullable=False),
        sa.Column("evidence_mapped", sa.String(10), nullable=False),
        sa.Column("location_display", sa.Text(), nullable=True),
    )
    op.create_index("ix_pgx_ca_pharmgkb_id", "pgx_clinical_annotations", ["pharmgkb_id"])
    op.create_index("ix_pgx_ca_gene", "pgx_clinical_annotations", ["gene"])
    op.create_index("ix_pgx_ca_gene_drug", "pgx_clinical_annotations", ["gene", "drug_name"])
    op.create_index("ix_pgx_ca_evidence", "pgx_clinical_annotations", ["evidence_level"])

    op.create_table(
        "pgx_allele_phenotypes",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("annotation_id", sa.Integer(), nullable=False),
        sa.Column("gene", sa.String(20), nullable=False),
        sa.Column("allele", sa.Text(), nullable=False),
        sa.Column("phenotype_text", sa.Text(), nullable=False),
    )
    op.create_index("ix_pgx_ap_annotation", "pgx_allele_phenotypes", ["annotation_id"])
    op.create_index("ix_pgx_ap_gene_allele", "pgx_allele_phenotypes", ["gene", "allele"])

    op.create_table(
        "pgx_fda_labels",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pharmgkb_id", sa.String(20), nullable=False),
        sa.Column("gene", sa.String(20), nullable=False),
        sa.Column("drug_name", sa.String(200), nullable=False),
        sa.Column("label_name", sa.Text(), nullable=False),
    )
    op.create_index("ix_pgx_fda_pharmgkb_id", "pgx_fda_labels", ["pharmgkb_id"])
    op.create_index("ix_pgx_fda_gene", "pgx_fda_labels", ["gene"])


def downgrade() -> None:
    op.drop_table("pgx_fda_labels")
    op.drop_table("pgx_allele_phenotypes")
    op.drop_table("pgx_clinical_annotations")
