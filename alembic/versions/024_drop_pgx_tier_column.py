"""Drop tier column from pgx_gene_definitions.

Revision ID: 024
Revises: 023_drop_hla_tables
"""

import sqlalchemy as sa
from alembic import op

revision = "024"
down_revision = "023_drop_hla_tables"


def upgrade() -> None:
    op.drop_column("pgx_gene_definitions", "tier")


def downgrade() -> None:
    op.add_column(
        "pgx_gene_definitions",
        sa.Column("tier", sa.Integer, nullable=True),
    )
