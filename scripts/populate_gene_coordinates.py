"""Populate gene coordinates from NCBI RefSeq GFF files.

Downloads GRCh37 and GRCh38 GFF annotation files from NCBI and extracts
gene boundaries (chrom, start, end) for all genes matching our genes table.

Usage:
    python -m scripts.populate_gene_coordinates [--grch38-only] [--dry-run]
"""

from __future__ import annotations

import argparse
import gzip
import logging
import re
import sys
import urllib.request
from pathlib import Path
from tempfile import NamedTemporaryFile

from sqlalchemy import text, create_engine

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s  %(message)s")
log = logging.getLogger(__name__)

GFF_URLS = {
    "GRCh38": "https://ftp.ncbi.nlm.nih.gov/refseq/H_sapiens/annotation/GRCh38_latest/refseq_identifiers/GRCh38_latest_genomic.gff.gz",
    "GRCh37": "https://ftp.ncbi.nlm.nih.gov/refseq/H_sapiens/annotation/GRCh37_latest/refseq_identifiers/GRCh37_latest_genomic.gff.gz",
}

# RefSeq chromosome accession → simple chromosome name
# GRCh38 assembled chromosomes
_CHROM_MAP_38 = {
    f"NC_{str(i).zfill(6)}.{v}": str(i) if i <= 22 else ("X" if i == 23 else "Y")
    for i, v in [
        (1, 11), (2, 12), (3, 12), (4, 12), (5, 10), (6, 12),
        (7, 14), (8, 11), (9, 12), (10, 11), (11, 10), (12, 12),
        (13, 11), (14, 9), (15, 10), (16, 10), (17, 11), (18, 11),
        (19, 10), (20, 11), (21, 9), (22, 11), (23, 11), (24, 10),
    ]
}
# GRCh37
_CHROM_MAP_37 = {
    f"NC_{str(i).zfill(6)}.{v}": str(i) if i <= 22 else ("X" if i == 23 else "Y")
    for i, v in [
        (1, 10), (2, 11), (3, 11), (4, 11), (5, 9), (6, 11),
        (7, 13), (8, 10), (9, 11), (10, 10), (11, 9), (12, 11),
        (13, 10), (14, 8), (15, 9), (16, 9), (17, 10), (18, 10),
        (19, 9), (20, 10), (21, 8), (22, 10), (23, 10), (24, 9),
    ]
}

_GENE_RE = re.compile(r"(?:^|;)gene=([^;]+)")


def _download_gff(url: str, dest: Path) -> Path:
    """Download GFF file if not already cached."""
    if dest.exists():
        log.info(f"Using cached {dest}")
        return dest
    log.info(f"Downloading {url} ...")
    urllib.request.urlretrieve(url, dest)
    log.info(f"Downloaded to {dest} ({dest.stat().st_size / 1e6:.1f} MB)")
    return dest


def parse_gff_genes(gff_path: Path, chrom_map: dict[str, str]) -> dict[str, tuple[str, int, int]]:
    """Parse gene features from GFF, returning {symbol: (chrom, start, end)}.

    For genes appearing on multiple chromosomes or with multiple entries,
    keeps the longest span on assembled chromosomes only.
    """
    genes: dict[str, tuple[str, int, int]] = {}
    n_parsed = 0

    with gzip.open(gff_path, "rt") as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.split("\t")
            if len(parts) < 9 or parts[2] != "gene":
                continue

            accession = parts[0]
            chrom = chrom_map.get(accession)
            if not chrom:
                # Skip unplaced scaffolds, patches, alts
                continue

            start = int(parts[3])
            end = int(parts[4])
            attrs = parts[8]

            m = _GENE_RE.search(attrs)
            if not m:
                continue
            symbol = m.group(1)
            n_parsed += 1

            # Keep longest span if gene appears multiple times
            if symbol in genes:
                existing_chrom, existing_start, existing_end = genes[symbol]
                existing_len = existing_end - existing_start
                new_len = end - start
                if new_len <= existing_len:
                    continue

            genes[symbol] = (chrom, start, end)

    log.info(f"Parsed {n_parsed} gene features → {len(genes)} unique genes")
    return genes


def main() -> None:
    parser = argparse.ArgumentParser(description="Populate gene coordinates from NCBI RefSeq GFF")
    parser.add_argument("--grch38-only", action="store_true", help="Only populate GRCh38 coordinates")
    parser.add_argument("--dry-run", action="store_true", help="Parse and report without writing to DB")
    parser.add_argument("--cache-dir", type=Path, default=Path("/tmp"), help="Directory to cache downloaded GFFs")
    args = parser.parse_args()

    cache_dir = args.cache_dir
    cache_dir.mkdir(parents=True, exist_ok=True)

    # Parse GRCh38
    gff38_path = _download_gff(GFF_URLS["GRCh38"], cache_dir / "GRCh38_latest_genomic.gff.gz")
    genes_38 = parse_gff_genes(gff38_path, _CHROM_MAP_38)

    # Parse GRCh37
    genes_37: dict[str, tuple[str, int, int]] = {}
    if not args.grch38_only:
        gff37_path = _download_gff(GFF_URLS["GRCh37"], cache_dir / "GRCh37_latest_genomic.gff.gz")
        genes_37 = parse_gff_genes(gff37_path, _CHROM_MAP_37)

    if args.dry_run:
        # Show sample
        sample = list(genes_38.items())[:10]
        for sym, (chrom, start, end) in sample:
            g37 = genes_37.get(sym)
            log.info(f"  {sym}: chr{chrom}:{start}-{end} (GRCh38)"
                     + (f", {g37[1]}-{g37[2]} (GRCh37)" if g37 else ""))
        log.info(f"Total: {len(genes_38)} GRCh38, {len(genes_37)} GRCh37")
        return

    # Write to DB
    sync_url = settings.database_url.replace("+asyncpg", "").replace("postgresql+asyncpg", "postgresql")
    engine = create_engine(sync_url)

    with engine.begin() as conn:
        # Get existing gene symbols
        result = conn.execute(text("SELECT symbol FROM genes"))
        existing_symbols = {row[0] for row in result}
        log.info(f"Genes in DB: {len(existing_symbols)}")

        # Build update data
        updates = []
        for symbol in existing_symbols:
            g38 = genes_38.get(symbol)
            g37 = genes_37.get(symbol)
            if not g38 and not g37:
                continue
            row = {"symbol": symbol}
            if g38:
                row["chrom"] = g38[0]
                row["start_38"] = g38[1]
                row["end_38"] = g38[2]
            if g37:
                row["chrom"] = row.get("chrom") or g37[0]
                row["start_37"] = g37[1]
                row["end_37"] = g37[2]
            updates.append(row)

        log.info(f"Updating coordinates for {len(updates)} genes")

        # Batch update using unnest
        if updates:
            symbols = [u["symbol"] for u in updates]
            chroms = [u.get("chrom") for u in updates]
            starts_37 = [u.get("start_37") for u in updates]
            ends_37 = [u.get("end_37") for u in updates]
            starts_38 = [u.get("start_38") for u in updates]
            ends_38 = [u.get("end_38") for u in updates]

            conn.execute(
                text("""
                    UPDATE genes SET
                        chrom = data.chrom,
                        start_position_grch37 = data.start_37,
                        end_position_grch37 = data.end_37,
                        start_position_grch38 = data.start_38,
                        end_position_grch38 = data.end_38
                    FROM (
                        SELECT unnest(:symbols) AS symbol,
                               unnest(:chroms) AS chrom,
                               unnest(:starts_37) AS start_37,
                               unnest(:ends_37) AS end_37,
                               unnest(:starts_38) AS start_38,
                               unnest(:ends_38) AS end_38
                    ) AS data
                    WHERE genes.symbol = data.symbol
                """),
                {
                    "symbols": symbols,
                    "chroms": chroms,
                    "starts_37": starts_37,
                    "ends_37": ends_37,
                    "starts_38": starts_38,
                    "ends_38": ends_38,
                },
            )

        # Report
        result = conn.execute(text("SELECT COUNT(*) FROM genes WHERE chrom IS NOT NULL"))
        n_with_coords = result.scalar()
        log.info(f"Done. {n_with_coords} genes now have coordinates.")

        # Spot check
        result = conn.execute(text(
            "SELECT symbol, chrom, start_position_grch38, end_position_grch38 "
            "FROM genes WHERE symbol IN ('BRCA1', 'APOE', 'CYP2D6') ORDER BY symbol"
        ))
        for row in result:
            log.info(f"  {row[0]}: chr{row[1]}:{row[2]}-{row[3]}")

    engine.dispose()


if __name__ == "__main__":
    main()
