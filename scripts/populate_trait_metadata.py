"""Populate prs_trait_metadata with prevalence data for absolute risk computation.

Each PRS score for a binary trait (disease) needs a population prevalence estimate
so the absolute risk model can convert z-scores into disease probabilities.

Prevalence sources are documented per-trait below, with reference URLs.
All prevalence figures are lifetime risk or point prevalence for a general adult
population (mixed sex, unless sex-specific cancer).

Usage:
    python -m scripts.populate_trait_metadata
    python -m scripts.populate_trait_metadata --force   # overwrite existing entries

References are stored in the `source` column of prs_trait_metadata so users can
verify the prevalence numbers. The frontend should display these as clickable links.
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.base import Base
from app.models.prs import PrsScore, PrsTraitMetadata

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


# ── Curated trait metadata ────────────────────────────────────────────────
#
# Each entry maps a trait name pattern (lowercase) to:
#   trait_type:  "binary" (disease) or "continuous" (quantitative)
#   prevalence:  lifetime risk or point prevalence (0-1), for binary traits
#   source:      human-readable citation with URL
#   pop_mean:    population mean (for continuous traits only)
#   pop_std:     population std deviation (for continuous traits only)
#
# Matching is case-insensitive substring: if the prs_scores.trait_name
# contains the key, it matches.
#
# ──────────────────────────────────────────────────────────────────────────

TRAIT_METADATA: dict[str, dict] = {
    # ── Cardiovascular ──────────────────────────────────────────────────
    "coronary artery disease": {
        "trait_type": "binary",
        "prevalence": 0.065,
        "source": (
            "CDC NHANES 2017-2020: 6.5% of US adults aged 20+ have CHD. "
            "https://www.cdc.gov/heart-disease/data-research/facts-stats/"
        ),
    },
    "coronary heart disease": {
        "trait_type": "binary",
        "prevalence": 0.065,
        "source": (
            "CDC NHANES 2017-2020: 6.5% of US adults aged 20+ have CHD. "
            "https://www.cdc.gov/heart-disease/data-research/facts-stats/"
        ),
    },
    "atrial fibrillation": {
        "trait_type": "binary",
        "prevalence": 0.034,
        "source": (
            "AHA 2023 Heart Disease & Stroke Statistics: 3.4% prevalence in US adults. "
            "https://www.ahajournals.org/doi/10.1161/CIR.0000000000001123"
        ),
    },
    "heart failure": {
        "trait_type": "binary",
        "prevalence": 0.024,
        "source": (
            "AHA 2023: ~6.7M US adults (2.4%) have heart failure. "
            "https://www.ahajournals.org/doi/10.1161/CIR.0000000000001123"
        ),
    },
    "stroke": {
        "trait_type": "binary",
        "prevalence": 0.03,
        "source": (
            "AHA 2023: ~3.0% of US adults have had a stroke. "
            "https://www.ahajournals.org/doi/10.1161/CIR.0000000000001123"
        ),
    },

    # ── Metabolic ───────────────────────────────────────────────────────
    "type 2 diabetes": {
        "trait_type": "binary",
        "prevalence": 0.113,
        "source": (
            "CDC National Diabetes Statistics Report 2022: 11.3% of US adults. "
            "https://www.cdc.gov/diabetes/php/data-research/index.html"
        ),
    },
    "diabetes mellitus": {
        "trait_type": "binary",
        "prevalence": 0.113,
        "source": (
            "CDC National Diabetes Statistics Report 2022: 11.3% of US adults. "
            "https://www.cdc.gov/diabetes/php/data-research/index.html"
        ),
    },
    "obesity": {
        "trait_type": "binary",
        "prevalence": 0.419,
        "source": (
            "CDC NHANES 2017-2020: 41.9% of US adults have obesity (BMI >= 30). "
            "https://www.cdc.gov/obesity/php/data-research/adult-obesity-facts.html"
        ),
    },

    # ── Cancer ──────────────────────────────────────────────────────────
    "breast cancer": {
        "trait_type": "binary",
        "prevalence": 0.132,
        "source": (
            "NCI SEER: 13.2% lifetime risk of female breast cancer (2018-2020 data). "
            "https://seer.cancer.gov/statfacts/html/breast.html"
        ),
    },
    "prostate cancer": {
        "trait_type": "binary",
        "prevalence": 0.128,
        "source": (
            "NCI SEER: 12.8% lifetime risk of prostate cancer (2018-2020 data). "
            "https://seer.cancer.gov/statfacts/html/prost.html"
        ),
    },
    "colorectal cancer": {
        "trait_type": "binary",
        "prevalence": 0.041,
        "source": (
            "NCI SEER: 4.1% lifetime risk of colorectal cancer (2018-2020 data). "
            "https://seer.cancer.gov/statfacts/html/colorect.html"
        ),
    },
    "lung cancer": {
        "trait_type": "binary",
        "prevalence": 0.062,
        "source": (
            "NCI SEER: 6.2% lifetime risk of lung/bronchus cancer (2018-2020 data). "
            "https://seer.cancer.gov/statfacts/html/lungb.html"
        ),
    },
    "melanoma": {
        "trait_type": "binary",
        "prevalence": 0.024,
        "source": (
            "NCI SEER: ~2.4% lifetime risk of melanoma (2018-2020 data). "
            "https://seer.cancer.gov/statfacts/html/melan.html"
        ),
    },

    # ── Neurological ────────────────────────────────────────────────────
    "alzheimer": {
        "trait_type": "binary",
        "prevalence": 0.107,
        "source": (
            "Alzheimer's Association 2024: 10.7% of Americans aged 65+ have Alzheimer's. "
            "https://www.alz.org/alzheimers-dementia/facts-figures"
        ),
    },
    "dementia": {
        "trait_type": "binary",
        "prevalence": 0.107,
        "source": (
            "Alzheimer's Association 2024: 10.7% of Americans aged 65+ have Alzheimer's/dementia. "
            "https://www.alz.org/alzheimers-dementia/facts-figures"
        ),
    },
    "parkinson": {
        "trait_type": "binary",
        "prevalence": 0.02,
        "source": (
            "Parkinson's Foundation: ~2% lifetime risk; ~1M Americans affected. "
            "https://www.parkinson.org/understanding-parkinsons/statistics"
        ),
    },
    "schizophrenia": {
        "trait_type": "binary",
        "prevalence": 0.0075,
        "source": (
            "NIMH: ~0.75% lifetime prevalence of schizophrenia worldwide. "
            "https://www.nimh.nih.gov/health/statistics/schizophrenia"
        ),
    },
    "bipolar": {
        "trait_type": "binary",
        "prevalence": 0.028,
        "source": (
            "NIMH: 2.8% of US adults had bipolar disorder in the past year. "
            "https://www.nimh.nih.gov/health/statistics/bipolar-disorder"
        ),
    },
    "major depressive disorder": {
        "trait_type": "binary",
        "prevalence": 0.083,
        "source": (
            "NIMH: 8.3% of US adults had at least one major depressive episode in 2021. "
            "https://www.nimh.nih.gov/health/statistics/major-depression"
        ),
    },
    "depression": {
        "trait_type": "binary",
        "prevalence": 0.083,
        "source": (
            "NIMH: 8.3% of US adults had at least one major depressive episode in 2021. "
            "https://www.nimh.nih.gov/health/statistics/major-depression"
        ),
    },

    # ── Autoimmune / Inflammatory ───────────────────────────────────────
    "rheumatoid arthritis": {
        "trait_type": "binary",
        "prevalence": 0.01,
        "source": (
            "CDC: ~1.0% of US adults have rheumatoid arthritis. "
            "https://www.cdc.gov/arthritis/data_statistics/arthritis-related-stats.htm"
        ),
    },
    "celiac": {
        "trait_type": "binary",
        "prevalence": 0.01,
        "source": (
            "Celiac Disease Foundation: ~1% worldwide prevalence. "
            "https://celiac.org/about-celiac-disease/what-is-celiac-disease/facts-and-figures/"
        ),
    },
    "inflammatory bowel disease": {
        "trait_type": "binary",
        "prevalence": 0.013,
        "source": (
            "CDC: ~3.1M US adults (1.3%) diagnosed with IBD (2015-2016 NHIS). "
            "https://www.cdc.gov/ibd/data-and-statistics/ibd-data-statistics.html"
        ),
    },
    "crohn": {
        "trait_type": "binary",
        "prevalence": 0.005,
        "source": (
            "CDC: ~500K US adults (~0.5%) have Crohn's disease. "
            "https://www.cdc.gov/ibd/data-and-statistics/ibd-data-statistics.html"
        ),
    },
    "ulcerative colitis": {
        "trait_type": "binary",
        "prevalence": 0.003,
        "source": (
            "Gastroenterology 2023: ~0.3% prevalence in Western countries. "
            "https://www.cdc.gov/ibd/data-and-statistics/ibd-data-statistics.html"
        ),
    },
    "type 1 diabetes": {
        "trait_type": "binary",
        "prevalence": 0.005,
        "source": (
            "CDC: ~1.6M Americans have type 1 diabetes (~0.5%). "
            "https://www.cdc.gov/diabetes/php/data-research/index.html"
        ),
    },
    "asthma": {
        "trait_type": "binary",
        "prevalence": 0.079,
        "source": (
            "CDC: 7.9% of US adults currently have asthma (2021). "
            "https://www.cdc.gov/asthma/most_recent_national_asthma_data.htm"
        ),
    },

    # ── Continuous traits ───────────────────────────────────────────────
    "body mass index": {
        "trait_type": "continuous",
        "prevalence": None,
        "pop_mean": 26.5,
        "pop_std": 4.5,
        "source": (
            "CDC NHANES 2017-2020: mean BMI ~26.5 kg/m² in US adults. "
            "https://www.cdc.gov/nchs/fastats/body-measurements.htm"
        ),
    },
    "bmi": {
        "trait_type": "continuous",
        "prevalence": None,
        "pop_mean": 26.5,
        "pop_std": 4.5,
        "source": (
            "CDC NHANES 2017-2020: mean BMI ~26.5 kg/m² in US adults. "
            "https://www.cdc.gov/nchs/fastats/body-measurements.htm"
        ),
    },
    "height": {
        "trait_type": "continuous",
        "prevalence": None,
        "pop_mean": 170.0,
        "pop_std": 10.0,
        "source": (
            "CDC NHANES: mean height ~170 cm (mixed sex) in US adults. "
            "https://www.cdc.gov/nchs/fastats/body-measurements.htm"
        ),
    },
    "ldl cholesterol": {
        "trait_type": "continuous",
        "prevalence": None,
        "pop_mean": 110.0,
        "pop_std": 35.0,
        "source": (
            "CDC NHANES 2017-2020: mean LDL ~110 mg/dL in US adults. "
            "https://www.cdc.gov/cholesterol/data-research/facts-stats/"
        ),
    },
    "hdl cholesterol": {
        "trait_type": "continuous",
        "prevalence": None,
        "pop_mean": 54.0,
        "pop_std": 15.0,
        "source": (
            "CDC NHANES 2017-2020: mean HDL ~54 mg/dL in US adults. "
            "https://www.cdc.gov/cholesterol/data-research/facts-stats/"
        ),
    },
    "total cholesterol": {
        "trait_type": "continuous",
        "prevalence": None,
        "pop_mean": 192.0,
        "pop_std": 40.0,
        "source": (
            "CDC NHANES 2017-2020: mean total cholesterol ~192 mg/dL in US adults. "
            "https://www.cdc.gov/cholesterol/data-research/facts-stats/"
        ),
    },
    "systolic blood pressure": {
        "trait_type": "continuous",
        "prevalence": None,
        "pop_mean": 126.0,
        "pop_std": 16.0,
        "source": (
            "AHA 2023: mean SBP ~126 mmHg in US adults. "
            "https://www.ahajournals.org/doi/10.1161/CIR.0000000000001123"
        ),
    },
}


def match_trait(trait_name: str) -> dict | None:
    """Match a PRS trait_name to our curated metadata by case-insensitive substring."""
    name_lower = trait_name.lower()
    for pattern, meta in TRAIT_METADATA.items():
        if pattern in name_lower:
            return meta
    return None


async def populate(force: bool = False) -> None:
    engine = create_async_engine(settings.database_url)

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        # Get all PRS scores
        result = await session.execute(select(PrsScore))
        scores = result.scalars().all()

        if not scores:
            log.warning("No PRS scores in database. Run ingest_pgs first.")
            await engine.dispose()
            return

        log.info(f"Found {len(scores)} PRS scores in database")

        matched = 0
        skipped = 0
        for score in scores:
            meta = match_trait(score.trait_name)
            if not meta:
                log.warning(f"  No metadata match for: {score.pgs_id} — {score.trait_name}")
                continue

            # Check if entry already exists
            existing = await session.execute(
                select(PrsTraitMetadata).where(PrsTraitMetadata.pgs_id == score.pgs_id)
            )
            existing_row = existing.scalar_one_or_none()

            if existing_row and not force:
                log.info(f"  {score.pgs_id} already has metadata, skipping (use --force)")
                skipped += 1
                continue

            if existing_row and force:
                await session.delete(existing_row)
                await session.flush()

            entry = PrsTraitMetadata(
                pgs_id=score.pgs_id,
                trait_type=meta["trait_type"],
                prevalence=meta.get("prevalence"),
                population_mean=meta.get("pop_mean"),
                population_std=meta.get("pop_std"),
                source=meta["source"],
            )
            session.add(entry)
            matched += 1
            log.info(
                f"  {score.pgs_id} ({score.trait_name}): "
                f"type={meta['trait_type']}, "
                f"prevalence={meta.get('prevalence', 'N/A')}, "
                f"source={meta['source'][:60]}..."
            )

        await session.commit()
        log.info(f"Done: {matched} populated, {skipped} skipped")

    await engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Populate PRS trait metadata (prevalence, trait type)")
    parser.add_argument("--force", action="store_true", help="Overwrite existing metadata entries")
    args = parser.parse_args()
    asyncio.run(populate(force=args.force))
