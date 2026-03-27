"""Shared helpers for route handlers.

Extracted from results.py / account.py to avoid cross-route imports.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pgx import PgxGeneDefinition, PgxStarAlleleDefinition
from app.models.user import Analysis
from app.schemas import PgxRow, PrsRow
from app.services.absolute_risk import compute_absolute_risk


# ---------------------------------------------------------------------------
# Analysis / result fetchers
# ---------------------------------------------------------------------------

async def get_latest_analysis(
    session: AsyncSession, user_id: str,
) -> Analysis:
    """Return the user's most recent completed analysis, or raise 404."""
    result = await session.execute(
        select(Analysis)
        .where(Analysis.user_id == user_id, Analysis.status.in_(["done", "scoring_prs", "complete"]))
        .order_by(Analysis.created_at.desc())
        .limit(1)
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="No completed analysis found")
    return analysis


async def fetch_pgx_rows(
    session: AsyncSession, analysis_id: str, user_id: str,
) -> list[PgxRow]:
    """Fetch PGX results joined with gene definitions.

    Shared by the PGX results endpoint and the PGX PDF report endpoint.
    """
    rows = await session.execute(
        text("""
            SELECT r.gene, r.diplotype, r.allele1, r.allele2,
                   r.allele1_function, r.allele2_function,
                   r.phenotype, r.activity_score,
                   r.n_variants_tested, r.n_variants_total,
                   r.calling_method, r.confidence,
                   r.drugs_affected, r.clinical_note, r.computed_at,
                   r.variant_genotypes,
                   g.description AS gene_description
            FROM user_pgx_results r
            LEFT JOIN pgx_gene_definitions g ON r.gene = g.gene
            WHERE r.analysis_id = :aid AND r.user_id = :uid
            ORDER BY r.gene
        """),
        {"aid": analysis_id, "uid": user_id},
    )
    return [
        {
            "gene": row.gene,
            "diplotype": row.diplotype,
            "allele1": row.allele1,
            "allele2": row.allele2,
            "allele1_function": row.allele1_function,
            "allele2_function": row.allele2_function,
            "phenotype": row.phenotype,
            "activity_score": row.activity_score,
            "n_variants_tested": row.n_variants_tested,
            "n_variants_total": row.n_variants_total,
            "calling_method": row.calling_method,
            "confidence": row.confidence,
            "drugs_affected": row.drugs_affected,
            "clinical_note": row.clinical_note,
            "gene_description": row.gene_description,
            "variant_genotypes": row.variant_genotypes,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        }
        for row in rows
    ]


async def fetch_prs_results(
    session: AsyncSession, analysis_id: str, user_id: str,
    inferred_sex: str | None = None,
) -> list[PrsRow]:
    """Fetch PRS results with score metadata and compute absolute risk.

    Shared by the results endpoint and the PDF report endpoint.
    When inferred_sex is provided ('male'/'female'), sex-specific PRS scores
    that don't apply to this user are excluded (e.g., breast cancer for males).
    """
    sex_filter = "AND (s.target_sex IS NULL OR s.target_sex = :inferred_sex)" if inferred_sex else ""
    rows = await session.execute(
        text(f"""
            SELECT r.pgs_id, r.raw_score, r.percentile, r.z_score,
                   r.ref_mean, r.ref_std, r.ancestry_group_used,
                   r.n_variants_matched, r.n_variants_total, r.computed_at,
                   r.percentile_lower, r.percentile_upper, r.coverage_quality,
                   s.trait_name, s.reported_auc,
                   s.publication_pmid, s.publication_doi,
                   m.trait_type, m.prevalence, m.source AS prevalence_source
            FROM prs_results r
            JOIN prs_scores s ON r.pgs_id = s.pgs_id
            LEFT JOIN prs_trait_metadata m ON r.pgs_id = m.pgs_id
            WHERE r.analysis_id = :aid AND r.user_id = :uid
            {sex_filter}
            ORDER BY r.percentile DESC
        """),
        {"aid": analysis_id, "uid": user_id, "inferred_sex": inferred_sex},
    )

    result_list = []
    for row in rows:
        entry = {
            "pgs_id": row.pgs_id,
            "trait_name": row.trait_name,
            "raw_score": row.raw_score,
            "percentile": round(row.percentile, 1),
            "z_score": round(row.z_score, 4) if row.z_score is not None else None,
            "ref_mean": row.ref_mean,
            "ref_std": row.ref_std,
            "ancestry_group_used": row.ancestry_group_used,
            "n_variants_matched": row.n_variants_matched,
            "n_variants_total": row.n_variants_total,
            "reported_auc": row.reported_auc,
            "publication_pmid": row.publication_pmid,
            "publication_doi": row.publication_doi,
            "percentile_lower": round(row.percentile_lower, 1) if row.percentile_lower is not None else None,
            "percentile_upper": round(row.percentile_upper, 1) if row.percentile_upper is not None else None,
            "coverage_quality": row.coverage_quality,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
            "absolute_risk": None,
            "population_risk": None,
            "risk_category": None,
            "prevalence_source": None,
            "absolute_risk_lower": None,
            "absolute_risk_upper": None,
        }

        if (
            row.z_score is not None
            and row.reported_auc is not None
            and row.prevalence is not None
            and row.trait_type == "binary"
        ):
            # Derive z-score CI bounds from percentile CI bounds
            z_lower = None
            z_upper = None
            if row.percentile_lower is not None and row.percentile_upper is not None:
                from app.services.absolute_risk import _norm_ppf
                z_lower = _norm_ppf(row.percentile_lower / 100.0)
                z_upper = _norm_ppf(row.percentile_upper / 100.0)

            risk = compute_absolute_risk(
                z_score=row.z_score,
                prevalence=row.prevalence,
                auc=row.reported_auc,
                z_score_lower=z_lower,
                z_score_upper=z_upper,
            )
            if risk is not None:
                entry["absolute_risk"] = round(risk.absolute_risk, 4)
                entry["population_risk"] = round(risk.population_risk, 4)
                entry["risk_category"] = risk.risk_category
                entry["prevalence_source"] = row.prevalence_source
                entry["absolute_risk_lower"] = round(risk.absolute_risk_lower, 4) if risk.absolute_risk_lower is not None else None
                entry["absolute_risk_upper"] = round(risk.absolute_risk_upper, 4) if risk.absolute_risk_upper is not None else None

        result_list.append(entry)

    return result_list


# ---------------------------------------------------------------------------
# PGX defining variants
# ---------------------------------------------------------------------------

SKIP_ALLELES = frozenset({"negative", "positive", "rapid", "slow", "count"})


async def fetch_pgx_panel_snps(
    session: AsyncSession,
    genes: list[str],
) -> dict[str, list[str]]:
    """Fetch all unique rsids in each gene's star allele panel.

    Returns {gene: [rsid, ...]} sorted by rsid.
    """
    if not genes:
        return {}

    stmt = (
        select(
            PgxStarAlleleDefinition.gene,
            PgxStarAlleleDefinition.rsid,
        )
        .where(PgxStarAlleleDefinition.gene.in_(genes))
        .distinct()
    )
    rows = await session.execute(stmt)

    result: dict[str, list[str]] = defaultdict(list)
    for row in rows:
        result[row.gene].append(row.rsid)
    for gene in result:
        result[gene].sort()
    return result


async def fetch_pgx_defining_variants(
    session: AsyncSession,
    allele_pairs: set[tuple[str, str]],
) -> dict[tuple[str, str], list[dict]]:
    """Batch-fetch defining variants for non-default star alleles.

    Returns {(gene, star_allele): [{"rsid": ..., "variant_allele": ...}, ...]}.
    """
    if not allele_pairs:
        return {}

    stmt = select(
        PgxStarAlleleDefinition.gene,
        PgxStarAlleleDefinition.star_allele,
        PgxStarAlleleDefinition.rsid,
        PgxStarAlleleDefinition.variant_allele,
    ).where(
        or_(*(
            and_(PgxStarAlleleDefinition.gene == g, PgxStarAlleleDefinition.star_allele == a)
            for g, a in allele_pairs
        ))
    )
    def_rows = await session.execute(stmt)

    result: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for dr in def_rows:
        result[(dr.gene, dr.star_allele)].append({
            "rsid": dr.rsid,
            "variant_allele": dr.variant_allele,
        })
    return result


# ---------------------------------------------------------------------------
# PGX default alleles + defining variant attachment
# ---------------------------------------------------------------------------

async def fetch_pgx_default_alleles(
    session: AsyncSession,
) -> dict[str, str]:
    """Fetch {gene: default_allele} for all PGX genes."""
    result = await session.execute(
        select(PgxGeneDefinition.gene, PgxGeneDefinition.default_allele)
    )
    return {row.gene: row.default_allele for row in result}


def _collect_nondefault_allele_pairs(
    results: list[PgxRow],
    default_alleles: dict[str, str],
) -> set[tuple[str, str]]:
    """Collect (gene, star_allele) pairs for non-default alleles in results."""
    pairs: set[tuple[str, str]] = set()
    for r in results:
        default = default_alleles.get(r["gene"], "*1")
        for allele in (r["allele1"], r["allele2"]):
            if allele and allele != default and allele not in SKIP_ALLELES:
                pairs.add((r["gene"], allele))
    return pairs


async def attach_defining_variants(
    session: AsyncSession,
    results: list[PgxRow],
    default_alleles: dict[str, str],
) -> None:
    """Attach defining variant info to each PGX result dict in-place.

    Sets r["defining_variants"] = {allele: [{rsid, variant_allele}, ...]} or None.
    """
    allele_pairs = _collect_nondefault_allele_pairs(results, default_alleles)
    defining_map = await fetch_pgx_defining_variants(session, allele_pairs)
    for r in results:
        variants: dict[str, list[dict]] = {}
        for allele in (r["allele1"], r["allele2"]):
            if allele and (r["gene"], allele) in defining_map:
                variants[allele] = defining_map[(r["gene"], allele)]
        r["defining_variants"] = variants if variants else None


async def build_defining_variants_by_gene(
    session: AsyncSession,
    results: list[PgxRow],
    default_alleles: dict[str, str],
) -> dict[str, dict[str, list[dict]]]:
    """Build {gene: {allele: [variants]}} for PGX report PDF generation."""
    allele_pairs = _collect_nondefault_allele_pairs(results, default_alleles)
    defining_map = await fetch_pgx_defining_variants(session, allele_pairs)
    by_gene: dict[str, dict[str, list[dict]]] = {}
    for r in results:
        gene_dv: dict[str, list[dict]] = {}
        for allele in (r["allele1"], r["allele2"]):
            if allele and (r["gene"], allele) in defining_map:
                gene_dv[allele] = defining_map[(r["gene"], allele)]
        if gene_dv:
            by_gene[r["gene"]] = gene_dv
    return by_gene
