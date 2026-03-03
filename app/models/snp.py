import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, Index, Integer, String, Text, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class SnpediaSnp(Base):
    """Lookup table of rsids that have SNPedia pages (~109K)."""
    __tablename__ = "snpedia_snps"

    rsid: Mapped[str] = mapped_column(String(20), primary_key=True)


class Snp(Base):
    __tablename__ = "snps"

    rsid: Mapped[str] = mapped_column(String, primary_key=True)
    chrom: Mapped[str] = mapped_column(String(2))
    position: Mapped[int]  # GRCh37 position
    position_grch38: Mapped[int | None] = mapped_column(Integer)
    # NOTE: These store PGS Catalog other_allele/effect_allele, NOT genomic REF/ALT.
    # The scorer uses effect_allele from prs_variant_weights directly.
    ref_allele: Mapped[str] = mapped_column(String(255))
    alt_allele: Mapped[str] = mapped_column(String(255))
    gene: Mapped[str | None] = mapped_column(String(50), index=True)
    functional_class: Mapped[str | None] = mapped_column(String(50))
    maf_global: Mapped[float | None] = mapped_column(Float)

    # Pathogenicity scores
    cadd_phred: Mapped[float | None] = mapped_column(Float)
    sift_category: Mapped[str | None] = mapped_column(String(20))
    sift_score: Mapped[float | None] = mapped_column(Float)
    polyphen_category: Mapped[str | None] = mapped_column(String(30))
    polyphen_score: Mapped[float | None] = mapped_column(Float)
    revel_score: Mapped[float | None] = mapped_column(Float)

    # ClinVar
    clinvar_significance: Mapped[str | None] = mapped_column(String(100))
    clinvar_conditions: Mapped[str | None] = mapped_column(Text)
    clinvar_review_stars: Mapped[int | None] = mapped_column(Integer)
    clinvar_allele_id: Mapped[int | None] = mapped_column(Integer)
    clinvar_submitter_count: Mapped[int | None] = mapped_column(Integer)
    clinvar_citation_count: Mapped[int | None] = mapped_column(Integer)
    clinvar_pmids: Mapped[str | None] = mapped_column(Text)  # comma-separated top PMIDs

    # HGVS notation
    hgvs_coding: Mapped[str | None] = mapped_column(String(255))
    hgvs_protein: Mapped[str | None] = mapped_column(String(255))

    # gnomAD population frequencies
    gnomad_afr: Mapped[float | None] = mapped_column(Float)
    gnomad_eas: Mapped[float | None] = mapped_column(Float)
    gnomad_nfe: Mapped[float | None] = mapped_column(Float)
    gnomad_sas: Mapped[float | None] = mapped_column(Float)
    gnomad_amr: Mapped[float | None] = mapped_column(Float)
    gnomad_fin: Mapped[float | None] = mapped_column(Float)
    gnomad_asj: Mapped[float | None] = mapped_column(Float)


class SnpTraitAssociation(Base):
    __tablename__ = "snp_trait_associations"
    __table_args__ = (Index("ix_snp_trait_rsid_trait", "rsid", "trait"),)

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, server_default=text("gen_random_uuid()")
    )
    rsid: Mapped[str] = mapped_column(String, index=True)
    trait: Mapped[str] = mapped_column(String(255), index=True)
    risk_allele: Mapped[str] = mapped_column(String(10))
    odds_ratio: Mapped[float | None] = mapped_column(Float)
    beta: Mapped[float | None] = mapped_column(Float)
    p_value: Mapped[float | None] = mapped_column(Float)
    effect_description: Mapped[str | None] = mapped_column(Text)
    effect_summary: Mapped[str | None] = mapped_column(String(120))  # short label e.g. "Higher Alzheimer's risk"
    evidence_level: Mapped[str] = mapped_column(String(10))  # high/medium/low
    source_pmid: Mapped[str | None] = mapped_column(String(20))
    source_title: Mapped[str | None] = mapped_column(Text)
    trait_prevalence: Mapped[float | None] = mapped_column(Float)  # population prevalence (0-1)
    extraction_method: Mapped[str] = mapped_column(String(20))  # ai_agent/gwas_catalog/manual
    extracted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )
