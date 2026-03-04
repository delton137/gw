"""Build Aeon reference parquet from allele frequency file.

One-time script that:
1. Reads Aeon's g1k_allele_freqs.txt (128,097 AILs × 26 populations)
2. Parses variant IDs into chrom/position/ref/alt
3. Optionally resolves rsids via MyVariant.info (slow, ~30 min)
4. Optionally adds GRCh37 positions via pyliftover
5. Outputs app/data/aeon_reference.parquet

The primary matching strategy is chromosome+position, so rsid resolution
is optional. Pass --with-rsids to enable MyVariant.info lookups.
Pass --with-grch37 to add GRCh37 position column via liftover.

Usage:
    python -m scripts.build_aeon_reference                          # fast
    python -m scripts.build_aeon_reference --with-rsids             # slow, includes rsids
    python -m scripts.build_aeon_reference --with-grch37            # adds GRCh37 positions
    python -m scripts.build_aeon_reference --with-rsids --with-grch37  # both
"""

from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import polars as pl

log = logging.getLogger(__name__)

AEON_AF_PATH = Path(__file__).resolve().parent.parent / "existing_tools" / "aeon" / "aeon_ancestry" / "refs" / "g1k_allele_freqs.txt"
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "aeon_reference.parquet"

MYVARIANT_BATCH_URL = "http://myvariant.info/v1/variant"
BATCH_SIZE = 1000

POPULATIONS = [
    "ACB", "ASW", "BEB", "CDX", "CEU", "CHB", "CHS", "CLM", "ESN", "FIN",
    "GBR", "GIH", "GWD", "IBS", "ITU", "JPT", "KHV", "LWK", "MSL", "MXL",
    "PEL", "PJL", "PUR", "STU", "TSI", "YRI",
]


def _build_hgvs_id(var_id: str) -> str:
    """Convert Aeon VAR_ID to HGVS notation for MyVariant.info.

    'chr1_898818_T_C' → 'chr1:g.898818T>C'
    """
    parts = var_id.split("_")
    chrom, pos, ref, alt = parts[0], parts[1], parts[2], parts[3]
    return f"{chrom}:g.{pos}{ref}>{alt}"


def _query_rsids(hgvs_ids: list[str]) -> dict[str, str | None]:
    """Batch-query MyVariant.info for rsids (hg38 assembly).

    Returns dict mapping HGVS ID → rsid (or None if not found).
    """
    import requests

    result: dict[str, str | None] = {}

    for i in range(0, len(hgvs_ids), BATCH_SIZE):
        batch = hgvs_ids[i : i + BATCH_SIZE]
        batch_num = i // BATCH_SIZE + 1
        total_batches = (len(hgvs_ids) + BATCH_SIZE - 1) // BATCH_SIZE

        for attempt in range(3):
            try:
                resp = requests.post(
                    MYVARIANT_BATCH_URL,
                    data={
                        "ids": ",".join(batch),
                        "fields": "dbsnp.rsid",
                        "assembly": "hg38",
                    },
                    timeout=120,
                )
                resp.raise_for_status()
                data = resp.json()

                for item in data:
                    qid = item.get("query", item.get("_id", ""))
                    rsid = None
                    dbsnp = item.get("dbsnp")
                    if isinstance(dbsnp, dict):
                        rsid = dbsnp.get("rsid")
                    result[qid] = rsid

                resolved = sum(1 for v in result.values() if v is not None)
                print(
                    f"  Batch {batch_num}/{total_batches}: "
                    f"{len(batch)} queried, {resolved} total resolved",
                    flush=True,
                )
                break  # Success

            except Exception as e:
                if attempt < 2:
                    wait = (attempt + 1) * 5
                    print(
                        f"  Batch {batch_num} attempt {attempt + 1} failed: {e}, "
                        f"retrying in {wait}s...",
                        flush=True,
                    )
                    time.sleep(wait)
                else:
                    print(
                        f"  Batch {batch_num} failed after 3 attempts: {e}",
                        flush=True,
                    )
                    for hid in batch:
                        result.setdefault(hid, None)

        # Rate limit
        if i + BATCH_SIZE < len(hgvs_ids):
            time.sleep(1.0)

    return result


def _liftover_grch38_to_grch37(chroms: list[str], positions: list[int]) -> list[int | None]:
    """Convert GRCh38 positions to GRCh37 using pyliftover.

    Returns list of GRCh37 positions (None for failed conversions).
    """
    from pyliftover import LiftOver

    lo = LiftOver("hg38", "hg19")
    results: list[int | None] = []
    n_failed = 0

    for i, (chrom, pos) in enumerate(zip(chroms, positions)):
        # pyliftover expects 0-based, "chr"-prefixed chromosomes
        chrom_prefixed = f"chr{chrom}" if not chrom.startswith("chr") else chrom
        converted = lo.convert_coordinate(chrom_prefixed, pos - 1)  # 0-based
        if converted and len(converted) > 0:
            # converted[0] = (chrom, pos_0based, strand, score)
            results.append(converted[0][1] + 1)  # back to 1-based
        else:
            results.append(None)
            n_failed += 1

        if (i + 1) % 10000 == 0:
            print(f"  Lifted {i + 1:,}/{len(positions):,} positions...", flush=True)

    print(f"  Liftover complete: {len(positions) - n_failed:,} succeeded, {n_failed:,} failed", flush=True)
    return results


def main():
    parser = argparse.ArgumentParser(description="Build Aeon reference parquet")
    parser.add_argument(
        "--with-rsids",
        action="store_true",
        help="Query MyVariant.info for rsid mappings (slow, ~30 min)",
    )
    parser.add_argument(
        "--with-grch37",
        action="store_true",
        help="Add GRCh37 positions via pyliftover (takes ~1 min)",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    if not AEON_AF_PATH.exists():
        print(f"ERROR: Aeon allele frequency file not found: {AEON_AF_PATH}")
        print("Make sure existing_tools/aeon/ is present.")
        sys.exit(1)

    # Step 1: Read allele frequency file
    print(f"Reading {AEON_AF_PATH}...", flush=True)
    af_df = pl.read_csv(
        AEON_AF_PATH,
        separator="\t",
        schema_overrides={pop: pl.Float32 for pop in POPULATIONS},
    )
    print(f"  Loaded {len(af_df):,} variants × {len(af_df.columns)} columns", flush=True)

    # Step 2: Parse VAR_ID into components
    print("Parsing variant IDs...", flush=True)
    af_df = af_df.with_columns([
        pl.col("VAR_ID").map_elements(
            lambda v: v.split("_")[0].replace("chr", ""), return_dtype=pl.Utf8
        ).alias("chrom"),
        pl.col("VAR_ID").map_elements(
            lambda v: int(v.split("_")[1]), return_dtype=pl.Int64
        ).alias("position"),
        pl.col("VAR_ID").map_elements(
            lambda v: v.split("_")[2], return_dtype=pl.Utf8
        ).alias("ref"),
        pl.col("VAR_ID").map_elements(
            lambda v: v.split("_")[3], return_dtype=pl.Utf8
        ).alias("alt"),
    ])

    # Step 3: Optionally resolve rsids
    if args.with_rsids:
        var_ids = af_df["VAR_ID"].to_list()
        hgvs_ids = [_build_hgvs_id(v) for v in var_ids]

        print(f"Querying MyVariant.info for rsids ({len(hgvs_ids):,} variants)...", flush=True)
        rsid_map = _query_rsids(hgvs_ids)

        rsids = []
        for var_id in var_ids:
            hgvs = _build_hgvs_id(var_id)
            rsids.append(rsid_map.get(hgvs))

        af_df = af_df.with_columns(
            pl.Series("rsid", rsids, dtype=pl.Utf8)
        )
        n_resolved = sum(1 for r in rsids if r is not None)
        print(f"  Resolved {n_resolved:,}/{len(rsids):,} rsids ({n_resolved/len(rsids)*100:.1f}%)", flush=True)
    else:
        # No rsid lookup — add null column
        af_df = af_df.with_columns(
            pl.lit(None).cast(pl.Utf8).alias("rsid")
        )
        print("  Skipping rsid lookup (use --with-rsids to enable)", flush=True)

    # Step 4: Optionally add GRCh37 positions via liftover
    if args.with_grch37:
        print("Lifting over GRCh38 → GRCh37 positions...", flush=True)
        chroms = af_df["chrom"].to_list()
        positions = af_df["position"].to_list()
        grch37_positions = _liftover_grch38_to_grch37(chroms, positions)
        af_df = af_df.with_columns(
            pl.Series("position_grch37", grch37_positions, dtype=pl.Int64)
        )
        n_lifted = sum(1 for p in grch37_positions if p is not None)
        print(f"  {n_lifted:,}/{len(grch37_positions):,} positions lifted ({n_lifted/len(grch37_positions)*100:.1f}%)", flush=True)
    else:
        af_df = af_df.with_columns(
            pl.lit(None).cast(pl.Int64).alias("position_grch37")
        )
        print("  Skipping GRCh37 liftover (use --with-grch37 to enable)", flush=True)

    # Step 5: Select final columns and write parquet
    output_cols = ["rsid", "VAR_ID", "chrom", "position", "position_grch37", "ref", "alt"] + POPULATIONS
    af_df = af_df.select(output_cols).rename({"VAR_ID": "var_id"})

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    af_df.write_parquet(OUTPUT_PATH)
    size_mb = OUTPUT_PATH.stat().st_size / (1024 * 1024)
    print(f"\nWrote {OUTPUT_PATH} ({size_mb:.1f} MB, {len(af_df):,} rows)", flush=True)

    n_with_rsid = af_df.filter(pl.col("rsid").is_not_null()).shape[0]
    print(f"\nSummary:")
    print(f"  Total markers: {len(af_df):,}")
    print(f"  With rsid: {n_with_rsid:,} ({n_with_rsid/len(af_df)*100:.1f}%)")
    print(f"  With chrom+position: {len(af_df):,} (100%)")
    print(f"  Populations: {len(POPULATIONS)}")


if __name__ == "__main__":
    main()
