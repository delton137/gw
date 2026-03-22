"""Trait matcher — matches user variants against SNP-trait associations.

Takes a user's parsed genotype DataFrame and queries the snp_trait_associations
table for matching rsids. Classifies each hit by risk level based on whether
the user carries 0, 1, or 2 copies of the risk allele.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import polars as pl
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

BATCH_SIZE = 5000  # rsids per SQL query


@dataclass
class TraitHit:
    """A single SNP-trait association matched to a user's genotype."""
    rsid: str
    user_genotype: str  # e.g. "AG"
    trait: str
    effect_description: str | None
    risk_level: str  # increased / moderate / typical
    evidence_level: str
    association_id: str  # UUID as string
    odds_ratio: float | None = None


def classify_risk(
    allele1: str,
    allele2: str,
    risk_allele: str,
    odds_ratio: float | None = None,
) -> str:
    """Classify risk based on copies of the risk allele and effect size.

    When odds_ratio is available, uses effect-size-aware thresholds:
      - OR >= 2.0 with 2 copies → increased
      - OR >= 1.5 with 1+ copies, or OR 1.2–2.0 with 2 copies → moderate
      - OR < 1.2 → typical (regardless of copies)
    When odds_ratio is unavailable, falls back to allele-count logic.
    """
    copies = (allele1 == risk_allele) + (allele2 == risk_allele)
    if copies == 0:
        return "typical"

    if odds_ratio is not None and odds_ratio > 0:
        if odds_ratio >= 2.0 and copies == 2:
            return "increased"
        if odds_ratio >= 1.5 and copies >= 1:
            return "moderate"
        if odds_ratio >= 1.2 and copies == 2:
            return "moderate"
        if odds_ratio < 1.2:
            return "typical"

    # Fallback: allele-count only (when OR unavailable)
    if copies == 2:
        return "increased"
    return "moderate"


async def match_traits(
    user_df: pl.DataFrame,
    session: AsyncSession,
    is_vcf: bool = False,
) -> list[TraitHit]:
    """Match user variants against snp_trait_associations table.

    For variant-only VCFs (is_vcf=True), positions absent from the file are
    imputed as homozygous reference (REF/REF) using the snps table ref_allele.
    This mirrors the imputation logic in scorer._impute_vcf_missing().

    Args:
        user_df: DataFrame with columns [rsid, chrom, position, allele1, allele2]
        session: Async database session
        is_vcf: If True, impute missing positions as REF/REF

    Returns:
        List of TraitHit results sorted by risk level (increased first).
    """
    t0 = time.perf_counter()

    user_rsids = user_df["rsid"].to_list()
    if not user_rsids and not is_vcf:
        return []

    # Build a lookup from rsid → (allele1, allele2) using vectorized extraction
    rsids = user_df["rsid"].to_list()
    a1s = user_df["allele1"].to_list()
    a2s = user_df["allele2"].to_list()
    user_lookup: dict[str, tuple[str, str]] = dict(zip(rsids, zip(a1s, a2s)))

    hits: list[TraitHit] = []
    matched_assoc_rsids: set[str] = set()

    # Query in batches using ANY() for better Postgres performance
    for i in range(0, len(user_rsids), BATCH_SIZE):
        batch = user_rsids[i : i + BATCH_SIZE]
        result = await session.execute(
            text("""
                SELECT id, rsid, trait, risk_allele, effect_description,
                       evidence_level, odds_ratio
                FROM snp_trait_associations
                WHERE rsid = ANY(:rsids)
            """),
            {"rsids": batch},
        )

        for row in result:
            assoc_id, rsid, trait, risk_allele, effect_desc, evidence, or_val = row
            alleles = user_lookup.get(rsid)
            if not alleles:
                continue

            matched_assoc_rsids.add(rsid)
            a1, a2 = alleles
            risk_level = classify_risk(a1, a2, risk_allele, odds_ratio=or_val)

            hits.append(TraitHit(
                rsid=rsid,
                user_genotype=f"{a1}{a2}",
                trait=trait,
                effect_description=effect_desc,
                risk_level=risk_level,
                evidence_level=evidence,
                association_id=str(assoc_id),
                odds_ratio=or_val,
            ))

    # For variant-only VCFs: impute missing positions as REF/REF
    if is_vcf:
        imputed_result = await session.execute(
            text("""
                SELECT sta.id, sta.rsid, sta.trait, sta.risk_allele,
                       sta.effect_description, sta.evidence_level,
                       sta.odds_ratio, s.ref_allele
                FROM snp_trait_associations sta
                JOIN snps s ON s.rsid = sta.rsid
                WHERE sta.rsid != ALL(:matched)
            """),
            {"matched": list(matched_assoc_rsids)},
        )

        n_imputed = 0
        for row in imputed_result:
            assoc_id, rsid, trait, risk_allele, effect_desc, evidence, or_val, ref_allele = row
            if not ref_allele or len(ref_allele) != 1:
                continue  # skip indels / multi-base alleles
            risk_level = classify_risk(ref_allele, ref_allele, risk_allele, odds_ratio=or_val)
            hits.append(TraitHit(
                rsid=rsid,
                user_genotype=f"{ref_allele}{ref_allele}",
                trait=trait,
                effect_description=effect_desc,
                risk_level=risk_level,
                evidence_level=evidence,
                association_id=str(assoc_id),
                odds_ratio=or_val,
            ))
            n_imputed += 1

        if n_imputed:
            log.info(f"Trait matching: imputed {n_imputed} missing VCF positions as REF/REF")

    # Sort: increased first, then moderate, then typical
    risk_order = {"increased": 0, "moderate": 1, "typical": 2}
    hits.sort(key=lambda h: risk_order.get(h.risk_level, 3))

    elapsed = time.perf_counter() - t0
    log.info(f"Trait matching: {len(hits)} hits from {len(user_rsids)} variants in {elapsed:.2f}s")

    return hits
