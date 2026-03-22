"""Typed dictionaries for structured data passing between routes, services, and reports.

These provide IDE autocompletion and type-checker safety with zero runtime cost.
"""

from __future__ import annotations

from typing import TypedDict


class PgxRow(TypedDict):
    """Row returned by fetch_pgx_rows() — PGX result joined with gene definition."""

    gene: str
    diplotype: str
    allele1: str
    allele2: str
    allele1_function: str
    allele2_function: str
    phenotype: str
    activity_score: float | None
    n_variants_tested: int
    n_variants_total: int
    calling_method: str
    confidence: str
    drugs_affected: str | None
    clinical_note: str | None
    gene_description: str | None
    variant_genotypes: dict[str, str] | None
    computed_at: str | None


class PrsRow(TypedDict):
    """Row returned by fetch_prs_results() — PRS result with metadata and absolute risk."""

    pgs_id: str
    trait_name: str
    raw_score: float
    percentile: float
    z_score: float | None
    ref_mean: float | None
    ref_std: float | None
    ancestry_group_used: str
    n_variants_matched: int
    n_variants_total: int
    reported_auc: float | None
    publication_pmid: str | None
    publication_doi: str | None
    percentile_lower: float | None
    percentile_upper: float | None
    coverage_quality: str | None
    computed_at: str | None
    absolute_risk: float | None
    population_risk: float | None
    risk_category: str | None
    prevalence_source: str | None
    absolute_risk_lower: float | None
    absolute_risk_upper: float | None
