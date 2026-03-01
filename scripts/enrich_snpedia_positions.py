"""Enrich SNPedia rsIDs that are missing from the snps table with position data.

Batch-queries MyVariant.info (1000 rsIDs per request) for GRCh37/GRCh38
coordinates, ref/alt alleles, and gene symbol, then inserts into the snps table.

Usage:
    python -m scripts.enrich_snpedia_positions
    python -m scripts.enrich_snpedia_positions --dry-run
    python -m scripts.enrich_snpedia_positions --limit 100   # test with small batch
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time

import httpx
from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.snp import Snp

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

MYVARIANT_BATCH_URL = "https://myvariant.info/v1/query"
BATCH_SIZE = 1000
# MyVariant.info fields: dbsnp positions (hg19 + hg38), alleles, gene
FIELDS = "dbsnp.chrom,dbsnp.hg19,dbsnp.hg38,dbsnp.ref,dbsnp.alt,dbsnp.gene.symbol"


async def get_missing_rsids(session: AsyncSession, limit: int | None = None) -> list[str]:
    """Find SNPedia rsIDs not yet in the snps table."""
    q = text("""
        SELECT ss.rsid FROM snpedia_snps ss
        LEFT JOIN snps s ON ss.rsid = s.rsid
        WHERE s.rsid IS NULL
        ORDER BY ss.rsid
    """)
    result = await session.execute(q)
    rsids = [row[0] for row in result]
    if limit:
        rsids = rsids[:limit]
    return rsids


async def batch_query_myvariant(
    rsids: list[str], client: httpx.AsyncClient,
) -> list[dict]:
    """Query MyVariant.info with a batch of rsIDs via POST."""
    resp = await client.post(
        MYVARIANT_BATCH_URL,
        data={
            "q": ",".join(rsids),
            "scopes": "dbsnp.rsid",
            "fields": FIELDS,
            "size": BATCH_SIZE,
        },
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def parse_hit(hit: dict) -> dict | None:
    """Extract position data from a MyVariant.info hit."""
    if hit.get("notfound"):
        return None

    query_rsid = hit.get("query")
    dbsnp = hit.get("dbsnp", {})
    if not dbsnp:
        return None

    chrom = dbsnp.get("chrom")
    if not chrom:
        return None

    # GRCh37 position
    hg19 = dbsnp.get("hg19", {})
    if isinstance(hg19, list):
        hg19 = hg19[0] if hg19 else {}
    pos37 = hg19.get("start") if isinstance(hg19, dict) else None

    # GRCh38 position
    hg38 = dbsnp.get("hg38", {})
    if isinstance(hg38, list):
        hg38 = hg38[0] if hg38 else {}
    pos38 = hg38.get("start") if isinstance(hg38, dict) else None

    if pos37 is None and pos38 is None:
        return None

    # Ref/alt alleles
    ref = dbsnp.get("ref")
    alt = dbsnp.get("alt")
    if isinstance(alt, list):
        alt = alt[0] if alt else None

    # Gene symbol
    gene_info = dbsnp.get("gene")
    gene = None
    if isinstance(gene_info, list) and gene_info:
        gene = gene_info[0].get("symbol")
    elif isinstance(gene_info, dict):
        gene = gene_info.get("symbol")

    return {
        "rsid": query_rsid,
        "chrom": str(chrom),
        "position": int(pos37) if pos37 is not None else (int(pos38) if pos38 is not None else None),
        "position_grch38": int(pos38) if pos38 is not None else None,
        "ref_allele": ref or "N",
        "alt_allele": alt or "N",
        "gene": gene,
    }


async def main():
    parser = argparse.ArgumentParser(description="Enrich SNPedia rsIDs with position data from MyVariant.info")
    parser.add_argument("--dry-run", action="store_true", help="Print stats without inserting")
    parser.add_argument("--limit", type=int, default=None, help="Limit number of rsIDs to process")
    args = parser.parse_args()

    engine = create_async_engine(settings.database_url, pool_size=5)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        missing = await get_missing_rsids(session, args.limit)
        log.info(f"Found {len(missing):,} SNPedia rsIDs missing from snps table")

        if not missing:
            log.info("Nothing to do.")
            return

        if args.dry_run:
            log.info("Dry run — would query MyVariant.info and insert results. Exiting.")
            return

        t0 = time.perf_counter()
        total_inserted = 0
        total_not_found = 0
        n_batches = (len(missing) + BATCH_SIZE - 1) // BATCH_SIZE

        async with httpx.AsyncClient() as client:
            for i in range(0, len(missing), BATCH_SIZE):
                batch = missing[i : i + BATCH_SIZE]
                batch_num = i // BATCH_SIZE + 1

                try:
                    hits = await batch_query_myvariant(batch, client)
                except Exception as e:
                    log.error(f"Batch {batch_num}/{n_batches} failed: {e}")
                    continue

                rows_to_insert = []
                for hit in hits:
                    parsed = parse_hit(hit)
                    if parsed and parsed["position"] is not None:
                        rows_to_insert.append(parsed)
                    else:
                        total_not_found += 1

                if rows_to_insert:
                    stmt = pg_insert(Snp).values(rows_to_insert)
                    stmt = stmt.on_conflict_do_nothing(index_elements=["rsid"])
                    await session.execute(stmt)
                    await session.commit()
                    total_inserted += len(rows_to_insert)

                elapsed = time.perf_counter() - t0
                log.info(
                    f"Batch {batch_num}/{n_batches}: "
                    f"+{len(rows_to_insert)} inserted, "
                    f"{total_not_found} not found, "
                    f"{elapsed:.1f}s elapsed"
                )

                # Brief pause to be polite to the API
                if i + BATCH_SIZE < len(missing):
                    await asyncio.sleep(0.3)

        elapsed = time.perf_counter() - t0
        log.info(
            f"Done: {total_inserted:,} inserted, {total_not_found:,} not found "
            f"in {elapsed:.1f}s"
        )

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
