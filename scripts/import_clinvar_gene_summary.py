"""Import ClinVar gene_specific_summary into the genes table.

Downloads gene_specific_summary.txt from ClinVar FTP and populates the genes
table with per-gene variant counts, OMIM numbers, and submission stats.

Usage:
    python -m scripts.import_clinvar_gene_summary
    python -m scripts.import_clinvar_gene_summary --file gene_specific_summary.txt
    python -m scripts.import_clinvar_gene_summary --dry-run
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

CLINVAR_GENE_URL = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/gene_specific_summary.txt"
DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "app" / "data"


def download_gene_summary(dest: Path) -> Path:
    """Download gene_specific_summary.txt from ClinVar FTP."""
    out = dest / "gene_specific_summary.txt"
    if out.exists():
        log.info(f"Using existing file: {out} ({out.stat().st_size / 1e6:.1f} MB)")
        return out
    log.info(f"Downloading {CLINVAR_GENE_URL} ...")
    urllib.request.urlretrieve(CLINVAR_GENE_URL, out)
    log.info(f"Downloaded: {out} ({out.stat().st_size / 1e6:.1f} MB)")
    return out


def load_gene_summary(file_path: Path) -> pl.DataFrame:
    """Load and clean gene_specific_summary.txt."""
    log.info(f"Reading {file_path} ...")

    df = pl.read_csv(
        file_path,
        separator="\t",
        infer_schema_length=0,
        null_values=["-", "-1", ""],
        ignore_errors=True,
        truncate_ragged_lines=True,
        comment_prefix="#Overview",  # skip the first comment line
    )
    log.info(f"  Raw rows: {len(df):,}")

    # Rename #Symbol if present (second line starts with #Symbol)
    if "#Symbol" in df.columns:
        df = df.rename({"#Symbol": "Symbol"})

    # Filter out rows without a gene symbol
    df = df.filter(pl.col("Symbol").is_not_null() & (pl.col("Symbol") != ""))

    # Deduplicate by symbol (keep first occurrence)
    df = df.unique(subset=["Symbol"], keep="first")
    log.info(f"  Unique genes: {len(df):,}")

    return df


def _safe_int(val) -> int | None:
    """Convert a value to int, return None if not possible."""
    if val is None:
        return None
    try:
        return int(val)
    except (ValueError, TypeError):
        return None


async def import_genes(df: pl.DataFrame, dry_run: bool = False) -> None:
    """Bulk upsert gene stats into genes table."""
    if dry_run:
        log.info("DRY RUN — no database writes")
        print(f"Would upsert {len(df):,} genes")
        # Columns: Symbol, GeneID, Total_submissions, Total_alleles,
        # Submissions_reporting_this_gene, Alleles_reported_Pathogenic_Likely_pathogenic,
        # Gene_MIM_number, Number_uncertain, Number_with_conflicts
        print(df.head(10))
        return

    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    t0 = time.perf_counter()
    batch_size = 2000
    n_total = 0

    async with async_session() as session:
        total = len(df)
        for i in range(0, total, batch_size):
            batch = df.slice(i, batch_size)
            values_list = []

            for row in batch.iter_rows(named=True):
                symbol = row.get("Symbol", "")
                if not symbol or len(symbol) > 50:
                    continue

                gene_id = _safe_int(row.get("GeneID"))
                omim = row.get("Gene_MIM_number")
                if omim and len(str(omim)) > 20:
                    omim = None

                total_alleles = _safe_int(row.get("Total_alleles"))
                pathogenic = _safe_int(row.get("Alleles_reported_Pathogenic_Likely_pathogenic"))
                uncertain = _safe_int(row.get("Number_uncertain"))
                conflicting = _safe_int(row.get("Number_with_conflicts"))
                total_submissions = _safe_int(row.get("Total_submissions"))

                values_list.append({
                    "symbol": symbol,
                    "ncbi_gene_id": gene_id,
                    "omim_number": str(omim) if omim else None,
                    "clinvar_total_variants": total_alleles,
                    "clinvar_pathogenic_count": pathogenic,
                    "clinvar_uncertain_count": uncertain,
                    "clinvar_conflicting_count": conflicting,
                    "clinvar_total_submissions": total_submissions,
                })

            if not values_list:
                continue

            await session.execute(
                text("""
                    INSERT INTO genes (symbol, ncbi_gene_id, omim_number,
                        clinvar_total_variants, clinvar_pathogenic_count,
                        clinvar_uncertain_count, clinvar_conflicting_count,
                        clinvar_total_submissions)
                    VALUES (:symbol, :ncbi_gene_id, :omim_number,
                        :clinvar_total_variants, :clinvar_pathogenic_count,
                        :clinvar_uncertain_count, :clinvar_conflicting_count,
                        :clinvar_total_submissions)
                    ON CONFLICT (symbol) DO UPDATE SET
                        ncbi_gene_id = COALESCE(EXCLUDED.ncbi_gene_id, genes.ncbi_gene_id),
                        omim_number = COALESCE(EXCLUDED.omim_number, genes.omim_number),
                        clinvar_total_variants = EXCLUDED.clinvar_total_variants,
                        clinvar_pathogenic_count = EXCLUDED.clinvar_pathogenic_count,
                        clinvar_uncertain_count = EXCLUDED.clinvar_uncertain_count,
                        clinvar_conflicting_count = EXCLUDED.clinvar_conflicting_count,
                        clinvar_total_submissions = EXCLUDED.clinvar_total_submissions
                """),
                values_list,
            )
            n_total += len(values_list)

            if (i // batch_size) % 10 == 0:
                log.info(f"  Progress: {min(i + batch_size, total):,} / {total:,} ...")

        await session.commit()

    elapsed = time.perf_counter() - t0
    log.info(f"Done in {elapsed:.1f}s — upserted {n_total:,} genes")
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Import ClinVar gene-level summary")
    parser.add_argument("--file", type=str, help="Path to local gene_specific_summary.txt")
    parser.add_argument("--dry-run", action="store_true", help="Count and preview only")
    args = parser.parse_args()

    if args.file:
        file_path = Path(args.file)
    else:
        file_path = download_gene_summary(DOWNLOAD_DIR)

    df = load_gene_summary(file_path)

    if len(df) == 0:
        log.warning("No genes found — nothing to import")
        return

    asyncio.run(import_genes(df, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
