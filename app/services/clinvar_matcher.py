"""ClinVar matcher — cross-references user variants against ClinVar annotations.

Takes a user's parsed genotype DataFrame and identifies which variants have
ClinVar annotations in the snps table. Returns lightweight hit objects (rsid +
genotype only); full ClinVar details are joined at read time to keep storage lean.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

import polars as pl
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

BATCH_SIZE = 5000

# Complement bases for strand-flip detection
_COMP = {"A": "T", "T": "A", "C": "G", "G": "C"}


@dataclass
class ClinvarHit:
    """A user variant that has a ClinVar annotation."""
    rsid: str
    user_genotype: str  # e.g. "AG"


async def match_clinvar(
    user_df: pl.DataFrame,
    session: AsyncSession,
) -> list[ClinvarHit]:
    """Match user variants against ClinVar-annotated entries in the snps table.

    Args:
        user_df: DataFrame with columns [rsid, chrom, position, allele1, allele2]
        session: Async database session

    Returns:
        List of ClinvarHit for each user variant with a ClinVar annotation.
    """
    t0 = time.perf_counter()

    user_rsids = user_df["rsid"].to_list()
    if not user_rsids:
        return []

    # Build rsid → genotype lookup
    genotype_lookup: dict[str, str] = {}
    for row in user_df.select("rsid", "allele1", "allele2").iter_rows():
        genotype_lookup[row[0]] = f"{row[1]}{row[2]}"

    hits: list[ClinvarHit] = []

    # Query in batches — fetch rsid + ref_allele to filter out hom-ref variants
    skipped_hom_ref = 0
    for i in range(0, len(user_rsids), BATCH_SIZE):
        batch = user_rsids[i : i + BATCH_SIZE]
        result = await session.execute(
            text("""
                SELECT rsid, ref_allele FROM snps
                WHERE rsid = ANY(:rsids)
                  AND clinvar_significance IS NOT NULL
            """),
            {"rsids": batch},
        )

        for rsid, ref_allele in result:
            genotype = genotype_lookup.get(rsid)
            if not genotype or len(genotype) != 2:
                continue
            a1, a2 = genotype[0], genotype[1]
            # Skip if user is homozygous reference (doesn't carry the variant)
            if ref_allele and a1 == ref_allele and a2 == ref_allele:
                skipped_hom_ref += 1
                continue
            # Also check complement strand (some chips report opposite strand)
            comp_ref = _COMP.get(ref_allele, "") if ref_allele else ""
            if comp_ref and a1 == comp_ref and a2 == comp_ref:
                skipped_hom_ref += 1
                continue
            hits.append(ClinvarHit(rsid=rsid, user_genotype=genotype))

    elapsed = time.perf_counter() - t0
    log.info(
        f"ClinVar matching: {len(hits)} hits from {len(user_rsids)} variants "
        f"({skipped_hom_ref} hom-ref skipped) in {elapsed:.2f}s"
    )

    return hits
