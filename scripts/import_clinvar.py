"""Import ClinVar variant_summary into the snps table.

Downloads variant_summary.txt.gz from ClinVar FTP and bulk-imports all single
nucleotide variants (with rsIDs) on GRCh37 into the snps table.

Usage:
    python -m scripts.import_clinvar                                  # download + import
    python -m scripts.import_clinvar --file variant_summary.txt.gz    # use local file
    python -m scripts.import_clinvar --dry-run                        # count only
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

CLINVAR_FTP = "https://ftp.ncbi.nlm.nih.gov/pub/clinvar/tab_delimited/variant_summary.txt.gz"
DOWNLOAD_DIR = Path(__file__).resolve().parent.parent / "app" / "data"

# ClinVar ReviewStatus → star rating
REVIEW_STARS = {
    "practice guideline": 4,
    "reviewed by expert panel": 4,
    "criteria provided, multiple submitters, no conflicts": 3,
    "criteria provided, conflicting interpretations": 2,
    "criteria provided, single submitter": 1,
    "no assertion for the individual variant": 0,
    "no assertion criteria provided": 0,
    "no classification provided": 0,
    "no classification for the individual variant": 0,
}

# Clinical significance priority (higher = more severe)
SIGNIFICANCE_PRIORITY = {
    "pathogenic": 8,
    "likely pathogenic": 7,
    "pathogenic/likely pathogenic": 7,
    "risk factor": 6,
    "association": 5,
    "drug response": 4,
    "affects": 3,
    "uncertain significance": 2,
    "likely benign": 1,
    "benign": 0,
    "benign/likely benign": 0,
    "conflicting classifications of pathogenicity": 2,
    "conflicting interpretations of pathogenicity": 2,
}


def _normalize_significance(raw: str) -> str:
    """Pick the most severe significance from a potentially multi-value string."""
    if not raw or raw == "-":
        return "uncertain_significance"
    parts = [p.strip().lower() for p in raw.replace("/", ";").split(";")]
    best = max(parts, key=lambda p: SIGNIFICANCE_PRIORITY.get(p, -1))
    return best.replace(" ", "_")


def _review_stars(raw: str) -> int:
    """Map ClinVar ReviewStatus string to 0-4 star rating."""
    if not raw or raw == "-":
        return 0
    return REVIEW_STARS.get(raw.strip().lower(), 0)


def _first_gene(raw: str) -> str | None:
    """Extract first gene symbol from potentially comma-separated list."""
    if not raw or raw == "-":
        return None
    return raw.split(",")[0].strip()[:50]


def download_clinvar(dest: Path) -> Path:
    """Download variant_summary.txt.gz from ClinVar FTP."""
    out = dest / "variant_summary.txt.gz"
    if out.exists():
        log.info(f"Using existing file: {out} ({out.stat().st_size / 1e6:.0f} MB)")
        return out
    log.info(f"Downloading {CLINVAR_FTP} ...")
    urllib.request.urlretrieve(CLINVAR_FTP, out)
    log.info(f"Downloaded: {out} ({out.stat().st_size / 1e6:.0f} MB)")
    return out


def load_and_filter(file_path: Path) -> pl.DataFrame:
    """Load variant_summary.txt.gz and filter to GRCh37 SNVs with rsIDs."""
    log.info(f"Reading {file_path} ...")
    t0 = time.perf_counter()

    df = pl.read_csv(
        file_path,
        separator="\t",
        infer_schema_length=0,  # read everything as strings first
        null_values=["-", "-1", "na", ""],
        ignore_errors=True,
    )
    log.info(f"  Raw rows: {len(df):,} ({time.perf_counter() - t0:.1f}s)")

    # Rename columns with special characters
    col_map = {}
    for col in df.columns:
        if col == "#AlleleID":
            col_map[col] = "AlleleID"
        elif col == "RS# (dbSNP)":
            col_map[col] = "RS"
        elif col == "nsv/esv (dbVar)":
            col_map[col] = "nsv_esv"
    if col_map:
        df = df.rename(col_map)

    # Filter
    df = df.filter(
        (pl.col("Assembly") == "GRCh37")
        & (pl.col("Type") == "single nucleotide variant")
        & (pl.col("RS").is_not_null())
        & (pl.col("RS") != "-1")
        & (pl.col("RS") != "")
        & (pl.col("Chromosome").is_not_null())
        & (pl.col("PositionVCF").is_not_null())
        & (pl.col("ReferenceAlleleVCF").is_not_null())
        & (pl.col("AlternateAlleleVCF").is_not_null())
    )
    log.info(f"  After filtering (GRCh37 + SNV + has rsID): {len(df):,}")

    # Deduplicate by RS — keep the row with the most severe significance
    # Add a priority column for sorting
    df = df.with_columns(
        pl.col("ClinicalSignificance").map_elements(
            lambda x: SIGNIFICANCE_PRIORITY.get(
                _normalize_significance(x).replace("_", " "), -1
            ),
            return_dtype=pl.Int32,
        ).alias("_sig_priority")
    )
    df = df.sort("_sig_priority", descending=True).unique(subset=["RS"], keep="first")
    df = df.drop("_sig_priority")
    log.info(f"  After dedup by rsID: {len(df):,}")

    return df


async def import_variants(df: pl.DataFrame, dry_run: bool = False) -> None:
    """Bulk upsert ClinVar variants into snps table."""
    if dry_run:
        log.info("DRY RUN — no database writes")
        # Show sample
        sample = df.head(5).select(
            "RS", "Chromosome", "PositionVCF", "GeneSymbol",
            "ClinicalSignificance", "PhenotypeList", "ReviewStatus",
        )
        print(sample)
        return

    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    t0 = time.perf_counter()
    batch_size = 5000
    n_new = 0
    n_updated = 0

    async with async_session() as session:
        # Get existing rsids to track new vs updated
        result = await session.execute(text("SELECT rsid FROM snps"))
        existing = {row[0] for row in result}
        log.info(f"Existing SNPs in database: {len(existing):,}")

        total = len(df)
        for i in range(0, total, batch_size):
            batch = df.slice(i, batch_size)
            values_list = []

            for row in batch.iter_rows(named=True):
                rsid = f"rs{row['RS']}"
                chrom = row["Chromosome"]
                position = row["PositionVCF"]
                ref = row["ReferenceAlleleVCF"]
                alt = row["AlternateAlleleVCF"]
                gene = _first_gene(row.get("GeneSymbol", ""))
                significance = _normalize_significance(row.get("ClinicalSignificance", ""))
                conditions = row.get("PhenotypeList", "")
                if conditions and conditions != "not provided":
                    conditions = conditions.replace("|", "; ")
                else:
                    conditions = None
                stars = _review_stars(row.get("ReviewStatus", ""))
                allele_id = row.get("AlleleID")
                submitter_count = row.get("NumberSubmitters")

                try:
                    position = int(position)
                except (ValueError, TypeError):
                    continue
                try:
                    allele_id = int(allele_id) if allele_id else None
                except (ValueError, TypeError):
                    allele_id = None
                try:
                    submitter_count = int(submitter_count) if submitter_count else None
                except (ValueError, TypeError):
                    submitter_count = None

                if rsid in existing:
                    n_updated += 1
                else:
                    n_new += 1

                values_list.append({
                    "rsid": rsid,
                    "chrom": chrom[:2],
                    "position": position,
                    "ref_allele": ref[:255],
                    "alt_allele": alt[:255],
                    "gene": gene,
                    "clinvar_significance": significance,
                    "clinvar_conditions": conditions,
                    "clinvar_review_stars": stars,
                    "clinvar_allele_id": allele_id,
                    "clinvar_submitter_count": submitter_count,
                })

            if not values_list:
                continue

            # Build upsert SQL
            await session.execute(
                text("""
                    INSERT INTO snps (rsid, chrom, position, ref_allele, alt_allele, gene,
                        clinvar_significance, clinvar_conditions, clinvar_review_stars,
                        clinvar_allele_id, clinvar_submitter_count)
                    VALUES (:rsid, :chrom, :position, :ref_allele, :alt_allele, :gene,
                        :clinvar_significance, :clinvar_conditions, :clinvar_review_stars,
                        :clinvar_allele_id, :clinvar_submitter_count)
                    ON CONFLICT (rsid) DO UPDATE SET
                        clinvar_significance = EXCLUDED.clinvar_significance,
                        clinvar_conditions = EXCLUDED.clinvar_conditions,
                        clinvar_review_stars = EXCLUDED.clinvar_review_stars,
                        clinvar_allele_id = EXCLUDED.clinvar_allele_id,
                        clinvar_submitter_count = EXCLUDED.clinvar_submitter_count,
                        chrom = COALESCE(snps.chrom, EXCLUDED.chrom),
                        position = COALESCE(snps.position, EXCLUDED.position),
                        ref_allele = COALESCE(snps.ref_allele, EXCLUDED.ref_allele),
                        alt_allele = COALESCE(snps.alt_allele, EXCLUDED.alt_allele),
                        gene = COALESCE(snps.gene, EXCLUDED.gene)
                """),
                values_list,
            )

            if (i // batch_size) % 20 == 0:
                log.info(f"  Progress: {min(i + batch_size, total):,} / {total:,} ...")

        await session.commit()

    elapsed = time.perf_counter() - t0
    log.info(f"Done in {elapsed:.1f}s — {n_new:,} new, {n_updated:,} updated")
    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Import ClinVar variants into snps table")
    parser.add_argument("--file", type=str, help="Path to local variant_summary.txt.gz")
    parser.add_argument("--dry-run", action="store_true", help="Count and preview only")
    args = parser.parse_args()

    if args.file:
        file_path = Path(args.file)
    else:
        file_path = download_clinvar(DOWNLOAD_DIR)

    df = load_and_filter(file_path)

    if len(df) == 0:
        log.warning("No variants matched filters — nothing to import")
        return

    asyncio.run(import_variants(df, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
