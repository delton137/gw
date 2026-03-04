"""Match CPIC/DPWG drug guidelines to user PGX results.

Given a user's gene results (phenotype + activity score), looks up matching
prescribing recommendations from the pgx_drug_guidelines table.
"""

from __future__ import annotations

import logging
import math
from collections import defaultdict

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

# Phenotype normalization: our phenotype strings → canonical lookup values
_PHENOTYPE_ALIASES = {
    "ultra-rapid metabolizer": "Ultrarapid Metabolizer",
    "ultrarapid metabolizer": "Ultrarapid Metabolizer",
    "rapid metabolizer": "Rapid Metabolizer",
    "normal metabolizer": "Normal Metabolizer",
    "intermediate metabolizer": "Intermediate Metabolizer",
    "poor metabolizer": "Poor Metabolizer",
    # Transporter / function phenotypes
    "normal function": "Normal Function",
    "decreased function": "Decreased Function",
    "poor function": "Poor Function",
    "increased function": "Increased Function",
    # NAT2 acetylator
    "rapid acetylator": "Rapid Metabolizer",
    "intermediate acetylator": "Intermediate Metabolizer",
    "slow acetylator": "Poor Metabolizer",
    # G6PD
    "deficient": "Deficient",
    "normal": "Normal",
    "variable": "Variable",
    # Binary
    "positive (carrier)": "positive",
    "negative (non-carrier)": "negative",
}


def _normalize_phenotype(phenotype: str) -> str:
    """Normalize phenotype string for lookup matching."""
    return _PHENOTYPE_ALIASES.get(phenotype.lower(), phenotype)


def _round_activity_score(score: float) -> float:
    """Round activity score to nearest 0.25 for matching."""
    return round(score * 4) / 4


async def match_guidelines(
    session: AsyncSession,
    results: list[dict],
) -> dict[str, dict[str, list[dict]]]:
    """Match guidelines for a batch of PGX results.

    Args:
        session: Database session.
        results: List of PGX result dicts with gene, phenotype, activity_score.

    Returns:
        {gene: {"cpic": [...], "dpwg": [...]}} mapping.
    """
    if not results:
        return {}

    # Collect genes from results
    genes = list({r["gene"] for r in results})

    # Batch-load all guidelines for these genes
    rows = await session.execute(
        text("""
            SELECT gene, source, drug, lookup_type, lookup_value,
                   activity_score_min, activity_score_max,
                   recommendation, implication, strength,
                   alternate_drug, pmid
            FROM pgx_drug_guidelines
            WHERE gene = ANY(:genes)
            ORDER BY gene, source, drug
        """),
        {"genes": genes},
    )

    # Index guidelines by gene
    guidelines_by_gene: dict[str, list] = defaultdict(list)
    for row in rows:
        guidelines_by_gene[row.gene].append(row)

    # Match each result
    matched: dict[str, dict[str, list[dict]]] = {}

    for r in results:
        gene = r["gene"]
        phenotype = r.get("phenotype") or ""
        activity_score = r.get("activity_score")
        calling_method = r.get("calling_method", "")

        # For binary genes, map gene_phenotype to lookup-compatible form
        gene_key = gene.split("_")[0] if "_" in gene else gene
        gene_guidelines = guidelines_by_gene.get(gene_key, [])

        if not gene_guidelines:
            matched[gene] = {"cpic": [], "dpwg": []}
            continue

        cpic_matches: list[dict] = []
        dpwg_matches: list[dict] = []

        # Track which (source, drug) pairs matched by activity_score so we
        # can skip redundant phenotype-lookup duplicates for the same drug.
        as_matched: set[tuple[str, str]] = set()  # (source, drug_lower)

        for gl in gene_guidelines:
            if _matches_guideline(gl, phenotype, activity_score, calling_method, gene):
                key = (gl.source, gl.drug.lower())
                if gl.lookup_type == "activity_score":
                    as_matched.add(key)
                elif gl.lookup_type == "phenotype" and key in as_matched:
                    continue  # skip duplicate phenotype entry

                entry = {
                    "drug": gl.drug,
                    "recommendation": gl.recommendation,
                    "implication": gl.implication,
                    "strength": gl.strength,
                    "pmid": gl.pmid,
                }
                if gl.source == "CPIC":
                    cpic_matches.append(entry)
                else:
                    dpwg_matches.append(entry)

        matched[gene] = {"cpic": cpic_matches, "dpwg": dpwg_matches}

    return matched


def _matches_guideline(gl, phenotype: str, activity_score: float | None,
                       calling_method: str, gene: str) -> bool:
    """Check if a guideline row matches the user's result."""

    if gl.lookup_type == "activity_score":
        if activity_score is None:
            return False
        rounded = _round_activity_score(activity_score)
        if gl.activity_score_min is not None and gl.activity_score_max is not None:
            if gl.activity_score_max >= 999.0:
                # "≥X" range — match anything at or above min
                return rounded >= gl.activity_score_min
            return gl.activity_score_min - 0.001 <= rounded <= gl.activity_score_max + 0.001
        return False

    elif gl.lookup_type == "phenotype":
        normalized = _normalize_phenotype(phenotype)
        lookup_val = gl.lookup_value

        # Exact match
        if normalized == lookup_val:
            return True

        # Case-insensitive match
        if normalized.lower() == lookup_val.lower():
            return True

        # Binary gene: check if lookup contains "positive"/"negative"
        if calling_method == "binary":
            if "positive" in normalized.lower() and "positive" in lookup_val.lower():
                return True
            if "negative" in normalized.lower() and "negative" in lookup_val.lower():
                return True

        return False

    return False
