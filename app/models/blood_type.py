"""Blood type determination models."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class UserBloodTypeResult(Base):
    """Per-user blood type result from a single analysis."""

    __tablename__ = "user_blood_type_results"
    __table_args__ = (
        Index("ix_user_bt_user_analysis", "user_id", "analysis_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"))

    # ABO
    abo_genotype: Mapped[str] = mapped_column(String(100))  # ISBT: "ABO*A1.01/ABO*O.01.01"
    abo_phenotype: Mapped[str] = mapped_column(String(5))   # "A", "B", "AB", "O"

    # Rh
    rh_c_antigen: Mapped[str | None] = mapped_column(String(5))  # "C/c", "c/c", etc.
    rh_e_antigen: Mapped[str | None] = mapped_column(String(5))  # "E/e", "e/e", etc.
    rh_cw_antigen: Mapped[bool | None] = mapped_column(Boolean)

    # Extended systems (widened for RBCeq2 phenotype strings)
    kell_phenotype: Mapped[str | None] = mapped_column(String(100))
    mns_phenotype: Mapped[str | None] = mapped_column(String(100))
    duffy_phenotype: Mapped[str | None] = mapped_column(String(100))
    kidd_phenotype: Mapped[str | None] = mapped_column(String(100))
    secretor_status: Mapped[str | None] = mapped_column(String(100))

    # Summary
    display_type: Mapped[str] = mapped_column(String(10))  # "A", "O", "AB"

    # All determined systems — JSON dict of system → {genotype, phenotype}
    systems_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)

    # Confidence
    n_variants_tested: Mapped[int] = mapped_column(Integer)
    n_variants_total: Mapped[int] = mapped_column(Integer)
    n_systems_determined: Mapped[int] = mapped_column(Integer, default=0)
    confidence: Mapped[str] = mapped_column(String(10))  # high / medium / low
    confidence_note: Mapped[str | None] = mapped_column(Text)

    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
