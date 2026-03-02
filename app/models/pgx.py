"""Pharmacogenomics models — star allele definitions, diplotype phenotypes, user results."""

import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Index, Integer, JSON, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class PgxGeneDefinition(Base):
    """Per-gene configuration controlling star allele calling behavior."""

    __tablename__ = "pgx_gene_definitions"

    gene: Mapped[str] = mapped_column(String(20), primary_key=True)
    calling_method: Mapped[str] = mapped_column(String(20))  # activity_score | simple | binary | count
    default_allele: Mapped[str] = mapped_column(String(10), default="*1")
    description: Mapped[str | None] = mapped_column(Text)


class PgxStarAlleleDefinition(Base):
    """Maps rsID variants to star alleles for each pharmacogene."""

    __tablename__ = "pgx_star_allele_definitions"
    __table_args__ = (
        Index("ix_pgx_star_rsid", "rsid"),
        Index("ix_pgx_star_gene_allele", "gene", "star_allele"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gene: Mapped[str] = mapped_column(String(20), ForeignKey("pgx_gene_definitions.gene", ondelete="CASCADE"))
    star_allele: Mapped[str] = mapped_column(String(20))  # "*4", "positive"
    rsid: Mapped[str] = mapped_column(String(20))
    variant_allele: Mapped[str] = mapped_column(String(10))  # allele that defines this star allele
    function: Mapped[str] = mapped_column(String(30))  # no_function | decreased_function | normal_function | increased_function
    activity_score: Mapped[float | None] = mapped_column(Float)  # for activity_score genes
    clinical_significance: Mapped[str | None] = mapped_column(Text)
    source: Mapped[str | None] = mapped_column(String(50))  # CPIC 


class PgxDiplotypePhenotype(Base):
    """Maps function-pair combinations to metabolizer phenotypes."""

    __tablename__ = "pgx_diplotype_phenotypes"
    __table_args__ = (
        Index("ix_pgx_diplo_gene", "gene"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    gene: Mapped[str] = mapped_column(String(20))
    function_pair: Mapped[str] = mapped_column(String(60))  # sorted: "no_function/no_function"
    phenotype: Mapped[str] = mapped_column(String(50))  # "Poor Metabolizer"
    description: Mapped[str | None] = mapped_column(Text)


class PgxDrugGuideline(Base):
    """CPIC/DPWG prescribing recommendations keyed by gene + phenotype/activity score."""

    __tablename__ = "pgx_drug_guidelines"
    __table_args__ = (
        Index("ix_pgx_guidelines_gene_source", "gene", "source"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(10))  # CPIC or DPWG
    gene: Mapped[str] = mapped_column(String(20))
    drug: Mapped[str] = mapped_column(String(100))
    lookup_type: Mapped[str] = mapped_column(String(20))  # activity_score | phenotype
    lookup_value: Mapped[str] = mapped_column(String(60))
    activity_score_min: Mapped[float | None] = mapped_column(Float)
    activity_score_max: Mapped[float | None] = mapped_column(Float)
    recommendation: Mapped[str] = mapped_column(Text)
    implication: Mapped[str | None] = mapped_column(Text)
    strength: Mapped[str | None] = mapped_column(String(20))
    alternate_drug: Mapped[bool] = mapped_column(Boolean, default=False)
    pmid: Mapped[str | None] = mapped_column(String(20))


class UserPgxResult(Base):
    """Per-user pharmacogenomics result for a single gene."""

    __tablename__ = "user_pgx_results"
    __table_args__ = (
        Index("ix_user_pgx_user_analysis", "user_id", "analysis_id"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    user_id: Mapped[str] = mapped_column(String(255), index=True)
    analysis_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("analyses.id", ondelete="CASCADE"))
    gene: Mapped[str] = mapped_column(String(20))
    diplotype: Mapped[str] = mapped_column(String(40))  # "*1/*4"
    allele1: Mapped[str] = mapped_column(String(20))
    allele2: Mapped[str] = mapped_column(String(20))
    allele1_function: Mapped[str] = mapped_column(String(30))
    allele2_function: Mapped[str] = mapped_column(String(30))
    phenotype: Mapped[str] = mapped_column(String(50))
    activity_score: Mapped[float | None] = mapped_column(Float)
    n_variants_tested: Mapped[int] = mapped_column(Integer)
    n_variants_total: Mapped[int] = mapped_column(Integer)
    calling_method: Mapped[str] = mapped_column(String(20))
    confidence: Mapped[str] = mapped_column(String(10))  # high / medium / low
    drugs_affected: Mapped[str | None] = mapped_column(Text)
    clinical_note: Mapped[str | None] = mapped_column(Text)
    variant_genotypes: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    computed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
