"""Public SNP endpoints — unauthenticated."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.db import get_session
from app.models.gene import Gene
from app.models.snp import Snp, SnpTraitAssociation

router = APIRouter()


@router.get("/snp/featured")
async def get_featured_snps(
    session: AsyncSession = Depends(get_session),
):
    """Get all SNPs that have curated trait associations, with a summary."""
    result = await session.execute(
        text("""
            SELECT s.rsid, s.chrom, s.position, s.gene, s.functional_class, s.maf_global,
                   s.ref_allele, s.alt_allele,
                   a.trait, a.effect_description, a.evidence_level, a.risk_allele
            FROM snps s
            JOIN snp_trait_associations a ON s.rsid = a.rsid
            ORDER BY s.gene, s.rsid, a.trait
        """)
    )
    rows = result.all()

    # Group by rsid
    snps: dict[str, dict] = {}
    for row in rows:
        if row.rsid not in snps:
            snps[row.rsid] = {
                "rsid": row.rsid,
                "chrom": row.chrom,
                "position": row.position,
                "gene": row.gene,
                "functional_class": row.functional_class,
                "maf_global": row.maf_global,
                "ref_allele": row.ref_allele,
                "alt_allele": row.alt_allele,
                "traits": [],
            }
        snps[row.rsid]["traits"].append({
            "trait": row.trait,
            "summary": (row.effect_description or "")[:200],
            "evidence_level": row.evidence_level,
            "risk_allele": row.risk_allele,
        })

    return {"snps": list(snps.values())}


@router.get("/snp/{rsid}")
async def get_snp(
    rsid: str,
    session: AsyncSession = Depends(get_session),
):
    """Get SNP info + trait associations + PRS scores it appears in."""
    # Validate rsid format
    if len(rsid) > 20 or not rsid.startswith("rs") or not rsid[2:].isdigit():
        raise HTTPException(status_code=400, detail="Invalid rsid format")

    # Get SNP info (may not exist in our knowledge base yet)
    snp_result = await session.execute(select(Snp).where(Snp.rsid == rsid))
    snp = snp_result.scalar_one_or_none()

    # Build response — minimal if SNP not in our DB, full if it is
    # Look up gene info if we have a gene symbol
    gene_info = None
    if snp and snp.gene:
        gene_result = await session.execute(select(Gene).where(Gene.symbol == snp.gene))
        gene = gene_result.scalar_one_or_none()
        if gene:
            gene_info = {
                "symbol": gene.symbol,
                "name": gene.name,
                "summary": gene.summary,
                "omim_number": gene.omim_number,
                "ncbi_gene_id": gene.ncbi_gene_id,
                "clinvar_total_variants": gene.clinvar_total_variants,
                "clinvar_pathogenic_count": gene.clinvar_pathogenic_count,
            }

    response: dict = {
        "rsid": rsid,
        "chrom": snp.chrom if snp else None,
        "position": snp.position if snp else None,
        "ref_allele": snp.ref_allele if snp else None,
        "alt_allele": snp.alt_allele if snp else None,
        "gene": snp.gene if snp else None,
        "functional_class": snp.functional_class if snp else None,
        "maf_global": snp.maf_global if snp else None,
        "in_database": snp is not None,
        "gene_info": gene_info,
        "trait_associations": [],

        # Enriched annotations
        "pathogenicity": None,
        "clinvar": None,
        "hgvs": None,
        "population_frequencies": None,
    }

    if snp:
        # Pathogenicity scores (CADD, SIFT, PolyPhen, REVEL)
        has_patho = any([snp.cadd_phred, snp.sift_category, snp.polyphen_category, snp.revel_score])
        if has_patho:
            response["pathogenicity"] = {
                "cadd_phred": snp.cadd_phred,
                "sift": {"category": snp.sift_category, "score": snp.sift_score}
                    if snp.sift_category else None,
                "polyphen": {"category": snp.polyphen_category, "score": snp.polyphen_score}
                    if snp.polyphen_category else None,
                "revel_score": snp.revel_score,
            }

        # ClinVar
        if snp.clinvar_significance:
            response["clinvar"] = {
                "significance": snp.clinvar_significance,
                "conditions": snp.clinvar_conditions,
                "review_stars": snp.clinvar_review_stars,
                "allele_id": snp.clinvar_allele_id,
                "submitter_count": snp.clinvar_submitter_count,
                "citation_count": snp.clinvar_citation_count,
            }

        # HGVS notation
        if snp.hgvs_coding or snp.hgvs_protein:
            response["hgvs"] = {
                "coding": snp.hgvs_coding,
                "protein": snp.hgvs_protein,
            }

        # gnomAD population frequencies
        pop_freqs = {
            "african": snp.gnomad_afr,
            "east_asian": snp.gnomad_eas,
            "european": snp.gnomad_nfe,
            "south_asian": snp.gnomad_sas,
            "latino": snp.gnomad_amr,
            "finnish": snp.gnomad_fin,
            "ashkenazi_jewish": snp.gnomad_asj,
        }
        if any(v is not None for v in pop_freqs.values()):
            response["population_frequencies"] = pop_freqs

    if snp:
        # Get trait associations
        assoc_result = await session.execute(
            select(SnpTraitAssociation).where(SnpTraitAssociation.rsid == rsid)
        )
        associations = assoc_result.scalars().all()

        response["trait_associations"] = [
            {
                "id": str(a.id),
                "trait": a.trait,
                "risk_allele": a.risk_allele,
                "odds_ratio": a.odds_ratio,
                "beta": a.beta,
                "p_value": a.p_value,
                "effect_description": a.effect_description,
                "evidence_level": a.evidence_level,
                "source_pmid": a.source_pmid,
                "source_title": a.source_title,
                "trait_prevalence": a.trait_prevalence,
            }
            for a in associations
        ]


    return response


@router.get("/snp/")
async def search_snps(
    gene: str | None = Query(None, max_length=50),
    trait: str | None = Query(None, max_length=100),
    chrom: str | None = Query(None, max_length=5),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0, le=10000),
    session: AsyncSession = Depends(get_session),
):
    """Search SNPs by gene, trait, or chromosome."""
    if not any([gene, trait, chrom]):
        raise HTTPException(status_code=400, detail="Provide at least one filter: gene, trait, or chrom")

    query = select(Snp)
    if trait:
        query = query.join(SnpTraitAssociation, Snp.rsid == SnpTraitAssociation.rsid)
        query = query.where(SnpTraitAssociation.trait.ilike(
            "%" + trait.replace("%", r"\%").replace("_", r"\_") + "%"
        ))
    if gene:
        query = query.where(Snp.gene == gene)
    if chrom:
        query = query.where(Snp.chrom == chrom)
    query = query.offset(offset).limit(limit)
    result = await session.execute(query)
    snps = result.scalars().all()

    return {
        "total": len(snps),
        "offset": offset,
        "snps": [
            {
                "rsid": s.rsid,
                "chrom": s.chrom,
                "position": s.position,
                "gene": s.gene,
                "ref_allele": s.ref_allele,
                "alt_allele": s.alt_allele,
            }
            for s in snps
        ],
    }
