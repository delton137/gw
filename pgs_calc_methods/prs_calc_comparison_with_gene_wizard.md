# PRS Score Comparison: Gene-Wizard vs pgsc_calc + Empirical EUR Reference

**Date:** 2026-03-02

**Methodology:**
- **pgsc_calc v2.2.0** scored user's original (non-backfilled) VCF against PGS Catalog harmonized files (GRCh37)
- **Hom-ref correction:** For variants missing from the VCF (user is homozygous reference), added 2×weight when effect_allele=REF in the reference genome
- **Reference panel:** HGDP+1kGP (770 EUR individuals), scored with PLINK2 using no-mean-imputation
- **Empirical percentile:** Fraction of EUR reference individuals scoring ≤ the user's corrected score

## Results

| PGS | Trait | Variants | GW Score | Corrected | EUR Mean | EUR Std | Emp% | GW% | Score Δ |
|-----|-------|----------|----------|-----------|----------|---------|------|-----|---------|
| PGS003992 | Alzheimer's disease | 1136K | -0.2424 | -0.2429 | -0.0127 | 0.1408 | 4.4% | 4% | ✓ exact |
| PGS002753 | Alzheimer's disease | 1092K | -0.5427 | -0.5450 | -0.2571 | 0.1118 | 0.3% | < 1 | ✓ exact |
| PGS005170 | All-cause dementia | 1320K | 2.1500 | 2.1425 | 2.4773 | 0.2032 | 5.3% | 8% | ✓ exact |
| PGS004008 | Alzheimer's disease | 6K | -0.3733 | -0.3763 | -0.1866 | 0.1116 | 1.8% | 3% | ✓ exact |
| PGS002035 | Dementia | 40K | -9.42e-05 | -9.42e-05 | 0.0019 | 0.0029 | 46.9% | 20% | ✓ exact |
| PGS004228 | Alzheimer's disease | 9K | -19.4500 | -19.5887 | -20.7841 | 3.1259 | 65.2% | 73% | ✓ exact |
| PGS004590 | Alzheimer's disease | 363 | -3.2150 | -3.4114 | -3.2835 | 0.6554 | 43.6% | 49% | ~0.3σ |
| PGS000003 | ER-negative breast cancer | 77 | 0.0772 | 0.1079 | 0.4412 | 0.3799 | 18.8% | 17% | ✓ exact |
| PGS000001 | Breast cancer | 77 | 0.7931 | 0.6498 | 0.5208 | 0.4289 | 61.3% | 77% | ~0.3σ |
| PGS000002 | ER-positive breast cancer | 77 | 0.9513 | 0.7658 | 0.5096 | 0.4807 | 71.2% | 84% | ~0.4σ |
| PGS002280 | Alzheimer's disease | 83 | 4.7450 | 4.4232 | 5.1770 | 0.3379 | 1.3% | 15% | **1.0σ** |
| PGS000018 | Coronary artery disease | 1745K | -0.3186 | -0.6846 | -0.3197 | 0.5417 | 23.9% | 51% | **0.7σ** |
| PGS002249 | Alzheimer's disease | 249K | 140.6 | 112.5 | 116.0 | 17.2 | 42.2% | 87% | **1.6σ** |
| PGS000039 | Ischemic stroke | 3226K | 12.5300 | 1.2958 | 1.9376 | 0.2802 | 0.9% | 8% | **40σ !!** |

**GW Score** = Gene-Wizard raw score; **Corrected** = pgsc_calc SUM + hom-ref correction; **Emp%** = empirical EUR percentile; **GW%** = Gene-Wizard percentile; **Score Δ** = difference in σ units

## Analysis

### Scores that match (Δ < 0.1σ)

Six genome-wide PGS raw scores agree to within <1%: PGS003992, PGS002753, PGS005170, PGS004008, PGS002035, PGS004228. This validates that Gene-Wizard's scoring logic is correct for these scores.

### Small PGS differ slightly (Δ ~ 0.1–0.5σ)

PGS000001/2/3 (77 variants each) and PGS004590 (363 variants) differ by ~0.1–0.4σ. pgsc_calc excludes 6–8% of variants as strand-ambiguous (A/T, C/G SNPs). Gene-Wizard likely includes these, accounting for the small gap.

### Significant discrepancies

- **PGS000039 (Ischemic stroke, 3.2M variants):** Gene-Wizard score 12.53 vs corrected 1.296 — a 40σ discrepancy. EUR reference range is 1.2–2.7, making 12.53 physically impossible. Likely a different scoring file version or a scoring bug specific to this PGS.
- **PGS002249 (Alzheimer's, 249K variants):** Gene-Wizard 140.6 vs corrected 112.5 — a 1.6σ gap (~25% higher). May indicate different PGS file versions or variant matching differences.
- **PGS000018 (CAD, 1.7M variants):** Gene-Wizard -0.319 vs corrected -0.685 — a 0.7σ gap. 72% of variants were unmatched in the VCF; the correction for 1.1M effect=REF hom-ref positions is large (-9.84), making the result sensitive to allele orientation accuracy.
- **PGS002280 (Alzheimer's, 83 variants):** Gene-Wizard 4.745 vs corrected 4.423 — a 0.95σ gap. Small variant count makes this sensitive to individual variant differences.

### Percentile comparison

Where raw scores agree, empirical EUR percentiles are close to Gene-Wizard's analytical percentiles (PGS003992: 4% vs 4%, PGS004008: 2% vs 3%, PGS002753: 0.3% vs <1%). Notable exceptions:

- **PGS002035:** Emp 47% vs GW 20% — significant percentile disagreement despite identical raw scores, indicating the analytical reference distribution is incorrect for this PGS.
- **PGS002280:** Emp 1% vs GW 15% — large percentile gap, partly from the 0.95σ score difference and partly from reference distribution differences.

## Methodology Details

### Hom-ref correction

The user's original VCF only contains variant sites (positions with ≥1 ALT allele). Positions absent from the VCF are homozygous reference. For PRS scoring:
- If effect_allele = ALT → hom-ref dosage = 0 → no score contribution
- If effect_allele = REF → hom-ref dosage = 2 → contributes 2×weight

pgsc_calc's PLINK2 scoring with no-mean-imputation treats all missing genotypes as dosage=0. The correction adds 2×weight for missing positions where effect_allele matches the genomic REF allele (determined from the HGDP+1kGP reference panel's pvar).

### Reference panel

HGDP+1kGP panel (3,942 individuals): 770 EUR, 891 AFR, 812 EAS, 766 CSA, 545 AMR, 158 MID. Scored with PLINK2 v2.00a5.10 using no-mean-imputation. Empirical percentiles computed from the EUR subset.
