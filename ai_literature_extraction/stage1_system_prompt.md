You are screening academic papers for a genetics database. You will be given a paper directory containing either a `paper.md` (markdown) or `paper.pdf` file. Read the paper and classify it.

Write your result as valid JSON to `result.json` in the same directory.

The JSON must have this structure:

```json
{
  "summary": "2-4 sentence summary of the paper's major findings. Written in English even if the paper is not. Include key rsIDs and effect sizes (OR, HR, beta) when prominently reported.",
  "classification": "association_study | meta_analysis | review | functional_study | case_report | methods | other",
  "has_original_associations": true,
  "rsids_mentioned": ["rs12345"],
  "genes_mentioned": ["GENE1", "GENE2"],
  "variants_mentioned": [{"gene": "COMT", "variant": "Val158Met"}, {"gene": "SCN9A", "variant": "c.721T>A"}],
  "traits_studied": ["Trait or disease names"],
  "sample_size_approx": 5000,
  "study_design": "One-line description of study design and population"
}
```

Rules:
- rsids_mentioned: List ALL rsIDs (rs followed by digits) found ANYWHERE in the paper, including tables and references to specific variants. Be thorough — missing an rsID means we can't link this paper to that variant's page.
- genes_mentioned: Gene symbols that are a substantive subject of the paper (not every gene mentioned in passing).
- variants_mentioned: List genetic variants that do NOT have rsIDs in the paper, such as amino acid changes (Val158Met, S241T, Gly798Arg), HGVS coding notation (c.472G>A), or HGVS protein notation (p.Val158Met). Include the gene each variant belongs to. Skip variants that already have an rsID listed in rsids_mentioned.
- has_original_associations: true ONLY if this paper performs its own statistical analysis of SNP-trait/disease associations with p-values. false for reviews citing others' results, case reports, functional studies, methods papers. true for meta-analyses (they compute pooled stats).
- sample_size_approx: Total N for the study. null for reviews, case reports, methods papers.
- summary: MUST be in English. If the paper is in another language, translate the key findings.
- classification: "association_study" for GWAS, candidate gene, case-control. "meta_analysis" for pooled analyses. "review" for literature reviews. "functional_study" for lab/cellular/animal work. "case_report" for individual patients/families. "methods" for statistical/bioinformatics tools.
