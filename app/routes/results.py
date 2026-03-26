"""Results endpoints — analysis status, PRS results, and trait hits."""

from __future__ import annotations

import uuid
from collections import defaultdict
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id, get_verified_user_id
from app.db import get_session
from app.models.carrier_status import UserCarrierStatusResult
from app.services.pgx_guidelines import match_guidelines
from app.models.gwas import GwasPrsResult, GwasStudy
from app.models.snp import Snp, SnpTraitAssociation
from app.models.user import Analysis, UserClinvarHit, UserSnpTraitHit, UserVariant
from app.routes._helpers import (
    attach_defining_variants,
    fetch_pgx_default_alleles,
    fetch_pgx_panel_snps,
    fetch_pgx_rows,
    fetch_prs_results,
    get_latest_analysis,
)

router = APIRouter()


@router.get("/results/analysis/{analysis_id}")
async def get_analysis_status(
    analysis_id: uuid.UUID,
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Poll analysis status.

    Uses get_current_user_id (not get_verified_user_id) because this endpoint
    is keyed by analysis_id rather than user_id. Ownership is enforced by the
    WHERE clause below — the query returns None if the analysis belongs to a
    different user, resulting in a 404.
    """
    result = await session.execute(
        select(Analysis).where(
            Analysis.id == str(analysis_id),
            Analysis.user_id == user_id,
        )
    )
    analysis = result.scalar_one_or_none()
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    return {
        "id": str(analysis.id),
        "status": analysis.status,
        "chip_type": analysis.chip_type,
        "variant_count": analysis.variant_count,
        "error_message": analysis.error_message if analysis.status in ("failed", "done") else None,
        "detected_ancestry": analysis.detected_ancestry,
        "ancestry_method": analysis.ancestry_method,
        "ancestry_confidence": analysis.ancestry_confidence,
        "selected_ancestry": analysis.selected_ancestry,
        "created_at": analysis.created_at.isoformat(),
        "filename": analysis.filename,
        "completed_at": analysis.completed_at.isoformat() if analysis.completed_at else None,
        "genome_build": analysis.genome_build,
        "status_detail": analysis.status_detail,
        "pipeline_fast_seconds": analysis.pipeline_fast_seconds,
        "is_imputed": analysis.is_imputed,
    }


@router.get("/results/prs/{user_id}")
async def get_prs_results(
    user_id: str = Depends(get_verified_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get PRS results for a user from their most recent completed analysis."""

    analysis = await get_latest_analysis(session, user_id)
    result_list = await fetch_prs_results(session, str(analysis.id), user_id)

    # Determine PRS computation status
    if analysis.status == "complete":
        prs_status = "ready"
    elif analysis.status == "done" and analysis.error_message:
        prs_status = "failed"
    else:
        prs_status = "computing"

    return {
        "analysis_id": str(analysis.id),
        "prs_status": prs_status,
        "prs_status_detail": analysis.status_detail if prs_status == "computing" else None,
        "selected_ancestry": analysis.selected_ancestry,
        "results": result_list,
    }


@router.get("/results/traits/{user_id}")
async def get_trait_hits(
    user_id: str = Depends(get_verified_user_id),
    risk_level: Literal["increased", "moderate", "typical"] | None = Query(None),
    evidence_level: Literal["high", "medium", "low"] | None = Query(None),
    limit: int = Query(500, ge=1, le=1000),
    offset: int = Query(0, ge=0, le=10000),
    session: AsyncSession = Depends(get_session),
):
    """Get trait hits for a user with optional filters."""

    analysis = await get_latest_analysis(session, user_id)

    # Build query with filters — join snps table for gene info, associations for risk_allele
    query = (
        select(UserSnpTraitHit, Snp.gene, SnpTraitAssociation.risk_allele, SnpTraitAssociation.effect_summary)
        .outerjoin(Snp, UserSnpTraitHit.rsid == Snp.rsid)
        .outerjoin(SnpTraitAssociation, UserSnpTraitHit.association_id == SnpTraitAssociation.id)
        .where(
            UserSnpTraitHit.analysis_id == analysis.id,
            UserSnpTraitHit.user_id == user_id,
        )
    )
    if risk_level:
        query = query.where(UserSnpTraitHit.risk_level == risk_level)
    if evidence_level:
        query = query.where(UserSnpTraitHit.evidence_level == evidence_level)

    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    rows = result.all()

    # Count total unique SNPs in knowledge base
    kb_total_result = await session.execute(
        text("SELECT COUNT(DISTINCT rsid) FROM snp_trait_associations")
    )
    kb_total = kb_total_result.scalar() or 0

    # Count unique SNPs matched for this user (regardless of pagination)
    unique_matched_result = await session.execute(
        text(
            "SELECT COUNT(DISTINCT rsid) FROM user_snp_trait_hits "
            "WHERE analysis_id = :aid AND user_id = :uid"
        ),
        {"aid": str(analysis.id), "uid": user_id},
    )
    unique_snps_matched = unique_matched_result.scalar() or 0

    return {
        "analysis_id": str(analysis.id),
        "total": len(rows),
        "total_snps_in_kb": kb_total,
        "unique_snps_matched": unique_snps_matched,
        "offset": offset,
        "hits": [
            {
                "id": str(h.id),
                "rsid": h.rsid,
                "gene": gene,
                "user_genotype": h.user_genotype,
                "risk_allele": risk_allele,
                "effect_summary": effect_summary,
                "trait": h.trait,
                "effect_description": h.effect_description,
                "risk_level": h.risk_level,
                "evidence_level": h.evidence_level,
            }
            for h, gene, risk_allele, effect_summary in rows
        ],
    }



@router.get("/results/clinvar/{user_id}")
async def get_clinvar_hits(
    user_id: str = Depends(get_verified_user_id),
    significance: str | None = Query(None),
    gene: str | None = Query(None, max_length=50),
    condition: str | None = Query(None, max_length=200),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Get ClinVar-annotated variants for a user, joined with snps table."""

    analysis = await get_latest_analysis(session, user_id)

    # Summary counts by significance (always return full summary regardless of filters)
    count_result = await session.execute(
        text("""
            SELECT s.clinvar_significance, COUNT(*) as cnt
            FROM user_clinvar_hits uch
            JOIN snps s ON uch.rsid = s.rsid
            WHERE uch.user_id = :uid AND uch.analysis_id = :aid
              AND s.clinvar_significance IS NOT NULL
            GROUP BY s.clinvar_significance
        """),
        {"uid": user_id, "aid": str(analysis.id)},
    )
    counts = {row.clinvar_significance: row.cnt for row in count_result}
    total = sum(counts.values())

    # Filtered query for paginated results
    query = (
        select(
            UserClinvarHit.rsid,
            UserClinvarHit.user_genotype,
            Snp.gene,
            Snp.clinvar_significance,
            Snp.clinvar_conditions,
            Snp.clinvar_review_stars,
            Snp.clinvar_allele_id,
            Snp.functional_class,
            Snp.chrom,
            Snp.position,
            Snp.ref_allele,
            Snp.alt_allele,
        )
        .join(Snp, UserClinvarHit.rsid == Snp.rsid)
        .where(
            UserClinvarHit.user_id == user_id,
            UserClinvarHit.analysis_id == analysis.id,
            Snp.clinvar_significance.is_not(None),
        )
    )
    if significance:
        query = query.where(Snp.clinvar_significance == significance)
    if gene:
        query = query.where(Snp.gene == gene)
    if condition:
        escaped_cond = condition.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        query = query.where(Snp.clinvar_conditions.ilike(f"%{escaped_cond}%", escape="\\"))

    # Sort by clinical severity
    query = query.order_by(
        text("""CASE clinvar_significance
            WHEN 'pathogenic' THEN 0
            WHEN 'likely_pathogenic' THEN 1
            WHEN 'risk_factor' THEN 4
            WHEN 'drug_response' THEN 6
            WHEN 'uncertain_significance' THEN 9
            WHEN 'likely_benign' THEN 12
            WHEN 'benign' THEN 13
            ELSE 7
        END"""),
        Snp.gene,
    )
    query = query.offset(offset).limit(limit)

    result = await session.execute(query)
    rows = result.all()

    return {
        "analysis_id": str(analysis.id),
        "total": total,
        "counts": counts,
        "offset": offset,
        "hits": [
            {
                "rsid": row.rsid,
                "user_genotype": row.user_genotype,
                "gene": row.gene,
                "clinvar_significance": row.clinvar_significance,
                "clinvar_conditions": row.clinvar_conditions,
                "review_stars": row.clinvar_review_stars,
                "allele_id": row.clinvar_allele_id,
                "functional_class": row.functional_class,
                "chrom": row.chrom,
                "position": row.position,
                "ref_allele": row.ref_allele,
                "alt_allele": row.alt_allele,
            }
            for row in rows
        ],
    }


@router.get("/results/variants/{user_id}")
async def get_user_variants(
    user_id: str = Depends(get_verified_user_id),
    search: str | None = Query(None, max_length=20),
    limit: int = Query(100, ge=1, le=500),
    offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Get SNPedia-listed variants from a user's most recent analysis."""

    analysis = await get_latest_analysis(session, user_id)

    # Get total count of user's SNPedia variants
    count_params = {"aid": str(analysis.id), "uid": user_id}
    count_sql = "SELECT COUNT(*) FROM user_variants WHERE analysis_id = :aid AND user_id = :uid"
    if search:
        count_sql += r" AND rsid LIKE :search ESCAPE '\'"
        escaped = search.replace("\\", "\\\\").replace("%", r"\%").replace("_", r"\_")
        count_params["search"] = f"{escaped}%"
    total_result = await session.execute(text(count_sql), count_params)
    total = total_result.scalar()

    # Get total SNPedia coverage
    snpedia_total_result = await session.execute(text("SELECT COUNT(*) FROM snpedia_snps"))
    snpedia_total = snpedia_total_result.scalar()

    # Get paginated variants
    query = select(UserVariant).where(
        UserVariant.analysis_id == analysis.id,
        UserVariant.user_id == user_id,
    )
    if search:
        query = query.where(UserVariant.rsid.startswith(search))
    query = query.order_by(UserVariant.rsid).offset(offset).limit(limit)

    result = await session.execute(query)
    variants = result.scalars().all()

    return {
        "analysis_id": str(analysis.id),
        "filename": analysis.filename,
        "total": total,
        "snpedia_total": snpedia_total,
        "offset": offset,
        "variants": [{"rsid": v.rsid} for v in variants],
    }


@router.get("/results/featured-snps/{user_id}")
async def get_user_featured_snps(
    user_id: str = Depends(get_verified_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get featured SNPs the user has, with their genotype and risk info."""

    analysis = await get_latest_analysis(session, user_id)

    # Get all featured SNP rsids (those with trait associations)
    featured_result = await session.execute(
        text("SELECT DISTINCT rsid FROM snp_trait_associations")
    )
    featured_rsids = {row.rsid for row in featured_result}

    if not featured_rsids:
        return {"snps": []}

    # Get user's trait hits for featured SNPs (has genotype + risk level)
    hits_result = await session.execute(
        select(UserSnpTraitHit).where(
            UserSnpTraitHit.analysis_id == analysis.id,
            UserSnpTraitHit.user_id == user_id,
            UserSnpTraitHit.rsid.in_(featured_rsids),
        )
    )
    hits = hits_result.scalars().all()

    # Group hits by rsid
    hit_map: dict[str, dict] = {}
    for h in hits:
        if h.rsid not in hit_map:
            hit_map[h.rsid] = {
                "rsid": h.rsid,
                "user_genotype": h.user_genotype,
                "traits": [],
            }
        hit_map[h.rsid]["traits"].append({
            "trait": h.trait,
            "risk_level": h.risk_level,
            "evidence_level": h.evidence_level,
            "effect_description": h.effect_description,
        })

    # Also check user_variants for featured SNPs the user has but maybe no trait hit
    uv_result = await session.execute(
        select(UserVariant.rsid).where(
            UserVariant.analysis_id == analysis.id,
            UserVariant.user_id == user_id,
            UserVariant.rsid.in_(featured_rsids),
        )
    )
    user_featured_rsids = {row.rsid for row in uv_result}

    # Merge: trait hits take priority, but also include rsids with no trait hit
    for rsid in user_featured_rsids:
        if rsid not in hit_map:
            hit_map[rsid] = {
                "rsid": rsid,
                "user_genotype": None,
                "traits": [],
            }

    return {"snps": list(hit_map.values())}


@router.get("/results/pgx/{user_id}")
async def get_pgx_results(
    user_id: str = Depends(get_verified_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get pharmacogenomics results for a user from their most recent completed analysis."""

    from app.services.pgx_matcher import PGX_SKIP_GENES

    analysis = await get_latest_analysis(session, user_id)
    results = await fetch_pgx_rows(session, str(analysis.id), user_id)
    results = [r for r in results if r["gene"] not in PGX_SKIP_GENES]

    # Batch-fetch and attach defining variants
    default_alleles = await fetch_pgx_default_alleles(session)
    await attach_defining_variants(session, results, default_alleles)

    # Match CPIC/DPWG drug guidelines to results
    guidelines_map = await match_guidelines(session, results)
    for r in results:
        gl = guidelines_map.get(r["gene"], {"cpic": [], "dpwg": []})
        r["guidelines"] = gl if (gl["cpic"] or gl["dpwg"]) else None

    # Fetch all SNPs in each gene's panel
    gene_list = [r["gene"] for r in results]
    panel_snps_map = await fetch_pgx_panel_snps(session, gene_list)
    for r in results:
        r["panel_snps"] = panel_snps_map.get(r["gene"], [])

    return {
        "analysis_id": str(analysis.id),
        "results": results,
    }


@router.get("/results/pgx/{user_id}/gene/{gene}")
async def get_pgx_gene_detail(
    gene: str,
    user_id: str = Depends(get_verified_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get detailed pharmacogenomics data for a single gene."""
    from app.services.pgx_matcher import PGX_SKIP_GENES

    if gene in PGX_SKIP_GENES:
        raise HTTPException(status_code=404, detail="Gene result not found")

    analysis = await get_latest_analysis(session, user_id)

    # Fetch user result for this gene
    all_rows = await fetch_pgx_rows(session, str(analysis.id), user_id)
    gene_result = next((r for r in all_rows if r["gene"] == gene), None)
    if not gene_result:
        raise HTTPException(status_code=404, detail="Gene result not found")

    # Attach defining variants
    default_alleles = await fetch_pgx_default_alleles(session)
    await attach_defining_variants(session, [gene_result], default_alleles)

    # Match CPIC/DPWG guidelines
    guidelines_map = await match_guidelines(session, [gene_result])
    gl = guidelines_map.get(gene, {"cpic": [], "dpwg": []})
    gene_result["guidelines"] = gl if (gl["cpic"] or gl["dpwg"]) else None

    return {
        "gene": gene,
        "gene_description": gene_result.get("gene_description"),
        "user_result": gene_result,
    }


@router.get("/results/carrier-status/{user_id}")
async def get_carrier_status_results(
    user_id: str = Depends(get_verified_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get carrier status screening results for a user."""

    analysis = await get_latest_analysis(session, user_id)

    cs_result = await session.execute(
        select(UserCarrierStatusResult).where(
            UserCarrierStatusResult.analysis_id == analysis.id,
            UserCarrierStatusResult.user_id == user_id,
        )
    )
    cs = cs_result.scalar_one_or_none()

    if not cs:
        return {"analysis_id": str(analysis.id), "result": None}

    return {
        "analysis_id": str(analysis.id),
        "result": {
            "results_json": cs.results_json,
            "n_genes_screened": cs.n_genes_screened,
            "n_carrier_genes": cs.n_carrier_genes,
            "n_affected_flags": cs.n_affected_flags,
            "computed_at": cs.computed_at.isoformat() if cs.computed_at else None,
        },
    }



@router.get("/results/gwas/{user_id}")
async def get_gwas_results(
    user_id: str = Depends(get_verified_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Get GWAS-hit PRS results for a user, grouped by disease category."""

    analysis = await get_latest_analysis(session, user_id)

    # Determine status (GWAS scores are computed alongside PRS in background)
    if analysis.status == "complete":
        gwas_status = "ready"
    elif analysis.status == "done" and analysis.error_message:
        gwas_status = "failed"
    else:
        gwas_status = "computing"

    # Fetch results with study metadata
    result = await session.execute(
        select(GwasPrsResult, GwasStudy)
        .join(GwasStudy, GwasPrsResult.study_id == GwasStudy.study_id)
        .where(
            GwasPrsResult.analysis_id == analysis.id,
            GwasPrsResult.user_id == user_id,
        )
        .order_by(GwasStudy.category, GwasStudy.trait)
    )
    rows = result.all()

    # Group by category
    by_category: dict[str, list] = defaultdict(list)
    for gwas_result, study in rows:
        by_category[study.category or "other"].append({
            "study_id": study.study_id,
            "trait": study.trait,
            "category": study.category,
            "citation": study.citation,
            "pmid": study.pmid,
            "n_snps_in_score": study.n_snps,
            "raw_score": gwas_result.raw_score,
            "percentile": gwas_result.percentile,
            "z_score": gwas_result.z_score,
            "ref_mean": gwas_result.ref_mean,
            "ref_std": gwas_result.ref_std,
            "ancestry_group_used": gwas_result.ancestry_group_used,
            "n_variants_matched": gwas_result.n_variants_matched,
            "n_variants_total": gwas_result.n_variants_total,
        })

    return {
        "analysis_id": str(analysis.id),
        "gwas_status": gwas_status,
        "total_scores": len(rows),
        "categories": dict(by_category),
    }
