"""Shared helpers for route handlers.

Extracted from results.py / account.py to avoid cross-route imports.
"""

from __future__ import annotations

from collections import defaultdict

from fastapi import HTTPException
from sqlalchemy import and_, or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.pgx import PgxStarAlleleDefinition
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
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
        }
        for row in rows
    ]


async def fetch_prs_results(
    session: AsyncSession, analysis_id: str, user_id: str,
) -> list[PrsRow]:
    """Fetch PRS results with score metadata and compute absolute risk.

    Shared by the results endpoint and the PDF report endpoint.
    """
    rows = await session.execute(
        text("""
            SELECT r.pgs_id, r.raw_score, r.percentile, r.z_score,
                   r.ref_mean, r.ref_std, r.ancestry_group_used,
                   r.n_variants_matched, r.n_variants_total, r.computed_at,
                   r.percentile_lower, r.percentile_upper, r.coverage_quality,
                   s.trait_name, s.reported_auc,
                   m.trait_type, m.prevalence, m.source AS prevalence_source
            FROM prs_results r
            JOIN prs_scores s ON r.pgs_id = s.pgs_id
            LEFT JOIN prs_trait_metadata m ON r.pgs_id = m.pgs_id
            WHERE r.analysis_id = :aid AND r.user_id = :uid
            ORDER BY r.percentile DESC
        """),
        {"aid": analysis_id, "uid": user_id},
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
            "percentile_lower": round(row.percentile_lower, 1) if row.percentile_lower is not None else None,
            "percentile_upper": round(row.percentile_upper, 1) if row.percentile_upper is not None else None,
            "coverage_quality": row.coverage_quality,
            "computed_at": row.computed_at.isoformat() if row.computed_at else None,
            "absolute_risk": None,
            "population_risk": None,
            "risk_category": None,
            "prevalence_source": None,
        }

        if (
            row.z_score is not None
            and row.reported_auc is not None
            and row.prevalence is not None
            and row.trait_type == "binary"
        ):
            risk = compute_absolute_risk(
                z_score=row.z_score,
                prevalence=row.prevalence,
                auc=row.reported_auc,
            )
            if risk is not None:
                entry["absolute_risk"] = round(risk.absolute_risk, 4)
                entry["population_risk"] = round(risk.population_risk, 4)
                entry["risk_category"] = risk.risk_category
                entry["prevalence_source"] = row.prevalence_source

        result_list.append(entry)

    return result_list


# ---------------------------------------------------------------------------
# PGX defining variants
# ---------------------------------------------------------------------------

SKIP_ALLELES = frozenset({"negative", "positive", "rapid", "slow", "count"})


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
