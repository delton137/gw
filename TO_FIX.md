# Scientific Error Review — Fix Plan

Comprehensive audit of the genewizard codebase for scientific, statistical, and biological errors across all analysis services. Three parallel reviews examined: ancestry estimation, PRS scoring, absolute risk, PGx matching, blood typing, carrier screening, trait matching, parsing, and data files.

Findings are prioritized by clinical impact. Issues 1-3 produce wrong results for real users and should be fixed immediately. Issues 4-8 are medium severity. Issues 9-14 are low severity.

---

## HIGH SEVERITY — Wrong results

### 1. ~~CFTR F508del false positives in VCF users~~ FIXED
**Resolution:** Removed CFTR from carrier_panel.json entirely. F508del is a 3-nt indel that encodes differently across file formats (VCF: ATCT/A, DTC: I/D) — the string `.count()` approach in `_count_allele` is fundamentally broken for indels where the pathogenic allele is a substring of the reference. The remaining 3 CFTR SNPs (G551D, W1282X, N1303K) are individually too rare to provide meaningful screening without F508del covering ~70% of CF alleles.

### 2. ~~CYP2C19 *17 activity score = 2.0 (should be 1.5)~~ FIXED
**Resolution:** Changed `activity_score` from `2.0` to `1.5` in `_pgx_allele_definitions.py` and `pgx_alleles.json`. CPIC assigns no numeric activity value to CYP2C19 *17 (only "Increased function"). The 2.0 was a mistaken analogy from CYP2D6 gene duplication convention. Value of 1.5 produces correct CPIC phenotypes for all diplotypes. Re-run `seed_pgx_definitions.py` on prod to update DB.

### 3. PGx guideline activity score range matching broken
**Files:** `app/services/pgx_guidelines.py:154`
**Bug:** For non-open-ended ranges (`max < 999`), uses `math.isclose(rounded, gl.activity_score_min)` — point matching, not range matching. Any guideline with a true range (e.g., `min=0.5, max=1.0`) would only match scores equal to the min.
**Fix:** Replace with proper range check:
```python
return gl.activity_score_min - 0.001 <= rounded <= gl.activity_score_max + 0.001
```

---

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

### 5. ABO "func" fallback defaults to "A"
**Files:** `app/services/blood_type.py:617-620`
**Bug:** When only the 261delG is available and user is homozygous functional (G/G), defaults to phenotype "A". The user could equally be B/B or A/B. The 261delG only distinguishes functional (A or B) from non-functional (O).
**Fix:** Change the fallback to report an inconclusive result:
```python
abo_phenotype = "A or B"
# Add confidence_note indicating 261delG cannot distinguish A from B
```

### 6. Blood type `_variant_matches` returns "hom_ref" for non-ref homozygotes
**Files:** `app/services/blood_type.py:302`
**Bug:** When user has two alleles neither matching REF (e.g., ref=G, user=T/T), returns `"hom_ref"` instead of `None`. Could cause incorrect allele matching at multiallelic positions.
**Fix:** Change line 302 from `return "hom_ref"` to `return None`.

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

### 9. rs2104286 wrong position in seed_snp_pages.py
**Files:** `scripts/seed_snp_pages.py:1160`
**Bug:** Fallback position `6099045` is copy-pasted from rs12722489 (line 688). Two different IL2RA variants share the same position. Needs correction to the actual GRCh37 position for rs2104286. Verify via dbSNP.

### 10. rs6025 (Factor V Leiden) ref/alt swapped in seed_snp_pages.py
**Files:** `scripts/seed_snp_pages.py:985`
**Bug:** Fallback has `ref_allele="T"`, `alt_allele="C"`. On GRCh37 plus strand, reference is C and alt is T (F5 is on minus strand; c.1601G>A coding = C>T genomic). The risk_allele="T" in the trait is correct, but the ref/alt labels are swapped.
**Fix:** Swap to `ref_allele="C"`, `alt_allele="T"`.

### 11. MEFV GRCh38 positions — suspicious -50000 offset
**Files:** `app/data/carrier_panel.json` lines 189, 203, 217
**Bug:** All three MEFV variants show exactly -50000 offset from GRCh37 to GRCh38 (e.g., 3293407 → 3243407). Real liftover offsets are almost never exactly round numbers.
**Fix:** Verify against dbSNP GRCh38 positions. Correct if wrong.

### 12. Ancestry proportions don't sum to 1.0
**Files:** `app/services/ancestry_estimator.py:231-242`
**Bug:** Rounding to 4 decimal places + zeroing below 0.0001 causes proportions to sum to ~0.998 instead of 1.0. Cosmetic issue visible to frontend users.
**Fix:** Renormalize after rounding/zeroing: `proportions = [p / sum(proportions) for p in proportions]`.

### 13. DPYD: CPIC now distinguishes within IM (AS=1.0 vs AS=0.5)
**Files:** `app/services/pgx_matcher.py:64-68`
**Note:** Both AS=0.5 and AS=1.0 map to "Intermediate Metabolizer" which is correct. But CPIC 2023 update distinguishes these for dosing (AS=0.5 gets more aggressive dose reduction). Not wrong, but a refinement opportunity for guideline matching.

### 14. Absolute risk: P(case|z=0) != prevalence
**Note:** At population-average PRS (z=0), computed risk is lower than prevalence (e.g., 0.069 vs 0.10 for K=0.10, d=1.0). Mathematically correct for this model but potentially confusing. Consider adding a note in the frontend display. Not a bug.

---

## Verification Plan

1. **Carrier screening:** Write a test for CFTR F508del with VCF-style alleles (ATCT/ATCT → 0 pathogenic, ATCT/A → 1 pathogenic, A/A → 2 pathogenic)
2. **CYP2C19:** Write tests for `*1/*17` → Rapid, `*2/*17` → Likely IM, `*17/*17` → Ultrarapid
3. **PGx guidelines:** Check if any `cpic_dpwg_guidelines.json` entries use true activity score ranges (min != max and max < 999). If so, write test for range matching.
4. **Absolute risk:** Test that at z=2, K=0.1, AUC=0.75, the rescaled result differs from current result, and compare to published values.
5. **Blood type:** Test `_variant_matches` when user is hom for a non-ref, non-alt allele.
6. **Data fixes:** Verify rs2104286 position, rs6025 ref/alt, and MEFV GRCh38 positions against dbSNP before correcting.
7. Run full test suite: `python -m pytest tests/ -x`
