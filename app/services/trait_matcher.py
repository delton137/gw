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


def classify_risk(
    allele1: str,
    allele2: str,
    risk_allele: str,
) -> str:
    """Classify risk based on copies of the risk allele.

    2 copies → increased
    1 copy → moderate
    0 copies → typical
    """
    copies = (allele1 == risk_allele) + (allele2 == risk_allele)
    if copies == 2:
        return "increased"
    elif copies == 1:
        return "moderate"
    return "typical"


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

    # Build a lookup from rsid → (allele1, allele2) using polars
    user_lookup: dict[str, tuple[str, str]] = {}
    for row in user_df.select("rsid", "allele1", "allele2").iter_rows():
        user_lookup[row[0]] = (row[1], row[2])

    hits: list[TraitHit] = []
    matched_assoc_rsids: set[str] = set()

    # Query in batches using ANY() for better Postgres performance
    for i in range(0, len(user_rsids), BATCH_SIZE):
        batch = user_rsids[i : i + BATCH_SIZE]
        result = await session.execute(
            text("""
                SELECT id, rsid, trait, risk_allele, effect_description, evidence_level
                FROM snp_trait_associations
                WHERE rsid = ANY(:rsids)
            """),
            {"rsids": batch},
        )

        for row in result:
            assoc_id, rsid, trait, risk_allele, effect_desc, evidence = row
            alleles = user_lookup.get(rsid)
            if not alleles:
                continue

            matched_assoc_rsids.add(rsid)
            a1, a2 = alleles
            risk_level = classify_risk(a1, a2, risk_allele)

            hits.append(TraitHit(
                rsid=rsid,
                user_genotype=f"{a1}{a2}",
                trait=trait,
                effect_description=effect_desc,
                risk_level=risk_level,
                evidence_level=evidence,
                association_id=str(assoc_id),
            ))

    # For variant-only VCFs: impute missing positions as REF/REF
    if is_vcf:
        imputed_result = await session.execute(
            text("""
                SELECT sta.id, sta.rsid, sta.trait, sta.risk_allele,
                       sta.effect_description, sta.evidence_level, s.ref_allele
                FROM snp_trait_associations sta
                JOIN snps s ON s.rsid = sta.rsid
                WHERE sta.rsid != ALL(:matched)
            """),
            {"matched": list(matched_assoc_rsids)},
        )

        n_imputed = 0
        for row in imputed_result:
            assoc_id, rsid, trait, risk_allele, effect_desc, evidence, ref_allele = row
            if not ref_allele or len(ref_allele) != 1:
                continue  # skip indels / multi-base alleles
            risk_level = classify_risk(ref_allele, ref_allele, risk_allele)
            hits.append(TraitHit(
                rsid=rsid,
                user_genotype=f"{ref_allele}{ref_allele}",
                trait=trait,
                effect_description=effect_desc,
                risk_level=risk_level,
                evidence_level=evidence,
                association_id=str(assoc_id),
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
