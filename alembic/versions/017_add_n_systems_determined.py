"""Add n_systems_determined column to blood type results.

Revision ID: 017_n_systems
Revises: 016_update_blood_type
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa

revision = "017_n_systems"
down_revision = "016_update_blood_type"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "user_blood_type_results",
        sa.Column("n_systems_determined", sa.Integer, nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("user_blood_type_results", "n_systems_determined")
