"""Add HLA genotyping tables.

Revision ID: 013_hla
Revises: 012_blood_type
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "013_hla"
down_revision = "012_blood_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "hla_allele_definitions",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("gene", sa.String(20), nullable=False),
        sa.Column("allele", sa.String(30), nullable=False),
        sa.Column("g_group", sa.String(30), nullable=True),
        sa.Column("sequence_length", sa.Integer, nullable=False, server_default="0"),
        sa.Column("freq_eur", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("freq_afr", sa.Float, nullable=False, server_default="0.0"),
        sa.Column("freq_eas", sa.Float, nullable=False, server_default="0.0"),
    )
    op.create_index("ix_hla_allele_gene", "hla_allele_definitions", ["gene"])

    op.create_table(
        "user_hla_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(255), nullable=False),
        sa.Column("analysis_id", UUID(as_uuid=True), nullable=False),
        sa.Column("gene", sa.String(20), nullable=False),
        sa.Column("allele1", sa.String(30), nullable=False),
        sa.Column("allele2", sa.String(30), nullable=False),
        sa.Column("resolution", sa.String(10), nullable=False),
        sa.Column("score", sa.Float, nullable=True),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("method", sa.String(30), nullable=False),
        sa.Column("n_variants_in_gene", sa.Integer, nullable=False, server_default="0"),
        sa.Column("n_exonic_variants", sa.Integer, nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_hla_user_id", "user_hla_results", ["user_id"])
    op.create_index("ix_user_hla_user_analysis", "user_hla_results", ["user_id", "analysis_id"])


def downgrade() -> None:
    op.drop_table("user_hla_results")
    op.drop_table("hla_allele_definitions")
