"""Pharmacogenomics star allele definitions for diplotype inference.

Three data structures:
- PGX_GENE_DEFS: Per-gene configuration (calling method, tier, default allele)
- PGX_STAR_ALLELES: rsID → star allele mappings with function annotations
- PGX_DIPLOTYPE_PHENOTYPES: Function-pair → phenotype mappings for 'simple' calling method genes

"""

# ---------------------------------------------------------------------------
# 1. PGX_GENE_DEFS — Per-gene configuration
# ---------------------------------------------------------------------------

PGX_GENE_DEFS = [
    # -----------------------------------------------------------------------
    # Tier 1: CPIC Level A — strongest clinical evidence
    # -----------------------------------------------------------------------

    # Activity-score genes
    {"gene": "CYP2D6", "calling_method": "activity_score", "tier": 1, "default_allele": "*1",
     "description": "Cytochrome P450 2D6 — metabolizes ~25% of all drugs including codeine, tamoxifen, antidepressants, antipsychotics"},
    {"gene": "CYP2C19", "calling_method": "activity_score", "tier": 1, "default_allele": "*1",
     "description": "Cytochrome P450 2C19 — metabolizes clopidogrel, PPIs, SSRIs, voriconazole"},
    {"gene": "CYP2C9", "calling_method": "activity_score", "tier": 1, "default_allele": "*1",
     "description": "Cytochrome P450 2C9 — metabolizes warfarin, phenytoin, NSAIDs"},
    {"gene": "DPYD", "calling_method": "activity_score", "tier": 1, "default_allele": "*1",
     "description": "Dihydropyrimidine dehydrogenase — metabolizes fluoropyrimidine chemotherapy (5-FU, capecitabine)"},

    # Simple genes
    {"gene": "CYP3A5", "calling_method": "simple", "tier": 1, "default_allele": "*1",
     "description": "Cytochrome P450 3A5 — metabolizes tacrolimus, sirolimus"},
    {"gene": "CYP3A4", "calling_method": "simple", "tier": 1, "default_allele": "*1",
     "description": "Cytochrome P450 3A4 — metabolizes >50% of all drugs; most abundant hepatic CYP"},
    {"gene": "TPMT", "calling_method": "simple", "tier": 1, "default_allele": "*1",
     "description": "Thiopurine S-methyltransferase — inactivates azathioprine, 6-mercaptopurine, thioguanine"},
    {"gene": "NUDT15", "calling_method": "simple", "tier": 1, "default_allele": "*1",
     "description": "Nudix hydrolase 15 — modulates thiopurine toxicity, especially in East Asian populations"},
    {"gene": "UGT1A1", "calling_method": "simple", "tier": 1, "default_allele": "*1",
     "description": "UDP-glucuronosyltransferase 1A1 — glucuronidates bilirubin and irinotecan (SN-38)"},
    {"gene": "SLCO1B1", "calling_method": "simple", "tier": 1, "default_allele": "*1A",
     "description": "Solute carrier OATP1B1 — hepatic uptake of statins; variants increase myopathy risk"},
    {"gene": "CYP2B6", "calling_method": "simple", "tier": 1, "default_allele": "*1",
     "description": "Cytochrome P450 2B6 — metabolizes efavirenz, nevirapine, methadone, bupropion"},
    {"gene": "VKORC1", "calling_method": "simple", "tier": 1, "default_allele": "ref",
     "description": "Vitamin K epoxide reductase complex subunit 1 — warfarin target; variants alter dose requirements"},
    {"gene": "CYP4F2", "calling_method": "simple", "tier": 1, "default_allele": "*1",
     "description": "Cytochrome P450 4F2 — vitamin K1 oxidase; variants affect warfarin dose"},

    # Count gene
    {"gene": "NAT2", "calling_method": "count", "tier": 1, "default_allele": "*4",
     "description": "N-acetyltransferase 2 — acetylates isoniazid, sulfonamides, hydralazine, caffeine"},

    # Binary (HLA) genes
    {"gene": "HLA-B_5701", "calling_method": "binary", "tier": 1, "default_allele": "negative",
     "description": "HLA-B*57:01 — abacavir hypersensitivity; MANDATORY pre-prescription test"},
    {"gene": "HLA-B_5801", "calling_method": "binary", "tier": 1, "default_allele": "negative",
     "description": "HLA-B*58:01 — allopurinol-induced SJS/TEN; pre-test recommended in high-risk populations"},
    {"gene": "HLA-A_3101", "calling_method": "binary", "tier": 1, "default_allele": "negative",
     "description": "HLA-A*31:01 — carbamazepine/oxcarbazepine hypersensitivity risk"},

    # -----------------------------------------------------------------------
    # Tier 2: Informational / emerging evidence
    # -----------------------------------------------------------------------
    {"gene": "CYP1A2", "calling_method": "simple", "tier": 2, "default_allele": "*1",
     "description": "Cytochrome P450 1A2 — metabolizes caffeine, theophylline, clozapine; inducible by smoking"},
    {"gene": "MTHFR", "calling_method": "simple", "tier": 2, "default_allele": "CC",
     "description": "Methylenetetrahydrofolate reductase — folate metabolism; C677T variant reduces enzyme activity"},
    {"gene": "ABCB1", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "P-glycoprotein (MDR1) — efflux transporter affecting oral bioavailability of many drugs"},
    {"gene": "ABCG2", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "Breast cancer resistance protein (BCRP) — efflux transporter; Q141K affects rosuvastatin levels"},
    {"gene": "IFNL4", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "Interferon lambda 4 — rs12979860 genotype predicts HCV treatment response and spontaneous clearance"},

    # Tier 2: New simple genes — neuropharmacology & receptor pharmacogenomics
    {"gene": "OPRM1", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "Mu-opioid receptor — mediates opioid analgesia response; A118G variant affects morphine, codeine, fentanyl efficacy"},
    {"gene": "COMT", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "Catechol-O-methyltransferase — degrades catecholamine neurotransmitters; Val158Met affects pain sensitivity and psychiatric drug response"},
    {"gene": "HTR2A", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "Serotonin 5-HT2A receptor — rs7997012 associated with SSRI and antipsychotic response"},
    {"gene": "HTR2C", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "Serotonin 5-HT2C receptor — rs3813929 linked to antipsychotic-induced weight gain"},
    {"gene": "DRD2", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "Dopamine D2 receptor — rs1799978 affects antipsychotic response and extrapyramidal side effects"},
    {"gene": "ANKK1", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "Ankyrin repeat and kinase domain containing 1 — DRD2-adjacent; Taq1A (rs1800497) affects dopamine signaling"},
    {"gene": "ADRA2A", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "Alpha-2A adrenergic receptor — rs1800544 affects response to guanfacine and methylphenidate for ADHD"},
    {"gene": "ADRB1", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "Beta-1 adrenergic receptor — Arg389Gly affects beta-blocker response for heart failure and hypertension"},
    {"gene": "ADRB2", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "Beta-2 adrenergic receptor — Arg16Gly and Gln27Glu affect bronchodilator response in asthma"},

    # Tier 2: New simple genes — UGT enzymes
    {"gene": "UGT1A4", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "UDP-glucuronosyltransferase 1A4 — glucuronidates lamotrigine; variants alter seizure drug levels"},
    {"gene": "UGT2B15", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "UDP-glucuronosyltransferase 2B15 — metabolizes lorazepam and oxazepam; D85Y affects clearance"},

    # Tier 2: New simple genes — kinases & glutamate receptor
    {"gene": "GRK4", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "G protein-coupled receptor kinase 4 — rs1024323 and rs1801058 affect beta-adrenergic signaling and hypertension treatment"},
    {"gene": "GRK5", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "G protein-coupled receptor kinase 5 — rs2230345 affects beta-adrenergic receptor desensitization and heart failure outcomes"},
    {"gene": "GRIK4", "calling_method": "simple", "tier": 2, "default_allele": "ref",
     "description": "Glutamate ionotropic receptor kainate type subunit 4 — rs1954787 associated with SSRI antidepressant response"},

    # Tier 2: New binary genes — coagulation, hemolysis, anesthesia safety
    {"gene": "F5", "calling_method": "binary", "tier": 2, "default_allele": "negative",
     "description": "Coagulation Factor V — Factor V Leiden (rs6025) increases risk of venous thromboembolism; affects oral contraceptive safety"},
    {"gene": "F2", "calling_method": "binary", "tier": 2, "default_allele": "negative",
     "description": "Prothrombin/Factor II — G20210A mutation (rs1799963) increases thrombosis risk; affects anticoagulant prescribing"},
    {"gene": "G6PD", "calling_method": "simple", "tier": 2, "default_allele": "*1",
     "description": "Glucose-6-phosphate dehydrogenase — deficiency causes hemolytic anemia with oxidant drugs (rasburicase, primaquine, dapsone)"},
    {"gene": "RYR1", "calling_method": "simple", "tier": 2, "default_allele": "*1",
     "description": "Ryanodine receptor 1 — mutations cause malignant hyperthermia from volatile anesthetics and succinylcholine"},
    {"gene": "CYP2C_cluster", "calling_method": "binary", "tier": 2, "default_allele": "negative",
     "description": "CYP2C cluster variant rs12777823 — affects warfarin dose requirements in African American patients"},

    # -----------------------------------------------------------------------
    # Tier 3: Stargazer-imported genes — extended pharmacogenomic coverage
    # -----------------------------------------------------------------------

    # CYP enzymes
    {"gene": "CYP1A1", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 1A1 — metabolizes PAHs and estrogens; variants affect cancer susceptibility"},
    {"gene": "CYP1B1", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 1B1 — metabolizes estradiol, PAHs; variants linked to glaucoma and cancer risk"},
    {"gene": "CYP2A6", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 2A6 — primary nicotine and cotinine metabolizer; affects smoking behavior and cessation therapy"},
    {"gene": "CYP2A13", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 2A13 — metabolizes NNK (tobacco carcinogen) in respiratory tract"},
    {"gene": "CYP2C8", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 2C8 — metabolizes paclitaxel, amodiaquine, repaglinide, rosiglitazone"},
    {"gene": "CYP2E1", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 2E1 — metabolizes ethanol, acetaminophen, volatile anesthetics; inducible by alcohol"},
    {"gene": "CYP2F1", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 2F1 — expressed in lung; metabolizes naphthalene and styrene"},
    {"gene": "CYP2J2", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 2J2 — metabolizes arachidonic acid to EETs; expressed in cardiovascular tissue"},
    {"gene": "CYP2R1", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 2R1 — vitamin D 25-hydroxylase; variants affect vitamin D levels"},
    {"gene": "CYP2S1", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 2S1 — expressed in extrahepatic tissues; metabolizes some anti-cancer prodrugs"},
    {"gene": "CYP2W1", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 2W1 — tumor-selective expression; potential prodrug activation target"},
    {"gene": "CYP3A7", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 3A7 — fetal CYP3A; adult expression variants affect tacrolimus and midazolam metabolism"},
    {"gene": "CYP3A43", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 3A43 — low hepatic expression; contributes to testosterone metabolism"},
    {"gene": "CYP4A11", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 4A11 — omega-hydroxylates arachidonic acid to 20-HETE; variants affect blood pressure"},
    {"gene": "CYP4A22", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 4A22 — arachidonic acid omega-hydroxylase in kidney; variants affect renal function"},
    {"gene": "CYP4B1", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 4B1 — metabolizes 4-ABP and 2-aminofluorene; lung carcinogen bioactivation"},
    {"gene": "CYP17A1", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 17A1 — steroid 17-hydroxylase; target of abiraterone for prostate cancer"},
    {"gene": "CYP19A1", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 19A1 (aromatase) — estrogen synthesis; target of letrozole, anastrozole"},
    {"gene": "CYP26A1", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Cytochrome P450 26A1 — retinoic acid catabolism; affects vitamin A metabolism and retinoid therapy"},

    # Transporters
    {"gene": "SLC15A2", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Peptide transporter PEPT2 — renal reabsorption of peptide-like drugs (cephalosporins, ACE inhibitors)"},
    {"gene": "SLC22A2", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Organic cation transporter OCT2 — renal secretion of metformin, cisplatin; variants affect nephrotoxicity"},
    {"gene": "SLCO1B3", "calling_method": "activity_score", "tier": 3, "default_allele": "*1A",
     "description": "Solute carrier OATP1B3 — hepatic uptake of statins, rifampin, methotrexate"},
    {"gene": "SLCO2B1", "calling_method": "activity_score", "tier": 3, "default_allele": "*1",
     "description": "Solute carrier OATP2B1 — intestinal/hepatic uptake of statins, fexofenadine"},

    # Transferases and other enzymes
    {"gene": "NAT1", "calling_method": "simple", "tier": 3, "default_allele": "*1",
     "description": "N-acetyltransferase 1 — acetylates aromatic amines; variants affect bladder cancer risk"},
    {"gene": "GSTM1", "calling_method": "simple", "tier": 3, "default_allele": "*1",
     "description": "Glutathione S-transferase Mu 1 — detoxifies electrophilic compounds; null genotype common (~50%)"},
    {"gene": "GSTP1", "calling_method": "simple", "tier": 3, "default_allele": "*1",
     "description": "Glutathione S-transferase Pi 1 — detoxifies platinum chemotherapy; I105V affects cisplatin/oxaliplatin response"},
    {"gene": "SULT1A1", "calling_method": "simple", "tier": 3, "default_allele": "*1",
     "description": "Sulfotransferase 1A1 — sulfonates catecholamines, thyroid hormones, tamoxifen metabolites"},
    {"gene": "POR", "calling_method": "simple", "tier": 3, "default_allele": "*1",
     "description": "NADPH-cytochrome P450 oxidoreductase — electron donor for all microsomal CYPs; variants affect CYP activity globally"},
    {"gene": "UGT2B7", "calling_method": "simple", "tier": 3, "default_allele": "*1",
     "description": "UDP-glucuronosyltransferase 2B7 — glucuronidates morphine, zidovudine, valproic acid"},
    {"gene": "XPC", "calling_method": "simple", "tier": 3, "default_allele": "*1",
     "description": "Xeroderma pigmentosum group C — DNA repair; variants affect cisplatin chemotherapy response"},
    {"gene": "TBXAS1", "calling_method": "simple", "tier": 3, "default_allele": "*1",
     "description": "Thromboxane A synthase 1 — converts PGH2 to TXA2; variants affect aspirin response and thrombosis"},
    {"gene": "PTGIS", "calling_method": "simple", "tier": 3, "default_allele": "*1",
     "description": "Prostacyclin synthase — converts PGH2 to prostacyclin; variants affect vascular function"},

    # Disease-associated genes
    {"gene": "CFTR", "calling_method": "simple", "tier": 3, "default_allele": "*1",
     "description": "Cystic fibrosis transmembrane conductance regulator — CFTR modulators (ivacaftor, lumacaftor) are mutation-specific"},
    {"gene": "CACNA1S", "calling_method": "simple", "tier": 3, "default_allele": "*1",
     "description": "Calcium voltage-gated channel subunit alpha1 S — malignant hyperthermia susceptibility with volatile anesthetics"},
    {"gene": "IFNL3", "calling_method": "simple", "tier": 3, "default_allele": "*1",
     "description": "Interferon lambda 3 (IL28B) — rs12979860 predicts HCV treatment response and spontaneous clearance"},
]


# ---------------------------------------------------------------------------
# 2. PGX_STAR_ALLELES — rsID → star allele mappings
# ---------------------------------------------------------------------------

PGX_STAR_ALLELES = [
    # ===================================================================
    # CYP2D6 (activity_score gene)
    # ===================================================================
    {"gene": "CYP2D6", "star_allele": "*2", "rsid": "rs16947",
     "variant_allele": "A", "function": "normal_function", "activity_score": 1.0,
     "clinical_significance": "R296C — normal function defining variant",
     "source": "CPIC"},
    {"gene": "CYP2D6", "star_allele": "*3", "rsid": "rs35742686",
     "variant_allele": "C", "function": "no_function", "activity_score": 0,
     "clinical_significance": "2549delA frameshift — complete loss of function",
     "source": "CPIC"},
    {"gene": "CYP2D6", "star_allele": "*4", "rsid": "rs3892097",
     "variant_allele": "T", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Splice defect — most common null allele in Europeans (~20%)",
     "source": "CPIC"},
    {"gene": "CYP2D6", "star_allele": "*6", "rsid": "rs5030655",
     "variant_allele": "C", "function": "no_function", "activity_score": 0,
     "clinical_significance": "1707delT frameshift — complete loss of function",
     "source": "CPIC"},
    {"gene": "CYP2D6", "star_allele": "*9", "rsid": "rs5030656",
     "variant_allele": "C", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "K281del — reduced but not absent activity",
     "source": "CPIC"},
    {"gene": "CYP2D6", "star_allele": "*10", "rsid": "rs1065852",
     "variant_allele": "A", "function": "decreased_function", "activity_score": 0.25,
     "clinical_significance": "P34S — unstable protein, most common in East Asians (~40%)",
     "source": "CPIC"},
    {"gene": "CYP2D6", "star_allele": "*12", "rsid": "rs5030862",
     "variant_allele": "T", "function": "no_function", "activity_score": 0,
     "clinical_significance": "G212E — complete loss of function (rare)",
     "source": "CPIC"},
    {"gene": "CYP2D6", "star_allele": "*17", "rsid": "rs28371706",
     "variant_allele": "A", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "T107I — reduced function, common in African populations",
     "source": "CPIC"},
    {"gene": "CYP2D6", "star_allele": "*41", "rsid": "rs28371725",
     "variant_allele": "T", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "Aberrant splicing — reduced mRNA expression",
     "source": "CPIC"},
    # CYP2D6 haplotype phasing marker
    {"gene": "CYP2D6", "star_allele": "*2_tag", "rsid": "rs1135840",
     "variant_allele": "C", "function": "normal_function", "activity_score": 1.0,
     "clinical_significance": "4180G>C — haplotype phasing marker for *2",
     "source": ""},
    # CYP2D6 expanded alleles (WGS coverage)
    {"gene": "CYP2D6", "star_allele": "*2A", "rsid": "rs16947",
     "variant_allele": "A", "function": "normal_function", "activity_score": 1.0,
     "clinical_significance": "R296C + 4180G>C — *2A is defined by both rs16947 and rs1135840",
     "source": "CPIC"},
    {"gene": "CYP2D6", "star_allele": "*7", "rsid": "rs5030867",
     "variant_allele": "G", "function": "no_function", "activity_score": 0,
     "clinical_significance": "H324P — non-functional enzyme",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*8", "rsid": "rs5030865",
     "variant_allele": "A", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Stop codon — truncated non-functional protein",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*11", "rsid": "rs5030863",
     "variant_allele": "G", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Splice defect — non-functional",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*14", "rsid": "rs5030866",
     "variant_allele": "T", "function": "no_function", "activity_score": 0,
     "clinical_significance": "G169R + P34S — non-functional compound variant",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*15", "rsid": "rs774671100",
     "variant_allele": "CA", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Frameshift — non-functional",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*19", "rsid": "rs72549353",
     "variant_allele": "del", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Frameshift — non-functional",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*20", "rsid": "rs72549354",
     "variant_allele": "TC", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Frameshift — non-functional",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*21", "rsid": "rs72549355",
     "variant_allele": "del", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Frameshift — non-functional",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*29", "rsid": "rs59421388",
     "variant_allele": "T", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "V136I — reduced function, common in African populations",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*30", "rsid": "rs28371717",
     "variant_allele": "T", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Splice site — non-functional",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*31", "rsid": "rs267608275",
     "variant_allele": "del", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Frameshift — non-functional",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*35", "rsid": "rs769258",
     "variant_allele": "T", "function": "normal_function", "activity_score": 1.0,
     "clinical_significance": "V11M — normal function, sometimes considered *2 subgroup",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*36", "rsid": "rs28371730",
     "variant_allele": "A", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Gene conversion with CYP2D7 — non-functional",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*40", "rsid": "rs72549356",
     "variant_allele": "del", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Frameshift — non-functional (very rare)",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*42", "rsid": "rs72549357",
     "variant_allele": "del", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Splice variant — non-functional (very rare)",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*49", "rsid": "rs1135822",
     "variant_allele": "T", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "F120I — reduced activity",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*56", "rsid": "rs28371738",
     "variant_allele": "del", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Frameshift — non-functional",
     "source": ""},
    {"gene": "CYP2D6", "star_allele": "*59", "rsid": "rs79292917",
     "variant_allele": "T", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Splice site variant — non-functional",
     "source": ""},

    # ===================================================================
    # CYP2C19 (activity_score gene)
    # ===================================================================
    {"gene": "CYP2C19", "star_allele": "*2", "rsid": "rs4244285",
     "variant_allele": "A", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Splice defect — most common loss-of-function allele",
     "source": "CPIC"},
    {"gene": "CYP2C19", "star_allele": "*3", "rsid": "rs4986893",
     "variant_allele": "A", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Premature stop codon — complete loss of function",
     "source": "CPIC"},
    {"gene": "CYP2C19", "star_allele": "*17", "rsid": "rs12248560",
     "variant_allele": "T", "function": "increased_function", "activity_score": 1.5,
     "clinical_significance": "Promoter variant — increased CYP2C19 expression",
     "source": "CPIC"},
    # CYP2C19 expanded alleles (WGS coverage)
    {"gene": "CYP2C19", "star_allele": "*4", "rsid": "rs28399504",
     "variant_allele": "G", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Initiator codon variant — no protein produced",
     "source": "CPIC"},
    {"gene": "CYP2C19", "star_allele": "*5", "rsid": "rs56337013",
     "variant_allele": "T", "function": "no_function", "activity_score": 0,
     "clinical_significance": "R433W — non-functional enzyme",
     "source": ""},
    {"gene": "CYP2C19", "star_allele": "*6", "rsid": "rs72552267",
     "variant_allele": "A", "function": "no_function", "activity_score": 0,
     "clinical_significance": "R132Q — non-functional enzyme",
     "source": ""},
    {"gene": "CYP2C19", "star_allele": "*7", "rsid": "rs72558186",
     "variant_allele": "A", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Splice site variant — non-functional",
     "source": ""},
    {"gene": "CYP2C19", "star_allele": "*8", "rsid": "rs41291556",
     "variant_allele": "C", "function": "no_function", "activity_score": 0,
     "clinical_significance": "W120R — non-functional enzyme",
     "source": ""},
    {"gene": "CYP2C19", "star_allele": "*9", "rsid": "rs17884712",
     "variant_allele": "A", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "H251R — reduced function",
     "source": ""},
    {"gene": "CYP2C19", "star_allele": "*10", "rsid": "rs6413438",
     "variant_allele": "T", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "P227L — reduced function",
     "source": ""},
    {"gene": "CYP2C19", "star_allele": "*16", "rsid": "rs192154563",
     "variant_allele": "T", "function": "no_function", "activity_score": 0,
     "clinical_significance": "R442C — non-functional",
     "source": ""},
    {"gene": "CYP2C19", "star_allele": "*35", "rsid": "rs12769205",
     "variant_allele": "G", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Intronic — associated with reduced CYP2C19 function",
     "source": ""},

    # ===================================================================
    # CYP2C9 (activity_score gene)
    # ===================================================================
    {"gene": "CYP2C9", "star_allele": "*2", "rsid": "rs1799853",
     "variant_allele": "T", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "R144C — ~30% reduced warfarin metabolism",
     "source": "CPIC"},
    {"gene": "CYP2C9", "star_allele": "*3", "rsid": "rs1057910",
     "variant_allele": "C", "function": "no_function", "activity_score": 0,
     "clinical_significance": "I359L — ~80% reduced warfarin metabolism",
     "source": "CPIC"},
    {"gene": "CYP2C9", "star_allele": "*4", "rsid": "rs9332239",
     "variant_allele": "T", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "I359T — rare reduced function",
     "source": ""},
    {"gene": "CYP2C9", "star_allele": "*5", "rsid": "rs28371686",
     "variant_allele": "G", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Loss of function — found primarily in African Americans",
     "source": "CPIC"},
    {"gene": "CYP2C9", "star_allele": "*6", "rsid": "rs9332131",
     "variant_allele": "G", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Frameshift deletion — complete loss of function",
     "source": "CPIC"},
    {"gene": "CYP2C9", "star_allele": "*8", "rsid": "rs7900194",
     "variant_allele": "A", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "Reduced function — important in African Americans",
     "source": "CPIC"},
    {"gene": "CYP2C9", "star_allele": "*11", "rsid": "rs28371685",
     "variant_allele": "T", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "R150H — reduced function",
     "source": ""},
    {"gene": "CYP2C9", "star_allele": "*12", "rsid": "rs28371674",
     "variant_allele": "T", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "P489S — reduced function (rare)",
     "source": ""},
    # CYP2C9 expanded alleles (WGS coverage)
    {"gene": "CYP2C9", "star_allele": "*13", "rsid": "rs72558187",
     "variant_allele": "C", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "L90P — reduced function",
     "source": ""},
    {"gene": "CYP2C9", "star_allele": "*14", "rsid": "rs72558188",
     "variant_allele": "A", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "R125H — reduced function",
     "source": ""},
    {"gene": "CYP2C9", "star_allele": "*15", "rsid": "rs72558189",
     "variant_allele": "T", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "S162X — reduced function",
     "source": ""},
    {"gene": "CYP2C9", "star_allele": "*25", "rsid": "rs367543002",
     "variant_allele": "T", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Non-functional — very rare",
     "source": ""},
    {"gene": "CYP2C9", "star_allele": "*26", "rsid": "rs362306684",
     "variant_allele": "A", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Non-functional — very rare",
     "source": ""},
    {"gene": "CYP2C9", "star_allele": "*28", "rsid": "rs56165452",
     "variant_allele": "A", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "Reduced function — found in diverse populations",
     "source": ""},
    {"gene": "CYP2C9", "star_allele": "*29", "rsid": "rs182132442",
     "variant_allele": "A", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "Reduced function",
     "source": ""},
    {"gene": "CYP2C9", "star_allele": "*30", "rsid": "rs72558190",
     "variant_allele": "T", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "Reduced function",
     "source": ""},
    {"gene": "CYP2C9", "star_allele": "*35", "rsid": "rs767576260",
     "variant_allele": "T", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Non-functional — very rare",
     "source": ""},
    {"gene": "CYP2C9", "star_allele": "*44", "rsid": "rs2017319123",
     "variant_allele": "G", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Non-functional — very rare",
     "source": ""},

    # ===================================================================
    # DPYD (activity_score gene)
    # ===================================================================
    {"gene": "DPYD", "star_allele": "*2A", "rsid": "rs3918290",
     "variant_allele": "T", "function": "no_function", "activity_score": 0,
     "clinical_significance": "IVS14+1G>A splice — LIFE-THREATENING 5-FU toxicity",
     "source": "CPIC"},
    {"gene": "DPYD", "star_allele": "*13", "rsid": "rs55886062",
     "variant_allele": "C", "function": "no_function", "activity_score": 0,
     "clinical_significance": "I560S — complete loss of DPD function",
     "source": "CPIC"},
    {"gene": "DPYD", "star_allele": "D949V", "rsid": "rs67376798",
     "variant_allele": "A", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "D949V — reduced DPD activity",
     "source": "CPIC"},
    {"gene": "DPYD", "star_allele": "HapB3", "rsid": "rs75017182",
     "variant_allele": "C", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "Haplotype B3 — partial DPD reduction",
     "source": "CPIC"},
    # DPYD expanded alleles (WGS coverage)
    {"gene": "DPYD", "star_allele": "*3", "rsid": "rs72549303",
     "variant_allele": "T", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Premature stop — complete loss of function",
     "source": "CPIC"},
    {"gene": "DPYD", "star_allele": "*7", "rsid": "rs72549309",
     "variant_allele": "C", "function": "no_function", "activity_score": 0,
     "clinical_significance": "Splice variant — loss of function",
     "source": "CPIC"},
    {"gene": "DPYD", "star_allele": "*8", "rsid": "rs1801268",
     "variant_allele": "A", "function": "no_function", "activity_score": 0,
     "clinical_significance": "R886H — complete loss of function",
     "source": "CPIC"},
    {"gene": "DPYD", "star_allele": "*10", "rsid": "rs1801267",
     "variant_allele": "A", "function": "no_function", "activity_score": 0,
     "clinical_significance": "H665R — complete loss of function",
     "source": "CPIC"},
    {"gene": "DPYD", "star_allele": "*12", "rsid": "rs78060119",
     "variant_allele": "A", "function": "no_function", "activity_score": 0,
     "clinical_significance": "G926V — complete loss of function",
     "source": "CPIC"},
    {"gene": "DPYD", "star_allele": "rs115232898", "rsid": "rs115232898",
     "variant_allele": "C", "function": "decreased_function", "activity_score": 0.5,
     "clinical_significance": "Reduced DPD activity — clinically significant",
     "source": "CPIC"},

    # ===================================================================
    # CYP3A5 (simple gene)
    # ===================================================================
    {"gene": "CYP3A5", "star_allele": "*3", "rsid": "rs776746",
     "variant_allele": "C", "function": "no_function", "activity_score": None,
     "clinical_significance": "Splice variant — non-functional protein (85-95% of Europeans)",
     "source": "CPIC"},
    {"gene": "CYP3A5", "star_allele": "*6", "rsid": "rs10264272",
     "variant_allele": "T", "function": "no_function", "activity_score": None,
     "clinical_significance": "Exon skipping — loss of function",
     "source": "CPIC"},
    {"gene": "CYP3A5", "star_allele": "*7", "rsid": "rs41303343",
     "variant_allele": "TA", "function": "no_function", "activity_score": None,
     "clinical_significance": "Frameshift — loss of function (African populations)",
     "source": ""},

    # ===================================================================
    # CYP3A4 (simple gene)
    # ===================================================================
    {"gene": "CYP3A4", "star_allele": "*1B", "rsid": "rs2740574",
     "variant_allele": "C", "function": "uncertain_function", "activity_score": None,
     "clinical_significance": "Promoter variant — may alter CYP3A4 expression",
     "source": ""},
    {"gene": "CYP3A4", "star_allele": "*22", "rsid": "rs35599367",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Intron 6 — ~50% reduced mRNA expression",
     "source": "CPIC"},

    # ===================================================================
    # TPMT (simple gene) — *3A is multi-SNP
    # ===================================================================
    {"gene": "TPMT", "star_allele": "*2", "rsid": "rs1800462",
     "variant_allele": "G", "function": "no_function", "activity_score": None,
     "clinical_significance": "A80P — rapid degradation",
     "source": "CPIC"},
    # *3A requires BOTH rs1800460 AND rs1142345
    {"gene": "TPMT", "star_allele": "*3A", "rsid": "rs1800460",
     "variant_allele": "T", "function": "no_function", "activity_score": None,
     "clinical_significance": "A154T — protein misfolding (requires BOTH rs1800460+rs1142345)",
     "source": "CPIC"},
    {"gene": "TPMT", "star_allele": "*3A", "rsid": "rs1142345",
     "variant_allele": "C", "function": "no_function", "activity_score": None,
     "clinical_significance": "Y240C — protein misfolding (part of *3A haplotype)",
     "source": "CPIC"},
    # *3B = rs1800460 alone (without rs1142345)
    {"gene": "TPMT", "star_allele": "*3B", "rsid": "rs1800460",
     "variant_allele": "T", "function": "no_function", "activity_score": None,
     "clinical_significance": "A154T alone (without rs1142345)",
     "source": ""},
    # *3C = rs1142345 alone (without rs1800460)
    {"gene": "TPMT", "star_allele": "*3C", "rsid": "rs1142345",
     "variant_allele": "C", "function": "no_function", "activity_score": None,
     "clinical_significance": "Y240C alone (without rs1800460) — most common in East Asian/African",
     "source": "CPIC"},
    # TPMT expanded alleles (WGS coverage)
    {"gene": "TPMT", "star_allele": "*4", "rsid": "rs1800584",
     "variant_allele": "T", "function": "no_function", "activity_score": None,
     "clinical_significance": "Splice defect — loss of function (rare)",
     "source": ""},
    {"gene": "TPMT", "star_allele": "*11", "rsid": "rs72552739",
     "variant_allele": "T", "function": "no_function", "activity_score": None,
     "clinical_significance": "Y240S — non-functional (very rare)",
     "source": ""},
    {"gene": "TPMT", "star_allele": "*14", "rsid": "rs72552740",
     "variant_allele": "G", "function": "no_function", "activity_score": None,
     "clinical_significance": "Loss of function — very rare",
     "source": ""},
    {"gene": "TPMT", "star_allele": "*15", "rsid": "rs72552741",
     "variant_allele": "T", "function": "no_function", "activity_score": None,
     "clinical_significance": "Loss of function — very rare",
     "source": ""},
    {"gene": "TPMT", "star_allele": "*23", "rsid": "rs72552745",
     "variant_allele": "G", "function": "no_function", "activity_score": None,
     "clinical_significance": "Loss of function — very rare",
     "source": ""},

    # ===================================================================
    # NUDT15 (simple gene)
    # ===================================================================
    {"gene": "NUDT15", "star_allele": "*3", "rsid": "rs116855232",
     "variant_allele": "T", "function": "no_function", "activity_score": None,
     "clinical_significance": "R139C — critical in East Asian populations (7-10%)",
     "source": "CPIC"},
    {"gene": "NUDT15", "star_allele": "*2", "rsid": "rs186364861",
     "variant_allele": "A", "function": "no_function", "activity_score": None,
     "clinical_significance": "Loss of function — very rare",
     "source": "CPIC"},
    # NUDT15 expanded alleles (WGS coverage)
    {"gene": "NUDT15", "star_allele": "*9", "rsid": "rs746071566",
     "variant_allele": "G", "function": "no_function", "activity_score": None,
     "clinical_significance": "Loss of function — very rare",
     "source": "CPIC"},

    # ===================================================================
    # UGT1A1 (simple gene)
    # ===================================================================
    {"gene": "UGT1A1", "star_allele": "*80", "rsid": "rs887829",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Proxy for *28 TA repeat — reduced UGT1A1 expression",
     "source": "CPIC"},
    {"gene": "UGT1A1", "star_allele": "*6", "rsid": "rs4148323",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "G71R — common in East Asian populations",
     "source": "CPIC"},
    # UGT1A1 expanded alleles (WGS coverage)
    {"gene": "UGT1A1", "star_allele": "*27", "rsid": "rs35350960",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "P229Q — decreased function, found in Asian populations",
     "source": ""},

    # ===================================================================
    # SLCO1B1 (simple gene)
    # ===================================================================
    {"gene": "SLCO1B1", "star_allele": "*5", "rsid": "rs4149056",
     "variant_allele": "C", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "V174A — reduced hepatic statin uptake, myopathy risk",
     "source": "CPIC"},
    {"gene": "SLCO1B1", "star_allele": "*1B", "rsid": "rs2306283",
     "variant_allele": "G", "function": "increased_function", "activity_score": None,
     "clinical_significance": "N130D — slightly increased transport",
     "source": "CPIC"},
    # SLCO1B1 expanded alleles (WGS coverage)
    {"gene": "SLCO1B1", "star_allele": "*9", "rsid": "rs59502379",
     "variant_allele": "C", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Decreased hepatic statin uptake",
     "source": "CPIC"},
    {"gene": "SLCO1B1", "star_allele": "*14", "rsid": "rs4149015",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Decreased function — reduced hepatic uptake",
     "source": "CPIC"},
    {"gene": "SLCO1B1", "star_allele": "*20", "rsid": "rs11045819",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "E667G — decreased function",
     "source": "CPIC"},

    # ===================================================================
    # CYP2B6 (simple gene)
    # ===================================================================
    {"gene": "CYP2B6", "star_allele": "*6", "rsid": "rs3745274",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Q172H — reduced activity, 3-4x higher efavirenz levels",
     "source": "CPIC"},
    {"gene": "CYP2B6", "star_allele": "*4", "rsid": "rs2279343",
     "variant_allele": "G", "function": "increased_function", "activity_score": None,
     "clinical_significance": "K262R — increased CYP2B6 activity",
     "source": ""},
    {"gene": "CYP2B6", "star_allele": "*9", "rsid": "rs3211371",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "R487C — reduced activity",
     "source": ""},
    {"gene": "CYP2B6", "star_allele": "*18", "rsid": "rs28399499",
     "variant_allele": "C", "function": "no_function", "activity_score": None,
     "clinical_significance": "I328T — near-complete loss, African populations",
     "source": "CPIC"},
    # CYP2B6 expanded alleles (WGS coverage) — *5/*7 skipped (share rsIDs with *9/*4)
    {"gene": "CYP2B6", "star_allele": "*2", "rsid": "rs8192709",
     "variant_allele": "T", "function": "normal_function", "activity_score": None,
     "clinical_significance": "C64T — normal function variant",
     "source": ""},
    {"gene": "CYP2B6", "star_allele": "*22", "rsid": "rs34223104",
     "variant_allele": "C", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Promoter variant — reduced CYP2B6 expression",
     "source": ""},
    {"gene": "CYP2B6", "star_allele": "*28", "rsid": "rs145884402",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Reduced function — identified in African populations",
     "source": ""},

    # ===================================================================
    # VKORC1 (simple gene)
    # ===================================================================
    {"gene": "VKORC1", "star_allele": "-1639G>A", "rsid": "rs9923231",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Major warfarin sensitivity variant — reduces VKORC1 expression",
     "source": "CPIC"},
    {"gene": "VKORC1", "star_allele": "Asp36Tyr", "rsid": "rs61742245",
     "variant_allele": "T", "function": "increased_function", "activity_score": None,
     "clinical_significance": "Warfarin resistance — dramatically higher dose required",
     "source": "CPIC"},
    # VKORC1 expanded alleles (WGS coverage)
    {"gene": "VKORC1", "star_allele": "rs72547529", "rsid": "rs72547529",
     "variant_allele": "T", "function": "increased_function", "activity_score": None,
     "clinical_significance": "Warfarin resistance variant — may require higher warfarin dose",
     "source": "CPIC"},

    # ===================================================================
    # CYP4F2 (simple gene)
    # ===================================================================
    {"gene": "CYP4F2", "star_allele": "*3", "rsid": "rs2108622",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "V433M — reduced vitamin K metabolism, higher warfarin dose",
     "source": "CPIC"},

    # ===================================================================
    # CYP1A2 (simple gene, tier 2)
    # ===================================================================
    {"gene": "CYP1A2", "star_allele": "*1F", "rsid": "rs762551",
     "variant_allele": "A", "function": "increased_function", "activity_score": None,
     "clinical_significance": "Inducibility variant — faster caffeine/theophylline metabolism",
     "source": ""},
    # CYP1A2 expanded alleles (WGS coverage)
    {"gene": "CYP1A2", "star_allele": "*1C", "rsid": "rs2069514",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Promoter variant — decreased CYP1A2 inducibility",
     "source": ""},
    {"gene": "CYP1A2", "star_allele": "*1K", "rsid": "rs12720461",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Reduced CYP1A2 inducibility",
     "source": ""},

    # ===================================================================
    # NAT2 (count gene) — count slow-allele variants
    # ===================================================================
    {"gene": "NAT2", "star_allele": "*5", "rsid": "rs1801280",
     "variant_allele": "C", "function": "no_function", "activity_score": None,
     "clinical_significance": "I114T — slow acetylator defining variant",
     "source": "CPIC"},
    {"gene": "NAT2", "star_allele": "*6", "rsid": "rs1799930",
     "variant_allele": "A", "function": "no_function", "activity_score": None,
     "clinical_significance": "R197Q — second most common slow allele",
     "source": "CPIC"},
    {"gene": "NAT2", "star_allele": "*11", "rsid": "rs1799929",
     "variant_allele": "T", "function": "normal_function", "activity_score": None,
     "clinical_significance": "481C>T (L161L) — synonymous variant defining NAT2*11 rapid acetylator haplotype",
     "source": "CPIC"},
    {"gene": "NAT2", "star_allele": "*14", "rsid": "rs1801279",
     "variant_allele": "A", "function": "no_function", "activity_score": None,
     "clinical_significance": "R64Q — slow allele in African populations",
     "source": ""},
    {"gene": "NAT2", "star_allele": "*12/*4_tag", "rsid": "rs1208",
     "variant_allele": "G", "function": "normal_function", "activity_score": None,
     "clinical_significance": "K268R — rapid acetylator haplotype tag",
     "source": ""},

    # ===================================================================
    # HLA binary markers
    # ===================================================================
    {"gene": "HLA-B_5701", "star_allele": "positive", "rsid": "rs2395029",
     "variant_allele": "G", "function": "risk", "activity_score": None,
     "clinical_significance": "Tags HLA-B*57:01 — MANDATORY abacavir pre-test",
     "source": "CPIC"},
    {"gene": "HLA-B_5801", "star_allele": "positive_tag1", "rsid": "rs6928038",
     "variant_allele": "A", "function": "risk", "activity_score": None,
     "clinical_significance": "Tags HLA-B*58:01 — allopurinol SJS/TEN risk",
     "source": "CPIC"},
    {"gene": "HLA-B_5801", "star_allele": "positive_tag2", "rsid": "rs9262570",
     "variant_allele": "G", "function": "risk", "activity_score": None,
     "clinical_significance": "Alternative HLA-B*58:01 tag",
     "source": "CPIC"},
    {"gene": "HLA-A_3101", "star_allele": "positive_tag1", "rsid": "rs1061235",
     "variant_allele": "T", "function": "risk", "activity_score": None,
     "clinical_significance": "Tags HLA-A*31:01 — carbamazepine hypersensitivity",
     "source": "CPIC"},
    {"gene": "HLA-A_3101", "star_allele": "positive_tag2", "rsid": "rs2571375",
     "variant_allele": "G", "function": "risk", "activity_score": None,
     "clinical_significance": "Alternative HLA-A*31:01 tag",
     "source": "CPIC"},

    # ===================================================================
    # IFNL4 (simple gene, tier 2)
    # ===================================================================
    {"gene": "IFNL4", "star_allele": "unfavorable", "rsid": "rs12979860",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "TT genotype = reduced HCV clearance",
     "source": "CPIC"},
    # IFNL4 expanded alleles (WGS coverage)
    {"gene": "IFNL4", "star_allele": "frameshift", "rsid": "rs11322783",
     "variant_allele": "TT", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Frameshift creating functional IFNL4 protein — associated with reduced HCV clearance",
     "source": "CPIC"},

    # ===================================================================
    # MTHFR (simple gene, tier 2)
    # ===================================================================
    {"gene": "MTHFR", "star_allele": "C677T", "rsid": "rs1801133",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "C677T — ~35% reduced activity per allele (NOTE: on minus strand, T in literature = A in dbSNP)",
     "source": "CPIC"},
    {"gene": "MTHFR", "star_allele": "A1298C", "rsid": "rs1801131",
     "variant_allele": "G", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "A1298C — mildly reduced activity",
     "source": "CPIC"},

    # ===================================================================
    # ABCB1 (simple gene, tier 2)
    # ===================================================================
    {"gene": "ABCB1", "star_allele": "altered", "rsid": "rs2032582",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "S893A/T — altered P-glycoprotein efflux",
     "source": "CPIC"},
    {"gene": "ABCB1", "star_allele": "altered", "rsid": "rs2032583",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Intronic — altered ABCB1 splicing",
     "source": "CPIC"},

    # ===================================================================
    # ABCG2 (simple gene, tier 2)
    # ===================================================================
    {"gene": "ABCG2", "star_allele": "reduced", "rsid": "rs2231142",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Q141K — reduced BCRP efflux, higher rosuvastatin levels",
     "source": "CPIC"},

    # ===================================================================
    # OPRM1 (simple gene, tier 2) — opioid receptor
    # ===================================================================
    {"gene": "OPRM1", "star_allele": "A118G", "rsid": "rs1799971",
     "variant_allele": "G", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "A118G (N40D) — reduced mu-opioid receptor expression; associated with reduced morphine efficacy and higher opioid dose requirements",
     "source": "CPIC"},

    # ===================================================================
    # COMT (simple gene, tier 2) — catecholamine metabolism
    # ===================================================================
    {"gene": "COMT", "star_allele": "Val158Met", "rsid": "rs4680",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Val158Met — 3-4x reduced COMT activity; Met/Met = higher dopamine levels, increased pain sensitivity, altered psychiatric drug response",
     "source": "CPIC"},

    # ===================================================================
    # HTR2A (simple gene, tier 2) — serotonin receptor
    # ===================================================================
    {"gene": "HTR2A", "star_allele": "variant", "rsid": "rs7997012",
     "variant_allele": "G", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Intronic variant associated with altered serotonin signaling and SSRI/antipsychotic response",
     "source": "CPIC"},

    # ===================================================================
    # HTR2C (simple gene, tier 2) — serotonin receptor
    # ===================================================================
    {"gene": "HTR2C", "star_allele": "variant", "rsid": "rs3813929",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Promoter variant — associated with antipsychotic-induced weight gain and metabolic syndrome",
     "source": "CPIC"},

    # ===================================================================
    # DRD2 (simple gene, tier 2) — dopamine receptor
    # ===================================================================
    {"gene": "DRD2", "star_allele": "variant", "rsid": "rs1799978",
     "variant_allele": "C", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Promoter variant affecting D2 receptor expression — associated with antipsychotic response",
     "source": "CPIC"},

    # ===================================================================
    # ANKK1 (simple gene, tier 2) — DRD2-adjacent
    # ===================================================================
    {"gene": "ANKK1", "star_allele": "Taq1A", "rsid": "rs1800497",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Taq1A (E713K) — reduces striatal D2 receptor density; affects antipsychotic and addiction treatment response",
     "source": "CPIC"},

    # ===================================================================
    # ADRA2A (simple gene, tier 2) — alpha-2A adrenergic receptor
    # ===================================================================
    {"gene": "ADRA2A", "star_allele": "variant", "rsid": "rs1800544",
     "variant_allele": "G", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Promoter C-1291G — affects alpha-2A receptor expression; associated with guanfacine and methylphenidate response for ADHD",
     "source": "CPIC"},

    # ===================================================================
    # ADRB1 (simple gene, tier 2) — beta-1 adrenergic receptor
    # ===================================================================
    {"gene": "ADRB1", "star_allele": "Arg389Gly", "rsid": "rs1801253",
     "variant_allele": "G", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Arg389Gly — Gly389 has reduced beta-blocker response; affects metoprolol, atenolol, carvedilol efficacy for HF and hypertension",
     "source": "CPIC"},

    # ===================================================================
    # ADRB2 (simple gene, tier 2) — beta-2 adrenergic receptor
    # ===================================================================
    {"gene": "ADRB2", "star_allele": "Arg16Gly", "rsid": "rs1042713",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Arg16Gly — Arg16 (A allele) shows enhanced agonist-promoted receptor downregulation, reducing long-term bronchodilator response",
     "source": "CPIC"},
    {"gene": "ADRB2", "star_allele": "Gln27Glu", "rsid": "rs1042714",
     "variant_allele": "G", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Gln27Glu — Glu27 associated with reduced beta-2 receptor downregulation and altered bronchodilator response",
     "source": "CPIC"},

    # ===================================================================
    # UGT1A4 (simple gene, tier 2) — lamotrigine metabolism
    # ===================================================================
    {"gene": "UGT1A4", "star_allele": "P24T", "rsid": "rs2011425",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "P24T — altered lamotrigine glucuronidation; may affect seizure control at standard doses",
     "source": "CPIC"},

    # ===================================================================
    # UGT2B15 (simple gene, tier 2) — benzodiazepine metabolism
    # ===================================================================
    {"gene": "UGT2B15", "star_allele": "D85Y", "rsid": "rs1902023",
     "variant_allele": "A", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "D85Y — reduced glucuronidation of lorazepam and oxazepam; carriers may have slower benzodiazepine clearance",
     "source": "CPIC"},

    # ===================================================================
    # F5 (binary gene, tier 2) — Factor V Leiden
    # ===================================================================
    {"gene": "F5", "star_allele": "positive", "rsid": "rs6025",
     "variant_allele": "T", "function": "risk", "activity_score": None,
     "clinical_significance": "Factor V Leiden (R506Q) — 3-8x increased VTE risk; contraindication for estrogen-containing contraceptives",
     "source": "CPIC"},

    # ===================================================================
    # F2 (binary gene, tier 2) — Prothrombin
    # ===================================================================
    {"gene": "F2", "star_allele": "positive", "rsid": "rs1799963",
     "variant_allele": "A", "function": "risk", "activity_score": None,
     "clinical_significance": "G20210A — 2-3x increased VTE risk; affects anticoagulant and hormonal contraceptive prescribing",
     "source": "CPIC"},

    # ===================================================================
    # G6PD (binary gene, tier 2) — glucose-6-phosphate dehydrogenase
    # ===================================================================
    {"gene": "G6PD", "star_allele": "positive_202A", "rsid": "rs1050828",
     "variant_allele": "T", "function": "risk", "activity_score": None,
     "clinical_significance": "G6PD A- (V68M) — defines the most common deficiency variant worldwide; hemolysis from rasburicase, primaquine, dapsone",
     "source": "CPIC"},
    {"gene": "G6PD", "star_allele": "positive_376G", "rsid": "rs1050829",
     "variant_allele": "C", "function": "risk", "activity_score": None,
     "clinical_significance": "G6PD A (N126D) — alone causes mild reduction; combined with 202A creates G6PD A- deficiency",
     "source": "CPIC"},

    # ===================================================================
    # RYR1 (binary gene, tier 2) — malignant hyperthermia
    # ===================================================================
    {"gene": "RYR1", "star_allele": "positive", "rsid": "rs121918592",
     "variant_allele": "T", "function": "risk", "activity_score": None,
     "clinical_significance": "R614C — malignant hyperthermia susceptibility; AVOID volatile anesthetics and succinylcholine",
     "source": "CPIC"},

    # ===================================================================
    # GRK4 (simple gene, tier 2) — G protein-coupled receptor kinase
    # ===================================================================
    {"gene": "GRK4", "star_allele": "A142V", "rsid": "rs1024323",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "A142V — gain-of-function variant enhancing D1 receptor desensitization in renal tubules; reduces atenolol BP response",
     "source": "CPIC"},
    {"gene": "GRK4", "star_allele": "A486V", "rsid": "rs1801058",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "A486V — enhances GRK4-mediated receptor phosphorylation; associated with adverse cardiovascular outcomes in INVEST trial",
     "source": "CPIC"},

    # ===================================================================
    # GRK5 (simple gene, tier 2) — G protein-coupled receptor kinase
    # ===================================================================
    {"gene": "GRK5", "star_allele": "variant", "rsid": "rs2230345",
     "variant_allele": "T", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Affects beta-adrenergic receptor desensitization and heart failure outcomes",
     "source": "CPIC"},

    # ===================================================================
    # GRIK4 (simple gene, tier 2) — glutamate receptor
    # ===================================================================
    {"gene": "GRIK4", "star_allele": "variant", "rsid": "rs1954787",
     "variant_allele": "C", "function": "decreased_function", "activity_score": None,
     "clinical_significance": "Intronic variant associated with SSRI antidepressant treatment response",
     "source": "CPIC"},

    # ===================================================================
    # CYP2C_cluster (binary gene, tier 2) — warfarin dosing
    # ===================================================================
    {"gene": "CYP2C_cluster", "star_allele": "positive", "rsid": "rs12777823",
     "variant_allele": "A", "function": "risk", "activity_score": None,
     "clinical_significance": "Near CYP2C cluster — affects warfarin dose in African Americans (independent of CYP2C9 genotype)",
     "source": "CPIC"},
]


# ---------------------------------------------------------------------------
# 3. PGX_DIPLOTYPE_PHENOTYPES — Function-pair → phenotype mappings
#    for 'simple' calling-method genes
#
#    function_pair = two function values, sorted alphabetically, joined with "/"
# ---------------------------------------------------------------------------

PGX_DIPLOTYPE_PHENOTYPES = [
    # ===================================================================
    # CYP3A5
    # ===================================================================
    {"gene": "CYP3A5", "function_pair": "no_function/no_function",
     "phenotype": "CYP3A5 Non-expressor",
     "description": "Non-expressor — likely requires standard tacrolimus dosing"},
    {"gene": "CYP3A5", "function_pair": "no_function/normal_function",
     "phenotype": "CYP3A5 Intermediate Expressor",
     "description": "One functional allele — may need moderately higher tacrolimus dose"},
    {"gene": "CYP3A5", "function_pair": "normal_function/normal_function",
     "phenotype": "CYP3A5 Expressor",
     "description": "Two functional alleles — likely requires higher tacrolimus dose"},

    # ===================================================================
    # CYP3A4
    # ===================================================================
    {"gene": "CYP3A4", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal Metabolizer",
     "description": "Standard CYP3A4 activity expected"},
    {"gene": "CYP3A4", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate Metabolizer",
     "description": "One reduced-function allele — may have moderately decreased CYP3A4 activity"},
    {"gene": "CYP3A4", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Poor Metabolizer",
     "description": "Two reduced-function alleles — significantly decreased CYP3A4 activity"},
    {"gene": "CYP3A4", "function_pair": "normal_function/uncertain_function",
     "phenotype": "Normal Metabolizer",
     "description": "Conservative assignment — uncertain allele assumed normal"},
    {"gene": "CYP3A4", "function_pair": "decreased_function/uncertain_function",
     "phenotype": "Intermediate Metabolizer",
     "description": "One decreased plus one uncertain — conservative intermediate assignment"},
    {"gene": "CYP3A4", "function_pair": "uncertain_function/uncertain_function",
     "phenotype": "Uncertain",
     "description": "Both alleles have uncertain function — clinical significance unknown"},

    # ===================================================================
    # TPMT
    # ===================================================================
    {"gene": "TPMT", "function_pair": "no_function/no_function",
     "phenotype": "TPMT Poor Metabolizer",
     "description": "Two non-functional alleles — contraindicated or drastically reduce thiopurine dose"},
    {"gene": "TPMT", "function_pair": "no_function/normal_function",
     "phenotype": "TPMT Intermediate Metabolizer",
     "description": "One non-functional allele — reduce thiopurine dose by ~50%"},
    {"gene": "TPMT", "function_pair": "normal_function/normal_function",
     "phenotype": "TPMT Normal Metabolizer",
     "description": "Standard thiopurine dosing"},

    # ===================================================================
    # NUDT15
    # ===================================================================
    {"gene": "NUDT15", "function_pair": "no_function/no_function",
     "phenotype": "NUDT15 Poor Metabolizer",
     "description": "Extreme thiopurine sensitivity — avoid or use minimal dose"},
    {"gene": "NUDT15", "function_pair": "no_function/normal_function",
     "phenotype": "NUDT15 Intermediate Metabolizer",
     "description": "Reduced thiopurine tolerance"},
    {"gene": "NUDT15", "function_pair": "normal_function/normal_function",
     "phenotype": "NUDT15 Normal Metabolizer",
     "description": "Standard thiopurine dosing"},

    # ===================================================================
    # UGT1A1
    # ===================================================================
    {"gene": "UGT1A1", "function_pair": "decreased_function/decreased_function",
     "phenotype": "UGT1A1 Poor Metabolizer",
     "description": "Gilbert syndrome likely — reduce irinotecan starting dose"},
    {"gene": "UGT1A1", "function_pair": "decreased_function/normal_function",
     "phenotype": "UGT1A1 Intermediate Metabolizer",
     "description": "Mildly reduced glucuronidation"},
    {"gene": "UGT1A1", "function_pair": "normal_function/normal_function",
     "phenotype": "UGT1A1 Normal Metabolizer",
     "description": "Standard irinotecan dosing"},

    # ===================================================================
    # SLCO1B1
    # ===================================================================
    {"gene": "SLCO1B1", "function_pair": "decreased_function/decreased_function",
     "phenotype": "SLCO1B1 Poor Function",
     "description": "High statin myopathy risk — avoid simvastatin >20mg"},
    {"gene": "SLCO1B1", "function_pair": "decreased_function/normal_function",
     "phenotype": "SLCO1B1 Intermediate Function",
     "description": "Moderate myopathy risk — consider lower statin dose"},
    {"gene": "SLCO1B1", "function_pair": "decreased_function/increased_function",
     "phenotype": "SLCO1B1 Intermediate Function",
     "description": "*5/*1B — mixed function"},
    {"gene": "SLCO1B1", "function_pair": "increased_function/increased_function",
     "phenotype": "SLCO1B1 Increased Function",
     "description": "May have enhanced hepatic statin uptake"},
    {"gene": "SLCO1B1", "function_pair": "increased_function/normal_function",
     "phenotype": "SLCO1B1 Normal Function",
     "description": "Normal statin transport"},
    {"gene": "SLCO1B1", "function_pair": "normal_function/normal_function",
     "phenotype": "SLCO1B1 Normal Function",
     "description": "Standard statin dosing"},

    # ===================================================================
    # CYP2B6
    # ===================================================================
    {"gene": "CYP2B6", "function_pair": "no_function/no_function",
     "phenotype": "CYP2B6 Poor Metabolizer",
     "description": "Significantly elevated efavirenz/methadone levels — dose reduction required"},
    {"gene": "CYP2B6", "function_pair": "decreased_function/no_function",
     "phenotype": "CYP2B6 Poor Metabolizer",
     "description": "Very low CYP2B6 activity — consider dose reduction"},
    {"gene": "CYP2B6", "function_pair": "decreased_function/decreased_function",
     "phenotype": "CYP2B6 Intermediate Metabolizer",
     "description": "Reduced CYP2B6 activity — monitor for elevated drug levels"},
    {"gene": "CYP2B6", "function_pair": "decreased_function/normal_function",
     "phenotype": "CYP2B6 Intermediate Metabolizer",
     "description": "Mildly reduced CYP2B6 activity"},
    {"gene": "CYP2B6", "function_pair": "no_function/normal_function",
     "phenotype": "CYP2B6 Intermediate Metabolizer",
     "description": "One non-functional allele — intermediate activity"},
    {"gene": "CYP2B6", "function_pair": "normal_function/normal_function",
     "phenotype": "CYP2B6 Normal Metabolizer",
     "description": "Standard CYP2B6 activity"},
    {"gene": "CYP2B6", "function_pair": "increased_function/normal_function",
     "phenotype": "CYP2B6 Rapid Metabolizer",
     "description": "Enhanced CYP2B6 activity — may have reduced drug exposure"},
    {"gene": "CYP2B6", "function_pair": "increased_function/increased_function",
     "phenotype": "CYP2B6 Ultra-rapid Metabolizer",
     "description": "Very high CYP2B6 activity — may require higher doses"},

    # ===================================================================
    # VKORC1
    # ===================================================================
    {"gene": "VKORC1", "function_pair": "decreased_function/decreased_function",
     "phenotype": "High Warfarin Sensitivity",
     "description": "Homozygous — likely requires significantly lower warfarin dose"},
    {"gene": "VKORC1", "function_pair": "decreased_function/normal_function",
     "phenotype": "Moderate Warfarin Sensitivity",
     "description": "Heterozygous — likely requires moderately lower warfarin dose"},
    {"gene": "VKORC1", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal Warfarin Sensitivity",
     "description": "Standard warfarin dose range"},
    {"gene": "VKORC1", "function_pair": "increased_function/normal_function",
     "phenotype": "Warfarin Resistance",
     "description": "May require higher than standard warfarin dose"},
    {"gene": "VKORC1", "function_pair": "decreased_function/increased_function",
     "phenotype": "Variable Warfarin Sensitivity",
     "description": "Mixed alleles"},
    {"gene": "VKORC1", "function_pair": "increased_function/increased_function",
     "phenotype": "Warfarin Resistance",
     "description": "Likely requires significantly higher warfarin dose"},

    # ===================================================================
    # CYP4F2
    # ===================================================================
    {"gene": "CYP4F2", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Reduced Vitamin K Metabolism",
     "description": "Homozygous — ~2 mg/day higher warfarin dose"},
    {"gene": "CYP4F2", "function_pair": "decreased_function/normal_function",
     "phenotype": "Slightly Reduced Vitamin K Metabolism",
     "description": "Heterozygous — ~1 mg/day higher warfarin dose"},
    {"gene": "CYP4F2", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal Vitamin K Metabolism",
     "description": "Standard warfarin dosing considerations"},

    # ===================================================================
    # CYP1A2
    # ===================================================================
    {"gene": "CYP1A2", "function_pair": "increased_function/increased_function",
     "phenotype": "CYP1A2 Ultra-rapid Metabolizer (Inducible)",
     "description": "Enhanced induction — rapid caffeine/theophylline clearance"},
    {"gene": "CYP1A2", "function_pair": "increased_function/normal_function",
     "phenotype": "CYP1A2 Rapid Metabolizer (Inducible)",
     "description": "Partially inducible"},
    {"gene": "CYP1A2", "function_pair": "normal_function/normal_function",
     "phenotype": "CYP1A2 Normal Metabolizer",
     "description": "Standard caffeine metabolism"},
    # CYP1A2 expanded mappings (with *1C decreased_function allele)
    {"gene": "CYP1A2", "function_pair": "decreased_function/decreased_function",
     "phenotype": "CYP1A2 Poor Metabolizer",
     "description": "Reduced CYP1A2 inducibility — slower caffeine/theophylline clearance"},
    {"gene": "CYP1A2", "function_pair": "decreased_function/normal_function",
     "phenotype": "CYP1A2 Intermediate Metabolizer",
     "description": "One decreased-function allele — mildly reduced CYP1A2 activity"},
    {"gene": "CYP1A2", "function_pair": "decreased_function/increased_function",
     "phenotype": "CYP1A2 Normal Metabolizer",
     "description": "Opposing alleles — net effect approximately normal CYP1A2 activity"},

    # ===================================================================
    # MTHFR
    # ===================================================================
    {"gene": "MTHFR", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Reduced MTHFR Activity",
     "description": "Homozygous — significantly reduced folate metabolism"},
    {"gene": "MTHFR", "function_pair": "decreased_function/normal_function",
     "phenotype": "Mildly Reduced MTHFR Activity",
     "description": "Heterozygous — mildly reduced folate metabolism"},
    {"gene": "MTHFR", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal MTHFR Activity",
     "description": "Normal folate metabolism"},

    # ===================================================================
    # IFNL4
    # ===================================================================
    {"gene": "IFNL4", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Unfavorable IFNL4 Genotype",
     "description": "TT — reduced HCV spontaneous clearance"},
    {"gene": "IFNL4", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate IFNL4 Genotype",
     "description": "CT — intermediate HCV clearance"},
    {"gene": "IFNL4", "function_pair": "normal_function/normal_function",
     "phenotype": "Favorable IFNL4 Genotype",
     "description": "CC — best HCV treatment response/clearance"},

    # ===================================================================
    # ABCB1
    # ===================================================================
    {"gene": "ABCB1", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Reduced P-glycoprotein Function",
     "description": "May have increased oral bioavailability of P-gp substrates"},
    {"gene": "ABCB1", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate P-glycoprotein Function",
     "description": "Mildly altered P-glycoprotein efflux"},
    {"gene": "ABCB1", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal P-glycoprotein Function",
     "description": "Standard P-glycoprotein efflux activity"},

    # ===================================================================
    # ABCG2
    # ===================================================================
    {"gene": "ABCG2", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Reduced BCRP Function",
     "description": "Significantly higher rosuvastatin levels — use lower dose"},
    {"gene": "ABCG2", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate BCRP Function",
     "description": "Moderately higher rosuvastatin levels"},
    {"gene": "ABCG2", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal BCRP Function",
     "description": "Standard rosuvastatin dosing"},

    # ===================================================================
    # OPRM1 — opioid receptor
    # ===================================================================
    {"gene": "OPRM1", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Reduced Opioid Receptor Response",
     "description": "Homozygous A118G — may require higher opioid doses for pain control"},
    {"gene": "OPRM1", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate Opioid Receptor Response",
     "description": "Heterozygous — mildly reduced opioid efficacy"},
    {"gene": "OPRM1", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal Opioid Receptor Response",
     "description": "Standard opioid response expected"},

    # ===================================================================
    # COMT — catecholamine metabolism
    # ===================================================================
    {"gene": "COMT", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Low COMT Activity (Met/Met)",
     "description": "Higher dopamine levels — increased pain sensitivity, potential benefits from COMT-independent analgesics"},
    {"gene": "COMT", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate COMT Activity (Val/Met)",
     "description": "Intermediate dopamine metabolism"},
    {"gene": "COMT", "function_pair": "normal_function/normal_function",
     "phenotype": "High COMT Activity (Val/Val)",
     "description": "Normal dopamine catabolism"},

    # ===================================================================
    # HTR2A — serotonin receptor
    # ===================================================================
    {"gene": "HTR2A", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Altered HTR2A Function",
     "description": "Homozygous variant — may have altered SSRI/antipsychotic response"},
    {"gene": "HTR2A", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate HTR2A Function",
     "description": "Heterozygous — mildly altered serotonin receptor signaling"},
    {"gene": "HTR2A", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal HTR2A Function",
     "description": "Standard serotonin receptor function"},

    # ===================================================================
    # HTR2C — serotonin receptor (weight gain)
    # ===================================================================
    {"gene": "HTR2C", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Increased Antipsychotic Weight Gain Risk",
     "description": "Homozygous — higher risk of antipsychotic-induced weight gain"},
    {"gene": "HTR2C", "function_pair": "decreased_function/normal_function",
     "phenotype": "Moderate Antipsychotic Weight Gain Risk",
     "description": "Heterozygous — moderate risk of antipsychotic-induced weight gain"},
    {"gene": "HTR2C", "function_pair": "normal_function/normal_function",
     "phenotype": "Typical Antipsychotic Weight Gain Risk",
     "description": "Standard risk for antipsychotic-induced metabolic effects"},

    # ===================================================================
    # DRD2 — dopamine receptor
    # ===================================================================
    {"gene": "DRD2", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Altered DRD2 Expression",
     "description": "Homozygous — reduced D2 receptor expression, may affect antipsychotic response"},
    {"gene": "DRD2", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate DRD2 Expression",
     "description": "Heterozygous — mildly altered dopamine D2 signaling"},
    {"gene": "DRD2", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal DRD2 Expression",
     "description": "Standard D2 receptor function"},

    # ===================================================================
    # ANKK1 — DRD2-adjacent (Taq1A)
    # ===================================================================
    {"gene": "ANKK1", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Reduced DRD2 Density (Taq1A A1/A1)",
     "description": "Homozygous Taq1A — significantly reduced striatal D2 receptor density"},
    {"gene": "ANKK1", "function_pair": "decreased_function/normal_function",
     "phenotype": "Mildly Reduced DRD2 Density (Taq1A A1/A2)",
     "description": "Heterozygous — mildly reduced D2 receptor density"},
    {"gene": "ANKK1", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal DRD2 Density (Taq1A A2/A2)",
     "description": "Normal striatal D2 receptor density"},

    # ===================================================================
    # ADRA2A — alpha-2A adrenergic receptor
    # ===================================================================
    {"gene": "ADRA2A", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Altered ADRA2A Function",
     "description": "Homozygous variant — may have altered response to guanfacine and methylphenidate"},
    {"gene": "ADRA2A", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate ADRA2A Function",
     "description": "Heterozygous — mildly altered alpha-2A receptor signaling"},
    {"gene": "ADRA2A", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal ADRA2A Function",
     "description": "Standard alpha-2A adrenergic receptor function"},

    # ===================================================================
    # ADRB1 — beta-1 adrenergic receptor
    # ===================================================================
    {"gene": "ADRB1", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Reduced Beta-Blocker Response",
     "description": "Gly389/Gly389 — reduced beta-blocker efficacy; may need alternative antihypertensive"},
    {"gene": "ADRB1", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate Beta-Blocker Response",
     "description": "Arg389/Gly389 — intermediate beta-blocker response"},
    {"gene": "ADRB1", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal Beta-Blocker Response",
     "description": "Arg389/Arg389 — standard beta-blocker efficacy expected"},

    # ===================================================================
    # ADRB2 — beta-2 adrenergic receptor
    # ===================================================================
    {"gene": "ADRB2", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Altered Bronchodilator Response",
     "description": "Homozygous variants — may have altered response to albuterol and other beta-2 agonists"},
    {"gene": "ADRB2", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate Bronchodilator Response",
     "description": "Heterozygous — mildly altered beta-2 receptor function"},
    {"gene": "ADRB2", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal Bronchodilator Response",
     "description": "Standard response to beta-2 agonist bronchodilators"},

    # ===================================================================
    # UGT1A4 — lamotrigine metabolism
    # ===================================================================
    {"gene": "UGT1A4", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Reduced UGT1A4 Activity",
     "description": "Homozygous — significantly altered lamotrigine metabolism; may need dose adjustment"},
    {"gene": "UGT1A4", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate UGT1A4 Activity",
     "description": "Heterozygous — mildly altered lamotrigine glucuronidation"},
    {"gene": "UGT1A4", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal UGT1A4 Activity",
     "description": "Standard lamotrigine metabolism"},

    # ===================================================================
    # UGT2B15 — benzodiazepine metabolism
    # ===================================================================
    {"gene": "UGT2B15", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Reduced UGT2B15 Activity",
     "description": "Homozygous D85Y — significantly slower lorazepam/oxazepam clearance"},
    {"gene": "UGT2B15", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate UGT2B15 Activity",
     "description": "Heterozygous — mildly reduced benzodiazepine clearance"},
    {"gene": "UGT2B15", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal UGT2B15 Activity",
     "description": "Standard benzodiazepine metabolism"},

    # ===================================================================
    # GRK4 — G protein-coupled receptor kinase
    # ===================================================================
    {"gene": "GRK4", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Altered GRK4 Function",
     "description": "Homozygous — altered beta-adrenergic signaling; may affect hypertension treatment response"},
    {"gene": "GRK4", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate GRK4 Function",
     "description": "Heterozygous — mildly altered receptor signaling"},
    {"gene": "GRK4", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal GRK4 Function",
     "description": "Standard G protein-coupled receptor kinase activity"},

    # ===================================================================
    # GRK5 — G protein-coupled receptor kinase
    # ===================================================================
    {"gene": "GRK5", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Altered GRK5 Function",
     "description": "Homozygous — altered beta-adrenergic desensitization; may affect heart failure treatment"},
    {"gene": "GRK5", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate GRK5 Function",
     "description": "Heterozygous — mildly altered receptor desensitization"},
    {"gene": "GRK5", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal GRK5 Function",
     "description": "Standard G protein-coupled receptor kinase 5 activity"},

    # ===================================================================
    # GRIK4 — glutamate receptor
    # ===================================================================
    {"gene": "GRIK4", "function_pair": "decreased_function/decreased_function",
     "phenotype": "Altered GRIK4 Function",
     "description": "Homozygous variant — may have altered SSRI antidepressant response"},
    {"gene": "GRIK4", "function_pair": "decreased_function/normal_function",
     "phenotype": "Intermediate GRIK4 Function",
     "description": "Heterozygous — mildly altered glutamate receptor signaling"},
    {"gene": "GRIK4", "function_pair": "normal_function/normal_function",
     "phenotype": "Normal GRIK4 Function",
     "description": "Standard glutamate receptor function"},

    # ===================================================================
    # IFNL3 — interferon lambda 3 (IL28B)
    # ===================================================================
    {"gene": "IFNL3", "function_pair": "uncertain_function/uncertain_function",
     "phenotype": "Uncertain Function",
     "description": "IFNL3 variant function not yet fully characterized — rs12979860 genotype may inform HCV treatment response"},
]
