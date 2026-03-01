"""Extract PRSKB empirical percentile data for our 27 GWAS studies.

One-time script. Reads the PRSKB allPercentiles_{cohort}.txt files and
produces app/data/gwas_percentiles.json with p0-p100 for each study × ancestry.

Usage:
    python -m scripts.extract_gwas_percentiles
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

PRSKB_DIR = Path("existing_tools/PolyRiskScore/static/downloadables/preppedServerFiles")
OUTPUT = Path("app/data/gwas_percentiles.json")

COHORT_MAP = {
    "eur": "EUR",
    "afr": "AFR",
    "amr": "AMR",
    "eas": "EAS",
    "sas": "SAS",
}

# Our 27 GWAS studies with their traits (for disambiguation when multiple entries exist)
OUR_STUDIES = {
    "GCST000755": "HDL Cholesterol",
    "GCST001341": "Multiple Sclerosis",
    "GCST003044": "Crohn's Disease",
    "GCST003045": "Ulcerative Colitis",
    "GCST003268": "Psoriasis",
    "GCST004521": "Schizophrenia",
    "GCST004748": "Lung Cancer",
    "GCST005195": "Coronary Artery Disease",
    "GCST005212": "Asthma",
    "GCST005536": "Type 1 Diabetes",
    "GCST005839": "Depression",
    "GCST006061": "Atrial Fibrillation",
    "GCST006085": "Prostate Cancer",
    "GCST006624": "Systolic Blood Pressure",
    "GCST006626": "Pulse Pressure",
    "GCST006959": "Rheumatoid Arthritis",
    "GCST007320": "Alzheimer's Disease",
    "GCST007552": "Colorectal Cancer",
    "GCST008103": "Bipolar Disorder",
    "GCST009325": "Parkinson's Disease",
    "GCST011956": "Systemic Lupus Erythematosus",
    "GCST90011809": "Melanoma",
    "GCST90014132": "Ischemic Stroke",
    "GCST90018926": "Type 2 Diabetes",
    "GCST90018961": "LDL Cholesterol",
    "GCST90018974": "Total Cholesterol",
    "GCST90090980": "Breast Cancer",
}


def _find_best_entry(data: dict, study_id: str, our_trait: str) -> dict | None:
    """Find the best matching PRSKB entry for a study.

    Strategy:
    1. Find all entries containing the study_id
    2. Prefer entries with |NA|NA| annotation (most inclusive SNP set)
    3. Among NA|NA entries, prefer the one matching our trait name
    4. Among remaining, pick the one with highest snpOverlap
    """
    matches = [(k, data[k]) for k in data if study_id in k]
    if not matches:
        return None

    if len(matches) == 1:
        return matches[0][1]

    # Prefer |NA|NA| entries (no ancestry-specific annotation filter)
    na_matches = [(k, v) for k, v in matches if "|NA|NA|" in k]
    if na_matches:
        matches = na_matches

    if len(matches) == 1:
        return matches[0][1]

    # Try to match our trait name
    trait_lower = our_trait.lower()
    for key, entry in matches:
        entry_trait = key.split("|")[0].lower()
        if trait_lower in entry_trait or entry_trait in trait_lower:
            return entry

    # Fall back to highest snpOverlap
    return max(matches, key=lambda x: x[1].get("snpOverlap", 0))[1]


def extract_percentiles(entry: dict) -> dict[str, float]:
    """Extract p0-p100 from a PRSKB entry."""
    return {f"p{i}": entry[f"p{i}"] for i in range(101)}


def main():
    result: dict[str, dict[str, dict[str, float]]] = {}

    for cohort_key, ancestry in COHORT_MAP.items():
        path = PRSKB_DIR / f"allPercentiles_{cohort_key}.txt"
        if not path.exists():
            log.error(f"Missing file: {path}")
            sys.exit(1)

        log.info(f"Loading {path} ({path.stat().st_size / 1e6:.1f} MB)...")
        with open(path) as f:
            data = json.load(f)

        for study_id, our_trait in OUR_STUDIES.items():
            entry = _find_best_entry(data, study_id, our_trait)
            if entry is None:
                log.warning(f"  {study_id} ({our_trait}): NOT FOUND in {cohort_key}")
                continue

            pcts = extract_percentiles(entry)
            result.setdefault(study_id, {})[ancestry] = pcts

            if ancestry == "EUR":
                log.info(
                    f"  {study_id}: {entry.get('reportedTrait', '?')[:40]} "
                    f"type={entry.get('ogValueTypes')} "
                    f"overlap={entry.get('snpOverlap')} "
                    f"p50={pcts['p50']}"
                )

    # Validate
    missing = [s for s in OUR_STUDIES if s not in result]
    if missing:
        log.error(f"Missing studies: {missing}")
        sys.exit(1)

    incomplete = [s for s, v in result.items() if len(v) < 5]
    if incomplete:
        log.warning(f"Studies with < 5 ancestries: {incomplete}")

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT, "w") as f:
        json.dump(result, f, indent=2)

    size_kb = OUTPUT.stat().st_size / 1024
    log.info(f"Wrote {OUTPUT} ({size_kb:.0f} KB, {len(result)} studies × {len(COHORT_MAP)} ancestries)")


if __name__ == "__main__":
    main()
