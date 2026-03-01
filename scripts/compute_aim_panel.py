"""Compute an Ancestry-Informative Marker (AIM) panel from 1000 Genomes Phase 3.

Downloads sites-only VCFs from 1000G, computes Wright's Fst for each biallelic
SNP across the 5 superpopulations (EUR, AFR, EAS, SAS, AMR), LD-prunes, and
selects the top ~500 high-Fst markers. Outputs app/data/aim_panel.json.

Usage:
    python -m scripts.compute_aim_panel [--n-markers 500] [--keep-vcfs]

Requires ~1.2GB temporary disk space for VCF downloads (deleted after unless --keep-vcfs).
Takes ~15-30 minutes depending on download speed.
"""

from __future__ import annotations

import argparse
import gzip
import json
import logging
import os
import sys
import time
from pathlib import Path
from urllib.request import urlretrieve

import polars as pl

log = logging.getLogger(__name__)

# 1000 Genomes Phase 3 sites VCF URL pattern
_1KG_BASE = "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502"
_1KG_PATTERN = "ALL.chr{chrom}.phase3_shapeit2_mvncall_integrated_v5b.20130502.sites.vcf.gz"

# 1000G superpopulation sample sizes (Phase 3)
SUPERPOP_N = {"EUR": 503, "AFR": 661, "EAS": 504, "SAS": 489, "AMR": 347}
POPULATIONS = list(SUPERPOP_N.keys())
TOTAL_N = sum(SUPERPOP_N.values())

# Output path
OUTPUT_PATH = Path(__file__).resolve().parent.parent / "app" / "data" / "aim_panel.json"


def download_chromosome(chrom: int, dest_dir: Path) -> Path:
    """Download a single chromosome's sites VCF from 1000G FTP."""
    filename = _1KG_PATTERN.format(chrom=chrom)
    url = f"{_1KG_BASE}/{filename}"
    dest = dest_dir / filename

    if dest.exists():
        log.info(f"  chr{chrom}: already downloaded ({dest.stat().st_size / 1e6:.1f} MB)")
        return dest

    log.info(f"  chr{chrom}: downloading from {url} ...")
    t0 = time.time()
    urlretrieve(url, dest)
    elapsed = time.time() - t0
    size_mb = dest.stat().st_size / 1e6
    log.info(f"  chr{chrom}: done ({size_mb:.1f} MB in {elapsed:.0f}s)")
    return dest


def parse_vcf_info_afs(vcf_path: Path) -> pl.DataFrame:
    """Parse a 1000G sites VCF, extracting rsID + superpopulation AFs from INFO.

    Only keeps biallelic SNPs with an rs* ID and all 5 superpop AFs present.
    """
    rows = []
    af_keys = {f"{pop}_AF" for pop in POPULATIONS}

    with gzip.open(vcf_path, "rt") as f:
        for line in f:
            if line.startswith("#"):
                continue

            fields = line.split("\t", 8)  # CHROM POS ID REF ALT QUAL FILTER INFO
            if len(fields) < 8:
                continue

            chrom, pos, rsid, ref, alt = fields[0], fields[1], fields[2], fields[3], fields[4]

            # Skip non-rs IDs, multiallelic, and indels
            if not rsid.startswith("rs"):
                continue
            if "," in alt:
                continue
            if len(ref) != 1 or len(alt) != 1:
                continue

            # Parse INFO field for superpopulation AFs
            info = fields[7]
            afs = {}
            for part in info.split(";"):
                if "=" in part:
                    key, val = part.split("=", 1)
                    if key in af_keys:
                        try:
                            afs[key] = float(val)
                        except ValueError:
                            pass

            if len(afs) != 5:
                continue

            rows.append({
                "rsid": rsid,
                "chrom": chrom,
                "position": int(pos),
                "ref": ref,
                "alt": alt,
                "eur_af": afs["EUR_AF"],
                "afr_af": afs["AFR_AF"],
                "eas_af": afs["EAS_AF"],
                "sas_af": afs["SAS_AF"],
                "amr_af": afs["AMR_AF"],
            })

    if not rows:
        return pl.DataFrame()

    return pl.DataFrame(rows)


def compute_fst(df: pl.DataFrame) -> pl.DataFrame:
    """Compute Wright's Fst for each variant across the 5 superpopulations.

    Uses the weighted Fst estimator:
        p_bar = Σ(n_k * p_k) / Σ(n_k)
        Fst = Σ(n_k * (p_k - p_bar)²) / (Σ(n_k) * p_bar * (1 - p_bar))
    """
    af_cols = ["eur_af", "afr_af", "eas_af", "sas_af", "amr_af"]
    weights = [SUPERPOP_N[pop] for pop in POPULATIONS]

    # Weighted mean allele frequency
    p_bar = sum(w * pl.col(c) for w, c in zip(weights, af_cols)) / TOTAL_N

    # Weighted variance: Σ(n_k * (p_k - p_bar)²) / Σ(n_k)
    var_expr = sum(
        w * (pl.col(c) - p_bar) ** 2 for w, c in zip(weights, af_cols)
    ) / TOTAL_N

    # Fst = var / (p_bar * (1 - p_bar))
    # Avoid division by zero for fixed variants
    denominator = p_bar * (1.0 - p_bar)

    return df.with_columns(
        p_bar.alias("p_bar"),
        pl.when(denominator > 0.0)
        .then(var_expr / denominator)
        .otherwise(0.0)
        .alias("fst"),
    )


def ld_prune(df: pl.DataFrame, window_kb: int = 500) -> pl.DataFrame:
    """Keep only the highest-Fst SNP within each genomic window.

    Simple LD-pruning by position: for each chrom, divide into windows
    and keep the variant with the highest Fst in each window.
    """
    window_bp = window_kb * 1000
    return (
        df.with_columns(
            (pl.col("position") // window_bp).alias("window")
        )
        .sort("fst", descending=True)
        .group_by(["chrom", "window"])
        .first()
        .drop("window")
        .sort("fst", descending=True)
    )


def parse_wgs_vcf_streaming(vcf_path: Path, min_fst: float = 0.15, min_maf: float = 0.05) -> pl.DataFrame:
    """Parse the whole-genome sites VCF, computing Fst on the fly.

    Does NOT require rsIDs — uses chrom+position as the identifier.
    Filters by Fst and MAF during parsing to avoid storing 81M rows in memory.
    Only keeps high-Fst variants (candidate AIMs).
    """
    try:
        from isal import igzip
        opener = igzip.open
        log.info("  Using isal for accelerated decompression")
    except ImportError:
        opener = gzip.open

    rows = []
    af_keys = {f"{pop}_AF" for pop in POPULATIONS}
    pop_weights = [SUPERPOP_N[pop] for pop in POPULATIONS]
    n_lines = 0
    n_passed = 0

    with opener(str(vcf_path), "rt") as f:
        for line in f:
            if line.startswith("#"):
                continue
            n_lines += 1
            if n_lines % 10_000_000 == 0:
                log.info(f"  Processed {n_lines / 1e6:.0f}M lines, kept {n_passed:,} high-Fst SNPs...")

            fields = line.split("\t", 8)
            if len(fields) < 8:
                continue

            chrom, pos, rsid, ref, alt = fields[0], fields[1], fields[2], fields[3], fields[4]

            # Skip multiallelic and indels
            if "," in alt:
                continue
            if len(ref) != 1 or len(alt) != 1:
                continue

            # Parse INFO field for superpopulation AFs
            info = fields[7]
            afs = {}
            for part in info.split(";"):
                if "=" in part:
                    key, val = part.split("=", 1)
                    if key in af_keys:
                        try:
                            afs[key] = float(val)
                        except ValueError:
                            pass

            if len(afs) != 5:
                continue

            pop_afs = [afs[f"{pop}_AF"] for pop in POPULATIONS]

            # Compute Fst inline
            p_bar = sum(w * p for w, p in zip(pop_weights, pop_afs)) / TOTAL_N

            # MAF filter
            if p_bar < min_maf or p_bar > (1.0 - min_maf):
                continue

            denom = p_bar * (1.0 - p_bar)
            if denom <= 0:
                continue

            var = sum(w * (p - p_bar) ** 2 for w, p in zip(pop_weights, pop_afs)) / TOTAL_N
            fst = var / denom

            if fst < min_fst:
                continue

            pos_int = int(pos)
            resolved_rsid = rsid if rsid.startswith("rs") else f"{chrom}:{pos_int}"

            rows.append({
                "rsid": resolved_rsid,
                "chrom": chrom,
                "position": pos_int,
                "ref": ref,
                "alt": alt,
                "eur_af": afs["EUR_AF"],
                "afr_af": afs["AFR_AF"],
                "eas_af": afs["EAS_AF"],
                "sas_af": afs["SAS_AF"],
                "amr_af": afs["AMR_AF"],
                "fst": fst,
                "p_bar": p_bar,
            })
            n_passed += 1

    log.info(f"  Parsed {n_lines / 1e6:.0f}M lines, kept {n_passed:,} high-Fst SNPs")
    return pl.DataFrame(rows) if rows else pl.DataFrame()


def load_from_database() -> pl.DataFrame:
    """Load per-population AFs from prs_variant_weights + snps tables.

    AFs in the database are aligned to the PRS effect allele. For the AIM panel,
    we need AFs aligned to the VCF ALT allele (since the ancestry estimator counts
    copies of the ALT allele). For markers where effect_is_alt=False, we flip the
    AFs back: alt_af = 1 - effect_af.
    """
    import asyncio
    from sqlalchemy import text as sa_text
    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession as AsyncSess
    from sqlalchemy.orm import sessionmaker as sm
    from app.config import settings

    async def _load():
        engine = create_async_engine(settings.database_url)
        async_session = sm(engine, class_=AsyncSess)
        async with async_session() as session:
            result = await session.execute(sa_text("""
                SELECT DISTINCT ON (w.rsid)
                    w.rsid, w.chrom, w.position,
                    s.ref_allele, s.alt_allele,
                    w.effect_is_alt,
                    w.eur_af, w.afr_af, w.eas_af, w.sas_af, w.amr_af
                FROM prs_variant_weights w
                JOIN snps s ON s.rsid = w.rsid
                WHERE w.eur_af IS NOT NULL
                  AND w.afr_af IS NOT NULL
                  AND w.eas_af IS NOT NULL
                  AND w.sas_af IS NOT NULL
                  AND w.amr_af IS NOT NULL
                  AND w.effect_is_alt IS NOT NULL
                  AND s.alt_allele IS NOT NULL
                ORDER BY w.rsid
            """))
            rows = result.fetchall()
        await engine.dispose()
        return rows

    rows = asyncio.run(_load())
    if not rows:
        return pl.DataFrame()

    # Convert effect-allele AFs to VCF ALT AFs
    rsids, chroms, positions, refs, alts = [], [], [], [], []
    eur_afs, afr_afs, eas_afs, sas_afs, amr_afs = [], [], [], [], []

    for r in rows:
        rsids.append(r.rsid)
        chroms.append(r.chrom)
        positions.append(r.position)
        refs.append(r.ref_allele)
        alts.append(r.alt_allele)

        if r.effect_is_alt:
            # Effect allele = ALT → stored AFs are already ALT AFs
            eur_afs.append(r.eur_af)
            afr_afs.append(r.afr_af)
            eas_afs.append(r.eas_af)
            sas_afs.append(r.sas_af)
            amr_afs.append(r.amr_af)
        else:
            # Effect allele = REF → stored AFs are REF AFs → flip to get ALT AFs
            eur_afs.append(1.0 - r.eur_af)
            afr_afs.append(1.0 - r.afr_af)
            eas_afs.append(1.0 - r.eas_af)
            sas_afs.append(1.0 - r.sas_af)
            amr_afs.append(1.0 - r.amr_af)

    log.info(f"  Loaded {len(rows):,} variants with all 5 superpop AFs from database")
    return pl.DataFrame({
        "rsid": rsids,
        "chrom": chroms,
        "position": positions,
        "ref": refs,
        "alt": alts,
        "eur_af": eur_afs,
        "afr_af": afr_afs,
        "eas_af": eas_afs,
        "sas_af": sas_afs,
        "amr_af": amr_afs,
    })


def main():
    parser = argparse.ArgumentParser(description="Compute AIM panel from 1000 Genomes Phase 3")
    parser.add_argument("--n-markers", type=int, default=500, help="Number of AIMs to select")
    parser.add_argument("--keep-vcfs", action="store_true", help="Don't delete downloaded VCFs")
    parser.add_argument("--vcf-dir", type=str, default=None, help="Directory for VCF downloads")
    parser.add_argument("--wgs-vcf", type=str, default=None,
                        help="Path to whole-genome sites VCF (skips per-chrom download)")
    parser.add_argument("--from-db", action="store_true",
                        help="Use AFs already loaded in prs_variant_weights table (fastest)")
    parser.add_argument("--min-fst", type=float, default=0.15, help="Minimum Fst threshold")
    parser.add_argument("--min-maf", type=float, default=0.05, help="Minimum global MAF")
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")

    if args.from_db:
        log.info("Step 1-2: Loading AFs from database...")
        combined = load_from_database()
    elif args.wgs_vcf:
        wgs_path = Path(args.wgs_vcf)
        if not wgs_path.exists():
            log.error(f"VCF not found: {wgs_path}")
            sys.exit(1)
        log.info(f"Step 1-2: Parsing whole-genome sites VCF: {wgs_path} ({wgs_path.stat().st_size / 1e9:.1f} GB)")
        combined = parse_wgs_vcf_streaming(wgs_path, min_fst=args.min_fst, min_maf=args.min_maf)
    else:
        vcf_dir = Path(args.vcf_dir) if args.vcf_dir else Path("/tmp/1kg_sites_vcf")
        vcf_dir.mkdir(parents=True, exist_ok=True)

        log.info("Step 1: Downloading 1000 Genomes Phase 3 sites VCFs...")
        vcf_paths = []
        for chrom in range(1, 23):
            vcf_paths.append(download_chromosome(chrom, vcf_dir))

        log.info("Step 2: Parsing VCFs and extracting allele frequencies...")
        all_dfs = []
        for i, vcf_path in enumerate(vcf_paths):
            chrom = i + 1
            log.info(f"  Parsing chr{chrom}...")
            t0 = time.time()
            df = parse_vcf_info_afs(vcf_path)
            elapsed = time.time() - t0
            log.info(f"  chr{chrom}: {len(df)} biallelic SNPs with rs IDs in {elapsed:.1f}s")
            if len(df) > 0:
                all_dfs.append(df)

        if not all_dfs:
            log.error("No variants found! Check VCF download.")
            sys.exit(1)

        combined = pl.concat(all_dfs)

    log.info(f"Total: {len(combined)} variants across all chromosomes")

    if len(combined) == 0:
        log.error("No variants found!")
        sys.exit(1)

    # Step 3-4: Compute Fst then filter by MAF
    # (skip if already computed during streaming parse)
    if "fst" not in combined.columns:
        log.info("Step 3: Computing Fst...")
        combined = compute_fst(combined)

        log.info(f"Step 4: Filtering by global MAF >= {args.min_maf}...")
        combined = combined.filter(
            (pl.col("p_bar") >= args.min_maf) & (pl.col("p_bar") <= (1.0 - args.min_maf))
        )
        log.info(f"After MAF filter: {len(combined)} variants")

        # Filter by Fst
        combined = combined.filter(pl.col("fst") >= args.min_fst)
        log.info(f"After Fst >= {args.min_fst} filter: {len(combined)} variants")
    else:
        log.info(f"Step 3-4: Fst and MAF already computed during streaming parse")

    # Step 5: LD prune
    log.info("Step 5: LD pruning (500kb windows)...")
    pruned = ld_prune(combined)
    log.info(f"After LD pruning: {len(pruned)} variants")

    # Step 6: Select top N markers
    top = pruned.sort("fst", descending=True).head(args.n_markers)
    log.info(f"Selected top {len(top)} markers (Fst range: {top['fst'].min():.3f} - {top['fst'].max():.3f})")

    # Step 7: Export to JSON
    log.info(f"Step 7: Exporting to {OUTPUT_PATH}...")
    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    markers = []
    for row in top.sort(["chrom", "position"]).iter_rows(named=True):
        markers.append({
            "rsid": row["rsid"],
            "chrom": row["chrom"],
            "position": row["position"],
            "ref": row["ref"],
            "alt": row["alt"],
            "fst": round(row["fst"], 6),
            "af": {
                "EUR": round(row["eur_af"], 6),
                "AFR": round(row["afr_af"], 6),
                "EAS": round(row["eas_af"], 6),
                "SAS": round(row["sas_af"], 6),
                "AMR": round(row["amr_af"], 6),
            },
        })

    panel = {
        "version": "1.0",
        "source": "1000 Genomes Phase 3 (GRCh37)",
        "method": "Wright's Fst, LD-pruned 500kb windows",
        "n_markers": len(markers),
        "populations": POPULATIONS,
        "population_sample_sizes": SUPERPOP_N,
        "markers": markers,
    }

    with open(OUTPUT_PATH, "w") as f:
        json.dump(panel, f, indent=2)

    log.info(f"Done! {len(markers)} AIMs written to {OUTPUT_PATH}")

    # Cleanup
    if not args.from_db and not args.wgs_vcf and not args.keep_vcfs:
        log.info("Cleaning up downloaded VCFs...")
        for p in vcf_paths:
            if p.exists():
                p.unlink()
        log.info("VCFs deleted.")

    # Print summary statistics
    fst_vals = top["fst"]
    log.info(f"\nPanel summary:")
    log.info(f"  Markers: {len(markers)}")
    log.info(f"  Fst range: {fst_vals.min():.4f} - {fst_vals.max():.4f}")
    log.info(f"  Fst median: {fst_vals.median():.4f}")
    log.info(f"  Chromosomes covered: {top['chrom'].n_unique()}")


if __name__ == "__main__":
    main()
