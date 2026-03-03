"""Pharmacogenomic SNP seed data (~84 variants).

These entries are imported by seed_snp_pages.py and appended to SEED_SNPS.
Organized by gene family.
"""

PGX_SEED_SNPS = [
    # ── CYP2C9 additional alleles ─────────────────────────────────────────
    {
        "rsid": "rs1057910",
        "fallback": {"chrom": "10", "position": 96741053, "ref_allele": "A", "alt_allele": "C",
                      "gene": "CYP2C9", "functional_class": "missense", "maf_global": 0.06},
        "traits": [
            {
                "trait": "Warfarin Sensitivity",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": -1.1,
                "p_value": 1e-30,
                "effect_description": "CYP2C9*3 (I359L) reduces warfarin metabolism by approximately 80%, more severely than the *2 allele. Carriers typically require 30-50% lower warfarin doses to maintain therapeutic INR. This variant also significantly affects metabolism of phenytoin, celecoxib, and flurbiprofen. CPIC guidelines recommend reduced initial warfarin dosing for *3 carriers.",
                "evidence_level": "high",
                "source_pmid": "19228618",
                "source_title": "Estimation of the warfarin dose with clinical and pharmacogenomic data",
            },
        ],
    },
    {
        "rsid": "rs28371686",
        "fallback": {"chrom": "10", "position": 96731944, "ref_allele": "C", "alt_allele": "G",
                      "gene": "CYP2C9", "functional_class": "missense", "maf_global": 0.015},
        "traits": [
            {
                "trait": "Warfarin Sensitivity",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": -0.5,
                "p_value": 1e-8,
                "effect_description": "CYP2C9*5 is a rare loss-of-function variant found primarily in African American populations (~3.5% allele frequency). The substitution reduces CYP2C9 enzymatic activity, leading to impaired metabolism of warfarin and other CYP2C9 substrates. This variant is important for accurate warfarin dose prediction in populations of African descent where *2 and *3 are less prevalent.",
                "evidence_level": "medium",
                "source_pmid": "18484748",
                "source_title": "CYP2C9 allele frequency data in African Americans",
            },
        ],
    },
    {
        "rsid": "rs9332131",
        "fallback": {"chrom": "10", "position": 96741723, "ref_allele": "A", "alt_allele": "del",
                      "gene": "CYP2C9", "functional_class": "frameshift", "maf_global": 0.005},
        "traits": [
            {
                "trait": "Warfarin Sensitivity",
                "risk_allele": "del",
                "odds_ratio": None,
                "beta": -1.0,
                "p_value": 1e-10,
                "effect_description": "CYP2C9*6 is a frameshift deletion causing complete loss of CYP2C9 enzyme function. Although very rare globally, carriers who receive standard warfarin doses face serious bleeding risk due to inability to metabolize the drug. CPIC classifies *6 as a no-function allele requiring the same dose adjustments as other null CYP2C9 variants.",
                "evidence_level": "medium",
                "source_pmid": "18484748",
                "source_title": "CYP2C9 allele frequency data in African Americans",
            },
        ],
    },
    {
        "rsid": "rs7900194",
        "fallback": {"chrom": "10", "position": 96707470, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CYP2C9", "functional_class": "missense", "maf_global": 0.04},
        "traits": [
            {
                "trait": "Warfarin Sensitivity",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": -0.7,
                "p_value": 1e-12,
                "effect_description": "CYP2C9*8 is a reduced-function variant found primarily in African Americans at 4-8% allele frequency. The amino acid substitution impairs CYP2C9 catalytic activity, reducing warfarin metabolism. This variant is clinically important for warfarin dosing in populations of African descent where the common *2 and *3 alleles are rare, and its inclusion significantly improves dose prediction algorithms for these populations.",
                "evidence_level": "medium",
                "source_pmid": "18484748",
                "source_title": "CYP2C9 allele frequency data in African Americans",
            },
        ],
    },
    {
        "rsid": "rs28371685",
        "fallback": {"chrom": "10", "position": 96731938, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CYP2C9", "functional_class": "missense", "maf_global": 0.01},
        "traits": [
            {
                "trait": "Warfarin Sensitivity",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": -0.5,
                "p_value": 1e-6,
                "effect_description": "CYP2C9*11 carries an R150H substitution that reduces enzymatic function. This variant contributes to warfarin dose variability especially in non-European populations where it is more commonly found. CPIC classifies *11 as a decreased-function allele, and carriers may require lower warfarin doses compared to those with normal CYP2C9 activity.",
                "evidence_level": "medium",
                "source_pmid": "18484748",
                "source_title": "CYP2C9 allele frequency data in African Americans",
            },
        ],
    },

    # ── CYP2D6 ────────────────────────────────────────────────────────────
    {
        "rsid": "rs16947",
        "fallback": {"chrom": "22", "position": 42526694, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CYP2D6", "functional_class": "missense", "maf_global": 0.33},
        "traits": [
            {
                "trait": "CYP2D6 Metabolizer Status",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2D6*2 is defined by the R296C substitution (rs16947) and is classified as a normal-function allele. It is the most common non-reference CYP2D6 haplotype and serves as the backbone for several other alleles. While *2 itself does not cause altered drug metabolism, accurate genotyping of this variant is essential for correct CYP2D6 star allele assignment and metabolizer phenotype prediction.",
                "evidence_level": "high",
                "source_pmid": "24549605",
                "source_title": "Clinical Pharmacogenetics Implementation Consortium guidelines for CYP2D6 genotype and codeine therapy",
            },
        ],
    },
    {
        "rsid": "rs35742686",
        "fallback": {"chrom": "22", "position": 42524947, "ref_allele": "T", "alt_allele": "del",
                      "gene": "CYP2D6", "functional_class": "frameshift", "maf_global": 0.01},
        "traits": [
            {
                "trait": "Codeine Response",
                "risk_allele": "del",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2D6*3 is a frameshift deletion (2549delA) that completely abolishes CYP2D6 enzyme function. Carriers cannot convert the prodrug codeine into its active metabolite morphine, rendering codeine and tramadol ineffective for pain relief. CPIC recommends avoiding codeine in CYP2D6 poor metabolizers and selecting alternative analgesics such as non-codeine opioids or non-opioid pain medications.",
                "evidence_level": "high",
                "source_pmid": "24549605",
                "source_title": "CPIC Guideline for CYP2D6 and Codeine Therapy",
            },
        ],
    },
    {
        "rsid": "rs3892097",
        "fallback": {"chrom": "22", "position": 42524244, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CYP2D6", "functional_class": "splice_acceptor", "maf_global": 0.12},
        "traits": [
            {
                "trait": "Codeine Response",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2D6*4 is the most common null allele, carried by approximately 20% of Europeans. A splice site defect completely abolishes CYP2D6 enzyme activity, preventing activation of codeine to morphine and tramadol to its active metabolite. This variant also impairs tamoxifen conversion to its active metabolite endoxifen, and affects metabolism of ondansetron and many antidepressants. CPIC recommends alternative analgesics for poor metabolizers.",
                "evidence_level": "high",
                "source_pmid": "24549605",
                "source_title": "Clinical Pharmacogenetics Implementation Consortium guidelines for CYP2D6 genotype and codeine therapy",
            },
        ],
    },
    {
        "rsid": "rs5030655",
        "fallback": {"chrom": "22", "position": 42525086, "ref_allele": "T", "alt_allele": "del",
                      "gene": "CYP2D6", "functional_class": "frameshift", "maf_global": 0.01},
        "traits": [
            {
                "trait": "Codeine Response",
                "risk_allele": "del",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2D6*6 is a frameshift deletion (1707delT) that causes complete loss of CYP2D6 enzyme function. Clinically, it has the same impact as the more common *4 null allele — carriers are poor metabolizers unable to activate codeine, tramadol, or tamoxifen. CPIC guidelines for poor metabolizers apply regardless of which specific null allele is carried.",
                "evidence_level": "high",
                "source_pmid": "24549605",
                "source_title": "Clinical Pharmacogenetics Implementation Consortium guidelines for CYP2D6 genotype and codeine therapy",
            },
        ],
    },
    {
        "rsid": "rs5030656",
        "fallback": {"chrom": "22", "position": 42523610, "ref_allele": "AAG", "alt_allele": "del",
                      "gene": "CYP2D6", "functional_class": "in_frame_deletion", "maf_global": 0.02},
        "traits": [
            {
                "trait": "Codeine Response",
                "risk_allele": "del",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2D6*9 carries an in-frame deletion of lysine 281 (K281del) that reduces but does not eliminate CYP2D6 activity. CPIC classifies *9 as a decreased-function allele, meaning carriers are intermediate metabolizers when paired with a null allele. Intermediate metabolizers may have reduced codeine efficacy and altered metabolism of tamoxifen, antidepressants, and other CYP2D6 substrates.",
                "evidence_level": "high",
                "source_pmid": "24549605",
                "source_title": "Clinical Pharmacogenetics Implementation Consortium guidelines for CYP2D6 genotype and codeine therapy",
            },
        ],
    },
    {
        "rsid": "rs1065852",
        "fallback": {"chrom": "22", "position": 42526763, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CYP2D6", "functional_class": "missense", "maf_global": 0.20},
        "traits": [
            {
                "trait": "Codeine Response",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2D6*10 carries a P34S substitution that destabilizes the enzyme, reducing its catalytic activity. It is the most common CYP2D6 variant in East Asian populations (~40% allele frequency), explaining the higher proportion of intermediate metabolizers in these populations. Carriers have reduced metabolism of codeine, tamoxifen, and many antidepressants, potentially requiring dose adjustments.",
                "evidence_level": "high",
                "source_pmid": "24549605",
                "source_title": "Clinical Pharmacogenetics Implementation Consortium guidelines for CYP2D6 genotype and codeine therapy",
            },
        ],
    },
    {
        "rsid": "rs28371706",
        "fallback": {"chrom": "22", "position": 42525772, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CYP2D6", "functional_class": "missense", "maf_global": 0.10},
        "traits": [
            {
                "trait": "Codeine Response",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2D6*17 carries a T107I substitution that reduces enzyme function and alters substrate specificity compared to other reduced-function alleles. It is common in Sub-Saharan African populations (20-35% allele frequency) and is a major contributor to the intermediate metabolizer phenotype in these populations. Carriers may have altered response to codeine, tamoxifen, and CYP2D6-metabolized antidepressants.",
                "evidence_level": "high",
                "source_pmid": "24549605",
                "source_title": "Clinical Pharmacogenetics Implementation Consortium guidelines for CYP2D6 genotype and codeine therapy",
            },
        ],
    },
    {
        "rsid": "rs28371725",
        "fallback": {"chrom": "22", "position": 42524175, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CYP2D6", "functional_class": "intronic", "maf_global": 0.08},
        "traits": [
            {
                "trait": "Codeine Response",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2D6*41 is an intronic variant that causes aberrant splicing and reduced mRNA expression, resulting in decreased CYP2D6 enzyme levels. CPIC classifies *41 as a decreased-function allele. It is common in Middle Eastern and European populations, and carriers may have reduced activation of codeine and tramadol and altered metabolism of tamoxifen and antidepressants.",
                "evidence_level": "high",
                "source_pmid": "24549605",
                "source_title": "Clinical Pharmacogenetics Implementation Consortium guidelines for CYP2D6 genotype and codeine therapy",
            },
        ],
    },

    # ── CYP3A4 and CYP3A5 ────────────────────────────────────────────────
    {
        "rsid": "rs2740574",
        "fallback": {"chrom": "7", "position": 99382096, "ref_allele": "A", "alt_allele": "G",
                      "gene": "CYP3A4", "functional_class": "regulatory", "maf_global": 0.20},
        "traits": [
            {
                "trait": "Tacrolimus Metabolism",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP3A4*1B is a promoter variant (-392A>G) that may increase CYP3A4 expression, leading to faster metabolism of tacrolimus and other CYP3A4 substrates. It is common in African populations (~60% allele frequency). Carriers may require higher doses of tacrolimus to maintain therapeutic trough levels, and the variant is also associated with altered statin metabolism.",
                "evidence_level": "medium",
                "source_pmid": "25801146",
                "source_title": "CYP3A pharmacogenomics",
            },
        ],
    },
    {
        "rsid": "rs35599367",
        "fallback": {"chrom": "7", "position": 99354604, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CYP3A4", "functional_class": "intronic", "maf_global": 0.05},
        "traits": [
            {
                "trait": "Tacrolimus Metabolism",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP3A4*22 is an intron 6 variant that reduces CYP3A4 mRNA expression by approximately 50%, leading to slower metabolism of many drugs. Carriers require lower doses of tacrolimus, statins (particularly atorvastatin and simvastatin), and other CYP3A4 substrates. This variant is included in the Dutch Pharmacogenetics Working Group (DPWG) guidelines for statin dosing adjustments.",
                "evidence_level": "high",
                "source_pmid": "25801146",
                "source_title": "CYP3A pharmacogenomics",
            },
        ],
    },
    {
        "rsid": "rs776746",
        "fallback": {"chrom": "7", "position": 99270539, "ref_allele": "A", "alt_allele": "G",
                      "gene": "CYP3A5", "functional_class": "splice_variant", "maf_global": 0.65},
        "traits": [
            {
                "trait": "Tacrolimus Metabolism",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP3A5*3 is a splice variant that creates a cryptic splice site producing a truncated, non-functional protein. It is the most common CYP3A5 variant — 85-95% of Europeans are homozygous *3/*3 (CYP3A5 non-expressors). Individuals who carry at least one *1 allele (CYP3A5 expressors) metabolize tacrolimus significantly faster and require higher doses. CPIC guidelines recommend genotype-guided tacrolimus dosing based on CYP3A5 status.",
                "evidence_level": "high",
                "source_pmid": "25801146",
                "source_title": "CYP3A pharmacogenomics",
            },
        ],
    },
    {
        "rsid": "rs10264272",
        "fallback": {"chrom": "7", "position": 99270868, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CYP3A5", "functional_class": "splice_variant", "maf_global": 0.05},
        "traits": [
            {
                "trait": "Tacrolimus Metabolism",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP3A5*6 is a splice variant causing exon skipping and loss of CYP3A5 function. It is found primarily in African populations (~15% allele frequency). Combined genotyping of *3 and *6 is necessary for accurate CYP3A5 phenotype prediction, particularly in individuals of African descent where *3 alone does not fully capture non-expressor status.",
                "evidence_level": "high",
                "source_pmid": "25801146",
                "source_title": "CYP3A pharmacogenomics",
            },
        ],
    },
    {
        "rsid": "rs41303343",
        "fallback": {"chrom": "7", "position": 99262835, "ref_allele": "T", "alt_allele": "ins",
                      "gene": "CYP3A5", "functional_class": "frameshift", "maf_global": 0.03},
        "traits": [
            {
                "trait": "Tacrolimus Metabolism",
                "risk_allele": "ins",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP3A5*7 is a frameshift insertion in exon 11 that causes complete loss of CYP3A5 function. It is found almost exclusively in African populations (8-10% allele frequency). Along with *3 and *6, *7 genotyping is important for accurate CYP3A5 phenotype assignment and tacrolimus dose optimization in diverse populations.",
                "evidence_level": "medium",
                "source_pmid": "25801146",
                "source_title": "CYP3A pharmacogenomics",
            },
        ],
    },

    # ── VKORC1 additional + CYP4F2 ────────────────────────────────────────
    {
        "rsid": "rs61742245",
        "fallback": {"chrom": "16", "position": 31104878, "ref_allele": "G", "alt_allele": "T",
                      "gene": "VKORC1", "functional_class": "missense", "maf_global": 0.001},
        "traits": [
            {
                "trait": "Warfarin Resistance",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "VKORC1 Asp36Tyr is a rare missense variant that causes warfarin resistance by directly altering the drug binding site on vitamin K epoxide reductase. Carriers require dramatically higher warfarin doses, sometimes exceeding 10 mg/day, to achieve therapeutic anticoagulation. This variant should be suspected when patients show unexpectedly poor response to standard or even elevated warfarin doses.",
                "evidence_level": "high",
                "source_pmid": "19492868",
                "source_title": "VKORC1 mutations and warfarin resistance",
            },
        ],
    },
    {
        "rsid": "rs72547529",
        "fallback": {"chrom": "16", "position": 31105274, "ref_allele": "C", "alt_allele": "T",
                      "gene": "VKORC1", "functional_class": "missense", "maf_global": 0.001},
        "traits": [
            {
                "trait": "Warfarin Dose Requirement",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "This rare VKORC1 missense variant affects warfarin sensitivity independently of the common -1639G>A promoter variant. Carriers may require modified warfarin doses due to altered vitamin K epoxide reductase function. When detected alongside the common VKORC1 variants, it may help explain residual dose variability.",
                "evidence_level": "medium",
                "source_pmid": "19492868",
                "source_title": "VKORC1 mutations and warfarin resistance",
            },
        ],
    },
    {
        "rsid": "rs2108622",
        "fallback": {"chrom": "19", "position": 15990431, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CYP4F2", "functional_class": "missense", "maf_global": 0.25},
        "traits": [
            {
                "trait": "Warfarin Dose Requirement",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP4F2*3 (V433M) reduces vitamin K1 hydroxylase activity, leading to higher hepatic vitamin K levels and increased warfarin dose requirements of approximately 1 mg/day per allele. This variant is included in the IWPC (International Warfarin Pharmacogenetics Consortium) dosing algorithm and is mentioned on the FDA warfarin label. CYP4F2 genotyping alongside CYP2C9 and VKORC1 improves warfarin dose prediction accuracy.",
                "evidence_level": "high",
                "source_pmid": "19228618",
                "source_title": "Estimation of the warfarin dose with clinical and pharmacogenomic data",
            },
        ],
    },

    # ── DPYD ──────────────────────────────────────────────────────────────
    {
        "rsid": "rs3918290",
        "fallback": {"chrom": "1", "position": 97915614, "ref_allele": "C", "alt_allele": "T",
                      "gene": "DPYD", "functional_class": "splice_variant", "maf_global": 0.01},
        "traits": [
            {
                "trait": "Fluoropyrimidine Toxicity",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "DPYD*2A (IVS14+1G>A) is a splice variant that causes exon 14 skipping and complete loss of dihydropyrimidine dehydrogenase (DPD) activity. Carriers face life-threatening toxicity from 5-fluorouracil and capecitabine, including severe neutropenia, mucositis, and potentially death. CPIC and EMA mandate pre-treatment DPYD testing: heterozygous carriers need 50% dose reduction, and homozygous carriers must avoid fluoropyrimidines entirely.",
                "evidence_level": "high",
                "source_pmid": "29152729",
                "source_title": "CPIC Guideline for Fluoropyrimidines and DPYD",
            },
        ],
    },
    {
        "rsid": "rs55886062",
        "fallback": {"chrom": "1", "position": 97981395, "ref_allele": "A", "alt_allele": "C",
                      "gene": "DPYD", "functional_class": "missense", "maf_global": 0.001},
        "traits": [
            {
                "trait": "Fluoropyrimidine Toxicity",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "DPYD*13 (I560S) causes complete loss of DPD enzyme function through a critical amino acid substitution. Although very rare, its clinical severity is equivalent to *2A — carriers are at high risk of fatal toxicity from 5-fluorouracil and capecitabine. CPIC and EMA include *13 in the recommended pre-treatment DPYD testing panel, and fluoropyrimidines are contraindicated in homozygous carriers.",
                "evidence_level": "high",
                "source_pmid": "29152729",
                "source_title": "CPIC Guideline for Fluoropyrimidines and DPYD",
            },
        ],
    },
    {
        "rsid": "rs67376798",
        "fallback": {"chrom": "1", "position": 98205966, "ref_allele": "T", "alt_allele": "A",
                      "gene": "DPYD", "functional_class": "missense", "maf_global": 0.01},
        "traits": [
            {
                "trait": "Fluoropyrimidine Toxicity",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "DPYD D949V causes reduced (but not absent) dihydropyrimidine dehydrogenase activity. Heterozygous carriers are at increased risk of fluoropyrimidine toxicity but retain partial enzyme function. CPIC recommends a 50% dose reduction of 5-fluorouracil or capecitabine for heterozygous carriers, with subsequent dose titration based on clinical tolerance and toxicity monitoring.",
                "evidence_level": "high",
                "source_pmid": "29152729",
                "source_title": "CPIC Guideline for Fluoropyrimidines and DPYD",
            },
        ],
    },
    {
        "rsid": "rs75017182",
        "fallback": {"chrom": "1", "position": 97573863, "ref_allele": "G", "alt_allele": "C",
                      "gene": "DPYD", "functional_class": "intronic", "maf_global": 0.02},
        "traits": [
            {
                "trait": "Fluoropyrimidine Toxicity",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "DPYD HapB3 is a deep intronic variant that causes partial reduction in DPD enzyme activity through aberrant mRNA splicing. It is part of the EMA-recommended 4-variant DPYD testing panel (alongside *2A, *13, and D949V) that is now mandatory before fluoropyrimidine chemotherapy in many European countries. CPIC recommends a 50% dose reduction for heterozygous HapB3 carriers.",
                "evidence_level": "high",
                "source_pmid": "29152729",
                "source_title": "CPIC Guideline for Fluoropyrimidines and DPYD",
            },
        ],
    },

    # ── TPMT ──────────────────────────────────────────────────────────────
    {
        "rsid": "rs1800462",
        "fallback": {"chrom": "6", "position": 18130918, "ref_allele": "C", "alt_allele": "G",
                      "gene": "TPMT", "functional_class": "missense", "maf_global": 0.003},
        "traits": [
            {
                "trait": "Thiopurine Toxicity",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "TPMT*2 carries an A80P substitution that causes rapid protein degradation and near-complete loss of thiopurine methyltransferase activity. Carriers metabolize azathioprine and mercaptopurine poorly, leading to toxic accumulation of thioguanine nucleotides that causes life-threatening myelosuppression. CPIC recommends a 10-fold dose reduction for TPMT poor metabolizers, or use of alternative immunosuppressants.",
                "evidence_level": "high",
                "source_pmid": "21270794",
                "source_title": "CPIC Guideline for Thiopurines and TPMT/NUDT15",
            },
        ],
    },
    {
        "rsid": "rs1800460",
        "fallback": {"chrom": "6", "position": 18130752, "ref_allele": "A", "alt_allele": "G",
                      "gene": "TPMT", "functional_class": "missense", "maf_global": 0.04},
        "traits": [
            {
                "trait": "Thiopurine Toxicity",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "TPMT*3B carries an A154T substitution and is usually found in cis with rs1142345 (Y240C) as TPMT*3A, the most common non-functional TPMT allele in Europeans (~5% allele frequency). The A154T change causes protein misfolding and degradation, abolishing TPMT enzymatic activity. CPIC recommends substantial dose reductions of azathioprine and mercaptopurine for carriers of non-functional TPMT alleles.",
                "evidence_level": "high",
                "source_pmid": "21270794",
                "source_title": "CPIC Guideline for Thiopurines and TPMT/NUDT15",
            },
        ],
    },
    {
        "rsid": "rs1142345",
        "fallback": {"chrom": "6", "position": 18143955, "ref_allele": "T", "alt_allele": "C",
                      "gene": "TPMT", "functional_class": "missense", "maf_global": 0.04},
        "traits": [
            {
                "trait": "Thiopurine Toxicity",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "TPMT*3C carries a Y240C substitution. When present alone (without rs1800460), it defines the *3C allele — the most common non-functional TPMT allele in East Asian and African populations. When combined with rs1800460, it defines *3A. Both result in complete loss of TPMT function and high risk of severe myelosuppression from standard thiopurine doses. CPIC recommends combined genotyping with NUDT15 for comprehensive thiopurine toxicity risk assessment.",
                "evidence_level": "high",
                "source_pmid": "21270794",
                "source_title": "CPIC Guideline for Thiopurines and TPMT/NUDT15",
            },
        ],
    },

    # ── NUDT15 ────────────────────────────────────────────────────────────
    {
        "rsid": "rs116855232",
        "fallback": {"chrom": "13", "position": 48611992, "ref_allele": "C", "alt_allele": "T",
                      "gene": "NUDT15", "functional_class": "missense", "maf_global": 0.04},
        "traits": [
            {
                "trait": "Thiopurine Toxicity",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "NUDT15*3 (R139C) abolishes NUDT15 nucleotide diphosphatase activity, which normally degrades thiopurine active metabolites. This variant is critical in East Asian populations where TPMT variants are rare but NUDT15*3 frequency is 7-10%. Homozygous carriers have extreme sensitivity to azathioprine and mercaptopurine, with near-certain severe myelosuppression at standard doses. CPIC recommends combined TPMT + NUDT15 genotyping before initiating thiopurine therapy.",
                "evidence_level": "high",
                "source_pmid": "21270794",
                "source_title": "CPIC Guideline for Thiopurines and TPMT/NUDT15",
            },
        ],
    },
    {
        "rsid": "rs186364861",
        "fallback": {"chrom": "13", "position": 48611968, "ref_allele": "G", "alt_allele": "A",
                      "gene": "NUDT15", "functional_class": "missense", "maf_global": 0.001},
        "traits": [
            {
                "trait": "Thiopurine Toxicity",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "NUDT15*2 is a rare loss-of-function variant that impairs the NUDT15 enzyme's ability to degrade thiopurine active metabolites. Although very rare globally, it contributes to thiopurine sensitivity risk when present. CPIC includes NUDT15*2 in its genotyping recommendations for pre-treatment assessment before azathioprine or mercaptopurine therapy.",
                "evidence_level": "high",
                "source_pmid": "21270794",
                "source_title": "CPIC Guideline for Thiopurines and TPMT/NUDT15",
            },
        ],
    },

    # ── UGT1A1 ────────────────────────────────────────────────────────────
    {
        "rsid": "rs887829",
        "fallback": {"chrom": "2", "position": 234668879, "ref_allele": "C", "alt_allele": "T",
                      "gene": "UGT1A1", "functional_class": "regulatory", "maf_global": 0.33},
        "traits": [
            {
                "trait": "Irinotecan Toxicity",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "UGT1A1*80 is a regulatory variant in perfect linkage disequilibrium with UGT1A1*28 (the TA repeat polymorphism). It reduces UGT1A1 expression, impairing glucuronidation of SN-38, the active metabolite of the chemotherapy drug irinotecan. Homozygous carriers have Gilbert syndrome and face severe neutropenia and diarrhea from standard irinotecan doses. CPIC recommends a reduced starting dose of irinotecan for UGT1A1 poor metabolizers (*28/*28 or *80/*80).",
                "evidence_level": "high",
                "source_pmid": "30294987",
                "source_title": "CPIC Guideline for UGT1A1 and Irinotecan",
            },
        ],
    },
    {
        "rsid": "rs4148323",
        "fallback": {"chrom": "2", "position": 234669144, "ref_allele": "G", "alt_allele": "A",
                      "gene": "UGT1A1", "functional_class": "missense", "maf_global": 0.10},
        "traits": [
            {
                "trait": "Irinotecan Toxicity",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "UGT1A1*6 (G71R) is a missense variant that reduces UGT1A1 catalytic activity. It is the most common reduced-function UGT1A1 allele in East Asian populations (15-25% allele frequency) and is important for irinotecan dosing in populations where *28 is less prevalent. UGT1A1*6 is also associated with neonatal hyperbilirubinemia and breast milk jaundice.",
                "evidence_level": "high",
                "source_pmid": "30294987",
                "source_title": "CPIC Guideline for UGT1A1 and Irinotecan",
            },
        ],
    },

    # ── SLCO1B1 ───────────────────────────────────────────────────────────
    {
        "rsid": "rs4149056",
        "fallback": {"chrom": "12", "position": 21331549, "ref_allele": "T", "alt_allele": "C",
                      "gene": "SLCO1B1", "functional_class": "missense", "maf_global": 0.08},
        "traits": [
            {
                "trait": "Statin Myopathy Risk",
                "risk_allele": "C",
                "odds_ratio": 4.5,
                "beta": None,
                "p_value": 5e-19,
                "effect_description": "SLCO1B1*5 (V174A) reduces function of the OATP1B1 hepatic uptake transporter, decreasing hepatic clearance of statins and increasing systemic exposure. Homozygous CC carriers have a 17-fold increased risk of simvastatin-induced myopathy. CPIC recommends avoiding simvastatin >20 mg or switching to alternative statins (rosuvastatin, pravastatin) in *5 carriers. The landmark SEARCH trial finding (PMID 18650507) led to FDA simvastatin label updates.",
                "evidence_level": "high",
                "source_pmid": "18650507",
                "source_title": "SLCO1B1 variants and statin-induced myopathy — a genomewide study",
            },
        ],
    },
    {
        "rsid": "rs2306283",
        "fallback": {"chrom": "12", "position": 21329738, "ref_allele": "A", "alt_allele": "G",
                      "gene": "SLCO1B1", "functional_class": "missense", "maf_global": 0.40},
        "traits": [
            {
                "trait": "Statin Transport",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "SLCO1B1*1B (N130D) causes slightly increased hepatic transporter function for some substrates. When combined with the *5 variant (rs4149056), it defines the *15 haplotype. The interaction between *1B and *5 is complex — *1B alone may modestly increase hepatic statin uptake, but its clinical significance is primarily in the context of haplotype determination for accurate SLCO1B1 phenotype prediction.",
                "evidence_level": "medium",
                "source_pmid": "18650507",
                "source_title": "SLCO1B1 variants and statin-induced myopathy — a genomewide study",
            },
        ],
    },

    # ── IFNL3/IFNL4 ──────────────────────────────────────────────────────
    {
        "rsid": "rs12979860",
        "fallback": {"chrom": "19", "position": 39738787, "ref_allele": "C", "alt_allele": "T",
                      "gene": "IFNL4", "functional_class": "regulatory", "maf_global": 0.35},
        "traits": [
            {
                "trait": "Hepatitis C Treatment Response",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-30,
                "effect_description": "Located upstream of IFNL4, this variant is the strongest predictor of response to peginterferon/ribavirin therapy for hepatitis C. The CC genotype is associated with 2-3 fold higher sustained virological response rates. While direct-acting antivirals (DAAs) have largely replaced interferon-based HCV therapy, this variant remains clinically relevant for treatment access in resource-limited settings and for predicting spontaneous HCV clearance.",
                "evidence_level": "high",
                "source_pmid": "24725395",
                "source_title": "IFNL4 and hepatitis C treatment response",
            },
        ],
    },
    {
        "rsid": "rs11322783",
        "fallback": {"chrom": "19", "position": 39738145, "ref_allele": "TT", "alt_allele": "deltaG",
                      "gene": "IFNL4", "functional_class": "frameshift", "maf_global": 0.35},
        "traits": [
            {
                "trait": "Hepatitis C Treatment Response",
                "risk_allele": "deltaG",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-25,
                "effect_description": "This is the causal variant for IFNL4 function. The deltaG allele creates a functional IFNL4 protein that paradoxically impairs hepatitis C virus clearance by inducing interferon-stimulated gene expression and desensitizing the interferon signaling pathway. It is strongly linked with rs12979860 (IL28B) and explains the association between IL28B genotype and HCV treatment outcomes.",
                "evidence_level": "high",
                "source_pmid": "24725395",
                "source_title": "IFNL4 and hepatitis C treatment response",
            },
        ],
    },

    # ── HLA alleles ───────────────────────────────────────────────────────
    {
        "rsid": "rs2395029",
        "fallback": {"chrom": "6", "position": 31431780, "ref_allele": "T", "alt_allele": "G",
                      "gene": "HLA-B", "functional_class": "regulatory", "maf_global": 0.05},
        "traits": [
            {
                "trait": "Abacavir Hypersensitivity",
                "risk_allele": "G",
                "odds_ratio": 960.0,
                "beta": None,
                "p_value": 1e-50,
                "effect_description": "This variant tags HLA-B*57:01, which causes severe abacavir hypersensitivity reaction — a potentially fatal immune-mediated response involving fever, rash, and multi-organ damage that worsens with rechallenge. HLA-B*57:01 testing is MANDATORY before starting abacavir (HIV treatment) per FDA label and all major HIV treatment guidelines. This is one of the most successful pharmacogenomic interventions: pre-treatment screening has virtually eliminated abacavir hypersensitivity reactions in clinical practice.",
                "evidence_level": "high",
                "source_pmid": "18192541",
                "source_title": "HLA-B*5701 screening for hypersensitivity to abacavir",
            },
        ],
    },
    {
        "rsid": "rs6928038",
        "fallback": {"chrom": "6", "position": 31280788, "ref_allele": "G", "alt_allele": "A",
                      "gene": "HLA-B", "functional_class": "intergenic", "maf_global": 0.08},
        "traits": [
            {
                "trait": "Allopurinol Hypersensitivity",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-15,
                "effect_description": "This variant tags HLA-B*58:01, which is associated with severe allopurinol-induced Stevens-Johnson syndrome and toxic epidermal necrolysis (SJS/TEN) — life-threatening immune-mediated skin reactions. Risk is highest in Southeast Asian, Korean, and African American populations where HLA-B*58:01 prevalence is 6-8%. The American College of Rheumatology recommends HLA-B*58:01 testing before starting allopurinol for gout, especially in high-risk populations.",
                "evidence_level": "high",
                "source_pmid": "26094938",
                "source_title": "HLA-B*58:01 and allopurinol hypersensitivity",
            },
        ],
    },
    {
        "rsid": "rs9262570",
        "fallback": {"chrom": "6", "position": 31114088, "ref_allele": "A", "alt_allele": "G",
                      "gene": "HLA-B", "functional_class": "intergenic", "maf_global": 0.06},
        "traits": [
            {
                "trait": "Allopurinol Hypersensitivity",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-10,
                "effect_description": "This is an alternative tag SNP for HLA-B*58:01, providing additional predictive power for allopurinol-induced Stevens-Johnson syndrome/toxic epidermal necrolysis risk. Using multiple tag SNPs improves sensitivity for HLA-B*58:01 detection across diverse populations where a single tag may not capture all HLA-B*58:01 haplotypes.",
                "evidence_level": "medium",
                "source_pmid": "26094938",
                "source_title": "HLA-B*58:01 and allopurinol hypersensitivity",
            },
        ],
    },
    {
        "rsid": "rs1061235",
        "fallback": {"chrom": "6", "position": 29910908, "ref_allele": "G", "alt_allele": "A",
                      "gene": "HLA-A", "functional_class": "regulatory", "maf_global": 0.06},
        "traits": [
            {
                "trait": "Carbamazepine Hypersensitivity",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-12,
                "effect_description": "This variant tags HLA-A*31:01, which is associated with carbamazepine-induced hypersensitivity including Stevens-Johnson syndrome/toxic epidermal necrolysis (SJS/TEN) and Drug Reaction with Eosinophilia and Systemic Symptoms (DRESS). This association is most relevant in European and Japanese populations. CPIC recommends HLA-A*31:01 testing before carbamazepine initiation and considering alternative anticonvulsants for carriers.",
                "evidence_level": "high",
                "source_pmid": "21428769",
                "source_title": "HLA-A*31:01 and carbamazepine hypersensitivity reactions",
            },
        ],
    },
    {
        "rsid": "rs2571375",
        "fallback": {"chrom": "6", "position": 29913249, "ref_allele": "G", "alt_allele": "A",
                      "gene": "HLA-A", "functional_class": "intergenic", "maf_global": 0.08},
        "traits": [
            {
                "trait": "Carbamazepine Hypersensitivity",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-8,
                "effect_description": "This is an alternative tag SNP for HLA-A*31:01. Together with rs1061235, it improves prediction accuracy of carbamazepine hypersensitivity risk across diverse populations. Using multiple tag SNPs compensates for incomplete linkage disequilibrium between any single tag and the HLA allele in different ethnic backgrounds.",
                "evidence_level": "medium",
                "source_pmid": "21428769",
                "source_title": "HLA-A*31:01 and carbamazepine hypersensitivity reactions",
            },
        ],
    },

    # ── NAT2 ──────────────────────────────────────────────────────────────
    {
        "rsid": "rs1801280",
        "fallback": {"chrom": "8", "position": 18257854, "ref_allele": "T", "alt_allele": "C",
                      "gene": "NAT2", "functional_class": "missense", "maf_global": 0.30},
        "traits": [
            {
                "trait": "Isoniazid Acetylation Rate",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "NAT2*5 carries an I114T substitution and is the key defining variant for the slow acetylator haplotype. Slow acetylators have higher plasma isoniazid levels due to reduced N-acetyltransferase 2 activity, increasing risk of hepatotoxicity and peripheral neuropathy during tuberculosis treatment. CPIC guidelines recommend reduced isoniazid doses or enhanced monitoring for slow acetylators. This variant also affects metabolism of hydralazine, sulfonamides, and procainamide.",
                "evidence_level": "high",
                "source_pmid": "25287227",
                "source_title": "CPIC Guideline for Isoniazid and NAT2",
            },
        ],
    },
    {
        "rsid": "rs1799930",
        "fallback": {"chrom": "8", "position": 18258103, "ref_allele": "G", "alt_allele": "A",
                      "gene": "NAT2", "functional_class": "missense", "maf_global": 0.28},
        "traits": [
            {
                "trait": "Isoniazid Acetylation Rate",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "NAT2*6 carries an R197Q substitution that defines the second most common slow acetylator haplotype worldwide. Together with *5, these two alleles account for over 80% of all slow acetylators. Carriers have reduced NAT2 enzymatic activity, leading to higher isoniazid exposure and increased risk of drug-induced liver injury during tuberculosis treatment.",
                "evidence_level": "high",
                "source_pmid": "25287227",
                "source_title": "CPIC Guideline for Isoniazid and NAT2",
            },
        ],
    },
    {
        "rsid": "rs1208",
        "fallback": {"chrom": "8", "position": 18258309, "ref_allele": "A", "alt_allele": "G",
                      "gene": "NAT2", "functional_class": "missense", "maf_global": 0.45},
        "traits": [
            {
                "trait": "Isoniazid Acetylation Rate",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "NAT2 K268R (rs1208) is used for NAT2 haplotype phasing, where the G allele (268Arg) defines rapid acetylator haplotypes including *4 and *12. Accurate determination of acetylator status requires genotyping this variant in combination with other NAT2 SNPs. Rapid acetylators clear isoniazid faster, which may reduce drug efficacy but protects against hepatotoxicity.",
                "evidence_level": "high",
                "source_pmid": "25287227",
                "source_title": "CPIC Guideline for Isoniazid and NAT2",
            },
        ],
    },
    {
        "rsid": "rs1799929",
        "fallback": {"chrom": "8", "position": 18257611, "ref_allele": "C", "alt_allele": "T",
                      "gene": "NAT2", "functional_class": "synonymous", "maf_global": 0.15},
        "traits": [
            {
                "trait": "Isoniazid Acetylation Rate",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "NAT2 rs1799929 (481C>T, L161L) is a synonymous variant that tags the *11 rapid acetylator and *5B slow acetylator haplotypes. On its own it defines NAT2*11 (rapid acetylator) and does not reduce enzyme activity. When co-inherited with rs1801280 (I114T), it indicates the *5B slow haplotype. Acetylator status is determined by the functional variants (rs1801280, rs1799930, rs1801279), not by this synonymous change.",
                "evidence_level": "medium",
                "source_pmid": "25287227",
                "source_title": "CPIC Guideline for Isoniazid and NAT2",
            },
        ],
    },
    {
        "rsid": "rs1041983",
        "fallback": {"chrom": "8", "position": 18257568, "ref_allele": "C", "alt_allele": "T",
                      "gene": "NAT2", "functional_class": "synonymous", "maf_global": 0.33},
        "traits": [
            {
                "trait": "Isoniazid Acetylation Rate",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "NAT2 C282T (rs1041983) is a synonymous variant used for NAT2 haplotype determination. Although it does not directly alter protein sequence, it tags slow acetylator haplotypes when combined with functional SNPs at other NAT2 positions. Comprehensive NAT2 genotyping using multiple variants including this tag SNP is necessary for accurate acetylator phenotype prediction.",
                "evidence_level": "medium",
                "source_pmid": "25287227",
                "source_title": "CPIC Guideline for Isoniazid and NAT2",
            },
        ],
    },
    {
        "rsid": "rs1801279",
        "fallback": {"chrom": "8", "position": 18257477, "ref_allele": "G", "alt_allele": "A",
                      "gene": "NAT2", "functional_class": "missense", "maf_global": 0.02},
        "traits": [
            {
                "trait": "Isoniazid Acetylation Rate",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "NAT2*14 carries an R64Q substitution defining the *14 slow acetylator haplotype. It is found primarily in African populations at 5-8% allele frequency and is important for accurate NAT2 phenotype prediction in diverse populations. Omitting *14 from NAT2 genotyping panels leads to misclassification of slow acetylators as rapid in populations of African descent.",
                "evidence_level": "medium",
                "source_pmid": "25287227",
                "source_title": "CPIC Guideline for Isoniazid and NAT2",
            },
        ],
    },

    # ── CYP2B6 ────────────────────────────────────────────────────────────
    {
        "rsid": "rs3745274",
        "fallback": {"chrom": "19", "position": 41512841, "ref_allele": "G", "alt_allele": "T",
                      "gene": "CYP2B6", "functional_class": "missense", "maf_global": 0.25},
        "traits": [
            {
                "trait": "Efavirenz Metabolism",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2B6*6 carries a Q172H substitution that reduces protein expression and catalytic activity. Homozygous *6/*6 carriers have 3-4 fold higher efavirenz plasma levels, significantly increasing risk of CNS side effects including dizziness, vivid dreams, and depression. CPIC recommends dose reduction to 400 mg (from standard 600 mg) or selection of an alternative antiretroviral for CYP2B6 poor metabolizers. This variant also affects methadone and bupropion metabolism.",
                "evidence_level": "high",
                "source_pmid": "24648792",
                "source_title": "CPIC Guideline for Efavirenz and CYP2B6",
            },
        ],
    },
    {
        "rsid": "rs2279343",
        "fallback": {"chrom": "19", "position": 41515263, "ref_allele": "A", "alt_allele": "G",
                      "gene": "CYP2B6", "functional_class": "missense", "maf_global": 0.10},
        "traits": [
            {
                "trait": "Efavirenz Metabolism",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2B6*4 carries a K262R substitution associated with increased CYP2B6 enzymatic activity. Rapid metabolizers carrying this variant may achieve sub-therapeutic efavirenz plasma levels with standard dosing, potentially compromising HIV viral suppression. This variant is also relevant for bupropion and cyclophosphamide metabolism.",
                "evidence_level": "medium",
                "source_pmid": "24648792",
                "source_title": "CPIC Guideline for Efavirenz and CYP2B6",
            },
        ],
    },
    {
        "rsid": "rs3211371",
        "fallback": {"chrom": "19", "position": 41522715, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CYP2B6", "functional_class": "missense", "maf_global": 0.10},
        "traits": [
            {
                "trait": "Efavirenz Metabolism",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2B6*9 carries an R487C substitution that causes reduced CYP2B6 catalytic activity. Carriers metabolize efavirenz and methadone more slowly, which may lead to elevated drug levels and increased risk of adverse effects. This variant contributes to the wide inter-individual variability in CYP2B6 substrate metabolism observed across populations.",
                "evidence_level": "medium",
                "source_pmid": "24648792",
                "source_title": "CPIC Guideline for Efavirenz and CYP2B6",
            },
        ],
    },
    {
        "rsid": "rs28399499",
        "fallback": {"chrom": "19", "position": 41515810, "ref_allele": "T", "alt_allele": "C",
                      "gene": "CYP2B6", "functional_class": "missense", "maf_global": 0.04},
        "traits": [
            {
                "trait": "Efavirenz Metabolism",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2B6*18 carries an I328T substitution causing near-complete loss of CYP2B6 function. It is found primarily in African populations (4-8% allele frequency) and is the most severe loss-of-function CYP2B6 allele known. This variant contributes significantly to efavirenz toxicity risk in sub-Saharan Africa, where efavirenz remains a common component of first-line HIV treatment regimens.",
                "evidence_level": "high",
                "source_pmid": "24648792",
                "source_title": "CPIC Guideline for Efavirenz and CYP2B6",
            },
        ],
    },

    # ── MTHFR additional ──────────────────────────────────────────────────
    {
        "rsid": "rs1801131",
        "fallback": {"chrom": "1", "position": 11854476, "ref_allele": "T", "alt_allele": "G",
                      "gene": "MTHFR", "functional_class": "missense", "maf_global": 0.30},
        "traits": [
            {
                "trait": "Folate Metabolism",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-10,
                "effect_description": "MTHFR A1298C (E429A) causes a mild reduction of approximately 15-20% in methylenetetrahydrofolate reductase activity, less severe than the C677T variant (rs1801133). Compound heterozygosity (677CT/1298AC) can cause moderately reduced folate metabolism and mildly elevated homocysteine levels. This variant is relevant for assessing methotrexate toxicity risk, as impaired folate metabolism can potentiate methotrexate's antifolate effects.",
                "evidence_level": "medium",
                "source_pmid": "16825280",
                "source_title": "MTHFR polymorphisms and folate metabolism",
            },
        ],
    },

    # ── Transporter genes ─────────────────────────────────────────────────
    {
        "rsid": "rs2032582",
        "fallback": {"chrom": "7", "position": 87160618, "ref_allele": "G", "alt_allele": "T",
                      "gene": "ABCB1", "functional_class": "missense", "maf_global": 0.40},
        "traits": [
            {
                "trait": "Drug Efflux Transport",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "ABCB1 S893A/T is a missense variant in P-glycoprotein, a critical drug efflux transporter expressed in the intestine, liver, kidney, and blood-brain barrier. The TT genotype is associated with lower intestinal P-glycoprotein expression and higher oral bioavailability of substrates including digoxin, cyclosporine, HIV protease inhibitors, and certain chemotherapy agents. Carriers may be more sensitive to standard doses of P-gp substrates.",
                "evidence_level": "medium",
                "source_pmid": "22992668",
                "source_title": "ABCB1 pharmacogenomics review",
            },
        ],
    },
    {
        "rsid": "rs2032583",
        "fallback": {"chrom": "7", "position": 87138645, "ref_allele": "G", "alt_allele": "A",
                      "gene": "ABCB1", "functional_class": "intronic", "maf_global": 0.15},
        "traits": [
            {
                "trait": "Drug Efflux Transport",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "This ABCB1 intronic variant affects P-glycoprotein mRNA splicing, potentially altering drug transport across the blood-brain barrier. Carriers may have modified CNS exposure to P-gp substrates, which is clinically relevant for antiepileptic drug resistance and the brain penetration of chemotherapy, HIV antiretrovirals, and immunosuppressants.",
                "evidence_level": "medium",
                "source_pmid": "22992668",
                "source_title": "ABCB1 pharmacogenomics review",
            },
        ],
    },
    {
        "rsid": "rs2231142",
        "fallback": {"chrom": "4", "position": 89052323, "ref_allele": "G", "alt_allele": "T",
                      "gene": "ABCG2", "functional_class": "missense", "maf_global": 0.10},
        "traits": [
            {
                "trait": "Rosuvastatin Levels",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-15,
                "effect_description": "ABCG2 Q141K reduces function of the BCRP efflux transporter, which normally limits oral absorption and promotes biliary excretion of substrate drugs. Carriers have approximately 2-fold higher rosuvastatin plasma levels at standard doses. CPIC recommends a lower rosuvastatin starting dose in homozygous TT carriers. This variant also increases exposure to sulfasalazine and the chemotherapy agent topotecan.",
                "evidence_level": "high",
                "source_pmid": "19898482",
                "source_title": "ABCG2 Q141K and rosuvastatin pharmacokinetics",
            },
        ],
    },

    # ── Adrenergic receptors ──────────────────────────────────────────────
    {
        "rsid": "rs1800544",
        # MyVariant verified: chr10:112836503 ref=G alt=C; gnomAD genome AF(C)=0.608
        "fallback": {"chrom": "10", "position": 112836503, "ref_allele": "G", "alt_allele": "C",
                      "gene": "ADRA2A", "functional_class": "upstream_gene_variant", "maf_global": 0.39},
        "traits": [
            {
                "trait": "Methylphenidate Response in ADHD",
                "risk_allele": "G",
                "odds_ratio": 3.08,
                "beta": None,
                "p_value": 2e-4,
                "effect_description": "ADRA2A rs1800544 (-1291C>G) is a promoter variant upstream of the alpha-2A adrenergic receptor gene. The G allele is associated with significantly greater improvement in ADHD symptom scores during methylphenidate treatment (OR 3.08). The alpha-2A receptor mediates norepinephrine signaling in the prefrontal cortex, and this variant may alter receptor expression, affecting stimulant and alpha-2 agonist (guanfacine, clonidine) drug response.",
                "effect_summary": "G allele linked to better methylphenidate response in ADHD",
                "evidence_level": "medium",
                "source_pmid": "36325160",
                "source_title": "Review and meta-analysis on the impact of the ADRA2A variant rs1800544 on methylphenidate outcomes in ADHD",
            },
        ],
    },
    {
        "rsid": "rs1801253",
        # MyVariant verified: chr10:115805056 ref=G alt=C; gnomAD genome AF(C)=0.698
        "fallback": {"chrom": "10", "position": 115805056, "ref_allele": "G", "alt_allele": "C",
                      "gene": "ADRB1", "functional_class": "missense", "maf_global": 0.30},
        "traits": [
            {
                "trait": "Beta-Blocker Response",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-3,
                "effect_description": "ADRB1 Gly389Arg (rs1801253 G>C) is a missense variant where the Arg389 allele (C, major allele ~70%) confers 2-3 fold higher basal adenylyl cyclase activity and greater catecholamine responsiveness. Arg389 homozygotes show significantly greater blood pressure reduction with beta-blockers (metoprolol, atenolol, bisoprolol) compared to Gly389 carriers. The 2024 CPIC guideline reviewed this variant but found insufficient evidence for clinical dosing recommendations.",
                "effect_summary": "Arg389 (C) allele: enhanced beta-blocker BP/HR response",
                "evidence_level": "medium",
                "source_pmid": "12709726",
                "source_title": "A common beta1-adrenergic receptor polymorphism (Arg389Gly) affects blood pressure response to beta-blockade",
            },
        ],
    },
    {
        "rsid": "rs1042713",
        # MyVariant verified: chr5:148206440 ref=G alt=A; gnomAD genome AF(A)=0.427
        "fallback": {"chrom": "5", "position": 148206440, "ref_allele": "G", "alt_allele": "A",
                      "gene": "ADRB2", "functional_class": "missense", "maf_global": 0.43},
        "traits": [
            {
                "trait": "Beta-Agonist Response (Bronchodilators)",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "ADRB2 Gly16Arg (rs1042713 G>A) is a common missense variant in the beta-2 adrenergic receptor. The Arg16 allele (A, ~48% globally) shows enhanced agonist-promoted receptor downregulation, potentially reducing long-term bronchodilator efficacy with regular albuterol or salmeterol use. Arg16 homozygotes using regular LABA therapy may have increased risk of asthma exacerbations. The 2024 CPIC guideline found insufficient evidence for clinical dosing recommendations.",
                "effect_summary": "Arg16 (A) allele: enhanced receptor downregulation with chronic beta-agonist use",
                "evidence_level": "medium",
                "source_pmid": "19927042",
                "source_title": "Very important pharmacogene summary: ADRB2",
            },
        ],
    },
    {
        "rsid": "rs1042714",
        # MyVariant verified: chr5:148206473 ref=G alt=C; gnomAD genome AF(C)=0.668
        "fallback": {"chrom": "5", "position": 148206473, "ref_allele": "G", "alt_allele": "C",
                      "gene": "ADRB2", "functional_class": "missense", "maf_global": 0.33},
        "traits": [
            {
                "trait": "Beta-Agonist Response (Bronchodilators)",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "ADRB2 Gln27Glu (rs1042714 G>C) is a missense variant where the Glu27 allele (G, genomic reference, ~21% globally) resists agonist-induced receptor downregulation, maintaining beta-2 receptor density during chronic beta-agonist therapy. This variant interacts with Gly16Arg (rs1042713) as a haplotype to determine overall receptor function and bronchodilator response.",
                "effect_summary": "Glu27 (G) allele resists receptor downregulation during beta-agonist therapy",
                "evidence_level": "medium",
                "source_pmid": "19927042",
                "source_title": "Very important pharmacogene summary: ADRB2",
            },
        ],
    },

    # ── UGT enzymes ───────────────────────────────────────────────────────
    {
        "rsid": "rs2011425",
        "fallback": {"chrom": "2", "position": 234627397, "ref_allele": "T", "alt_allele": "A",
                      "gene": "UGT1A4", "functional_class": "missense", "maf_global": 0.08},
        "traits": [
            {
                "trait": "Lamotrigine Metabolism",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "UGT1A4 P24T affects the glucuronidation rate of lamotrigine, the primary metabolic pathway for this anticonvulsant. Carriers may have altered lamotrigine clearance, leading to variable steady-state drug levels. Since UGT1A4 is the primary enzyme responsible for lamotrigine metabolism, this variant may be relevant for dose optimization, particularly in combination with valproate (which inhibits lamotrigine glucuronidation).",
                "evidence_level": "medium",
                "source_pmid": "22569206",
                "source_title": "UGT1A4 polymorphisms and lamotrigine pharmacokinetics",
            },
        ],
    },
    {
        "rsid": "rs1902023",
        # MyVariant verified: chr4:69536084 ref=A alt=C; gnomAD genome AF(C)=0.537
        "fallback": {"chrom": "4", "position": 69536084, "ref_allele": "A", "alt_allele": "C",
                      "gene": "UGT2B15", "functional_class": "missense", "maf_global": 0.46},
        "traits": [
            {
                "trait": "Benzodiazepine Metabolism",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "UGT2B15 D85Y (rs1902023) is a common missense variant in UDP-glucuronosyltransferase 2B15. The Tyr85 variant (A allele, *2 allele) reduces enzymatic glucuronidation activity, leading to significantly slower clearance of lorazepam (42% reduction) and oxazepam (52% reduction) in homozygous carriers. This may necessitate benzodiazepine dose adjustments to avoid prolonged sedation.",
                "effect_summary": "Slower benzodiazepine metabolism; prolonged sedation risk",
                "evidence_level": "medium",
                "source_pmid": "15044558",
                "source_title": "UGT2B15 D85Y genotype and gender are major determinants of oxazepam glucuronidation by human liver",
            },
        ],
    },

    # ── Serotonin receptors ───────────────────────────────────────────────
    {
        "rsid": "rs7997012",
        "fallback": {"chrom": "13", "position": 47471478, "ref_allele": "G", "alt_allele": "A",
                      "gene": "HTR2A", "functional_class": "intronic", "maf_global": 0.45},
        "traits": [
            {
                "trait": "SSRI Antidepressant Response",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "HTR2A rs7997012 is an intronic variant in the serotonin 2A receptor gene. The AA genotype was significantly associated with better response to citalopram in the STAR*D clinical trial, one of the largest pharmacogenomic studies of antidepressant treatment. The mechanism likely involves altered HTR2A receptor expression in the prefrontal cortex, modulating serotonergic neurotransmission.",
                "evidence_level": "medium",
                "source_pmid": "16804045",
                "source_title": "HTR2A gene variants and SSRI antidepressant response",
            },
        ],
    },
    {
        "rsid": "rs3813929",
        # MyVariant verified: chrX:113818520 ref=C alt=T; gnomAD genome AF(T)=0.130
        "fallback": {"chrom": "X", "position": 113818520, "ref_allele": "C", "alt_allele": "T",
                      "gene": "HTR2C", "functional_class": "upstream_gene_variant", "maf_global": 0.13},
        "traits": [
            {
                "trait": "Antipsychotic-Induced Weight Gain",
                "risk_allele": "C",
                "odds_ratio": 0.34,
                "beta": None,
                "p_value": 1e-4,
                "effect_description": "HTR2C -759C>T (rs3813929) is a promoter variant in the serotonin 2C receptor gene on the X chromosome. The T allele is protective against antipsychotic-induced weight gain: a meta-analysis of 17 studies (n=3,170) found T carriers had significantly less weight gain (OR 0.34, 95% CI 0.20-0.57). The C allele (common, risk) predisposes to greater metabolic side effects with clozapine, olanzapine, and risperidone.",
                "effect_summary": "T allele protects against antipsychotic-induced weight gain",
                "evidence_level": "medium",
                "source_pmid": "32478286",
                "source_title": "Association of the HTR2C rs3813929 polymorphism with antipsychotic-induced weight gain: a meta-analysis",
            },
        ],
    },

    # ── Dopamine system ───────────────────────────────────────────────────
    {
        "rsid": "rs1799978",
        # MyVariant verified: chr11:113346351 ref=T alt=C; gnomAD genome AF(C)=0.099
        "fallback": {"chrom": "11", "position": 113346351, "ref_allele": "T", "alt_allele": "C",
                      "gene": "DRD2", "functional_class": "upstream_gene_variant", "maf_global": 0.10},
        "traits": [
            {
                "trait": "Antipsychotic Response",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.02,
                "effect_description": "DRD2 -241A>G (rs1799978) is a promoter variant that modulates dopamine D2 receptor transcription. In first-episode schizophrenia patients, G allele carriers (C on forward strand) showed significantly faster time to sustained response during risperidone and olanzapine treatment. Since antipsychotics exert therapeutic effects primarily through D2 receptor blockade, altered D2 expression directly affects drug pharmacodynamics.",
                "effect_summary": "Faster antipsychotic response in C allele carriers",
                "evidence_level": "medium",
                "source_pmid": "16513877",
                "source_title": "DRD2 promoter region variation as a predictor of sustained response to antipsychotic medication in first-episode schizophrenia patients",
            },
        ],
    },

    # ── GRK4/GRK5 ────────────────────────────────────────────────────────
    {
        "rsid": "rs1024323",
        # MyVariant verified: chr4:3006043 ref=C alt=T; gnomAD genome AF(T)=0.457
        "fallback": {"chrom": "4", "position": 3006043, "ref_allele": "C", "alt_allele": "T",
                      "gene": "GRK4", "functional_class": "missense", "maf_global": 0.46},
        "traits": [
            {
                "trait": "Antihypertensive Response",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "GRK4 A142V (rs1024323) is a common missense variant in G protein-coupled receptor kinase 4 that modifies renal dopamine D1 receptor signaling. The 142V variant (T allele) enhances GRK4-mediated phosphorylation and desensitization of D1 receptors, impairing natriuresis and promoting sodium retention. In the PEAR clinical trial, the haplotype containing this variant was associated with reduced atenolol-induced blood pressure lowering.",
                "effect_summary": "Reduced beta-blocker blood pressure response",
                "evidence_level": "medium",
                "source_pmid": "22949529",
                "source_title": "G protein receptor kinase 4 polymorphisms: beta-blocker pharmacogenetics and treatment-related outcomes in hypertension",
            },
        ],
    },
    {
        "rsid": "rs1801058",
        # MyVariant verified: chr4:3039150 ref=T alt=C; gnomAD genome AF(C)=0.658
        "fallback": {"chrom": "4", "position": 3039150, "ref_allele": "T", "alt_allele": "C",
                      "gene": "GRK4", "functional_class": "missense", "maf_global": 0.34},
        "traits": [
            {
                "trait": "Antihypertensive Response",
                "risk_allele": "T",
                "odds_ratio": 2.29,
                "beta": None,
                "p_value": 2e-4,
                "effect_description": "GRK4 A486V (rs1801058) is a functional missense variant in the membrane-targeting region of GRK4. The 486V variant (T allele, genomic reference) enhances receptor phosphorylation and desensitization, contributing to salt-sensitive hypertension. In the INVEST trial (1,460 patients), 486V homozygotes had significantly increased risk for adverse cardiovascular outcomes (OR 2.29, p=0.0002).",
                "effect_summary": "Altered BP drug response and cardiovascular risk",
                "evidence_level": "medium",
                "source_pmid": "22949529",
                "source_title": "G protein receptor kinase 4 polymorphisms: beta-blocker pharmacogenetics and treatment-related outcomes in hypertension",
            },
        ],
    },
    {
        "rsid": "rs2230345",
        # MyVariant verified: chr10:121086097 ref=A alt=T; gnomAD genome AF(T)=0.083
        "fallback": {"chrom": "10", "position": 121086097, "ref_allele": "A", "alt_allele": "T",
                      "gene": "GRK5", "functional_class": "missense", "maf_global": 0.08},
        "traits": [
            {
                "trait": "Heart Failure and Beta-Blocker Response",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "GRK5 Gln41Leu (rs2230345) is a gain-of-function variant in G protein-coupled receptor kinase 5 that more effectively uncouples beta-adrenergic receptor signaling. The Leu41 variant (T allele) functions as an endogenous \"genetic beta-blocker,\" protecting against catecholamine-induced cardiomyopathy. In African American heart failure patients, carriers showed decreased mortality and improved ejection fraction. Enriched in populations of African descent (~30%) vs Europeans (~1%).",
                "effect_summary": "Natural beta-blocker effect; heart failure protection",
                "evidence_level": "medium",
                "source_pmid": "18425130",
                "source_title": "A GRK5 polymorphism that inhibits beta-adrenergic receptor signaling is protective in heart failure",
            },
        ],
    },

    # ── GRIK4 ─────────────────────────────────────────────────────────────
    {
        "rsid": "rs1954787",
        # MyVariant verified: chr11:120663363 ref=T alt=C; gnomAD genome AF(C)=0.456
        "fallback": {"chrom": "11", "position": 120663363, "ref_allele": "T", "alt_allele": "C",
                      "gene": "GRIK4", "functional_class": "intron_variant", "maf_global": 0.46},
        "traits": [
            {
                "trait": "SSRI Antidepressant Response",
                "risk_allele": "C",
                "odds_ratio": 1.22,
                "beta": None,
                "p_value": 0.02,
                "effect_description": "GRIK4 rs1954787 is an intronic variant in the glutamate kainate receptor subunit 4 gene. In the landmark STAR*D trial (n=1,816), the C allele was significantly associated with better citalopram treatment response, with CC homozygotes showing reduced nonresponse risk. A subsequent meta-analysis confirmed the association (OR 1.22, 95% CI 1.04-1.44). The mechanism likely involves modulation of glutamatergic neurotransmission, which interacts with serotonergic pathways targeted by SSRIs.",
                "effect_summary": "Better SSRI antidepressant response with C allele",
                "evidence_level": "medium",
                "source_pmid": "17671280",
                "source_title": "Association of GRIK4 with outcome of antidepressant treatment in the STAR*D cohort",
            },
        ],
    },

    # ── CYP2C cluster African American warfarin ───────────────────────────
    {
        "rsid": "rs12777823",
        # MyVariant verified: chr10:96405502 ref=G alt=A; gnomAD genome AF(A)=0.190
        "fallback": {"chrom": "10", "position": 96405502, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CYP2C18", "functional_class": "intergenic", "maf_global": 0.19},
        "traits": [
            {
                "trait": "Warfarin Dose (African American)",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-15,
                "effect_description": "This intergenic variant in the CYP2C gene cluster significantly reduces warfarin dose requirements independently of CYP2C9 and VKORC1. The A allele is common in African Americans (~25%) and has been incorporated into the CPIC pharmacogenetics-guided warfarin dosing guideline for patients of African descent. Including rs12777823 improves warfarin dose prediction by 21% relative to algorithms that only consider CYP2C9 and VKORC1.",
                "effect_summary": "Lower warfarin dose needed (African ancestry)",
                "evidence_level": "high",
                "source_pmid": "23755828",
                "source_title": "Genetic variants associated with warfarin dose in African-American individuals: a genome-wide association study",
            },
        ],
    },

    # ── TIER 3: Extended Panel ────────────────────────────────────────────

    # ── CYP2C9 additional ─────────────────────────────────────────────────
    {
        "rsid": "rs28371674",
        "fallback": {"chrom": "10", "position": 96702099, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CYP2C9", "functional_class": "missense", "maf_global": 0.005},
        "traits": [
            {
                "trait": "CYP2C9 Drug Metabolism",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2C9*12 carries a P489S substitution that reduces enzymatic function. Although rare, this variant contributes to residual dose variability for warfarin and phenytoin that is not explained by the more common *2 and *3 alleles. Including *12 in CYP2C9 genotyping panels improves the accuracy of metabolizer phenotype prediction.",
                "evidence_level": "medium",
                "source_pmid": "16958828",
                "source_title": "CYP2C9 allelic variants and clinical implications",
            },
        ],
    },
    {
        "rsid": "rs9332239",
        "fallback": {"chrom": "10", "position": 96748737, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CYP2C9", "functional_class": "missense", "maf_global": 0.005},
        "traits": [
            {
                "trait": "CYP2C9 Drug Metabolism",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2C9*4 carries an I359T substitution — similar but distinct from the more common *3 allele (I359L). This rare reduced-function variant contributes to CYP2C9 metabolizer variability primarily in European populations. It affects metabolism of warfarin, phenytoin, NSAIDs, and other CYP2C9 substrates.",
                "evidence_level": "medium",
                "source_pmid": "16958828",
                "source_title": "CYP2C9 allelic variants and clinical implications",
            },
        ],
    },

    # ── Additional CYP2D6 ─────────────────────────────────────────────────
    {
        "rsid": "rs1135840",
        "fallback": {"chrom": "22", "position": 42522613, "ref_allele": "G", "alt_allele": "C",
                      "gene": "CYP2D6", "functional_class": "synonymous", "maf_global": 0.40},
        "traits": [
            {
                "trait": "CYP2D6 Metabolizer Status",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2D6 4180G>C (rs1135840) is a synonymous variant used for CYP2D6 haplotype phasing and star allele assignment. Although it does not alter protein sequence, accurate genotyping of this position is important for distinguishing between CYP2D6 haplotypes that share other defining variants. Combined with functional SNPs, it enables correct metabolizer phenotype prediction.",
                "evidence_level": "medium",
                "source_pmid": "24549605",
                "source_title": "Clinical Pharmacogenetics Implementation Consortium guidelines for CYP2D6 genotype and codeine therapy",
            },
        ],
    },
    {
        "rsid": "rs5030862",
        "fallback": {"chrom": "22", "position": 42526716, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CYP2D6", "functional_class": "missense", "maf_global": 0.001},
        "traits": [
            {
                "trait": "Codeine Response",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "CYP2D6*12 carries a G212E substitution that causes complete loss of CYP2D6 enzyme function. Although a very rare null allele, it has the same clinical impact as the more common *4 — carriers are poor metabolizers unable to activate prodrugs like codeine and tramadol. CPIC guidelines for poor metabolizers apply regardless of which specific null allele is present.",
                "evidence_level": "medium",
                "source_pmid": "24549605",
                "source_title": "Clinical Pharmacogenetics Implementation Consortium guidelines for CYP2D6 genotype and codeine therapy",
            },
        ],
    },

    # ── G6PD ──────────────────────────────────────────────────────────────
    {
        "rsid": "rs1050828",
        "fallback": {"chrom": "X", "position": 153764217, "ref_allele": "G", "alt_allele": "A",
                      "gene": "G6PD", "functional_class": "missense", "maf_global": 0.10},
        "traits": [
            {
                "trait": "Rasburicase/Primaquine Hemolytic Risk",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "G6PD A- (V68M) defines the most common G6PD deficiency variant in African populations (10-25% allele frequency), causing moderate enzyme deficiency (~10-20% residual activity). Carriers face potentially severe hemolytic anemia when exposed to oxidant drugs including rasburicase, primaquine, dapsone, and certain sulfonamides. The FDA mandates G6PD testing before rasburicase administration (black box warning). WHO also recommends G6PD testing before primaquine for malaria treatment.",
                "evidence_level": "high",
                "source_pmid": "22547206",
                "source_title": "G6PD deficiency and pharmacogenomics",
            },
        ],
    },
    {
        "rsid": "rs1050829",
        "fallback": {"chrom": "X", "position": 153763492, "ref_allele": "A", "alt_allele": "G",
                      "gene": "G6PD", "functional_class": "missense", "maf_global": 0.20},
        "traits": [
            {
                "trait": "G6PD Enzyme Activity",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "G6PD A (N126D) defines the G6PD A variant, which alone causes only mild reduction in enzyme activity (sometimes called G6PD A+ with near-normal function). However, when combined with the 202A variant (rs1050828) on the same haplotype, it creates the G6PD A- deficiency variant associated with clinically significant hemolytic risk from oxidant drugs. Genotyping both variants together is necessary for accurate G6PD phenotype prediction.",
                "evidence_level": "high",
                "source_pmid": "22547206",
                "source_title": "G6PD deficiency and pharmacogenomics",
            },
        ],
    },

    # ── RYR1 ──────────────────────────────────────────────────────────────
    {
        "rsid": "rs121918592",
        "fallback": {"chrom": "19", "position": 38998741, "ref_allele": "C", "alt_allele": "T",
                      "gene": "RYR1", "functional_class": "missense", "maf_global": 0.001},
        "traits": [
            {
                "trait": "Malignant Hyperthermia Susceptibility",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "RYR1 R614C is one of the most common malignant hyperthermia (MH) susceptibility mutations, affecting the ryanodine receptor 1 in skeletal muscle. Carriers experience potentially fatal hypermetabolic crisis — characterized by rapidly rising body temperature, muscle rigidity, and metabolic acidosis — when exposed to volatile anesthetics (sevoflurane, desflurane) or succinylcholine. Pre-surgical genetic screening can be lifesaving, as non-triggering anesthetics (such as propofol and opioids) must be used for MH-susceptible individuals.",
                "evidence_level": "high",
                "source_pmid": "17383735",
                "source_title": "Ryanodine receptor mutations and malignant hyperthermia susceptibility",
            },
        ],
    },
]
