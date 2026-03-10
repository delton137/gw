"""Export demo analysis data as a TypeScript module.

One-time script that queries the database directly to capture real analysis
results, sanitizes PII (user_id, analysis_id, filename), and writes a typed
TypeScript file for the /demo page.

Usage:
    source .venv/bin/activate
    python -m scripts.export_demo_data
"""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.carrier_status import UserCarrierStatusResult
from app.models.user import Analysis, UserSnpTraitHit, UserVariant
from app.models.snp import Snp, SnpTraitAssociation
from app.routes._helpers import (
    fetch_prs_results,
    fetch_pgx_rows,
    fetch_pgx_default_alleles,
    attach_defining_variants,
    fetch_pgx_panel_snps,
)
from app.services.pgx_guidelines import match_guidelines
from app.services.pgx_matcher import PGX_SKIP_GENES

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

USER_ID = "user_3AA85FWDsOwTGXUvnx9nbbWvehF"
ANALYSIS_ID = "8a332039-d0dd-42b1-8899-03e94e64ac01"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "frontend" / "src" / "app" / "demo" / "demoData.ts"

# PII replacements
SANITIZE = {
    USER_ID: "demo_user",
    ANALYSIS_ID: "demo_analysis",
}


def sanitize(obj):
    """Recursively replace PII strings in a JSON-serializable object."""
    if isinstance(obj, str):
        for old, new in SANITIZE.items():
            obj = obj.replace(old, new)
        return obj
    if isinstance(obj, dict):
        return {k: sanitize(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [sanitize(v) for v in obj]
    return obj


def to_ts_const(name: str, type_hint: str, data) -> str:
    """Format a TypeScript export const with type annotation."""
    json_str = json.dumps(data, indent=2, ensure_ascii=False)
    return f"export const {name}: {type_hint} = {json_str};\n"


async def export_analysis(session: AsyncSession) -> dict:
    """Export analysis metadata."""
    result = await session.execute(
        select(Analysis).where(Analysis.id == ANALYSIS_ID)
    )
    a = result.scalar_one()

    ancestry = a.detected_ancestry
    if isinstance(ancestry, str):
        ancestry = json.loads(ancestry)

    return {
        "id": str(a.id),
        "chip_type": a.chip_type,
        "variant_count": a.variant_count,
        "status": a.status,
        "error_message": None,
        "detected_ancestry": ancestry,
        "ancestry_method": a.ancestry_method,
        "ancestry_confidence": a.ancestry_confidence,
        "selected_ancestry": a.selected_ancestry,
        "filename": a.filename,
        "genome_build": a.genome_build,
        "pipeline_fast_seconds": a.pipeline_fast_seconds,
        "status_detail": a.status_detail,
    }


async def export_traits(session: AsyncSession) -> dict:
    """Export trait hits with association details."""
    # Count total SNPs in knowledge base
    kb_count_result = await session.execute(
        text("SELECT COUNT(DISTINCT rsid) FROM snp_trait_associations")
    )
    total_snps_in_kb = kb_count_result.scalar() or 0

    # Fetch hits joined with association details
    rows = await session.execute(
        text("""
            SELECT h.id, h.rsid, h.user_genotype, h.trait, h.risk_level,
                   h.evidence_level,
                   a.risk_allele, a.effect_description, a.odds_ratio,
                   s.gene
            FROM user_snp_trait_hits h
            JOIN snp_trait_associations a ON h.association_id = a.id
            LEFT JOIN snps s ON h.rsid = s.rsid
            WHERE h.analysis_id = :aid AND h.user_id = :uid
            ORDER BY h.rsid
        """),
        {"aid": ANALYSIS_ID, "uid": USER_ID},
    )

    hits = []
    unique_rsids = set()
    for row in rows:
        unique_rsids.add(row.rsid)
        hits.append({
            "id": str(row.id),
            "rsid": row.rsid,
            "gene": row.gene,
            "user_genotype": row.user_genotype,
            "risk_allele": row.risk_allele,
            "effect_summary": None,
            "trait": row.trait,
            "effect_description": row.effect_description or "",
            "risk_level": row.risk_level,
            "evidence_level": row.evidence_level,
        })

    return {
        "analysis_id": ANALYSIS_ID,
        "total": len(hits),
        "total_snps_in_kb": total_snps_in_kb,
        "unique_snps_matched": len(unique_rsids),
        "offset": 0,
        "hits": hits,
    }


async def export_pgx(session: AsyncSession) -> list[dict]:
    """Export PGx results with guidelines and defining variants."""
    results = await fetch_pgx_rows(session, ANALYSIS_ID, USER_ID)
    results = [r for r in results if r["gene"] not in PGX_SKIP_GENES]

    default_alleles = await fetch_pgx_default_alleles(session)
    await attach_defining_variants(session, results, default_alleles)

    guidelines_map = await match_guidelines(session, results)
    for r in results:
        gl = guidelines_map.get(r["gene"], {"cpic": [], "dpwg": []})
        r["guidelines"] = gl if (gl["cpic"] or gl["dpwg"]) else None

    gene_list = [r["gene"] for r in results]
    panel_snps_map = await fetch_pgx_panel_snps(session, gene_list)
    for r in results:
        r["panel_snps"] = panel_snps_map.get(r["gene"], [])

    return results


async def export_carrier(session: AsyncSession) -> dict | None:
    """Export carrier status results."""
    result = await session.execute(
        select(UserCarrierStatusResult).where(
            UserCarrierStatusResult.analysis_id == ANALYSIS_ID,
            UserCarrierStatusResult.user_id == USER_ID,
        )
    )
    cs = result.scalar_one_or_none()
    if not cs:
        return None
    return {
        "results_json": cs.results_json,
        "n_genes_screened": cs.n_genes_screened,
        "n_carrier_genes": cs.n_carrier_genes,
        "n_affected_flags": cs.n_affected_flags,
        "computed_at": cs.computed_at.isoformat() if cs.computed_at else None,
    }


async def export_variants_summary(session: AsyncSession) -> dict:
    """Export variant count summaries."""
    total_result = await session.execute(
        text("SELECT COUNT(*) FROM user_variants WHERE analysis_id = :aid AND user_id = :uid"),
        {"aid": ANALYSIS_ID, "uid": USER_ID},
    )
    total = total_result.scalar() or 0

    snpedia_result = await session.execute(
        text("SELECT COUNT(*) FROM snpedia_snps")
    )
    snpedia_total = snpedia_result.scalar() or 0

    return {"total": total, "snpedia_total": snpedia_total}


async def export_clinvar_summary(session: AsyncSession) -> dict:
    """Export ClinVar hit counts."""
    rows = await session.execute(
        text("""
            SELECT s.clinvar_significance, COUNT(*) as cnt
            FROM user_variants uv
            JOIN snps s ON uv.rsid = s.rsid
            WHERE uv.analysis_id = :aid AND uv.user_id = :uid
              AND s.clinvar_significance IS NOT NULL
            GROUP BY s.clinvar_significance
        """),
        {"aid": ANALYSIS_ID, "uid": USER_ID},
    )
    counts = {}
    total = 0
    for row in rows:
        counts[row.clinvar_significance] = row.cnt
        total += row.cnt
    return {"total": total, "counts": counts}


async def export_gwas(session: AsyncSession) -> dict:
    """Export GWAS results grouped by category."""
    from collections import defaultdict

    rows = await session.execute(
        text("""
            SELECT r.raw_score, r.percentile, r.z_score,
                   r.ref_mean, r.ref_std, r.ancestry_group_used,
                   r.n_variants_matched, r.n_variants_total,
                   s.study_id, s.trait, s.category, s.citation, s.pmid, s.n_snps
            FROM gwas_prs_results r
            JOIN gwas_studies s ON r.study_id = s.study_id
            WHERE r.analysis_id = :aid AND r.user_id = :uid
            ORDER BY s.category, s.trait
        """),
        {"aid": ANALYSIS_ID, "uid": USER_ID},
    )

    by_category: dict[str, list] = defaultdict(list)
    count = 0
    for row in rows:
        count += 1
        by_category[row.category or "other"].append({
            "study_id": row.study_id,
            "trait": row.trait,
            "category": row.category,
            "citation": row.citation,
            "pmid": row.pmid,
            "n_snps_in_score": row.n_snps,
            "raw_score": row.raw_score,
            "percentile": row.percentile,
            "z_score": row.z_score,
            "ref_mean": row.ref_mean,
            "ref_std": row.ref_std,
            "ancestry_group_used": row.ancestry_group_used,
            "n_variants_matched": row.n_variants_matched,
            "n_variants_total": row.n_variants_total,
        })

    return {
        "analysis_id": ANALYSIS_ID,
        "gwas_status": "ready",
        "total_scores": count,
        "categories": dict(by_category),
    }


async def run():
    engine = create_async_engine(settings.database_url, pool_size=5)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        print("Exporting analysis metadata...", file=sys.stderr)
        analysis = await export_analysis(session)

        print("Exporting PRS results...", file=sys.stderr)
        prs_results = await fetch_prs_results(session, ANALYSIS_ID, USER_ID)
        prs = {
            "analysis_id": ANALYSIS_ID,
            "prs_status": "ready",
            "prs_status_detail": None,
            "selected_ancestry": analysis.get("selected_ancestry"),
            "results": prs_results,
        }

        print("Exporting trait hits...", file=sys.stderr)
        traits = await export_traits(session)

        print("Exporting PGx results...", file=sys.stderr)
        pgx_results = await export_pgx(session)

        print("Exporting carrier status...", file=sys.stderr)
        carrier = await export_carrier(session)

        print("Exporting variant summary...", file=sys.stderr)
        variants_summary = await export_variants_summary(session)

        print("Exporting ClinVar summary...", file=sys.stderr)
        clinvar_summary = await export_clinvar_summary(session)

        print("Exporting GWAS results...", file=sys.stderr)
        gwas = await export_gwas(session)

    await engine.dispose()

    # Strip fields not in TypeScript types (PrsResult has no computed_at)
    for r in prs_results:
        r.pop("computed_at", None)

    # Sanitize all PII
    analysis = sanitize(analysis)
    analysis["filename"] = "sample_wgs.vcf.gz"
    prs = sanitize(prs)
    traits = sanitize(traits)
    pgx_results = sanitize(pgx_results)
    carrier = sanitize(carrier)
    gwas = sanitize(gwas)

    # Write TypeScript file
    print(f"Writing {OUTPUT_PATH}...", file=sys.stderr)

    lines = [
        "/**",
        " * Static demo data exported from a real WGS analysis.",
        " * Generated by scripts/export_demo_data.py -- do not edit manually.",
        " */",
        "",
        "/* eslint-disable */",
        "",
        "import type {",
        "  Analysis, PrsResponse, TraitsResponse, PgxResult,",
        "  CarrierStatusResult, GwasResponse,",
        '} from "@/lib/types";',
        "",
        "",
    ]

    lines.append(to_ts_const("DEMO_ANALYSIS", "Analysis", analysis))
    lines.append("")
    lines.append(to_ts_const("DEMO_PRS", "PrsResponse", prs))
    lines.append("")
    lines.append(to_ts_const("DEMO_TRAITS", "TraitsResponse", traits))
    lines.append("")
    lines.append(to_ts_const("DEMO_PGX", "PgxResult[]", pgx_results))
    lines.append("")
    lines.append(to_ts_const("DEMO_CARRIER", "CarrierStatusResult | null", carrier))
    lines.append("")
    lines.append(to_ts_const(
        "DEMO_VARIANTS_SUMMARY",
        "{ total: number; snpedia_total: number }",
        variants_summary,
    ))
    lines.append("")
    lines.append(to_ts_const(
        "DEMO_CLINVAR_SUMMARY",
        "{ total: number; counts: Record<string, number> }",
        clinvar_summary,
    ))
    lines.append("")
    lines.append(to_ts_const("DEMO_GWAS", "GwasResponse", gwas))
    lines.append("")

    OUTPUT_PATH.write_text("\n".join(lines), encoding="utf-8")

    # Summary
    size_kb = OUTPUT_PATH.stat().st_size / 1024
    print(f"\nDone! Exported to {OUTPUT_PATH}:", file=sys.stderr)
    print(f"  Analysis: {analysis['chip_type']}, {analysis['variant_count']} variants", file=sys.stderr)
    print(f"  PRS: {len(prs['results'])} scores", file=sys.stderr)
    print(f"  Traits: {traits['total']} hits", file=sys.stderr)
    print(f"  PGx: {len(pgx_results)} genes", file=sys.stderr)
    print(f"  Carrier: {carrier['n_genes_screened'] if carrier else 0} genes screened", file=sys.stderr)
    print(f"  Variants: {variants_summary['total']} SNPedia matches", file=sys.stderr)
    print(f"  ClinVar: {clinvar_summary['total']} hits", file=sys.stderr)
    print(f"  GWAS: {gwas.get('total_scores', 0)} scores", file=sys.stderr)
    print(f"  File size: {size_kb:.0f} KB", file=sys.stderr)


if __name__ == "__main__":
    asyncio.run(run())
