"""Ingest curated GWAS-hit PRS from PRSKB associations data.

Reads associations_table.tsv and study_table.tsv from the PRSKB data,
extracts curated studies, converts OR→beta, computes analytical reference
distributions, and loads into gwas_* tables.

Population-specific AFs are fetched from Ensembl REST API when --fetch-afs
is passed; otherwise the global risk allele frequency (raf) from the GWAS
data is used for all populations.

Usage:
    python -m scripts.ingest_gwas_scores
    python -m scripts.ingest_gwas_scores --fetch-afs
    python -m scripts.ingest_gwas_scores --force   # delete and reimport
"""

from __future__ import annotations

import argparse
import asyncio
import csv
import json
import logging
import time
from collections import defaultdict
from math import log as math_log, sqrt
from pathlib import Path

import httpx
from sqlalchemy import delete, select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.base import Base
from app.models.gwas import (
    GwasAssociation,
    GwasPrsResult,
    GwasReferenceDistribution,
    GwasStudy,
)

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).resolve().parent.parent / "existing_tools" / "PolyRiskScore" / "tables"
PRSKB_DIR = Path(__file__).resolve().parent.parent / "existing_tools" / "PolyRiskScore" / "static" / "downloadables" / "preppedServerFiles"

ANCESTRY_GROUPS = ["EUR", "AFR", "EAS", "SAS", "AMR"]

# Ensembl population → our ancestry group mapping
ENSEMBL_POP_MAP = {
    "1000GENOMES:phase_3:EUR": "eur_af",
    "1000GENOMES:phase_3:AFR": "afr_af",
    "1000GENOMES:phase_3:EAS": "eas_af",
    "1000GENOMES:phase_3:SAS": "sas_af",
    "1000GENOMES:phase_3:AMR": "amr_af",
}

# Complement mapping for strand-flipped alleles
_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}

# ──────────────────────────────────────────────────────────────────────
# Curated studies: study_id → {trait, category, trait_filter}
# trait_filter: only include associations with this trait (for multi-trait studies)
# ──────────────────────────────────────────────────────────────────────
CURATED_STUDIES: dict[str, dict] = {
    # Cardiovascular
    "GCST005195": {"trait": "Coronary Artery Disease", "category": "cardiovascular"},
    "GCST006061": {"trait": "Atrial Fibrillation", "category": "cardiovascular"},
    "GCST90014132": {"trait": "Ischemic Stroke", "category": "cardiovascular"},
    "GCST006624": {"trait": "Systolic Blood Pressure", "category": "cardiovascular"},
    "GCST006626": {"trait": "Pulse Pressure", "category": "cardiovascular"},
    # Cancer
    "GCST90090980": {"trait": "Breast Cancer", "category": "cancer"},
    "GCST006085": {"trait": "Prostate Cancer", "category": "cancer"},
    "GCST007552": {"trait": "Colorectal Cancer", "category": "cancer"},
    "GCST004748": {"trait": "Lung Cancer", "category": "cancer"},
    "GCST90011809": {"trait": "Melanoma", "category": "cancer"},
    # Metabolic
    "GCST90018926": {"trait": "Type 2 Diabetes", "category": "metabolic"},
    "GCST005536": {"trait": "Type 1 Diabetes", "category": "metabolic"},
    "GCST90018974": {"trait": "Total Cholesterol", "category": "metabolic"},
    "GCST90018961": {"trait": "LDL Cholesterol", "category": "metabolic"},
    "GCST000755": {"trait": "HDL Cholesterol", "category": "metabolic"},
    # Autoimmune
    "GCST006959": {"trait": "Rheumatoid Arthritis", "category": "autoimmune"},
    "GCST003044": {"trait": "Crohn's Disease", "category": "autoimmune"},
    "GCST003045": {"trait": "Ulcerative Colitis", "category": "autoimmune"},
    "GCST001341": {"trait": "Multiple Sclerosis", "category": "autoimmune"},
    "GCST005212": {"trait": "Asthma", "category": "autoimmune"},
    "GCST011956": {"trait": "Systemic Lupus Erythematosus", "category": "autoimmune"},
    "GCST003268": {"trait": "Psoriasis", "category": "autoimmune"},
    # Neuropsychiatric
    "GCST007320": {"trait": "Alzheimer's Disease", "category": "neuropsychiatric",
                    "trait_filter": "Alzheimer Disease"},
    "GCST009325": {"trait": "Parkinson's Disease", "category": "neuropsychiatric"},
    "GCST004521": {"trait": "Schizophrenia", "category": "neuropsychiatric",
                    "trait_filter": "Schizophrenia"},
    "GCST008103": {"trait": "Bipolar Disorder", "category": "neuropsychiatric"},
    "GCST005839": {"trait": "Depression", "category": "neuropsychiatric"},
}


def _parse_position(coord: str) -> tuple[str | None, int | None]:
    """Parse 'chr:pos' format (e.g. '8:105553186') → (chrom, position)."""
    if not coord or coord == "NA":
        return None, None
    parts = coord.split(":")
    if len(parts) != 2:
        return None, None
    chrom = parts[0].lstrip("chr")
    try:
        pos = int(parts[1])
    except ValueError:
        return None, None
    return chrom, pos


def _parse_float(val: str) -> float | None:
    if not val or val == "NA":
        return None
    try:
        return float(val)
    except ValueError:
        return None


def load_study_metadata() -> dict[str, dict]:
    """Load PMID, citation, etc. from study_table.tsv."""
    study_file = DATA_DIR / "study_table.tsv"
    metadata: dict[str, dict] = {}
    with open(study_file) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            sid = row["studyID"]
            if sid in CURATED_STUDIES and sid not in metadata:
                metadata[sid] = {
                    "pmid": row.get("pubMedID"),
                    "citation": row.get("citation"),
                    "reported_trait": row.get("reportedTrait"),
                    "value_type": row.get("ogValueTypes", "").lower(),
                }
    return metadata


def load_associations() -> dict[str, list[dict]]:
    """Load associations from associations_table.tsv for curated studies.

    Filters to match PRSKB's percentile computation: only includes
    pValueAnnotation='NA' rows (non-ancestry-specific) unless ALL rows
    for a study are ancestry-annotated (e.g. Crohn's with '(ea)').
    """
    assoc_file = DATA_DIR / "associations_table.tsv"
    raw_assocs: dict[str, list[dict]] = defaultdict(list)

    with open(assoc_file) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            sid = row["studyID"]
            if sid not in CURATED_STUDIES:
                continue

            # Apply trait filter if specified
            trait_filter = CURATED_STUDIES[sid].get("trait_filter")
            if trait_filter and row["trait"] != trait_filter:
                continue

            raw_assocs[sid].append(row)

    # Filter to pValueAnnotation='NA' where applicable (matches PRSKB |NA|NA| percentile entries)
    filtered: dict[str, list[dict]] = {}
    for sid, rows in raw_assocs.items():
        na_rows = [r for r in rows if r.get("pValueAnnotation", "NA") == "NA"]
        if na_rows:
            # Has non-ancestry-specific associations — use only those
            filtered[sid] = na_rows
        else:
            # All rows are ancestry-annotated (e.g. Crohn's with '(ea)') — keep all
            filtered[sid] = rows

    return filtered


def deduplicate_snps(rows: list[dict], value_type: str) -> list[dict]:
    """Deduplicate SNPs per study: keep lowest p-value for each rsid."""
    by_snp: dict[str, dict] = {}
    for row in rows:
        rsid = row["snp"]
        if not rsid or not rsid.startswith("rs"):
            continue

        p_val = _parse_float(row["pValue"])

        # Extract the effect size
        if value_type == "or":
            or_val = _parse_float(row["oddsRatio"])
            if or_val is None or or_val <= 0:
                continue
            beta = math_log(or_val)
        else:
            beta = _parse_float(row["betaValue"])
            if beta is None:
                continue

        risk_allele = row.get("riskAllele", "").strip()
        if not risk_allele or len(risk_allele) > 1:
            # Skip multi-character alleles (indels, haplotypes)
            continue

        if rsid not in by_snp or (p_val is not None and (by_snp[rsid]["p_value"] is None or p_val < by_snp[rsid]["p_value"])):
            chrom37, pos37 = _parse_position(row.get("hg19", ""))
            chrom38, pos38 = _parse_position(row.get("hg38", ""))

            by_snp[rsid] = {
                "rsid": rsid,
                "chrom": chrom37 or chrom38,
                "position": pos37,
                "position_grch38": pos38,
                "risk_allele": risk_allele,
                "beta": beta,
                "risk_allele_frequency": _parse_float(row.get("raf", "")),
                "p_value": p_val,
            }

    return list(by_snp.values())


def compute_ref_dist(snps: list[dict], af_key: str = "risk_allele_frequency") -> tuple[float, float]:
    """Compute analytical HWE reference distribution.

    E[S] = Σ 2 * p * w
    Var[S] = Σ 2 * p * (1-p) * w²
    """
    mean = 0.0
    variance = 0.0
    for snp in snps:
        p = snp.get(af_key)
        w = snp["beta"]
        if p is None or p <= 0 or p >= 1:
            continue
        mean += 2 * p * w
        variance += 2 * p * (1 - p) * w * w
    std = sqrt(variance) if variance > 0 else 0.0
    return mean, std


async def fetch_ensembl_afs(
    rsids: list[str], client: httpx.AsyncClient
) -> dict[str, dict[str, float]]:
    """Fetch per-population AFs from Ensembl REST API.

    Returns: {rsid: {eur_af: 0.12, afr_af: 0.34, ...}}
    """
    result: dict[str, dict[str, float]] = {}
    batch_size = 200  # Ensembl POST endpoint limit

    for i in range(0, len(rsids), batch_size):
        batch = rsids[i : i + batch_size]
        try:
            resp = await client.post(
                "https://rest.ensembl.org/variation/homo_sapiens",
                params={"pops": "1"},
                json={"ids": batch},
                headers={"Content-Type": "application/json", "Accept": "application/json"},
                timeout=120,
            )
            if resp.status_code == 429:
                retry_after = float(resp.headers.get("Retry-After", "5"))
                log.warning(f"  Rate limited, sleeping {retry_after}s...")
                await asyncio.sleep(retry_after)
                resp = await client.post(
                    "https://rest.ensembl.org/variation/homo_sapiens",
                    params={"pops": "1"},
                    json={"ids": batch},
                    headers={"Content-Type": "application/json", "Accept": "application/json"},
                    timeout=120,
                )
            resp.raise_for_status()
            data = resp.json()
        except Exception as e:
            log.warning(f"  Ensembl batch {i}-{i+len(batch)} failed: {e}")
            continue

        for rsid, info in data.items():
            if not isinstance(info, dict):
                continue
            pops = info.get("populations", [])
            afs: dict[str, float] = {}
            for pop in pops:
                pop_name = pop.get("population", "")
                if pop_name in ENSEMBL_POP_MAP:
                    # Use the frequency of the first allele — we'll match to risk allele later
                    allele = pop.get("allele", "")
                    freq = pop.get("frequency")
                    if freq is not None:
                        col = ENSEMBL_POP_MAP[pop_name]
                        # Store all allele freqs, pick risk allele later
                        afs.setdefault(f"{col}_{allele}", freq)
            result[rsid] = afs

        if i + batch_size < len(rsids):
            await asyncio.sleep(0.5)  # Respect rate limits

    return result


def resolve_ensembl_afs(
    snps: list[dict], ensembl_data: dict[str, dict[str, float]]
) -> None:
    """Match Ensembl population AFs to risk alleles, updating snps in place."""
    for snp in snps:
        rsid = snp["rsid"]
        risk_allele = snp["risk_allele"]
        afs = ensembl_data.get(rsid, {})

        for ancestry_col in ["eur_af", "afr_af", "eas_af", "sas_af", "amr_af"]:
            # Look for the risk allele frequency in this population
            key = f"{ancestry_col}_{risk_allele}"
            if key in afs:
                snp[ancestry_col] = afs[key]


async def ingest(session: AsyncSession, force: bool = False, fetch_afs: bool = False) -> None:
    study_meta = load_study_metadata()
    raw_assocs = load_associations()

    if force:
        log.info("Force mode: deleting existing GWAS data...")
        await session.execute(delete(GwasPrsResult))
        await session.execute(delete(GwasReferenceDistribution))
        await session.execute(delete(GwasAssociation))
        await session.execute(delete(GwasStudy))
        await session.commit()

    # Collect all unique rsids for Ensembl lookup
    all_rsids: set[str] = set()
    study_snps: dict[str, list[dict]] = {}

    for study_id, study_info in CURATED_STUDIES.items():
        rows = raw_assocs.get(study_id, [])
        if not rows:
            log.warning(f"  {study_id}: No associations found in data — skipping")
            continue

        meta = study_meta.get(study_id, {})
        value_type = meta.get("value_type", "beta")

        snps = deduplicate_snps(rows, value_type)
        if not snps:
            log.warning(f"  {study_id}: No valid SNPs after dedup — skipping")
            continue

        study_snps[study_id] = snps
        for s in snps:
            all_rsids.add(s["rsid"])

    # Load population AFs from PRSKB 1000G MAF files (per-allele frequencies)
    # These files store frequencies for BOTH alleles at each position, so we can
    # match the risk allele exactly. This is critical for correct imputation.
    prskb_maf: dict[str, dict] = {}  # rsid -> {alleles: {A: 0.12, G: 0.88}, ...}
    cohort_to_col = {"eur": "eur_af", "afr": "afr_af", "eas": "eas_af", "sas": "sas_af", "amr": "amr_af"}
    for cohort, col in cohort_to_col.items():
        maf_path = PRSKB_DIR / f"{cohort}_maf_hg19.txt"
        if not maf_path.exists():
            log.warning(f"  Missing PRSKB MAF file: {maf_path}")
            continue
        log.info(f"Loading PRSKB MAF: {maf_path.name}...")
        with open(maf_path) as f:
            maf_data = json.load(f)
        for rsid in all_rsids:
            if rsid in maf_data:
                entry = prskb_maf.setdefault(rsid, {})
                entry[col] = maf_data[rsid]["alleles"]
    log.info(f"  Found PRSKB MAFs for {len(prskb_maf)}/{len(all_rsids)} SNPs")

    # Process each study
    n_studies = 0
    n_total_snps = 0

    for study_id, study_info in CURATED_STUDIES.items():
        snps = study_snps.get(study_id)
        if not snps:
            continue

        meta = study_meta.get(study_id, {})
        value_type = meta.get("value_type", "beta")

        # Apply PRSKB MAFs matched to risk allele (with strand complement fallback)
        for snp in snps:
            rsid = snp["rsid"]
            risk_allele = snp["risk_allele"]
            comp_allele = _COMPLEMENT.get(risk_allele, "")
            maf_entry = prskb_maf.get(rsid)
            if maf_entry:
                for col in ["eur_af", "afr_af", "eas_af", "sas_af", "amr_af"]:
                    alleles = maf_entry.get(col)
                    if not alleles:
                        continue
                    if risk_allele in alleles:
                        snp[col] = alleles[risk_allele]
                    elif comp_allele in alleles:
                        snp[col] = alleles[comp_allele]

        # Check if study already exists
        existing = await session.execute(
            select(GwasStudy).where(GwasStudy.study_id == study_id)
        )
        if existing.scalar_one_or_none():
            log.info(f"  {study_id}: Already exists — skipping (use --force to reimport)")
            continue

        # Insert study
        study = GwasStudy(
            study_id=study_id,
            trait=study_info["trait"],
            reported_trait=meta.get("reported_trait"),
            category=study_info["category"],
            citation=meta.get("citation"),
            pmid=meta.get("pmid"),
            n_snps=len(snps),
            value_type=value_type,
        )
        session.add(study)

        # Insert associations
        for snp in snps:
            assoc = GwasAssociation(
                study_id=study_id,
                rsid=snp["rsid"],
                chrom=snp.get("chrom"),
                position=snp.get("position"),
                position_grch38=snp.get("position_grch38"),
                risk_allele=snp["risk_allele"],
                beta=snp["beta"],
                risk_allele_frequency=snp.get("risk_allele_frequency"),
                p_value=snp.get("p_value"),
                eur_af=snp.get("eur_af"),
                afr_af=snp.get("afr_af"),
                eas_af=snp.get("eas_af"),
                sas_af=snp.get("sas_af"),
                amr_af=snp.get("amr_af"),
            )
            session.add(assoc)

        # Compute reference distributions per ancestry
        # Use population-specific AFs (from 1000G) when available, fall back to global raf
        for anc in ANCESTRY_GROUPS:
            af_col = f"{anc.lower()}_af"
            snps_with_pop_af = [s for s in snps if s.get(af_col) is not None]

            if len(snps_with_pop_af) >= len(snps) * 0.5:
                # Use population-specific AFs (with global raf fallback per-SNP)
                mean_val = 0.0
                var_val = 0.0
                for s in snps:
                    p = s.get(af_col) or s.get("risk_allele_frequency")
                    w = s["beta"]
                    if p is not None and 0 < p < 1:
                        mean_val += 2 * p * w
                        var_val += 2 * p * (1 - p) * w * w
                mean = mean_val
                std = sqrt(var_val) if var_val > 0 else 0.0
            else:
                # Fall back to global raf
                mean, std = compute_ref_dist(snps)

            session.add(GwasReferenceDistribution(
                study_id=study_id,
                ancestry_group=anc,
                mean=mean,
                std=std,
            ))

        n_studies += 1
        n_total_snps += len(snps)
        log.info(
            f"  {study_id}: {study_info['trait']} — {len(snps)} SNPs, "
            f"type={value_type}, ref_mean={mean:.4f}, ref_std={std:.4f}"
        )

    await session.commit()
    log.info(f"Ingested {n_studies} studies with {n_total_snps} total SNP associations")


async def main(force: bool = False, fetch_afs: bool = False) -> None:
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    t0 = time.perf_counter()
    async with async_session() as session:
        await ingest(session, force=force, fetch_afs=fetch_afs)
    elapsed = time.perf_counter() - t0

    log.info(f"Done in {elapsed:.1f}s")
    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Ingest curated GWAS-hit PRS from PRSKB data")
    parser.add_argument("--force", action="store_true", help="Delete and reimport all GWAS data")
    parser.add_argument("--fetch-afs", action="store_true",
                        help="Fetch per-population AFs from Ensembl (slower, more accurate ref dists)")
    args = parser.parse_args()

    asyncio.run(main(force=args.force, fetch_afs=args.fetch_afs))
