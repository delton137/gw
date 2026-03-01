"""Load 1000 Genomes Phase 3 per-superpopulation allele frequencies into PRS variant weights.

Downloads the 1000 Genomes whole-genome sites VCF (~1.4GB compressed) and extracts
per-superpopulation allele frequencies (EUR_AF, AFR_AF, EAS_AF, SAS_AF, AMR_AF)
for variants that appear in the prs_variant_weights table.

**Critical**: AFs are aligned to the PRS effect allele, not the VCF ALT allele.
If the PRS effect_allele matches the VCF ALT, the AF is stored as-is.
If the PRS effect_allele matches the VCF REF, the AF is flipped (1 - AF).

Usage:
    python -m scripts.load_1kg_frequencies
    python -m scripts.load_1kg_frequencies --vcf-path /path/to/cached/sites.vcf.gz
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import logging
import math
import os
import time

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

SITES_VCF_URL = (
    "https://ftp.1000genomes.ebi.ac.uk/vol1/ftp/release/20130502/"
    "ALL.wgs.phase3_shapeit2_mvncall_integrated_v5c.20130502.sites.vcf.gz"
)

CACHE_DIR = os.path.expanduser("~/.cache/genewizard")
CACHE_FILE = os.path.join(CACHE_DIR, "1000g_sites.vcf.gz")

SUPERPOP_AF_KEYS = ["EUR_AF", "AFR_AF", "EAS_AF", "SAS_AF", "AMR_AF"]
DB_COLUMNS = ["eur_af", "afr_af", "eas_af", "sas_af", "amr_af"]


async def download_vcf(target_path: str) -> None:
    """Download the 1000 Genomes sites VCF with progress."""
    os.makedirs(os.path.dirname(target_path), exist_ok=True)
    tmp_path = target_path + ".tmp"

    log.info(f"Downloading 1000 Genomes sites VCF to {target_path}...")
    log.info(f"  URL: {SITES_VCF_URL}")

    async with httpx.AsyncClient(follow_redirects=True, timeout=None) as client:
        async with client.stream("GET", SITES_VCF_URL) as resp:
            resp.raise_for_status()
            total = int(resp.headers.get("content-length", 0))
            downloaded = 0
            last_pct = -1

            with open(tmp_path, "wb") as f:
                async for chunk in resp.aiter_bytes(65536):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0:
                        pct = downloaded * 100 // total
                        if pct != last_pct and pct % 5 == 0:
                            last_pct = pct
                            log.info(f"  {pct}% ({downloaded / 1024 / 1024:.0f}/{total / 1024 / 1024:.0f} MB)")

    os.rename(tmp_path, target_path)
    log.info(f"  Download complete: {downloaded / 1024 / 1024:.0f} MB")


def parse_info_field(info: str, keys: list[str]) -> dict[str, float | None]:
    """Extract specific fields from a VCF INFO string."""
    result = {k: None for k in keys}
    for field in info.split(";"):
        if "=" not in field:
            continue
        k, v = field.split("=", 1)
        if k in result:
            try:
                # Some fields have multiple values (comma-separated for multiallelic)
                # We take the first value
                result[k] = float(v.split(",")[0])
            except ValueError:
                pass
    return result


def stream_parse_frequencies(
    vcf_path: str, target_positions: set[str]
) -> dict[str, dict[str, float | None | str]]:
    """Stream-parse the 1000G sites VCF and extract AFs + alleles by chr:pos.

    The 1000G whole-genome sites VCF uses '.' for variant IDs, so we match
    by chromosome:position instead of rsID.

    Args:
        target_positions: Set of "chrom:pos" strings (e.g., "1:55496039")

    Returns dict of "chrom:pos" → {EUR_AF: float, ..., "vcf_ref": str, "vcf_alt": str}
    """
    log.info(f"Parsing VCF for {len(target_positions):,} target positions...")
    t0 = time.perf_counter()

    # Use isal for faster gzip decompression if available
    try:
        from isal import igzip
        opener = igzip.open
        log.info("  Using isal for accelerated gzip decompression")
    except ImportError:
        opener = gzip.open

    result = {}
    n_lines = 0
    n_matched = 0

    with opener(vcf_path, "rt") as f:
        for line in f:
            if line.startswith("#"):
                continue
            n_lines += 1

            if n_lines % 5_000_000 == 0:
                log.info(f"  Processed {n_lines / 1_000_000:.0f}M lines, matched {n_matched:,} variants...")

            # VCF columns: CHROM POS ID REF ALT QUAL FILTER INFO
            parts = line.split("\t", 8)
            if len(parts) < 8:
                continue

            chrom = parts[0]
            pos = parts[1]
            key = f"{chrom}:{pos}"

            if key not in target_positions:
                continue

            vcf_ref = parts[3].strip()
            vcf_alt = parts[4].strip().split(",")[0]  # First ALT for multiallelic
            info = parts[7]
            freqs = parse_info_field(info, SUPERPOP_AF_KEYS)

            # Store alleles alongside frequencies for effect-allele alignment
            freqs["vcf_ref"] = vcf_ref
            freqs["vcf_alt"] = vcf_alt

            result[key] = freqs
            n_matched += 1

            # Early exit if we found all targets
            if n_matched == len(target_positions):
                break

    elapsed = time.perf_counter() - t0
    log.info(f"  Done: matched {n_matched:,}/{len(target_positions):,} variants in {elapsed:.0f}s ({n_lines / 1_000_000:.0f}M lines)")
    return result


async def update_weights(
    session: AsyncSession,
    freq_data: dict[str, dict[str, float | None | str]],
    pos_to_variants: dict[str, list[dict]],
    pgs_ids: list[str],
) -> None:
    """Batch-update prs_variant_weights with effect-allele-aligned frequencies.

    Processes one PGS ID at a time to limit peak memory usage. For each variant,
    compares the PRS effect_allele with the 1000G VCF REF/ALT:
    - effect_allele == VCF ALT → store AF as-is (AF is already for effect allele)
    - effect_allele == VCF REF → store 1-AF (flip to get effect allele frequency)
    - neither matches → store NULL (allele mismatch, can't use)
    """
    log.info(f"Updating allele frequencies in database (effect-allele aligned)...")
    t0 = time.perf_counter()
    total_updated = 0

    # Build per-PGS index: pgs_id → set of (rsid, chrom, position, effect_allele)
    # from pos_to_variants which has [{rsid, effect_allele, pgs_id}, ...]
    pgs_variants: dict[str, list[dict]] = {pid: [] for pid in pgs_ids}
    for chrpos, variants in pos_to_variants.items():
        for var in variants:
            pid = var.get("pgs_id")
            if pid and pid in pgs_variants:
                pgs_variants[pid].append({**var, "chrpos": chrpos})

    # Create temp table once
    await session.execute(text("""
        CREATE TEMP TABLE IF NOT EXISTS _af_updates (
            rsid TEXT, chrom TEXT, position INTEGER, effect_is_alt BOOLEAN,
            eur_af DOUBLE PRECISION, afr_af DOUBLE PRECISION,
            eas_af DOUBLE PRECISION, sas_af DOUBLE PRECISION, amr_af DOUBLE PRECISION
        )
    """))

    for pgs_id in pgs_ids:
        variants = pgs_variants.get(pgs_id, [])
        if not variants:
            continue

        updates = []
        n_aligned = 0
        n_flipped = 0
        n_mismatch = 0

        for var in variants:
            chrpos = var["chrpos"]
            freqs = freq_data.get(chrpos)
            if freqs is None:
                continue

            vcf_ref = freqs.get("vcf_ref", "")
            vcf_alt = freqs.get("vcf_alt", "")
            effect_allele = var["effect_allele"]

            if effect_allele == vcf_alt:
                flip = False
                n_aligned += 1
            elif effect_allele == vcf_ref:
                flip = True
                n_flipped += 1
            else:
                n_mismatch += 1
                continue

            aligned_freqs = {}
            for vcf_key, db_col in zip(SUPERPOP_AF_KEYS, DB_COLUMNS):
                af = freqs.get(vcf_key)
                if af is not None:
                    aligned_freqs[db_col] = (1.0 - af) if flip else af
                else:
                    aligned_freqs[db_col] = None

            updates.append({
                "rsid": var["rsid"],
                "chrom": chrpos.split(":")[0],
                "position": int(chrpos.split(":")[1]),
                "effect_is_alt": not flip,
                **aligned_freqs,
            })

        log.info(
            f"  {pgs_id}: {n_aligned:,} direct, {n_flipped:,} flipped, "
            f"{n_mismatch:,} mismatched → {len(updates):,} updates"
        )

        if not updates:
            continue

        # Load into temp table in batches
        await session.execute(text("TRUNCATE _af_updates"))
        BATCH = 3600
        for i in range(0, len(updates), BATCH):
            batch = updates[i : i + BATCH]
            values_parts = []
            params = {}
            for j, row in enumerate(batch):
                key = f"_{j}"
                values_parts.append(
                    f"(:rsid{key}, :chrom{key}, :pos{key}, :alt{key}, :eur{key}, :afr{key}, :eas{key}, :sas{key}, :amr{key})"
                )
                params[f"rsid{key}"] = row["rsid"]
                params[f"chrom{key}"] = row["chrom"]
                params[f"pos{key}"] = row["position"]
                params[f"alt{key}"] = row["effect_is_alt"]
                params[f"eur{key}"] = row["eur_af"]
                params[f"afr{key}"] = row["afr_af"]
                params[f"eas{key}"] = row["eas_af"]
                params[f"sas{key}"] = row["sas_af"]
                params[f"amr{key}"] = row["amr_af"]
            await session.execute(
                text(f"INSERT INTO _af_updates VALUES {', '.join(values_parts)}"),
                params,
            )

        # Bulk UPDATE from temp table for this PGS ID
        result = await session.execute(
            text("""
                UPDATE prs_variant_weights w
                SET eur_af = u.eur_af, afr_af = u.afr_af, eas_af = u.eas_af,
                    sas_af = u.sas_af, amr_af = u.amr_af,
                    effect_is_alt = u.effect_is_alt
                FROM _af_updates u
                WHERE w.rsid = u.rsid AND w.chrom = u.chrom AND w.position = u.position
                  AND w.pgs_id = :pgs_id
            """),
            {"pgs_id": pgs_id},
        )
        await session.commit()
        total_updated += result.rowcount
        log.info(f"  {pgs_id}: committed {result.rowcount:,} rows")

        # Free memory for this PGS ID
        del updates

    await session.execute(text("DROP TABLE IF EXISTS _af_updates"))
    await session.commit()

    elapsed = time.perf_counter() - t0
    log.info(f"  Total: updated {total_updated:,} variants in {elapsed:.0f}s")


async def recompute_ref_dists(session: AsyncSession, pgs_ids: list[str]) -> None:
    """Recompute reference distributions from per-variant allele frequencies.

    AFs are already aligned to effect allele, so the formula
    E[S] = Σ 2·p·w gives the correct expected PRS score.
    """
    for pgs_id in pgs_ids:
        rows = await session.execute(
            text("""
                SELECT weight, eur_af, afr_af, eas_af, sas_af, amr_af
                FROM prs_variant_weights
                WHERE pgs_id = :pgs_id
            """),
            {"pgs_id": pgs_id},
        )
        weights = rows.fetchall()

        n_total = len(weights)
        if n_total > 5000:
            log.warning(
                f"\n{pgs_id}: {n_total:,} variants — genome-wide PGS detected."
                f" The analytical formula Var[S] = Σ 2·p·(1-p)·w² assumes independence"
                f" between variants, which underestimates the true std when variants are"
                f" in LD. Consider running: python -m scripts.compute_empirical_ref_dists"
                f" --pgs-id {pgs_id}"
            )
        log.info(f"\n{pgs_id}: Recomputing reference distributions ({n_total:,} variants)...")

        await session.execute(
            text("DELETE FROM prs_reference_distributions WHERE pgs_id = :pgs_id"),
            {"pgs_id": pgs_id},
        )

        for pop, af_col in zip(
            ["EUR", "AFR", "EAS", "SAS", "AMR"],
            ["eur_af", "afr_af", "eas_af", "sas_af", "amr_af"],
        ):
            total_mean = 0.0
            total_var = 0.0
            n_with_af = 0

            for w in weights:
                af = getattr(w, af_col)
                if af is None:
                    continue
                weight = w.weight
                n_with_af += 1
                total_mean += 2 * af * weight
                total_var += 2 * af * (1 - af) * weight ** 2

            std = math.sqrt(total_var) if total_var > 0 else 0.0
            coverage = n_with_af / n_total * 100 if n_total > 0 else 0

            log.info(f"  {pop}: mean={total_mean:.6f}, std={std:.6f} ({n_with_af:,}/{n_total:,} = {coverage:.0f}%)")

            if n_with_af > 0:
                await session.execute(
                    text("""
                        INSERT INTO prs_reference_distributions (pgs_id, ancestry_group, mean, std)
                        VALUES (:pgs_id, :pop, :mean, :std)
                    """),
                    {"pgs_id": pgs_id, "pop": pop, "mean": total_mean, "std": std},
                )

        await session.commit()


async def update_flags_only(
    session: AsyncSession,
    freq_data: dict[str, dict[str, float | None | str]],
    pos_to_variants: dict[str, list[dict]],
    pgs_ids: list[str],
) -> None:
    """Update only the effect_is_alt flag (not AFs) for rows that already have AF data."""
    log.info("Updating effect_is_alt flags only (AFs already loaded)...")
    t0 = time.perf_counter()

    updates = []
    n_aligned = 0
    n_flipped = 0
    n_mismatch = 0

    for chrpos, freqs in freq_data.items():
        vcf_ref = freqs.get("vcf_ref", "")
        vcf_alt = freqs.get("vcf_alt", "")
        variants = pos_to_variants.get(chrpos, [])

        for var in variants:
            effect_allele = var["effect_allele"]
            if effect_allele == vcf_alt:
                effect_is_alt = True
                n_aligned += 1
            elif effect_allele == vcf_ref:
                effect_is_alt = False
                n_flipped += 1
            else:
                n_mismatch += 1
                continue

            updates.append({
                "rsid": var["rsid"],
                "chrom": chrpos.split(":")[0],
                "position": int(chrpos.split(":")[1]),
                "effect_is_alt": effect_is_alt,
            })

    log.info(
        f"  Allele alignment: {n_aligned:,} ALT, {n_flipped:,} REF, "
        f"{n_mismatch:,} mismatched"
    )

    # Use temp table + bulk UPDATE
    await session.execute(text("""
        CREATE TEMP TABLE IF NOT EXISTS _flag_updates (
            rsid TEXT, chrom TEXT, position INTEGER, effect_is_alt BOOLEAN
        )
    """))
    await session.execute(text("TRUNCATE _flag_updates"))

    # 4 params per row → batch up to 8000
    BATCH = 8000
    for i in range(0, len(updates), BATCH):
        batch = updates[i : i + BATCH]
        values_parts = []
        params = {}
        for j, row in enumerate(batch):
            key = f"_{i+j}"
            values_parts.append(f"(:rsid{key}, :chrom{key}, :pos{key}, :alt{key})")
            params[f"rsid{key}"] = row["rsid"]
            params[f"chrom{key}"] = row["chrom"]
            params[f"pos{key}"] = row["position"]
            params[f"alt{key}"] = row["effect_is_alt"]
        await session.execute(
            text(f"INSERT INTO _flag_updates VALUES {', '.join(values_parts)}"),
            params,
        )
        if (i + BATCH) % 500_000 == 0:
            log.info(f"  Loaded {i + len(batch):,}/{len(updates):,} into temp table...")

    await session.commit()
    log.info(f"  Loaded {len(updates):,} rows into temp table")

    for pgs_id in pgs_ids:
        result = await session.execute(
            text("""
                UPDATE prs_variant_weights w
                SET effect_is_alt = u.effect_is_alt
                FROM _flag_updates u
                WHERE w.rsid = u.rsid AND w.chrom = u.chrom AND w.position = u.position
                  AND w.pgs_id = :pgs_id
            """),
            {"pgs_id": pgs_id},
        )
        log.info(f"  {pgs_id}: updated {result.rowcount:,} rows")

    await session.commit()
    await session.execute(text("DROP TABLE IF EXISTS _flag_updates"))
    await session.commit()

    elapsed = time.perf_counter() - t0
    log.info(f"  Updated {len(updates):,} flags in {elapsed:.0f}s")


async def main(vcf_path: str | None, skip_download: bool, flags_only: bool = False) -> None:
    path = vcf_path or CACHE_FILE

    if not os.path.exists(path):
        if skip_download:
            log.error(f"VCF file not found at {path} and --skip-download specified")
            return
        await download_vcf(path)
    else:
        log.info(f"Using cached VCF: {path} ({os.path.getsize(path) / 1024 / 1024:.0f} MB)")

    # Connect to database and get target positions
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        if flags_only:
            # Only update effect_is_alt for rows that have AFs but missing flag
            result = await session.execute(text("""
                SELECT pgs_id, COUNT(*) as total,
                       COUNT(effect_is_alt) as with_flag
                FROM prs_variant_weights
                WHERE eur_af IS NOT NULL
                GROUP BY pgs_id
                HAVING COUNT(effect_is_alt) < COUNT(*)
            """))
            pgs_to_update = [(r.pgs_id, r.total, r.with_flag) for r in result.fetchall()]

            if not pgs_to_update:
                log.info("All variants with AFs already have effect_is_alt flag")
                await engine.dispose()
                return

            for pgs_id, total, with_flag in pgs_to_update:
                log.info(f"{pgs_id}: {total:,} variants with AF, {with_flag:,} already have flag")

            target_positions = set()
            pos_to_variants: dict[str, list[dict]] = {}
            pgs_ids = []
            for pgs_id, total, _ in pgs_to_update:
                pgs_ids.append(pgs_id)
                result = await session.execute(
                    text("""
                        SELECT rsid, chrom, position, effect_allele
                        FROM prs_variant_weights
                        WHERE pgs_id = :pid AND eur_af IS NOT NULL AND effect_is_alt IS NULL
                    """),
                    {"pid": pgs_id},
                )
                for r in result.fetchall():
                    key = f"{r.chrom}:{r.position}"
                    target_positions.add(key)
                    pos_to_variants.setdefault(key, []).append({
                        "rsid": r.rsid,
                        "effect_allele": r.effect_allele,
                    })

            log.info(f"\nTotal unique positions to look up: {len(target_positions):,}")
            freq_data = await asyncio.to_thread(stream_parse_frequencies, path, target_positions)
            await update_flags_only(session, freq_data, pos_to_variants, pgs_ids)

        else:
            # Full AF loading mode
            # Find PGS IDs that need AF data (any score with missing AFs)
            result = await session.execute(text("""
                SELECT pgs_id, COUNT(*) as total,
                       COUNT(eur_af) as with_af
                FROM prs_variant_weights
                GROUP BY pgs_id
                HAVING COUNT(eur_af) < COUNT(*) * 0.95
            """))
            pgs_to_update = [(r.pgs_id, r.total, r.with_af) for r in result.fetchall()]

            if not pgs_to_update:
                log.info("All PGS scores already have allele frequency data")
                # Even if AFs are complete, check for missing effect_is_alt flags
                result2 = await session.execute(text("""
                    SELECT pgs_id, COUNT(*) as total,
                           COUNT(effect_is_alt) as with_flag
                    FROM prs_variant_weights
                    WHERE eur_af IS NOT NULL
                    GROUP BY pgs_id
                    HAVING COUNT(effect_is_alt) < COUNT(*)
                """))
                missing_flags = [(r.pgs_id, r.total, r.with_flag) for r in result2.fetchall()]
                if not missing_flags:
                    await engine.dispose()
                    return
                log.info(
                    f"{len(missing_flags)} PGS score(s) have AFs but missing "
                    f"effect_is_alt flags — switching to flag-update mode"
                )
                for pgs_id, total, with_flag in missing_flags:
                    log.info(f"  {pgs_id}: {total:,} variants, {with_flag:,} have flag")
                # Fall through to flag-only logic below
                target_positions = set()
                pos_to_variants: dict[str, list[dict]] = {}
                pgs_ids = []
                for pgs_id, total, _ in missing_flags:
                    pgs_ids.append(pgs_id)
                    r3 = await session.execute(
                        text("""
                            SELECT rsid, chrom, position, effect_allele
                            FROM prs_variant_weights
                            WHERE pgs_id = :pid AND eur_af IS NOT NULL AND effect_is_alt IS NULL
                        """),
                        {"pid": pgs_id},
                    )
                    for r in r3.fetchall():
                        key = f"{r.chrom}:{r.position}"
                        target_positions.add(key)
                        pos_to_variants.setdefault(key, []).append({
                            "rsid": r.rsid,
                            "effect_allele": r.effect_allele,
                        })
                log.info(f"\nTotal unique positions to look up: {len(target_positions):,}")
                freq_data = await asyncio.to_thread(stream_parse_frequencies, path, target_positions)
                await update_flags_only(session, freq_data, pos_to_variants, pgs_ids)
                await engine.dispose()
                return

            for pgs_id, total, with_af in pgs_to_update:
                log.info(f"{pgs_id}: {total:,} variants, {with_af:,} already have AF data")

            # Collect all target positions and their effect alleles for alignment
            # NOTE: positions in prs_variant_weights are GRCh37 (matching the 1000G VCF)
            target_positions = set()
            pos_to_variants: dict[str, list[dict]] = {}
            pgs_ids = []
            for pgs_id, total, _ in pgs_to_update:
                pgs_ids.append(pgs_id)
                result = await session.execute(
                    text("""
                        SELECT rsid, chrom, position, effect_allele
                        FROM prs_variant_weights
                        WHERE pgs_id = :pid AND eur_af IS NULL
                    """),
                    {"pid": pgs_id},
                )
                for r in result.fetchall():
                    key = f"{r.chrom}:{r.position}"
                    target_positions.add(key)
                    pos_to_variants.setdefault(key, []).append({
                        "rsid": r.rsid,
                        "effect_allele": r.effect_allele,
                        "pgs_id": pgs_id,
                    })

            log.info(f"\nTotal unique positions to look up: {len(target_positions):,}")

            # Parse VCF (CPU-heavy, runs in main thread but that's fine for a script)
            freq_data = await asyncio.to_thread(stream_parse_frequencies, path, target_positions)

            # Update database with effect-allele-aligned frequencies
            await update_weights(session, freq_data, pos_to_variants, pgs_ids)

            # Recompute reference distributions
            await recompute_ref_dists(session, pgs_ids)

    await engine.dispose()
    log.info("\nDone!")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Load 1000 Genomes allele frequencies")
    parser.add_argument("--vcf-path", type=str, help="Path to pre-downloaded sites VCF")
    parser.add_argument("--skip-download", action="store_true", help="Don't download if missing")
    parser.add_argument("--update-flags", action="store_true",
                        help="Only update effect_is_alt flag (skip AF loading)")
    args = parser.parse_args()

    asyncio.run(main(args.vcf_path, args.skip_download, flags_only=args.update_flags))
