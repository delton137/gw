/** Gene → category mapping shared by /snp and /mysnps pages. */
export const GENE_CATEGORIES: Record<string, string> = {
  // Alzheimer's & Neurodegeneration
  APOE: "Alzheimer's & Neurodegeneration",
  // Hereditary Cancer
  BRCA1: "Hereditary Cancer",
  BRCA2: "Hereditary Cancer",
  APC: "Hereditary Cancer",
  MUTYH: "Hereditary Cancer",
  // Cardiovascular
  MTHFR: "Cardiovascular",
  HFE: "Cardiovascular",
  CETP: "Cardiovascular",
  APOC1: "Cardiovascular",
  "CDKN2B-AS1": "Cardiovascular",
  // Pharmacogenomics
  CYP2C19: "Pharmacogenomics",
  CYP2C9: "Pharmacogenomics",
  VKORC1: "Pharmacogenomics",
  CYP1A2: "Pharmacogenomics",
  // Metabolism & Nutrition
  MCM6: "Metabolism & Nutrition",
  PPARG: "Metabolism & Nutrition",
  TCF7L2: "Metabolism & Nutrition",
  FTO: "Metabolism & Nutrition",
  FUT2: "Metabolism & Nutrition",
  VDR: "Metabolism & Nutrition",
  GSTP1: "Metabolism & Nutrition",
  AOC1: "Metabolism & Nutrition",
  HNMT: "Metabolism & Nutrition",
  ADD1: "Metabolism & Nutrition",
  AGT: "Metabolism & Nutrition",
  APOA2: "Metabolism & Nutrition",
  FABP2: "Metabolism & Nutrition",
  TAS1R2: "Metabolism & Nutrition",
  TAS1R3: "Metabolism & Nutrition",
  CD36: "Metabolism & Nutrition",
  ADH1C: "Metabolism & Nutrition",
  // Mental Health & Cognition
  BDNF: "Mental Health & Cognition",
  COMT: "Mental Health & Cognition",
  OXTR: "Mental Health & Cognition",
  HTR2A: "Mental Health & Cognition",
  ANKK1: "Mental Health & Cognition",
  OPRM1: "Mental Health & Cognition",
  SLC6A4: "Mental Health & Cognition",
  DRD4: "Mental Health & Cognition",
  TPH2: "Mental Health & Cognition",
  // Physical Traits
  HERC2: "Physical Traits",
  MC1R: "Physical Traits",
  HMGA2: "Physical Traits",
  SLC24A5: "Physical Traits",
  OCA2: "Physical Traits",
  TAS2R38: "Physical Traits",
  OR2M7: "Physical Traits",
  ACTN3: "Physical Traits",
  // Immunity & Autoimmune
  "HLA-DQB1": "Immunity & Autoimmune",
  PTPN22: "Immunity & Autoimmune",
  IL2RA: "Immunity & Autoimmune",
  IL6: "Immunity & Autoimmune",
  HBB: "Immunity & Autoimmune",
  TNF: "Immunity & Autoimmune",
  IFITM3: "Immunity & Autoimmune",
  "HLA-DRA": "Immunity & Autoimmune",
  STAT4: "Immunity & Autoimmune",
  "HLA-DQA1": "Immunity & Autoimmune",
  NOD2: "Immunity & Autoimmune",
  IL23R: "Immunity & Autoimmune",
  "HLA-C": "Immunity & Autoimmune",
  "HLA-DRB1": "Immunity & Autoimmune",
  IRF5: "Immunity & Autoimmune",
  ITGAM: "Immunity & Autoimmune",
  "HLA-B": "Immunity & Autoimmune",
  // Clotting / Thrombophilia
  F5: "Clotting / Thrombophilia",
  F2: "Clotting / Thrombophilia",
  ABO: "Clotting / Thrombophilia",
  F12: "Clotting / Thrombophilia",
  // Diabetes / Metabolic
  KCNJ11: "Diabetes / Metabolic",
  SLC30A8: "Diabetes / Metabolic",
  G6PC2: "Diabetes / Metabolic",
  GCKR: "Diabetes / Metabolic",
  // Longevity / Aging
  FOXO3: "Longevity / Aging",
  PITX2: "Longevity / Aging",
  DAB2IP: "Longevity / Aging",
  TERT: "Longevity / Aging",
  KL: "Longevity / Aging",
  SIRT1: "Longevity / Aging",
  TOMM40: "Alzheimer's & Neurodegeneration",
  // Athletic Performance
  COL1A1: "Athletic Performance",
  PPARGC1A: "Athletic Performance",
  PPARA: "Athletic Performance",
  COL5A1: "Athletic Performance",
  ACE: "Athletic Performance",
  GABPB1: "Athletic Performance",
  // Vision
  MYP11: "Vision",
  LOXL1: "Vision",
  ARMS2: "Vision",
  CFH: "Vision",
  // Bone Health
  GC: "Bone Health",
  DHCR7: "Bone Health",
  CYP2R1: "Bone Health",
  AXIN1: "Bone Health",
  LRP5: "Bone Health",
  // Skin / Hair / Appearance
  KITLG: "Skin / Hair / Appearance",
  TYR: "Skin / Hair / Appearance",
  SLC45A2: "Skin / Hair / Appearance",
  EDAR: "Skin / Hair / Appearance",
  // Sleep / Circadian
  PER3: "Sleep / Circadian",
  ADA: "Sleep / Circadian",
  CLOCK: "Sleep / Circadian",
  MTNR1B: "Sleep / Circadian",
  ADORA2A: "Sleep / Circadian",
  // Fertility / Reproductive
  FSHB: "Fertility / Reproductive",
  ESR1: "Fertility / Reproductive",
  CYP1B1: "Fertility / Reproductive",
  ESR2: "Fertility / Reproductive",
  // Caffeine / Substances
  AHR: "Caffeine / Substances",
  CYP1A1: "Caffeine / Substances",
  ADH1B: "Caffeine / Substances",
  ALDH2: "Caffeine / Substances",
  AUTS2: "Caffeine / Substances",
};

/**
 * Trait-name overrides — checked before gene-based mapping.
 * Allows methylation-cycle traits to be grouped separately even when
 * the gene (e.g. COMT, VDR, MTHFR) already belongs to another category.
 */
export const TRAIT_CATEGORIES: Record<string, string> = {
  "Homocysteine Levels": "Methylation Cycle",
  "COMT Enzyme Activity": "Methylation Cycle",
  "Vitamin D Metabolism": "Methylation Cycle",
  "MAO-A Enzyme Activity": "Methylation Cycle",
  "Acetyl-CoA Metabolism": "Methylation Cycle",
  "Folate Metabolism": "Methylation Cycle",
  "Methionine Synthase / B12 Metabolism": "Methylation Cycle",
  "B12 Recycling / Methionine Synthase Reductase": "Methylation Cycle",
  "Methionine Synthase Reductase Activity": "Methylation Cycle",
  "Betaine-Homocysteine Methylation": "Methylation Cycle",
  "S-Adenosylhomocysteine Metabolism": "Methylation Cycle",
  "Transsulfuration Pathway": "Methylation Cycle",
  "Folate-Mediated One-Carbon Metabolism": "Methylation Cycle",
  "Cardiovascular Disease Risk": "Cardiovascular",
  "Alzheimer's Disease Risk": "Alzheimer's & Neurodegeneration",
};

/** Resolve category: trait-based override first, then gene-based, then "Other". */
export function getCategory(gene: string | null, trait: string): string {
  return TRAIT_CATEGORIES[trait] ?? GENE_CATEGORIES[gene || ""] ?? "Other";
}

/** All 76 genes in the PGx star-allele system. Used to filter "Other"-category
 *  hits from mysnps so they only appear on the dedicated /pgx page. */
export const PGX_GENES = new Set([
  "CYP2D6", "CYP2C19", "CYP2C9", "DPYD", "CYP3A5", "CYP3A4", "TPMT",
  "NUDT15", "UGT1A1", "SLCO1B1", "CYP2B6", "VKORC1", "CYP4F2", "NAT2",
  "HLA-B_5701", "HLA-B_5801", "HLA-A_3101", "CYP1A2", "MTHFR", "ABCB1",
  "ABCG2", "IFNL4", "OPRM1", "COMT", "HTR2A", "HTR2C", "DRD2", "ANKK1",
  "ADRA2A", "ADRB1", "ADRB2", "UGT1A4", "UGT2B15", "GRK4", "GRK5",
  "GRIK4", "F5", "F2", "G6PD", "RYR1", "CYP2C_cluster", "CYP1A1",
  "CYP1B1", "CYP2A6", "CYP2A13", "CYP2C8", "CYP2E1", "CYP2F1",
  "CYP2J2", "CYP2R1", "CYP2S1", "CYP2W1", "CYP3A7", "CYP3A43",
  "CYP4A11", "CYP4A22", "CYP4B1", "CYP17A1", "CYP19A1", "CYP26A1",
  "SLC15A2", "SLC22A2", "SLCO1B3", "SLCO2B1", "NAT1", "GSTM1", "GSTP1",
  "SULT1A1", "POR", "UGT2B7", "XPC", "TBXAS1", "PTGIS", "CFTR",
  "CACNA1S", "IFNL3",
]);

export const CATEGORY_ORDER = [
  "Alzheimer's & Neurodegeneration",
  "Athletic Performance",
  "Bone Health",
  "Caffeine / Substances",
  "Cardiovascular",
  "Clotting / Thrombophilia",
  "Diabetes / Metabolic",
  "Fertility / Reproductive",
  "Hereditary Cancer",
  "Immunity & Autoimmune",
  "Longevity / Aging",
  "Mental Health & Cognition",
  "Metabolism & Nutrition",
  "Methylation Cycle",
  "Pharmacogenomics",
  "Physical Traits",
  "Skin / Hair / Appearance",
  "Sleep / Circadian",
  "Vision",
  "Caffeine / Substances",
];
