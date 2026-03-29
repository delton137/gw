# Multi-Stage Literature Extraction Pipeline

## Context

33,710 academic papers (8,518 markdown + 25,192 PDF-only) in `/media/dan/500Gb/snpedia_pdfs/`, named by DOI. Metadata (PMID, title, authors, journal, year) already extracted in `ai_literature_extraction/snpedia_papers_metadata.csv` (36K rows, 34K with PMIDs, 32K with DOIs).

Goal: Extract structured SNP-trait association data to enrich SNP pages, with enough statistical detail to support replication detection and future meta-analysis.

## Architecture: 3 Stages

1. **Stage 1 (Haiku)**: Triage ALL 33.7K papers — classify, summarize, list rsids/genes
2. **Stage 2 (Sonnet)**: Deep extraction on papers flagged as association/meta-analysis studies
3. **Stage 3 (code)**: Aggregation — replication detection, pooled stats, consensus evidence levels

This plan focuses on **Stage 1** in detail.

---

## Stage 1: Triage (Haiku)

### Purpose
For every paper, produce:
1. A **1-3 sentence summary** of findings (displayed on SNP pages as "Papers discussing this variant")
2. A complete list of **rsids mentioned** (links papers ↔ SNPs)
3. A complete list of **genes discussed** (links papers ↔ gene pages)
4. A **classification** that determines whether the paper proceeds to Stage 2
5. Enough info to understand what kind of study this is without re-reading it

### Input strategy
- **Prefer markdown** when available (8,518 papers) — cheaper, cleaner
- **Fall back to PDF** for the remaining 25,192 — Claude API handles PDFs natively
- Process **all languages** — extract from non-English papers too (the model understands them)
- Join with metadata CSV to get PMID, title, year, journal (don't ask the model to extract these)

### What the model extracts

```json
{
  "summary": "1-3 sentence summary of the paper's main findings and conclusions.",
  "classification": "association_study",
  "has_original_associations": true,
  "organism": "human",
  "rsids_mentioned": ["rs429358", "rs7412"],
  "genes_mentioned": ["APOE", "CLU", "PICALM"],
  "traits_studied": ["Alzheimer's Disease", "Cognitive Decline"],
  "n_snps_tested": 12,
  "sample_size_approx": 5000,
  "study_design": "case-control GWAS in European population",
  "key_findings_direction": "positive"
}
```

### Field definitions

**summary**: Written in English regardless of paper language. Focuses on WHAT was studied and WHAT was found. Not a methods description. Examples:
- "This GWAS of 14,000 cases identified rs1234 as significantly associated with type 2 diabetes (OR=1.3, p=5e-8) in European populations."
- "A candidate gene study of MTHFR variants in 300 Brazilian patients found no significant association with neural tube defects after correction for multiple testing."
- "Review of 47 studies on APOE and Alzheimer's risk, summarizing that ε4 carriers have 3-4x increased risk."

**classification**: One of:
- `association_study` — reports its own statistical analysis of SNP-phenotype associations (GWAS, candidate gene, case-control, cohort)
- `meta_analysis` — pools data/results from multiple prior studies to compute combined effect sizes
- `review` — summarizes existing literature without new pooled analysis
- `functional_study` — lab/cellular/animal work characterizing what a variant does mechanistically (e.g., gene expression, protein function, splicing)
- `case_report` — individual patient(s) or families
- `methods` — statistical methods, bioinformatics tools, study design papers
- `other` — doesn't fit above categories

**has_original_associations**: `true` ONLY if the paper performs its own statistical test of SNP-trait associations with p-values on a study population. `false` for reviews, case reports, functional studies, methods papers. For meta-analyses: `true` (they compute pooled statistics).

**organism**: `human`, `mouse`, `rat`, `cell_line`, `multiple`, `other`. Important because some genetics papers are about model organisms and won't have human-relevant SNP associations.

**rsids_mentioned**: ALL rs-numbers found anywhere in the paper — tables, text, supplementary references. These are used to link the paper to SNP pages even if the paper isn't an association study. A review that discusses rs429358 is still a useful reference for the rs429358 page.

**genes_mentioned**: Gene symbols (APOE, BRCA1, CYP2D6, etc.) discussed substantively in the paper. Not every gene mentioned in passing — focus on genes that are a subject of the study.

**traits_studied**: Diseases, phenotypes, or biomarkers that are the subject of the study. Standardized names preferred.

**n_snps_tested**: Approximate number of SNPs analyzed. Helps estimate Stage 2 extraction volume. `null` if not applicable.

**sample_size_approx**: Approximate total sample size (cases + controls, or total cohort). `null` for reviews, case reports, methods papers.

**study_design**: Free-text 1-line description. Examples: "case-control GWAS in European population", "family-based TDT in Portuguese autism cohort", "meta-analysis of 12 cohort studies", "functional characterization in HEK293 cells".

**key_findings_direction**: `positive` (found significant associations), `negative` (found no significant associations / null result), `mixed` (some positive, some null), `not_applicable` (reviews, methods, etc.)

### Stage 1 Prompt (Haiku)

```
You are screening academic papers for a genetics database. Read this paper and classify it.

Return valid JSON only, no other text:

{
  "summary": "1-3 sentences summarizing findings. Written in English even if the paper is not. Focus on what was studied and what was found, including key rsIDs and effect sizes when available.",
  "classification": "association_study | meta_analysis | review | functional_study | case_report | methods | other",
  "has_original_associations": true,
  "organism": "human | mouse | rat | cell_line | multiple | other",
  "rsids_mentioned": ["rs12345"],
  "genes_mentioned": ["GENE1", "GENE2"],
  "traits_studied": ["Trait or disease names"],
  "n_snps_tested": 12,
  "sample_size_approx": 5000,
  "study_design": "One-line description of study design and population",
  "key_findings_direction": "positive | negative | mixed | not_applicable"
}

Rules:
- rsids_mentioned: List ALL rsIDs (rs followed by digits) found ANYWHERE in the paper, including tables and references to specific variants. Be thorough — missing an rsID means we can't link this paper to that variant's page.
- genes_mentioned: Gene symbols substantively discussed (not every gene mentioned in passing).
- has_original_associations: true ONLY if this paper performs its own statistical analysis of SNP-trait/disease associations with p-values. false for reviews citing others' results, case reports, functional studies, methods papers. true for meta-analyses (they compute pooled stats).
- organism: What organism is the primary subject? "human" for epidemiological/clinical genetics studies. "cell_line" for in vitro work. "mouse"/"rat" for animal models.
- sample_size_approx: Total N for the study. null for reviews, case reports, methods papers.
- n_snps_tested: How many individual SNPs were statistically tested. null if not applicable.
- summary: MUST be in English. If the paper is in another language, translate the key findings. Include specific rsIDs and effect sizes (OR, HR, beta) when prominently reported.
- key_findings_direction: "positive" if the paper reports significant SNP-trait associations. "negative" if the main conclusion is no association found. "mixed" if some positive, some null.

Paper DOI: {DOI}

{PAPER_CONTENT}
```

### Cost estimate

| Input type | Count | Avg tokens | Haiku input cost | Haiku output cost | Total |
|-----------|-------|-----------|-----------------|------------------|-------|
| Markdown | 8,518 | ~15K | $32 | $4 | $36 |
| PDF | 25,192 | ~25K | $158 | $13 | $171 |
| **Total** | **33,710** | | | | **~$207** |

### Implementation: `scripts/extract_literature.py`

```
- Load metadata CSV into a DOI→{pmid, title, year, journal, authors} lookup
- For each DOI in /media/dan/500Gb/snpedia_pdfs/:
  - Skip if already processed (output JSON exists)
  - Read markdown if available, else read PDF bytes
  - Send to Haiku API with the Stage 1 prompt
  - Merge model output with metadata (pmid, title, year, journal)
  - Save to /media/dan/500Gb/snpedia_extractions/stage1/{doi_safe}.json
- Async with configurable concurrency (default 20)
- Resume-friendly: checks for existing output files
- Progress logging: papers processed, classifications breakdown, rsid counts
```

### What Stage 1 enables

1. **SNP pages → "References" section**: For any rsid, query `paper_snp_mentions` to show all papers that discuss it, with title, journal, year, and summary
2. **Gene pages → "Literature" section**: Same for genes
3. **Stage 2 filtering**: Only send `has_original_associations=true` or `classification=meta_analysis` papers to Sonnet
4. **Corpus statistics**: How many association studies vs reviews vs functional work? What traits are most studied?
5. **Negative results**: Papers with `key_findings_direction=negative` are scientifically valuable — they help calibrate evidence levels

### Things we might be missing — considered and decided

| Considered | Decision | Reasoning |
|-----------|----------|-----------|
| Extract year from paper | **No** — get from metadata CSV | Already have it for 36K papers |
| Extract PMID from paper | **No** — get from metadata CSV | Already have 34K PMIDs |
| Extract author list | **No** — get from metadata CSV | Already have it |
| Extract conflict of interest | **Skip for now** | Low priority for SNP pages |
| Extract funding source | **Skip for now** | Low priority for SNP pages |
| Extract specific effect sizes | **Stage 2's job** | Haiku may get stats wrong; summary captures the gist |
| Extract population ancestry | **Partially** — via study_design | Full extraction in Stage 2 |
| Distinguish discovery vs replication cohorts | **Stage 2's job** | Too detailed for triage |
| Extract from supplementary materials | **No** — not in our files | We only have main paper text |

---

## Stages 2 & 3 (summary — detailed design later)

### Stage 2: Detailed Extraction (Sonnet)
- Run on papers where `has_original_associations=true` or `classification=meta_analysis`
- Extract per-rsid: effect_size, CI, p_value, n_cases, n_controls, population, genetic_model, survives_correction, is_replication
- Output: `snp_study_results` table (one row per rsid-trait-paper)
- See full Stage 2 prompt in previous version of this plan

### Stage 3: Aggregation (code)
- Group `snp_study_results` by (rsid, trait)
- Detect replications (same rsid+trait in independent populations)
- Check directional consistency
- Compute pooled meta-analysis estimates (fixed/random effects)
- Promote best-evidenced associations → `snp_trait_associations`

### New DB tables (for all stages)
- `papers` — doi (PK), pmid, title, summary, classification, year, journal, authors, organism, study_design, has_original_associations, key_findings_direction, sample_size_approx, processed_at
- `paper_snp_mentions` — doi (FK), rsid — composite PK
- `paper_gene_mentions` — doi (FK), gene_symbol — composite PK
- `snp_study_results` — id (UUID PK), doi (FK), rsid, gene, trait, risk_allele, effect_size, effect_size_type, ci_lower, ci_upper, p_value, n_cases, n_controls, n_total, population, study_type, genetic_model, survives_correction, is_replication, effect_description, effect_summary, extracted_at

## Files to create
- `scripts/extract_literature.py` — Stage 1 + 2 pipeline
- `scripts/ingest_extractions.py` — DB ingestion
- `alembic/versions/030_literature_tables.py` — migration
- `app/models/literature.py` — SQLAlchemy models
