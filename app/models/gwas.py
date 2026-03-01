"""GWAS-hit PRS models — small polygenic scores from curated GWAS studies.

Separate from the PGS Catalog PRS tables. All tables prefixed gwas_ for clarity.
This entire module can be removed without affecting the core PRS pipeline.
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Float, ForeignKey, Index, Integer, String, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base


class GwasStudy(Base):
    __tablename__ = "gwas_studies"

    study_id: Mapped[str] = mapped_column(String(30), primary_key=True)  # e.g. "GCST005195"
    trait: Mapped[str] = mapped_column(String(255), nullable=False)
    reported_trait: Mapped[str | None] = mapped_column(String(500))
    category: Mapped[str | None] = mapped_column(String(50))  # cardiovascular, cancer, etc.
    citation: Mapped[str | None] = mapped_column(String(500))
    pmid: Mapped[str | None] = mapped_column(String(20))
    n_snps: Mapped[int | None] = mapped_column(Integer)
    value_type: Mapped[str | None] = mapped_column(String(10))  # "beta" or "or"

    associations: Mapped[list["GwasAssociation"]] = relationship(
        back_populates="study", cascade="all, delete-orphan", passive_deletes=True
    )
    reference_distributions: Mapped[list["GwasReferenceDistribution"]] = relationship(
        back_populates="study", cascade="all, delete-orphan", passive_deletes=True
    )


class GwasAssociation(Base):
    __tablename__ = "gwas_associations"
    __table_args__ = (
        Index("ix_gwas_assoc_study_rsid", "study_id", "rsid"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    study_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("gwas_studies.study_id", ondelete="CASCADE")
    )
    rsid: Mapped[str] = mapped_column(String(20), nullable=False)
    chrom: Mapped[str | None] = mapped_column(String(2))
    position: Mapped[int | None] = mapped_column(Integer)  # GRCh37
    position_grch38: Mapped[int | None] = mapped_column(Integer)  # GRCh38
    risk_allele: Mapped[str] = mapped_column(String(255), nullable=False)
    beta: Mapped[float] = mapped_column(Float, nullable=False)  # log(OR) if originally OR
    risk_allele_frequency: Mapped[float | None] = mapped_column(Float)
    p_value: Mapped[float | None] = mapped_column(Float)
    # Per-population AFs for ref dist (from Ensembl)
    eur_af: Mapped[float | None] = mapped_column(Float)
    afr_af: Mapped[float | None] = mapped_column(Float)
    eas_af: Mapped[float | None] = mapped_column(Float)
    sas_af: Mapped[float | None] = mapped_column(Float)
    amr_af: Mapped[float | None] = mapped_column(Float)

    study: Mapped["GwasStudy"] = relationship(back_populates="associations")


class GwasReferenceDistribution(Base):
    __tablename__ = "gwas_reference_distributions"

    study_id: Mapped[str] = mapped_column(
        String(30),
        ForeignKey("gwas_studies.study_id", ondelete="CASCADE"),
        primary_key=True,
    )
    ancestry_group: Mapped[str] = mapped_column(String(3), primary_key=True)  # EUR, AFR, etc.
    mean: Mapped[float] = mapped_column(Float)
    std: Mapped[float] = mapped_column(Float)

    study: Mapped["GwasStudy"] = relationship(back_populates="reference_distributions")


class GwasPrsResult(Base):
    __tablename__ = "gwas_prs_results"
    __table_args__ = (
        Index("ix_gwas_prs_user_analysis", "user_id", "analysis_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[str] = mapped_column(String(255), nullable=False)
    analysis_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE")
    )
    study_id: Mapped[str] = mapped_column(
        String(30), ForeignKey("gwas_studies.study_id", ondelete="CASCADE")
    )
    raw_score: Mapped[float] = mapped_column(Float)
    percentile: Mapped[float | None] = mapped_column(Float)
    z_score: Mapped[float | None] = mapped_column(Float)
    ref_mean: Mapped[float | None] = mapped_column(Float)
    ref_std: Mapped[float | None] = mapped_column(Float)
    ancestry_group_used: Mapped[str | None] = mapped_column(String(3))
    n_variants_matched: Mapped[int] = mapped_column(Integer)
    n_variants_total: Mapped[int] = mapped_column(Integer)
