# GenoPred-Inspired Features for genewizard.net

The GenoPred paper and codebase (R/Shiny, 20+ PRS methods, PCA-based ancestry detection, absolute risk conversion) represent the academic gold standard for polygenic score interpretation. GeneWizard already has solid infrastructure (Polars-based scoring, ancestry-stratified reference distributions, trait matching, async pipeline), but lacks advanced visualization and clinical interpretation features. This plan identifies 7 high-impact features we can adapt from GenoPred's approach, ranked by utility and feasibility within our web app architecture.

**Key insight from the paper:** The biggest barrier to clinical PRS adoption isn't computation — it's *interpretation*. Converting a percentile into an actionable risk estimate is what makes PRS useful to patients and doctors.

---

## Feature 1: PRS Distribution Curve Visualizations (Build Order #9)

**What:** Replace flat percentile bars with interactive bell curves showing the reference population distribution and the user's position. This is already item #9 on the build order.

**Why:** A percentile number ("72nd percentile") is abstract. A bell curve with a "you are here" marker is instantly intuitive. Every major PRS reporting tool uses this pattern.

**Implementation:**
- **Backend:** Add `z_score`, `ref_mean`, `ref_std` columns to `prs_results` table (these values are already computed in `scorer.py` but discarded). Populate during analysis pipeline. Return in `/api/v1/results/prs/{user_id}` response.
- **Frontend:** New `PrsDistributionChart` Recharts component. Generate normal PDF curve client-side from mean/std (200 sample points across mean ± 4*std). Vertical marker at user's raw score. Gradient fill (green→yellow→red). Show percentile label, ancestry group, variant coverage ratio.
- **Migration:** Add 3 nullable Float columns to `prs_results`.

**Files:** `app/services/scorer.py`, `app/models/user.py`, `app/routes/results.py`, `frontend/src/app/dashboard/page.tsx`
**Complexity:** Medium | **Dependencies:** None

---

## Feature 2: Absolute Risk Conversion (Percentile → Disease Probability)

**What:** For binary disease traits, convert PRS z-score into estimated lifetime disease probability. Display: "Your estimated risk: ~15% (population average: 10%)".

**Why:** GenoPred's central innovation. A percentile is relative; absolute risk is actionable. The PGS Catalog already provides AUC for many scores (stored in `prs_scores.reported_auc`).

**Implementation:**
- **New service** `app/services/absolute_risk.py`: Implement the liability threshold model:
  - Convert AUC → liability R² via `r2 = 2 * (norminv(AUC))^2 / (1 + norminv(AUC)^2)`
  - For user z-score `z`: `risk = prevalence * Phi((z * sqrt(r2) - Phi_inv(1-K)) / sqrt(1 - r2))`
  - Pure scipy.stats computation, ~30 lines
- **New table** `prs_trait_metadata`: `pgs_id (FK)`, `trait_type` (binary/continuous), `prevalence`, `population_source`. Manually curate for the 8 priority scores.
- **Backend:** Add `absolute_risk` and `population_risk` to PRS results response.
- **Frontend:** Risk comparison card below each distribution chart. **Must include prominent disclaimer** (not diagnostic, doesn't account for family history/environment/lifestyle).

**Files:** New `app/services/absolute_risk.py`, `app/models/prs.py`, `app/routes/results.py`, `frontend/src/app/dashboard/page.tsx`
**Complexity:** Medium | **Dependencies:** Feature 1 (needs z_score stored)

---

## Feature 3: Genotype-Based Ancestry Estimation

**What:** Auto-detect ancestry composition from the genotype data using ~1,500 ancestry-informative markers (AIMs), instead of requiring user self-report. Show: "Your genotype suggests: 78% European, 15% East Asian, 7% South Asian".

**Why:** Wrong ancestry selection is the #1 source of PRS miscalibration. Many users don't know which category fits them. GenoPred uses PCA + elastic net, but a naive Bayes classifier on AIMs works well for DTC chips and requires no PLINK.

**Implementation:**
- **New table** `ancestry_informative_markers`: rsid + per-superpopulation allele frequencies (~1,500 high-Fst SNPs from published panels like Kidd et al. 2014 or 1000G high-Fst subset).
- **New service** `app/services/ancestry_estimator.py`: Naive Bayes classifier — compute log-likelihood per population from genotype + AIM allele frequencies under HWE. Normalize to posterior probabilities. Pure Polars vectorized computation.
- **Pipeline change:** Call after parsing, before scoring. Store `estimated_ancestry` JSON on `Analysis` model.
- **Upload UX:** Make ancestry dropdown optional with "Auto-detect (recommended)" as default.

**Security note:** Ancestry is sensitive. Store only superpopulation proportions. Allow user override. Include note that genetic ancestry ≠ identity.

**Files:** New `app/services/ancestry_estimator.py`, `app/models/user.py`, `app/services/analysis.py`, `app/routes/upload.py`, `frontend/src/app/upload/`
**Complexity:** Medium-Large (AIM panel curation is the hard part) | **Dependencies:** None, but unlocks Feature 5

---

## Feature 4: Effect Size Interpreter on SNP Pages

**What:** On public `/snp/[rsid]` pages, translate raw odds ratios into plain language and absolute risk differences. Interactive widget where users can adjust baseline prevalence and see: "Carriers have 1.3x higher odds of T2D, which translates to ~3 percentage point increase in lifetime risk."

**Why:** Current SNP pages show raw OR/p-values that are meaningless to non-scientists. Interpretable content improves user utility AND SEO (richer content = lower bounce rate = better rankings).

**Implementation:**
- **Frontend only** (client-side math):
  - `risk_exposed = (OR * baseline) / (1 - baseline + OR * baseline)`
  - `risk_difference = risk_exposed - baseline`
  - Interactive prevalence slider with sensible defaults per trait
- **New column** on `snp_trait_associations`: `trait_prevalence` (nullable float). Populate for common traits.
- **SNP page component:** Expandable "What does this mean?" section below each association row.

**Files:** `frontend/src/app/snp/[rsid]/page.tsx`, `app/models/snp.py` (if adding trait_prevalence)
**Complexity:** Small-Medium | **Dependencies:** None (fully independent)

---

## Feature 5: Continuous Ancestry-Weighted PRS Normalization

**What:** For admixed users, compute PRS percentiles using a weighted mixture of ancestry-specific reference distributions rather than forcing into one discrete bin.

**Why:** ~30% of Americans are multiracial/admixed. Forcing them into one bin introduces systematic bias. GenoPred uses PC regression; we can use a simpler Gaussian mixture that works with our existing per-ancestry reference distributions.

**Implementation:**
- **Scorer change** (`scorer.py`): Accept `ancestry_weights: dict[str, float]`. Compute mixture reference:
  - `mixture_mean = Σ(w_k * mean_k)`
  - `mixture_var = Σ(w_k * (var_k + mean_k²)) - mixture_mean²`
  - ~10 lines of Python
- **Pipeline:** If Feature 3 provides ancestry weights, pass to scorer. Otherwise accept user-provided weights via upload endpoint.
- **PrsResult model:** Add `ancestry_weights_used` JSON column.

**Files:** `app/services/scorer.py`, `app/services/analysis.py`, `app/models/user.py`
**Complexity:** Small | **Dependencies:** Feature 3 for automatic weights

---

## Feature 6: PRS Confidence Intervals / Coverage Quality

**What:** Show uncertainty around percentile estimates based on variant coverage. Display: "72nd percentile (likely range: 65th–79th)" with a quality badge (high/medium/low).

**Why:** A PRS from 95% matched variants is far more reliable than one from 30%. Users and clinicians need to know which scores to trust. Most DTC services lack this.

**Implementation:**
- **Scorer change:** Estimate variance from missing variants:
  - `avg_var_per_variant = mean(2 * p_i * (1-p_i) * w_i² for matched variants)`
  - `var_missing ≈ n_missing * avg_var_per_variant`
  - `CI = [percentile(score - 1.96*sqrt(var_missing)), percentile(score + 1.96*sqrt(var_missing))]`
- **PrsResult model:** Add `percentile_lower`, `percentile_upper`, `coverage_quality` columns.
- **Frontend:** Error bars on distribution chart, quality badge next to each score.

**Files:** `app/services/scorer.py`, `app/models/user.py`, `frontend/src/app/dashboard/page.tsx`
**Complexity:** Small-Medium | **Dependencies:** Feature 1 for visual display

---

## Feature 7: Downloadable PDF Report

**What:** Generate a formatted PDF summarizing all results, suitable for sharing with a healthcare provider.

**Why:** Users want to share PRS results with their doctor. A well-formatted PDF with context and disclaimers is more useful than a dashboard screenshot. Also creates a natural premium feature.

**Implementation:**
- **New endpoint** `GET /api/v1/results/report/{user_id}`: Generate PDF via `reportlab` (pure Python, no system deps).
- **Contents:** Header/branding, ancestry group, PRS results table with percentiles, top trait associations by risk level, disclaimer/interpretation guide.
- **Frontend:** "Download Report" button on dashboard.
- **Note:** Distribution curve images need server-side rendering (matplotlib or pre-rendered SVG).

**Files:** New `app/routes/report.py`, new `app/services/report_generator.py`, `frontend/src/app/dashboard/page.tsx`
**Complexity:** Medium-Large | **Dependencies:** Features 1 & 2 for rich content

---

## Recommended Build Sequence

```
Phase A (parallel):  Feature 1 (distribution charts) + Feature 4 (SNP page interpreter)
Phase B (parallel):  Feature 2 (absolute risk) + Feature 6 (confidence intervals)
Phase C:             Feature 3 (ancestry estimation)
Phase D:             Feature 5 (mixture normalization, uses Feature 3)
Phase E:             Feature 7 (PDF report, uses everything above)
```

# What We're NOT Adopting (and Why)

- **Multi-method PRS (LDpred2, PRS-CS, SBayesR, etc.):** Requires PLINK, LD matrices, HPC compute. We use pre-computed PGS Catalog weights, which is the right tradeoff for a web app.
- **PCA from genotype data:** Full PCA requires a reference panel in PLINK format. The naive Bayes AIM approach (Feature 3) achieves 95%+ accuracy for superpopulation classification without PLINK.
- **Cross-ancestry transfer learning (PRS-CSx):** Requires running the method on GWAS summary stats. Out of scope for a consumer web app.
- **K-fold cross-validation:** Relevant for method development, not for scoring individual users.

## Why we're not adopting blood typing
ABO alone has ~9% error rate (BOOGIE 2015 on 23andMe)
Extended systems (Kell, Duffy, Kidd, etc.) have zero published validation on DTC data
RBCeq2's microarray mode is undocumented and unvalidated
Our partial-match approach skips RBCeq2's core filtering pipeline
No clinical guidelines endorse DTC-derived blood typing
Need imputation (major undertaking) to get reliable results


## Verification

- **Feature 1:** Visual inspection of charts against known percentile values; compare curve shape to GenoPred's Shiny app
- **Feature 2:** Validate absolute risk calculations against GenoPred paper Table 1 (known AUC + prevalence → expected risk per quantile for 11 phenotypes)
- **Feature 3:** Test against 1000 Genomes samples with known ancestry labels; expect >95% accuracy at superpopulation level
- **Features 4-7:** Unit tests for math functions; manual UI review
- **All features:** Run existing 53-test suite to verify no regressions
