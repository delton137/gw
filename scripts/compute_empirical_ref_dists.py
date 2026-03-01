"""Compute empirical PRS reference distributions using PLINK2 on the HGDP+1kGP panel.

Scores 3,942 individuals from the HGDP+1kGP reference panel and computes
per-superpopulation mean/std from the actual score distribution. This captures
LD effects that the analytical formula (Var[S] = Σ 2·p·(1-p)·w²) misses,
which can dramatically underestimate variance for genome-wide PGS.

Reference panel: /media/dan/500Gb/work/ancestry/ref_extracted/GRCh37_HGDP+1kGP_ALL.{pgen,pvar.zst,psam}
PLINK2 Docker image: ghcr.io/pgscatalog/plink2:2.00a5.10

Three-step approach:
  1. Subset: --extract range to pull only target positions → small pfile
  2. Build scoring file: parse the subset pvar to get exact variant IDs,
     match effect alleles to pvar ALT/REF
  3. Score: --score on the small pfile (no ID renaming needed)

Usage:
    python -m scripts.compute_empirical_ref_dists --pgs-id PGS000039
    python -m scripts.compute_empirical_ref_dists --all
    python -m scripts.compute_empirical_ref_dists --all --ref-dir /path/to/ref
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import logging
import os
import shutil
import subprocess
import tempfile
import time

import numpy as np
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.base import Base
from app.models.prs import PrsReferenceDistribution, PrsScore

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DEFAULT_REF_DIR = "/media/dan/500Gb/work/ancestry/ref_extracted"
DEFAULT_DOCKER_IMAGE = "ghcr.io/pgscatalog/plink2:2.00a5.10"

# HGDP+1kGP uses "CSA" for Central/South Asian; gene-wizard uses "SAS"
SUPERPOP_MAP = {"CSA": "SAS"}


def load_psam(ref_dir: str, include_hgdp: bool = False) -> dict[str, str]:
    """Load psam file and return IID → SuperPop mapping.

    The psam has columns: #IID, SEX, SuperPop, Population, Project.

    By default, only 1kGP samples are included (Project == "gnomAD_1kG").
    HGDP samples use different superpopulation definitions (e.g., AMR includes
    indigenous Americans rather than admixed Latino) which inflates within-group
    variance due to population structure. Set include_hgdp=True to include them.
    """
    psam_path = os.path.join(ref_dir, "GRCh37_HGDP+1kGP_ALL.psam")
    iid_to_pop: dict[str, str] = {}
    with open(psam_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            if not include_hgdp and row["Project"] != "gnomAD_1kG":
                continue
            iid = row["#IID"]
            superpop = row["SuperPop"]
            superpop = SUPERPOP_MAP.get(superpop, superpop)
            iid_to_pop[iid] = superpop
    return iid_to_pop


def write_range_file(
    variants: list[tuple[str, str, int, str, float]], out_path: str
) -> int:
    """Write a PLINK2 --extract range file.

    Format: chrom start end label (1-indexed, inclusive positions).
    """
    with open(out_path, "w") as f:
        for _, chrom, position, _, _ in variants:
            f.write(f"{chrom}\t{position}\t{position}\tvar\n")
    return len(variants)


def parse_subset_pvar(pvar_path: str) -> dict[tuple[str, int], list[tuple[str, str, str]]]:
    """Parse the subsetted pvar to build (chrom, pos) → [(variant_id, ref, alt), ...] lookup.

    The pvar has columns: #CHROM, POS, ID, REF, ALT, QUAL, FILTER, INFO
    """
    pos_to_variants: dict[tuple[str, int], list[tuple[str, str, str]]] = {}
    with open(pvar_path) as f:
        for line in f:
            if line.startswith("#"):
                continue
            parts = line.rstrip("\n").split("\t")
            chrom, pos, vid, ref, alt = parts[0], int(parts[1]), parts[2], parts[3], parts[4]
            pos_to_variants.setdefault((chrom, pos), []).append((vid, ref, alt))
    return pos_to_variants


def write_scoring_file_from_pvar(
    variants: list[tuple[str, str, int, str, float]],
    pos_to_pvar: dict[tuple[str, int], list[tuple[str, str, str]]],
    out_path: str,
) -> tuple[int, int]:
    """Write scoring file using exact variant IDs from the pvar.

    For each PGS variant, find the matching pvar entry by (chrom, pos) AND
    by checking that the effect allele matches either REF or ALT.

    Returns (n_written, n_skipped).
    """
    n_written = 0
    n_skipped = 0
    with open(out_path, "w") as f:
        f.write("variant_id\teffect_allele\tweight\n")
        for rsid, chrom, position, effect_allele, weight in variants:
            pvar_entries = pos_to_pvar.get((chrom, position), [])
            matched = False
            for vid, ref, alt in pvar_entries:
                if effect_allele == alt or effect_allele == ref:
                    f.write(f"{vid}\t{effect_allele}\t{weight}\n")
                    n_written += 1
                    matched = True
                    break
            if not matched:
                n_skipped += 1
    return n_written, n_skipped


def run_plink2(
    cmd: list[str], description: str, timeout: int = 1800
) -> subprocess.CompletedProcess:
    """Run a PLINK2 command and log output."""
    log.info(f"  {description}...")
    log.info(f"  Command: {' '.join(cmd)}")

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)

    if result.returncode != 0:
        log.error(f"  PLINK2 failed (exit code {result.returncode}):")
        for line in result.stderr.splitlines():
            log.error(f"    {line}")
    else:
        for line in result.stderr.splitlines():
            stripped = line.strip()
            if any(kw in stripped.lower() for kw in [
                "variant", "score", "sample", "loaded", "warning",
                "written", "remaining", "excluded",
            ]):
                log.info(f"    PLINK2: {stripped}")

    return result


def subset_and_score(
    pgs_id: str,
    variants: list[tuple[str, str, int, str, float]],
    work_dir: str,
    ref_dir: str,
    docker_image: str,
) -> str | None:
    """Three-step PLINK2 pipeline.

    Step 1: Extract variants at target positions → small pfile
    Step 2: Parse subset pvar, write scoring file with exact variant IDs
    Step 3: Score the small pfile

    Returns path to .sscore file, or None on failure.
    """
    # Step 1: Subset the reference panel to target positions
    cmd_subset = [
        "docker", "run", "--rm",
        "-v", f"{ref_dir}:/ref:ro",
        "-v", f"{work_dir}:/work",
        docker_image,
        "plink2",
        "--threads", "4",
        "--pfile", "/ref/GRCh37_HGDP+1kGP_ALL", "vzs",
        "--extract", "range", f"/work/{pgs_id}_ranges.bed",
        "--make-pgen",
        "--out", f"/work/{pgs_id}_subset",
    ]

    result = run_plink2(cmd_subset, "Step 1: Subsetting reference panel by position range")
    if result.returncode != 0:
        return None

    # Step 2: Parse subset pvar and write scoring file with exact IDs
    log.info("  Step 2: Building scoring file from subset pvar...")
    subset_pvar = os.path.join(work_dir, f"{pgs_id}_subset.pvar")
    pos_to_pvar = parse_subset_pvar(subset_pvar)
    log.info(f"    Parsed {sum(len(v) for v in pos_to_pvar.values()):,} variant entries "
             f"at {len(pos_to_pvar):,} unique positions from subset pvar")

    scoring_path = os.path.join(work_dir, f"{pgs_id}_scoring.tsv")
    n_written, n_skipped = write_scoring_file_from_pvar(variants, pos_to_pvar, scoring_path)
    log.info(f"    Wrote {n_written:,} variants to scoring file ({n_skipped:,} skipped — no allele match)")

    if n_written == 0:
        log.error("  No variants matched — aborting")
        return None

    # Step 3: Score
    cmd_score = [
        "docker", "run", "--rm",
        "-v", f"{work_dir}:/work",
        docker_image,
        "plink2",
        "--threads", "4",
        "--pfile", f"/work/{pgs_id}_subset",
        "--score", f"/work/{pgs_id}_scoring.tsv", "header-read",
        "no-mean-imputation",
        "cols=+scoresums",
        "--out", f"/work/{pgs_id}_scores",
    ]

    result = run_plink2(cmd_score, "Step 3: Scoring subsetted panel")
    if result.returncode != 0:
        return None

    sscore_path = os.path.join(work_dir, f"{pgs_id}_scores.sscore")
    if not os.path.exists(sscore_path):
        log.error(f"  Expected output file not found: {sscore_path}")
        return None

    return sscore_path


def parse_sscore(sscore_path: str) -> dict[str, float]:
    """Parse PLINK2 .sscore file and return IID → raw score sum.

    With cols=+scoresums and header-read, PLINK2 names the score column
    after the scoring file weight header: "weight_SUM". We must use this
    specific column (not NAMED_ALLELE_DOSAGE_SUM which also ends in _SUM).
    """
    scores: dict[str, float] = {}
    with open(sscore_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        fieldnames = reader.fieldnames or []
        # Use weight_SUM specifically (our scoring file header is "weight")
        # Fall back to the last *_SUM column if weight_SUM not found
        if "weight_SUM" in fieldnames:
            sum_col = "weight_SUM"
        else:
            sum_cols = [c for c in fieldnames if c.endswith("_SUM") and c != "NAMED_ALLELE_DOSAGE_SUM"]
            if not sum_cols:
                raise ValueError(f"No score *_SUM column found in {sscore_path}. Columns: {fieldnames}")
            sum_col = sum_cols[0]
        log.info(f"    Using column '{sum_col}' from sscore")
        for row in reader:
            iid = row["#IID"]
            score_sum = float(row[sum_col])
            scores[iid] = score_sum
    return scores


def compute_pop_stats(
    scores: dict[str, float], iid_to_pop: dict[str, str]
) -> dict[str, tuple[float, float, int]]:
    """Compute per-superpopulation mean, std, and count.

    Returns: {pop: (mean, std, n_samples)}
    """
    pop_scores: dict[str, list[float]] = {}
    for iid, score in scores.items():
        pop = iid_to_pop.get(iid)
        if pop is None:
            continue
        pop_scores.setdefault(pop, []).append(score)

    results: dict[str, tuple[float, float, int]] = {}
    for pop, vals in sorted(pop_scores.items()):
        arr = np.array(vals)
        results[pop] = (float(np.mean(arr)), float(np.std(arr, ddof=1)), len(vals))

    return results


async def process_pgs(
    pgs_id: str,
    session: AsyncSession,
    ref_dir: str,
    docker_image: str,
    iid_to_pop: dict[str, str],
    work_dir: str,
) -> bool:
    """Process a single PGS: score reference panel, compute stats, update DB.

    Returns True on success.
    """
    t0 = time.perf_counter()

    # 1. Query DB for variant weights
    result = await session.execute(
        text("""
            SELECT rsid, chrom, position, effect_allele, weight
            FROM prs_variant_weights
            WHERE pgs_id = :pgs_id
        """),
        {"pgs_id": pgs_id},
    )
    rows = result.fetchall()
    if not rows:
        log.warning(f"{pgs_id}: No variant weights found, skipping")
        return False

    variants = [(r.rsid, r.chrom, r.position, r.effect_allele, r.weight) for r in rows]
    log.info(f"\n{pgs_id}: Scoring {len(variants):,} variants against reference panel...")

    # 2. Write range file for subsetting
    range_path = os.path.join(work_dir, f"{pgs_id}_ranges.bed")
    n_ranges = write_range_file(variants, range_path)
    log.info(f"  Wrote {n_ranges:,} position ranges")

    # 3. Run PLINK2 pipeline (subset → build scoring file → score)
    sscore_path = subset_and_score(pgs_id, variants, work_dir, ref_dir, docker_image)
    if sscore_path is None:
        return False

    # 4. Parse scores
    scores = parse_sscore(sscore_path)
    log.info(f"  Parsed scores for {len(scores):,} individuals")

    # 5. Compute per-population stats
    pop_stats = compute_pop_stats(scores, iid_to_pop)

    # 6. Load current analytical distributions for comparison
    # We keep the analytical mean (which matches the user's scoring basis) and
    # replace only the std with the empirical value (which captures LD effects).
    current = await session.execute(
        text("""
            SELECT ancestry_group, mean, std
            FROM prs_reference_distributions
            WHERE pgs_id = :pgs_id
        """),
        {"pgs_id": pgs_id},
    )
    analytical = {r.ancestry_group: (r.mean, r.std) for r in current.fetchall()}

    # 7. Log comparison and upsert into DB
    await session.execute(
        text("DELETE FROM prs_reference_distributions WHERE pgs_id = :pgs_id"),
        {"pgs_id": pgs_id},
    )

    for pop, (emp_mean, emp_std, n) in pop_stats.items():
        old_mean, old_std = analytical.get(pop, (None, None))

        # Use analytical mean (matches user scoring) + empirical std (captures LD)
        db_mean = old_mean if old_mean is not None else emp_mean
        db_std = emp_std

        if old_std is not None and old_std > 0:
            std_ratio = emp_std / old_std
            log.info(
                f"  {pop}: empirical mean={emp_mean:.6f}, std={emp_std:.6f} (n={n})"
                f"  [analytical: mean={old_mean:.6f}, std={old_std:.6f}, ratio={std_ratio:.2f}x]"
                f"  → DB: mean={db_mean:.6f}, std={db_std:.6f}"
            )
        else:
            log.info(
                f"  {pop}: empirical mean={emp_mean:.6f}, std={emp_std:.6f} (n={n})"
                f"  [no prior analytical dist]"
                f"  → DB: mean={db_mean:.6f}, std={db_std:.6f}"
            )

        await session.execute(
            text("""
                INSERT INTO prs_reference_distributions (pgs_id, ancestry_group, mean, std)
                VALUES (:pgs_id, :pop, :mean, :std)
            """),
            {"pgs_id": pgs_id, "pop": pop, "mean": db_mean, "std": db_std},
        )

    await session.commit()

    # Clean up intermediate subset files for this PGS (docker-owned)
    for suffix in [".pgen", ".pvar", ".psam", ".log",
                   "_scores.sscore", "_scores.log"]:
        path = os.path.join(work_dir, f"{pgs_id}_subset{suffix}")
        if os.path.exists(path):
            try:
                os.remove(path)
            except OSError:
                pass  # root-owned from Docker, will be cleaned up later

    elapsed = time.perf_counter() - t0
    log.info(f"  Done in {elapsed:.1f}s")
    return True


async def main(
    pgs_ids: list[str] | None,
    all_pgs: bool,
    ref_dir: str,
    docker_image: str,
    include_hgdp: bool = False,
) -> None:
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    # Load reference panel population info
    panel_label = "HGDP+1kGP" if include_hgdp else "1kGP only"
    log.info(f"Loading reference panel psam from {ref_dir} ({panel_label})...")
    iid_to_pop = load_psam(ref_dir, include_hgdp=include_hgdp)
    pop_counts: dict[str, int] = {}
    for pop in iid_to_pop.values():
        pop_counts[pop] = pop_counts.get(pop, 0) + 1
    log.info(f"  {len(iid_to_pop)} individuals: {dict(sorted(pop_counts.items()))}")

    async with async_session() as session:
        if pgs_ids:
            ids_to_process = pgs_ids
        elif all_pgs:
            result = await session.execute(select(PrsScore.pgs_id))
            ids_to_process = [r[0] for r in result.fetchall()]
        else:
            log.error("Specify --pgs-id or --all")
            await engine.dispose()
            return

        if not ids_to_process:
            log.warning("No PGS scores found to process")
            await engine.dispose()
            return

        log.info(f"Processing {len(ids_to_process)} PGS scores: {ids_to_process}")

        # Create temp work directory for PLINK2 files
        work_dir = tempfile.mkdtemp(prefix="pgs_empirical_")
        log.info(f"Work directory: {work_dir}")

        try:
            for pgs_id in ids_to_process:
                try:
                    await process_pgs(
                        pgs_id, session, ref_dir, docker_image, iid_to_pop, work_dir
                    )
                except Exception as e:
                    log.error(f"{pgs_id}: Failed: {e}", exc_info=True)
                    await session.rollback()
        finally:
            # Clean up temp files (use Docker to handle root-owned files)
            subprocess.run(
                ["docker", "run", "--rm", "-v", f"{work_dir}:/work",
                 "alpine", "rm", "-rf", "/work"],
                capture_output=True, timeout=30,
            )
            shutil.rmtree(work_dir, ignore_errors=True)
            log.info(f"Cleaned up work directory: {work_dir}")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Compute empirical PRS reference distributions using PLINK2 on HGDP+1kGP"
    )
    parser.add_argument(
        "--pgs-id", type=str, action="append", dest="pgs_ids",
        help="PGS ID to process (can be repeated, e.g. --pgs-id PGS000039 --pgs-id PGS000018)",
    )
    parser.add_argument(
        "--all", action="store_true",
        help="Process all PGS scores in the database",
    )
    parser.add_argument(
        "--ref-dir", type=str, default=DEFAULT_REF_DIR,
        help=f"Path to reference panel directory (default: {DEFAULT_REF_DIR})",
    )
    parser.add_argument(
        "--docker-image", type=str, default=DEFAULT_DOCKER_IMAGE,
        help=f"PLINK2 Docker image (default: {DEFAULT_DOCKER_IMAGE})",
    )
    parser.add_argument(
        "--include-hgdp", action="store_true",
        help="Include HGDP samples (default: 1kGP only). HGDP AMR populations "
             "are indigenous rather than admixed Latino, which inflates AMR std.",
    )
    args = parser.parse_args()

    if not args.pgs_ids and not args.all:
        parser.error("Must specify --pgs-id or --all")

    asyncio.run(main(args.pgs_ids, args.all, args.ref_dir, args.docker_image,
                      include_hgdp=args.include_hgdp))
