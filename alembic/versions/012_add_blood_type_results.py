"""Add user_blood_type_results table for blood type determination.

Revision ID: 012_blood_type
Revises: 011_pgx_guidelines
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "012_blood_type"
down_revision = "011_pgx_guidelines"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_blood_type_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("analysis_id", UUID(as_uuid=True), nullable=False),
        # ABO
        sa.Column("abo_genotype", sa.String(10), nullable=False),
        sa.Column("abo_phenotype", sa.String(5), nullable=False),
        # Rh
        sa.Column("rh_c_antigen", sa.String(5), nullable=True),
        sa.Column("rh_e_antigen", sa.String(5), nullable=True),
        sa.Column("rh_cw_antigen", sa.Boolean, nullable=True),
        # Extended systems
        sa.Column("kell_phenotype", sa.String(10), nullable=True),
        sa.Column("mns_phenotype", sa.String(15), nullable=True),
        sa.Column("duffy_phenotype", sa.String(15), nullable=True),
        sa.Column("kidd_phenotype", sa.String(10), nullable=True),
        sa.Column("secretor_status", sa.String(15), nullable=True),
        # Summary
        sa.Column("display_type", sa.String(10), nullable=False),
        # Confidence
        sa.Column("n_variants_tested", sa.Integer, nullable=False),
        sa.Column("n_variants_total", sa.Integer, nullable=False),
        sa.Column("confidence", sa.String(10), nullable=False),
        sa.Column("confidence_note", sa.Text, nullable=True),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_bt_user_analysis", "user_blood_type_results", ["user_id", "analysis_id"])


def downgrade() -> None:
    op.drop_index("ix_user_bt_user_analysis")
    op.drop_table("user_blood_type_results")
