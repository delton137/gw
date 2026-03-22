"""Check for stale PGS Catalog scoring files.

Compares the scoring_file_hash stored in the database against a fresh
download from the PGS Catalog FTP, reporting any mismatches.

Usage:
    python -m scripts.check_pgs_staleness
    python -m scripts.check_pgs_staleness --pgs-id PGS000001
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import hashlib
import logging

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.prs import PrsScore
from scripts.ingest_pgs import SCORING_FILE_URL_37

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


async def check_staleness(pgs_ids: list[str] | None = None) -> None:
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        query = select(PrsScore)
        if pgs_ids:
            query = query.where(PrsScore.pgs_id.in_(pgs_ids))
        result = await session.execute(query)
        scores = result.scalars().all()

    if not scores:
        log.info("No scores found in database")
        await engine.dispose()
        return

    stale = []
    no_hash = []
    up_to_date = []

    async with httpx.AsyncClient(timeout=120) as client:
        for score in scores:
            if not score.scoring_file_hash:
                no_hash.append(score.pgs_id)
                continue

            url = SCORING_FILE_URL_37.format(pgs_id=score.pgs_id)
            try:
                resp = await client.get(url, follow_redirects=True)
                resp.raise_for_status()
                content = gzip.decompress(resp.content).decode("utf-8")
                current_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
            except Exception as e:
                log.warning(f"  {score.pgs_id}: could not download — {e}")
                continue

            if current_hash != score.scoring_file_hash:
                stale.append(score.pgs_id)
                log.warning(
                    f"  {score.pgs_id}: STALE — stored hash {score.scoring_file_hash[:12]}... "
                    f"!= current {current_hash[:12]}..."
                )
            else:
                up_to_date.append(score.pgs_id)
                log.info(f"  {score.pgs_id}: up to date")

    # Summary
    print(f"\n{'='*50}")
    print(f"Up to date:    {len(up_to_date)}")
    print(f"Stale:         {len(stale)}")
    print(f"No hash stored: {len(no_hash)}")
    if stale:
        print(f"\nStale scores (reimport with --force):")
        for pgs_id in stale:
            print(f"  python -m scripts.ingest_pgs --pgs-id {pgs_id} --force")
    if no_hash:
        print(f"\nScores without hash (reimport to add tracking):")
        for pgs_id in no_hash:
            print(f"  python -m scripts.ingest_pgs --pgs-id {pgs_id} --force")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Check PGS scoring file staleness")
    parser.add_argument("--pgs-id", type=str, help="Check a single PGS ID")
    parser.add_argument("--pgs-ids", nargs="+", type=str, help="Check specific PGS IDs")
    args = parser.parse_args()

    ids = None
    if args.pgs_ids:
        ids = args.pgs_ids
    elif args.pgs_id:
        ids = [args.pgs_id]

    asyncio.run(check_staleness(ids))
