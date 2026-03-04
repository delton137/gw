"""Account endpoints — PDF report download and data deletion."""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import get_current_user_id
from app.db import get_session
from app.models.carrier_status import UserCarrierStatusResult
from app.models.pgx import PgxGeneDefinition, PgxStarAlleleDefinition
from app.models.user import Analysis, UserSnpTraitHit
from app.routes._helpers import (
    build_defining_variants_by_gene,
    fetch_pgx_default_alleles,
    fetch_pgx_rows,
    get_latest_analysis,
)
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
