/**
 * Shared type definitions for API responses.
 *
 * Canonical interfaces used across multiple pages — kept here to avoid
 * per-page duplication and ensure consistency with the backend contract.
 */

// ---------------------------------------------------------------------------
// Ancestry
// ---------------------------------------------------------------------------

export interface AncestryDetail {
  populations: Record<string, number>;
  superpopulations: Record<string, number>;
  n_markers_used: number;
  n_markers_total: number;
  coverage_quality: string;
  is_admixed: boolean;
}

// ---------------------------------------------------------------------------
// Analysis
// ---------------------------------------------------------------------------

export interface Analysis {
  id: string;
  chip_type: string;
  variant_count: number;
  status: string;
  error_message: string | null;
  detected_ancestry: AncestryDetail | Record<string, number> | null;
  ancestry_method: string | null;
  ancestry_confidence: number | null;
  selected_ancestry: string | null;
  filename: string | null;
  genome_build: string | null;
  pipeline_fast_seconds: number | null;
  is_imputed: boolean | null;
  status_detail?: string;
}

// ---------------------------------------------------------------------------
// PRS
// ---------------------------------------------------------------------------

export interface PrsResult {
  pgs_id: string;
  trait_name: string;
  percentile: number;
  raw_score: number;
  z_score: number | null;
  ref_mean: number | null;
  ref_std: number | null;
  n_variants_matched: number;
  n_variants_total: number;
  ancestry_group_used: string;
  reported_auc: number | null;
  publication_pmid: string | null;
  publication_doi: string | null;
  absolute_risk: number | null;
  population_risk: number | null;
  risk_category: string | null;
  prevalence_source: string | null;
  percentile_lower: number | null;
  percentile_upper: number | null;
  coverage_quality: string | null;
  absolute_risk_lower: number | null;
  absolute_risk_upper: number | null;
}

export interface PrsResponse {
  analysis_id: string;
  prs_status: "computing" | "failed" | "ready";
  prs_status_detail: string | null;
  selected_ancestry: string | null;
  results: PrsResult[];
}

// ---------------------------------------------------------------------------
// Pharmacogenomics
// ---------------------------------------------------------------------------

export interface DefiningVariant {
  rsid: string;
  variant_allele: string;
}

export interface DrugGuideline {
  drug: string;
  recommendation: string;
  implication: string | null;
  strength: string | null;
  pmid: string | null;
}

export interface PgxResult {
  gene: string;
  diplotype: string | null;
  allele1: string | null;
  allele2: string | null;
  allele1_function: string | null;
  allele2_function: string | null;
  phenotype: string | null;
  activity_score: number | null;
  n_variants_tested: number;
  n_variants_total: number;
  calling_method: string;
  confidence: string;
  drugs_affected: string | null;
  clinical_note: string | null;
  gene_description: string | null;
  computed_at: string | null;
  defining_variants: Record<string, DefiningVariant[]> | null;
  guidelines: { cpic: DrugGuideline[]; dpwg: DrugGuideline[] } | null;
  panel_snps: string[];
  variant_genotypes: Record<string, string> | null;
}

// ---------------------------------------------------------------------------
// Trait hits
// ---------------------------------------------------------------------------

export interface TraitHit {
  id: string;
  rsid: string;
  gene: string | null;
  user_genotype: string;
  risk_allele: string | null;
  effect_summary: string | null;
  trait: string;
  effect_description: string;
  risk_level: string;
  evidence_level: string;
}

export interface TraitsResponse {
  analysis_id: string;
  total: number;
  total_snps_in_kb: number;
  unique_snps_matched: number;
  offset: number;
  hits: TraitHit[];
}

// ---------------------------------------------------------------------------
// ClinVar
// ---------------------------------------------------------------------------

export interface ClinvarHit {
  rsid: string;
  user_genotype: string;
  gene: string | null;
  clinvar_significance: string;
  clinvar_conditions: string | null;
  review_stars: number | null;
  allele_id: number | null;
  functional_class: string | null;
  chrom: string | null;
  position: number | null;
  ref_allele: string | null;
  alt_allele: string | null;
}

export interface ClinvarResponse {
  analysis_id: string;
  total: number;
  counts: Record<string, number>;
  offset: number;
  hits: ClinvarHit[];
}

// ---------------------------------------------------------------------------
// Carrier screening
// ---------------------------------------------------------------------------

export interface CarrierVariant {
  rsid: string;
  name: string;
  genotype: string;
  pathogenic_allele: string;
  pathogenic_allele_count: number;
  classification: string;
  hgvs_p: string | null;
  population_frequency: number | null;
}

export interface CarrierGeneResult {
  gene: string;
  condition: string;
  inheritance: string;
  severity: string;
  status: string;
  variants_detected: CarrierVariant[];
  variants_tested: number;
  total_variants_screened: number;
  total_pathogenic_alleles: number;
  carrier_frequencies: Record<string, string>;
  condition_description: string;
  treatment_summary: string;
  penetrance_note: string;
  key_pmids: number[];
  limitations: string;
  clinical_note: string;
  panel_rsids: string[];
  variant_genotypes: Record<string, string | null>;
}

export interface CarrierStatusResult {
  results_json: Record<string, CarrierGeneResult>;
  n_genes_screened: number;
  n_carrier_genes: number;
  n_affected_flags: number;
  computed_at: string | null;
}

// ---------------------------------------------------------------------------
// Variants (SNPedia)
// ---------------------------------------------------------------------------

export interface VariantsResponse {
  analysis_id: string;
  filename: string | null;
  total: number;
  snpedia_total: number;
  offset: number;
  variants: { rsid: string }[];
}

// ---------------------------------------------------------------------------
// GWAS
// ---------------------------------------------------------------------------

export interface GwasScore {
  study_id: string;
  trait: string;
  category: string;
  citation: string | null;
  pmid: string | null;
  n_snps_in_score: number;
  raw_score: number;
  percentile: number | null;
  z_score: number | null;
  ref_mean: number | null;
  ref_std: number | null;
  ancestry_group_used: string;
  n_variants_matched: number;
  n_variants_total: number;
}

export interface GwasResponse {
  analysis_id: string;
  gwas_status: "computing" | "failed" | "ready";
  total_scores: number;
  categories: Record<string, GwasScore[]>;
}
