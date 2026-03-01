import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSON, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class Analysis(Base):
    __tablename__ = "analyses"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[str] = mapped_column(String(255), index=True)  # Clerk user ID
    chip_type: Mapped[str | None] = mapped_column(String(50))
    variant_count: Mapped[int | None] = mapped_column(Integer)
    status: Mapped[str] = mapped_column(String(20), default="pending")
    error_message: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    detected_ancestry: Mapped[dict | None] = mapped_column(JSON)  # {"EUR": 0.78, ...}
    ancestry_method: Mapped[str | None] = mapped_column(String(20))  # "auto" | "manual" | "auto_fallback"
    ancestry_confidence: Mapped[float | None] = mapped_column(Float)
    genome_build: Mapped[str | None] = mapped_column(String(10))  # "GRCh37" | "GRCh38"
    filename: Mapped[str | None] = mapped_column(String(255))  # original upload filename
    file_format: Mapped[str | None] = mapped_column(String(20))  # "23andme" | "ancestrydna" | "vcf"
    selected_ancestry: Mapped[str | None] = mapped_column(String(3))  # "EUR" | "AFR" | "EAS" | "SAS" | "AMR"
    status_detail: Mapped[str | None] = mapped_column(Text)  # human-readable progress message

    # Relationships to child tables (CASCADE handled at DB level)
    prs_results: Mapped[list["PrsResult"]] = relationship(back_populates="analysis", cascade="all, delete-orphan", passive_deletes=True)
    trait_hits: Mapped[list["UserSnpTraitHit"]] = relationship(back_populates="analysis", cascade="all, delete-orphan", passive_deletes=True)
    variants: Mapped[list["UserVariant"]] = relationship(back_populates="analysis", cascade="all, delete-orphan", passive_deletes=True)
    clinvar_hits: Mapped[list["UserClinvarHit"]] = relationship(back_populates="analysis", cascade="all, delete-orphan", passive_deletes=True)


class PrsResult(Base):
    __tablename__ = "prs_results"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[str] = mapped_column(String(255), index=True)  # Clerk user ID
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"))
    pgs_id: Mapped[str] = mapped_column(String(20), ForeignKey("prs_scores.pgs_id", ondelete="CASCADE"))
    raw_score: Mapped[float] = mapped_column(Float)
    percentile: Mapped[float] = mapped_column(Float)
    z_score: Mapped[float | None] = mapped_column(Float)
    ref_mean: Mapped[float | None] = mapped_column(Float)
    ref_std: Mapped[float | None] = mapped_column(Float)
    ancestry_group_used: Mapped[str] = mapped_column(String(3))
    n_variants_matched: Mapped[int] = mapped_column(Integer)
    n_variants_total: Mapped[int] = mapped_column(Integer)
    percentile_lower: Mapped[float | None] = mapped_column(Float)
    percentile_upper: Mapped[float | None] = mapped_column(Float)
    coverage_quality: Mapped[str | None] = mapped_column(String(10))  # high/medium/low
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    analysis: Mapped["Analysis"] = relationship(back_populates="prs_results")


class UserSnpTraitHit(Base):
    __tablename__ = "user_snp_trait_hits"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[str] = mapped_column(String(255), index=True)  # Clerk user ID
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"))
    rsid: Mapped[str] = mapped_column(String(20))
    user_genotype: Mapped[str] = mapped_column(String(2))
    trait: Mapped[str] = mapped_column(String(255))
    effect_description: Mapped[str | None] = mapped_column(Text)
    risk_level: Mapped[str] = mapped_column(String(20))  # increased/moderate/typical
    evidence_level: Mapped[str] = mapped_column(String(10))
    association_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("snp_trait_associations.id", ondelete="CASCADE"))

    analysis: Mapped["Analysis"] = relationship(back_populates="trait_hits")


class UserVariant(Base):
    """Stores which SNPedia-listed rsids a user has in their genotype file."""
    __tablename__ = "user_variants"
    __table_args__ = (
        Index("ix_user_variants_user_analysis", "user_id", "analysis_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"))
    rsid: Mapped[str] = mapped_column(String(20))

    analysis: Mapped["Analysis"] = relationship(back_populates="variants")


class UserClinvarHit(Base):
    """Stores user variants that have ClinVar annotations (joined at read time)."""
    __tablename__ = "user_clinvar_hits"
    __table_args__ = (
        Index("ix_user_clinvar_user_analysis", "user_id", "analysis_id"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"))
    rsid: Mapped[str] = mapped_column(String(20))
    user_genotype: Mapped[str] = mapped_column(String(10))

    analysis: Mapped["Analysis"] = relationship(back_populates="clinvar_hits")
