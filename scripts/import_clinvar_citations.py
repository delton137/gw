"""Import ClinVar citation data (PubMed IDs) per variant.

Downloads var_citations.txt from ClinVar FTP and updates snps with
citation counts and PubMed IDs for each variant.

Usage:
    python -m scripts.import_clinvar_citations                       # download + import
    python -m scripts.import_clinvar_citations --file var_citations.txt
    python -m scripts.import_clinvar_citations --dry-run
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import time
import urllib.request
from pathlib import Path

import polars as pl
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

CLINVAR_CITATIONS_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/var_citations.txt"
DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "app" / "data"
MAX_PMIDS_STORED = 20  # Store up to 20 PMIDs per variant


def download_citations(dest: Path) -> Path:
    """Download var_citations.txt from ClinVar FTP."""
    out = dest / "var_citations.txt"
    if out.exists():
        log.info(f"Using existing file: {out} ({out.stat().st_size / 1e6:.0f} MB)")
        return out
    log.info(f"Downloading {CLINVAR_CITATIONS_URL} ...")
    urllib.request.urlretrieve(CLINVAR_CITATIONS_URL, out)
    log.info(f"Downloaded: {out} ({out.stat().st_size / 1e6:.0f} MB)")
    return out


def load_and_aggregate(file_path: Path) -> pl.DataFrame:
    """Load var_citations.txt, filter to PubMed, group by rsid."""
    log.info(f"Reading {file_path} ...")
    t0 = time.perf_counter()

    df = pl.read_csv(
        file_path,
        separator="\t",
        infer_schema_length=0,
        null_values=["-", "-1", ""],
        ignore_errors=True,
    )
    log.info(f"  Raw rows: {len(df):,} ({time.perf_counter() - t0:.1f}s)")

    # Rename #AlleleID if present
    if "#AlleleID" in df.columns:
        df = df.rename({"#AlleleID": "AlleleID"})

    # Filter to PubMed citations with valid rsIDs
    # Column names: AlleleID, VariationID, rs, nsv, citation_source, citation_id
    df = df.filter(
        (pl.col("citation_source") == "PubMed")
        & (pl.col("rs").is_not_null())
        & (pl.col("rs") != "-1")
        & (pl.col("rs") != "")
        & (pl.col("citation_id").is_not_null())
    )
    log.info(f"  PubMed citations with rsIDs: {len(df):,}")

    # Group by rsid: count citations, collect PMIDs
    grouped = df.group_by("rs").agg(
        pl.col("citation_id").n_unique().alias("citation_count"),
        pl.col("citation_id").unique().sort().head(MAX_PMIDS_STORED).alias("pmids"),
    )

    # Format rsid and pmids
    grouped = grouped.with_columns(
        (pl.lit("rs") + pl.col("rs")).alias("rsid"),
        pl.col("pmids").list.join(",").alias("pmids_str"),
    )
    log.info(f"  Unique rsIDs with citations: {len(grouped):,}")
    return grouped


async def update_citations(df: pl.DataFrame, dry_run: bool = False) -> None:
    """Batch update snps with citation counts and PMIDs using unnest arrays."""
    if dry_run:
        log.info("DRY RUN — no database writes")
        print(f"Would update {len(df):,} variants with citation data")
        print(df.select("rsid", "citation_count", "pmids_str").head(10))
        return

    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    t0 = time.perf_counter()
    batch_size = 5000
    n_updated = 0

    async with async_session() as session:
        total = len(df)
        for i in range(0, total, batch_size):
            batch = df.slice(i, batch_size)

            rsids = batch["rsid"].to_list()
            counts = [int(c) for c in batch["citation_count"].to_list()]
            pmids = batch["pmids_str"].to_list()

            result = await session.execute(
                text("""
                    UPDATE snps SET
                        clinvar_citation_count = data.cnt,
                        clinvar_pmids = data.pmids
                    FROM unnest(:rsids::text[], :counts::int[], :pmids_arr::text[])
                        AS data(rsid, cnt, pmids)
                    WHERE snps.rsid = data.rsid
                """),
                {"rsids": rsids, "counts": counts, "pmids_arr": pmids},
            )
            n_updated += result.rowcount

            await session.commit()

            if (i // batch_size) % 10 == 0:
                elapsed = time.perf_counter() - t0
                log.info(f"  Progress: {min(i + batch_size, total):,} / {total:,} ({n_updated:,} updated, {elapsed:.0f}s)")

    elapsed = time.perf_counter() - t0
    log.info(f"Done in {elapsed:.1f}s — updated {n_updated:,} variants")
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Import ClinVar citation data")
    parser.add_argument("--file", type=str, help="Path to local var_citations.txt")
    parser.add_argument("--dry-run", action="store_true", help="Count and preview only")
    args = parser.parse_args()

    if args.file:
        file_path = Path(args.file)
    else:
        file_path = download_citations(DOWNLOAD_DIR)

    df = load_and_aggregate(file_path)

    if len(df) == 0:
        log.warning("No citations found — nothing to import")
        return

    asyncio.run(update_citations(df, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
