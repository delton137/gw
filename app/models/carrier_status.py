"""Carrier status screening result models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserCarrierStatusResult(Base):
    """Per-user carrier status screening result from a single analysis."""

    __tablename__ = "user_carrier_status_results"
    __table_args__ = (
        Index("ix_user_cs_user_analysis", "user_id", "analysis_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"))

    # Per-gene results as JSON — see carrier_panel.json for schema
    results_json: Mapped[dict] = mapped_column(JSON, nullable=False)

    # Summary counts
    n_genes_screened: Mapped[int] = mapped_column(Integer, nullable=False)
    n_carrier_genes: Mapped[int] = mapped_column(Integer, nullable=False)
    n_affected_flags: Mapped[int] = mapped_column(Integer, nullable=False, default=0)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
