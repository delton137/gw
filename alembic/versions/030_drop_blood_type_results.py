"""Drop user_blood_type_results table.

Blood typing removed — unreliable on DTC microarray data (~9% ABO error rate,
zero validation for extended systems). See TO_FIX.md for details.

Revision ID: 030
Revises: 029
"""

from alembic import op

revision = "030"
down_revision = "029"


def upgrade() -> None:
    op.drop_table("user_blood_type_results")


def downgrade() -> None:
    # Table recreation omitted — blood typing feature fully removed.
    # Restore from migration 012 + 016 + 017 + 028 if needed.
    pass
