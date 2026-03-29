"""Sitemap data endpoints — unauthenticated, used by Next.js sitemap generation."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.gene import Gene
from app.models.snp import Snp, SnpediaSnp

router = APIRouter()

PAGE_SIZE_MAX = 50_000


@router.get("/sitemap/snps")
async def sitemap_snps(
    page: int = Query(0, ge=0),
    size: int = Query(50_000, ge=1, le=PAGE_SIZE_MAX),
    session: AsyncSession = Depends(get_session),
):
    """Return paginated rsids for SNP sitemap (SNPedia rsids that have data in snps table)."""
    count_result = await session.execute(
        text("""
            SELECT COUNT(*) FROM snpedia_snps s
            JOIN snps n ON s.rsid = n.rsid
        """)
    )
    total = count_result.scalar()

    result = await session.execute(
        text("""
            SELECT s.rsid FROM snpedia_snps s
            JOIN snps n ON s.rsid = n.rsid
            ORDER BY s.rsid
            LIMIT :size OFFSET :offset
        """).bindparams(size=size, offset=page * size)
    )
    rsids = [row.rsid for row in result]

    return {"rsids": rsids, "total": total, "page": page}


@router.get("/sitemap/genes")
async def sitemap_genes(
    page: int = Query(0, ge=0),
    size: int = Query(50_000, ge=1, le=PAGE_SIZE_MAX),
    session: AsyncSession = Depends(get_session),
):
    """Return paginated gene symbols for gene sitemap."""
    count_result = await session.execute(select(func.count()).select_from(Gene))
    total = count_result.scalar()

    result = await session.execute(
        select(Gene.symbol).order_by(Gene.symbol).limit(size).offset(page * size)
    )
    symbols = [row.symbol for row in result]

    return {"symbols": symbols, "total": total, "page": page}
