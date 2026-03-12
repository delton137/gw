# Adding a New Polygenic Risk Score

This document describes the end-to-end process for adding a new PRS from the PGS Catalog to Gene Wizard.

## Prerequisites

- The score must exist in the [PGS Catalog](https://www.pgscatalog.org/) with harmonized GRCh37 (and ideally GRCh38) scoring files
- Local venv activated (`source .venv/bin/activate`)
- `DATABASE_URL` set (local or Railway prod)

## Step 1: Choose a Score

Browse the PGS Catalog. Prefer scores that:

- Have harmonized scoring files for GRCh37 (required) and GRCh38 (preferred)
- Were developed and validated in European ancestry (our primary reference panel is EUR)
- Have a published AUC/AUROC > 0.60
- Have a reasonable number of variants (< 5,000 for analytical reference distributions; genome-wide scores need empirical distributions)

Note the PGS ID (e.g., `PGS000001`).

## Step 2: Ingest from PGS Catalog

```bash
python -m scripts.ingest_pgs --pgs-id PGS000XXX
```

This downloads the harmonized scoring file(s), fetches metadata from the PGS Catalog REST API, and loads everything into the database:

- **`prs_scores`** — trait name, EFO ID, publication PMID, variant count, AUC
- **`prs_variant_weights`** — per-variant rsid, chrom, position (GRCh37 + GRCh38), effect allele, weight
- **`snps`** — upserts SNP records for any new rsids

To reimport a score (e.g., after a PGS Catalog update):

```bash
python -m scripts.ingest_pgs --pgs-id PGS000XXX --force
```

`--force` deletes the existing score, weights, reference distributions, and user results before reimporting.

## Step 3: Load 1000 Genomes Allele Frequencies

```bash
python -m scripts.load_1kg_frequencies
```

This automatically detects which PGS scores are missing allele frequency data and:

1. Downloads the 1000G Phase 3 whole-genome sites VCF (~1.4 GB, cached at `~/.cache/genewizard/1000g_sites.vcf.gz`)
2. Stream-parses it to extract per-superpopulation AFs (EUR, AFR, EAS, SAS, AMR)
3. Aligns AFs to the PRS effect allele (flips when effect_allele = VCF REF)
4. Sets the `effect_is_alt` flag on each variant
5. Computes analytical reference distributions (HWE mean/std per ancestry)

The script is idempotent — it skips PGS scores that already have ≥95% AF coverage.

## Step 4: Compute Reference Distributions

You have two options depending on the score size:

### Option A: Analytical (small scores, < ~5,000 variants)

Step 3 already computed these. If you need to recompute:

```bash
python -m scripts.compute_reference_dists --pgs-id PGS000XXX
```

This uses the HWE formula: `E[S] = Σ 2·p·w`, `Var[S] = Σ 2·p·(1-p)·w²`. Fast but assumes independence between variants (underestimates variance when variants are in LD).

### Option B: Empirical (genome-wide scores or for validated percentiles)

Score the HGDP+1kGP reference panel with PLINK2 and load the results:

```bash
# If you have pre-scored .sscore files:
python -m scripts.compute_empirical_ref_dists --sscore-dir /path/to/sscore/files/

# Or run PLINK2 from scratch (requires Docker + reference panel):
python -m scripts.compute_empirical_ref_dists --pgs-id PGS000XXX --ref-dir /path/to/ref
```

This stores sorted score arrays in `percentiles_json` for exact empirical percentile lookup at scoring time. The scorer prefers empirical percentiles when available, falling back to the analytical normal approximation.

**When to use empirical:** Genome-wide PGS (> ~5,000 variants) or any score where you want validated percentiles. The analytical formula can underestimate std by 2-3x for genome-wide scores due to LD.

## Step 5: Add Trait Metadata (for absolute risk)

If the trait is binary (a disease), add a prevalence entry in `scripts/populate_trait_metadata.py`:

```python
TRAIT_METADATA = {
    # ...existing entries...
    "PGS000XXX": {
        "trait_type": "binary",
        "prevalence": 0.05,  # lifetime risk or point prevalence
        "source": "https://doi.org/...",
    },
}
```

Then run:

```bash
python -m scripts.populate_trait_metadata
```

This enables the liability threshold model to convert PRS z-scores into absolute disease probabilities on the frontend.

Skip this step for continuous traits (e.g., height, BMI) — they display as percentiles only.

## Step 6: Verify

1. **Check the database:**

```sql
-- Score metadata
SELECT pgs_id, trait_name, n_variants_total, reported_auc FROM prs_scores WHERE pgs_id = 'PGS000XXX';

-- AF coverage
SELECT COUNT(*) AS total, COUNT(eur_af) AS with_af FROM prs_variant_weights WHERE pgs_id = 'PGS000XXX';

-- Reference distributions
SELECT ancestry_group, mean, std, percentiles_json IS NOT NULL AS has_empirical
FROM prs_reference_distributions WHERE pgs_id = 'PGS000XXX';

-- Trait metadata (if binary)
SELECT * FROM prs_trait_metadata WHERE pgs_id = 'PGS000XXX';
```

2. **Test with a real file:** Upload a genotype file and check that the new PRS appears on the `/prs` page with a reasonable percentile.

3. **Sanity check:** The scorer logs a warning if a score is > 5σ from the reference mean. If you see this, the scoring file or reference distribution is likely wrong.

## Quick Reference

| Step | Script | What it does |
|------|--------|-------------|
| 2 | `ingest_pgs --pgs-id X` | Download scoring file, load weights |
| 3 | `load_1kg_frequencies` | Load 1000G AFs, compute analytical ref dists |
| 4 | `compute_empirical_ref_dists` | (Optional) Empirical ref dists from PLINK2 |
| 5 | `populate_trait_metadata` | (Optional) Add prevalence for absolute risk |

## Troubleshooting

- **"already imported, skipping"** — Use `--force` to reimport
- **Impossible scores (e.g., 40σ from mean)** — Stale scoring file. Reimport with `--force`, then rerun `load_1kg_frequencies`
- **Analytical std seems too small** — Expected for genome-wide PGS. Use empirical distributions
- **Missing GRCh38 positions** — Some older PGS Catalog entries lack GRCh38 harmonized files. GRCh37 positions are sufficient for scoring (VCF and 1000G data are GRCh37). GRCh38 positions are used for matching against GRCh38 VCFs only
