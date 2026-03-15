"""Add email_subscribers table.

Revision ID: 031
Revises: 030
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "031"
down_revision = "030"


def upgrade() -> None:
    op.create_table(
        "email_subscribers",
        sa.Column("id", UUID(as_uuid=True), server_default=sa.text("gen_random_uuid()"), primary_key=True),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
    )
    op.create_index("ix_email_subscribers_email", "email_subscribers", ["email"], unique=True)


def downgrade() -> None:
    op.drop_index("ix_email_subscribers_email", table_name="email_subscribers")
    op.drop_table("email_subscribers")
