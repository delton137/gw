"""Fetch gene descriptions from NCBI Gene E-utilities API.

Enriches the genes table with short names and functional summaries from
NCBI Gene. Uses batch ESummary (up to 200 IDs per call) for efficiency.

Usage:
    python -m scripts.fetch_gene_descriptions
    python -m scripts.fetch_gene_descriptions --ncbi-api-key YOUR_KEY
    python -m scripts.fetch_gene_descriptions --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import time
import urllib.parse
import urllib.request
from http.client import HTTPResponse

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

ESEARCH_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esearch.fcgi"
ESUMMARY_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/esummary.fcgi"
BATCH_SIZE = 200  # max IDs per ESummary call


def _api_params(api_key: str | None) -> dict:
    """Base params for NCBI E-utilities."""
    params = {"retmode": "json"}
    if api_key:
        params["api_key"] = api_key
    return params


def _rate_delay(api_key: str | None) -> float:
    """Seconds between API calls (3/sec without key, 10/sec with key)."""
    return 0.1 if api_key else 0.34


def _fetch_json(url: str, params: dict) -> dict:
    """Make a GET request and return parsed JSON."""
    query = urllib.parse.urlencode(params)
    full_url = f"{url}?{query}"
    req = urllib.request.Request(full_url, headers={"User-Agent": "Gene Wizard/1.0"})
    resp: HTTPResponse = urllib.request.urlopen(req, timeout=30)
    return json.loads(resp.read())


def search_gene_id(symbol: str, api_key: str | None = None) -> int | None:
    """Search NCBI Gene for a human gene by symbol, return Gene ID."""
    params = {
        **_api_params(api_key),
        "db": "gene",
        "term": f"{symbol}[sym] AND Homo sapiens[orgn]",
        "retmax": 1,
    }
    try:
        data = _fetch_json(ESEARCH_URL, params)
        ids = data.get("esearchresult", {}).get("idlist", [])
        return int(ids[0]) if ids else None
    except Exception as e:
        log.warning(f"  esearch failed for {symbol}: {e}")
        return None


def fetch_gene_summaries(gene_ids: list[int], api_key: str | None = None) -> dict[int, dict]:
    """Batch fetch gene descriptions from NCBI ESummary.

    Returns dict mapping gene_id → {"name": ..., "summary": ...}.
    """
    params = {
        **_api_params(api_key),
        "db": "gene",
        "id": ",".join(str(gid) for gid in gene_ids),
    }
    try:
        data = _fetch_json(ESUMMARY_URL, params)
        result = data.get("result", {})
        out = {}
        for gid in gene_ids:
            entry = result.get(str(gid), {})
            if not entry or "error" in entry:
                continue
            name = entry.get("description", "")
            summary = entry.get("summary", "")
            out[gid] = {
                "name": name[:255] if name else None,
                "summary": summary if summary else None,
            }
        return out
    except Exception as e:
        log.warning(f"  esummary failed for batch: {e}")
        return {}


async def fetch_and_update(api_key: str | None = None, dry_run: bool = False) -> None:
    """Fetch gene descriptions and update the genes table."""
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Phase 1: Get genes that already have ncbi_gene_id but missing name
        result = await session.execute(
            text("SELECT symbol, ncbi_gene_id FROM genes WHERE name IS NULL AND ncbi_gene_id IS NOT NULL")
        )
        genes_with_id = [(row[0], row[1]) for row in result]
        log.info(f"Genes with NCBI ID but missing name: {len(genes_with_id):,}")

        # Phase 2: Get genes missing both name and ncbi_gene_id
        result = await session.execute(
            text("SELECT symbol FROM genes WHERE name IS NULL AND ncbi_gene_id IS NULL")
        )
        genes_without_id = [row[0] for row in result]
        log.info(f"Genes missing NCBI ID (need esearch): {len(genes_without_id):,}")

        if dry_run:
            log.info("DRY RUN — would fetch descriptions for "
                     f"{len(genes_with_id) + len(genes_without_id):,} genes")
            await engine.dispose()
            return

        t0 = time.perf_counter()
        delay = _rate_delay(api_key)
        n_updated = 0
        n_failed = 0

        # Phase 1: Batch fetch for genes with known IDs
        if genes_with_id:
            log.info("Phase 1: Batch fetching genes with known NCBI IDs ...")
            id_to_symbol = {gid: sym for sym, gid in genes_with_id}
            all_ids = list(id_to_symbol.keys())

            for i in range(0, len(all_ids), BATCH_SIZE):
                batch_ids = all_ids[i : i + BATCH_SIZE]
                summaries = fetch_gene_summaries(batch_ids, api_key)
                time.sleep(delay)

                updates = []
                for gid, info in summaries.items():
                    symbol = id_to_symbol.get(gid)
                    if symbol and info.get("name"):
                        updates.append({
                            "symbol": symbol,
                            "name": info["name"],
                            "summary": info.get("summary"),
                        })

                if updates:
                    for u in updates:
                        await session.execute(
                            text("""
                                UPDATE genes SET name = :name, summary = :summary
                                WHERE symbol = :symbol
                            """),
                            u,
                        )
                    n_updated += len(updates)

                fetched = min(i + BATCH_SIZE, len(all_ids))
                if (i // BATCH_SIZE) % 10 == 0:
                    log.info(f"  Phase 1: {fetched:,} / {len(all_ids):,} "
                             f"({n_updated:,} updated)")

            await session.commit()
            log.info(f"Phase 1 complete: {n_updated:,} genes updated")

        # Phase 2: Search + fetch for genes without IDs
        if genes_without_id:
            log.info(f"Phase 2: Searching {len(genes_without_id):,} genes by symbol ...")
            p2_updated = 0
            # Collect gene IDs first
            found_ids = {}
            for j, symbol in enumerate(genes_without_id):
                gid = search_gene_id(symbol, api_key)
                time.sleep(delay)
                if gid:
                    found_ids[symbol] = gid
                else:
                    n_failed += 1

                if (j + 1) % 100 == 0:
                    log.info(f"  Phase 2 search: {j + 1:,} / {len(genes_without_id):,} "
                             f"(found: {len(found_ids):,})")

            log.info(f"  Found NCBI IDs for {len(found_ids):,} / {len(genes_without_id):,} genes")

            # Batch fetch summaries
            symbol_list = list(found_ids.keys())
            id_list = [found_ids[s] for s in symbol_list]

            for i in range(0, len(id_list), BATCH_SIZE):
                batch_ids = id_list[i : i + BATCH_SIZE]
                batch_symbols = symbol_list[i : i + BATCH_SIZE]
                id_to_sym = dict(zip(batch_ids, batch_symbols))

                summaries = fetch_gene_summaries(batch_ids, api_key)
                time.sleep(delay)

                for gid, info in summaries.items():
                    sym = id_to_sym.get(gid)
                    if sym and info.get("name"):
                        await session.execute(
                            text("""
                                UPDATE genes SET
                                    name = :name, summary = :summary,
                                    ncbi_gene_id = :ncbi_gene_id
                                WHERE symbol = :symbol
                            """),
                            {
                                "symbol": sym,
                                "name": info["name"],
                                "summary": info.get("summary"),
                                "ncbi_gene_id": gid,
                            },
                        )
                        p2_updated += 1

            await session.commit()
            n_updated += p2_updated
            log.info(f"Phase 2 complete: {p2_updated:,} genes updated, {n_failed:,} not found")

    elapsed = time.perf_counter() - t0
    log.info(f"Done in {elapsed:.1f}s — {n_updated:,} genes enriched total")
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Fetch gene descriptions from NCBI Gene")
    parser.add_argument("--ncbi-api-key", type=str, help="NCBI API key for faster rate limits")
    parser.add_argument("--dry-run", action="store_true", help="Count only, no API calls")
    args = parser.parse_args()

    asyncio.run(fetch_and_update(api_key=args.ncbi_api_key, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
