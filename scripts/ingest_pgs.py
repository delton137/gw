"""PGS Catalog ingest script.

Fetches score metadata and harmonized weight files from the PGS Catalog,
then loads them into the database. Downloads BOTH GRCh37 and GRCh38
harmonized files to store positions for both genome builds.

Usage:
    python -m scripts.ingest_pgs --pgs-id PGS000001
    python -m scripts.ingest_pgs --top-scores 8
    python -m scripts.ingest_pgs --top-scores 8 --force   # delete + reimport
"""

from __future__ import annotations

import argparse
import asyncio
import gzip
import logging
import re
from datetime import datetime, timezone

import httpx
from sqlalchemy import select, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.base import Base
from app.models.prs import PrsScore, PrsVariantWeight
from app.models.snp import Snp

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

PGS_API = "https://www.pgscatalog.org/rest/score"
PGS_PERF_API = "https://www.pgscatalog.org/rest/performance/search"

# Harmonized scoring files URL patterns
SCORING_FILE_URL_37 = (
    "https://ftp.ebi.ac.uk/pub/databases/spot/pgs/scores/{pgs_id}/ScoringFiles/Harmonized/"
    "{pgs_id}_hmPOS_GRCh37.txt.gz"
)
SCORING_FILE_URL_38 = (
    "https://ftp.ebi.ac.uk/pub/databases/spot/pgs/scores/{pgs_id}/ScoringFiles/Harmonized/"
    "{pgs_id}_hmPOS_GRCh38.txt.gz"
)

PRIORITY_SCORES = [
    "PGS000001",  # CAD
    "PGS000002",  # Breast cancer
    "PGS000003",  # T2D
    "PGS000004",  # Prostate cancer
    "PGS000018",  # Atrial fibrillation
    "PGS000039",  # Alzheimer's
]

# Column name normalization map
COLUMN_MAP = {
    "rsID": "rsid",
    "rsid": "rsid",
    "hm_rsID": "rsid",
    "variant_id": "rsid",
    "hm_chr": "chrom",
    "chr_name": "chrom",
    "hm_pos": "position",
    "chr_position": "position",
    "effect_allele": "effect_allele",
    "effect_weight": "weight",
    "other_allele": "other_allele",
    "reference_allele": "other_allele",
}

# Regex to strip "chr" prefix from chromosome names
_CHR_PREFIX = re.compile(r"^chr", re.IGNORECASE)


def _normalize_chrom(chrom: str) -> str:
    """Normalize chromosome name: strip 'chr' prefix, uppercase."""
    return _CHR_PREFIX.sub("", chrom.strip())


async def fetch_score_metadata(client: httpx.AsyncClient, pgs_id: str) -> dict:
    """Fetch score metadata from PGS Catalog REST API."""
    resp = await client.get(f"{PGS_API}/{pgs_id}")
    resp.raise_for_status()
    return resp.json()


async def fetch_best_auc(client: httpx.AsyncClient, pgs_id: str) -> float | None:
    """Fetch the best AUC/AUROC/C-index from PGS Catalog performance endpoint.

    Prefers European-ancestry results; falls back to largest sample size.
    Returns None if no classification accuracy metrics are found.
    """
    try:
        resp = await client.get(f"{PGS_PERF_API}", params={"pgs_id": pgs_id})
        resp.raise_for_status()
        data = resp.json()
    except Exception as e:
        log.warning(f"  Could not fetch performance metrics for {pgs_id}: {e}")
        return None

    candidates: list[tuple[float, int, bool]] = []  # (auc, sample_size, is_european)
    for entry in data.get("results", []):
        metrics = entry.get("performance_metrics", {})
        class_acc = metrics.get("class_acc", [])
        for metric in class_acc:
            name = metric.get("name_short", "")
            if name not in ("AUROC", "C-index"):
                continue
            estimate = metric.get("estimate")
            if estimate is None:
                continue

            # Determine ancestry and sample size
            samples = entry.get("sampleset", {}).get("samples", [])
            sample_n = sum(s.get("sample_number", 0) for s in samples)
            is_eur = any("european" in (s.get("ancestry_broad", "") or "").lower() for s in samples)
            candidates.append((estimate, sample_n, is_eur))

    if not candidates:
        return None

    # Prefer European, then largest sample
    candidates.sort(key=lambda x: (x[2], x[1]), reverse=True)
    best_auc = candidates[0][0]
    log.info(f"  Best AUC for {pgs_id}: {best_auc:.3f}")
    return best_auc


async def download_scoring_file(
    client: httpx.AsyncClient, pgs_id: str, url_template: str
) -> str | None:
    """Download and decompress a single harmonized scoring file. Returns None on failure."""
    url = url_template.format(pgs_id=pgs_id)
    try:
        resp = await client.get(url, follow_redirects=True)
        resp.raise_for_status()
        content = gzip.decompress(resp.content).decode("utf-8")
        log.info(f"  Downloaded {url.split('/')[-1]}")
        return content
    except (httpx.HTTPStatusError, gzip.BadGzipFile) as e:
        log.warning(f"  Could not download {url.split('/')[-1]}: {e}")
        return None


def parse_scoring_file(content: str) -> list[dict]:
    """Parse a PGS Catalog harmonized scoring TSV file into normalized rows."""
    lines = content.splitlines()

    # Skip comment/header lines starting with #
    data_lines = []
    header = None
    for line in lines:
        if line.startswith("#"):
            continue
        if header is None:
            header = line.strip().split("\t")
            continue
        data_lines.append(line.strip().split("\t"))

    if not header:
        raise ValueError("No header found in scoring file")

    # Normalize column names
    col_indices: dict[str, int] = {}
    for i, col in enumerate(header):
        normalized = COLUMN_MAP.get(col)
        if normalized:
            col_indices[normalized] = i

    required = {"rsid", "effect_allele", "weight"}
    missing = required - col_indices.keys()
    if missing:
        raise ValueError(f"Missing required columns: {missing}. Available: {header}")

    rows = []
    for parts in data_lines:
        if len(parts) <= max(col_indices.values()):
            continue

        rsid = parts[col_indices["rsid"]].strip()
        if not rsid.startswith("rs"):
            continue

        effect_allele = parts[col_indices["effect_allele"]].strip()
        weight_str = parts[col_indices["weight"]].strip()

        try:
            weight = float(weight_str)
        except ValueError:
            continue

        # Position and chrom may be missing in some files
        chrom = _normalize_chrom(parts[col_indices["chrom"]]) if "chrom" in col_indices else ""
        pos_str = parts[col_indices["position"]].strip() if "position" in col_indices else "0"
        try:
            position = int(pos_str)
        except ValueError:
            position = 0

        other_allele = ""
        if "other_allele" in col_indices:
            other_allele = parts[col_indices["other_allele"]].strip()

        rows.append({
            "rsid": rsid,
            "chrom": chrom,
            "position": position,
            "effect_allele": effect_allele,
            "other_allele": other_allele,
            "weight": weight,
        })

    return rows


def merge_builds(
    rows_37: list[dict] | None, rows_38: list[dict] | None
) -> list[dict]:
    """Merge GRCh37 and GRCh38 parsed rows into a single list with both positions.

    Uses rsid + effect_allele + weight as the join key between builds.
    The merged rows have 'position' (GRCh37) and 'position_grch38' fields.
    """
    if rows_37 and rows_38:
        # Build a lookup from the GRCh38 rows: (rsid, effect_allele) → grch38_position
        # We use rsid only since the same rsid should have the same effect_allele and weight
        pos38_lookup: dict[str, int] = {}
        for r in rows_38:
            pos38_lookup[r["rsid"]] = r["position"]

        merged = []
        for r in rows_37:
            r["position_grch38"] = pos38_lookup.get(r["rsid"], 0)
            merged.append(r)

        n_with_38 = sum(1 for r in merged if r["position_grch38"] > 0)
        log.info(f"  Merged: {len(merged)} variants, {n_with_38} have GRCh38 positions")
        return merged

    elif rows_37:
        # Only GRCh37 available
        for r in rows_37:
            r["position_grch38"] = 0
        log.info(f"  GRCh37 only: {len(rows_37)} variants (no GRCh38 positions)")
        return rows_37

    elif rows_38:
        # Only GRCh38 available — store GRCh38 as the primary position too
        for r in rows_38:
            r["position_grch38"] = r["position"]
            # GRCh37 position unknown, leave as 0
            r["position"] = 0
        log.info(f"  GRCh38 only: {len(rows_38)} variants (no GRCh37 positions)")
        return rows_38

    return []


async def delete_score_data(pgs_id: str, session: AsyncSession) -> None:
    """Delete all data for a PGS ID (for --force reimport)."""
    # Delete in dependency order
    await session.execute(
        text("DELETE FROM prs_reference_distributions WHERE pgs_id = :pid"),
        {"pid": pgs_id},
    )
    await session.execute(
        text("DELETE FROM prs_variant_weights WHERE pgs_id = :pid"),
        {"pid": pgs_id},
    )
    await session.execute(
        text("DELETE FROM prs_results WHERE pgs_id = :pid"),
        {"pid": pgs_id},
    )
    await session.execute(
        text("DELETE FROM prs_scores WHERE pgs_id = :pid"),
        {"pid": pgs_id},
    )
    await session.commit()
    log.info(f"  Deleted existing data for {pgs_id}")


async def ingest_score(
    pgs_id: str, session: AsyncSession, client: httpx.AsyncClient, force: bool = False
) -> None:
    """Ingest a single PGS score: metadata + weights + SNP records.

    Downloads BOTH GRCh37 and GRCh38 harmonized files to store positions
    for both genome builds.
    """
    # Check if already imported
    existing = await session.get(PrsScore, pgs_id)
    if existing:
        if force:
            log.info(f"{pgs_id}: Force reimport — deleting existing data...")
            await delete_score_data(pgs_id, session)
        else:
            log.info(f"{pgs_id} already imported, skipping (use --force to reimport)")
            return

    log.info(f"Fetching metadata for {pgs_id}...")
    meta = await fetch_score_metadata(client, pgs_id)
    auc = await fetch_best_auc(client, pgs_id)

    # Download BOTH builds
    log.info(f"Downloading scoring files for {pgs_id}...")
    content_37, content_38 = await asyncio.gather(
        download_scoring_file(client, pgs_id, SCORING_FILE_URL_37),
        download_scoring_file(client, pgs_id, SCORING_FILE_URL_38),
    )

    if not content_37 and not content_38:
        raise RuntimeError(f"Could not download any scoring file for {pgs_id}")

    # Parse both builds
    rows_37 = parse_scoring_file(content_37) if content_37 else None
    rows_38 = parse_scoring_file(content_38) if content_38 else None

    # Merge to get both position sets
    rows = merge_builds(rows_37, rows_38)
    log.info(f"  {len(rows)} total variants for {pgs_id}")

    if not rows:
        log.warning(f"No variants parsed for {pgs_id}, skipping")
        return

    # Extract metadata fields
    trait_name = meta.get("trait_reported", "Unknown")
    trait_efo = None
    efo_traits = meta.get("trait_efo", [])
    if efo_traits:
        trait_efo = efo_traits[0].get("id")

    pub = meta.get("publication", {}) or {}
    pmid = pub.get("PMID") or pub.get("pmid")
    if isinstance(pmid, str):
        pmid = pmid if pmid else None
    doi = pub.get("doi")

    samples_dev = meta.get("samples_variants", [])
    dev_ancestry = None
    if samples_dev:
        ancestries = [s.get("ancestry_broad", "") for s in samples_dev if s.get("ancestry_broad")]
        dev_ancestry = ", ".join(ancestries[:3]) if ancestries else None

    # Create PrsScore record
    prs_score = PrsScore(
        pgs_id=pgs_id,
        trait_name=trait_name,
        trait_efo_id=trait_efo,
        publication_pmid=str(pmid) if pmid else None,
        publication_doi=doi,
        n_variants_total=len(rows),
        development_ancestry=dev_ancestry,
        reported_auc=auc,
    )
    session.add(prs_score)

    # Upsert SNP records for any new rsids
    snp_values = []
    for row in rows:
        chrom = row["chrom"]
        pos_37 = row["position"]
        pos_38 = row.get("position_grch38", 0)
        if chrom and (pos_37 or pos_38):
            snp_values.append({
                "rsid": row["rsid"],
                "chrom": chrom,
                "position": pos_37,
                "position_grch38": pos_38 if pos_38 else None,
                "ref_allele": row.get("other_allele", ""),
                "alt_allele": row["effect_allele"],
            })

    # Batch upsert SNPs — update GRCh38 position on conflict if we have it
    BATCH_SIZE = 1000
    if snp_values:
        for i in range(0, len(snp_values), BATCH_SIZE):
            batch = snp_values[i : i + BATCH_SIZE]
            stmt = (
                pg_insert(Snp)
                .values(batch)
                .on_conflict_do_update(
                    index_elements=["rsid"],
                    set_={
                        "position_grch38": text("COALESCE(EXCLUDED.position_grch38, snps.position_grch38)"),
                    },
                )
            )
            await session.execute(stmt)

    # Insert variant weights in batches
    for i in range(0, len(rows), BATCH_SIZE):
        batch = rows[i : i + BATCH_SIZE]
        weight_records = [
            PrsVariantWeight(
                pgs_id=pgs_id,
                rsid=row["rsid"],
                chrom=row["chrom"],
                position=row["position"],
                position_grch38=row.get("position_grch38") or None,
                effect_allele=row["effect_allele"],
                weight=row["weight"],
            )
            for row in batch
        ]
        session.add_all(weight_records)
        await session.flush()

    await session.commit()
    log.info(f"Successfully imported {pgs_id}: {trait_name} ({len(rows)} variants)")


async def update_auc_only(pgs_ids: list[str]) -> None:
    """Fetch and update AUC for existing scores without re-importing weights."""
    engine = create_async_engine(settings.database_url)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with httpx.AsyncClient(timeout=120) as client:
        async with async_session() as session:
            for pgs_id in pgs_ids:
                existing = await session.get(PrsScore, pgs_id)
                if not existing:
                    log.warning(f"{pgs_id} not in database, skipping")
                    continue
                if existing.reported_auc is not None:
                    log.info(f"{pgs_id} already has AUC={existing.reported_auc:.3f}, skipping")
                    continue

                auc = await fetch_best_auc(client, pgs_id)
                if auc is not None:
                    existing.reported_auc = auc
                    log.info(f"{pgs_id}: set AUC={auc:.3f}")
                else:
                    log.warning(f"{pgs_id}: no AUC found in PGS Catalog")

            await session.commit()

    await engine.dispose()
    log.info("AUC update complete")


async def main(pgs_ids: list[str], force: bool = False) -> None:
    engine = create_async_engine(settings.database_url)

    # Ensure tables exist
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with httpx.AsyncClient(timeout=120) as client:
        async with async_session() as session:
            for pgs_id in pgs_ids:
                try:
                    await ingest_score(pgs_id, session, client, force=force)
                except Exception as e:
                    log.error(f"Failed to import {pgs_id}: {e}")
                    await session.rollback()

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Import PGS Catalog scores")
    parser.add_argument("--pgs-id", type=str, help="Single PGS ID to import")
    parser.add_argument("--pgs-ids", nargs="+", type=str, help="Multiple PGS IDs to import")
    parser.add_argument("--top-scores", type=int, help="Import top N priority scores")
    parser.add_argument("--force", action="store_true", help="Delete and reimport existing scores")
    parser.add_argument("--update-auc", action="store_true", help="Only fetch/update AUC for existing scores (no reimport)")
    args = parser.parse_args()

    if args.pgs_ids:
        ids = args.pgs_ids
    elif args.pgs_id:
        ids = [args.pgs_id]
    elif args.top_scores:
        ids = PRIORITY_SCORES[: args.top_scores]
    else:
        ids = PRIORITY_SCORES

    if args.update_auc:
        asyncio.run(update_auc_only(ids))
    else:
        asyncio.run(main(ids, force=args.force))
