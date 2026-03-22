"""Account endpoints — report download and data deletion."""

from __future__ import annotations

import logging
from collections import defaultdict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import delete, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id
from app.db import get_session
from app.models.carrier_status import UserCarrierStatusResult
from app.models.gwas import GwasPrsResult, GwasStudy
from app.models.pgx import PgxGeneDefinition, PgxStarAlleleDefinition
from app.models.snp import Snp
from app.models.user import Analysis, UserClinvarHit, UserSnpTraitHit, UserVariant
from app.routes._helpers import (
    build_defining_variants_by_gene,
    fetch_pgx_default_alleles,
    fetch_pgx_panel_snps,
    fetch_pgx_rows,
    fetch_prs_results,
    get_latest_analysis,
)
from app.services.html_report import generate_html_report
from app.services.pgx_guidelines import match_guidelines
from app.services.pgx_matcher import _load_drug_cache
from app.services.pgx_report import generate_pgx_report_pdf
from app.services.report import generate_report_pdf

log = logging.getLogger(__name__)

router = APIRouter()


@router.get("/report/download")
async def download_report(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Generate and return a PDF report of the user's most recent analysis."""
    analysis = await get_latest_analysis(session, user_id)

    analysis_dict = {
        "chip_type": analysis.chip_type,
        "variant_count": analysis.variant_count,
        "detected_ancestry": analysis.detected_ancestry,
        "ancestry_method": analysis.ancestry_method,
        "ancestry_confidence": analysis.ancestry_confidence,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
    }

    # Get trait hits
    hits_result = await session.execute(
        select(UserSnpTraitHit).where(
            UserSnpTraitHit.analysis_id == analysis.id,
            UserSnpTraitHit.user_id == user_id,
        )
    )
    hits = hits_result.scalars().all()
    trait_hits = [
        {
            "rsid": h.rsid,
            "user_genotype": h.user_genotype,
            "trait": h.trait,
            "effect_description": h.effect_description,
            "risk_level": h.risk_level,
            "evidence_level": h.evidence_level,
        }
        for h in hits
    ]

    # Get carrier status
    cs_result = await session.execute(
        select(UserCarrierStatusResult).where(
            UserCarrierStatusResult.analysis_id == analysis.id,
            UserCarrierStatusResult.user_id == user_id,
        )
    )
    cs = cs_result.scalar_one_or_none()
    carrier_status = None
    if cs:
        carrier_status = {
            "results_json": cs.results_json,
            "n_genes_screened": cs.n_genes_screened,
            "n_carrier_genes": cs.n_carrier_genes,
            "n_affected_flags": cs.n_affected_flags,
        }

    pdf_bytes = generate_report_pdf(analysis_dict, carrier_status, trait_hits)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=genewizard-report.pdf",
        },
    )


@router.get("/report/pgx/download")
async def download_pgx_report(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Generate and return a PGX PDF report of the user's most recent analysis."""
    analysis = await get_latest_analysis(session, user_id)
    pgx_results = await fetch_pgx_rows(session, str(analysis.id), user_id)

    # Build analysis dict with PGX-specific variant count (not total file variants)
    pgx_variants_tested = sum(r["n_variants_tested"] for r in pgx_results)
    analysis_dict = {
        "chip_type": analysis.chip_type,
        "variant_count": pgx_variants_tested,
    }

    # Gene definitions for interpretation section
    gene_def_result = await session.execute(select(PgxGeneDefinition))
    gene_defs = {
        g.gene: {"description": g.description, "calling_method": g.calling_method}
        for g in gene_def_result.scalars().all()
    }

    # Drug annotations 
    drug_cache = _load_drug_cache()

    # Match CPIC/DPWG guidelines to PGX results
    guidelines_map = await match_guidelines(session, pgx_results)
    for r in pgx_results:
        gl = guidelines_map.get(r["gene"], {"cpic": [], "dpwg": []})
        r["guidelines"] = gl if (gl["cpic"] or gl["dpwg"]) else None

    # Star allele rsIDs per gene (panel SNPs)
    sa_result = await session.execute(
        select(
            PgxStarAlleleDefinition.gene,
            PgxStarAlleleDefinition.rsid,
        )
    )
    star_allele_rsids: dict[str, list[str]] = {}
    for row in sa_result:
        star_allele_rsids.setdefault(row.gene, []).append(row.rsid)

    # Defining variants per gene (non-default alleles)
    default_alleles = await fetch_pgx_default_alleles(session)
    defining_variants = await build_defining_variants_by_gene(
        session, pgx_results, default_alleles,
    )

    pdf_bytes = generate_pgx_report_pdf(
        analysis=analysis_dict,
        pgx_results=pgx_results,
        gene_definitions=gene_defs,
        drug_annotations=drug_cache,
        star_allele_rsids=star_allele_rsids,
        defining_variants=defining_variants,
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": "attachment; filename=genewizard-pgx-report.pdf",
        },
    )


@router.get("/report/html/download")
async def download_html_report(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Generate and return a comprehensive HTML report of all analysis results."""
    analysis = await get_latest_analysis(session, user_id)
    analysis_id = str(analysis.id)

    analysis_dict = {
        "chip_type": analysis.chip_type,
        "variant_count": analysis.variant_count,
        "filename": analysis.filename,
        "genome_build": analysis.genome_build,
        "file_format": analysis.file_format,
        "created_at": analysis.created_at.isoformat() if analysis.created_at else None,
        "pipeline_fast_seconds": getattr(analysis, "pipeline_fast_seconds", None),
        "is_imputed": getattr(analysis, "is_imputed", False),
    }

    # Ancestry
    ancestry = analysis.detected_ancestry  # rich dict or None

    # Determine PRS/GWAS status
    if analysis.status == "complete":
        prs_status = gwas_status = "ready"
    elif analysis.status in ("done", "scoring_prs"):
        prs_status = gwas_status = "computing"
    else:
        prs_status = gwas_status = "not_available"

    # --- Fetch all results ---

    # Trait hits
    hits_result = await session.execute(
        select(UserSnpTraitHit).where(
            UserSnpTraitHit.analysis_id == analysis.id,
            UserSnpTraitHit.user_id == user_id,
        )
    )
    trait_hits = [
        {
            "rsid": h.rsid,
            "gene": getattr(h, "gene", None),
            "user_genotype": h.user_genotype,
            "trait": h.trait,
            "effect_description": h.effect_description,
            "risk_level": h.risk_level,
            "evidence_level": h.evidence_level,
        }
        for h in hits_result.scalars().all()
    ]

    # Carrier status
    cs_result = await session.execute(
        select(UserCarrierStatusResult).where(
            UserCarrierStatusResult.analysis_id == analysis.id,
            UserCarrierStatusResult.user_id == user_id,
        )
    )
    cs = cs_result.scalar_one_or_none()
    carrier_status = None
    if cs:
        carrier_status = {
            "results_json": cs.results_json,
            "n_genes_screened": cs.n_genes_screened,
            "n_carrier_genes": cs.n_carrier_genes,
            "n_affected_flags": cs.n_affected_flags,
        }

    # PGx results + guidelines + defining variants
    pgx_results = await fetch_pgx_rows(session, analysis_id, user_id)
    guidelines_map = await match_guidelines(session, pgx_results)
    for r in pgx_results:
        gl = guidelines_map.get(r["gene"], {"cpic": [], "dpwg": []})
        r["guidelines"] = gl if (gl["cpic"] or gl["dpwg"]) else None

    genes = [r["gene"] for r in pgx_results]
    star_allele_rsids = await fetch_pgx_panel_snps(session, genes)
    default_alleles = await fetch_pgx_default_alleles(session)
    defining_variants = await build_defining_variants_by_gene(
        session, pgx_results, default_alleles,
    )

    # PRS results
    prs_results = []
    if prs_status in ("ready", "computing"):
        prs_results = await fetch_prs_results(session, analysis_id, user_id)

    # ClinVar: counts by significance + top actionable hits
    clinvar_counts: dict[str, int] = {}
    clinvar_hits: list[dict] = []
    count_result = await session.execute(
        text("""
            SELECT s.clinvar_significance, COUNT(*) as cnt
            FROM user_clinvar_hits uch
            JOIN snps s ON uch.rsid = s.rsid
            WHERE uch.user_id = :uid AND uch.analysis_id = :aid
              AND s.clinvar_significance IS NOT NULL
            GROUP BY s.clinvar_significance
        """),
        {"uid": user_id, "aid": analysis_id},
    )
    clinvar_counts = {row.clinvar_significance: row.cnt for row in count_result}

    if clinvar_counts:
        # Fetch top actionable hits (pathogenic, likely_pathogenic, risk_factor)
        actionable_sigs = ("pathogenic", "likely_pathogenic", "risk_factor")
        cv_query = (
            select(
                UserClinvarHit.rsid,
                UserClinvarHit.user_genotype,
                Snp.gene,
                Snp.clinvar_significance,
                Snp.clinvar_conditions,
                Snp.clinvar_review_stars,
            )
            .join(Snp, UserClinvarHit.rsid == Snp.rsid)
            .where(
                UserClinvarHit.user_id == user_id,
                UserClinvarHit.analysis_id == analysis.id,
                Snp.clinvar_significance.in_(actionable_sigs),
            )
            .order_by(
                text("""CASE clinvar_significance
                    WHEN 'pathogenic' THEN 0
                    WHEN 'likely_pathogenic' THEN 1
                    WHEN 'risk_factor' THEN 2
                    ELSE 3
                END"""),
                Snp.gene,
            )
            .limit(150)  # fetch a bit more than cap for overflow count
        )
        cv_result = await session.execute(cv_query)
        clinvar_hits = [
            {
                "rsid": row.rsid,
                "gene": row.gene,
                "user_genotype": row.user_genotype,
                "clinvar_significance": row.clinvar_significance,
                "clinvar_conditions": row.clinvar_conditions,
                "review_stars": row.clinvar_review_stars,
            }
            for row in cv_result
        ]

    # GWAS results grouped by category
    gwas_categories: dict[str, list[dict]] = {}
    if gwas_status in ("ready", "computing"):
        gwas_result = await session.execute(
            select(GwasPrsResult, GwasStudy)
            .join(GwasStudy, GwasPrsResult.study_id == GwasStudy.study_id)
            .where(
                GwasPrsResult.analysis_id == analysis.id,
                GwasPrsResult.user_id == user_id,
            )
            .order_by(GwasStudy.category, GwasStudy.trait)
        )
        for gwas_row, study in gwas_result.all():
            cat = study.category or "other"
            gwas_categories.setdefault(cat, []).append({
                "study_id": study.study_id,
                "trait": study.trait,
                "category": cat,
                "citation": study.citation,
                "pmid": study.pmid,
                "percentile": gwas_row.percentile,
                "n_variants_matched": gwas_row.n_variants_matched,
                "n_variants_total": gwas_row.n_variants_total,
                "ancestry_group_used": gwas_row.ancestry_group_used,
                "raw_score": gwas_row.raw_score,
            })

    # SNPedia variant count
    snpedia_result = await session.execute(
        select(func.count()).select_from(UserVariant).where(
            UserVariant.analysis_id == analysis.id,
            UserVariant.user_id == user_id,
        )
    )
    snpedia_count = snpedia_result.scalar() or 0

    html = generate_html_report(
        analysis=analysis_dict,
        ancestry=ancestry,
        carrier_status=carrier_status,
        pgx_results=pgx_results,
        pgx_star_allele_rsids=star_allele_rsids,
        pgx_defining_variants=defining_variants,
        clinvar_counts=clinvar_counts,
        clinvar_hits=clinvar_hits,
        prs_results=prs_results,
        prs_status=prs_status,
        gwas_categories=gwas_categories,
        gwas_status=gwas_status,
        trait_hits=trait_hits,
        snpedia_count=snpedia_count,
    )

    return Response(
        content=html,
        media_type="text/html",
        headers={
            "Content-Disposition": "attachment; filename=genewizard-comprehensive-report.html",
        },
    )


@router.delete("/account/data")
async def delete_all_user_data(
    user_id: str = Depends(get_current_user_id),
    session: AsyncSession = Depends(get_session),
):
    """Delete all stored data for the authenticated user.

    Removes all analyses and cascades to all child tables (PRS results, trait hits,
    variants, PGX results, carrier status). This is irreversible.
    Raw genotype data was never stored, so this fully removes the user's footprint.
    """
    # CASCADE FKs on all child tables handle cleanup automatically
    result = await session.execute(
        delete(Analysis).where(Analysis.user_id == user_id)
    )
    await session.commit()

    n_deleted = result.rowcount
    log.info("Deleted %d analyses (+ cascaded children) for user %s", n_deleted, user_id)

    return {
        "message": "All your data has been permanently deleted.",
        "deleted": {"analyses": n_deleted},
    }
