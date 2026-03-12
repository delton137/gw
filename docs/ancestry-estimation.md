# Ancestry Estimation — Technical Documentation

## Overview

Gene Wizard estimates genetic ancestry using Maximum Likelihood Estimation (MLE)
on 128,097 ancestry-informative loci (AILs) from the 1000 Genomes Phase 3 project.
This provides admixture fractions across 26 fine-grained populations, which are
aggregated into 5 continental superpopulations.

The algorithm is a reimplementation of AEon (Warren & Pinese 2024), adapted from
PyTorch/Pyro to scipy for lightweight deployment. The core probabilistic model
is identical.

## Algorithm

### Probabilistic Model

The model assumes an individual is a mixture of K=26 reference populations.
At each locus j, the individual's allele frequency is a weighted average:

    r_j = Σ_k (p_k × AF_kj)

where:
- `p_k` is the fraction of the individual's ancestry from population k
- `AF_kj` is the allele frequency of the ALT allele in population k at locus j
- `r_j` is the resulting per-locus mixture allele frequency

Given `r_j`, the genotype probability follows Hardy-Weinberg equilibrium:

    P(dosage=0) = (1 - r_j)²      # homozygous reference
    P(dosage=1) = 2 × r_j × (1 - r_j)  # heterozygous
    P(dosage=2) = r_j²             # homozygous alternate

The likelihood of the full genotype vector is the product across all loci:

    L(p) = Π_j P(dosage_j | r_j)

This is the standard binomial mixture model for global ancestry estimation,
where each individual's genotype is modeled as arising from a mixture of
reference population allele frequencies under HWE assumptions.

### Optimization

We maximize the log-likelihood (equivalently minimize the negative log-likelihood):

    -ℓ(p) = -Σ_j log P(dosage_j | r_j)

subject to the simplex constraint:
- p_k ≥ 0 for all k
- Σ_k p_k = 1

This is solved using scipy's Sequential Least Squares Programming (SLSQP) optimizer:
- Initial guess: uniform (1/26 for each population)
- Bounds: [0, 1] per population
- Equality constraint: sum to 1
- Tolerance: 1e-10
- Max iterations: 1000

The original AEon implementation uses Pyro's SVI (Stochastic Variational Inference)
with a PyTorch backend. Our reimplementation uses scipy.optimize.minimize with SLSQP,
which produces equivalent results for this convex optimization problem with no
stochastic components.

### Key Properties

1. **Admixture-aware**: MLE naturally produces mixture fractions. A half-European,
   half-African individual gets ~0.50/0.50, not a forced single-population
   classification.

2. **All loci contribute equally**: No weighting by informativeness. With 128K
   markers, the law of large numbers ensures stable estimates even with some
   noise.

3. **Position-based matching**: Primary matching is by chromosome+position
   (GRCh38), with rsid-based fallback for older DTC files on GRCh37.

4. **Converges fast**: Typical optimization completes in <1 second for 10K–50K
   matched markers (SLSQP is efficient for simplex-constrained problems).

## Reference Data

### Source

The reference allele frequencies come from the 1000 Genomes Phase 3 project
(2,504 unrelated individuals from 26 populations). The original AIL panel was
curated by AEon from a set of 133,872 LD-pruned variants originally derived
by Pinese et al. (2020) for the Medical Genome Reference Bank (MGRB). Variants
that became reference in GRCh38 and variants with missing genotypes in any of
the 2,504 reference samples were excluded, yielding the final 128,097-marker panel.

The allele frequency data was processed by the AEon package
(`existing_tools/aeon/aeon_ancestry/refs/g1k_allele_freqs.txt`):
- 128,097 ancestry-informative loci
- Allele frequencies for 26 populations (calculated from 1000G 30x GRCh38 data)
- Variant IDs in `chr_pos_ref_alt` format (e.g., `chr1_898818_T_C`)

### Build Script

The one-time build script (`scripts/build_aeon_reference.py`) reads the Aeon
allele frequency file, parses variant IDs into chrom/position/ref/alt, and
outputs `app/data/aeon_reference.parquet`. This takes a few seconds.

Optionally, rsids can be resolved via MyVariant.info (Xin et al. 2016) by
passing `--with-rsids` (takes ~30 min for 129 batch API calls with hg38 assembly).
rsid resolution is not required — the primary matching strategy uses
chromosome+position.

### Reference Parquet Schema

| Column    | Type    | Description                          |
|-----------|---------|--------------------------------------|
| rsid      | String  | dbSNP rsid (nullable if unmapped)    |
| var_id    | String  | Original Aeon ID (chr_pos_ref_alt)   |
| chrom     | String  | Chromosome (no "chr" prefix)         |
| position  | Int64   | GRCh38 1-based position              |
| ref       | String  | Reference allele                     |
| alt       | String  | Alternate allele                     |
| ACB..YRI  | Float32 | ALT allele frequency per population  |

File size: ~6 MB (Parquet compressed, vs 63 MB raw text).

### 26 Reference Populations

From the 1000 Genomes Phase 3 project (1000 Genomes Project Consortium 2015):

| Code | Population                             | Superpopulation |
|------|----------------------------------------|-----------------|
| ACB  | African Caribbean in Barbados          | AFR             |
| ASW  | African Ancestry in SW USA             | AFR             |
| BEB  | Bengali in Bangladesh                  | SAS             |
| CDX  | Chinese Dai in Xishuangbanna           | EAS             |
| CEU  | Utah Residents (N/W European)          | EUR             |
| CHB  | Han Chinese in Beijing                 | EAS             |
| CHS  | Han Chinese South                      | EAS             |
| CLM  | Colombian in Medellin                  | AMR             |
| ESN  | Esan in Nigeria                        | AFR             |
| FIN  | Finnish in Finland                     | EUR             |
| GBR  | British from England and Scotland      | EUR             |
| GIH  | Gujarati Indians in Houston            | SAS             |
| GWD  | Gambian in Western Division            | AFR             |
| IBS  | Iberian Populations in Spain           | EUR             |
| ITU  | Indian Telugu in the UK                | SAS             |
| JPT  | Japanese in Tokyo                      | EAS             |
| KHV  | Kinh in Ho Chi Minh City               | EAS             |
| LWK  | Luhya in Webuye, Kenya                 | AFR             |
| MSL  | Mende in Sierra Leone                  | AFR             |
| MXL  | Mexican Ancestry in Los Angeles        | AMR             |
| PEL  | Peruvian in Lima                       | AMR             |
| PJL  | Punjabi in Lahore                      | SAS             |
| PUR  | Puerto Rican in Puerto Rico            | AMR             |
| STU  | Sri Lankan Tamil in the UK             | SAS             |
| TSI  | Toscani in Italia                      | EUR             |
| YRI  | Yoruba in Ibadan, Nigeria              | AFR             |

### 5 Superpopulations

| Code | Name              | Color (frontend) |
|------|-------------------|------------------|
| AFR  | African           | #10b981 emerald  |
| EUR  | European          | #f59e0b amber    |
| EAS  | East Asian        | #8b5cf6 violet   |
| SAS  | South Asian       | #f43f5e rose     |
| AMR  | Americas/Admixed  | #0ea5e9 sky      |

## Pipeline Integration

### Flow

1. User uploads genotype file → parse into Polars DataFrame
2. Fast matching phase (traits, PGx, carrier, blood type, HLA) → commit → status: `done`
3. Background: `estimate_ancestry(user_df)` runs via `asyncio.to_thread`
4. If successful → store result in `analysis.detected_ancestry` (JSON column)
5. Set `analysis.ancestry_method = "aeon_mle"`, `analysis.ancestry_confidence = <max superpop fraction>`

### Genotype Matching

1. **Primary: position join** — Join user (chrom, position) against reference
   (chrom, position) with normalized chromosome names (strip "chr" prefix).
   Works for GRCh38 VCFs and many DTC files.
2. **Fallback: rsid join** — If position match yields < 500 markers, try
   matching by rsid (build-independent). Requires rsids in the reference
   (populated via `--with-rsids` flag during build).

### Dosage Conversion

For each matched variant, convert the diploid genotype to ALT allele dosage:
- Both alleles match REF → dosage 0 (homozygous reference)
- One allele matches ALT → dosage 1 (heterozygous)
- Both alleles match ALT → dosage 2 (homozygous alternate)
- Unknown alleles → treated as REF (conservative)

### Typical Match Counts

| File Type        | Typical Matches | Coverage    |
|------------------|-----------------|-------------|
| 23andMe v5       | 40,000–60,000   | 30–45%      |
| AncestryDNA v2   | 35,000–50,000   | 27–39%      |
| WGS VCF          | 100,000+        | 80–100%     |
| Old 23andMe v3   | 20,000–35,000   | 15–27%      |

Minimum threshold: 500 markers (very conservative — estimates are reliable with 5K+).

### Coverage Quality Rating

| Rating | Marker Coverage | Typical File Type    |
|--------|-----------------|----------------------|
| High   | ≥ 20%           | Most DTC, all WGS    |
| Medium | 5–20%           | Older DTC chips      |
| Low    | < 5%            | Rare, near threshold |

### Result Storage

The `analysis.detected_ancestry` JSON column stores:

```json
{
  "populations": {"CEU": 0.42, "GBR": 0.35, "IBS": 0.08, "FIN": 0.05, ...},
  "superpopulations": {"EUR": 0.92, "AFR": 0.03, "EAS": 0.02, "SAS": 0.02, "AMR": 0.01},
  "n_markers_used": 45000,
  "n_markers_total": 128097,
  "coverage_quality": "high",
  "is_admixed": false
}
```

Additional analysis columns:
- `ancestry_method`: `"aeon_mle"` (or `"computed_failed"` on failure)
- `ancestry_confidence`: max superpopulation fraction (0–1)
- `selected_ancestry`: user's manual override (for PRS normalization)

## Frontend

### /ancestry Page

Full ancestry breakdown with:
1. Summary card — best superpopulation + confidence + admixed flag
2. Donut chart — 5 superpopulation segments (Recharts PieChart)
3. Population table — 26 populations grouped by superpopulation, sorted by fraction
4. Coverage metrics — markers matched vs total
5. Interpretation guide — what the numbers mean, significance thresholds
6. Disclaimer — genetic ancestry ≠ ethnic/cultural identity

### Dashboard Card

Compact ancestry summary on the main dashboard:
- Colored progress bars for each superpopulation
- Marker count
- Link to full /ancestry page

## Configuration

Key constants in `app/services/ancestry_estimator.py`:

| Constant            | Value | Purpose                                  |
|---------------------|-------|------------------------------------------|
| MIN_MARKERS         | 500   | Minimum matched markers for estimation   |
| ADMIXED_THRESHOLD   | 0.80  | Below this → flagged as admixed          |
| SLSQP ftol          | 1e-10 | Optimizer convergence tolerance          |
| SLSQP maxiter       | 1000  | Max optimization iterations              |
| Clip epsilon        | 1e-10 | Prevents log(0) in likelihood            |

## Files

| Path                                  | Purpose                              |
|---------------------------------------|--------------------------------------|
| `app/services/ancestry_estimator.py`  | Core MLE estimator                   |
| `app/data/aeon_reference.parquet`     | 128K AIL reference (build artifact)  |
| `app/data/pop_to_superpop.json`       | 26-pop → 5-superpop mapping         |
| `app/data/population_names.json`      | Human-readable population names      |
| `scripts/build_aeon_reference.py`     | One-time rsid mapping builder        |
| `frontend/src/app/ancestry/page.tsx`  | Full ancestry page                   |
| `tests/test_ancestry_estimator.py`    | 18 unit/integration tests            |

## How to Rebuild Reference Data

If the reference needs rebuilding (e.g., new rsid mappings):

```bash
source .venv/bin/activate
python -m scripts.build_aeon_reference
```

Without `--with-rsids`, this completes in a few seconds. With `--with-rsids`,
it takes ~30 minutes (129 batch API calls to MyVariant.info). The script is
idempotent and can be re-run safely.

6. Revert dashboard card changes in `frontend/src/app/dashboard/page.tsx`
7. Revert test changes in `tests/test_analysis_pipeline.py`

## References

1. **Warren NM, Pinese M.** AEon: A global genetic ancestry estimation tool.
   *bioRxiv* 2024.06.18.599246 (2024).
   https://doi.org/10.1101/2024.06.18.599246
   — Source algorithm and 128K AIL reference panel.

2. **1000 Genomes Project Consortium.** A global reference for human genetic variation.
   *Nature* 526, 68–74 (2015).
   https://doi.org/10.1038/nature15393
   — Reference population data (2,504 individuals, 26 populations, GRCh38 30x).

3. **Pinese M, Lacaze P, Rath EM, et al.** The Medical Genome Reference Bank
   contains whole genome and phenotype data of 2570 healthy elderly.
   *Nature Communications* 11, 435 (2020).
   https://doi.org/10.1038/s41467-019-14079-0
   — Original AIL panel curation methodology (133,872 LD-pruned variants).

4. **Xin J, Mark A, Afrasiabi C, et al.** High-performance web services for
   querying gene and variant annotation. *Genome Biology* 17, 91 (2016).
   https://doi.org/10.1186/s13059-016-0953-9
   — MyVariant.info API used for rsid mapping of GRCh38 positions.

5. **Kraft D.** A software package for sequential quadratic programming.
   *Tech. Rep. DFVLR-FB 88-28*, DLR German Aerospace Center (1988).
   — SLSQP optimizer used in scipy.optimize.minimize.

## License

The AEon package is licensed under the Apache License 2.0, which permits
commercial use, modification, and distribution. The 1000 Genomes Phase 3 data
is publicly available under the Fort Lauderdale agreement.
