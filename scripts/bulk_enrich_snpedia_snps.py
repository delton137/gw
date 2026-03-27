"""Bulk-enrich all SNPedia rsids with MyVariant.info annotation.

Reads all rsids from snpedia_snps that are not already in the snps table,
fetches annotation in POST batches of 1000, and upserts into snps.

No trait associations are inserted — these are structural/annotation-only pages.

Usage:
    python -m scripts.bulk_enrich_snpedia_snps            # full run
    python -m scripts.bulk_enrich_snpedia_snps --dry-run  # preview only
    python -m scripts.bulk_enrich_snpedia_snps --limit 500  # partial run for testing
"""

from __future__ import annotations

import argparse
import asyncio
import logging

import httpx
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.snp import Snp, SnpediaSnp

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

MYVARIANT_BATCH_URL = "https://myvariant.info/v1/query"
MYVARIANT_FIELDS = (
    "dbsnp.chrom,dbsnp.hg19,dbsnp.ref,dbsnp.alt,"
    "dbsnp.gene.symbol,dbsnp.vartype,"
    "gnomad_genome.af,"
    "cadd.phred,cadd.consequence,cadd.sift,cadd.polyphen,"
    "dbnsfp.revel,"
    "clinvar.rcv,clinvar.hgvs,clinvar.allele_id"
)
BATCH_SIZE = 1000
COMMIT_EVERY = 5000

# ClinVar significance severity ordering (highest first)
CLINVAR_SEVERITY = [
    "pathogenic",
    "likely_pathogenic",
    "risk_factor",
    "association",
    "drug_response",
    "uncertain_significance",
    "likely_benign",
    "benign",
]

REVIEW_STATUS_STARS: dict[str, int] = {
    "practice guideline": 4,
    "reviewed by expert panel": 4,
    "criteria provided, multiple submitters, no conflicts": 3,
    "criteria provided, single submitter": 1,
    "criteria provided, conflicting interpretations": 1,
    "no assertion criteria provided": 0,
}


def _safe_float(val) -> float | None:
    if val is None:
        return None
    if isinstance(val, list):
        val = val[0] if val else None
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


def _parse_clinvar(hit: dict) -> dict:
    clinvar = hit.get("clinvar", {})
    if not clinvar:
        return {}

    rcv_list = clinvar.get("rcv", [])
    if isinstance(rcv_list, dict):
        rcv_list = [rcv_list]

    best_sig = None
    best_rank = len(CLINVAR_SEVERITY)
    best_stars = 0
    conditions: set[str] = set()

    for rcv in rcv_list:
        sig = rcv.get("clinical_significance", "")
        if not isinstance(sig, str):
            continue
        sig_lower = sig.lower().replace(" ", "_")

        cond_list = rcv.get("conditions", [])
        if isinstance(cond_list, dict):
            cond_list = [cond_list]
        for cond in cond_list:
            name = cond.get("name")
            if name and name.lower() != "not provided":
                conditions.add(name)

        for i, sev in enumerate(CLINVAR_SEVERITY):
            if sev in sig_lower:
                if i < best_rank:
                    best_rank = i
                    best_sig = CLINVAR_SEVERITY[i]
                break

        review = rcv.get("review_status", "")
        stars = REVIEW_STATUS_STARS.get(review, 0)
        if stars > best_stars:
            best_stars = stars

    hgvs = clinvar.get("hgvs", {})
    hgvs_coding_list = hgvs.get("coding", [])
    hgvs_protein_list = hgvs.get("protein", [])
    if isinstance(hgvs_coding_list, str):
        hgvs_coding_list = [hgvs_coding_list]
    if isinstance(hgvs_protein_list, str):
        hgvs_protein_list = [hgvs_protein_list]

    result: dict = {}
    if best_sig:
        result["clinvar_significance"] = best_sig
        result["clinvar_conditions"] = "; ".join(sorted(conditions)) if conditions else None
        result["clinvar_review_stars"] = best_stars

    allele_id = clinvar.get("allele_id")
    if allele_id is not None:
        result["clinvar_allele_id"] = int(allele_id) if not isinstance(allele_id, int) else allele_id

    if hgvs_coding_list:
        result["hgvs_coding"] = hgvs_coding_list[0][:255]
    if hgvs_protein_list:
        result["hgvs_protein"] = hgvs_protein_list[0][:255]

    return result


def _parse_hit(rsid: str, hit: dict) -> dict | None:
    """Parse a single MyVariant.info hit into a snps row dict. Returns None if unusable."""
    dbsnp = hit.get("dbsnp", {})
    if not dbsnp:
        return None

    hg19 = dbsnp.get("hg19", {})
    position = hg19.get("start") if isinstance(hg19, dict) else None
    chrom = dbsnp.get("chrom")
    if not chrom or not position:
        return None

    gene_info = dbsnp.get("gene")
    gene = None
    if isinstance(gene_info, list) and gene_info:
        gene = gene_info[0].get("symbol")
    elif isinstance(gene_info, dict):
        gene = gene_info.get("symbol")

    alt = dbsnp.get("alt")
    if isinstance(alt, list):
        alt = alt[0] if alt else None

    cadd = hit.get("cadd", {})
    if not isinstance(cadd, dict):
        cadd = {}

    consequence = cadd.get("consequence")
    if isinstance(consequence, list):
        consequence = consequence[0] if consequence else None

    gnomad = hit.get("gnomad_genome", {})
    af_data = gnomad.get("af", {}) if isinstance(gnomad, dict) else {}
    if not isinstance(af_data, dict):
        af_data = {}

    sift = cadd.get("sift", {})
    if not isinstance(sift, dict):
        sift = {}
    polyphen = cadd.get("polyphen", {})
    if not isinstance(polyphen, dict):
        polyphen = {}

    dbnsfp = hit.get("dbnsfp", {})
    revel = dbnsfp.get("revel", {}) if isinstance(dbnsfp, dict) else {}
    if not isinstance(revel, dict):
        revel = {}

    result = {
        "rsid": rsid,
        "chrom": str(chrom),
        "position": position,
        "ref_allele": dbsnp.get("ref"),
        "alt_allele": alt,
        "gene": gene,
        "functional_class": consequence,
        "maf_global": _safe_float(af_data.get("af")),
        "cadd_phred": _safe_float(cadd.get("phred")),
        "sift_category": sift.get("cat"),
        "sift_score": _safe_float(sift.get("val")),
        "polyphen_category": polyphen.get("cat"),
        "polyphen_score": _safe_float(polyphen.get("val")),
        "revel_score": _safe_float(revel.get("score")),
        "gnomad_afr": _safe_float(af_data.get("af_afr")),
        "gnomad_eas": _safe_float(af_data.get("af_eas")),
        "gnomad_nfe": _safe_float(af_data.get("af_nfe")),
        "gnomad_sas": _safe_float(af_data.get("af_sas")),
        "gnomad_amr": _safe_float(af_data.get("af_amr")),
        "gnomad_fin": _safe_float(af_data.get("af_fin")),
        "gnomad_asj": _safe_float(af_data.get("af_asj")),
    }
    result.update(_parse_clinvar(hit))
    return result


async def fetch_batch(rsids: list[str], client: httpx.AsyncClient) -> dict[str, dict]:
    """POST a batch of rsids to MyVariant.info. Returns {rsid: parsed_row}."""
    try:
        resp = await client.post(
            MYVARIANT_BATCH_URL,
            data={
                "q": ",".join(rsids),
                "scopes": "dbsnp.rsid",
                "fields": MYVARIANT_FIELDS,
                "size": len(rsids),
            },
            timeout=60,
        )
        resp.raise_for_status()
        hits = resp.json()
        if not isinstance(hits, list):
            hits = hits.get("hits", [])
    except Exception as e:
        log.warning("MyVariant.info batch request failed: %s", e)
        return {}

    results: dict[str, dict] = {}
    for hit in hits:
        # MyVariant returns a "query" field with the rsid we queried
        queried_rsid = hit.get("query", "").lower()
        if not queried_rsid or hit.get("notfound"):
            continue
        parsed = _parse_hit(queried_rsid, hit)
        if parsed:
            results[queried_rsid] = parsed

    return results


async def upsert_rows(session: AsyncSession, rows: list[dict]) -> None:
    """Upsert a list of snps rows. Preserves existing non-None fields."""
    for row in rows:
        update_set = {k: v for k, v in row.items() if k != "rsid" and v is not None}
        stmt = pg_insert(Snp).values(**row).on_conflict_do_update(
            index_elements=["rsid"],
            set_=update_set,
        )
        await session.execute(stmt)


async def run(*, dry_run: bool = False, limit: int | None = None) -> None:
    engine = create_async_engine(settings.database_url, pool_size=5)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # All SNPedia rsids that either:
        # (a) are not yet in snps at all, or
        # (b) are in snps but have no CADD score (unannotated PRS-loaded rows)
        result = await session.execute(
            text("""
                SELECT s.rsid FROM snpedia_snps s
                LEFT JOIN snps n ON s.rsid = n.rsid
                WHERE n.rsid IS NULL OR n.cadd_phred IS NULL
                ORDER BY s.rsid
            """)
        )
        todo = [row.rsid for row in result]

    log.info("SNPedia rsids not yet in snps table: %d", len(todo))

    if limit:
        todo = todo[:limit]
        log.info("Limiting to %d rsids (--limit)", limit)

    if dry_run:
        log.info("Dry run — no writes. Sample rsids: %s", todo[:10])
        await engine.dispose()
        return

    total = len(todo)
    n_batches = (total + BATCH_SIZE - 1) // BATCH_SIZE
    inserted = 0
    no_hit = 0
    pending_rows: list[dict] = []

    async with httpx.AsyncClient() as client:
        async with async_session() as session:
            for batch_num, start in enumerate(range(0, total, BATCH_SIZE), 1):
                batch = todo[start : start + BATCH_SIZE]
                log.info(
                    "Batch %d/%d — fetching %d rsids (inserted so far: %d, no-hit: %d)",
                    batch_num, n_batches, len(batch), inserted, no_hit,
                )

                hits = await fetch_batch(batch, client)
                no_hit += len(batch) - len(hits)

                for rsid in batch:
                    row = hits.get(rsid)
                    if row:
                        pending_rows.append(row)

                # Commit in chunks
                if len(pending_rows) >= COMMIT_EVERY or batch_num == n_batches:
                    if pending_rows:
                        await upsert_rows(session, pending_rows)
                        await session.commit()
                        inserted += len(pending_rows)
                        log.info("Committed %d rows (total inserted: %d)", len(pending_rows), inserted)
                        pending_rows = []

    log.info("Done. Inserted/updated: %d  |  No MyVariant hit: %d", inserted, no_hit)
    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="Preview without writing")
    parser.add_argument("--limit", type=int, default=None, help="Process only N rsids (for testing)")
    args = parser.parse_args()
    asyncio.run(run(dry_run=args.dry_run, limit=args.limit))


if __name__ == "__main__":
    main()
