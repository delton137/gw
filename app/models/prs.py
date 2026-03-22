from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PrsScore(Base):
    __tablename__ = "prs_scores"

    pgs_id: Mapped[str] = mapped_column(String(20), primary_key=True)
    trait_name: Mapped[str] = mapped_column(String(255))
    trait_efo_id: Mapped[str | None] = mapped_column(String(50))
    publication_pmid: Mapped[str | None] = mapped_column(String(20))
    publication_doi: Mapped[str | None] = mapped_column(String(100))
    n_variants_total: Mapped[int] = mapped_column(Integer)
    n_variants_on_chip: Mapped[int | None] = mapped_column(Integer)
    development_ancestry: Mapped[str | None] = mapped_column(String(255))
    validation_ancestry: Mapped[str | None] = mapped_column(String(255))
    reported_auc: Mapped[float | None] = mapped_column(Float)
    scoring_file_hash: Mapped[str | None] = mapped_column(String(64))  # SHA-256 hex
    scoring_file_date: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )


class PrsVariantWeight(Base):
    __tablename__ = "prs_variant_weights"
    __table_args__ = (Index("ix_prs_weights_pgs_rsid", "pgs_id", "rsid"),)

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pgs_id: Mapped[str] = mapped_column(String(20), ForeignKey("prs_scores.pgs_id", ondelete="CASCADE"))
    rsid: Mapped[str] = mapped_column(String(20))
    chrom: Mapped[str] = mapped_column(String(2))
    position: Mapped[int] = mapped_column(Integer)  # GRCh37
    position_grch38: Mapped[int | None] = mapped_column(Integer)
    effect_allele: Mapped[str] = mapped_column(String(255))
    weight: Mapped[float] = mapped_column(Float)
    # Per-ancestry effect allele frequencies (1000 Genomes Phase 3)
    eur_af: Mapped[float | None] = mapped_column(Float)
    afr_af: Mapped[float | None] = mapped_column(Float)
    eas_af: Mapped[float | None] = mapped_column(Float)
    sas_af: Mapped[float | None] = mapped_column(Float)
    amr_af: Mapped[float | None] = mapped_column(Float)
    # True if effect_allele == VCF ALT (determined during 1000G AF loading)
    # False if effect_allele == VCF REF. Used for VCF imputation.
    effect_is_alt: Mapped[bool | None] = mapped_column(Boolean)


class PrsTraitMetadata(Base):
    """Metadata about a PRS trait needed for absolute risk conversion."""
    __tablename__ = "prs_trait_metadata"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pgs_id: Mapped[str] = mapped_column(String(20), ForeignKey("prs_scores.pgs_id", ondelete="CASCADE"), unique=True)
    trait_type: Mapped[str] = mapped_column(String(20))  # binary or continuous
    prevalence: Mapped[float | None] = mapped_column(Float)  # population prevalence (0-1)
    population_mean: Mapped[float | None] = mapped_column(Float)  # for continuous traits
    population_std: Mapped[float | None] = mapped_column(Float)  # for continuous traits
    source: Mapped[str | None] = mapped_column(String(255))  # where the metadata came from


class PrsReferenceDistribution(Base):
    __tablename__ = "prs_reference_distributions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    pgs_id: Mapped[str] = mapped_column(String(20), ForeignKey("prs_scores.pgs_id", ondelete="CASCADE"))
    ancestry_group: Mapped[str] = mapped_column(String(3))  # EUR, AFR, EAS, SAS, AMR
    mean: Mapped[float] = mapped_column(Float)
    std: Mapped[float] = mapped_column(Float)
    percentiles_json: Mapped[dict | None] = mapped_column(JSON)
