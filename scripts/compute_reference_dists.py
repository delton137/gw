"""Compute PRS reference distributions for percentile normalization.

Fetches per-ancestry allele frequencies from Ensembl (1000 Genomes Phase 3)
and computes analytical mean/std for each PGS score per superpopulation.

Uses the formula (under Hardy-Weinberg equilibrium):
  E[S] = Σ 2 * p_i * w_i
  Var[S] = Σ 2 * p_i * (1 - p_i) * w_i²
  std[S] = sqrt(Var[S])

where p_i is the effect allele frequency and w_i is the PRS weight.

Usage:
    python -m scripts.compute_reference_dists
    python -m scripts.compute_reference_dists --pgs-id PGS000001
    python -m scripts.compute_reference_dists --max-variants 5000  # skip genome-wide PRS
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
import math
import time

import httpx
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.base import Base
from app.models.prs import PrsReferenceDistribution, PrsScore

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

ENSEMBL_API = "https://rest.ensembl.org"

# 1000 Genomes Phase 3 superpopulations → our ancestry groups
SUPERPOPS = ["EUR", "AFR", "EAS", "SAS", "AMR"]


async def fetch_allele_frequencies(
    client: httpx.AsyncClient, rsids: list[str]
) -> dict[str, dict[str, float]]:
    """Fetch per-superpopulation allele frequencies from Ensembl.

    Args:
        client: httpx async client
        rsids: List of rsIDs to query

    Returns:
        Dict mapping rsid → {allele → {pop → frequency}}
        e.g. {"rs123": {"A": {"EUR": 0.3, "AFR": 0.5, ...}, "G": {...}}}
    """
    result: dict[str, dict[str, dict[str, float]]] = {}

    # Ensembl POST endpoint supports max 200 IDs per request
    batch_size = 200
    for i in range(0, len(rsids), batch_size):
        batch = rsids[i : i + batch_size]
        batch_num = i // batch_size + 1
        total_batches = math.ceil(len(rsids) / batch_size)

        if total_batches > 1:
            log.info(f"  Fetching frequencies batch {batch_num}/{total_batches} ({len(batch)} variants)...")

        resp = None
        for attempt in range(3):
            try:
                resp = await client.post(
                    f"{ENSEMBL_API}/variation/homo_sapiens?pops=1",
                    json={"ids": batch},
                    headers={"Content-Type": "application/json"},
                    timeout=60,
                )
                if resp.status_code == 429:
                    retry_after = float(resp.headers.get("Retry-After", "2"))
                    log.warning(f"  Rate limited, waiting {retry_after}s...")
                    await asyncio.sleep(retry_after)
                    continue
                resp.raise_for_status()
                break
            except (httpx.HTTPStatusError, httpx.ReadTimeout) as e:
                if attempt == 2:
                    log.error(f"  Failed to fetch batch {batch_num}: {e}")
                await asyncio.sleep(2 ** attempt)

        if resp is None or resp.status_code != 200:
            continue

        data = resp.json()

        for rsid, info in data.items():
            if not isinstance(info, dict):
                continue
            pops = info.get("populations", [])
            allele_freqs: dict[str, dict[str, float]] = {}

            for p in pops:
                pop_name = p.get("population", "")
                if not pop_name.startswith("1000GENOMES:phase_3:"):
                    continue
                superpop = pop_name.split(":")[-1]
                if superpop not in SUPERPOPS:
                    continue

                allele = p.get("allele", "")
                freq = p.get("frequency", 0.0)
                if allele not in allele_freqs:
                    allele_freqs[allele] = {}
                allele_freqs[allele][superpop] = freq

            if allele_freqs:
                result[rsid] = allele_freqs

        # Be nice to Ensembl API
        if total_batches > 1:
            await asyncio.sleep(0.5)

    return result


def compute_analytical_distribution(
    weights: list[tuple[str, str, float]],
    freq_data: dict[str, dict[str, dict[str, float]]],
    pop: str,
) -> tuple[float, float, int]:
    """Compute analytical mean and std for a PRS in a given population.

    Args:
        weights: List of (rsid, effect_allele, weight) tuples
        freq_data: Allele frequency data from Ensembl
        pop: Superpopulation code (EUR, AFR, etc.)

    Returns:
        (mean, std, n_variants_with_freq)
    """
    total_mean = 0.0
    total_var = 0.0
    n_with_freq = 0

    for rsid, effect_allele, weight in weights:
        if rsid not in freq_data:
            continue
        allele_freqs = freq_data[rsid]
        if effect_allele not in allele_freqs:
            continue
        if pop not in allele_freqs[effect_allele]:
            continue

        p = allele_freqs[effect_allele][pop]
        n_with_freq += 1

        # Under HWE: E[dosage] = 2p, Var[dosage] = 2p(1-p)
        total_mean += 2 * p * weight
        total_var += 2 * p * (1 - p) * weight ** 2

    std = math.sqrt(total_var) if total_var > 0 else 0.0
    return total_mean, std, n_with_freq


async def compute_for_pgs(
    pgs_id: str,
    session: AsyncSession,
    client: httpx.AsyncClient,
    max_variants: int | None = None,
) -> None:
    """Compute reference distributions for a single PGS score."""
    t0 = time.perf_counter()

    # Load variant weights
    result = await session.execute(
        text("SELECT rsid, effect_allele, weight FROM prs_variant_weights WHERE pgs_id = :pgs_id"),
        {"pgs_id": pgs_id},
    )
    rows = result.fetchall()
    if not rows:
        log.warning(f"{pgs_id}: No variant weights found, skipping")
        return

    n_variants = len(rows)
    if max_variants and n_variants > max_variants:
        log.info(f"{pgs_id}: {n_variants} variants exceeds --max-variants {max_variants}, skipping")
        log.info(f"  (use --max-variants 0 or download 1000G data for genome-wide PRS)")
        return

    log.info(f"{pgs_id}: Computing reference distributions for {n_variants} variants...")

    weights = [(r.rsid, r.effect_allele, r.weight) for r in rows]
    rsids = [r.rsid for r in rows]

    # Fetch allele frequencies from Ensembl
    log.info(f"  Fetching allele frequencies from Ensembl ({len(rsids)} variants)...")
    freq_data = await fetch_allele_frequencies(client, rsids)
    log.info(f"  Got frequency data for {len(freq_data)}/{len(rsids)} variants")

    if not freq_data:
        log.error(f"  No frequency data available, cannot compute reference distribution")
        return

    # Store per-variant allele frequencies in prs_variant_weights
    log.info(f"  Storing per-variant allele frequencies...")
    af_updates = 0
    for rsid, effect_allele, weight in weights:
        if rsid not in freq_data:
            continue
        allele_freqs = freq_data[rsid]
        if effect_allele not in allele_freqs:
            continue

        pop_freqs = allele_freqs[effect_allele]
        await session.execute(
            text("""
                UPDATE prs_variant_weights
                SET eur_af = :eur, afr_af = :afr, eas_af = :eas, sas_af = :sas, amr_af = :amr
                WHERE pgs_id = :pgs_id AND rsid = :rsid
            """),
            {
                "pgs_id": pgs_id,
                "rsid": rsid,
                "eur": pop_freqs.get("EUR"),
                "afr": pop_freqs.get("AFR"),
                "eas": pop_freqs.get("EAS"),
                "sas": pop_freqs.get("SAS"),
                "amr": pop_freqs.get("AMR"),
            },
        )
        af_updates += 1

    await session.commit()
    log.info(f"  Updated allele frequencies for {af_updates}/{n_variants} variants")

    # Delete existing reference distributions for this PGS
    await session.execute(
        text("DELETE FROM prs_reference_distributions WHERE pgs_id = :pgs_id"),
        {"pgs_id": pgs_id},
    )

    # Compute per-superpopulation distributions
    for pop in SUPERPOPS:
        mean, std, n_with_freq = compute_analytical_distribution(weights, freq_data, pop)

        if n_with_freq == 0:
            log.warning(f"  {pop}: No frequency data, skipping")
            continue

        coverage = n_with_freq / n_variants * 100
        log.info(f"  {pop}: mean={mean:.6f}, std={std:.6f} ({n_with_freq}/{n_variants} variants = {coverage:.0f}%)")

        session.add(PrsReferenceDistribution(
            pgs_id=pgs_id,
            ancestry_group=pop,
            mean=mean,
            std=std,
            percentiles_json=None,
        ))

    await session.commit()
    elapsed = time.perf_counter() - t0
    log.info(f"  Done in {elapsed:.1f}s")


async def main(pgs_ids: list[str] | None, max_variants: int | None) -> None:
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        if pgs_ids:
            ids_to_process = pgs_ids
        else:
            result = await session.execute(select(PrsScore.pgs_id))
            ids_to_process = [r[0] for r in result.fetchall()]

        if not ids_to_process:
            log.warning("No PGS scores found in database")
            return

        log.info(f"Computing reference distributions for {len(ids_to_process)} PGS scores")

        async with httpx.AsyncClient() as client:
            for pgs_id in ids_to_process:
                try:
                    await compute_for_pgs(pgs_id, session, client, max_variants)
                except Exception as e:
                    log.error(f"{pgs_id}: Failed: {e}")
                    await session.rollback()

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Compute PRS reference distributions")
    parser.add_argument("--pgs-id", type=str, help="Single PGS ID to compute")
    parser.add_argument(
        "--max-variants",
        type=int,
        default=5000,
        help="Skip PGS with more variants than this (default: 5000). Use 0 for no limit.",
    )
    args = parser.parse_args()

    pgs_ids = [args.pgs_id] if args.pgs_id else None
    max_var = args.max_variants if args.max_variants > 0 else None

    asyncio.run(main(pgs_ids, max_var))
