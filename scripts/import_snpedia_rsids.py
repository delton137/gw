"""Import SNPedia rsid list into the snpedia_snps lookup table.

Reads the SNPedia SQLite database dump and extracts all rs-numbered SNP IDs.
Only the rsid list is used (no content from SNPedia due to licensing).

Usage:
    python -m scripts.import_snpedia_rsids --db-path /path/to/SNPedia2025.db
"""

from __future__ import annotations

import argparse
import logging
import sqlite3
import sys
import time

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


async def import_snpedia_rsids(sqlite_path: str) -> None:
    """Read rs-numbered SNP IDs from SNPedia SQLite dump and insert into Postgres."""
    # Read rsids from SQLite
    log.info(f"Reading SNPedia database: {sqlite_path}")
    conn = sqlite3.connect(sqlite_path)
    cursor = conn.execute("SELECT rsid FROM snps WHERE rsid LIKE 'rs%'")
    rsids = [row[0].lower() for row in cursor]
    conn.close()
    log.info(f"Found {len(rsids):,} rs-numbered SNPs in SNPedia")

    # Connect to Postgres
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Clear existing data
        await session.execute(text("DELETE FROM snpedia_snps"))

        # Bulk insert in batches of 5000
        t0 = time.perf_counter()
        batch_size = 5000
        for i in range(0, len(rsids), batch_size):
            batch = rsids[i : i + batch_size]
            values = ", ".join(f"('{rsid}')" for rsid in batch)
            await session.execute(
                text(f"INSERT INTO snpedia_snps (rsid) VALUES {values} ON CONFLICT DO NOTHING")
            )
            if (i // batch_size) % 5 == 0:
                log.info(f"  Inserted {min(i + batch_size, len(rsids)):,} / {len(rsids):,}...")

        await session.commit()

    elapsed = time.perf_counter() - t0
    log.info(f"Imported {len(rsids):,} SNPedia rsids in {elapsed:.1f}s")
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Import SNPedia rsid list")
    parser.add_argument(
        "--db-path",
        default="/home/dan/Dropbox/AAA_GENEWIZARD/SNPedia2025/SNPedia2025.db",
        help="Path to SNPedia SQLite database",
    )
    args = parser.parse_args()

    import asyncio
    asyncio.run(import_snpedia_rsids(args.db_path))


if __name__ == "__main__":
    main()
