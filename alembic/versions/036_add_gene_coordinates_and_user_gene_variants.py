"""Add gene coordinate columns and user_gene_variants + user_gene_coverage tables.

Revision ID: 036
Revises: 035
Create Date: 2026-03-29
"""

import sqlalchemy as sa
from alembic import op

revision = "036"
down_revision = "035"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Add coordinate columns to genes table
    op.add_column("genes", sa.Column("chrom", sa.String(5), nullable=True))
    op.add_column("genes", sa.Column("start_position_grch37", sa.Integer(), nullable=True))
    op.add_column("genes", sa.Column("end_position_grch37", sa.Integer(), nullable=True))
    op.add_column("genes", sa.Column("start_position_grch38", sa.Integer(), nullable=True))
    op.add_column("genes", sa.Column("end_position_grch38", sa.Integer(), nullable=True))

    # user_gene_variants — individual non-ref variants per gene
    op.create_table(
        "user_gene_variants",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column(
            "analysis_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gene", sa.String(50), nullable=False),
        sa.Column("rsid", sa.String(20), nullable=True),
        sa.Column("chrom", sa.String(5), nullable=True),
        sa.Column("position", sa.Integer(), nullable=True),
        sa.Column("user_genotype", sa.String(10), nullable=False),
    )
    op.create_index(
        "ix_user_gene_variants_user_analysis",
        "user_gene_variants",
        ["user_id", "analysis_id"],
    )
    op.create_index(
        "ix_user_gene_variants_user_analysis_gene",
        "user_gene_variants",
        ["user_id", "analysis_id", "gene"],
    )

    # user_gene_coverage — per-gene coverage summary
    op.create_table(
        "user_gene_coverage",
        sa.Column("id", sa.Integer(), autoincrement=True, primary_key=True),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column(
            "analysis_id",
            sa.dialects.postgresql.UUID(as_uuid=True),
            sa.ForeignKey("analyses.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("gene", sa.String(50), nullable=False),
        sa.Column("total_variants_tested", sa.Integer(), nullable=False),
        sa.Column("non_reference_count", sa.Integer(), nullable=False),
    )
    op.create_index(
        "ix_user_gene_coverage_user_analysis_gene",
        "user_gene_coverage",
        ["user_id", "analysis_id", "gene"],
    )


def downgrade() -> None:
    op.drop_table("user_gene_coverage")
    op.drop_table("user_gene_variants")
    op.drop_column("genes", "end_position_grch38")
    op.drop_column("genes", "start_position_grch38")
    op.drop_column("genes", "end_position_grch37")
    op.drop_column("genes", "start_position_grch37")
    op.drop_column("genes", "chrom")
