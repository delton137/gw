"""Add variant_genotypes JSON column to user_pgx_results.

Stores per-variant genotypes ({rsid: "A/G", ...}) so the UI can display
user genotypes alongside each gene's SNP panel.

Revision ID: 027
Revises: 026
"""

import sqlalchemy as sa
from alembic import op

revision = "027"
down_revision = "026"


def upgrade() -> None:
    op.add_column(
        "user_pgx_results",
        sa.Column("variant_genotypes", sa.JSON(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_pgx_results", "variant_genotypes")
