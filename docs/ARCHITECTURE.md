# genewizard.net — How It Works

Technical documentation for the genewizard.net genomic analysis platform. This covers the full pipeline from file upload to results display.

---

## Table of Contents

1. [Overview](#overview)
2. [What Gene Wizard Does](#what-genewizard-does)
3. [The Analysis Pipeline](#the-analysis-pipeline)
4. [File Parsing](#1-file-parsing)
5. [Polygenic Risk Scoring](#2-polygenic-risk-scoring)
6. [Trait Matching](#3-trait-matching)
7. [Reference Distributions](#reference-distributions--the-hardest-part)
8. [Data Sources](#data-sources)
9. [Database Schema](#database-schema)
10. [Privacy & Security](#privacy--security)
11. [Frontend Visualization](#frontend-visualization)

---

## Overview

Gene Wizard analyzes raw genetic data from direct-to-consumer (DTC) genomics companies — 23andMe, AncestryDNA, Dante Labs, etc. — and produces two kinds of results:

1. **Polygenic Risk Scores (PRS):** Aggregate genetic risk for complex traits like heart disease, diabetes, Alzheimer's, etc.
2. **Trait Associations:** Individual SNP variants linked to specific traits from published research.

The entire analysis runs in under 2 minutes, even for whole-genome sequencing files with millions of variants.

**Critical design constraint:** Raw genetic data is **never stored**. Files are parsed in memory, results are saved, and the raw data is immediately discarded.

---

## What Gene Wizard Does

### Polygenic Risk Scores (PRS)

Most common diseases aren't caused by a single gene — they're influenced by thousands of small genetic variants, each contributing a tiny amount of risk. A PRS aggregates all these tiny effects into a single number.

For example, a coronary artery disease (CAD) PRS might look at 1.7 million variants across your genome. Each variant has a **weight** (how much it contributes to risk) and an **effect allele** (which version of the DNA increases risk). Your score is the sum of all your risk contributions.

The raw score alone doesn't mean much — it needs context. That's where **reference distributions** come in: we compare your score against what's expected in a reference population (e.g., European, African, East Asian) and report your **percentile** — where you fall on the bell curve.

### Trait Associations

Beyond the aggregate PRS, individual SNP variants are sometimes strongly linked to specific traits. For example, rs429358 (in the APOE gene) is one of the strongest single-variant predictors of Alzheimer's risk.

Gene Wizard matches your variants against a curated knowledge base of SNP-trait associations from published research, and classifies each match by risk level:

- **Increased:** You carry two copies of the risk allele (homozygous)
- **Moderate:** You carry one copy (heterozygous)
- **Typical:** You don't carry the risk allele

---

## The Analysis Pipeline

When you upload a file, here's what happens step by step:

```
Upload File → Parse → Score PRS → Match Traits → Display Results
     │            │         │            │              │
     ▼            ▼         ▼            ▼              ▼
  Temp file   DataFrame  Raw scores  Risk levels   Dashboard
  (deleted    (in memory  + z-scores  per variant   + charts
   after       only)      + percentiles
   parsing)
```

The upload endpoint accepts the file, streams it to a temporary file, creates an Analysis record with status `"pending"`, and kicks off a background task. The API returns immediately with the analysis ID so the frontend can poll for progress.

---

## 1. File Parsing

**Code:** `app/services/parser.py`

### Supported Formats

| Format | Structure | Example |
|--------|-----------|---------|
| **23andMe** | Tab-separated: rsid, chrom, position, genotype | `rs429358  19  45411941  CT` |
| **AncestryDNA** | Tab-separated: rsid, chrom, position, allele1, allele2 | `rs429358  19  45411941  C  T` |
| **VCF** | Standard VCF 4.x (from WGS providers like Dante Labs) | Standard VCF with GT field |

All formats are auto-detected from file headers. Gzipped files are automatically decompressed (using Intel SIMD-accelerated `isal` when available, for ~3x faster decompression).

### What Parsing Produces

A normalized Polars DataFrame with columns:

| Column | Type | Example |
|--------|------|---------|
| rsid | String | "rs429358" |
| chrom | String | "19" |
| position | Int | 45411941 |
| allele1 | String | "C" |
| allele2 | String | "T" |

### Filtering

The parser applies strict quality filters:
- Only valid DNA bases (A, C, G, T)
- No indels, no-calls, or ambiguous genotypes
- VCF: only biallelic SNPs, only the first sample

### VCF rsID Resolution

Whole-genome sequencing VCFs (like Dante Labs) often use `"."` instead of rsIDs for variant identifiers. When this happens, the parser looks up rsIDs from our SNP database using chromosome + position, matching ~1.2M out of ~3.7M variants in a typical WGS file.

### Chip Detection

Variant count is used to guess the genotyping platform:

| Variant Count | Platform |
|--------------|----------|
| 3M – 100M | Whole Genome Sequencing |
| 900K – 1.1M | 23andMe v5 |
| 600K – 900K | 23andMe v4 |
| 500K – 600K | 23andMe v3 |
| 300K – 500K | AncestryDNA v2 |
| 100K – 300K | AncestryDNA v1 |

---

## 2. Polygenic Risk Scoring

**Code:** `app/services/scorer.py`

### Step 1: Compute Dosage

For each variant in a PRS, count how many copies of the **effect allele** the user carries:

```
dosage = (allele1 == effect_allele) + (allele2 == effect_allele)
```

This gives 0, 1, or 2. For example, if the effect allele is "C" and you're genotype "CT", your dosage is 1.

### Step 2: Compute Raw Score

The raw PRS is a simple weighted sum:

```
Raw Score = Σ (dosage_i × weight_i)
```

where `weight_i` is the published effect size for each variant. This is essentially a dot product between your genotype vector and the weight vector, computed efficiently with Polars.

### Step 3: Compute Percentile

A raw score of, say, 13.85 means nothing on its own. We need to compare it to a reference population. The scorer computes a **z-score** and converts to a percentile using the normal CDF:

```
z = (raw_score - population_mean) / population_std
percentile = Φ(z) × 100
```

where `Φ(z) = 0.5 × (1 + erf(z / √2))` is the cumulative normal distribution function.

A percentile of 72 means your score is higher than 72% of the reference population.

### Step 4: Confidence Interval

Not all variants in a PRS will be present in your genotype file (especially for microarray data). Missing variants introduce uncertainty. The scorer estimates a **95% confidence interval**:

1. Compute average per-variant variance from matched variants
2. Extrapolate total variance from missing variants
3. Compute CI: `[score ± 1.96 × √(variance_from_missing)]`
4. Convert CI bounds to percentile space

Coverage quality is classified as:
- **High:** ≥80% of PRS variants matched
- **Medium:** 50–80% matched
- **Low:** <50% matched

---

## Ancestry Estimation & Mixture Normalization

Gene Wizard auto-detects genetic ancestry using a naive Bayes classifier on ~500 ancestry-informative markers, then uses the detected proportions to compute a weighted mixture of reference distributions for PRS normalization. This eliminates the need for users to manually select their ancestry group and provides more accurate percentiles for admixed individuals.

**See [ANCESTRY_ESTIMATION.md](ANCESTRY_ESTIMATION.md) for full technical details.**

---

## Reference Distributions — The Hardest Part

Getting meaningful percentiles requires knowing what "normal" looks like. This is the most technically challenging part of the system.

### The Problem

PRS raw scores vary enormously depending on:
1. **Which variants matched** — a microarray might match 40 out of 77 variants for a small PRS, or 494K out of 1.7M for a genome-wide PRS
2. **Which population** — allele frequencies differ between ancestries, so the same raw score means different things for different populations
3. **The PRS itself** — each score has a different scale (some range from 0–2, others from 0–30)

You can't just use a single pre-computed mean/std, because different users will match different subsets of variants. If user A matches 40/77 variants and user B matches 60/77, their raw scores aren't directly comparable — you need a reference distribution computed from the *same* 40 or 60 variants.

### The Solution: Matched-Variant Reference Distributions

We store **per-variant allele frequencies** from 1000 Genomes Phase 3 for five superpopulations (EUR, AFR, EAS, SAS, AMR). At scoring time, the scorer computes a reference distribution **dynamically** from only the variants that matched the user's genotype.

Under Hardy-Weinberg Equilibrium, the expected PRS distribution is:

```
Mean = Σ 2 × p_i × w_i
Variance = Σ 2 × p_i × (1 - p_i) × w_i²
Std = √Variance
```

where:
- `p_i` = effect allele frequency for variant i in the reference population
- `w_i` = PRS weight for variant i
- The sum is over **only matched variants** (those present in both the PRS and the user's genotype)

This is elegant because:
- It adapts to whatever subset of variants the user has
- It's fast (just arithmetic over arrays, no simulation needed)
- It's mathematically exact under HWE assumptions
- It works for any chip type or WGS

### Where Allele Frequencies Come From

**For small PRS (≤5,000 variants):** Fetched from the Ensembl REST API, which provides 1000 Genomes Phase 3 per-superpopulation frequencies.

**For genome-wide PRS (>5,000 variants):** Extracted from the 1000 Genomes Phase 3 whole-genome sites VCF (~1.4GB compressed, 85M variant lines). Our script (`scripts/load_1kg_frequencies.py`) stream-parses this file and matches by chromosome:position (the VCF uses "." for rsIDs). With Intel SIMD-accelerated decompression (`isal`), this takes ~46 seconds for 3.5M target positions.

The allele frequencies are stored per-variant in the `prs_variant_weights` table (columns: `eur_af`, `afr_af`, `eas_af`, `sas_af`, `amr_af`) so they only need to be loaded once.

---

## Data Sources

### PGS Catalog (pgscatalog.org)

The PRS weights come from the **PGS Catalog**, a public database of published polygenic scores. Each score has:
- A unique ID (e.g., PGS000001)
- A trait it predicts (e.g., coronary artery disease)
- A list of variants with effect alleles and weights
- Metadata: publication, development ancestry, reported AUC

We import scores using `scripts/ingest_pgs.py`, which:
1. Fetches metadata from the PGS Catalog REST API
2. Downloads harmonized scoring files (GRCh37 coordinates preferred)
3. Normalizes column names (the format varies across scores)
4. Loads weights into the database

**Currently imported scores:**

| PGS ID | Trait | Variants |
|--------|-------|----------|
| PGS000001 | Coronary Artery Disease | 77 |
| PGS000002 | Breast Cancer | 77 |
| PGS000003 | Type 2 Diabetes | 77 |
| PGS000018 | Atrial Fibrillation | 1,745,017 |
| PGS000039 | Alzheimer's Disease | 3,225,164 |

### 1000 Genomes Phase 3

Per-superpopulation allele frequencies for reference distribution computation. Five superpopulations:

| Code | Population | Description |
|------|-----------|-------------|
| EUR | European | CEU, FIN, GBR, IBS, TSI |
| AFR | African | ASW, ACB, ESN, GWD, LWK, MSL, YRI |
| EAS | East Asian | CDX, CHB, CHS, JPT, KHV |
| SAS | South Asian | BEB, GIH, ITU, PJL, STU |
| AMR | American/Latino | CLM, MXL, PEL, PUR |

### SNP-Trait Associations

Individual variant-trait links from published GWAS studies. (This database is currently being populated.)

---

## Database Schema

### Knowledge Base (Public)

```
snps                        Per-variant metadata
├── rsid (PK)               e.g., "rs429358"
├── chrom, position          Genomic coordinates
├── gene                     Gene name (nullable)
├── functional_class         missense, intronic, etc.
└── maf_global              Minor allele frequency

snp_trait_associations       SNP → trait links
├── rsid (FK → snps)
├── trait                    e.g., "Alzheimer's Disease"
├── risk_allele, odds_ratio  Effect size
├── evidence_level           high/medium/low
└── source_pmid              PubMed reference

prs_scores                   Published polygenic scores
├── pgs_id (PK)              e.g., "PGS000001"
├── trait_name               What it predicts
├── n_variants_total         How many variants
└── reported_auc             Published accuracy

prs_variant_weights          Individual weights
├── pgs_id, rsid             Which variant in which score
├── effect_allele, weight    The weight
└── eur_af, afr_af, ...      Per-population allele frequencies

prs_reference_distributions  Population reference stats
├── pgs_id, ancestry_group   Which score + population
└── mean, std                For percentile computation
```

### User Data

```
analyses                     Upload/analysis tracking
├── user_id                  Clerk user ID (no User table)
├── status                   pending → parsing → scoring → done/failed
├── chip_type                Detected platform
└── variant_count            After filtering

prs_results                  Computed PRS per user
├── user_id, analysis_id
├── raw_score, percentile    The results
├── z_score, ref_mean, ref_std
├── n_variants_matched/total Coverage info
└── coverage_quality         high/medium/low

user_snp_trait_hits          Trait matches
├── user_id, analysis_id
├── rsid, user_genotype      What they carry
├── trait, risk_level         increased/moderate/typical
└── evidence_level           high/medium/low
```

---

## Privacy & Security

- **The file uploaded is never stored, but results are.** Uploaded files are streamed to a temp file, parsed into memory, and the temp file is deleted immediately after parsing. If the analysis crashes, the temp file is still deleted (guaranteed by try/finally).
- **No User table.** Authentication is handled by Clerk. We only store a Clerk user ID string on each result record — no emails, names, or passwords.
- **Results are user-scoped.** Every API endpoint verifies the authenticated user matches the data owner.
- **Temp files are restricted.** Created with mode `0o600` (owner read/write only).
- **Upload limits.** Max 2GB file size, max 3 uploads per user per hour.

---

## Frontend Visualization

### PRS Distribution Chart

Each PRS result is displayed as an interactive bell curve showing:

1. **The reference distribution** — a normal curve with mean and std from the matched-variant computation
2. **Your position** — a vertical line and marker showing where your score falls
3. **Color gradient** — green (below average) → gray (average) → red (above average)
4. **Percentile label** — e.g., "72nd percentile"
5. **Confidence interval** — shaded band showing the likely range given missing variants
6. **Coverage info** — how many variants matched and the quality classification
7. **Ancestry reference** — which population was used for comparison

### Risk Categories

| Percentile | Category | Color |
|-----------|----------|-------|
| ≥ 90th | High | Red |
| ≥ 75th | Elevated | Orange |
| 25th – 75th | Average | Gray |
| < 25th | Below Average | Green |

### Trait Association Table

A filterable table showing:
- rsID (links to public SNP detail page)
- Trait name
- Your genotype (e.g., "AG")
- Risk level (increased / moderate / typical)
- Evidence level (high / medium / low)

Filters available for risk level and evidence level.

---

## Architecture Summary

```
┌─────────────┐     ┌──────────────┐     ┌──────────────┐
│  Next.js     │────▶│  FastAPI      │────▶│  PostgreSQL   │
│  Frontend    │◀────│  Backend      │◀────│  Database     │
│  (Vercel)    │     │  (Railway)    │     │  (Railway)    │
└─────────────┘     └──────────────┘     └──────────────┘
      │                    │
      │                    ├── Parser (Polars)
      │                    ├── Scorer (Polars + math)
      │                    ├── Trait Matcher (SQL)
      │                    └── Background Tasks (asyncio)
      │
      ├── Clerk Auth (JWT)
      ├── Recharts (Visualizations)
      └── TailwindCSS v4 (Styling)
```

**Tech stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), Polars, asyncpg, Next.js 16, TypeScript, TailwindCSS v4, Clerk, Recharts.

**No Redis or separate workers.** The analysis pipeline runs as an `asyncio.create_task()` on the same FastAPI process. CPU-heavy work (parsing, scoring) runs in thread pools via `asyncio.to_thread()`.
