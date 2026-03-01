"""Widen blood type phenotype columns for RBCeq2 ISBT notation and add systems_json.

Revision ID: 016_update_blood_type
Revises: 015_status_detail
Create Date: 2026-02-26
"""

from alembic import op
import sqlalchemy as sa

revision = "016_update_blood_type"
down_revision = "015_status_detail"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Widen abo_genotype for ISBT notation (e.g. "ABO*A1.01/ABO*O.01.01")
    op.alter_column(
        "user_blood_type_results", "abo_genotype",
        type_=sa.String(100), existing_type=sa.String(10),
    )
    # Widen extended system phenotype columns for RBCeq2 phenotype strings
    for col in ("kell_phenotype", "mns_phenotype", "duffy_phenotype", "kidd_phenotype", "secretor_status"):
        op.alter_column(
            "user_blood_type_results", col,
            type_=sa.String(100), existing_type=sa.String(15),
            existing_nullable=True,
        )
    # Add systems_json for full blood group system details
    op.add_column(
        "user_blood_type_results",
        sa.Column("systems_json", sa.JSON, nullable=True),
    )


def downgrade() -> None:
    op.drop_column("user_blood_type_results", "systems_json")
    for col in ("kell_phenotype", "mns_phenotype", "duffy_phenotype", "kidd_phenotype", "secretor_status"):
        op.alter_column(
            "user_blood_type_results", col,
            type_=sa.String(15), existing_type=sa.String(100),
            existing_nullable=True,
        )
    op.alter_column(
        "user_blood_type_results", "abo_genotype",
        type_=sa.String(10), existing_type=sa.String(100),
    )
