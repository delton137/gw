


## MEDIUM SEVERITY — Edge case errors

### 4. Absolute risk z-score scale mismatch
**Files:** `app/services/absolute_risk.py:114-127`
**Bug:** The Bayesian mixture model defines case/control PRS distributions with unit variance on the raw scale. But `z_score` from the scorer is population-standardized (`z = (raw - mean) / std`). The population SD on the raw scale is `sqrt(1 + K*(1-K)*d^2) > 1`, so the z-score compresses the scale. This causes systematic underestimation of risk at the tails (~2.8pp error at z=3 for K=0.1, AUC=0.75).
**Fix:** Rescale before computing posterior:
```python
sigma_pop = sqrt(1.0 + K * (1.0 - K) * d * d)
z_raw = z_score * sigma_pop
# Use z_raw instead of z_score in pdf_case/pdf_control
```
Also fix docstring: model is a Bayesian mixture (Mars et al. 2020), not GenoPred's liability threshold model.


### 7. No strand/complement handling in PGx and trait matchers
**Files:** `app/services/pgx_matcher.py:241-242`, `app/services/trait_matcher.py:46-47`
**Bug:** Direct string comparison for allele matching. DTC data on the opposite strand would get false wild-type calls. `carrier_matcher.py` has `_resolve_alleles` for this but PGx and trait matchers lack it.
**Impact:** Mitigated if allele definitions are already on the chip-reported strand, but any new variant added on the wrong strand would silently fail. VCF data (always plus strand) is not affected if definitions are on the plus strand.
**Fix:** Add complement-aware matching to both matchers, similar to `carrier_matcher._resolve_alleles`. At minimum, for DTC data, try complement if direct match fails (skip strand-ambiguous A/T and C/G SNPs).

### 8. Mixture normalization not wired up for admixed users
**Files:** `app/services/analysis.py:~613`
**Bug:** `compute_prs()` always receives `ancestry_weights=None`. The mixture normalization code in `scorer.py` exists but is never invoked. Admixed users get PRS percentiles against a single-ancestry reference.
**Fix:** Pass `ancestry_weights` from `detected_ancestry` into `compute_prs` when `is_admixed` is true. (Feature gap, not a code error.)

---

## LOW SEVERITY — Data errors and cosmetic

### 10. rs6025 (Factor V Leiden) ref/alt swapped in seed_snp_pages.py
**Files:** `scripts/seed_snp_pages.py:985`
**Bug:** Fallback has `ref_allele="T"`, `alt_allele="C"`. On GRCh37 plus strand, reference is C and alt is T (F5 is on minus strand; c.1601G>A coding = C>T genomic). The risk_allele="T" in the trait is correct, but the ref/alt labels are swapped.
**Fix:** Swap to `ref_allele="C"`, `alt_allele="T"`.

### 11. MEFV GRCh38 positions — suspicious -50000 offset
**Files:** `app/data/carrier_panel.json` lines 189, 203, 217
**Bug:** All three MEFV variants show exactly -50000 offset from GRCh37 to GRCh38 (e.g., 3293407 → 3243407). Real liftover offsets are almost never exactly round numbers.
**Fix:** Verify against dbSNP GRCh38 positions. Correct if wrong.

### 12. ~~Ancestry proportions don't sum to 1.0~~ FIXED
**Resolution:** Added renormalization after rounding/zeroing for both populations and superpopulations in `ancestry_estimator.py`.

### 13. DPYD: CPIC now distinguishes within IM (AS=1.0 vs AS=0.5)
**Files:** `app/services/pgx_matcher.py:64-68`
**Note:** Both AS=0.5 and AS=1.0 map to "Intermediate Metabolizer" which is correct. But CPIC 2023 update distinguishes these for dosing (AS=0.5 gets more aggressive dose reduction). Not wrong, but a refinement opportunity for guideline matching.

### 14. Absolute risk: P(case|z=0) != prevalence
**Note:** At population-average PRS (z=0), computed risk is lower than prevalence (e.g., 0.069 vs 0.10 for K=0.10, d=1.0). Mathematically correct for this model but potentially confusing. Consider adding a note in the frontend display. Not a bug.
