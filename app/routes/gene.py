"""Public Gene endpoints — unauthenticated."""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.gene import Gene
from app.models.snp import Snp, SnpTraitAssociation

router = APIRouter()

# Load carrier panel gene list once
_carrier_panel_path = Path(__file__).resolve().parent.parent / "data" / "carrier_panel.json"
_CARRIER_GENES: set[str] = set()
if _carrier_panel_path.exists():
    with open(_carrier_panel_path) as f:
        _panel = json.load(f)
        _CARRIER_GENES = {g["gene"] for g in _panel.get("genes", [])}


@router.get("/gene/featured")
async def get_featured_genes(
    session: AsyncSession = Depends(get_session),
):
    """Get high-interest genes with ClinVar stats."""
    # Return genes that have the most pathogenic variants and an OMIM number
    result = await session.execute(
        select(Gene)
        .where(Gene.clinvar_pathogenic_count.is_not(None))
        .where(Gene.clinvar_pathogenic_count > 0)
        .where(Gene.name.is_not(None))
        .order_by(Gene.clinvar_pathogenic_count.desc())
        .limit(50)
    )
    genes = result.scalars().all()

    return {
        "genes": [
            {
                "symbol": g.symbol,
                "name": g.name,
                "omim_number": g.omim_number,
                "clinvar_total_variants": g.clinvar_total_variants,
                "clinvar_pathogenic_count": g.clinvar_pathogenic_count,
                "is_pharmacogene": False,  # populated below
                "in_carrier_panel": g.symbol in _CARRIER_GENES,
            }
            for g in genes
        ],
    }


@router.get("/gene/search")
async def search_genes(
    q: str = Query(..., min_length=1, max_length=100),
    limit: int = Query(20, ge=1, le=100),
    session: AsyncSession = Depends(get_session),
):
    """Search genes by symbol or name (partial match)."""
    q_escaped = q.replace("%", r"\%").replace("_", r"\_")

    # Prefer exact symbol match first, then partial
    result = await session.execute(
        select(Gene)
        .where(
            (Gene.symbol.ilike(f"%{q_escaped}%"))
            | (Gene.name.ilike(f"%{q_escaped}%"))
        )
        .order_by(
            # Exact symbol match first
            (func.lower(Gene.symbol) == q.lower()).desc(),
            # Then by pathogenic variant count (more relevant genes first)
            Gene.clinvar_pathogenic_count.desc().nulls_last(),
        )
        .limit(limit)
    )
    genes = result.scalars().all()

    return {
        "total": len(genes),
        "genes": [
            {
                "symbol": g.symbol,
                "name": g.name,
                "omim_number": g.omim_number,
                "clinvar_total_variants": g.clinvar_total_variants,
                "clinvar_pathogenic_count": g.clinvar_pathogenic_count,
            }
            for g in genes
        ],
    }


@router.get("/gene/{symbol}")
async def get_gene(
    symbol: str,
    snp_limit: int = Query(50, ge=1, le=500),
    snp_offset: int = Query(0, ge=0),
    session: AsyncSession = Depends(get_session),
):
    """Get gene detail page data with SNPs and cross-references."""
    if len(symbol) > 50:
        raise HTTPException(status_code=400, detail="Invalid gene symbol")

    # Look up gene (case-insensitive)
    result = await session.execute(
        select(Gene).where(func.upper(Gene.symbol) == symbol.upper())
    )
    gene = result.scalar_one_or_none()
    if not gene:
        raise HTTPException(status_code=404, detail="Gene not found")

    # Get SNPs in this gene (paginated)
    snps_result = await session.execute(
        select(Snp)
        .where(Snp.gene == gene.symbol)
        .order_by(Snp.position)
        .offset(snp_offset)
        .limit(snp_limit)
    )
    snps = snps_result.scalars().all()

    # Total SNP count for this gene
    count_result = await session.execute(
        select(func.count()).select_from(Snp).where(Snp.gene == gene.symbol)
    )
    total_snps = count_result.scalar()

    # Check if this is a pharmacogene
    pgx_result = await session.execute(
        text("SELECT gene FROM pgx_gene_definitions WHERE gene = :symbol"),
        {"symbol": gene.symbol},
    )
    is_pharmacogene = pgx_result.scalar_one_or_none() is not None

    # Get aggregate trait associations for all SNPs in this gene
    trait_result = await session.execute(
        select(
            SnpTraitAssociation.trait,
            func.count().label("snp_count"),
        )
        .where(SnpTraitAssociation.rsid.in_(
            select(Snp.rsid).where(Snp.gene == gene.symbol)
        ))
        .group_by(SnpTraitAssociation.trait)
        .order_by(func.count().desc())
        .limit(20)
    )
    traits = [{"trait": row.trait, "snp_count": row.snp_count} for row in trait_result]

    return {
        "symbol": gene.symbol,
        "name": gene.name,
        "summary": gene.summary,
        "ncbi_gene_id": gene.ncbi_gene_id,
        "omim_number": gene.omim_number,
        "clinvar_stats": {
            "total_variants": gene.clinvar_total_variants,
            "pathogenic_count": gene.clinvar_pathogenic_count,
            "uncertain_count": gene.clinvar_uncertain_count,
            "conflicting_count": gene.clinvar_conflicting_count,
            "total_submissions": gene.clinvar_total_submissions,
        },
        "is_pharmacogene": is_pharmacogene,
        "in_carrier_panel": gene.symbol in _CARRIER_GENES,
        "traits": traits,
        "snps": {
            "total": total_snps,
            "offset": snp_offset,
            "items": [
                {
                    "rsid": s.rsid,
                    "chrom": s.chrom,
                    "position": s.position,
                    "ref_allele": s.ref_allele,
                    "alt_allele": s.alt_allele,
                    "functional_class": s.functional_class,
                    "clinvar_significance": s.clinvar_significance,
                    "maf_global": s.maf_global,
                }
                for s in snps
            ],
        },
    }
