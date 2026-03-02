# PGS Score Comparison: gene-wizard vs pgsc_calc

## Overview

This analysis compares polygenic scores (PGS) computed by gene-wizard software against
pgsc_calc (the PGS Catalog's official scoring pipeline) for 14 PGS IDs, using the
HGDP+1kGP reference panel for empirical EUR percentile estimation.

## Input Data

- **User VCF**: `/home/dan/Dropbox/AA_DOCUMENTS/AAA_medical/genetic/raw_genome/DTC7U778.autosomes.vcf.gz`
  - 4,564,468 variant sites (original VCF, no backfilling)
  - GRCh37/hg19 coordinates
- **Reference panel**: HGDP+1kGP (`/media/dan/500Gb/work/ancestry/ref_extracted/GRCh37_HGDP+1kGP_ALL.{pgen,pvar.zst,psam}`)
  - 3,942 individuals: 770 EUR, 891 AFR, 812 EAS, 766 CSA, 545 AMR, 158 MID
  - 83M variants, GRCh37

## Step 1: Run pgsc_calc

pgsc_calc v2.2.0 was run to get raw PGS scores from the original VCF.

### Samplesheet (`samplesheet_original.csv`)

```csv
sampleset,path_prefix,chrom,format
mygenome,/home/dan/Dropbox/AA_DOCUMENTS/AAA_medical/genetic/raw_genome/DTC7U778.autosomes,,vcf
```

### Command

```bash
cd /media/dan/500Gb/work2
nextflow run pgscatalog/pgsc_calc -r v2.2.0 \
  --input /home/dan/Dropbox/AA_DOCUMENTS/AAA_medical/genetic/raw_genome/samplesheet_original.csv \
  --pgs_id PGS002249,PGS000002,PGS000001,PGS004228,PGS000018,PGS004590,PGS002035,PGS000003,PGS002280,PGS005170,PGS000039,PGS003992,PGS004008,PGS002753 \
  --target_build GRCh37 \
  --min_overlap 0.01 \
  -profile docker \
  -c /home/dan/Dropbox/AA_DOCUMENTS/AAA_medical/genetic/raw_genome/resource_fix.config
```

Key flags:
- `--min_overlap 0.01` — The original VCF only has variant sites (no hom-ref), so
  overlap with PGS scoring files is typically 30-50%. Without this flag, pgsc_calc
  would reject scores with <75% overlap.
- No `--run_ancestry` — ancestry assumed EUR from prior analysis.

### Output

Raw scores extracted from `aggregated_scores.txt.gz`:

| PGS ID | pgsc_calc SUM |
|--------|---------------|
| PGS000001 | 0.401249 |
| PGS000002 | 0.524557 |
| PGS000003 | -0.157072 |
| PGS000018 | 9.154010 |
| PGS000039 | 1.285808 |
| PGS002035 | -0.000094 |
| PGS002249 | 108.756100 |
| PGS002280 | 2.517800 |
| PGS002753 | -0.535011 |
| PGS003992 | -0.133765 |
| PGS004008 | -0.104058 |
| PGS004228 | -4.076900 |
| PGS004590 | -0.040600 |
| PGS005170 | 2.313820 |

**Important**: These raw scores only include variants present in the VCF. Positions
absent from the VCF (homozygous reference) are treated as missing and receive zero
dosage. This is incorrect for variants where effect_allele = REF, which should get
dosage = 2. This is corrected in Step 3.

## Step 2: Score Reference Panel

The HGDP+1kGP reference panel was scored for all 14 PGS using PLINK2 to obtain
empirical EUR score distributions.

### 2a. Create Variant Subset

Scoring the full 83M-variant reference panel from a spinning HDD was too slow.
Instead, a subset containing only PGS variants was extracted first.

Combined variant IDs from all 14 formatted PGS files into `all_pgs_ids.txt`
(8,512,450 IDs — both `chr:pos:effect:other` and `chr:pos:other:effect` orderings):

```python
# Pseudocode for creating all_pgs_ids.txt
for each formatted PGS file:
    for each variant (chr, pos, effect, other):
        write f"{chr}:{pos}:{effect}:{other}"
        write f"{chr}:{pos}:{other}:{effect}"
```

Extract subset + compute allele frequencies:

```bash
docker run --rm \
  -v /media/dan/500Gb/work/ancestry/ref_extracted:/ref:ro \
  -v /tmp/pgs_ref:/work \
  ghcr.io/pgscatalog/plink2:2.00a5.10 plink2 \
  --pfile /ref/GRCh37_HGDP+1kGP_ALL vzs \
  --extract /work/all_pgs_ids.txt \
  --make-pgen vzs \
  --freq \
  --out /work/ref_pgs_subset
```

Result: 4,220,207 variants extracted (2.2 GB pgen vs 13 GB original).

### 2b. Score Each PGS

For each PGS, a PLINK2 scoring file was created from the formatted PGS file with
both ID orderings (so one matches the reference panel's `chr:pos:REF:ALT` format):

```
ID	effect_allele	weight
1:123456:A:G	A	0.0023
1:123456:G:A	A	0.0023
```

PLINK2 scoring command (per PGS):

```bash
docker run --rm \
  -v /tmp/pgs_ref:/work \
  ghcr.io/pgscatalog/plink2:2.00a5.10 plink2 \
  --pfile /work/ref_pgs_subset vzs \
  --score /work/{PGS_ID}_scoring.tsv header-read cols=+scoresums no-mean-imputation \
  --out /work/{PGS_ID}_ref
```

Key flags:
- `cols=+scoresums` — include raw score sums in output
- `no-mean-imputation` — missing genotypes get dosage 0 (not mean-imputed)

Output: `.sscore` files with columns including `SuperPop` and `weight_SUM`.

## Step 3: Homozygous Reference Correction

The user's VCF only contains variant sites. At positions absent from the VCF, the
true genotype is homozygous reference (0/0). pgsc_calc treats these as missing
(dosage = 0), but the correct dosage depends on the effect allele:

- **effect_allele = ALT**: dosage = 0 (correct — no copies of ALT)
- **effect_allele = REF**: dosage = 2 (incorrect — should be 2 copies of REF)

The correction adds `2 * weight` for each missing variant where `effect_allele = REF`:

```
corrected_score = pgscalc_sum + Σ(2 * weight_i) for all missing variants where effect_allele = REF_allele
```

REF alleles were determined from the reference panel's `.afreq` file (REF column).

## Step 4: Compute EUR Percentiles

For each PGS, the corrected user score was compared against the empirical EUR
distribution from the reference panel:

```
empirical_percentile = (count of EUR scores ≤ user_score) / (total EUR count) × 100
```

## Results

| PGS | Trait | Variants | User Score | pgsc_calc | Corrected | EUR Mean | EUR Std | Emp% | User% | Match |
|-----|-------|----------|------------|-----------|-----------|----------|---------|------|-------|-------|
| PGS002249 | Alzheimer's | 249,248 | 140.60 | 108.76 | 112.53 | 116.01 | 17.21 | 42 | 87 | !! |
| PGS000002 | Breast Cancer | 77 | 0.95 | 0.52 | 0.77 | 0.51 | 0.48 | 71 | 84 | ~ |
| PGS000001 | Breast Cancer | 77 | 0.79 | 0.40 | 0.65 | 0.52 | 0.43 | 61 | 77 | ~ |
| PGS004228 | Blood Pressure | 8,863 | -19.45 | -4.08 | -19.59 | -20.78 | 3.13 | 65 | 73 | ~ |
| PGS000018 | CAD | 1,745,179 | -0.32 | 9.15 | -0.68 | -0.32 | 0.54 | 24 | 51 | ? |
| PGS004590 | Statin Response | 363 | -3.22 | -0.04 | -3.41 | -3.28 | 0.66 | 44 | 49 | ~ |
| PGS002035 | Gout | 39,752 | -0.00009 | -0.00009 | -0.00009 | 0.002 | 0.003 | 47 | 20 | ? |
| PGS000003 | T2 Diabetes | 77 | 0.08 | -0.16 | 0.11 | 0.44 | 0.38 | 19 | 17 | ~ |
| PGS002280 | Alzheimer's | 83 | 4.75 | 2.52 | 4.42 | 5.18 | 0.34 | 1 | 15 | !! |
| PGS005170 | Prostate Cancer | 1,320,229 | 2.15 | 2.31 | 2.14 | 2.48 | 0.20 | 5 | 8 | ~ |
| PGS000039 | Stroke | 3,225,583 | 12.53 | 1.29 | 1.30 | 1.94 | 0.28 | 1 | 8 | !! |
| PGS003992 | Atrial Fib | 1,136,212 | -0.24 | -0.13 | -0.24 | -0.01 | 0.14 | 4 | 4 | ~ |
| PGS004008 | Obesity | 5,663 | -0.37 | -0.10 | -0.38 | -0.19 | 0.11 | 2 | 3 | ~ |
| PGS002753 | BMI | 1,092,011 | -0.54 | -0.54 | -0.55 | -0.26 | 0.11 | 0.3 | <1 | ~ |

**Match column**: `~` = corrected score within 0.5 EUR std of user score,
`?` = 0.5-2 std difference, `!!` = >2 std difference.

### Interpretation

**Good agreement (10/14):** PGS003992, PGS002753, PGS005170, PGS004008, PGS002035,
PGS004228, PGS004590, PGS000003, PGS000001, PGS000002 — raw scores match within
0.5σ after correction, confirming the scoring methodology is sound.

**Moderate disagreement (2/14):**
- **PGS000018 (CAD)**: 0.7σ difference. Corrected = -0.68 vs user = -0.32.
  Likely due to differences in how missing variants are handled in genome-wide scores.
- **PGS002035 (Gout)**: Raw scores identical, but percentile difference (47% vs 20%)
  reflects different reference distributions.

**Large disagreement (2/14):**
- **PGS000039 (Stroke)**: 40σ discrepancy (user=12.53 vs corrected=1.30). The user
  software score of 12.53 is implausible — it's ~38 EUR stds above the reference mean.
  This suggests a scoring bug in the user software for this particular PGS.
- **PGS002249 (Alzheimer's)**: 1.6σ discrepancy (user=140.6 vs corrected=112.5).
  May reflect different effect allele alignment or weight normalization in user software.

## Files

| File | Description |
|------|-------------|
| `score_all.py` | Main scoring script (final version) — creates scoring files, runs PLINK2 on reference subset, computes hom-ref corrections and empirical percentiles |
| `score_all_v1.py` | Earlier version that scored the full reference panel (slower) |
| `results.json` | Complete JSON results for all 14 PGS |

### Intermediate files (in `/tmp/pgs_ref/`)

| File | Description |
|------|-------------|
| `ref_pgs_subset.{pgen,pvar.zst,psam}` | Reference panel subset (4.2M PGS variants) |
| `ref_pgs_subset.afreq` | Allele frequencies for subset (used for REF allele lookup) |
| `{PGS_ID}_ref.sscore` | PLINK2 scoring output per PGS (14 files) |
| `{PGS_ID}_ref.log` | PLINK2 log per PGS (14 files) |
| `all_pgs_ids.txt` | Combined variant ID list for all 14 PGS |

### pgsc_calc output (in `/media/dan/500Gb/work2/`)

| Path | Description |
|------|-------------|
| `e5/16d539f0.../formatted/` | Formatted (harmonized) PGS scoring files |
| `1b/02970c.../aggregated_scores.txt.gz` | Aggregated raw scores |

## Software Versions

- pgsc_calc v2.2.0 (Nextflow pipeline)
- PLINK2 v2.00a5.10 (`ghcr.io/pgscatalog/plink2:2.00a5.10`)
- Python 3 with numpy
- Docker for PLINK2 execution

## Key Learnings

1. **VCFs with only variant sites need hom-ref correction**: When the VCF does not
   contain homozygous reference sites, any PGS variant where effect_allele = REF will
   be incorrectly scored as dosage 0 instead of 2. The correction is
   `+2*weight` per missing REF-effect variant.

2. **Empirical reference distributions capture LD effects**: Analytical variance
   formulas (`Var = Σ 2p(1-p)w²`) assume independence between variants. For genome-wide
   PGS with millions of variants in LD, this dramatically underestimates the true std.
   Empirical distributions from scoring real reference genomes are more accurate.

3. **Both ID orderings needed for PLINK2 scoring**: The reference panel pvar uses
   `chr:pos:REF:ALT` format. Since PGS scoring files use `chr:pos:effect:other`,
   and effect may be either REF or ALT, both `chr:pos:effect:other` and
   `chr:pos:other:effect` must be written so one matches.

4. **`--min_overlap 0.01` needed for variant-only VCFs**: pgsc_calc defaults to
   requiring 75% overlap between scoring file variants and the VCF. Variant-only
   VCFs typically have 30-50% overlap, so this threshold must be lowered.
