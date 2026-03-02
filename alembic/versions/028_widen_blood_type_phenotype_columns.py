"""Widen blood type phenotype columns from VARCHAR(100) to TEXT.

RBCeq2 phenotype strings can far exceed 100 characters (MNS up to ~482,
Kell ~211, Kidd ~166, Duffy ~148), causing StringDataRightTruncationError.

VARCHAR→TEXT is metadata-only in PostgreSQL (no table rewrite).

Revision ID: 028
Revises: 027
"""

import sqlalchemy as sa
from alembic import op

revision = "028"
down_revision = "027"


def upgrade() -> None:
    for col in ("kell_phenotype", "mns_phenotype", "duffy_phenotype", "kidd_phenotype", "secretor_status"):
        op.alter_column("user_blood_type_results", col, type_=sa.Text(), existing_type=sa.String(100))


def downgrade() -> None:
    for col in ("kell_phenotype", "mns_phenotype", "duffy_phenotype", "kidd_phenotype", "secretor_status"):
        op.alter_column("user_blood_type_results", col, type_=sa.String(100), existing_type=sa.Text())
