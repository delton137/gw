# genewizard.net — Claude Code Build Prompt

## Project Overview

genewizard.net analyzes raw genetic data from DTC genomics companies (23andMe, AncestryDNA) and WGS VCFs. The app auto-detects genetic ancestry, computes polygenic risk scores (PRS) with ancestry-aware normalization, matches user variants against a curated SNP-trait knowledge base, infers pharmacogenomic star alleles with CPIC/DPWG drug guidelines, and screens for recessive carrier status. It also serves public SEO-friendly pages for every SNP in the database.

**Critical design constraint: Raw genetic data is NEVER persisted.** Files are parsed in memory, analysis results are stored, and the raw genotype data is discarded immediately after processing.

## Tech Stack

- **Backend:** Python 3.12, FastAPI, SQLAlchemy 2.0 (async), asyncpg, Polars, asyncio background tasks
- **Database:** PostgreSQL 16 (native, no Docker)
- **Frontend:** Next.js 15 (App Router), TypeScript, TailwindCSS v4, Recharts
- **Auth:** Clerk (@clerk/nextjs frontend, PyJWT + JWKS verification backend)
- **PDF Reports:** ReportLab
- **Deployment:** Railway via Nixpacks (backend), Vercel (frontend)

## Database Schema

### Public Knowledge Base

**snps** — rsid (PK), chrom, position, ref_allele, alt_allele, gene, functional_class, maf_global, cadd_phred, sift_score, polyphen_score, revel_score, clinvar_significance, hgvs_c, hgvs_p, gnomad_af_global/afr/amr/eas/nfe/sas

**snp_trait_associations** — id (UUID PK), rsid (FK), trait, risk_allele, odds_ratio, beta, p_value, effect_description, evidence_level (high/medium/low), source_pmid, source_title, extraction_method, extracted_at. Composite index on (rsid, trait).

**snpedia_snps** — rsid (PK)

### PRS Definitions

**prs_scores** — pgs_id (PK), trait_name, trait_efo_id, publication_pmid, n_variants_total, n_variants_on_chip, development_ancestry, validation_ancestry, reported_auc, imported_at

**prs_variant_weights** — pgs_id (FK), rsid (FK), chrom, position, effect_allele, weight, eur_af/afr_af/eas_af/sas_af/amr_af

**prs_trait_metadata** — pgs_id (FK, unique), trait_type ("binary"/"continuous"), prevalence, population_mean, population_std

**prs_reference_distributions** — pgs_id (FK), ancestry_group, mean, std, percentiles_json

### Pharmacogenomics

**pgx_gene_definitions** — gene (PK), calling_method, tier, default_allele, description
**pgx_star_allele_definitions** — gene, star_allele, rsid, variant_allele, function, activity_score
**pgx_diplotype_phenotypes** — gene, function_pair, phenotype
**pgx_drug_guidelines** — source (CPIC/DPWG), gene, drug, lookup_type, lookup_value, activity_score_min/max, recommendation, implication, strength, alternate_drug, pmid

### User Data

No `users` table — Clerk handles auth. `user_id` is String(255) on each user-owned record.

**analyses** — id (UUID PK), user_id, chip_type, variant_count, status (parsing → matching_fast → done → scoring_prs → complete | failed), status_detail, error_message, filename, file_format, genome_build, created_at, completed_at, detected_ancestry (JSON), ancestry_method, ancestry_confidence, selected_ancestry

**prs_results** — user_id, analysis_id, pgs_id, raw_score, percentile, z_score, ref_mean, ref_std, ancestry_group_used, n_variants_matched, n_variants_total, percentile_lower, percentile_upper, coverage_quality

**user_snp_trait_hits** — user_id, analysis_id, rsid, user_genotype, trait, effect_description, risk_level, evidence_level, association_id

**user_variants** — user_id, analysis_id, rsid, genotype (SNPedia matches)

**user_pgx_results** — user_id, analysis_id, gene, diplotype, allele1, allele2, allele1_function, allele2_function, phenotype, activity_score, n_variants_tested, n_variants_total, calling_method, confidence, drugs_affected, clinical_note

**user_carrier_status_results** — user_id, analysis_id, results_json (per-gene status/variants), n_genes_screened, n_carrier_genes, n_affected_flags

**genes** — symbol (PK), name, summary, ncbi_gene_id, omim_number, clinvar_total_variants, clinvar_pathogenic_count, clinvar_uncertain_count, clinvar_conflicting_count, clinvar_total_submissions

## Backend Implementation

### Analysis Pipeline (app/services/analysis.py)

Two-phase pipeline running as asyncio background task:

1. **Parse** genotype file (status: `parsing`) — detect format, chip type, build
2. **Fast matching** (status: `matching_fast`) — SNPedia, traits, PGx, carrier screening
3. Commit fast results → status: `done` (frontend redirects to dashboard)
4. **Background** — ancestry estimation + PRS scoring (status: `scoring_prs`)
5. Complete → status: `complete`

Raw file deleted after parsing. On failure: status `failed` with error_message.

### Services

**parser.py** — Parse 23andMe, AncestryDNA, VCF into Polars DataFrame [rsid, chrom, position, allele1, allele2]. Auto-detect format, filter indels/no-calls, detect chip version.

**ancestry_estimator.py** — MLE ancestry estimation on 128,097 AILs from 1000G Phase 3 (Aeon algorithm reimplemented in scipy). Estimates admixture fractions across 26 populations, aggregated to 5 superpopulations. Hardy-Weinberg genotype model with SLSQP optimization. Min 500 markers. See `docs/ancestry-estimation.md` for full details.

**scorer.py** — PRS scoring with matched-variant reference distributions, mixture normalization for admixed users, 95% CI from missing-variant uncertainty. Prefers empirical percentiles from scored reference panel (sorted_scores in percentiles_json) when available, falls back to analytical HWE. Sanity check flags scores >5σ from reference mean. Position-based rsid fallback handles both "." rsids (VCFs without annotation) and rsid version mismatches (user VCF uses different dbSNP rsids than PGS Catalog at the same position).

**absolute_risk.py** — Converts PRS z-scores to disease probabilities via liability threshold model.

**trait_matcher.py** — Batch-match user rsids against snp_trait_associations. Classify increased/moderate/typical.

**pgx_matcher.py** — Star allele calling for 76 pharmacogenes (1916 alleles). Four calling methods: activity_score, simple, binary, count.

**pgx_guidelines.py** — Match CPIC/DPWG prescribing recommendations to user PGx results.

**carrier_matcher.py** — Screen for recessive carrier status across 9 genes. Returns per-gene status (not_detected/carrier/likely_affected/potential_compound_het) with detected variant details.

**report.py** — General PDF report: carrier screening, trait hits. No PRS.

**pgx_report.py** — Clinical-style PGx PDF: gene results table, CPIC/DPWG guidelines, drug-gene interactions by therapeutic area, methods, disclaimers.

### API Routes

**POST /api/v1/upload/** — Multipart upload, max 2GB, rate limited 3/user/hour, optional ancestry_group (default: "auto")
**GET /api/v1/results/analysis/{analysis_id}** — Poll status + ancestry info
**GET /api/v1/results/prs/{user_id}** — PRS results with prs_status (ready/computing/failed), absolute risk when available
**GET /api/v1/results/pgx/{user_id}** — PGx diplotypes, phenotypes, CPIC/DPWG guidelines
**GET /api/v1/results/traits/{user_id}** — Trait hits with filters and pagination
**GET /api/v1/results/carrier-status/{user_id}** — Carrier screening results
**GET /api/v1/results/variants/{user_id}** — User SNPedia variant matches
**GET /api/v1/results/featured-snps/{user_id}** — Notable SNP hits for user
**GET /api/v1/results/pgx/{user_id}/gene/{gene}** — Per-gene PGx detail with guidelines
**GET /api/v1/snp/{rsid}** — Public SNP page data (unauthenticated)
**GET /api/v1/snp/featured** — Featured SNPs
**GET /api/v1/snp/search** — Search by gene, trait, chrom
**GET /api/v1/gene/{symbol}** — Public gene page data (unauthenticated)
**GET /api/v1/gene/featured** — Featured genes
**GET /api/v1/gene/search** — Search genes by symbol, name
**GET /api/v1/report/download** — General PDF report
**GET /api/v1/report/pgx/download** — PGx PDF report
**DELETE /api/v1/account/data** — Delete all user data (irreversible)
**GET /health** — Health check

### Shared Helpers (app/routes/_helpers.py)

`get_latest_analysis()`, `fetch_prs_results()`, `fetch_pgx_rows()`

### Scripts

- **ingest_pgs.py** — PGS Catalog ingest (metadata + weights)
- **compute_aim_panel.py** — AIM panel from 1000G (one-time)
- **load_1kg_frequencies.py** — 1000G allele frequencies into prs_variant_weights
- **compute_reference_dists.py** — Per-PRS, per-ancestry analytical reference distributions (HWE formula)
- **compute_empirical_ref_dists.py** — Empirical reference distributions from scored reference panel (PLINK2 .sscore files). Stores sorted score arrays in percentiles_json for empirical percentile lookup. Two modes: `--ref-dir` (score with PLINK2) or `--sscore-dir` (read pre-existing .sscore files)
- **seed_pgx_definitions.py** — PGx knowledge base (76 genes, 1916 alleles, 1136 guidelines). Idempotent.
- **extract_cpic_dpwg.py** — ETL from PharmCAT (one-time)
- **seed_snp_pages.py** — ~237 curated SNPs (high-traffic + pharmacogenomic + methylation cycle) with MyVariant.info enrichment
- **import_snpedia_rsids.py** — ~109K SNPedia rsids
- **populate_trait_metadata.py** — PRS trait metadata for absolute risk
- **build_aeon_reference.py** — Build aeon_reference.parquet from Aeon AF file (one-time). Optional `--with-rsids` for MyVariant.info rsid lookup

## Frontend (Next.js App Router)

### Pages

**/** — Landing page, CTA to upload
**/upload** — Drag-and-drop upload, ancestry auto-detected (manual override under Advanced)
**/dashboard** — File summary, ancestry card, PRS status, carrier screening, SNP traits, PGx summary, report downloads
**/ancestry** — Full ancestry breakdown: superpopulation donut chart, 26-population table, coverage metrics, interpretation guide
**/prs** — PRS results with distribution charts and absolute risk
**/pgx** — Pharmacogenomics gene table with expandable CPIC/DPWG guidelines
**/pgx/[gene]** — Per-gene PGx detail with star allele info and drug guidelines
**/carrier** — Carrier screening details per gene
**/mysnps** — User-specific SNPedia variant matches, trait-based category grouping (geneCategories.ts: TRAIT_CATEGORIES overrides GENE_CATEGORIES)
**/snp** — SNP search/discovery
**/snp/[rsid]** — Public SNP pages (SSR for SEO): variant info, trait associations, ClinVar, PRS membership, PubMed links
**/auth-redirect** — Post-login redirect: checks for existing results, sends to /dashboard or /upload
**/sign-in, /sign-up** — Clerk authentication

### Key Components

**PrsDistributionChart** — Recharts bell curve with percentile, CI band, coverage badge, absolute risk
**SnpInfobox** — Variant detail card
**SnpAssociationsTable** — Filterable trait associations table

## Data Files (app/data/)

- **aeon_reference.parquet** (~6 MB) — 128,097 AILs × 26 populations with chrom+position (build artifact from `scripts/build_aeon_reference.py`)
- **pop_to_superpop.json** (1 KB) — 26 population → 5 superpopulation mapping
- **population_names.json** (3 KB) — Human-readable names, regions, colors for all 26 populations + 5 superpopulations
- **carrier_panel.json** (22 KB) — Pathogenic variant panel for carrier screening
- **cpic_dpwg_guidelines.json** (736 KB) — CPIC/DPWG drug-gene recommendations
- **pgx_alleles.json** (665 KB) — star allele definitions

## Local Dev

```bash
sudo systemctl start postgresql
source .venv/bin/activate
alembic upgrade head
python -m scripts.seed_pgx_definitions
uvicorn app.main:app --reload --port 8000
```

Frontend (requires Node 22 via nvm):
```bash
cd frontend
PATH="/home/dan/.nvm/versions/node/v22.22.0/bin:$PATH"
npm run dev
```

## Testing

~423 tests across 18 test files (all passing):

- **test_parser.py** — 23andMe, AncestryDNA, VCF parsing
- **test_scorer.py** — PRS scoring, mixture normalization, CIs
- **test_trait_matcher.py** / **test_trait_matcher_integration.py** — Trait matching
- **test_ancestry_estimator.py** — MLE ancestry estimation (18 tests: algorithm, dosage, integration)
- **test_absolute_risk.py** — Liability threshold model
- **test_pgx_matcher.py** — Star allele calling, diplotypes
- **test_pgx_report.py** — PGx PDF generation
- **test_carrier_matcher.py** — Carrier screening
- **test_report.py** — General PDF generation
- **test_analysis_pipeline.py** — Full E2E pipeline
- **test_routes_upload.py** — Upload endpoint
- **test_routes_results.py** — Results endpoints
- **test_routes_snp.py** — SNP endpoints
- **test_routes_health.py** — Health check
- **test_account.py** — Account deletion + report download

## Database Migrations

23 migrations in `alembic/versions/` (000–023):

- **000** — Base tables (snps, PRS, analyses, trait hits)
- **001-005** — PRS distributions, trait prevalence, metadata, CIs, ancestry detection
- **006** — SNPedia + user_variants
- **007** — Analysis filename
- **008** — SNP enrichment (CADD, SIFT, PolyPhen, REVEL, ClinVar, gnomAD)
- **009** — Analysis file_format + genome_build
- **010-011** — PGx tables + drug guidelines
- **012** — Blood type results
- **013** — HLA tables (dropped in 023)
- **014** — selected_ancestry field
- **015** — status_detail field
- **016-017** — Blood type columns update + n_systems_determined
- **018** — Carrier status tables
- **019** — FK indexes/constraints
- **020** — Genes table + ClinVar enrichment columns
- **023** — Drop HLA tables (user_hla_results, hla_allele_definitions)

## More Notes

- Use Alembic for database migrations (not auto-create in production)
- CORS: allow localhost:3000 (dev) and genewizard.net (prod)
- All timestamps timezone-aware (UTC)
- Pydantic v2 with `model_config = {"from_attributes": True}`
- Frontend API base URL: env var `NEXT_PUBLIC_API_URL`
- `isal` (Intel ISA-L) for faster gzip decompression
- Background tasks stored in a set to prevent GC
- No arq/Redis — asyncio.create_task() in upload endpoint
- Auth: Clerk frontend (@clerk/nextjs v7), PyJWT + JWKS backend (app/auth.py). Dev mode bypasses auth when no Clerk keys configured.
- Clerk middleware at `frontend/middleware.ts` (project root, NOT inside src/). Public routes: /, /sign-in, /sign-up, /auth-redirect, /privacy, /snp/*, /gene/*
- `DATABASE_URL` is required (no default). Must be set in .env for local dev and Railway env vars for prod.
- `frontend/next.config.ts` sets `outputFileTracingRoot` to the frontend dir to avoid workspace root confusion with the monorepo.
