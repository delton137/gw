"""Add pgx_drug_guidelines table for CPIC/DPWG prescribing recommendations.

Revision ID: 011_pgx_guidelines
Revises: 010_pgx_tables
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa

revision = "011_pgx_guidelines"
down_revision = "010_pgx_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pgx_drug_guidelines",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("source", sa.String(10), nullable=False),  # CPIC or DPWG
        sa.Column("gene", sa.String(20), nullable=False),
        sa.Column("drug", sa.String(100), nullable=False),
        sa.Column("lookup_type", sa.String(20), nullable=False),  # activity_score, phenotype
        sa.Column("lookup_value", sa.String(60), nullable=False),
        sa.Column("activity_score_min", sa.Float, nullable=True),
        sa.Column("activity_score_max", sa.Float, nullable=True),
        sa.Column("recommendation", sa.Text, nullable=False),
        sa.Column("implication", sa.Text, nullable=True),
        sa.Column("strength", sa.String(20), nullable=True),
        sa.Column("alternate_drug", sa.Boolean, nullable=False, server_default="false"),
        sa.Column("pmid", sa.String(20), nullable=True),
    )
    op.create_index("ix_pgx_guidelines_gene_source", "pgx_drug_guidelines", ["gene", "source"])


def downgrade() -> None:
    op.drop_index("ix_pgx_guidelines_gene_source")
    op.drop_table("pgx_drug_guidelines")
