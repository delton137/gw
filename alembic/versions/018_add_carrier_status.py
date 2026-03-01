"""Add user_carrier_status_results table for carrier screening.

Revision ID: 018_carrier_status
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "018_carrier_status"
down_revision = "018_pharmgkb_tables"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "user_carrier_status_results",
        sa.Column("id", UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", sa.String(255), nullable=False, index=True),
        sa.Column("analysis_id", UUID(as_uuid=True), nullable=False),
        sa.Column("results_json", sa.JSON, nullable=False),
        sa.Column("n_genes_screened", sa.Integer, nullable=False),
        sa.Column("n_carrier_genes", sa.Integer, nullable=False),
        sa.Column("n_affected_flags", sa.Integer, nullable=False, server_default="0"),
        sa.Column("computed_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_user_cs_user_analysis", "user_carrier_status_results", ["user_id", "analysis_id"])


def downgrade() -> None:
    op.drop_index("ix_user_cs_user_analysis")
    op.drop_table("user_carrier_status_results")
