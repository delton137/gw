Our Approach: Deterministic REF/REF Imputation
The blog post discusses three imputation strategies: mean imputation (assume average AF), genetic/LD imputation (TOPMed/Michigan), and ignore missing. We use none of these — we use a fourth approach that's actually better for WGS:

The Logic (scorer.py:360-418)
In a variant-only VCF, only positions with at least one ALT allele are reported. Every position absent from the VCF is REF/REF. So for missing PRS variants:

effect_is_alt = True → effect allele is the ALT. REF/REF = 0 copies → dosage = 0 → contributes nothing (no action needed)
effect_is_alt = False → effect allele is the REF. REF/REF = 2 copies → dosage = 2 → contributes 2 × weight
This is deterministic, not statistical. For WGS data, missing = REF/REF is ground truth (modulo no-call regions, which are ~2.7% per the blog post).

Reference Distribution in VCF Mode (scorer.py:474-512)
After imputation, the score covers essentially all variants, so the scorer uses the global reference distribution (computed over ALL weight variants) rather than a matched-variant subset. This is correct — if you impute all missing positions, your score is comparable to the full-genome reference distribution.

The Pipeline Flow in analysis.py
effect_is_alt column is conditionally added to the weights DataFrame only if at least one value is non-NULL (analysis.py:604-607)
If the column is present, VCF imputation runs; if absent, it silently falls back to array mode (scorer.py:467-472 now warns about this)
ancestry_weights=None is hardcoded (analysis.py:631), so mixture normalization is dead code
What the Blog Post Highlights That's Relevant
The blog post notes PRSKB uses mean imputation (assume population-average AF for missing variants) — this is statistically noisier than our approach for WGS. Our deterministic REF/REF imputation is scientifically stronger because we know the genotype at missing positions.

However, two weaknesses remain:

The effect_is_alt dependency — the entire imputation mechanism is gated on this flag being populated (the bug just fixed by the other agent). Without it, ~49% of variant contributions are silently zeroed.

No-call contamination — we treat no-call regions identically to true REF positions. For typical 30x WGS this is minor (~2-3% of genome), but for low-coverage WGS it could introduce error. We don't distinguish the two.

Want me to update the plan to address any of these, or are you ready to move forward with implementation?