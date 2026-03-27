"""Seed ~40 high-traffic SNPs into the snps and snp_trait_associations tables.

Fetches structural data (chrom, position, alleles, gene, MAF) from MyVariant.info,
then inserts curated trait association descriptions.

Usage:
    python -m scripts.seed_snp_pages           # fetch from API + insert
    python -m scripts.seed_snp_pages --offline  # use fallback values only
    python -m scripts.seed_snp_pages --dry-run  # print what would be inserted
"""

from __future__ import annotations

import argparse
import asyncio
import logging
from datetime import datetime, timezone

import httpx
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.base import Base
from app.models.snp import Snp, SnpTraitAssociation
from scripts._pgx_seed_data import PGX_SEED_SNPS

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

MYVARIANT_API = "https://myvariant.info/v1/query"

# ---------------------------------------------------------------------------
# Curated seed data: ~100 high-traffic SNPs across 7 categories
# + ~76 pharmacogenomic SNPs from _pgx_seed_data.py
# ---------------------------------------------------------------------------

SEED_SNPS = [
    # ── APOE / Alzheimer's ──────────────────────────────────────────────
    {
        "rsid": "rs429358",
        "fallback": {"chrom": "19", "position": 45411941, "ref_allele": "T", "alt_allele": "C",
                      "gene": "APOE", "functional_class": "missense", "maf_global": 0.14},
        "traits": [
            {
                "trait": "Alzheimer's Disease",
                "risk_allele": "C",
                "odds_ratio": 3.2,
                "beta": None,
                "p_value": 1e-100,
                "effect_description": "The C allele at rs429358 defines the APOE \u03b54 isoform, the strongest common genetic risk factor for late-onset Alzheimer's disease. Each copy of \u03b54 increases risk roughly 3-fold, with homozygous carriers facing up to 12-fold elevated risk. The \u03b54 isoform impairs amyloid-\u03b2 clearance and promotes neuroinflammation.",
                "effect_summary": "Higher Alzheimer's risk",
                "evidence_level": "high",
                "source_pmid": "9343467",
                "source_title": "Effects of age, sex, and ethnicity on the association between apolipoprotein E genotype and Alzheimer disease",
            },
            {
                "trait": "Cardiovascular Disease Risk",
                "risk_allele": "C",
                "odds_ratio": 1.06,
                "beta": None,
                "p_value": 5e-12,
                "effect_description": "APOE \u03b54 carriers have elevated LDL cholesterol levels, increasing coronary artery disease risk by approximately 6% per allele.",
                "effect_summary": "Elevated LDL cholesterol",
                "evidence_level": "high",
                "source_pmid": "17903302",
                "source_title": "Effects of the apolipoprotein E polymorphism on lipid profiles and coronary heart disease",
            },
        ],
    },
    {
        "rsid": "rs7412",
        "fallback": {"chrom": "19", "position": 45412079, "ref_allele": "C", "alt_allele": "T",
                      "gene": "APOE", "functional_class": "missense", "maf_global": 0.08},
        "traits": [
            {
                "trait": "Alzheimer's Disease (Protective)",
                "risk_allele": "T",
                "odds_ratio": 0.56,
                "beta": None,
                "p_value": 1e-50,
                "effect_description": "The T allele defines the APOE \u03b52 isoform, which is protective against Alzheimer's disease. Carriers have approximately 40% reduced risk. The \u03b52 isoform enhances amyloid-\u03b2 clearance from the brain.",
                "effect_summary": "Lower Alzheimer's risk",
                "evidence_level": "high",
                "source_pmid": "9343467",
                "source_title": "Effects of age, sex, and ethnicity on the association between apolipoprotein E genotype and Alzheimer disease",
            },
        ],
    },
    # ── BRCA / Cancer ───────────────────────────────────────────────────
    {
        "rsid": "rs80357906",
        "fallback": {"chrom": "17", "position": 41245471, "ref_allele": "C", "alt_allele": "T",
                      "gene": "BRCA1", "functional_class": "stop_gained", "maf_global": 0.0001},
        "traits": [
            {
                "trait": "Breast Cancer Risk",
                "risk_allele": "T",
                "odds_ratio": 11.0,
                "beta": None,
                "p_value": 1e-200,
                "effect_description": "This BRCA1 pathogenic variant (5382insC) introduces a premature stop codon, disrupting DNA double-strand break repair. Female carriers have 60-80% lifetime breast cancer risk and 40-60% ovarian cancer risk.",
                "effect_summary": "Higher breast cancer risk",
                "evidence_level": "high",
                "source_pmid": "12677558",
                "source_title": "Average risks of breast and ovarian cancer associated with BRCA1 or BRCA2 mutations",
            },
        ],
    },
    {
        "rsid": "rs1799950",
        "fallback": {"chrom": "17", "position": 41246481, "ref_allele": "G", "alt_allele": "A",
                      "gene": "BRCA1", "functional_class": "missense", "maf_global": 0.005},
        "traits": [
            {
                "trait": "Breast Cancer Risk",
                "risk_allele": "A",
                "odds_ratio": 1.2,
                "beta": None,
                "p_value": 2e-6,
                "effect_description": "The A allele at this BRCA1 missense variant (D693N) has been associated with modestly increased breast cancer risk. This is classified as a variant of uncertain to low clinical significance.",
                "effect_summary": "Modestly higher breast cancer risk",
                "evidence_level": "medium",
                "source_pmid": "17924331",
                "source_title": "Evaluation of common genetic variants in BRCA1 and breast cancer risk",
            },
        ],
    },
    {
        "rsid": "rs16942",
        "fallback": {"chrom": "17", "position": 41244000, "ref_allele": "G", "alt_allele": "A",
                      "gene": "BRCA1", "functional_class": "synonymous", "maf_global": 0.32},
        "traits": [
            {
                "trait": "Breast Cancer Risk",
                "risk_allele": "A",
                "odds_ratio": 1.05,
                "beta": None,
                "p_value": 1e-4,
                "effect_description": "Common synonymous variant in BRCA1 frequently observed in linkage disequilibrium with other BRCA1 variants. Minor association with breast cancer risk, likely as a tagging variant.",
                "effect_summary": "Slightly higher breast cancer risk",
                "evidence_level": "low",
                "source_pmid": "17924331",
                "source_title": "Evaluation of common genetic variants in BRCA1 and breast cancer risk",
            },
        ],
    },
    # ── Cardiovascular ──────────────────────────────────────────────────
    {
        "rsid": "rs1801133",
        "fallback": {"chrom": "1", "position": 11856378, "ref_allele": "G", "alt_allele": "A",
                      "gene": "MTHFR", "functional_class": "missense", "maf_global": 0.25},
        "traits": [
            {
                "trait": "Homocysteine Levels",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": 1.93,
                "p_value": 1e-50,
                "effect_description": "The MTHFR C677T variant (A allele on plus strand) reduces enzyme activity by ~35% per allele. Homozygous TT individuals have ~70% reduced activity, leading to elevated homocysteine, a cardiovascular risk factor. Adequate folate intake can mitigate this effect.",
                "effect_summary": "Elevated homocysteine",
                "evidence_level": "high",
                "source_pmid": "16175882",
                "source_title": "A quantitative assessment of plasma homocysteine as a risk factor for vascular disease",
            },
        ],
    },
    {
        "rsid": "rs1800562",
        "fallback": {"chrom": "6", "position": 26093141, "ref_allele": "G", "alt_allele": "A",
                      "gene": "HFE", "functional_class": "missense", "maf_global": 0.06},
        "traits": [
            {
                "trait": "Hereditary Hemochromatosis",
                "risk_allele": "A",
                "odds_ratio": 64.0,
                "beta": None,
                "p_value": 1e-200,
                "effect_description": "The C282Y mutation in HFE is the primary cause of hereditary hemochromatosis in Europeans. Homozygous carriers absorb excessive dietary iron, leading to iron overload that can damage the liver, heart, and pancreas if untreated. Penetrance is variable (~28% in males, lower in females).",
                "effect_summary": "Iron overload risk",
                "evidence_level": "high",
                "source_pmid": "8696333",
                "source_title": "A novel MHC class I-like gene is mutated in patients with hereditary haemochromatosis",
            },
        ],
    },
    {
        "rsid": "rs5882",
        "fallback": {"chrom": "16", "position": 57016092, "ref_allele": "A", "alt_allele": "G",
                      "gene": "CETP", "functional_class": "missense", "maf_global": 0.33},
        "traits": [
            {
                "trait": "HDL Cholesterol Levels",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": 2.1,
                "p_value": 1e-30,
                "effect_description": "The G allele reduces CETP activity, leading to higher HDL cholesterol levels. Carriers tend to have a more favorable lipid profile and potentially lower cardiovascular risk. The variant changes isoleucine to valine at position 405.",
                "effect_summary": "Higher HDL cholesterol",
                "evidence_level": "high",
                "source_pmid": "18193044",
                "source_title": "CETP polymorphisms and risk of coronary heart disease",
            },
        ],
    },
    {
        "rsid": "rs4420638",
        "fallback": {"chrom": "19", "position": 45422946, "ref_allele": "A", "alt_allele": "G",
                      "gene": "APOC1", "functional_class": "intergenic", "maf_global": 0.16},
        "traits": [
            {
                "trait": "LDL Cholesterol Levels",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": 6.0,
                "p_value": 1e-150,
                "effect_description": "Located near the APOE-APOC1-APOC4 gene cluster, this variant is a strong proxy for APOE \u03b54 status and is associated with significantly elevated LDL cholesterol. It is one of the strongest common associations with lipid levels genome-wide.",
                "effect_summary": "Elevated LDL cholesterol",
                "evidence_level": "high",
                "source_pmid": "20686565",
                "source_title": "Biological, clinical and population relevance of 95 loci for blood lipids",
            },
        ],
    },
    {
        "rsid": "rs10757274",
        "fallback": {"chrom": "9", "position": 22096055, "ref_allele": "A", "alt_allele": "G",
                      "gene": "CDKN2B-AS1", "functional_class": "intergenic", "maf_global": 0.47},
        "traits": [
            {
                "trait": "Coronary Artery Disease",
                "risk_allele": "G",
                "odds_ratio": 1.29,
                "beta": None,
                "p_value": 1e-20,
                "effect_description": "Located in the 9p21 locus near CDKN2A/B, the strongest and most replicated common genetic risk factor for coronary artery disease. The risk allele is very common, affecting ~47% of the population. The locus regulates cell proliferation in vascular smooth muscle.",
                "effect_summary": "Higher coronary artery disease risk",
                "evidence_level": "high",
                "source_pmid": "17478679",
                "source_title": "A common allele on chromosome 9 associated with coronary heart disease",
            },
        ],
    },
    # ── Pharmacogenomics ────────────────────────────────────────────────
    {
        "rsid": "rs4244285",
        "fallback": {"chrom": "10", "position": 96541616, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CYP2C19", "functional_class": "splice_acceptor", "maf_global": 0.15},
        "traits": [
            {
                "trait": "Clopidogrel Response",
                "risk_allele": "A",
                "odds_ratio": 1.76,
                "beta": None,
                "p_value": 1e-20,
                "effect_description": "The CYP2C19*2 allele is the most common loss-of-function variant, carried by ~25% of people. Poor metabolizers cannot efficiently convert clopidogrel (Plavix) to its active form, leading to reduced antiplatelet effect and increased cardiovascular event risk. FDA label includes a boxed warning about CYP2C19 poor metabolizers.",
                "effect_summary": "Reduced clopidogrel efficacy",
                "evidence_level": "high",
                "source_pmid": "20833655",
                "source_title": "Clinical pharmacogenomics of CYP2C19",
            },
        ],
    },
    {
        "rsid": "rs4986893",
        "fallback": {"chrom": "10", "position": 96540410, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CYP2C19", "functional_class": "stop_gained", "maf_global": 0.03},
        "traits": [
            {
                "trait": "Clopidogrel Response",
                "risk_allele": "A",
                "odds_ratio": 2.0,
                "beta": None,
                "p_value": 1e-15,
                "effect_description": "CYP2C19*3 introduces a premature stop codon, completely abolishing enzyme activity. Most prevalent in East Asian populations (~5-8%). Carriers are poor metabolizers of clopidogrel, proton pump inhibitors (omeprazole), and several antidepressants.",
                "effect_summary": "Reduced clopidogrel efficacy",
                "evidence_level": "high",
                "source_pmid": "20833655",
                "source_title": "Clinical pharmacogenomics of CYP2C19",
            },
        ],
    },
    {
        "rsid": "rs1799853",
        "fallback": {"chrom": "10", "position": 96702047, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CYP2C9", "functional_class": "missense", "maf_global": 0.07},
        "traits": [
            {
                "trait": "Warfarin Sensitivity",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": -0.85,
                "p_value": 1e-30,
                "effect_description": "CYP2C9*2 reduces warfarin metabolism by ~30%. Carriers require lower warfarin doses to achieve therapeutic anticoagulation. FDA-approved pharmacogenomic dosing guidelines incorporate this variant.",
                "effect_summary": "Increased warfarin sensitivity",
                "evidence_level": "high",
                "source_pmid": "19228618",
                "source_title": "Estimation of the warfarin dose with clinical and pharmacogenomic data",
            },
        ],
    },
    {
        "rsid": "rs9923231",
        "fallback": {"chrom": "16", "position": 31107689, "ref_allele": "C", "alt_allele": "T",
                      "gene": "VKORC1", "functional_class": "regulatory", "maf_global": 0.39},
        "traits": [
            {
                "trait": "Warfarin Sensitivity",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": -1.6,
                "p_value": 1e-80,
                "effect_description": "The strongest genetic predictor of warfarin dose. The T allele reduces VKORC1 expression by ~44%, meaning less warfarin is needed to inhibit vitamin K recycling. Explains ~25% of warfarin dose variability. Combined with CYP2C9 genotyping, enables personalized dosing.",
                "effect_summary": "Increased warfarin sensitivity",
                "evidence_level": "high",
                "source_pmid": "19228618",
                "source_title": "Estimation of the warfarin dose with clinical and pharmacogenomic data",
            },
        ],
    },
    {
        "rsid": "rs12248560",
        "fallback": {"chrom": "10", "position": 96521657, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CYP2C19", "functional_class": "regulatory", "maf_global": 0.18},
        "traits": [
            {
                "trait": "Clopidogrel Ultra-Rapid Metabolism",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-10,
                "effect_description": "CYP2C19*17 is a gain-of-function promoter variant that increases CYP2C19 expression. Ultra-rapid metabolizers may experience increased bleeding risk on clopidogrel and faster metabolism of proton pump inhibitors, reducing their efficacy.",
                "effect_summary": "Faster clopidogrel metabolism",
                "evidence_level": "high",
                "source_pmid": "20833655",
                "source_title": "Clinical pharmacogenomics of CYP2C19",
            },
        ],
    },
    # ── Metabolism / Nutrition ──────────────────────────────────────────
    {
        "rsid": "rs4988235",
        "fallback": {"chrom": "2", "position": 136608646, "ref_allele": "G", "alt_allele": "A",
                      "gene": "MCM6", "functional_class": "regulatory", "maf_global": 0.24},
        "traits": [
            {
                "trait": "Lactose Tolerance",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-200,
                "effect_description": "The A allele (also known as -13910*T in European notation) maintains LCT gene expression into adulthood, enabling continued lactose digestion. This is the primary lactase persistence variant in European populations, arising ~7,500 years ago with dairy farming. Homozygous G/G individuals typically develop lactose intolerance after childhood.",
                "effect_summary": "Lactose tolerant",
                "evidence_level": "high",
                "source_pmid": "11788828",
                "source_title": "Identification of a variant associated with adult-type hypolactasia",
            },
        ],
    },
    {
        "rsid": "rs1801282",
        "fallback": {"chrom": "3", "position": 12393125, "ref_allele": "C", "alt_allele": "G",
                      "gene": "PPARG", "functional_class": "missense", "maf_global": 0.09},
        "traits": [
            {
                "trait": "Type 2 Diabetes Risk",
                "risk_allele": "C",
                "odds_ratio": 1.14,
                "beta": None,
                "p_value": 1e-20,
                "effect_description": "The Pro12Ala variant in PPARG is one of the most replicated type 2 diabetes associations. The common C allele (Pro12) confers modestly increased risk. PPARG is the target of thiazolidinedione diabetes drugs (pioglitazone, rosiglitazone).",
                "effect_summary": "Higher type 2 diabetes risk",
                "evidence_level": "high",
                "source_pmid": "17554300",
                "source_title": "Replication of genome-wide association signals in UK samples reveals risk loci for type 2 diabetes",
            },
        ],
    },
    {
        "rsid": "rs7903146",
        "fallback": {"chrom": "10", "position": 114758349, "ref_allele": "C", "alt_allele": "T",
                      "gene": "TCF7L2", "functional_class": "intronic", "maf_global": 0.25},
        "traits": [
            {
                "trait": "Type 2 Diabetes Risk",
                "risk_allele": "T",
                "odds_ratio": 1.37,
                "beta": None,
                "p_value": 1e-75,
                "effect_description": "The strongest common genetic risk factor for type 2 diabetes. The T allele impairs \u03b2-cell function and insulin secretion through disrupted Wnt signaling. Homozygous T/T carriers have ~1.9x increased risk. TCF7L2 is a transcription factor critical for pancreatic \u03b2-cell development.",
                "effect_summary": "Higher type 2 diabetes risk",
                "evidence_level": "high",
                "source_pmid": "17463248",
                "source_title": "TCF7L2 polymorphisms and progression to diabetes in the Diabetes Prevention Program",
            },
        ],
    },
    {
        "rsid": "rs9939609",
        "fallback": {"chrom": "16", "position": 53820527, "ref_allele": "T", "alt_allele": "A",
                      "gene": "FTO", "functional_class": "intronic", "maf_global": 0.34},
        "traits": [
            {
                "trait": "Obesity / BMI",
                "risk_allele": "A",
                "odds_ratio": 1.31,
                "beta": 0.39,
                "p_value": 1e-120,
                "effect_description": "The first obesity-associated variant discovered by GWAS. Each A allele increases BMI by ~0.39 kg/m\u00b2 (~1.2 kg for average-height person). The FTO locus acts through regulation of IRX3/IRX5 in adipocyte thermogenesis. Homozygous A/A carriers average ~3 kg heavier. Effect can be attenuated by physical activity.",
                "effect_summary": "Higher BMI",
                "evidence_level": "high",
                "source_pmid": "17434869",
                "source_title": "A common variant in the FTO gene is associated with body mass index and predisposes to childhood and adult obesity",
            },
        ],
    },
    {
        "rsid": "rs1800497",
        "fallback": {"chrom": "11", "position": 113270828, "ref_allele": "G", "alt_allele": "A",
                      "gene": "ANKK1", "functional_class": "missense", "maf_global": 0.26},
        "traits": [
            {
                "trait": "Dopamine Receptor Density",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-15,
                "effect_description": "Known as the Taq1A polymorphism (Glu713Lys), the A1 allele causes a missense change in ANKK1's 11th ankyrin repeat. Although originally attributed to DRD2, this variant is in strong LD with the D2 receptor locus and A1 homozygotes show 30-40% reduced striatal D2 receptor density. This creates a hypodopaminergic state associated with altered reward processing and impulsive behavior.",
                "effect_summary": "Reduced dopamine D2 receptor density (30-40%)",
                "evidence_level": "high",
                "source_pmid": "15054482",
                "source_title": "The DRD2 TaqIA polymorphism and aspects of dopaminergic function",
            },
            {
                "trait": "Antipsychotic Side Effects",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.03,
                "effect_description": "The A1 allele of ANKK1/DRD2 Taq1A is associated with increased susceptibility to second-generation antipsychotic-induced akathisia. Carriers show higher global clinical akathisia scores during treatment with atypical antipsychotics such as olanzapine and risperidone, likely due to baseline reduction in striatal D2 receptor availability altering the pharmacodynamic response to D2-blocking medications.",
                "effect_summary": "Higher risk of antipsychotic-induced akathisia",
                "evidence_level": "medium",
                "source_pmid": "23118020",
                "source_title": "DRD2/ANKK1 Taq1A genotypes are associated with susceptibility to second generation antipsychotic-induced akathisia",
            },
            {
                "trait": "Addiction Vulnerability",
                "risk_allele": "A",
                "odds_ratio": 1.3,
                "beta": None,
                "p_value": 1e-10,
                "effect_description": "The A1 allele reduces striatal D2 dopamine receptor density by 30-40%, creating a hypodopaminergic state that increases vulnerability to substance use disorders including alcohol, nicotine, and stimulant dependence. Reduced reward sensitivity may drive compensatory substance-seeking behavior. This is one of the most replicated genetic associations in addiction research.",
                "effect_summary": "Increased addiction vulnerability via reduced D2 receptors",
                "evidence_level": "high",
                "source_pmid": "20194480",
                "source_title": "Dopamine D2 receptor genetic variation and clinical response to antipsychotic drug treatment: a meta-analysis",
            },
        ],
    },
    {
        "rsid": "rs1695",
        "fallback": {"chrom": "11", "position": 67352689, "ref_allele": "A", "alt_allele": "G",
                      "gene": "GSTP1", "functional_class": "missense", "maf_global": 0.33},
        "traits": [
            {
                "trait": "Detoxification Capacity",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-10,
                "effect_description": "The Ile105Val variant in glutathione S-transferase P1 alters the enzyme's substrate specificity and detoxification capacity. The G allele (Val105) reduces activity toward certain carcinogens but increases activity toward others. Relevant to chemotherapy drug metabolism and oxidative stress response.",
                "effect_summary": "Altered detoxification capacity",
                "evidence_level": "medium",
                "source_pmid": "15280900",
                "source_title": "Glutathione S-transferase polymorphisms and cancer susceptibility",
            },
        ],
    },
    # ── Mental Health ───────────────────────────────────────────────────
    {
        "rsid": "rs6265",
        "fallback": {"chrom": "11", "position": 27679916, "ref_allele": "C", "alt_allele": "T",
                      "gene": "BDNF", "functional_class": "missense", "maf_global": 0.20},
        "traits": [
            {
                "trait": "Brain-Derived Neurotrophic Factor (BDNF) Function",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-20,
                "effect_description": "The Val66Met polymorphism in BDNF impairs activity-dependent secretion of the neurotrophin. The Met allele reduces hippocampal volume and episodic memory performance. Associated with differential response to stress, antidepressant efficacy, and neuroplasticity.",
                "effect_summary": "Reduced BDNF secretion",
                "evidence_level": "high",
                "source_pmid": "12553913",
                "source_title": "The BDNF val66met polymorphism affects activity-dependent secretion of BDNF and human memory and hippocampal function",
            },
        ],
    },
    {
        "rsid": "rs4680",
        "fallback": {"chrom": "22", "position": 19951271, "ref_allele": "G", "alt_allele": "A",
                      "gene": "COMT", "functional_class": "missense", "maf_global": 0.37},
        "traits": [
            {
                "trait": "Dopamine Metabolism / Cognitive Function",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-15,
                "effect_description": "The Val158Met variant in catechol-O-methyltransferase. The Met allele (A) reduces enzyme activity 3-4x, leading to higher prefrontal dopamine. This creates a cognitive tradeoff: Met/Met individuals show better working memory but increased stress vulnerability ('worrier' phenotype), while Val/Val show stress resilience but less cognitive efficiency ('warrior' phenotype).",
                "effect_summary": "Slower dopamine clearance",
                "evidence_level": "high",
                "source_pmid": "14615855",
                "source_title": "COMT val158met genotype affects prefrontal dopamine and cognitive function",
            },
        ],
    },
    {
        "rsid": "rs53576",
        "fallback": {"chrom": "3", "position": 8804371, "ref_allele": "G", "alt_allele": "A",
                      "gene": "OXTR", "functional_class": "intronic", "maf_global": 0.37},
        "traits": [
            {
                "trait": "Social Behavior / Empathy",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 3e-6,
                "effect_description": "Intronic variant in the oxytocin receptor gene associated with social cognition and behavior. The G allele is linked to higher empathy scores, greater social sensitivity, and more secure attachment styles. The A allele is associated with lower empathic accuracy and reduced prosocial behavior, though effect sizes are modest.",
                "effect_summary": "Lower empathic accuracy",
                "evidence_level": "medium",
                "source_pmid": "19934046",
                "source_title": "Oxytocin receptor genetic variation relates to empathy and stress reactivity",
            },
        ],
    },
    {
        "rsid": "rs6311",
        "fallback": {"chrom": "13", "position": 47471478, "ref_allele": "G", "alt_allele": "A",
                      "gene": "HTR2A", "functional_class": "regulatory", "maf_global": 0.44},
        "traits": [
            {
                "trait": "Antidepressant Response",
                "risk_allele": "A",
                "odds_ratio": 1.18,
                "beta": None,
                "p_value": 2e-5,
                "effect_description": "Promoter variant in the serotonin 2A receptor gene (-1438G/A). The A allele increases HTR2A expression and has been associated with differential response to SSRI antidepressants. Also linked to susceptibility to major depression and altered serotonergic signaling.",
                "effect_summary": "Altered SSRI response",
                "evidence_level": "medium",
                "source_pmid": "17386950",
                "source_title": "HTR2A gene variants and response to antidepressant treatment",
            },
        ],
    },
    # ── Physical Traits ─────────────────────────────────────────────────
    {
        "rsid": "rs12913832",
        "fallback": {"chrom": "15", "position": 28365618, "ref_allele": "A", "alt_allele": "G",
                      "gene": "HERC2", "functional_class": "regulatory", "maf_global": 0.26},
        "traits": [
            {
                "trait": "Eye Color",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-300,
                "effect_description": "The single most important genetic determinant of human eye color. The G allele reduces OCA2 expression in iris melanocytes, resulting in blue eyes. Homozygous G/G predicts blue eyes with >90% accuracy in Europeans. The A allele is associated with brown eyes. This regulatory variant sits in HERC2 but controls the OCA2 gene.",
                "effect_summary": "Blue eyes",
                "evidence_level": "high",
                "source_pmid": "18172690",
                "source_title": "A single SNP in an evolutionary conserved region within intron 86 of the HERC2 gene determines human blue-brown eye color",
            },
        ],
    },
    {
        "rsid": "rs1805007",
        "fallback": {"chrom": "16", "position": 89986117, "ref_allele": "C", "alt_allele": "T",
                      "gene": "MC1R", "functional_class": "missense", "maf_global": 0.06},
        "traits": [
            {
                "trait": "Red Hair / Fair Skin",
                "risk_allele": "T",
                "odds_ratio": 6.1,
                "beta": None,
                "p_value": 1e-50,
                "effect_description": "The R151C variant in melanocortin-1 receptor is the strongest genetic predictor of red hair. Homozygous carriers have ~80% chance of red hair. MC1R loss-of-function shifts melanin production from eumelanin (brown/black) to pheomelanin (red/yellow), also causing fair skin, freckling, and increased UV sensitivity.",
                "effect_summary": "Red hair and fair skin",
                "evidence_level": "high",
                "source_pmid": "11260714",
                "source_title": "Melanocortin 1 receptor variants and skin cancer risk",
            },
            {
                "trait": "Melanoma Susceptibility",
                "risk_allele": "T",
                "odds_ratio": 2.4,
                "beta": None,
                "p_value": 1e-15,
                "effect_description": "MC1R variants increase melanoma risk independently of their effect on pigmentation. The reduced eumelanin:pheomelanin ratio impairs UV-induced DNA damage repair. Risk applies even in individuals without red hair phenotype.",
                "effect_summary": "Higher melanoma risk",
                "evidence_level": "high",
                "source_pmid": "11260714",
                "source_title": "Melanocortin 1 receptor variants and skin cancer risk",
            },
        ],
    },
    {
        "rsid": "rs1042725",
        "fallback": {"chrom": "12", "position": 66358347, "ref_allele": "C", "alt_allele": "T",
                      "gene": "HMGA2", "functional_class": "3_prime_UTR", "maf_global": 0.49},
        "traits": [
            {
                "trait": "Height",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": 0.3,
                "p_value": 1e-30,
                "effect_description": "One of the strongest common variants associated with adult height. Located in the 3'UTR of HMGA2, a chromatin architectural factor involved in growth. Each C allele adds approximately 0.3 cm to predicted height, though individual height is influenced by hundreds of variants plus environment.",
                "effect_summary": "Slightly taller stature",
                "evidence_level": "high",
                "source_pmid": "18391950",
                "source_title": "Many sequence variants affecting diversity of adult human height",
            },
        ],
    },
    {
        "rsid": "rs1426654",
        "fallback": {"chrom": "15", "position": 48426484, "ref_allele": "G", "alt_allele": "A",
                      "gene": "SLC24A5", "functional_class": "missense", "maf_global": 0.42},
        "traits": [
            {
                "trait": "Skin Pigmentation",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-300,
                "effect_description": "The Ala111Thr variant in SLC24A5 is the single largest contributor to light skin pigmentation in Europeans. The A allele (Thr111) is nearly fixed in European populations (~99%) and rare in African/East Asian populations. The variant affects melanosome calcium transport, reducing melanin production.",
                "effect_summary": "Lighter skin pigmentation",
                "evidence_level": "high",
                "source_pmid": "16357253",
                "source_title": "SLC24A5, a putative cation exchanger, affects pigmentation in zebrafish and humans",
            },
        ],
    },
    # ── Immunity / Autoimmune ───────────────────────────────────────────
    {
        "rsid": "rs6457617",
        "fallback": {"chrom": "6", "position": 32663851, "ref_allele": "C", "alt_allele": "T",
                      "gene": "HLA-DQB1", "functional_class": "intergenic", "maf_global": 0.39},
        "traits": [
            {
                "trait": "Rheumatoid Arthritis",
                "risk_allele": "T",
                "odds_ratio": 2.8,
                "beta": None,
                "p_value": 1e-200,
                "effect_description": "Located in the MHC/HLA region, the strongest genetic susceptibility locus for rheumatoid arthritis. Tags the HLA-DRB1 shared epitope alleles, which present citrullinated peptides to T cells, driving autoimmune joint inflammation. The HLA region contributes ~40% of genetic risk for RA.",
                "effect_summary": "Higher rheumatoid arthritis risk",
                "evidence_level": "high",
                "source_pmid": "17804836",
                "source_title": "Genome-wide association study of rheumatoid arthritis",
            },
        ],
    },
    {
        "rsid": "rs2476601",
        "fallback": {"chrom": "1", "position": 114377568, "ref_allele": "G", "alt_allele": "A",
                      "gene": "PTPN22", "functional_class": "missense", "maf_global": 0.08},
        "traits": [
            {
                "trait": "Autoimmune Disease Risk",
                "risk_allele": "A",
                "odds_ratio": 1.89,
                "beta": None,
                "p_value": 1e-50,
                "effect_description": "The R620W variant in PTPN22 is a master regulator of autoimmune susceptibility, associated with type 1 diabetes, rheumatoid arthritis, lupus, thyroid autoimmunity, and other conditions. The A allele alters T-cell receptor signaling threshold, promoting autoreactive T-cell survival. Almost exclusive to European-descent populations.",
                "effect_summary": "Higher autoimmune disease risk",
                "evidence_level": "high",
                "source_pmid": "15208781",
                "source_title": "A functional variant of LYP phosphatase is associated with type I diabetes",
            },
        ],
    },
    {
        "rsid": "rs12722489",
        "fallback": {"chrom": "10", "position": 6102012, "ref_allele": "C", "alt_allele": "T",
                      "gene": "IL2RA", "functional_class": "intronic", "maf_global": 0.15},
        "traits": [
            {
                "trait": "Multiple Sclerosis Risk",
                "risk_allele": "T",
                "odds_ratio": 1.25,
                "beta": None,
                "p_value": 1e-15,
                "effect_description": "Intronic variant in IL2RA (CD25), the high-affinity IL-2 receptor alpha chain critical for regulatory T-cell function. The T allele is associated with reduced Treg activity and increased MS risk. IL2RA variants are also associated with type 1 diabetes, suggesting shared autoimmune pathways.",
                "effect_summary": "Higher multiple sclerosis risk",
                "evidence_level": "high",
                "source_pmid": "19525953",
                "source_title": "Genetic risk and a primary role for cell-mediated immune mechanisms in multiple sclerosis",
            },
        ],
    },
    # ── More Metabolism / Nutrition ─────────────────────────────────────
    {
        "rsid": "rs762551",
        "fallback": {"chrom": "15", "position": 75041917, "ref_allele": "C", "alt_allele": "A",
                      "gene": "CYP1A2", "functional_class": "intronic", "maf_global": 0.33},
        "traits": [
            {
                "trait": "Caffeine Metabolism",
                "risk_allele": "C",
                "odds_ratio": 1.36,
                "beta": None,
                "p_value": 2e-8,
                "effect_description": "The -163C>A polymorphism determines caffeine metabolism speed. The A allele confers 'fast metabolizer' status with higher CYP1A2 inducibility, allowing rapid caffeine clearance. Slow metabolizers (C/C) who drink \u22653 cups of coffee/day have increased heart attack risk, while fast metabolizers (A/A) may have reduced risk.",
                "effect_summary": "Slower caffeine metabolism",
                "evidence_level": "high",
                "source_pmid": "16522833",
                "source_title": "Coffee, CYP1A2 genotype, and risk of myocardial infarction",
            },
        ],
    },
    {
        "rsid": "rs602662",
        "fallback": {"chrom": "19", "position": 49206985, "ref_allele": "G", "alt_allele": "A",
                      "gene": "FUT2", "functional_class": "missense", "maf_global": 0.37},
        "traits": [
            {
                "trait": "Vitamin B12 Levels",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": -0.12,
                "p_value": 3e-16,
                "effect_description": "Variant in FUT2 (secretor gene) that affects intestinal vitamin B12 absorption. The A allele reduces fucosyltransferase 2 activity, altering gut mucosa glycosylation and intrinsic factor binding. Non-secretors (homozygous A/A) tend to have lower B12 levels and may benefit from B12 supplementation monitoring.",
                "effect_summary": "Lower vitamin B12 levels",
                "evidence_level": "high",
                "source_pmid": "18660489",
                "source_title": "Genome-wide association study of vitamin B12 and folate levels",
            },
        ],
    },
    {
        "rsid": "rs2228570",
        "fallback": {"chrom": "12", "position": 48272895, "ref_allele": "C", "alt_allele": "T",
                      "gene": "VDR", "functional_class": "missense", "maf_global": 0.35},
        "traits": [
            {
                "trait": "Vitamin D Receptor Function",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 5e-8,
                "effect_description": "The FokI polymorphism in the vitamin D receptor creates a shorter, more transcriptionally active protein (f allele). The longer variant (F/T allele) has reduced VDR activity, potentially affecting calcium absorption, immune function, and bone density. VDR genotype influences optimal vitamin D supplementation dose.",
                "effect_summary": "Reduced vitamin D receptor activity",
                "evidence_level": "medium",
                "source_pmid": "15562834",
                "source_title": "Vitamin D receptor polymorphisms and cancer risk",
            },
        ],
    },
    # ── Additional high-traffic SNPs ────────────────────────────────────
    {
        "rsid": "rs1800795",
        "fallback": {"chrom": "7", "position": 22766645, "ref_allele": "G", "alt_allele": "C",
                      "gene": "IL6", "functional_class": "regulatory", "maf_global": 0.30},
        "traits": [
            {
                "trait": "Inflammation / IL-6 Levels",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": 0.27,
                "p_value": 1e-10,
                "effect_description": "The -174G/C promoter polymorphism in interleukin-6. The C allele reduces IL-6 transcription in some contexts. Lower IL-6 is generally anti-inflammatory, but the relationship is complex: this variant affects susceptibility to multiple conditions including cardiovascular disease, diabetes, and systemic lupus erythematosus.",
                "effect_summary": "Altered IL-6 levels",
                "evidence_level": "medium",
                "source_pmid": "11152661",
                "source_title": "Interleukin-6 promoter polymorphism in atherosclerosis",
            },
        ],
    },
    {
        "rsid": "rs334",
        "fallback": {"chrom": "11", "position": 5248232, "ref_allele": "T", "alt_allele": "A",
                      "gene": "HBB", "functional_class": "missense", "maf_global": 0.05},
        "traits": [
            {
                "trait": "Sickle Cell Disease / Malaria Resistance",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-200,
                "effect_description": "The HbS mutation (Glu6Val) in beta-globin. Homozygous A/A causes sickle cell disease with chronic anemia, pain crises, and organ damage. Heterozygous carriers (sickle cell trait) have ~90% protection against severe P. falciparum malaria, explaining the high allele frequency in malaria-endemic regions. The classic example of balanced selection in humans.",
                "effect_summary": "Sickle cell trait carrier",
                "evidence_level": "high",
                "source_pmid": "11700288",
                "source_title": "Sickle cell disease: molecular mechanisms and therapy",
            },
        ],
    },
    {
        "rsid": "rs1800629",
        "fallback": {"chrom": "6", "position": 31543031, "ref_allele": "G", "alt_allele": "A",
                      "gene": "TNF", "functional_class": "regulatory", "maf_global": 0.10},
        "traits": [
            {
                "trait": "Inflammatory Response",
                "risk_allele": "A",
                "odds_ratio": 1.5,
                "beta": None,
                "p_value": 1e-12,
                "effect_description": "The TNF -308G/A promoter variant. The A allele increases TNF-\u03b1 transcription by ~2-fold, promoting a stronger pro-inflammatory response. Associated with increased susceptibility to sepsis, cerebral malaria, autoimmune conditions, and variable responses to anti-TNF biologics (infliximab, adalimumab).",
                "effect_summary": "Stronger inflammatory response",
                "evidence_level": "high",
                "source_pmid": "15562834",
                "source_title": "TNF promoter polymorphisms and susceptibility to disease",
            },
        ],
    },
    {
        "rsid": "rs12255372",
        "fallback": {"chrom": "10", "position": 114808902, "ref_allele": "G", "alt_allele": "T",
                      "gene": "TCF7L2", "functional_class": "intronic", "maf_global": 0.22},
        "traits": [
            {
                "trait": "Type 2 Diabetes Risk",
                "risk_allele": "T",
                "odds_ratio": 1.33,
                "beta": None,
                "p_value": 1e-50,
                "effect_description": "Another strong variant in the TCF7L2 locus, in linkage disequilibrium with rs7903146. The T allele impairs pancreatic \u03b2-cell function and incretin signaling. Combined with rs7903146, these variants form a diabetes risk haplotype with substantial population-attributable risk.",
                "effect_summary": "Higher type 2 diabetes risk",
                "evidence_level": "high",
                "source_pmid": "16415884",
                "source_title": "Variant of transcription factor 7-like 2 (TCF7L2) gene confers risk of type 2 diabetes",
            },
        ],
    },
    {
        "rsid": "rs1799971",
        "fallback": {"chrom": "6", "position": 154360797, "ref_allele": "A", "alt_allele": "G",
                      "gene": "OPRM1", "functional_class": "missense", "maf_global": 0.12},
        "traits": [
            {
                "trait": "Opioid Sensitivity / Addiction Risk",
                "risk_allele": "G",
                "odds_ratio": 1.26,
                "beta": None,
                "p_value": 3e-8,
                "effect_description": "The A118G variant in the mu-opioid receptor (Asn40Asp). The G allele reduces receptor expression by ~1.5x and alters \u03b2-endorphin binding affinity. Carriers may require higher opioid doses for pain relief and show differential response to naltrexone for alcohol dependence treatment. Associated with altered stress response and reward processing.",
                "effect_summary": "Altered opioid sensitivity",
                "evidence_level": "high",
                "source_pmid": "12724789",
                "source_title": "Association of OPRM1 A118G variant with the relative reinforcing value of opioids",
            },
        ],
    },
    # ── Additional: Taste / Sensory ─────────────────────────────────────
    {
        "rsid": "rs1726866",
        "fallback": {"chrom": "7", "position": 141672705, "ref_allele": "G", "alt_allele": "A",
                      "gene": "TAS2R38", "functional_class": "missense", "maf_global": 0.43},
        "traits": [
            {
                "trait": "Bitter Taste Perception (PTC/PROP)",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-50,
                "effect_description": "rs1726866 is one of three key missense variants in TAS2R38 that together define whether you are a 'taster' or 'non-taster' of bitter compounds like phenylthiocarbamide (PTC) and PROP. The G allele (Val262) is part of the PAV taster haplotype; the A allele (Ala262) belongs to the AVI non-taster haplotype. AVI/AVI homozygotes barely notice the bitterness that PAV carriers find overwhelming.",
                "effect_summary": "Reduced bitter taste perception",
                "evidence_level": "high",
                "source_pmid": "12595690",
                "source_title": "Positional cloning of the human quantitative trait locus underlying taste sensitivity to phenylthiocarbamide",
            },
        ],
    },
    {
        "rsid": "rs713598",
        "fallback": {"chrom": "7", "position": 141673345, "ref_allele": "C", "alt_allele": "G",
                      "gene": "TAS2R38", "functional_class": "missense", "maf_global": 0.44},
        "traits": [
            {
                "trait": "Bitter Taste Perception (PTC/PROP)",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-50,
                "effect_description": "rs713598 encodes the amino acid at position 49 of TAS2R38. The G allele creates proline (Pro49, part of the PAV super-taster haplotype), while the C allele creates alanine (Ala49, part of the AVI non-taster haplotype). Together with rs1726866 and rs10246939, this trio determines whether you perceive bitter flavors intensely or barely notice them.",
                "effect_summary": "Reduced bitter taste perception",
                "evidence_level": "high",
                "source_pmid": "12595690",
                "source_title": "Positional cloning of the human quantitative trait locus underlying taste sensitivity to phenylthiocarbamide",
            },
        ],
    },
    {
        "rsid": "rs4481887",
        "fallback": {"chrom": "1", "position": 248496863, "ref_allele": "A", "alt_allele": "G",
                      "gene": "OR2M7", "functional_class": "intergenic", "maf_global": 0.35},
        "traits": [
            {
                "trait": "Asparagus Metabolite Detection",
                "risk_allele": "G",
                "odds_ratio": 2.08,
                "beta": None,
                "p_value": 1.41e-43,
                "effect_description": "After eating asparagus, the body converts asparagusic acid into pungent sulfur-containing compounds in urine. The A allele near OR2M7 (an olfactory receptor gene) is strongly associated with being able to perceive this asparagus aroma. GG individuals have anosmia to this specific odor. The ability to produce the odorous compounds is universal; only the ability to smell them varies.",
                "effect_summary": "Cannot smell asparagus metabolite",
                "evidence_level": "high",
                "source_pmid": "27965198",
                "source_title": "Sniffing out significant 'Pee values': genome wide association study of asparagus anosmia",
            },
        ],
    },
    # ── Additional: Athletic Performance ────────────────────────────────
    {
        "rsid": "rs1815739",
        "fallback": {"chrom": "11", "position": 66328095, "ref_allele": "C", "alt_allele": "T",
                      "gene": "ACTN3", "functional_class": "stop_gained", "maf_global": 0.39},
        "traits": [
            {
                "trait": "Sprint / Power Athletic Performance",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.001,
                "effect_description": "The ACTN3 R577X variant. Alpha-actinin-3 is expressed exclusively in fast-twitch (type II) muscle fibers responsible for explosive power and speed. The C allele (X) introduces a premature stop codon, preventing protein production. ~18% of people are XX and entirely alpha-actinin-3 deficient. TT (RR) individuals are over-represented among elite sprinters; CC (XX) may be better suited to endurance events.",
                "effect_summary": "Alpha-actinin-3 deficient",
                "evidence_level": "high",
                "source_pmid": "12879365",
                "source_title": "ACTN3 genotype is associated with human elite athletic performance",
            },
        ],
    },
    # ── Additional: Eye Color (OCA2 modifier) ───────────────────────────
    {
        "rsid": "rs7495174",
        "fallback": {"chrom": "15", "position": 28344238, "ref_allele": "A", "alt_allele": "G",
                      "gene": "OCA2", "functional_class": "intronic", "maf_global": 0.35},
        "traits": [
            {
                "trait": "Eye Color (Green/Hazel vs Brown)",
                "risk_allele": "G",
                "odds_ratio": 6.90,
                "beta": None,
                "p_value": 3e-24,
                "effect_description": "This intronic variant in OCA2 modifies iris color, particularly the green/hazel vs brown distinction that rs12913832 in HERC2 cannot fully explain. The A allele forms part of a three-SNP OCA2 haplotype found in ~90% of blue/green eyes in Europeans, while the G allele is enriched in brown-eyed individuals. Together with rs12913832, this provides much of the predictive power used by forensic eye-color tools.",
                "effect_summary": "Brown eye tendency",
                "evidence_level": "high",
                "source_pmid": "17236130",
                "source_title": "Genetic determinants of hair, eye and skin pigmentation in Europeans",
            },
        ],
    },
    # ── Additional: Viral Immunity ──────────────────────────────────────
    {
        "rsid": "rs12252",
        "fallback": {"chrom": "11", "position": 320772, "ref_allele": "A", "alt_allele": "G",
                      "gene": "IFITM3", "functional_class": "splice_site", "maf_global": 0.05},
        "traits": [
            {
                "trait": "Severe Influenza Risk",
                "risk_allele": "G",
                "odds_ratio": 2.37,
                "beta": None,
                "p_value": 0.004,
                "effect_description": "IFITM3 is a frontline innate immune protein that blocks influenza virus from escaping endosomes during cellular entry. The G allele disrupts a splice donor site, producing a truncated, less effective IFITM3 protein. Carriers are significantly more likely to be hospitalized with severe influenza (~2-2.4x higher odds). Most pronounced in East Asian populations where the G allele is more common (~25-44% vs ~3-5% in Europeans).",
                "effect_summary": "Higher severe influenza risk",
                "evidence_level": "high",
                "source_pmid": "22446628",
                "source_title": "IFITM3 restricts the morbidity and mortality associated with influenza",
            },
        ],
    },

    # ══════════════════════════════════════════════════════════════════════
    # NEW CATEGORIES — expanded from curated research
    # ══════════════════════════════════════════════════════════════════════

    # ── Clotting / Thrombophilia ───────────────────────────────────────────
    {
        "rsid": "rs6025",
        "fallback": {"chrom": "1", "position": 169519049, "ref_allele": "T", "alt_allele": "C",
                      "gene": "F5", "functional_class": "missense_variant", "maf_global": 0.017},
        "traits": [
            {
                "trait": "Venous Thromboembolism",
                "risk_allele": "T",
                "odds_ratio": 4.22,
                "beta": None,
                "p_value": None,
                "effect_description": "Factor V Leiden is caused by a single missense change (Arg506Gln) in the Factor V coagulation protein. The substitution removes the cleavage site used by activated protein C (APC) to switch off clotting, so blood coagulation remains active longer than normal. Heterozygous carriers have roughly a 4-fold higher lifetime risk of deep-vein thrombosis or pulmonary embolism compared to non-carriers; homozygotes face a risk roughly 11-fold above baseline. It is the most common inherited thrombophilia in people of European descent, found in ~2-7% of that population.",
                "effect_summary": "Higher blood clot risk",
                "evidence_level": "high",
                "source_pmid": "23900608",
                "source_title": "Risk of venous thromboembolism associated with single and combined effects of Factor V Leiden, Prothrombin 20210A and MTHFR C677T: a meta-analysis",
            },
        ],
    },
    {
        "rsid": "rs1799963",
        "fallback": {"chrom": "11", "position": 46761055, "ref_allele": "G", "alt_allele": "A",
                      "gene": "F2", "functional_class": "3_prime_UTR_variant", "maf_global": 0.008},
        "traits": [
            {
                "trait": "Venous Thromboembolism",
                "risk_allele": "A",
                "odds_ratio": 2.8,
                "beta": None,
                "p_value": 1e-10,
                "effect_description": "The Prothrombin G20210A variant sits in the 3' untranslated region of the prothrombin gene and enhances RNA processing, leading to ~30% higher circulating prothrombin (Factor II) levels. Elevated prothrombin tips the coagulation balance toward clot formation, giving heterozygous carriers roughly a 2-4-fold higher risk of deep-vein thrombosis or pulmonary embolism. It is the second most common inherited thrombophilia in European populations, found in about 1-3% of that group.",
                "effect_summary": "Higher blood clot risk",
                "evidence_level": "high",
                "source_pmid": "8807679",
                "source_title": "A common genetic variation in the 3'-untranslated region of the prothrombin gene is associated with elevated plasma prothrombin levels and an increase in venous thrombosis",
            },
        ],
    },
    {
        "rsid": "rs8176719",
        "fallback": {"chrom": "9", "position": 136132908, "ref_allele": "-", "alt_allele": "C",
                      "gene": "ABO", "functional_class": "frameshift_variant", "maf_global": 0.36},
        "traits": [
            {
                "trait": "ABO Blood Group (O vs Non-O)",
                "risk_allele": "C",
                "odds_ratio": 1.92,
                "beta": None,
                "p_value": 2.4e-16,
                "effect_description": "This single-base deletion at codon 261 of the ABO gene shifts the reading frame, abolishing glycosyltransferase activity and producing blood type O. Non-O blood groups (A, B, AB) carry higher circulating levels of von Willebrand factor (vWF) and Factor VIII, because ABO glycans on vWF reduce its clearance rate. People with blood type O have approximately half the risk of venous thromboembolism compared to those with non-O blood types (OR ~0.52). ABO genotype accounts for ~20-25% of variation in vWF levels.",
                "effect_summary": "Non-O blood type",
                "evidence_level": "high",
                "source_pmid": "22672568",
                "source_title": "A genome-wide association study of venous thromboembolism identifies risk variants in chromosomes 1q24.2 and 9q",
            },
        ],
    },
    {
        "rsid": "rs8176746",
        "fallback": {"chrom": "9", "position": 136131322, "ref_allele": "G", "alt_allele": "T",
                      "gene": "ABO", "functional_class": "missense_variant", "maf_global": 0.086},
        "traits": [
            {
                "trait": "ABO Blood Group B Antigen",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "The Leu265Met substitution encoded by rs8176746 is one of seven canonical amino-acid differences that switch the ABO glycosyltransferase from A-specificity (adding N-acetylgalactosamine) to B-specificity (adding galactose). Individuals carrying the T allele at this position produce the B antigen on red cell surfaces. Like blood type A, blood type B is associated with elevated von Willebrand factor and Factor VIII levels relative to blood type O, contributing to a modestly higher thrombosis risk.",
                "effect_summary": "Blood type B antigen",
                "evidence_level": "high",
                "source_pmid": "17393014",
                "source_title": "ABO blood group genotypes, plasma von Willebrand factor levels and loading of von Willebrand factor with A and B antigens",
            },
        ],
    },
    {
        "rsid": "rs1801020",
        "fallback": {"chrom": "5", "position": 176836532, "ref_allele": "A", "alt_allele": "G",
                      "gene": "F12", "functional_class": "5_prime_UTR_variant", "maf_global": 0.263},
        "traits": [
            {
                "trait": "Plasma Factor XII Level",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-20,
                "effect_description": "The rs1801020 variant sits in the 5'-untranslated region of the Factor XII (F12) gene and disrupts the canonical Kozak translation-initiation sequence. It also introduces a competing upstream ATG that stalls ribosomes, collectively reducing FXII protein production. Individuals homozygous for the minor allele have roughly half the circulating Factor XII of those homozygous for the major allele. Factor XII initiates the contact activation pathway of coagulation; lower FXII levels are paradoxically not associated with a clinically significant bleeding tendency, but may modulate thrombosis and inflammatory signaling.",
                "effect_summary": "Lower Factor XII levels",
                "evidence_level": "high",
                "source_pmid": "19786295",
                "source_title": "Combined cis-regulator elements as important mechanism affecting FXII plasma levels",
            },
        ],
    },

    # ── Diabetes / Metabolic ───────────────────────────────────────────────
    {
        "rsid": "rs5219",
        "fallback": {"chrom": "11", "position": 17409572, "ref_allele": "C", "alt_allele": "T",
                      "gene": "KCNJ11", "functional_class": "missense_variant", "maf_global": 0.34},
        "traits": [
            {
                "trait": "Type 2 Diabetes",
                "risk_allele": "T",
                "odds_ratio": 1.15,
                "beta": None,
                "p_value": 6.7e-11,
                "effect_description": "The T allele of rs5219 encodes the Lys23 variant (E23K) in the KCNJ11 gene, which forms the pore-forming subunit of the pancreatic beta-cell ATP-sensitive potassium channel (KATP). The Lys23 variant increases the open probability of the channel, making beta cells slightly less responsive to glucose-stimulated ATP rises and reducing insulin secretion. The OR of ~1.15 per allele has been replicated across dozens of GWAS in European, East Asian, and South Asian populations.",
                "effect_summary": "Higher type 2 diabetes risk",
                "evidence_level": "high",
                "source_pmid": "12829785",
                "source_title": "Variants of the gene encoding the Kir6.2 subunit of the KATP channel (KCNJ11) and susceptibility to type 2 diabetes",
            },
        ],
    },
    {
        "rsid": "rs13266634",
        "fallback": {"chrom": "8", "position": 118184783, "ref_allele": "C", "alt_allele": "T",
                      "gene": "SLC30A8", "functional_class": "missense_variant", "maf_global": 0.25},
        "traits": [
            {
                "trait": "Type 2 Diabetes",
                "risk_allele": "C",
                "odds_ratio": 1.12,
                "beta": None,
                "p_value": 5.3e-8,
                "effect_description": "The C allele of rs13266634 encodes the Arg325 variant (R325W) in SLC30A8, the zinc transporter ZnT8 that is almost exclusively expressed in pancreatic beta-cell insulin secretory granules. The Arg325 variant reduces zinc transport into granules, impairing insulin crystallization and processing. Paradoxically, rare loss-of-function SLC30A8 mutations are protective against T2D, while this common coding variant slightly increases risk.",
                "effect_summary": "Higher type 2 diabetes risk",
                "evidence_level": "high",
                "source_pmid": "17293876",
                "source_title": "A genome-wide association study identifies novel risk loci for type 2 diabetes",
            },
        ],
    },
    {
        "rsid": "rs560887",
        "fallback": {"chrom": "2", "position": 169763148, "ref_allele": "C", "alt_allele": "T",
                      "gene": "G6PC2", "functional_class": "intron_variant", "maf_global": 0.30},
        "traits": [
            {
                "trait": "Fasting Glucose Levels",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": 0.075,
                "p_value": 1e-83,
                "effect_description": "rs560887 in G6PC2 is the strongest common genetic determinant of fasting plasma glucose levels, explaining ~1% of population variance. G6PC2 encodes an islet-specific glucose-6-phosphatase catalytic subunit that acts as a negative regulator of glucose-stimulated insulin secretion. The C allele increases G6PC2 expression, raising the glucose threshold for insulin release and thereby increasing fasting glucose. Despite elevating fasting glucose, variants at this locus have a neutral or even slightly protective effect on T2D risk.",
                "effect_summary": "Higher fasting glucose",
                "evidence_level": "high",
                "source_pmid": "20081858",
                "source_title": "New genetic loci implicated in fasting glucose homeostasis and their impact on type 2 diabetes risk",
            },
        ],
    },
    {
        "rsid": "rs780094",
        "fallback": {"chrom": "2", "position": 27741237, "ref_allele": "C", "alt_allele": "T",
                      "gene": "GCKR", "functional_class": "intron_variant", "maf_global": 0.40},
        "traits": [
            {
                "trait": "Triglyceride Levels",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": 0.15,
                "p_value": 1e-133,
                "effect_description": "rs780094 in GCKR tags the functional missense variant P446L (rs1260326) in glucokinase regulatory protein. The T allele disrupts GCKR's ability to sequester glucokinase in the nucleus in the fasted state, leading to constitutively higher hepatic glucose uptake and glycolysis. This reduces fasting glucose but paradoxically increases de novo lipogenesis and triglyceride production. The pleiotropic effects — lower glucose but higher triglycerides — make this a textbook example of metabolic trade-offs in human genetics.",
                "effect_summary": "Elevated triglycerides",
                "evidence_level": "high",
                "source_pmid": "18372903",
                "source_title": "A common variant in the GCKR gene with an effect on fasting glucose is also associated with higher LDL cholesterol and triglycerides",
            },
        ],
    },

    # ── Autoimmune (additional) ────────────────────────────────────────────
    {
        "rsid": "rs2104286",
        "fallback": {"chrom": "10", "position": 6099045, "ref_allele": "C", "alt_allele": "T",
                      "gene": "IL2RA", "functional_class": "intron_variant", "maf_global": 0.25},
        "traits": [
            {
                "trait": "Multiple Sclerosis",
                "risk_allele": "T",
                "odds_ratio": 1.25,
                "beta": None,
                "p_value": 2.9e-8,
                "effect_description": "rs2104286 lies in intron 1 of IL2RA, the gene encoding the high-affinity IL-2 receptor alpha chain (CD25). The T allele reduces surface CD25 expression on CD4+ regulatory T cells (Tregs), impairing IL-2-dependent Treg proliferation and suppressive function. This disruption of peripheral immune tolerance increases susceptibility to multiple sclerosis. The association has been replicated in multiple large GWAS across European populations.",
                "effect_summary": "Higher multiple sclerosis risk",
                "evidence_level": "high",
                "source_pmid": "17660530",
                "source_title": "Risk alleles for multiple sclerosis identified by a genomewide study",
            },
        ],
    },
    {
        "rsid": "rs3135388",
        "fallback": {"chrom": "6", "position": 32413051, "ref_allele": "A", "alt_allele": "G",
                      "gene": "HLA-DRA", "functional_class": "intron_variant", "maf_global": 0.26},
        "traits": [
            {
                "trait": "Multiple Sclerosis",
                "risk_allele": "A",
                "odds_ratio": 2.88,
                "beta": None,
                "p_value": 1e-200,
                "effect_description": "rs3135388 is a near-perfect proxy (r² > 0.95 in Europeans) for the HLA-DRB1*15:01 allele, the single strongest genetic risk factor for multiple sclerosis. The A allele tags the DRB1*15:01 haplotype, which encodes an MHC class II molecule that presents myelin-derived peptides to autoreactive CD4+ T cells with high affinity, triggering the autoimmune demyelination characteristic of MS. Homozygous carriers have roughly 6-fold elevated risk.",
                "effect_summary": "Higher multiple sclerosis risk",
                "evidence_level": "high",
                "source_pmid": "17660530",
                "source_title": "Risk alleles for multiple sclerosis identified by a genomewide study",
            },
        ],
    },
    {
        "rsid": "rs7574865",
        "fallback": {"chrom": "2", "position": 191964633, "ref_allele": "G", "alt_allele": "T",
                      "gene": "STAT4", "functional_class": "intron_variant", "maf_global": 0.22},
        "traits": [
            {
                "trait": "Systemic Lupus Erythematosus",
                "risk_allele": "T",
                "odds_ratio": 1.57,
                "beta": None,
                "p_value": 1.7e-15,
                "effect_description": "rs7574865 in STAT4 is one of the most replicated non-HLA genetic risk factors for systemic lupus erythematosus (SLE). STAT4 is a transcription factor that mediates signalling downstream of IL-12 and IL-23 receptors, driving Th1/Th17 differentiation and type I interferon responses. The T allele increases STAT4 expression, amplifying pro-inflammatory signalling cascades central to lupus pathogenesis.",
                "effect_summary": "Higher lupus risk",
                "evidence_level": "high",
                "source_pmid": "17676033",
                "source_title": "A risk haplotype of STAT4 for systemic lupus erythematosus is over-expressed, correlates with anti-dsDNA and shows additive effects with two risk alleles of IRF5",
            },
            {
                "trait": "Rheumatoid Arthritis",
                "risk_allele": "T",
                "odds_ratio": 1.27,
                "beta": None,
                "p_value": None,
                "effect_description": "The STAT4 rs7574865 T allele is also associated with increased risk of rheumatoid arthritis (RA). A meta-analysis of 16,088 RA cases and 16,509 controls confirmed an OR of 1.27 per T allele for RA susceptibility. The association has been replicated across European and Asian populations. STAT4's role in IL-12/IL-23 signalling and Th1/Th17 cell differentiation makes it a pleiotropic autoimmune risk locus, contributing to both SLE and RA through shared inflammatory pathways.",
                "effect_summary": "Higher rheumatoid arthritis risk",
                "evidence_level": "high",
                "source_pmid": "19588142",
                "source_title": "Association between the rs7574865 polymorphism of STAT4 and rheumatoid arthritis: a meta-analysis",
            },
        ],
    },
    {
        "rsid": "rs2187668",
        "fallback": {"chrom": "6", "position": 32605884, "ref_allele": "T", "alt_allele": "C",
                      "gene": "HLA-DQA1", "functional_class": "intron_variant", "maf_global": 0.09},
        "traits": [
            {
                "trait": "Celiac Disease",
                "risk_allele": "C",
                "odds_ratio": 7.0,
                "beta": None,
                "p_value": 1e-300,
                "effect_description": "rs2187668 tags the HLA-DQ2.5 haplotype (DQA1*05:01/DQB1*02:01), which is carried by approximately 90-95% of all celiac disease patients. The DQ2.5 molecule has a binding groove that preferentially accommodates deamidated gluten peptides, presenting them to gut-homing CD4+ T cells and triggering the inflammatory cascade that destroys intestinal villi. Homozygous carriers face the highest celiac risk (OR ~7.0), while heterozygous DQ2.5/DQ8 individuals also have substantial risk.",
                "effect_summary": "Higher celiac disease risk",
                "evidence_level": "high",
                "source_pmid": "20190752",
                "source_title": "A genome-wide meta-analysis of celiac disease identifies novel risk loci and a pathogenic role for HLA",
            },
        ],
    },
    {
        "rsid": "rs7454108",
        "fallback": {"chrom": "6", "position": 32681483, "ref_allele": "T", "alt_allele": "C",
                      "gene": "HLA-DQB1", "functional_class": "intron_variant", "maf_global": 0.17},
        "traits": [
            {
                "trait": "Type 1 Diabetes",
                "risk_allele": "C",
                "odds_ratio": 4.5,
                "beta": None,
                "p_value": 1e-200,
                "effect_description": "rs7454108 tags the HLA-DR3/DQ2 and DR4/DQ8 haplotypes, the two strongest genetic risk factors for type 1 diabetes. These HLA class II molecules present beta-cell autoantigens (insulin, GAD65, IA-2) to CD4+ T cells, initiating the autoimmune destruction of pancreatic islets. Compound heterozygotes carrying both DR3/DQ2 and DR4/DQ8 (the DR3/4 genotype) face the highest T1D risk, with an OR of approximately 16 compared to the general population.",
                "effect_summary": "Higher type 1 diabetes risk",
                "evidence_level": "high",
                "source_pmid": "19430480",
                "source_title": "Genome-wide association study and meta-analysis find that over 40 loci affect risk of type 1 diabetes",
            },
        ],
    },
    {
        "rsid": "rs2395029",
        "fallback": {"chrom": "6", "position": 31431780, "ref_allele": "T", "alt_allele": "G",
                      "gene": "HCP5", "functional_class": "missense_variant", "maf_global": 0.05},
        "traits": [
            {
                "trait": "Abacavir Hypersensitivity (HLA-B*57:01 Tag)",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-50,
                "effect_description": "rs2395029 in HCP5 is a validated tag SNP for HLA-B*57:01, the allele that causes abacavir hypersensitivity syndrome in HIV-positive patients. The G allele predicts HLA-B*57:01 carrier status with ~100% sensitivity and ~99.4% specificity in Europeans. FDA labelling recommends HLA-B*57:01 testing before prescribing abacavir. This tag SNP was validated in >1,100 HIV patients (Young et al. 2008). Performance may be reduced in non-European populations due to HCP5 copy number variation and differing LD patterns.",
                "effect_summary": "Abacavir hypersensitivity risk",
                "evidence_level": "high",
                "source_pmid": "18684101",
                "source_title": "The HCP5 single-nucleotide polymorphism: a simple screening tool for prediction of hypersensitivity reaction to abacavir",
            },
        ],
    },
    {
        "rsid": "rs1061235",
        "fallback": {"chrom": "6", "position": 29913298, "ref_allele": "G", "alt_allele": "A",
                      "gene": "HLA-A", "functional_class": "upstream_gene_variant", "maf_global": 0.07},
        "traits": [
            {
                "trait": "Carbamazepine Hypersensitivity (HLA-A*31:01 Tag)",
                "risk_allele": "A",
                "odds_ratio": 8.0,
                "beta": None,
                "p_value": 1.7e-8,
                "effect_description": "rs1061235 is a proxy SNP for HLA-A*31:01, which is associated with carbamazepine-induced hypersensitivity reactions in Europeans (McCormack et al. 2011, NEJM). The A allele tags HLA-A*31:01 with ~100% sensitivity and 84-96% specificity in Europeans. A known 5-16% false positive rate exists due to cross-reactivity with HLA-A*33:03. Performance is reduced in South/West Asian and Native American populations where different HLA haplotype structures predominate.",
                "effect_summary": "Carbamazepine hypersensitivity risk",
                "evidence_level": "high",
                "source_pmid": "21428769",
                "source_title": "HLA-A*3101 and carbamazepine-induced hypersensitivity reactions in Europeans",
            },
        ],
    },
    {
        "rsid": "rs9262570",
        "fallback": {"chrom": "6", "position": 31012485, "ref_allele": "T", "alt_allele": "G",
                      "gene": "HLA-B", "functional_class": "intergenic_variant", "maf_global": 0.04},
        "traits": [
            {
                "trait": "Allopurinol Hypersensitivity / SJS/TEN (HLA-B*58:01 Tag)",
                "risk_allele": "G",
                "odds_ratio": 80.0,
                "beta": None,
                "p_value": 1e-15,
                "effect_description": "rs9262570 is a tag SNP for HLA-B*58:01, which is strongly associated with allopurinol-induced Stevens-Johnson syndrome (SJS) and toxic epidermal necrolysis (TEN). This tag was validated with 100% sensitivity and >95% specificity in Chinese Han populations (Zhang et al. 2015). However, it performs poorly in Europeans (26% sensitivity), where no reliable single tag SNP for HLA-B*58:01 has been identified. This result is most informative for individuals of East Asian ancestry; direct HLA typing is recommended for clinical decisions in other populations.",
                "effect_summary": "Allopurinol hypersensitivity risk",
                "evidence_level": "medium",
                "source_pmid": "25787076",
                "source_title": "Tag SNPs for HLA-B alleles that are associated with drug response and disease risk in the Chinese Han population",
            },
        ],
    },

    # ── Longevity / Aging ──────────────────────────────────────────────────
    {
        "rsid": "rs2802292",
        "fallback": {"chrom": "6", "position": 108908518, "ref_allele": "G", "alt_allele": "T",
                      "gene": "FOXO3", "functional_class": "intron_variant", "maf_global": 0.38},
        "traits": [
            {
                "trait": "Longevity",
                "risk_allele": "T",
                "odds_ratio": 1.26,
                "beta": None,
                "p_value": 1e-4,
                "effect_description": "rs2802292 in FOXO3 is one of the most replicated longevity-associated variants across multiple ethnic groups including Japanese, German, Chinese, Italian, and American cohorts. The T allele increases FOXO3 transcription, enhancing cellular stress resistance, DNA repair, autophagy, and apoptosis of damaged cells. FOXO3 is a master regulator of the insulin/IGF-1 signalling pathway, and its activation mimics some effects of caloric restriction.",
                "effect_summary": "Enhanced longevity",
                "evidence_level": "high",
                "source_pmid": "18765803",
                "source_title": "FOXO3A genotype is strongly associated with human longevity",
            },
        ],
    },
    {
        "rsid": "rs1556516",
        "fallback": {"chrom": "9", "position": 22100176, "ref_allele": "G", "alt_allele": "C",
                      "gene": "CDKN2B-AS1", "functional_class": "intron_variant", "maf_global": 0.48},
        "traits": [
            {
                "trait": "Coronary Artery Disease",
                "risk_allele": "C",
                "odds_ratio": 1.29,
                "beta": None,
                "p_value": 1e-20,
                "effect_description": "rs1556516 lies in the 9p21.3 locus within the long non-coding RNA CDKN2B-AS1 (ANRIL). This locus is the strongest common genetic risk factor for coronary artery disease, replicated across all major ethnic groups. The risk allele alters ANRIL splicing and expression, disrupting regulation of the adjacent tumor suppressors CDKN2A/B (p16INK4a/p15INK4b), promoting vascular smooth muscle proliferation and atherosclerotic plaque formation.",
                "effect_summary": "Higher coronary artery disease risk",
                "evidence_level": "high",
                "source_pmid": "17634449",
                "source_title": "A common allele on chromosome 9 associated with coronary heart disease",
            },
        ],
    },
    {
        "rsid": "rs10757278",
        "fallback": {"chrom": "9", "position": 22124477, "ref_allele": "A", "alt_allele": "G",
                      "gene": "CDKN2B-AS1", "functional_class": "intron_variant", "maf_global": 0.47},
        "traits": [
            {
                "trait": "Myocardial Infarction",
                "risk_allele": "G",
                "odds_ratio": 1.28,
                "beta": None,
                "p_value": 1.2e-20,
                "effect_description": "rs10757278 is a lead variant at the 9p21.3 locus, the most significant common genetic risk factor for myocardial infarction identified to date. The G allele disrupts a STAT1 binding site within the ANRIL (CDKN2B-AS1) gene, altering expression of the antisense RNA and its downstream targets in vascular tissue. The effect is independent of traditional risk factors (lipids, blood pressure, diabetes) and operates through vascular inflammation and smooth muscle cell proliferation.",
                "effect_summary": "Higher heart attack risk",
                "evidence_level": "high",
                "source_pmid": "17478679",
                "source_title": "A common variant on chromosome 9p21 affects the risk of myocardial infarction",
            },
        ],
    },
    {
        "rsid": "rs2200733",
        "fallback": {"chrom": "4", "position": 111710169, "ref_allele": "C", "alt_allele": "T",
                      "gene": "PITX2", "functional_class": "intergenic_variant", "maf_global": 0.11},
        "traits": [
            {
                "trait": "Atrial Fibrillation",
                "risk_allele": "T",
                "odds_ratio": 1.72,
                "beta": None,
                "p_value": 3.3e-13,
                "effect_description": "rs2200733 on chromosome 4q25 near PITX2 is the strongest common genetic risk factor for atrial fibrillation. PITX2 is a homeodomain transcription factor essential for left-right cardiac asymmetry; it suppresses the default sinoatrial node gene program in the left atrium. The T risk allele reduces PITX2 expression in left atrial cardiomyocytes via disruption of an enhancer element, predisposing to ectopic pacemaker activity and re-entrant arrhythmia circuits.",
                "effect_summary": "Higher atrial fibrillation risk",
                "evidence_level": "high",
                "source_pmid": "17603472",
                "source_title": "Variants in ZFHX3 and other loci associated with atrial fibrillation",
            },
        ],
    },
    {
        "rsid": "rs7025486",
        "fallback": {"chrom": "9", "position": 124422403, "ref_allele": "A", "alt_allele": "G",
                      "gene": "DAB2IP", "functional_class": "intron_variant", "maf_global": 0.26},
        "traits": [
            {
                "trait": "Abdominal Aortic Aneurysm",
                "risk_allele": "G",
                "odds_ratio": 1.21,
                "beta": None,
                "p_value": 4.6e-10,
                "effect_description": "rs7025486 in DAB2IP (DAB2 interacting protein) is associated with both abdominal aortic aneurysm and early-onset coronary heart disease. DAB2IP is a Ras-GTPase-activating protein that inhibits TNF-mediated NF-kB activation in vascular smooth muscle cells. The G allele reduces DAB2IP expression, leading to enhanced vascular inflammation and extracellular matrix degradation that promotes aneurysm formation and atherosclerosis.",
                "effect_summary": "Higher aortic aneurysm risk",
                "evidence_level": "high",
                "source_pmid": "21378990",
                "source_title": "Genome-wide association study of coronary artery disease and abdominal aortic aneurysm identifies shared risk loci",
            },
        ],
    },

    # ── Athletic Performance / Injury ──────────────────────────────────────
    {
        "rsid": "rs1800012",
        "fallback": {"chrom": "17", "position": 48277749, "ref_allele": "G", "alt_allele": "T",
                      "gene": "COL1A1", "functional_class": "intron_variant", "maf_global": 0.17},
        "traits": [
            {
                "trait": "Soft Tissue Injury Susceptibility",
                "risk_allele": "T",
                "odds_ratio": 0.43,
                "beta": None,
                "p_value": 0.004,
                "effect_description": "rs1800012 (Sp1 binding site polymorphism, +1245 G>T) in COL1A1 affects type I collagen production. The rare T allele alters an Sp1 transcription factor binding site in intron 1, increasing the alpha1(I)-to-alpha2(I) collagen chain ratio. This produces altered collagen fibril architecture in tendons and ligaments. Paradoxically, the T allele appears protective against cruciate ligament rupture (OR ~0.43) and shoulder dislocations, but is associated with reduced bone mineral density and increased osteoporotic fracture risk.",
                "effect_summary": "Lower ligament injury risk",
                "evidence_level": "medium",
                "source_pmid": "19165182",
                "source_title": "The COL1A1 gene Sp1 binding site polymorphism predisposes to the development of ligamentous injuries",
            },
        ],
    },
    {
        "rsid": "rs8192678",
        "fallback": {"chrom": "4", "position": 23815662, "ref_allele": "G", "alt_allele": "A",
                      "gene": "PPARGC1A", "functional_class": "missense_variant", "maf_global": 0.35},
        "traits": [
            {
                "trait": "Endurance Exercise Capacity",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.002,
                "effect_description": "rs8192678 encodes the Gly482Ser substitution in PGC-1α, the master transcriptional coactivator of mitochondrial biogenesis. The Ser482 (A) allele reduces PGC-1α transcriptional activity, leading to lower mitochondrial content in skeletal muscle, reduced oxidative phosphorylation capacity, and impaired adaptation to endurance training. The Gly482 (G) allele is enriched in elite endurance athletes across multiple studies in European and Asian populations.",
                "effect_summary": "Reduced endurance capacity",
                "evidence_level": "medium",
                "source_pmid": "19526209",
                "source_title": "PGC-1alpha genotype (Gly482Ser) predicts exceptional endurance capacity in European men",
            },
        ],
    },
    {
        "rsid": "rs4253778",
        "fallback": {"chrom": "22", "position": 46630634, "ref_allele": "G", "alt_allele": "C",
                      "gene": "PPARA", "functional_class": "intron_variant", "maf_global": 0.14},
        "traits": [
            {
                "trait": "Power vs Endurance Athletic Performance",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.005,
                "effect_description": "rs4253778 in PPARα (peroxisome proliferator-activated receptor alpha) influences fatty acid oxidation capacity in skeletal muscle and heart. The C allele is associated with reduced PPARα transcriptional activity and is over-represented in power/sprint athletes, while the G allele (higher fat oxidation) is enriched in endurance athletes. PPARα regulates expression of genes involved in fatty acid transport and beta-oxidation, directly affecting the muscle's fuel preference during exercise.",
                "effect_summary": "Power-oriented muscle profile",
                "evidence_level": "medium",
                "source_pmid": "15026790",
                "source_title": "The PPAR-alpha gene variation and physical performance in Russian athletes",
            },
        ],
    },
    {
        "rsid": "rs12722",
        "fallback": {"chrom": "9", "position": 137734416, "ref_allele": "C", "alt_allele": "T",
                      "gene": "COL5A1", "functional_class": "3_prime_UTR_variant", "maf_global": 0.34},
        "traits": [
            {
                "trait": "Achilles Tendon Injury Risk",
                "risk_allele": "T",
                "odds_ratio": 1.8,
                "beta": None,
                "p_value": 0.001,
                "effect_description": "rs12722 in the 3'-UTR of COL5A1 affects the stability and secondary structure of the mRNA, altering type V collagen production. Type V collagen is a minor but critical component of collagen fibrils in tendons, where it regulates fibril diameter. The T allele is associated with altered fibril assembly and reduced tendon mechanical strength, increasing susceptibility to Achilles tendinopathy and rupture, particularly in physically active populations.",
                "effect_summary": "Higher Achilles tendon injury risk",
                "evidence_level": "medium",
                "source_pmid": "16818727",
                "source_title": "Sequence variants within the 3'-UTR of the COL5A1 gene are associated with Achilles tendinopathy",
            },
        ],
    },

    # ── Mental Health / Cognition (additional) ─────────────────────────────
    {
        "rsid": "rs25531",
        "fallback": {"chrom": "17", "position": 28564346, "ref_allele": "T", "alt_allele": "C",
                      "gene": "SLC6A4", "functional_class": "2kb_upstream_variant", "maf_global": 0.026},
        "traits": [
            {
                "trait": "Panic Disorder",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "rs25531 is a functional SNP within the 5-HTTLPR promoter region of the serotonin transporter gene SLC6A4. The C minor allele tags the low-expression LG haplotype, which drives serotonin transporter levels down to a level comparable to the short (S) allele, despite being embedded in the traditionally 'long' promoter. Carriers of the low-expression haplotype show higher neuroticism and anxiety-related phenotypes and elevated comorbidity rates in panic disorder patients, including co-occurring major depression and agoraphobia.",
                "effect_summary": "Higher anxiety vulnerability",
                "evidence_level": "medium",
                "source_pmid": "33333511",
                "source_title": "Association of Serotonin Transporter Gene (5-HTTLPR/rs25531) Polymorphism with Comorbidities of Panic Disorder",
            },
        ],
    },
    {
        "rsid": "rs1800955",
        "fallback": {"chrom": "11", "position": 636784, "ref_allele": "T", "alt_allele": "C",
                      "gene": "DRD4", "functional_class": "2kb_upstream_variant", "maf_global": 0.406},
        "traits": [
            {
                "trait": "Novelty Seeking",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-4,
                "effect_description": "rs1800955 (-521C/T) lies in the promoter of the dopamine D4 receptor gene DRD4, where the T allele reduces transcriptional efficiency by approximately 40% relative to C. The C allele (higher receptor expression) was associated with elevated novelty-seeking scores on the Temperament and Character Inventory, with the CC genotype showing the highest scores and TT the lowest. A subsequent meta-analysis confirmed a modest but replicable association, with the C allele accounting for roughly 2% of phenotypic variance.",
                "effect_summary": "Higher novelty seeking",
                "evidence_level": "medium",
                "source_pmid": "11244482",
                "source_title": "Association between Novelty Seeking and the -521 C/T polymorphism in the promoter region of the DRD4 gene",
            },
        ],
    },
    {
        "rsid": "rs4570625",
        "fallback": {"chrom": "12", "position": 72331923, "ref_allele": "G", "alt_allele": "T",
                      "gene": "TPH2", "functional_class": "2kb_upstream_variant", "maf_global": 0.352},
        "traits": [
            {
                "trait": "Major Depressive Disorder",
                "risk_allele": "G",
                "odds_ratio": 1.20,
                "beta": None,
                "p_value": 0.0011,
                "effect_description": "rs4570625 (G-703T) is a promoter polymorphism in TPH2, the gene encoding the rate-limiting enzyme for serotonin synthesis in the brain. A meta-analysis of 27 studies found that the T allele was protective against major depressive disorder (OR = 0.83), meaning the G allele confers elevated risk. The G allele is also associated with enhanced amygdala reactivity to negative stimuli and higher harm-avoidance scores in healthy volunteers.",
                "effect_summary": "Higher depression risk",
                "evidence_level": "high",
                "source_pmid": "22693556",
                "source_title": "TPH2 Gene Polymorphisms and Major Depression - A Meta-Analysis",
            },
        ],
    },
    {
        "rsid": "rs165599",
        "fallback": {"chrom": "22", "position": 19956781, "ref_allele": "G", "alt_allele": "A",
                      "gene": "COMT", "functional_class": "3prime_UTR_variant", "maf_global": 0.354},
        "traits": [
            {
                "trait": "Anxiety Spectrum Disorders",
                "risk_allele": "A",
                "odds_ratio": 1.95,
                "beta": None,
                "p_value": 1.97e-5,
                "effect_description": "rs165599 lies in the 3' UTR of COMT and tags a low-expression haplotype that reduces COMT mRNA stability. When analysed as a two-marker haplotype with the functional rs4680 (Val158Met), the combination was associated with approximately doubled risk for anxiety spectrum disorders including generalised anxiety disorder, neuroticism, major depression, panic disorder, and social phobia in females. The association was restricted to women, consistent with sex-specific modulation of prefrontal dopamine catabolism by oestrogen.",
                "effect_summary": "Higher anxiety disorder risk",
                "evidence_level": "medium",
                "source_pmid": "18436194",
                "source_title": "COMT Contributes to Genetic Susceptibility Shared Among Anxiety Spectrum Phenotypes",
            },
        ],
    },

    # ── Vision ─────────────────────────────────────────────────────────────
    {
        "rsid": "rs10034228",
        "fallback": {"chrom": "4", "position": 112611750, "ref_allele": "T", "alt_allele": "C",
                      "gene": None, "functional_class": "intergenic_variant", "maf_global": 0.317},
        "traits": [
            {
                "trait": "High-Grade Myopia",
                "risk_allele": "C",
                "odds_ratio": 1.23,
                "beta": None,
                "p_value": 7.7e-13,
                "effect_description": "The C allele at rs10034228 in the intergenic MYP11 region on chromosome 4q25 is associated with increased susceptibility to high-grade myopia (spherical equivalent <= -6.0 diopters) in Han Chinese individuals. The locus falls within a gene desert containing expressed sequence tags; the precise molecular mechanism linking this variant to ocular axial elongation remains under investigation.",
                "effect_summary": "Higher severe myopia risk",
                "evidence_level": "high",
                "source_pmid": "21505071",
                "source_title": "A genome-wide association study reveals association between common variants in an intergenic region of 4q25 and high-grade myopia",
            },
        ],
    },
    {
        "rsid": "rs1048661",
        "fallback": {"chrom": "15", "position": 74219546, "ref_allele": "G", "alt_allele": "T",
                      "gene": "LOXL1", "functional_class": "missense_variant", "maf_global": 0.311},
        "traits": [
            {
                "trait": "Exfoliation Glaucoma",
                "risk_allele": "G",
                "odds_ratio": 1.99,
                "beta": None,
                "p_value": 2.3e-12,
                "effect_description": "rs1048661 encodes the R141L amino acid change in exon 1 of LOXL1, a lysyl oxidase-like enzyme essential for cross-linking elastin and collagen fibers in the extracellular matrix. The G allele (risk in Europeans) disrupts normal elastin fiber assembly in the trabecular meshwork and lens capsule, promoting accumulation of exfoliative fibrillar material. Affected individuals progress to exfoliation glaucoma through elevated intraocular pressure caused by trabecular meshwork obstruction. Notably, the risk allele reverses in East Asian populations, where the T allele confers markedly elevated risk.",
                "effect_summary": "Higher glaucoma risk",
                "evidence_level": "high",
                "source_pmid": "17690259",
                "source_title": "Common sequence variants in the LOXL1 gene confer susceptibility to exfoliation glaucoma",
            },
        ],
    },
    {
        "rsid": "rs10490924",
        "fallback": {"chrom": "10", "position": 124214448, "ref_allele": "G", "alt_allele": "T",
                      "gene": "ARMS2", "functional_class": "missense_variant", "maf_global": 0.287},
        "traits": [
            {
                "trait": "Age-Related Macular Degeneration",
                "risk_allele": "T",
                "odds_ratio": 2.66,
                "beta": None,
                "p_value": 5.3e-30,
                "effect_description": "The T allele of rs10490924 introduces an Ala69Ser substitution in the ARMS2 protein, a mitochondrial outer-membrane protein expressed in retinal photoreceptors. Homozygous TT carriers have approximately 7-fold increased risk of AMD. The T allele reduces superoxide dismutase (SOD) activity, causing accumulation of reactive oxygen species and heightened oxidative damage — a key driver of drusen formation and photoreceptor degeneration in AMD. The variant acts independently of the CFH Y402H risk variant and is one of the two most strongly associated common AMD loci genome-wide.",
                "effect_summary": "Higher macular degeneration risk",
                "evidence_level": "high",
                "source_pmid": "16174643",
                "source_title": "Hypothetical LOC387715 is a second major susceptibility gene for age-related macular degeneration",
            },
        ],
    },
    {
        "rsid": "rs1061170",
        "fallback": {"chrom": "1", "position": 196659237, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CFH", "functional_class": "missense_variant", "maf_global": 0.36},
        "traits": [
            {
                "trait": "Age-Related Macular Degeneration",
                "risk_allele": "C",
                "odds_ratio": 2.45,
                "beta": None,
                "p_value": 1e-7,
                "effect_description": "rs1061170 encodes the Y402H substitution (Tyr->His at residue 402) in complement factor H (CFH), a key inhibitor of the alternative complement pathway. The His402 (C) risk allele alters the heparin- and C-reactive protein-binding domain, reducing its ability to regulate complement activation on drusen and Bruch's membrane in the macula. This leads to chronic complement-mediated inflammation and oxidative damage. Homozygous CC carriers face 5-7-fold increased AMD risk, and the variant accounts for approximately 43-50% of the population-attributable risk for AMD in Europeans.",
                "effect_summary": "Higher macular degeneration risk",
                "evidence_level": "high",
                "source_pmid": "15761120",
                "source_title": "Complement factor H variant increases the risk of age-related macular degeneration",
            },
        ],
    },

    # ── Bone Health ────────────────────────────────────────────────────────
    {
        "rsid": "rs2282679",
        "fallback": {"chrom": "4", "position": 72608383, "ref_allele": "T", "alt_allele": "G",
                      "gene": "GC", "functional_class": "intron_variant", "maf_global": 0.21},
        "traits": [
            {
                "trait": "Vitamin D Levels",
                "risk_allele": "G",
                "odds_ratio": 1.63,
                "beta": None,
                "p_value": 3.5e-50,
                "effect_description": "The G allele of rs2282679 in the GC gene, which encodes vitamin D-binding protein (DBP), is strongly associated with reduced circulating 25-hydroxyvitamin D levels. DBP is the principal plasma carrier of vitamin D metabolites; reduced DBP expression impairs transport of vitamin D to target tissues. Carriers of two copies of the G allele have median 25(OH)D levels approximately 18% lower than non-carriers, more than doubling the risk of vitamin D insufficiency.",
                "effect_summary": "Lower vitamin D levels",
                "evidence_level": "high",
                "source_pmid": "20541252",
                "source_title": "Common genetic determinants of vitamin D insufficiency: a genome-wide association study",
            },
        ],
    },
    {
        "rsid": "rs12785878",
        "fallback": {"chrom": "11", "position": 71167449, "ref_allele": "G", "alt_allele": "T",
                      "gene": "DHCR7", "functional_class": "intron_variant", "maf_global": 0.35},
        "traits": [
            {
                "trait": "Vitamin D Levels",
                "risk_allele": "G",
                "odds_ratio": "",
                "beta": None,
                "p_value": "",
                "effect_description": "rs12785878 lies in an intron of NADSYN1 adjacent to DHCR7, which encodes 7-dehydrocholesterol reductase — the enzyme that competes with the vitamin D synthesis pathway by converting 7-dehydrocholesterol (the skin precursor of vitamin D3) to cholesterol. The G allele is associated with lower circulating 25(OH)D levels; G-allele carriers have less 7-DHC available for UV-driven conversion to pre-vitamin D3.",
                "effect_summary": "Lower vitamin D levels",
                "evidence_level": "high",
                "source_pmid": "20541252",
                "source_title": "Common genetic determinants of vitamin D insufficiency: a genome-wide association study",
            },
        ],
    },
    {
        "rsid": "rs10741657",
        "fallback": {"chrom": "11", "position": 14914878, "ref_allele": "A", "alt_allele": "G",
                      "gene": "CYP2R1", "functional_class": "intron_variant", "maf_global": 0.34},
        "traits": [
            {
                "trait": "Vitamin D Levels",
                "risk_allele": "G",
                "odds_ratio": 1.21,
                "beta": None,
                "p_value": 3.3e-20,
                "effect_description": "rs10741657 resides near the 5' end of CYP2R1, which encodes the principal hepatic vitamin D 25-hydroxylase that converts vitamin D3 into the main circulating form, 25(OH)D3. The G allele is associated with reduced CYP2R1 expression and activity, leading to lower serum 25-hydroxyvitamin D concentrations. This variant also predicts attenuated response to high-dose vitamin D3 supplementation. For a single G allele there is an odds ratio of 1.21 for having vitamin d insufficency, defined as 25-hydroxyvitamin D concentration <75 nmol/L.",
                "effect_summary": "Lower vitamin D levels",
                "evidence_level": "high",
                "source_pmid": "20541252",
                "source_title": "Common genetic determinants of vitamin D insufficiency: a genome-wide association study",
            },
        ],
    },
    {
        "rsid": "rs9921222",
        "fallback": {"chrom": "16", "position": 375782, "ref_allele": "C", "alt_allele": "T",
                      "gene": "AXIN1", "functional_class": "intron_variant", "maf_global": 0.43},
        "traits": [
            {
                "trait": "Bone Mineral Density",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.001,
                "effect_description": "rs9921222 is an intronic variant of AXIN1, a scaffold protein in the beta-catenin destruction complex that acts as a negative regulator of WNT signaling. The T allele creates a higher-affinity binding site for GATA4 and estrogen receptor alpha in osteoblasts, resulting in increased AXIN1 expression, suppressed WNT/beta-catenin activity, and reduced osteoblast differentiation. TT homozygotes show markedly lower lumbar spine and femoral neck BMD.",
                "effect_summary": "Lower bone mineral density",
                "evidence_level": "medium",
                "source_pmid": "35678873",
                "source_title": "GATA4 and estrogen receptor alpha bind at SNPs rs9921222 and rs10794639 to regulate AXIN1 expression in osteoblasts",
            },
        ],
    },
    {
        "rsid": "rs3736228",
        "fallback": {"chrom": "11", "position": 68201295, "ref_allele": "C", "alt_allele": "T",
                      "gene": "LRP5", "functional_class": "missense_variant", "maf_global": 0.14},
        "traits": [
            {
                "trait": "Osteoporosis and Fracture Risk",
                "risk_allele": "T",
                "odds_ratio": 1.19,
                "beta": None,
                "p_value": 0.014,
                "effect_description": "rs3736228 causes a missense substitution p.Ala1330Val in LRP5, a co-receptor in the WNT/beta-catenin signalling pathway essential for osteoblast function. The Val allele disrupts a propeller domain contact required for efficient WNT ligand binding, reducing downstream beta-catenin signalling. Meta-analyses show that A/A homozygotes have significantly higher lumbar spine BMD than T-allele carriers. The T allele increases fracture/osteoporosis risk with OR 1.19 per allele, rising to OR 1.76 in homozygous T/T individuals.",
                "effect_summary": "Higher osteoporosis risk",
                "evidence_level": "high",
                "source_pmid": "25580429",
                "source_title": "Common polymorphism in the LRP5 gene may increase the risk of bone fracture and osteoporosis",
            },
        ],
    },

    # ── Skin / Hair / Appearance ───────────────────────────────────────────
    {
        "rsid": "rs1805008",
        "fallback": {"chrom": "16", "position": 89986144, "ref_allele": "C", "alt_allele": "T",
                      "gene": "MC1R", "functional_class": "missense_variant", "maf_global": 0.015},
        "traits": [
            {
                "trait": "Red Hair Color",
                "risk_allele": "T",
                "odds_ratio": 7.86,
                "beta": None,
                "p_value": 4.2e-95,
                "effect_description": "The T allele of MC1R rs1805008 (Arg160Trp, R160W) is one of the three strongest known genetic determinants of red hair. It encodes a loss-of-function variant in the melanocortin-1 receptor, shifting melanin synthesis from eumelanin (brown/black) toward phaeomelanin (red/yellow). Individuals who are compound heterozygous or homozygous for high-penetrance MC1R variants including R160W have up to a 96% probability of having pure red hair.",
                "effect_summary": "Red hair",
                "evidence_level": "high",
                "source_pmid": "17952075",
                "source_title": "Genetic determinants of hair, eye and skin pigmentation in Europeans",
            },
        ],
    },
    {
        "rsid": "rs1805009",
        "fallback": {"chrom": "16", "position": 89986546, "ref_allele": "G", "alt_allele": "C",
                      "gene": "MC1R", "functional_class": "missense_variant", "maf_global": 0.011},
        "traits": [
            {
                "trait": "Red Hair Color",
                "risk_allele": "C",
                "odds_ratio": 5.10,
                "beta": None,
                "p_value": 1e-40,
                "effect_description": "The C allele of rs1805009 encodes the Asp294His (D294H) substitution in the MC1R protein, one of three canonical high-penetrance 'R' alleles strongly associated with red hair. D294H disrupts normal receptor signalling, markedly reducing cAMP-mediated eumelanin induction in melanocytes. Individuals homozygous or compound-heterozygous for D294H and other MC1R R alleles almost invariably present with red hair and fair skin. The variant has its highest prevalence in the British Isles.",
                "effect_summary": "Red hair",
                "evidence_level": "high",
                "source_pmid": "17952075",
                "source_title": "Genetic determinants of hair, eye and skin pigmentation in Europeans",
            },
        ],
    },
    {
        "rsid": "rs12821256",
        "fallback": {"chrom": "12", "position": 89328335, "ref_allele": "T", "alt_allele": "C",
                      "gene": "KITLG", "functional_class": "regulatory_region_variant", "maf_global": 0.03},
        "traits": [
            {
                "trait": "Blonde Hair Color",
                "risk_allele": "C",
                "odds_ratio": 2.32,
                "beta": None,
                "p_value": 5.5e-14,
                "effect_description": "rs12821256 lies within a hair-follicle-specific enhancer approximately 355 kb upstream of the KITLG (KIT Ligand / SCF) transcription start site. The C allele alters a binding motif for the LEF1 transcription factor, reducing enhancer activity by ~20% in keratinocytes and lowering KITLG expression in hair follicle melanocytes, which decreases melanin production and produces lighter (blonde) hair. The C allele is almost exclusively present in northern European populations.",
                "effect_summary": "Blonde hair",
                "evidence_level": "high",
                "source_pmid": "24880339",
                "source_title": "A molecular basis for classic blond hair color in Europeans",
            },
        ],
    },
    {
        "rsid": "rs4778138",
        "fallback": {"chrom": "15", "position": 28335820, "ref_allele": "A", "alt_allele": "G",
                      "gene": "OCA2", "functional_class": "intron_variant", "maf_global": 0.32},
        "traits": [
            {
                "trait": "Eye Color (Blue vs Brown)",
                "risk_allele": "A",
                "odds_ratio": 3.50,
                "beta": None,
                "p_value": 1e-54,
                "effect_description": "rs4778138 resides in intron 1 of OCA2 and is one of three tightly linked SNPs forming the TGT haplotype that explains the majority of human blue-versus-brown eye color variation. OCA2 encodes the P protein, a melanosomal transporter critical for melanin biosynthesis; intronic variants in this block regulate OCA2 expression in iris melanocytes. The A allele at rs4778138 is carried on the haplotype associated with blue eyes.",
                "effect_summary": "Blue eyes",
                "evidence_level": "high",
                "source_pmid": "17236130",
                "source_title": "A three-single-nucleotide polymorphism haplotype in intron 1 of OCA2 explains most human eye-color variation",
            },
        ],
    },
    {
        "rsid": "rs1393350",
        "fallback": {"chrom": "11", "position": 89011046, "ref_allele": "G", "alt_allele": "A",
                      "gene": "TYR", "functional_class": "intron_variant", "maf_global": 0.08},
        "traits": [
            {
                "trait": "Freckling",
                "risk_allele": "A",
                "odds_ratio": 1.52,
                "beta": None,
                "p_value": 2.41e-14,
                "effect_description": "rs1393350 is an intronic variant in TYR (tyrosinase, the rate-limiting enzyme of melanin synthesis) that tags the coding variant rs1126809 (R402Q) via strong linkage disequilibrium (r2=0.86). The A allele is associated with reduced TYR activity, lighter skin, and increased freckling propensity. It also shows a modest shift toward blue versus green iris pigmentation.",
                "effect_summary": "Increased freckling",
                "evidence_level": "high",
                "source_pmid": "18488028",
                "source_title": "Two newly identified genetic determinants of pigmentation in Europeans",
            },
        ],
    },
    {
        "rsid": "rs1126809",
        "fallback": {"chrom": "11", "position": 89017961, "ref_allele": "G", "alt_allele": "A",
                      "gene": "TYR", "functional_class": "missense_variant", "maf_global": 0.17},
        "traits": [
            {
                "trait": "Skin Sun Sensitivity",
                "risk_allele": "A",
                "odds_ratio": 1.65,
                "beta": None,
                "p_value": 7.1e-13,
                "effect_description": "rs1126809 encodes the Arg402Gln (R402Q) substitution in tyrosinase. The glutamine-402 enzyme is thermolabile and subject to endoplasmic reticulum retention at 37C, retaining only ~25% of wild-type catalytic activity. This partial loss-of-function reduces constitutive skin pigmentation and impairs the tanning response to UV exposure. The A allele is common in Europeans (~28%) but rare in Africans (~5%) and absent in East Asians.",
                "effect_summary": "Higher sun sensitivity",
                "evidence_level": "high",
                "source_pmid": "18488028",
                "source_title": "Two newly identified genetic determinants of pigmentation in Europeans",
            },
        ],
    },
    {
        "rsid": "rs16891982",
        "fallback": {"chrom": "5", "position": 33951693, "ref_allele": "C", "alt_allele": "G",
                      "gene": "SLC45A2", "functional_class": "missense_variant", "maf_global": 0.28},
        "traits": [
            {
                "trait": "Skin Pigmentation",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": -0.036,
                "p_value": 1e-10,
                "effect_description": "rs16891982 encodes the Leu374Phe (L374F) substitution in SLC45A2 (MATP/AIM1), a transporter protein essential for melanosome acidification and melanin biosynthesis. The C allele (374F) is nearly fixed in Europeans (>95%) but rare in Africans and East Asians, and is one of the two strongest known genetic determinants of skin pigmentation in humans alongside SLC24A5 rs1426654. The 374F (C) allele associates with pale skin, blue/green eyes, and blonde hair.",
                "effect_summary": "Lighter skin",
                "evidence_level": "high",
                "source_pmid": "17999355",
                "source_title": "A genomewide association study of skin pigmentation in a South Asian population",
            },
        ],
    },
    {
        "rsid": "rs3827760",
        "fallback": {"chrom": "2", "position": 109513601, "ref_allele": "A", "alt_allele": "C",
                      "gene": "EDAR", "functional_class": "missense_variant", "maf_global": 0.24},
        "traits": [
            {
                "trait": "Hair Thickness",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 7.7e-10,
                "effect_description": "rs3827760 encodes the Val370Ala substitution in the intracellular death domain of EDAR (ectodysplasin A receptor). The 370A variant has gain-of-function properties, producing stronger NF-kB signalling. This leads to enlarged hair follicle placodes during embryogenesis, resulting in thicker, rounder cross-section hair shafts characteristic of East Asian hair morphology. The C allele is found at ~70-90% frequency in East Asian and Native American populations but is essentially absent from Europeans and Africans. It is also the primary genetic determinant of shovel-shaped incisors.",
                "effect_summary": "Thicker hair",
                "evidence_level": "high",
                "source_pmid": "18704500",
                "source_title": "A replication study confirmed the EDAR gene to be a major contributor to population differentiation regarding head hair thickness in Asia",
            },
        ],
    },

    # ── Sleep / Circadian ─────────────────────────────────────────────
    {
        "rsid": "rs57875989",
        "fallback": {"chrom": "1", "position": 7876284, "ref_allele": "G", "alt_allele": "A",
                      "gene": "PER3", "functional_class": "coding_sequence_variant", "maf_global": 0.25},
        "traits": [
            {
                "trait": "Delayed Sleep-Wake Phase Disorder",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.04,
                "effect_description": "The PER3 VNTR 4-repeat allele (PER3-4) is significantly enriched in patients with delayed sleep-wake phase disorder (DSWPD): 75% of DSWPD patients were homozygous 4/4. The shorter repeat attenuates PER3 protein abundance, weakening the homeostatic sleep pressure signal and shifting the sleep-wake cycle toward eveningness. PER3-4 carriers show reduced slow-wave activity rebound after sleep deprivation and perform worse on sustained attention tasks under sleep loss.",
                "effect_summary": "Evening chronotype tendency",
                "evidence_level": "medium",
                "source_pmid": "12841365",
                "source_title": "A length polymorphism in the circadian clock gene Per3 is linked to delayed sleep phase syndrome and extreme diurnal preference",
            },
            {
                "trait": "Sleep Deprivation Vulnerability",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.001,
                "effect_description": "PER3 4/4 individuals show substantially greater cognitive performance deterioration during sustained wakefulness compared with PER3 5/5 individuals. Under 40-hour sleep deprivation, 4/4 carriers exhibit greater deficits in psychomotor vigilance and working memory, particularly during the circadian trough (02:00-08:00 h), reflecting impaired homeostatic sleep drive.",
                "effect_summary": "Greater sleep deprivation impact",
                "evidence_level": "medium",
                "source_pmid": "12841365",
                "source_title": "A length polymorphism in the circadian clock gene Per3 is linked to delayed sleep phase syndrome and extreme diurnal preference",
            },
        ],
    },
    {
        "rsid": "rs73598374",
        "fallback": {"chrom": "20", "position": 43280227, "ref_allele": "G", "alt_allele": "A",
                      "gene": "ADA", "functional_class": "missense_variant", "maf_global": 0.06},
        "traits": [
            {
                "trait": "Slow-Wave Sleep Depth",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.04,
                "effect_description": "Carriers of the ADA A allele (Asp8Asn, ~20-30% reduced enzyme activity) accumulate higher extracellular adenosine compared to G/G homozygotes. Because adenosine is the primary endogenous sleep-promoting molecule, elevated adenosine drives greater slow-wave activity (delta 0.75-1.5 Hz) in NREM stage 3/4 sleep. In controlled polysomnography studies (n=14 matched pairs), G/A individuals showed enhanced delta oscillation amplitude, fewer nocturnal awakenings, and more consolidated deep sleep than G/G controls. A large epidemiological replication in 800 subjects confirmed higher delta and theta spectral power across multiple sleep stages in A-allele carriers.",
                "effect_summary": "Deeper slow-wave sleep",
                "evidence_level": "high",
                "source_pmid": "16221767",
                "source_title": "A functional genetic variation of adenosine deaminase affects the duration and intensity of deep sleep in humans",
            },
            {
                "trait": "Sleep EEG Spectral Power",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.05,
                "effect_description": "In the EPISONO epidemiological cohort (800 participants, full-night PSG), ADA A-allele carriers showed significantly higher EEG spectral power in delta frequencies during NREM stages 1 and 3+4, and elevated theta power during stages 1, 2, and REM sleep. The findings establish ADA rs73598374 as an important source of inter-individual variation in sleep homeostasis, mediated by reduced adenosine catabolism and consequent enhancement of A1/A2A receptor-mediated sleep-promoting signaling.",
                "effect_summary": "Higher sleep EEG power",
                "evidence_level": "high",
                "source_pmid": "22952909",
                "source_title": "Adenosine deaminase polymorphism affects sleep EEG spectral power in a large epidemiological sample",
            },
        ],
    },
    {
        "rsid": "rs12649507",
        "fallback": {"chrom": "4", "position": 56380484, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CLOCK", "functional_class": "intron_variant", "maf_global": 0.30},
        "traits": [
            {
                "trait": "Sleep Duration",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.0087,
                "effect_description": "The CLOCK rs12649507 A allele is associated with shorter habitual sleep duration across two independent European populations (South Tyrol, n=283; Estonia, n=1,011). A allele carriers slept less than G/G homozygotes; the rs12649507/rs11932595 GGAA haplotype was associated with long sleep (>8.5 hours). The variant is located in intron 1 of CLOCK and likely affects transcriptional regulation of the master circadian pacemaker gene, shifting the endogenous period or amplitude of the CLOCK/BMAL1 transcription-translation feedback loop.",
                "effect_summary": "Shorter sleep duration",
                "evidence_level": "medium",
                "source_pmid": "20149345",
                "source_title": "CLOCK gene variants associate with sleep duration in two independent populations",
            },
        ],
    },
    {
        "rsid": "rs1801260",
        "fallback": {"chrom": "4", "position": 56301369, "ref_allele": "T", "alt_allele": "C",
                      "gene": "CLOCK", "functional_class": "3_prime_UTR_variant", "maf_global": 0.27},
        "traits": [
            {
                "trait": "Evening Chronotype",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.02,
                "effect_description": "The CLOCK 3111C allele (rs1801260) was the first common variant linked to human circadian preference. C allele carriers showed significantly greater eveningness on the Horne-Ostberg questionnaire compared to T/T homozygotes. In Japanese populations, C carriers had delayed sleep timing averaging ~79 minutes later and slept ~75 minutes less per night. Mechanistically, the C allele in the 3'-UTR increases CLOCK and PER2 mRNA levels in cellular models, potentially lengthening the circadian period.",
                "effect_summary": "Evening chronotype",
                "evidence_level": "medium",
                "source_pmid": "9700173",
                "source_title": "A CLOCK polymorphism associated with human diurnal preference",
            },
            {
                "trait": "Obesity and Metabolic Syndrome",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.01,
                "effect_description": "CLOCK 3111C/C homozygotes are more likely to be obese and lose less weight in dietary interventions compared to T allele carriers, an effect modulated by physical activity and sex. The circadian misalignment resulting from the C allele disrupts appetite-regulating hormone rhythms (elevated nocturnal ghrelin, blunted leptin amplitude), promoting caloric overconsumption. Interaction analysis shows physical activity attenuates the obesity risk in C-allele carriers.",
                "effect_summary": "Higher obesity risk",
                "evidence_level": "medium",
                "source_pmid": "23131019",
                "source_title": "Physical activity and sex modulate obesity risk linked to 3111T/C gene variant of the CLOCK gene in an elderly population: the SUN Project",
            },
        ],
    },
    {
        "rsid": "rs4753426",
        "fallback": {"chrom": "11", "position": 92701596, "ref_allele": "T", "alt_allele": "C",
                      "gene": "MTNR1B", "functional_class": "upstream_gene_variant", "maf_global": 0.49},
        "traits": [
            {
                "trait": "Morning Chronotype",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.05,
                "effect_description": "The MTNR1B -1193C allele (rs4753426) in the promoter region is associated with extreme morningness in a codominant model (n=814). C/C homozygotes show the earliest sleep-onset and wake times. The C allele is hypothesized to alter MTNR1B promoter activity, modifying MT2 receptor expression levels and thereby shifting the phase-advancing response to evening melatonin. Population-level analysis shows C-allele frequency is inversely correlated with annual sunshine duration worldwide, suggesting latitude-driven natural selection on circadian entrainment.",
                "effect_summary": "Morning chronotype",
                "evidence_level": "medium",
                "source_pmid": "30508778",
                "source_title": "Melatonin receptor 1B -1193T>C polymorphism is associated with diurnal preference and sleep habits",
            },
            {
                "trait": "Type 2 Diabetes Risk",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.004,
                "effect_description": "The MTNR1B rs4753426 C allele has been associated with altered oral glucose tolerance test-derived indices of beta-cell function and higher fasting insulin levels. MTNR1B is expressed in pancreatic beta-cells; melatonin signaling through MT2 receptors inhibits insulin secretion via Gi-coupled cAMP reduction. Promoter variants that alter MTNR1B expression levels consequently dysregulate the circadian gating of insulin release.",
                "effect_summary": "Altered insulin secretion timing",
                "evidence_level": "medium",
                "source_pmid": "30508778",
                "source_title": "Melatonin receptor 1B -1193T>C polymorphism is associated with diurnal preference and sleep habits",
            },
        ],
    },

    # ── Fertility / Reproductive ──────────────────────────────────────
    {
        "rsid": "rs10835638",
        "fallback": {"chrom": "11", "position": 30252352, "ref_allele": "G", "alt_allele": "T",
                      "gene": "FSHB", "functional_class": "upstream_gene_variant", "maf_global": 0.11},
        "traits": [
            {
                "trait": "Serum FSH Levels",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": -0.41,
                "p_value": 1.11e-6,
                "effect_description": "The T allele at the FSHB promoter position -211 reduces binding of the LHX3 homeodomain transcription factor, lowering FSHB gene transcription and circulating FSH levels. In a study of 1,054 Baltic men, each T allele reduced serum FSH by ~0.41 IU/L and was associated with reduced testicular volume, lower total testosterone, and lower inhibin-B. TT homozygous men may represent a pharmacogenetically distinct subgroup benefiting from FSH supplementation.",
                "effect_summary": "Lower FSH levels",
                "evidence_level": "high",
                "source_pmid": "21733993",
                "source_title": "Genetically determined dosage of follicle-stimulating hormone (FSH) affects male reproductive parameters",
            },
            {
                "trait": "Menstrual Cycle Length",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": 0.16,
                "p_value": 6e-16,
                "effect_description": "The FSH-lowering T allele of rs10835638 is associated with longer menstrual cycles in women. A Mendelian randomisation study in up to 63,350 UK Biobank women found each T allele lengthened cycle by ~0.16 SD (approximately 1 day). This is consistent with lower FSH slowing follicular maturation and extending the follicular phase.",
                "effect_summary": "Longer menstrual cycles",
                "evidence_level": "high",
                "source_pmid": "26732621",
                "source_title": "Genetic evidence that lower circulating FSH levels lengthen menstrual cycle, increase age at menopause and impact female reproductive health",
            },
        ],
    },
    {
        "rsid": "rs2234693",
        "fallback": {"chrom": "6", "position": 152163335, "ref_allele": "T", "alt_allele": "C",
                      "gene": "ESR1", "functional_class": "intron_variant", "maf_global": 0.46},
        "traits": [
            {
                "trait": "Premature Ovarian Failure",
                "risk_allele": "C",
                "odds_ratio": 0.5,
                "beta": None,
                "p_value": 0.001,
                "effect_description": "The PvuII polymorphism (rs2234693 T>C) in intron 1 of ESR1 modulates estrogen receptor alpha expression. The C allele was associated with a halved risk of idiopathic premature ovarian failure (POF) in a Chinese Han cohort. The variant likely influences the rate of follicular depletion through altered ERalpha-mediated oestrogen signalling in the hypothalamic-pituitary-ovarian axis.",
                "effect_summary": "Lower premature ovarian failure risk",
                "evidence_level": "medium",
                "source_pmid": "22248077",
                "source_title": "ESR1, HK3 and BRSK1 gene variants are associated with both age at natural menopause and premature ovarian failure",
            },
            {
                "trait": "Polycystic Ovary Syndrome (PCOS)",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 4.81e-6,
                "effect_description": "The rs2234693 T allele showed the strongest association with PCOS susceptibility in a Tunisian population (p=4.81e-6, OR=0.31 for the C allele as protective). In additional work in Brazilian and Spanish women, the PvuII polymorphism influenced metabolic features of PCOS including C-reactive protein, testosterone, and waist circumference. These findings suggest the variant modulates oestrogen receptor signalling in ways that affect androgen levels and insulin sensitivity.",
                "effect_summary": "Higher PCOS risk",
                "evidence_level": "medium",
                "source_pmid": "25617525",
                "source_title": "Estrogen receptor alpha gene (ESR1) PvuII and XbaI polymorphisms are associated to metabolic and proinflammatory factors in polycystic ovary syndrome",
            },
        ],
    },
    {
        "rsid": "rs1800440",
        "fallback": {"chrom": "2", "position": 38298139, "ref_allele": "T", "alt_allele": "C",
                      "gene": "CYP1B1", "functional_class": "missense_variant", "maf_global": 0.17},
        "traits": [
            {
                "trait": "Endometrial Cancer Risk",
                "risk_allele": "T",
                "odds_ratio": 0.82,
                "beta": None,
                "p_value": 5e-3,
                "effect_description": "CYP1B1 is the primary extrahepatic enzyme catalysing 4-hydroxylation of 17beta-oestradiol, generating the genotoxic catechol oestrogen 4-OHE2 which can form depurinating DNA adducts. The rs1800440 C allele (p.Asn453Ser, CYP1B1*4) encodes a protein with a half-life of only 1.6 h versus 4.8 h for the Asn453 wild-type, resulting in ~2-fold lower cellular CYP1B1 protein levels. A meta-analysis found the Ser453 (C) allele significantly reduced endometrial cancer risk (pooled OR=0.82). Women homozygous for the common T allele (Asn453) have higher CYP1B1 activity and consequently greater endometrial cancer susceptibility.",
                "effect_summary": "Higher endometrial cancer risk",
                "evidence_level": "high",
                "source_pmid": "23370603",
                "source_title": "Catechol-O-methyltransferase and cytochrome P-450 1B1 polymorphisms and endometrial cancer risk: a meta-analysis",
            },
            {
                "trait": "Oestrogen Metabolism / CYP1B1 Enzyme Activity",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "The rs1800440 missense variant (p.Asn453Ser) in exon 3 of CYP1B1 directly affects post-translational stability of the enzyme via the ubiquitin-proteasome pathway. The Ser453 variant (C allele, CYP1B1*4) is degraded approximately 3 times faster than the Asn453 wild-type, leading to ~2-fold lower intracellular CYP1B1 protein and proportionally reduced 4-hydroxylation of oestradiol. Individuals homozygous for the T allele (Asn453) generate more genotoxic oestrogen metabolites in hormonally active tissues.",
                "effect_summary": "Higher oestrogen metabolite production",
                "evidence_level": "high",
                "source_pmid": "15486049",
                "source_title": "Proteasomal degradation of human CYP1B1: effect of the Asn453Ser polymorphism on the post-translational regulation of CYP1B1 expression",
            },
        ],
    },
    {
        "rsid": "rs4986938",
        "fallback": {"chrom": "14", "position": 64699816, "ref_allele": "C", "alt_allele": "T",
                      "gene": "ESR2", "functional_class": "3_prime_UTR_variant", "maf_global": 0.35},
        "traits": [
            {
                "trait": "Bone Mineral Density (Postmenopausal)",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.044,
                "effect_description": "The ESR2 AluI 1730G>A polymorphism (rs4986938; T allele on + strand) in the 3' UTR of oestrogen receptor beta affects mRNA stability and/or microRNA-binding efficiency, potentially altering ERbeta protein levels in bone. Regression analysis showed that the AA1730 homozygous genotype was the strongest genetic predictor of lumbar spine BMD, with 85% of AA1730 carriers having the lowest BMD values. ERbeta has anti-proliferative roles in osteoclast activity; reduced ERbeta expression from the A allele may accelerate bone resorption.",
                "effect_summary": "Lower postmenopausal bone density",
                "evidence_level": "medium",
                "source_pmid": "21689747",
                "source_title": "The ESR2 AluI gene polymorphism is associated with bone mineral density in postmenopausal women",
            },
            {
                "trait": "Graves' Disease",
                "risk_allele": "T",
                "odds_ratio": 1.26,
                "beta": None,
                "p_value": 9e-3,
                "effect_description": "The ESR2 A1730 allele (rs4986938 T on + strand) is associated with susceptibility to Graves' disease, a sex-biased autoimmune condition. In a Polish cohort of 375 Graves' disease patients and 1,001 controls, the A allele frequency was 38.0% in cases vs. 32.7% in controls (OR=1.26). Under a recessive model, AA1730 homozygotes had OR=1.67. The 3'UTR location suggests the variant may alter ERbeta-mediated regulation of immune tolerance.",
                "effect_summary": "Higher Graves' disease risk",
                "evidence_level": "medium",
                "source_pmid": "17941906",
                "source_title": "Polymorphism of the oestrogen receptor beta gene (ESR2) is associated with susceptibility to Graves' disease",
            },
        ],
    },

    # ── Caffeine / Substances ─────────────────────────────────────────
    {
        "rsid": "rs4410790",
        "fallback": {"chrom": "7", "position": 17284577, "ref_allele": "T", "alt_allele": "C",
                      "gene": "AHR", "functional_class": "intron_variant", "maf_global": 0.47},
        "traits": [
            {
                "trait": "Caffeine Consumption",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": 0.15,
                "p_value": 2.4e-19,
                "effect_description": "The C allele at rs4410790, located within an intron of the aryl hydrocarbon receptor gene (AHR), is robustly associated with higher habitual caffeine intake. AHR is a ligand-activated transcription factor that senses xenobiotics in roasted coffee and induces transcription of CYP1A1 and CYP1A2. Carriers of the C allele have enhanced AHR-driven CYP1A2 induction, accelerating caffeine clearance and reducing plasma caffeine levels, which in turn drives higher consumption to maintain preferred stimulant effects. The association was genome-wide significant (p=2.4e-19) in a meta-analysis of 47,341 individuals.",
                "effect_summary": "Higher caffeine consumption",
                "evidence_level": "high",
                "source_pmid": "21490707",
                "source_title": "Genome-wide meta-analysis identifies regions on 7p21 (AHR) and 15q24 (CYP1A2) as determinants of habitual caffeine consumption",
            },
            {
                "trait": "Coffee Consumption",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": 0.11,
                "p_value": 6e-70,
                "effect_description": "rs4410790-C is one of the strongest common genetic determinants of daily coffee intake. A large-scale GWAS of coffee consumption (cups per day) in UK Biobank and other cohorts identified this variant at genome-wide significance (p=6e-70, beta~0.11 cups/day per C allele). The effect is driven by the AHR-CYP1A2 regulatory axis: higher CYP1A2 inducibility in C-allele carriers leads to faster caffeine metabolism and a compensatory increase in coffee consumption.",
                "effect_summary": "Higher coffee consumption",
                "evidence_level": "high",
                "source_pmid": "31046077",
                "source_title": "Genome-wide association study of dietary habits in UK Biobank",
            },
        ],
    },
    {
        "rsid": "rs2472297",
        "fallback": {"chrom": "15", "position": 75027880, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CYP1A1", "functional_class": "intergenic_variant", "maf_global": 0.07},
        "traits": [
            {
                "trait": "Coffee Consumption",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": 0.20,
                "p_value": 5.4e-14,
                "effect_description": "rs2472297 lies in the 23-kb intergenic region shared between the 5' ends of CYP1A1 and CYP1A2 on chromosome 15q24. The T allele is associated with increased coffee consumption (~0.2 cups/day per allele) in a meta-analysis of 10,661 coffee drinkers. This intergenic region contains regulatory elements for both CYP1A1 and CYP1A2; the T allele enhances CYP1A2 transcriptional inducibility, accelerating caffeine metabolism and driving higher consumption. The T allele shows striking population stratification: ~21% in Europeans but essentially absent in East Asians.",
                "effect_summary": "Higher coffee consumption",
                "evidence_level": "high",
                "source_pmid": "21357676",
                "source_title": "Sequence variants at CYP1A1-CYP1A2 and AHR associate with coffee consumption",
            },
            {
                "trait": "Caffeine Metabolism (Plasma Caffeine Level)",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 5.2e-14,
                "effect_description": "The 15q24 locus containing rs2472297 was one of two genome-wide significant loci identified for plasma caffeine levels and caffeine metabolite ratios. The T allele is associated with lower plasma caffeine and a higher paraxanthine-to-caffeine ratio, indicating faster CYP1A2-mediated 3-demethylation of caffeine to paraxanthine. Together with the AHR locus, these two loci explain ~1% of variance in coffee intake.",
                "effect_summary": "Faster caffeine metabolism",
                "evidence_level": "high",
                "source_pmid": "27702941",
                "source_title": "Genome-wide association study of caffeine metabolites provides new insights to caffeine metabolism and dietary caffeine-consumption behavior",
            },
        ],
    },
    {
        "rsid": "rs1229984",
        "fallback": {"chrom": "4", "position": 100239319, "ref_allele": "T", "alt_allele": "A",
                      "gene": "ADH1B", "functional_class": "missense_variant", "maf_global": 0.16},
        "traits": [
            {
                "trait": "Alcohol Dependence",
                "risk_allele": "T",
                "odds_ratio": 2.94,
                "beta": None,
                "p_value": 6.6e-10,
                "effect_description": "rs1229984 is a missense variant in ADH1B (alcohol dehydrogenase 1B) encoding the Arg48His substitution. The A allele (His48) produces an ADH1B isoform that oxidizes ethanol to acetaldehyde approximately 70-80 times faster than the wild-type Arg48 form. The rapid acetaldehyde accumulation causes flushing, nausea, and tachycardia, strongly discouraging alcohol consumption. The A (His48) allele is powerfully protective against alcohol dependence (OR 0.34), while carriers of the T (Arg48) reference allele face higher risk. The A allele is common in East Asian populations (~75%) but rare in Europeans (~3%).",
                "effect_summary": "Higher alcohol dependence risk",
                "evidence_level": "high",
                "source_pmid": "21968928",
                "source_title": "ADH1B is associated with alcohol dependence and alcohol consumption in populations of European and African ancestry",
            },
            {
                "trait": "Esophageal Cancer",
                "risk_allele": "A",
                "odds_ratio": 2.07,
                "beta": None,
                "p_value": 3e-44,
                "effect_description": "Paradoxically, the His48 (A) allele that protects against alcohol dependence increases esophageal cancer risk in individuals who do drink alcohol. Fast ADH1B activity generates elevated acetaldehyde, a Group 1 IARC carcinogen, in the upper aerodigestive tract mucosa. The association is strongest when combined with ALDH2 rs671 heterozygosity: carriers of both fast-ADH1B and inactive-ALDH2 alleles who drink regularly have esophageal cancer risk approximately 4.8-fold higher than reference genotype drinkers.",
                "effect_summary": "Higher esophageal cancer risk",
                "evidence_level": "high",
                "source_pmid": "32514122",
                "source_title": "Large-scale genome-wide association study in a Japanese population identifies novel susceptibility loci across different diseases",
            },
        ],
    },
    {
        "rsid": "rs671",
        "fallback": {"chrom": "12", "position": 112241766, "ref_allele": "G", "alt_allele": "A",
                      "gene": "ALDH2", "functional_class": "missense_variant", "maf_global": 0.008},
        "traits": [
            {
                "trait": "Alcohol Flush Reaction",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 5e-26,
                "effect_description": "rs671 is the canonical 'Asian flush' variant: a missense change in ALDH2 encoding the Glu504Lys substitution. The Lys504 (A allele) protein is catalytically nearly inactive: heterozygotes retain only ~6% of wild-type ALDH2 activity and homozygotes have <1%. After drinking, acetaldehyde accumulates producing the characteristic alcohol flush syndrome: facial flushing, tachycardia, nausea, and headache. The A allele explains 29.2% of variance in flushing response, making it one of the largest effect-size pharmacogenomic variants in the human genome. The A allele reaches ~22% frequency in East Asians but is extremely rare (<1%) in all other ancestral groups.",
                "effect_summary": "Alcohol flush reaction",
                "evidence_level": "high",
                "source_pmid": "24277619",
                "source_title": "ALDH2 is associated to alcohol dependence and is the major genetic determinant of 'daily maximum drinks' in a GWAS study of an isolated rural Chinese sample",
            },
            {
                "trait": "Alcohol Consumption (Drinking Behavior)",
                "risk_allele": "G",
                "odds_ratio": 6.25,
                "beta": None,
                "p_value": 4e-211,
                "effect_description": "rs671-G (wild-type, functional ALDH2) is strongly associated with regular alcohol drinking compared to the A (Lys504) allele. In a large Japanese population GWAS (n>50,000), the G allele showed an OR of 6.25 for drinking behavior, the most significant variant association in the study. This quantifies the enormous behavioral deterrent effect of the Lys504 variant: A-allele carriers are approximately 6-fold less likely to become regular drinkers than GG homozygotes.",
                "effect_summary": "Higher alcohol consumption",
                "evidence_level": "high",
                "source_pmid": "21372407",
                "source_title": "Confirmation of ALDH2 as a major locus of drinking behavior and of its variants regulating multiple metabolic phenotypes in a Japanese population",
            },
            {
                "trait": "Esophageal Cancer (Alcohol-Related)",
                "risk_allele": "A",
                "odds_ratio": 1.39,
                "beta": None,
                "p_value": 1e-8,
                "effect_description": "The ALDH2 rs671 A (Lys504) allele substantially increases esophageal cancer risk among individuals who regularly consume alcohol. Impaired ALDH2 activity means acetaldehyde cannot be efficiently cleared, resulting in prolonged exposure of the esophageal epithelium to a known Group 1 carcinogen. A meta-analysis of 31 studies found AG heterozygotes have OR 1.39 for esophageal squamous cell carcinoma; among alcohol-drinking males the OR rises to 4.39. Paradoxically, AA homozygotes have reduced cancer risk because the severe flush reaction almost completely prevents alcohol consumption.",
                "effect_summary": "Higher esophageal cancer risk",
                "evidence_level": "high",
                "source_pmid": "25848305",
                "source_title": "Clinical significance of ALDH2 rs671 polymorphism in esophageal cancer: evidence from 31 case-control studies",
            },
        ],
    },
    # ── Hereditary Cancer ─────────────────────────────────────────────
    {
        "rsid": "rs11571833",
        "fallback": {"chrom": "13", "position": 32972626, "ref_allele": "A", "alt_allele": "T",
                      "gene": "BRCA2", "functional_class": "stop_gained", "maf_global": 0.0071},
        "traits": [
            {
                "trait": "Breast Cancer Risk (Moderate Penetrance)",
                "risk_allele": "T",
                "odds_ratio": 1.28,
                "beta": None,
                "p_value": 1e-8,
                "effect_description": "The BRCA2 K3326X variant (c.9976A>T, p.Lys3326Ter) creates a premature stop codon that truncates the final 93 amino acids of the BRCA2 protein. Unlike classic pathogenic BRCA2 mutations, this is a low-to-moderate risk allele: carrying one copy is associated with approximately 28% increased risk of breast cancer and 26% increased ovarian cancer risk. The truncated protein retains enough function to be compatible with health in most carriers. Present in ~0.7% of Europeans, clinical management recommendations differ from classic BRCA2 pathogenic variants.",
                "effect_summary": "Modestly higher breast cancer risk",
                "evidence_level": "high",
                "source_pmid": "26586665",
                "source_title": "BRCA2 Polymorphic Stop Codon K3326X and the Risk of Breast, Prostate, and Ovarian Cancers",
            },
        ],
    },
    {
        "rsid": "rs1801155",
        "fallback": {"chrom": "5", "position": 112175211, "ref_allele": "T", "alt_allele": "A",
                      "gene": "APC", "functional_class": "missense", "maf_global": 0.003},
        "traits": [
            {
                "trait": "Colorectal Cancer Risk",
                "risk_allele": "A",
                "odds_ratio": 1.75,
                "beta": None,
                "p_value": 1e-6,
                "effect_description": "The APC I1307K variant (c.3920T>A, p.Ile1307Lys) creates a hypermutable poly-A repeat (A8 instead of A3TA4) prone to somatic frameshift during DNA replication, meaning it does not directly inactivate APC but renders the gene susceptible to subsequent somatic mutations. Carriers have approximately 1.5–2× the average risk of colorectal cancer. The variant is present in roughly 6–10% of Ashkenazi Jewish individuals and is considerably rarer in other populations. Carriers should discuss colonoscopy surveillance with their physician.",
                "effect_summary": "Higher colorectal cancer risk",
                "evidence_level": "high",
                "source_pmid": "23896379",
                "source_title": "The APC p.I1307K polymorphism is a significant risk factor for CRC in average risk Ashkenazi Jews",
            },
        ],
    },
    {
        "rsid": "rs34612342",
        "fallback": {"chrom": "1", "position": 45798475, "ref_allele": "T", "alt_allele": "C",
                      "gene": "MUTYH", "functional_class": "missense", "maf_global": 0.0018},
        "traits": [
            {
                "trait": "MUTYH-Associated Polyposis and Colorectal Cancer",
                "risk_allele": "C",
                "odds_ratio": 1.34,
                "beta": None,
                "p_value": 5e-3,
                "effect_description": "The MUTYH Y179C variant (c.536A>G, p.Tyr179Cys) is one of the two most common pathogenic MUTYH variants in Northern Europeans. MUTYH is a base excision repair enzyme that corrects oxidative DNA damage. Homozygous carriers or compound heterozygotes (one Y179C plus one G396D) have up to 28-fold elevated colorectal cancer risk. Monoallelic carriers have a modest ~34% increase that remains controversial. All biallelic carriers should receive intensive surveillance starting at age 18–20.",
                "effect_summary": "Higher colorectal cancer risk",
                "evidence_level": "high",
                "source_pmid": "21248752",
                "source_title": "A large-scale meta-analysis to refine colorectal cancer risk estimates associated with MUTYH variants",
            },
        ],
    },
    {
        "rsid": "rs36053993",
        "fallback": {"chrom": "1", "position": 45797228, "ref_allele": "C", "alt_allele": "T",
                      "gene": "MUTYH", "functional_class": "missense", "maf_global": 0.0046},
        "traits": [
            {
                "trait": "MUTYH-Associated Polyposis and Colorectal Cancer",
                "risk_allele": "T",
                "odds_ratio": 1.35,
                "beta": None,
                "p_value": 5e-3,
                "effect_description": "The MUTYH G396D variant (c.1187G>A, p.Gly396Asp) is the second most common MUTYH pathogenic variant in Northern Europeans. Like Y179C, it disrupts base excision repair. Compound heterozygous individuals carrying one G396D and one Y179C have a greater than 20-fold elevated colorectal cancer risk. Monoallelic carriers have a modest and contested increased risk. Biallelic carriers require intensive colonoscopy surveillance beginning in late teens.",
                "effect_summary": "Higher colorectal cancer risk",
                "evidence_level": "high",
                "source_pmid": "21248752",
                "source_title": "A large-scale meta-analysis to refine colorectal cancer risk estimates associated with MUTYH variants",
            },
        ],
    },
    # ── Longevity & Aging (expanding existing category) ───────────────
    {
        "rsid": "rs13217795",
        "fallback": {"chrom": "6", "position": 108974098, "ref_allele": "C", "alt_allele": "T",
                      "gene": "FOXO3", "functional_class": "intron_variant", "maf_global": 0.45},
        "traits": [
            {
                "trait": "Longevity / Healthy Aging",
                "risk_allele": "C",
                "odds_ratio": 1.23,
                "beta": None,
                "p_value": 0.001,
                "effect_description": "The rs13217795 variant in FOXO3 is an intronic variant in the longevity-associated FOXO3 locus. In a meta-analysis of over 10,000 individuals, the C allele was associated with 23% increased odds of exceptional longevity. FOXO3 encodes a transcription factor regulating stress resistance, autophagy, and DNA repair. rs13217795 maps near an alternative FOXO3 promoter and may modulate isoform expression levels. The association is particularly robust in centenarian versus younger control studies.",
                "effect_summary": "Enhanced longevity",
                "evidence_level": "medium",
                "source_pmid": "24589462",
                "source_title": "Association between FOXO3A gene polymorphisms and human longevity: a meta-analysis",
            },
        ],
    },
    {
        "rsid": "rs2736100",
        "fallback": {"chrom": "5", "position": 1286516, "ref_allele": "C", "alt_allele": "A",
                      "gene": "TERT", "functional_class": "intron_variant", "maf_global": 0.49},
        "traits": [
            {
                "trait": "Lung Cancer Risk (Adenocarcinoma)",
                "risk_allele": "C",
                "odds_ratio": 1.20,
                "beta": None,
                "p_value": 1e-5,
                "effect_description": "The rs2736100 variant in intron 2 of TERT (telomerase reverse transcriptase) on chromosome 5p15.33 is a confirmed risk factor for lung adenocarcinoma. A meta-analysis of 56,223 cases and 86,680 controls found the C allele increases risk with a per-allele OR of 1.20. The C allele upregulates TERT expression, maintaining telomere length but also promoting cancer cell immortalization. This variant also shows associations with thyroid cancer, bladder cancer, and glioma.",
                "effect_summary": "Higher lung cancer risk",
                "evidence_level": "high",
                "source_pmid": "24590268",
                "source_title": "Increased lung cancer risk associated with the TERT rs2736100 polymorphism: an updated meta-analysis",
            },
            {
                "trait": "Telomere Length",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": 67.0,
                "p_value": 1e-30,
                "effect_description": "The C allele of rs2736100 in TERT is associated with longer telomere length in blood cells, adding approximately 67 base pairs per copy. Paradoxically, the same C allele that increases telomere length also increases lung cancer risk, likely because enhanced telomere maintenance promotes both cellular longevity and cancer cell immortalization. This variant illustrates the complex role of telomere biology in aging and cancer.",
                "effect_summary": "Longer telomeres",
                "evidence_level": "high",
                "source_pmid": "23555636",
                "source_title": "Longer telomere length in peripheral white blood cells is associated with risk of lung cancer and the rs2736100 polymorphism",
            },
        ],
    },
    {
        "rsid": "rs7726159",
        "fallback": {"chrom": "5", "position": 1282319, "ref_allele": "C", "alt_allele": "A",
                      "gene": "TERT", "functional_class": "intron_variant", "maf_global": 0.29},
        "traits": [
            {
                "trait": "Cancer Risk / Telomere Length",
                "risk_allele": "A",
                "odds_ratio": 1.05,
                "beta": None,
                "p_value": 5e-3,
                "effect_description": "In a study of 95,568 Danish individuals (10,895 cancer cases), the telomere-lengthening A allele of rs7726159 was associated with a modest 5% increased overall cancer risk (OR 1.05, 95% CI 1.02–1.09). Risk was strongest for melanoma (OR 1.19) and lung cancer (OR 1.14). The TERT-CLPTM1L region on 5p15.33 is one of the most important genomic regions for cancer susceptibility via telomere length regulation.",
                "effect_summary": "Slightly higher cancer risk",
                "evidence_level": "medium",
                "source_pmid": "27498151",
                "source_title": "Long telomeres and cancer risk among 95,568 individuals from the general population",
            },
        ],
    },
    {
        "rsid": "rs1800775",
        "fallback": {"chrom": "16", "position": 56995236, "ref_allele": "C", "alt_allele": "A",
                      "gene": "CETP", "functional_class": "upstream_gene_variant", "maf_global": 0.50},
        "traits": [
            {
                "trait": "HDL Cholesterol Levels",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": 2.5,
                "p_value": 1e-40,
                "effect_description": "The rs1800775 variant is a promoter-region SNP in CETP (cholesteryl ester transfer protein) approximately 629 bp upstream of the transcription start site. The A allele reduces CETP expression, leading to higher HDL ('good') cholesterol levels. Higher HDL driven by reduced CETP activity was associated with exceptional longevity in centenarian studies, particularly among Ashkenazi Jewish centenarians. However, Mendelian randomization studies show the cardiovascular disease benefit is more modest than HDL levels alone would suggest.",
                "effect_summary": "Higher HDL cholesterol",
                "evidence_level": "high",
                "source_pmid": "19698715",
                "source_title": "Polymorphism in the CETP Gene Region, HDL Cholesterol, and Risk of Future Myocardial Infarction",
            },
        ],
    },
    {
        "rsid": "rs9536314",
        "fallback": {"chrom": "13", "position": 33628138, "ref_allele": "T", "alt_allele": "G",
                      "gene": "KL", "functional_class": "missense", "maf_global": 0.15},
        "traits": [
            {
                "trait": "Longevity and Cognitive Function",
                "risk_allele": "G",
                "odds_ratio": 1.2,
                "beta": None,
                "p_value": 0.01,
                "effect_description": "The rs9536314 variant in the KL (Klotho) gene defines the KL-VS haplotype (F352V). Heterozygosity for the KL-VS haplotype, found in ~20–25% of the general population, is associated with higher circulating klotho protein levels, improved cognitive performance, greater cortical brain volume, and potentially longer lifespan. Klotho is an anti-aging protein modulating insulin signaling and FGF pathways. Importantly, benefits appear specific to heterozygous carriers — homozygous carriers do not show the same advantages.",
                "effect_summary": "Better cognitive function",
                "evidence_level": "medium",
                "source_pmid": "25815349",
                "source_title": "Variation in longevity gene KLOTHO is associated with greater cortical volumes",
            },
        ],
    },
    {
        "rsid": "rs3758391",
        "fallback": {"chrom": "10", "position": 69643342, "ref_allele": "T", "alt_allele": "C",
                      "gene": "SIRT1", "functional_class": "upstream_gene_variant", "maf_global": 0.38},
        "traits": [
            {
                "trait": "Longevity / Cognitive Aging",
                "risk_allele": "C",
                "odds_ratio": 1.45,
                "beta": None,
                "p_value": 0.026,
                "effect_description": "The rs3758391 variant lies ~2 kb upstream of SIRT1, encoding sirtuin-1 — a NAD+-dependent deacetylase central to stress responses, DNA repair, and caloric restriction pathways. SIRT1 extends lifespan in model organisms. In a study of 482 Han Chinese (246 aging, 236 younger controls), the C allele was more common in aging subjects (OR 1.45, p=0.026). However, a larger 2016 Chinese study (616 long-lived, 846 controls) found no significant association, and results remain inconsistent across populations.",
                "effect_summary": "Potential longevity benefit",
                "evidence_level": "low",
                "source_pmid": "20633545",
                "source_title": "SIRT1 variants are associated with aging in a healthy Han Chinese population",
            },
        ],
    },
    {
        "rsid": "rs2075650",
        "fallback": {"chrom": "19", "position": 45395619, "ref_allele": "A", "alt_allele": "G",
                      "gene": "TOMM40", "functional_class": "intron_variant", "maf_global": 0.13},
        "traits": [
            {
                "trait": "Alzheimer's Disease Risk",
                "risk_allele": "G",
                "odds_ratio": 2.87,
                "beta": None,
                "p_value": 1e-6,
                "effect_description": "The rs2075650 variant in TOMM40 (translocase of the outer mitochondrial membrane 40) is located in the APOE-TOMM40-APOC1 gene cluster and is in strong linkage disequilibrium with the APOE \u03b54 allele (rs429358). A meta-analysis of 8 studies (4,290 AD cases, 5,556 controls) found the G allele significantly associated with Alzheimer's disease in European and Korean populations. IMPORTANT: The large odds ratio primarily reflects LD with APOE \u03b54 rather than an independent TOMM40 effect. Conditional analyses adjusting for APOE suggest much of the signal is driven by rs429358. The independent TOMM40 contribution remains debated.",
                "effect_summary": "Higher Alzheimer's risk",
                "evidence_level": "medium",
                "source_pmid": "26572157",
                "source_title": "Meta-analysis of the rs2075650 polymorphism and risk of Alzheimer disease",
            },
        ],
    },
    # ── Autoimmune / HLA Expansion ────────────────────────────────────
    {
        "rsid": "rs7775228",
        "fallback": {"chrom": "6", "position": 32658079, "ref_allele": "T", "alt_allele": "C",
                      "gene": "HLA-DQB1", "functional_class": "intergenic_variant", "maf_global": 0.19},
        "traits": [
            {
                "trait": "Celiac Disease (HLA-DQ2.2 Haplotype Marker)",
                "risk_allele": "C",
                "odds_ratio": 1.67,
                "beta": None,
                "p_value": 0.05,
                "effect_description": "rs7775228 is a tag SNP for the HLA-DQ2.2 haplotype, one of the genetic variants in the HLA region associated with celiac disease risk. DQ2.2 alone is a much weaker celiac risk factor than DQ2.5 or DQ8, but risk increases when combined with DQ7 (creating a trans-DQ2.5-like molecule). About 3-5% of European-ancestry DQ2.2 carriers without DQ2.5 develop celiac disease. This SNP is best interpreted as part of a composite HLA-DQ haplotype panel rather than in isolation.",
                "effect_summary": "Modest celiac disease risk",
                "evidence_level": "medium",
                "source_pmid": "18509540",
                "source_title": "Effective Detection of Human Leukocyte Antigen Risk Alleles in Celiac Disease Using Tag Single Nucleotide Polymorphisms",
            },
        ],
    },
    {
        "rsid": "rs4349859",
        "fallback": {"chrom": "6", "position": 31365787, "ref_allele": "G", "alt_allele": "A",
                      "gene": "HLA-B", "functional_class": "intron_variant", "maf_global": 0.08},
        "traits": [
            {
                "trait": "Ankylosing Spondylitis",
                "risk_allele": "A",
                "odds_ratio": 48.9,
                "beta": None,
                "p_value": 1e-200,
                "effect_description": "rs4349859 is a tag SNP for HLA-B27, one of the strongest genetic risk factors known in all of human genetics. About 80-90% of people with ankylosing spondylitis (a chronic inflammatory arthritis of the spine) carry HLA-B27, versus ~8% of the general European population. However, only about 1-5% of HLA-B27-positive individuals develop the disease. Carrying the A allele indicates ~98% probability of carrying HLA-B27 in Europeans (98% sensitivity, 99% specificity). This tag SNP is less accurate in African or East Asian populations where different HLA-B27 subtypes predominate.",
                "effect_summary": "Higher ankylosing spondylitis risk",
                "evidence_level": "high",
                "source_pmid": "21743469",
                "source_title": "Interaction between ERAP1 and HLA-B27 in ankylosing spondylitis implicates peptide handling in the mechanism for HLA-B27 in disease susceptibility",
            },
        ],
    },
    {
        "rsid": "rs2066844",
        "fallback": {"chrom": "16", "position": 50745926, "ref_allele": "C", "alt_allele": "T",
                      "gene": "NOD2", "functional_class": "missense_variant", "maf_global": 0.026},
        "traits": [
            {
                "trait": "Crohn's Disease",
                "risk_allele": "T",
                "odds_ratio": 2.2,
                "beta": None,
                "p_value": None,
                "effect_description": "rs2066844 is a missense change in NOD2 (R702W: arginine to tryptophan at position 702). NOD2 is a key innate immune sensor that detects bacterial peptidoglycans in the gut. The R702W change impairs NOD2's ability to activate NF-\u03baB. One copy approximately doubles Crohn's disease risk; two NOD2 risk variants (homozygous or compound het with G908R or 3020insC) increase risk 15-40 fold. Found in ~3-4% of Europeans and extremely rare in East Asians.",
                "effect_summary": "Higher Crohn's disease risk",
                "evidence_level": "high",
                "source_pmid": "19713276",
                "source_title": "Genotyping for NOD2 genetic variants and Crohn disease: a metaanalysis",
            },
        ],
    },
    {
        "rsid": "rs2066845",
        "fallback": {"chrom": "16", "position": 50756540, "ref_allele": "G", "alt_allele": "C",
                      "gene": "NOD2", "functional_class": "missense_variant", "maf_global": 0.011},
        "traits": [
            {
                "trait": "Crohn's Disease",
                "risk_allele": "C",
                "odds_ratio": 2.6,
                "beta": None,
                "p_value": None,
                "effect_description": "rs2066845 causes a missense change in NOD2 (G908R: glycine to arginine at position 908), located in the leucine-rich repeat domain that senses bacterial peptidoglycans. Like R702W, G908R impairs NOD2's immune sensing function. One copy increases Crohn's risk approximately 2.6-fold. Combined with other NOD2 variants, risk rises 15-40 fold. Found in ~1% of Europeans, essentially absent in East Asians. Crohn's associated with NOD2 variants typically has ileal predominance and fibrostenotic phenotype.",
                "effect_summary": "Higher Crohn's disease risk",
                "evidence_level": "high",
                "source_pmid": "19713276",
                "source_title": "Genotyping for NOD2 genetic variants and Crohn disease: a metaanalysis",
            },
        ],
    },
    {
        "rsid": "rs2066847",
        "fallback": {"chrom": "16", "position": 50763781, "ref_allele": "C", "alt_allele": "CC",
                      "gene": "NOD2", "functional_class": "frameshift_variant", "maf_global": 0.02},
        "traits": [
            {
                "trait": "Crohn's Disease",
                "risk_allele": "CC",
                "odds_ratio": 3.8,
                "beta": None,
                "p_value": None,
                "effect_description": "rs2066847 is the NOD2 3020insC variant — a single cytosine insertion causing a frameshift and premature stop codon (p.Leu1007fs). The truncated NOD2 protein cannot activate NF-\u03baB, severely impairing gut innate immunity. Of the three major NOD2 Crohn's variants, this frameshift has the largest individual effect: one copy roughly quadruples risk, while homozygotes or compound heterozygotes face 17-40 fold elevation. Found in ~3-4% of Europeans. Note: this is an insertion/deletion, not a simple SNP — consumer arrays may not reliably genotype it.",
                "effect_summary": "Higher Crohn's disease risk",
                "evidence_level": "high",
                "source_pmid": "19713276",
                "source_title": "Genotyping for NOD2 genetic variants and Crohn disease: a metaanalysis",
            },
        ],
    },
    {
        "rsid": "rs11209026",
        "fallback": {"chrom": "1", "position": 67705958, "ref_allele": "G", "alt_allele": "A",
                      "gene": "IL23R", "functional_class": "missense_variant", "maf_global": 0.04},
        "traits": [
            {
                "trait": "Crohn's Disease (Protective)",
                "risk_allele": "A",
                "odds_ratio": 0.41,
                "beta": None,
                "p_value": 1e-50,
                "effect_description": "rs11209026 (R381Q) in IL23R is a PROTECTIVE variant — carriers have ~59% lower odds of developing Crohn's disease (OR \u2248 0.41). The R381Q change reduces IL-23 receptor signaling, dampening the IL-23/Th17 immune pathway that drives intestinal inflammation in IBD. This discovery was pivotal: the IL-23 pathway is now a major drug target, with biologics like ustekinumab and risankizumab effective for IBD treatment. The protective A allele is found in ~4% of Europeans.",
                "effect_summary": "Lower Crohn's disease risk",
                "evidence_level": "high",
                "source_pmid": "31728561",
                "source_title": "Genetic association between IL23R rs11209026 and rs10889677 polymorphisms and risk of Crohn's disease and ulcerative colitis",
            },
        ],
    },
    {
        "rsid": "rs10484554",
        "fallback": {"chrom": "6", "position": 31274555, "ref_allele": "C", "alt_allele": "T",
                      "gene": "HLA-C", "functional_class": "intergenic_variant", "maf_global": 0.17},
        "traits": [
            {
                "trait": "Psoriasis",
                "risk_allele": "T",
                "odds_ratio": 4.66,
                "beta": None,
                "p_value": 4e-214,
                "effect_description": "rs10484554 is the strongest single genetic risk factor for psoriasis, a highly accurate tag for HLA-C*06:02 (the classical psoriasis susceptibility allele). Carrying one copy increases psoriasis risk approximately 4.7-fold. HLA-C*06:02 alone accounts for as much genetic risk as all other known psoriasis loci combined. It is thought to alter how immune cells present skin proteins to T cells, triggering abnormal keratinocyte proliferation. About 32% of European psoriasis patients carry the T allele versus ~15% of controls. Environmental triggers like streptococcal infection and stress also play important roles.",
                "effect_summary": "Higher psoriasis risk",
                "evidence_level": "high",
                "source_pmid": "20953190",
                "source_title": "A genome-wide association study identifies new psoriasis susceptibility loci and an interaction between HLA-C and ERAP1",
            },
        ],
    },
    {
        "rsid": "rs6910071",
        "fallback": {"chrom": "6", "position": 32282854, "ref_allele": "A", "alt_allele": "G",
                      "gene": "HLA-DRB1", "functional_class": "intron_variant", "maf_global": 0.25},
        "traits": [
            {
                "trait": "Rheumatoid Arthritis",
                "risk_allele": "G",
                "odds_ratio": 2.88,
                "beta": None,
                "p_value": 1e-299,
                "effect_description": "rs6910071 tags the HLA-DRB1 'shared epitope' alleles (most closely HLA-DRB1*04:01) — a common amino-acid motif at positions 70-74 of HLA-DRB1 that is strongly associated with rheumatoid arthritis (RA). The shared epitope alleles are particularly associated with seropositive RA (anti-CCP antibody positive), more severe joint disease, and extra-articular manifestations. The HLA-DRB1 locus explains roughly one-third of the total genetic risk for RA. The actual risk comes from the HLA-DRB1 protein sequence this SNP tags, which alters presentation of citrullinated self-proteins.",
                "effect_summary": "Higher rheumatoid arthritis risk",
                "evidence_level": "high",
                "source_pmid": "20453842",
                "source_title": "Genome-wide association study meta-analysis identifies seven new rheumatoid arthritis risk loci",
            },
        ],
    },
    {
        "rsid": "rs10488631",
        "fallback": {"chrom": "7", "position": 128594183, "ref_allele": "T", "alt_allele": "C",
                      "gene": "IRF5", "functional_class": "downstream_gene_variant", "maf_global": 0.12},
        "traits": [
            {
                "trait": "Systemic Lupus Erythematosus",
                "risk_allele": "C",
                "odds_ratio": 2.07,
                "beta": None,
                "p_value": 9.4e-10,
                "effect_description": "rs10488631 lies ~5 kb downstream of IRF5 (interferon regulatory factor 5). IRF5 is a master transcription factor driving type I interferon (IFN-\u03b1) production — central to lupus pathology. The C allele is associated with elevated IRF5 expression and the 'interferon signature' seen in lupus patients, approximately doubling lupus risk. IRF5 is one of the most consistently replicated non-HLA lupus risk factors across multiple populations. The finding has therapeutic implications — drugs targeting the type I interferon pathway (like anifrolumab) are now approved for lupus.",
                "effect_summary": "Higher lupus risk",
                "evidence_level": "high",
                "source_pmid": "18063667",
                "source_title": "Comprehensive evaluation of the genetic variants of interferon regulatory factor 5 reveals a novel 5 bp length polymorphism as strong risk factor for systemic lupus erythematosus",
            },
        ],
    },
    {
        "rsid": "rs1143679",
        "fallback": {"chrom": "16", "position": 31276811, "ref_allele": "G", "alt_allele": "A",
                      "gene": "ITGAM", "functional_class": "missense_variant", "maf_global": 0.07},
        "traits": [
            {
                "trait": "Systemic Lupus Erythematosus",
                "risk_allele": "A",
                "odds_ratio": 1.76,
                "beta": None,
                "p_value": 6.9e-22,
                "effect_description": "rs1143679 is a missense variant in ITGAM (integrin alpha-M, encoding CD11b — the complement receptor 3 subunit). The R77H change reduces both ITGAM expression and CD11b's ability to bind fibrinogen and vitronectin. CR3 helps phagocytes clear immune complexes; when impaired, complexes accumulate and trigger inflammation — a lupus hallmark. The A allele increases lupus risk by ~76%. Replicated in European, African, Hispanic, and Asian populations, making it one of the most robustly validated non-HLA lupus loci.",
                "effect_summary": "Higher lupus risk",
                "evidence_level": "high",
                "source_pmid": "18204448",
                "source_title": "A nonsynonymous functional variant in integrin-alphaM (encoded by ITGAM) is associated with systemic lupus erythematosus",
            },
        ],
    },
    # ── Nutrition & Metabolism (expanding existing category) ──────────
    {
        "rsid": "rs1049793",
        "fallback": {"chrom": "7", "position": 150557665, "ref_allele": "C", "alt_allele": "T",
                      "gene": "AOC1", "functional_class": "missense", "maf_global": 0.31},
        "traits": [
            {
                "trait": "Histamine Intolerance",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "AOC1 encodes diamine oxidase (DAO), the primary enzyme breaking down histamine from food in the gut. The rs1049793 variant (His645Asp) reduces DAO activity: heterozygous carriers show ~34% lower serum DAO, homozygous carriers ~49% lower. People with reduced DAO may struggle to clear histamine after eating histamine-rich foods (aged cheeses, cured meats, red wine), potentially experiencing headaches, flushing, nasal congestion, or digestive symptoms.",
                "effect_summary": "Reduced histamine clearance",
                "evidence_level": "medium",
                "source_pmid": "17700358",
                "source_title": "Genetic variability of human diamine oxidase: occurrence of three nonsynonymous polymorphisms and study of their effect on serum enzyme activity",
            },
        ],
    },
    {
        "rsid": "rs11558538",
        "fallback": {"chrom": "2", "position": 138759649, "ref_allele": "C", "alt_allele": "T",
                      "gene": "HNMT", "functional_class": "missense", "maf_global": 0.11},
        "traits": [
            {
                "trait": "Histamine Intolerance",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "HNMT (histamine N-methyltransferase) degrades histamine inside cells and in the central nervous system. The rs11558538 variant (Thr105Ile) reduces HNMT stability and protein levels. T allele carriers may clear intracellular histamine less efficiently, potentially contributing to histamine sensitivity symptoms. This variant is sometimes included in histamine-intolerance genetic panels alongside AOC1 variants, though direct GWAS evidence for histamine intolerance symptoms is limited.",
                "effect_summary": "Slower histamine clearance",
                "evidence_level": "low",
                "source_pmid": "21794955",
                "source_title": "Histamine N-methyltransferase Thr105Ile polymorphism is associated with Parkinson's disease",
            },
        ],
    },
    {
        "rsid": "rs4961",
        "fallback": {"chrom": "4", "position": 2906707, "ref_allele": "G", "alt_allele": "T",
                      "gene": "ADD1", "functional_class": "missense", "maf_global": 0.22},
        "traits": [
            {
                "trait": "Salt-Sensitive Blood Pressure",
                "risk_allele": "T",
                "odds_ratio": 1.40,
                "beta": None,
                "p_value": None,
                "effect_description": "Alpha-adducin (ADD1) influences how kidney cells reabsorb sodium. The rs4961 variant (Gly460Trp) increases sodium reabsorption efficiency, meaning T allele carriers retain more sodium on a high-salt diet — salt-sensitive hypertension. A meta-analysis found an overall OR of 1.40 (95% CI 0.96–2.04) that did not reach statistical significance in the overall population, but was significant in the Asian subgroup (OR 1.33, p=0.02). People with this variant may benefit more from a low-sodium diet or diuretic medications for blood pressure management.",
                "effect_summary": "Salt-sensitive blood pressure",
                "evidence_level": "medium",
                "source_pmid": "20145305",
                "source_title": "Association between alpha-adducin gene polymorphism (Gly460Trp) and genetic predisposition to salt sensitivity: a meta-analysis",
            },
        ],
    },
    {
        "rsid": "rs699",
        "fallback": {"chrom": "1", "position": 230845794, "ref_allele": "A", "alt_allele": "G",
                      "gene": "AGT", "functional_class": "missense", "maf_global": 0.43},
        "traits": [
            {
                "trait": "Hypertension Risk",
                "risk_allele": "G",
                "odds_ratio": 1.21,
                "beta": None,
                "p_value": None,
                "effect_description": "Angiotensinogen (AGT) is the precursor protein that the renin-angiotensin system converts into angiotensin II, a blood-vessel constrictor and sodium balance regulator. The rs699 variant (M235T) results in higher circulating angiotensinogen levels. A meta-analysis found TT vs MM genotype OR of 1.21 (95% CI 1.11–1.32) for essential hypertension. The variant interacts with dietary sodium and potassium intake.",
                "effect_summary": "Higher hypertension risk",
                "evidence_level": "medium",
                "source_pmid": "15642127",
                "source_title": "Polymorphisms of the insertion/deletion ACE and M235T AGT genes and hypertension: surprising new findings and meta-analysis of data",
            },
        ],
    },
    {
        "rsid": "rs5082",
        "fallback": {"chrom": "1", "position": 161193683, "ref_allele": "T", "alt_allele": "C",
                      "gene": "APOA2", "functional_class": "upstream_gene_variant", "maf_global": 0.35},
        "traits": [
            {
                "trait": "Saturated Fat Response / Obesity Risk",
                "risk_allele": "C",
                "odds_ratio": 1.84,
                "beta": None,
                "p_value": 0.01,
                "effect_description": "APOA2 is a major HDL cholesterol component influencing fat metabolism and satiety. The rs5082 variant (−265T>C) shows a robust gene-diet interaction: CC homozygotes eating high saturated fat (≥22 g/day) have ~6.2% higher BMI and an obesity OR of 1.84 (95% CI 1.38–2.47) compared to other genotypes eating similarly. Under low saturated fat intake, the difference disappears. Replicated in multiple US, Mediterranean, and Asian populations — one of the most robustly validated nutrigenomics findings. CC individuals may benefit from limiting saturated fat.",
                "effect_summary": "Higher saturated fat sensitivity",
                "evidence_level": "high",
                "source_pmid": "19901143",
                "source_title": "APOA2, dietary fat, and body mass index: replication of a gene-diet interaction in 3 independent populations",
            },
        ],
    },
    {
        "rsid": "rs1799883",
        "fallback": {"chrom": "4", "position": 120241902, "ref_allele": "G", "alt_allele": "A",
                      "gene": "FABP2", "functional_class": "missense", "maf_global": 0.28},
        "traits": [
            {
                "trait": "Dietary Fat Absorption / Insulin Resistance",
                "risk_allele": "A",
                "odds_ratio": 1.18,
                "beta": None,
                "p_value": 1e-4,
                "effect_description": "FABP2 (fatty acid binding protein 2) in intestinal cells shuttles dietary fatty acids. The rs1799883 variant (Ala54Thr) doubles the protein's affinity for fatty acids — Thr54 (A allele) carriers absorb more dietary fat per meal and show higher postprandial triglyceride spikes. Over time this can contribute to insulin resistance and elevated metabolic risk. The T2D risk effect is most clearly shown in Asian populations; results in Europeans are less consistent. Carriers may benefit from moderating total fat intake.",
                "effect_summary": "Increased dietary fat absorption",
                "evidence_level": "medium",
                "source_pmid": "25388378",
                "source_title": "Association between FABP2 Ala54Thr polymorphisms and type 2 diabetes mellitus risk: a HuGE Review and Meta-Analysis",
            },
        ],
    },
    {
        "rsid": "rs10246939",
        "fallback": {"chrom": "7", "position": 141672604, "ref_allele": "C", "alt_allele": "T",
                      "gene": "TAS2R38", "functional_class": "missense", "maf_global": 0.49},
        "traits": [
            {
                "trait": "Bitter Taste Perception (PROP/PTC)",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-20,
                "effect_description": "TAS2R38 encodes a bitter taste receptor for compounds in vegetables like Brussels sprouts, broccoli, and kale. Three SNPs — rs713598, rs1726866, and rs10246939 — define the PAV (taster) and AVI (non-taster) haplotypes. This SNP determines position 296 (Ile vs Val). People with at least one PAV copy perceive bitter flavors more intensely. Non-tasters (AVI/AVI) may eat more bitter vegetables overall. This SNP must be interpreted alongside rs713598 and rs1726866 for full haplotype assignment.",
                "effect_summary": "Stronger bitter taste perception",
                "evidence_level": "high",
                "source_pmid": "12595690",
                "source_title": "Variation in the gene TAS2R38 determines nontaster status in humans and is associated with food preferences",
            },
        ],
    },
    {
        "rsid": "rs35874116",
        "fallback": {"chrom": "1", "position": 19181393, "ref_allele": "A", "alt_allele": "G",
                      "gene": "TAS1R2", "functional_class": "missense", "maf_global": 0.22},
        "traits": [
            {
                "trait": "Sweet Taste Sensitivity / Sugar Intake",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 5e-4,
                "effect_description": "TAS1R2 forms half of the sweet taste receptor (with TAS1R3). The rs35874116 variant (Ile191Val) partially impairs receptor function by reducing cell-surface delivery. Val (G allele) carriers perceive sweet tastes less intensely, tend to consume less added sugar, and have modestly lower HbA1c and better glucose control. Carriers of the Ile (A) allele have a fully functioning receptor and may find sweet foods more appealing, potentially driving higher sugar consumption.",
                "effect_summary": "Stronger sweet taste perception",
                "evidence_level": "medium",
                "source_pmid": "34509698",
                "source_title": "The Ile191Val is a partial loss-of-function variant of the TAS1R2 sweet-taste receptor and is associated with reduced glucose excursions in humans",
            },
        ],
    },
    {
        "rsid": "rs307355",
        "fallback": {"chrom": "1", "position": 1265154, "ref_allele": "C", "alt_allele": "T",
                      "gene": "TAS1R3", "functional_class": "upstream_gene_variant", "maf_global": 0.28},
        "traits": [
            {
                "trait": "Sweet and Umami Taste Sensitivity",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 5e-6,
                "effect_description": "TAS1R3 pairs with TAS1R2 for sweet taste and with TAS1R1 for umami. The rs307355 promoter variant reduces TAS1R3 expression — T allele carriers perceive sucrose as less sweet and may need higher sugar or glutamate concentrations for the same taste satisfaction. This variant explains ~16% of sucrose perception variation in the population. T allele frequency runs from low in Western Europeans to high in East Asians, potentially influencing population-level dietary preferences.",
                "effect_summary": "Reduced sweet taste perception",
                "evidence_level": "medium",
                "source_pmid": "19559618",
                "source_title": "Allelic polymorphism within the TAS1R3 promoter is associated with human taste sensitivity to sucrose",
            },
        ],
    },
    {
        "rsid": "rs1761667",
        "fallback": {"chrom": "7", "position": 80244939, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CD36", "functional_class": "upstream_gene_variant", "maf_global": 0.42},
        "traits": [
            {
                "trait": "Fat Taste Sensitivity",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 5e-4,
                "effect_description": "CD36 (fatty acid translocase) acts as a receptor on taste cells detecting long-chain fatty acids — the molecules responsible for the creamy, rich quality of high-fat foods. The rs1761667 A allele reduces CD36 expression, lowering oral fat detection. A/A individuals have a higher threshold for tasting fat and may consume more fat to reach satisfaction. G/G individuals detect fat more readily and may feel satisfied with less. This variant also associates with cardiometabolic risk factors in some populations.",
                "effect_summary": "Reduced fat taste sensitivity",
                "evidence_level": "medium",
                "source_pmid": "22384968",
                "source_title": "Genetic influences on oral fat perception and preference",
            },
        ],
    },
    {
        "rsid": "rs698",
        "fallback": {"chrom": "4", "position": 100260789, "ref_allele": "A", "alt_allele": "G",
                      "gene": "ADH1C", "functional_class": "missense", "maf_global": 0.37},
        "traits": [
            {
                "trait": "Alcohol Metabolism Rate",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": None,
                "effect_description": "ADH1C encodes one of the primary liver alcohol dehydrogenases. The rs698 variant (Ile350Val) creates fast (Ile/A, ADH1C*1) and slow (Val/G, ADH1C*2) enzyme forms — the fast form is 40-65% more active. G/G individuals metabolize alcohol more slowly, meaning alcohol stays in the bloodstream longer. This accounts for ~12% of individual variation in alcohol clearance rate. Because rs698 is in near-complete LD with ADH1B (rs1229984), the ADH1C contribution is secondary to the larger ADH1B effect.",
                "effect_summary": "Slower alcohol metabolism",
                "evidence_level": "medium",
                "source_pmid": "19193628",
                "source_title": "ADH single nucleotide polymorphism associations with alcohol metabolism in vivo",
            },
        ],
    },
    # ── Athletic Performance (expanding existing category) ────────────
    {
        "rsid": "rs4343",
        "fallback": {"chrom": "17", "position": 61566031, "ref_allele": "G", "alt_allele": "A",
                      "gene": "ACE", "functional_class": "synonymous_variant", "maf_global": 0.43},
        "traits": [
            {
                "trait": "Endurance Athletic Performance",
                "risk_allele": "A",
                "odds_ratio": 1.35,
                "beta": None,
                "p_value": 1e-6,
                "effect_description": "The ACE gene encodes angiotensin-converting enzyme, regulating blood vessel tone and muscle blood flow. rs4343 is the best SNP proxy (r²=0.88) for the famous ACE insertion/deletion (I/D) variant. The A allele marks the I (insertion) form, associated with lower ACE activity and improved endurance capacity — a meta-analysis of 25 studies found the II genotype at OR 1.35 (95% CI 1.17–1.55) for elite endurance athlete status. Elite marathon runners, rowers, and high-altitude climbers are enriched for the A allele. The G allele marks the D (deletion) form, linked to higher ACE activity and greater strength/power gains.",
                "effect_summary": "Better endurance capacity",
                "evidence_level": "high",
                "source_pmid": "23358679",
                "source_title": "The association of sport performance with ACE and ACTN3 genetic polymorphisms: a systematic review and meta-analysis",
            },
        ],
    },
    {
        "rsid": "rs7181866",
        "fallback": {"chrom": "15", "position": 50610792, "ref_allele": "A", "alt_allele": "G",
                      "gene": "GABPB1", "functional_class": "intron_variant", "maf_global": 0.30},
        "traits": [
            {
                "trait": "Endurance Trainability / VO2max Response",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": 1e-3,
                "effect_description": "GABPB1 encodes the beta-1 subunit of GA-binding protein (NRF-2, nuclear respiratory factor 2), a transcription factor that activates genes for mitochondrial biogenesis and oxidative phosphorylation. The G allele is associated with greater VO₂max improvements after endurance training. A study of Polish rowers found the AG genotype frequency significantly higher in elite rowers (10.9%) vs controls (2.3%), and the G allele frequency was 5.5% vs 1.2% in controls (p=0.014). The AG genotype may induce greater gene transcription and higher protein mRNA expression.",
                "effect_summary": "Greater VO2max training response",
                "evidence_level": "medium",
                "source_pmid": "23486860",
                "source_title": "The GABPB1 gene A/G polymorphism in Polish rowers",
            },
        ],
    },
    # ── Sleep / Circadian (expanding existing category) ───────────────
    {
        "rsid": "rs5751876",
        "fallback": {"chrom": "22", "position": 24837301, "ref_allele": "T", "alt_allele": "C",
                      "gene": "ADORA2A", "functional_class": "synonymous_variant", "maf_global": 0.47},
        "traits": [
            {
                "trait": "Caffeine Sensitivity / Sleep Disruption",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 5e-5,
                "effect_description": "The adenosine A2A receptor (ADORA2A) is the primary target through which caffeine promotes wakefulness. Adenosine builds up during waking hours and promotes sleepiness; caffeine blocks the A2A receptor. TT homozygotes are more sensitive to caffeine: they experience greater alertness, anxiety, and sleep disruption from the same dose. C allele carriers are relatively caffeine-tolerant. This explains why some people can drink espresso after dinner and sleep fine, while others are wired for hours.",
                "effect_summary": "Higher caffeine sensitivity",
                "evidence_level": "high",
                "source_pmid": "17329997",
                "source_title": "A genetic variation in the adenosine A2A receptor gene (ADORA2A) contributes to individual sensitivity to caffeine effects on sleep",
            },
        ],
    },
    # ── Wellness & Lifestyle (Dante Labs report SNPs) ────────────────
    {
        "rsid": "rs1126742",
        "fallback": {"chrom": "1", "position": 47398496, "ref_allele": "A", "alt_allele": "G",
                      "gene": "CYP4A11", "functional_class": "missense_variant", "maf_global": 0.15},
        "traits": [
            {
                "trait": "Hypertension",
                "risk_allele": "G",
                "odds_ratio": 1.15,
                "beta": None,
                "p_value": 0.02,
                "effect_description": "The CYP4A11 F434S variant (rs1126742 G allele) reduces 20-HETE synthesis by more than half. 20-HETE is a potent regulator of renal sodium excretion and vascular tone. Carriers of the G allele have modestly increased risk of essential hypertension (meta-analytic OR ~1.15 additive, ~1.52 recessive across 8 studies). The original discovery in a Tennessee cohort reported a stronger effect (OR 2.31), but this attenuated in larger replication samples.",
                "effect_summary": "Higher hypertension risk",
                "evidence_level": "medium",
                "source_pmid": "24278241",
                "source_title": "CYP4A11 T8590C polymorphism and hypertension risk: a meta-analysis",
            },
        ],
    },
    {
        "rsid": "rs12203592",
        "fallback": {"chrom": "6", "position": 396321, "ref_allele": "C", "alt_allele": "T",
                      "gene": "IRF4", "functional_class": "intron_variant", "maf_global": 0.11},
        "traits": [
            {
                "trait": "Skin Pigmentation / Tanning Ability",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": 0.37,
                "p_value": 3.9e-89,
                "effect_description": "The IRF4 rs12203592 T allele is one of the strongest common genetic determinants of human pigmentation. It disrupts a TFAP2A binding site in a melanocyte enhancer, reducing IRF4 expression and downstream tyrosinase activity. Carriers have lighter skin, reduced tanning ability, lighter hair, and increased susceptibility to UV damage and skin cancer. The variant is essentially absent in African and East Asian populations and reaches ~17% frequency in Europeans.",
                "effect_summary": "Reduced tanning ability",
                "evidence_level": "high",
                "source_pmid": "18483556",
                "source_title": "A genome-wide association study identifies novel alleles associated with hair color and skin pigmentation",
            },
        ],
    },
    {
        "rsid": "rs3749474",
        "fallback": {"chrom": "4", "position": 56300685, "ref_allele": "C", "alt_allele": "T",
                      "gene": "CLOCK", "functional_class": "3_prime_UTR_variant", "maf_global": 0.34},
        "traits": [
            {
                "trait": "Energy Intake / Appetite",
                "risk_allele": "T",
                "odds_ratio": 1.33,
                "beta": None,
                "p_value": 0.035,
                "effect_description": "The CLOCK gene regulates circadian rhythms that govern sleep-wake cycles, appetite, and metabolism. The rs3749474 T allele in the 3' UTR is associated with higher total energy intake across all macronutrients (OR 1.33 for high energy intake). T allele carriers also show altered circadian hormone patterns with higher ghrelin and lower leptin levels. However, the same allele predicts a greater weight-loss response to fat-restricted diets, suggesting potential for genotype-guided dietary interventions.",
                "effect_summary": "Higher energy intake tendency",
                "evidence_level": "medium",
                "source_pmid": "19888304",
                "source_title": "Genetic variants in human CLOCK associate with total energy intake and cytokine sleep factors in overweight subjects (GOLDN population)",
            },
        ],
    },
    {
        "rsid": "rs806368",
        "fallback": {"chrom": "6", "position": 88850100, "ref_allele": "T", "alt_allele": "C",
                      "gene": "CNR1", "functional_class": "3_prime_UTR_variant", "maf_global": 0.21},
        "traits": [
            {
                "trait": "Panic Disorder",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.05,
                "effect_description": "The CNR1 gene encodes cannabinoid receptor 1, a key component of the endocannabinoid system that modulates stress recovery and anxiety responses. The C allele of rs806368 in the 3' UTR was associated with increased vulnerability to panic disorder in a case-control study, with the effect more pronounced in females. The endocannabinoid system regulates emotional state through CB1 receptor signaling in the amygdala and prefrontal cortex.",
                "effect_summary": "Higher panic disorder vulnerability",
                "evidence_level": "low",
                "source_pmid": "32114795",
                "source_title": "Association of cannabinoid receptor genes (CNR1 and CNR2) polymorphisms and panic disorder",
            },
        ],
    },
    {
        "rsid": "rs12720071",
        "fallback": {"chrom": "6", "position": 88851181, "ref_allele": "T", "alt_allele": "C",
                      "gene": "CNR1", "functional_class": "3_prime_UTR_variant", "maf_global": 0.11},
        "traits": [
            {
                "trait": "Panic Disorder",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.012,
                "effect_description": "A second CNR1 3' UTR variant ~1 kb downstream of rs806368. The minor C allele of rs12720071 was associated with increased panic disorder vulnerability (p = 0.012) in the same candidate gene study, with a sex-specific pattern showing stronger effects in females. Together with rs806368, these variants implicate endocannabinoid signaling dysfunction in the pathophysiology of panic disorder.",
                "effect_summary": "Higher panic disorder vulnerability",
                "evidence_level": "low",
                "source_pmid": "32114795",
                "source_title": "Association of cannabinoid receptor genes (CNR1 and CNR2) polymorphisms and panic disorder",
            },
        ],
    },
    {
        "rsid": "rs6943555",
        "fallback": {"chrom": "7", "position": 69806023, "ref_allele": "T", "alt_allele": "A",
                      "gene": "AUTS2", "functional_class": "intron_variant", "maf_global": 0.36},
        "traits": [
            {
                "trait": "Alcohol Consumption",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": 0.055,
                "p_value": 4.1e-9,
                "effect_description": "The AUTS2 gene (Activator of Transcription and Developmental Regulator) is expressed in the brain and involved in neurodevelopmental processes. In a GWAS of 26,316 Europeans with 21,185 replication, the minor A allele was associated with ~5.5% lower alcohol consumption at genome-wide significance. Functional validation showed genotype-specific AUTS2 expression in human prefrontal cortex and differential expression in mice bred for alcohol preference. The common T allele is associated with higher baseline alcohol consumption.",
                "effect_summary": "Higher alcohol consumption",
                "evidence_level": "high",
                "source_pmid": "21471458",
                "source_title": "Genome-wide association and genetic functional studies identify autism susceptibility candidate 2 gene (AUTS2) in the regulation of alcohol consumption",
            },
        ],
    },
    {
        "rsid": "rs17601612",
        "fallback": {"chrom": "11", "position": 113317745, "ref_allele": "G", "alt_allele": "C",
                      "gene": "DRD2", "functional_class": "intron_variant", "maf_global": 0.28},
        "traits": [
            {
                "trait": "Sleep Duration",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": -3.07,
                "p_value": 9.75e-7,
                "effect_description": "The dopamine D2 receptor (DRD2) is a central mediator of reward processing and arousal. In a multi-ethnic GWAS meta-analysis of >25,000 individuals (CARe consortium), the derived C allele of rs17601612 in DRD2 intron 1 was associated with approximately 3 minutes shorter self-reported sleep duration per allele. Conditional analysis identified a second independent DRD2 signal with opposite effects, suggesting complex dopaminergic regulation of sleep behavior.",
                "effect_summary": "Shorter sleep duration",
                "evidence_level": "medium",
                "source_pmid": "26464489",
                "source_title": "Common variants in DRD2 are associated with sleep duration: the CARe consortium",
            },
        ],
    },
    {
        "rsid": "rs228697",
        "fallback": {"chrom": "1", "position": 7887579, "ref_allele": "C", "alt_allele": "G",
                      "gene": "PER3", "functional_class": "missense_variant", "maf_global": 0.07},
        "traits": [
            {
                "trait": "Chronotype (Morning/Evening Preference)",
                "risk_allele": "G",
                "odds_ratio": 2.48,
                "beta": None,
                "p_value": 0.012,
                "effect_description": "The PER3 gene is a core component of the circadian clock. The rs228697 G allele causes a Pro864Ala substitution that disrupts an SH3-binding domain, stabilizing PER3 protein and altering recruitment of PER2 into the CLOCK/BMAL1 repressor complex. In a systematic screening of 29 clock gene polymorphisms, this variant was significantly more common in evening chronotypes (OR 2.48, Bonferroni-corrected p = 0.012). Note: this SNP is in PER3, not PER2 as sometimes misreported.",
                "effect_summary": "Evening chronotype",
                "evidence_level": "medium",
                "source_pmid": "25201053",
                "source_title": "Screening of clock gene polymorphisms demonstrates association of a PER3 polymorphism with morningness-eveningness preference and circadian rhythm sleep disorder",
            },
        ],
    },
    {
        "rsid": "rs17782313",
        "fallback": {"chrom": "18", "position": 57851097, "ref_allele": "T", "alt_allele": "C",
                      "gene": "MC4R", "functional_class": "intergenic_variant", "maf_global": 0.24},
        "traits": [
            {
                "trait": "Obesity / BMI",
                "risk_allele": "C",
                "odds_ratio": 1.30,
                "beta": None,
                "p_value": 8.0e-11,
                "effect_description": "Located 188 kb downstream of MC4R, this was the second obesity locus identified by GWAS (after FTO). The C allele increases BMI by 0.05 Z-score units per allele in adults (p = 2.8e-15 in 77,228 adults) and confers a 1.30-fold increased odds of severe childhood obesity (p = 8.0e-11 in 10,583 children). MC4R is the most common cause of monogenic severe childhood-onset obesity, and this common variant acts through the same melanocortin pathway regulating appetite and energy balance. Subsequent studies show sex-specific effects on eating behavior, with female carriers displaying greater disinhibition and emotional eating.",
                "effect_summary": "Higher BMI",
                "evidence_level": "high",
                "source_pmid": "18454148",
                "source_title": "Common variants near MC4R are associated with fat mass, weight and risk of obesity",
            },
        ],
    },
    {
        "rsid": "rs16969968",
        "fallback": {"chrom": "15", "position": 78882925, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CHRNA5", "functional_class": "missense_variant", "maf_global": 0.31},
        "traits": [
            {
                "trait": "Nicotine Dependence",
                "risk_allele": "A",
                "odds_ratio": 1.3,
                "beta": None,
                "p_value": 6.4e-4,
                "effect_description": "The CHRNA5 D398N variant (rs16969968 A allele) alters the alpha-5 subunit of the nicotinic acetylcholine receptor, reducing receptor response to nicotine. This diminishes the aversive signals that normally limit smoking intensity, leading to heavier smoking. The per-allele OR for nicotine dependence is ~1.3, with homozygous AA carriers at nearly 2-fold increased risk (OR 1.9). The variant is also associated with earlier age of lung cancer diagnosis and delayed smoking cessation (AA carriers quit on average 4 years later). The A allele is common in Europeans (~35%) but rare in East Asian and African populations.",
                "effect_summary": "Higher nicotine dependence risk",
                "evidence_level": "high",
                "source_pmid": "17135278",
                "source_title": "Cholinergic nicotinic receptor genes implicated in a nicotine dependence association study targeting 348 candidate genes with 3713 SNPs",
            },
        ],
    },
    # ── Methylation Cycle ─────────────────────────────────────────────────
    # 23 SNPs covering the folate/methylation pathway: COMT, VDR, MAO-A,
    # MTHFR, MTR, MTRR, BHMT, AHCY, CBS, SHMT1, ACAT1.
    # Complements existing rs4680 (COMT V158M), rs1801133 (MTHFR C677T),
    # and rs1801131 (MTHFR A1298C, in PGx).
    {
        "rsid": "rs4633",
        "fallback": {"chrom": "22", "position": 19950235, "ref_allele": "C", "alt_allele": "T",
                      "gene": "COMT", "functional_class": "synonymous_variant", "maf_global": 0.45},
        "traits": [
            {
                "trait": "COMT Enzyme Activity",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 3.8e-8,
                "effect_description": "The COMT H62H variant (rs4633) is a synonymous SNP in strong linkage disequilibrium with the functional Val158Met polymorphism (rs4680). The T allele tags the low-activity COMT haplotype and has been shown to alter mRNA secondary structure, reducing COMT protein expression by up to 25%. This may lead to slower catecholamine clearance in the prefrontal cortex.",
                "effect_summary": "Lower COMT enzyme activity",
                "evidence_level": "medium",
                "source_pmid": "16631354",
                "source_title": "Human catechol-O-methyltransferase haplotypes modulate protein expression by altering mRNA secondary structure",
            },
        ],
    },
    {
        "rsid": "rs769224",
        "fallback": {"chrom": "22", "position": 19951804, "ref_allele": "G", "alt_allele": "A",
                      "gene": "COMT", "functional_class": "synonymous_variant", "maf_global": 0.05},
        "traits": [
            {
                "trait": "COMT Enzyme Activity",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.02,
                "effect_description": "The COMT P199P variant (rs769224) is a rare synonymous SNP that forms part of the COMT haplotype block. The A allele is uncommon (~5% globally) and contributes to a haplotype associated with altered COMT enzyme activity, though its independent functional impact is minimal.",
                "effect_summary": "Altered COMT enzyme activity",
                "evidence_level": "low",
                "source_pmid": "16631354",
                "source_title": "Human catechol-O-methyltransferase haplotypes modulate protein expression by altering mRNA secondary structure",
            },
        ],
    },
    {
        "rsid": "rs1544410",
        "fallback": {"chrom": "12", "position": 48239835, "ref_allele": "C", "alt_allele": "T",
                      "gene": "VDR", "functional_class": "intron_variant", "maf_global": 0.30},
        "traits": [
            {
                "trait": "Vitamin D Metabolism",
                "risk_allele": "T",
                "odds_ratio": 1.5,
                "beta": None,
                "p_value": 2.1e-4,
                "effect_description": "The VDR BsmI polymorphism (rs1544410) is an intronic variant in the vitamin D receptor gene. The T allele (BsmI 'b' allele) has been associated with reduced VDR mRNA stability, lower bone mineral density, and increased osteoporosis risk in Caucasian populations (OR ~1.5 for homozygous carriers). Effects are population-dependent and less consistent in Asian populations.",
                "effect_summary": "Reduced vitamin D metabolism",
                "evidence_level": "medium",
                "source_pmid": "23134477",
                "source_title": "Vitamin D receptor BsmI polymorphism and osteoporosis risk: a meta-analysis from 26 studies",
            },
        ],
    },
    {
        "rsid": "rs731236",
        "fallback": {"chrom": "12", "position": 48238757, "ref_allele": "A", "alt_allele": "G",
                      "gene": "VDR", "functional_class": "synonymous_variant", "maf_global": 0.34},
        "traits": [
            {
                "trait": "Vitamin D Metabolism",
                "risk_allele": "G",
                "odds_ratio": 1.3,
                "beta": None,
                "p_value": 1.2e-3,
                "effect_description": "The VDR TaqI polymorphism (rs731236) is a synonymous variant in exon 9 of the vitamin D receptor gene, in linkage disequilibrium with BsmI (rs1544410). The G allele (TaqI 't' allele) has been associated with reduced VDR expression, lower serum 25(OH)D levels, and modestly increased osteoporosis susceptibility.",
                "effect_summary": "Reduced vitamin D metabolism",
                "evidence_level": "medium",
                "source_pmid": "15472169",
                "source_title": "Genetics and biology of vitamin D receptor polymorphisms",
            },
        ],
    },
    {
        "rsid": "rs6323",
        "fallback": {"chrom": "X", "position": 43591036, "ref_allele": "G", "alt_allele": "T",
                      "gene": "MAOA", "functional_class": "synonymous_variant", "maf_global": 0.65},
        "traits": [
            {
                "trait": "MAO-A Enzyme Activity",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 6e-4,
                "effect_description": "The MAO-A R297R variant (rs6323) is a synonymous SNP on the X chromosome (males are hemizygous). The T allele is associated with lower MAO-A enzyme expression, resulting in slower breakdown of serotonin, dopamine, and norepinephrine. This variant has been associated with altered stress response, ADHD susceptibility, and antidepressant response. The T allele is the more common allele globally (~65%).",
                "effect_summary": "Lower MAO-A enzyme activity",
                "evidence_level": "medium",
                "source_pmid": "19593178",
                "source_title": "The pharmacogenomics of the placebo response in major depressive disorder",
            },
        ],
    },
    {
        "rsid": "rs3741049",
        "fallback": {"chrom": "11", "position": 108009927, "ref_allele": "G", "alt_allele": "A",
                      "gene": "ACAT1", "functional_class": "intron_variant", "maf_global": 0.10},
        "traits": [
            {
                "trait": "Acetyl-CoA Metabolism",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.03,
                "effect_description": "The ACAT1-02 variant (rs3741049) is an intronic polymorphism in the acetyl-CoA acetyltransferase 1 gene, which plays a role in lipid metabolism and ketone body formation. The A allele has been proposed to affect ACAT1 expression, potentially influencing B12 utilization, though published evidence for clinical significance is limited.",
                "effect_summary": "Altered acetyl-CoA metabolism",
                "evidence_level": "low",
                "source_pmid": "21068723",
                "source_title": "Identification and functional characterization of common polymorphisms in human ACAT1",
            },
        ],
    },
    {
        "rsid": "rs2066470",
        "fallback": {"chrom": "1", "position": 11863057, "ref_allele": "G", "alt_allele": "A",
                      "gene": "MTHFR", "functional_class": "synonymous_variant", "maf_global": 0.09},
        "traits": [
            {
                "trait": "Folate Metabolism",
                "risk_allele": "A",
                "odds_ratio": 1.2,
                "beta": None,
                "p_value": 0.04,
                "effect_description": "The MTHFR P39P variant (rs2066470) is a synonymous SNP in the 5' region of the MTHFR gene. The A allele has been associated with modestly increased risk of neural tube defects in some populations, possibly through effects on mRNA stability. Its functional impact is much smaller than the well-established C677T (rs1801133) variant.",
                "effect_summary": "Modestly altered folate metabolism",
                "evidence_level": "medium",
                "source_pmid": "15847033",
                "source_title": "Neural tube defects: pathogenesis and folate metabolism",
            },
        ],
    },
    {
        "rsid": "rs1805087",
        "fallback": {"chrom": "1", "position": 237048500, "ref_allele": "A", "alt_allele": "G",
                      "gene": "MTR", "functional_class": "missense_variant", "maf_global": 0.21},
        "traits": [
            {
                "trait": "Methionine Synthase / B12 Metabolism",
                "risk_allele": "G",
                "odds_ratio": 1.4,
                "beta": None,
                "p_value": 5e-5,
                "effect_description": "The MTR A2756G variant (rs1805087) is a missense polymorphism (Asp919Gly) in methionine synthase, the vitamin B12-dependent enzyme that remethylates homocysteine to methionine. The G allele may increase enzyme activity, leading to faster depletion of methylcobalamin (active B12). Combined with MTHFR C677T, this variant can contribute to persistently elevated homocysteine unless treated with both B12 and folate.",
                "effect_summary": "Faster B12 depletion",
                "evidence_level": "high",
                "source_pmid": "16485733",
                "source_title": "Influence of methionine synthase and methionine synthase reductase polymorphisms on plasma homocysteine levels and relation to risk of coronary artery disease",
            },
        ],
    },
    {
        "rsid": "rs1801394",
        "fallback": {"chrom": "5", "position": 7870973, "ref_allele": "A", "alt_allele": "G",
                      "gene": "MTRR", "functional_class": "missense_variant", "maf_global": 0.45},
        "traits": [
            {
                "trait": "B12 Recycling / Methionine Synthase Reductase",
                "risk_allele": "G",
                "odds_ratio": 1.31,
                "beta": None,
                "p_value": 1.3e-4,
                "effect_description": "The MTRR A66G variant (rs1801394) is a missense polymorphism (Ile22Met) in methionine synthase reductase, which regenerates the active form of vitamin B12 needed by methionine synthase. The G allele reduces enzyme efficiency, impairing B12 recycling and potentially elevating homocysteine. A meta-analysis found homozygous GG carriers have ~1.31-fold increased maternal risk for neural tube defects in Caucasian populations.",
                "effect_summary": "Impaired B12 recycling",
                "evidence_level": "high",
                "source_pmid": "23266814",
                "source_title": "Association between MTR A2756G and MTRR A66G polymorphisms and maternal risk for neural tube defects: a meta-analysis",
            },
        ],
    },
    {
        "rsid": "rs10380",
        "fallback": {"chrom": "5", "position": 7897191, "ref_allele": "C", "alt_allele": "T",
                      "gene": "MTRR", "functional_class": "missense_variant", "maf_global": 0.18},
        "traits": [
            {
                "trait": "Methionine Synthase Reductase Activity",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.08,
                "effect_description": "The MTRR H595Y variant (rs10380) is a missense polymorphism (His595Tyr) in methionine synthase reductase. The T allele changes a histidine to tyrosine residue. This variant is less well-studied than MTRR A66G (rs1801394) and has not shown consistent independent associations with homocysteine levels or disease risk in published studies.",
                "effect_summary": "Altered MTRR activity",
                "evidence_level": "low",
                "source_pmid": "16485733",
                "source_title": "Influence of methionine synthase and methionine synthase reductase polymorphisms on plasma homocysteine levels and relation to risk of coronary artery disease",
            },
        ],
    },
    {
        "rsid": "rs162036",
        "fallback": {"chrom": "5", "position": 7885959, "ref_allele": "A", "alt_allele": "G",
                      "gene": "MTRR", "functional_class": "missense_variant", "maf_global": 0.21},
        "traits": [
            {
                "trait": "Methionine Synthase Reductase Activity",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.05,
                "effect_description": "The MTRR K350A variant (rs162036) is a missense polymorphism (Lys350Ala) in methionine synthase reductase. The G allele changes a lysine to alanine residue, which may affect enzyme function. Some studies have found modest associations with altered homocysteine metabolism, but evidence is inconsistent and the variant has not been independently validated in large meta-analyses.",
                "effect_summary": "Altered MTRR activity",
                "evidence_level": "low",
                "source_pmid": "16485733",
                "source_title": "Influence of methionine synthase and methionine synthase reductase polymorphisms on plasma homocysteine levels and relation to risk of coronary artery disease",
            },
        ],
    },
    {
        "rsid": "rs2287780",
        "fallback": {"chrom": "5", "position": 7889304, "ref_allele": "C", "alt_allele": "T",
                      "gene": "MTRR", "functional_class": "missense_variant", "maf_global": 0.04},
        "traits": [
            {
                "trait": "Methionine Synthase Reductase Activity",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.12,
                "effect_description": "The MTRR R415T variant (rs2287780) is a rare missense polymorphism (Arg415Thr) in methionine synthase reductase (~4% global frequency). The T allele changes an arginine to threonine residue. Limited published evidence exists for independent clinical significance.",
                "effect_summary": "Altered MTRR activity",
                "evidence_level": "low",
                "source_pmid": "16485733",
                "source_title": "Influence of methionine synthase and methionine synthase reductase polymorphisms on plasma homocysteine levels and relation to risk of coronary artery disease",
            },
        ],
    },
    {
        "rsid": "rs1802059",
        "fallback": {"chrom": "5", "position": 7897319, "ref_allele": "G", "alt_allele": "A",
                      "gene": "MTRR", "functional_class": "synonymous_variant", "maf_global": 0.31},
        "traits": [
            {
                "trait": "Methionine Synthase Reductase Activity",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.15,
                "effect_description": "The MTRR A664A variant (rs1802059) is a synonymous polymorphism in methionine synthase reductase. The A allele does not change the amino acid sequence. This variant is part of the MTRR haplotype block and has limited independent evidence for functional impact on B12 recycling or homocysteine metabolism.",
                "effect_summary": "Altered MTRR activity",
                "evidence_level": "low",
                "source_pmid": "16485733",
                "source_title": "Influence of methionine synthase and methionine synthase reductase polymorphisms on plasma homocysteine levels and relation to risk of coronary artery disease",
            },
        ],
    },
    {
        "rsid": "rs567754",
        "fallback": {"chrom": "5", "position": 78416416, "ref_allele": "C", "alt_allele": "T",
                      "gene": "BHMT", "functional_class": "intron_variant", "maf_global": 0.27},
        "traits": [
            {
                "trait": "Betaine-Homocysteine Methylation",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.08,
                "effect_description": "The BHMT-02 variant (rs567754) is an intronic polymorphism in betaine-homocysteine S-methyltransferase, which provides an alternative pathway to remethylate homocysteine to methionine using betaine as the methyl donor. Published evidence for the independent clinical significance of this intronic variant is very limited.",
                "effect_summary": "Altered betaine methylation",
                "evidence_level": "low",
                "source_pmid": "17024475",
                "source_title": "Betaine-homocysteine S-methyltransferase and methylenetetrahydrofolate reductase polymorphisms, betaine, and choline in relation to homocysteine concentration",
            },
        ],
    },
    {
        "rsid": "rs617219",
        "fallback": {"chrom": "5", "position": 78429594, "ref_allele": "A", "alt_allele": "C",
                      "gene": "BHMT", "functional_class": "intron_variant", "maf_global": 0.36},
        "traits": [
            {
                "trait": "Betaine-Homocysteine Methylation",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.10,
                "effect_description": "The BHMT-04 variant (rs617219) is an intronic polymorphism in betaine-homocysteine S-methyltransferase. No peer-reviewed association studies have established independent clinical significance for this variant. It is primarily reported in methylation nutrigenomics protocols.",
                "effect_summary": "Altered betaine methylation",
                "evidence_level": "low",
                "source_pmid": "17024475",
                "source_title": "Betaine-homocysteine S-methyltransferase and methylenetetrahydrofolate reductase polymorphisms, betaine, and choline in relation to homocysteine concentration",
            },
        ],
    },
    {
        "rsid": "rs651852",
        "fallback": {"chrom": "5", "position": 78409060, "ref_allele": "C", "alt_allele": "T",
                      "gene": "BHMT", "functional_class": "intron_variant", "maf_global": 0.41},
        "traits": [
            {
                "trait": "Betaine-Homocysteine Methylation",
                "risk_allele": "T",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.05,
                "effect_description": "The BHMT-08 variant (rs651852) is a polymorphism in the BHMT gene region. This variant has been proposed to influence the betaine-dependent homocysteine remethylation shortcut pathway. Some studies suggest associations with altered glycine levels in homozygous carriers, but peer-reviewed evidence for clinical significance is limited.",
                "effect_summary": "Altered betaine methylation",
                "evidence_level": "low",
                "source_pmid": "17024475",
                "source_title": "Betaine-homocysteine S-methyltransferase and methylenetetrahydrofolate reductase polymorphisms, betaine, and choline in relation to homocysteine concentration",
            },
        ],
    },
    {
        "rsid": "rs819147",
        "fallback": {"chrom": "20", "position": 32889704, "ref_allele": "C", "alt_allele": "T",
                      "gene": "AHCY", "functional_class": "intron_variant", "maf_global": 0.29},
        "traits": [
            {
                "trait": "S-Adenosylhomocysteine Metabolism",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.20,
                "effect_description": "The AHCY-01 variant (rs819147) is an intronic polymorphism in S-adenosylhomocysteine hydrolase, which converts S-adenosylhomocysteine to adenosine and homocysteine. Note: the C allele is the GRCh38 reference but the minor allele (~29%). No peer-reviewed studies have established independent clinical significance for this variant.",
                "effect_summary": "Altered SAH metabolism",
                "evidence_level": "low",
                "source_pmid": "15523652",
                "source_title": "S-adenosylhomocysteine hydrolase deficiency in a human: a genetic disorder of methionine metabolism",
            },
        ],
    },
    {
        "rsid": "rs819134",
        "fallback": {"chrom": "20", "position": 32873619, "ref_allele": "G", "alt_allele": "A",
                      "gene": "AHCY", "functional_class": "intron_variant", "maf_global": 0.26},
        "traits": [
            {
                "trait": "S-Adenosylhomocysteine Metabolism",
                "risk_allele": "G",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.20,
                "effect_description": "The AHCY-02 variant (rs819134) is an intronic polymorphism in S-adenosylhomocysteine hydrolase. Note: the G allele is the GRCh38 reference but the minor allele (~26%). No peer-reviewed association studies have established independent clinical significance for this variant.",
                "effect_summary": "Altered SAH metabolism",
                "evidence_level": "low",
                "source_pmid": "15523652",
                "source_title": "S-adenosylhomocysteine hydrolase deficiency in a human: a genetic disorder of methionine metabolism",
            },
        ],
    },
    {
        "rsid": "rs819171",
        "fallback": {"chrom": "20", "position": 32867984, "ref_allele": "C", "alt_allele": "T",
                      "gene": "AHCY", "functional_class": "intron_variant", "maf_global": 0.25},
        "traits": [
            {
                "trait": "S-Adenosylhomocysteine Metabolism",
                "risk_allele": "C",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.20,
                "effect_description": "The AHCY-19 variant (rs819171) is an intronic polymorphism in S-adenosylhomocysteine hydrolase. Note: the C allele is the GRCh38 reference but the minor allele (~25%). No peer-reviewed studies have established independent clinical significance for this variant.",
                "effect_summary": "Altered SAH metabolism",
                "evidence_level": "low",
                "source_pmid": "15523652",
                "source_title": "S-adenosylhomocysteine hydrolase deficiency in a human: a genetic disorder of methionine metabolism",
            },
        ],
    },
    {
        "rsid": "rs234706",
        "fallback": {"chrom": "21", "position": 44485350, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CBS", "functional_class": "synonymous_variant", "maf_global": 0.27},
        "traits": [
            {
                "trait": "Transsulfuration Pathway",
                "risk_allele": "A",
                "odds_ratio": 0.50,
                "beta": None,
                "p_value": 0.008,
                "effect_description": "The CBS C699T variant (rs234706) is a synonymous polymorphism in cystathionine beta-synthase, which catalyzes the first step of the transsulfuration pathway converting homocysteine to cystathionine. The A allele (699T) has been associated with CBS upregulation, potentially lowering homocysteine levels. Homozygous carriers showed reduced risk of cleft lip/palate (OR 0.50). In normal populations, CBS upregulation appears protective against hyperhomocysteinemia.",
                "effect_summary": "Lower homocysteine levels",
                "evidence_level": "medium",
                "source_pmid": "11149614",
                "source_title": "Influence of 699C-->T and 1080C-->T polymorphisms of the cystathionine beta-synthase gene on plasma homocysteine levels",
            },
        ],
    },
    {
        "rsid": "rs1801181",
        "fallback": {"chrom": "21", "position": 44480616, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CBS", "functional_class": "synonymous_variant", "maf_global": 0.33},
        "traits": [
            {
                "trait": "Transsulfuration Pathway",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.02,
                "effect_description": "The CBS A360A variant (rs1801181) is a synonymous polymorphism in cystathionine beta-synthase. The A allele has been associated with altered CBS enzyme activity in the transsulfuration pathway. Some studies suggest it may influence homocysteine to cystathionine conversion, but evidence is less robust than for the C699T variant (rs234706).",
                "effect_summary": "Altered CBS enzyme activity",
                "evidence_level": "low",
                "source_pmid": "11149614",
                "source_title": "Influence of 699C-->T and 1080C-->T polymorphisms of the cystathionine beta-synthase gene on plasma homocysteine levels",
            },
        ],
    },
    {
        "rsid": "rs2298758",
        "fallback": {"chrom": "21", "position": 44485527, "ref_allele": "G", "alt_allele": "A",
                      "gene": "CBS", "functional_class": "synonymous_variant", "maf_global": 0.001},
        "traits": [
            {
                "trait": "Transsulfuration Pathway",
                "risk_allele": "A",
                "odds_ratio": None,
                "beta": None,
                "p_value": 0.30,
                "effect_description": "The CBS N212N variant (rs2298758) is a very rare synonymous polymorphism in cystathionine beta-synthase (~0.1% global frequency). Due to its rarity, there is very limited published evidence for any independent clinical significance.",
                "effect_summary": "Altered CBS enzyme activity",
                "evidence_level": "low",
                "source_pmid": "11149614",
                "source_title": "Influence of 699C-->T and 1080C-->T polymorphisms of the cystathionine beta-synthase gene on plasma homocysteine levels",
            },
        ],
    },
    {
        "rsid": "rs1979277",
        "fallback": {"chrom": "17", "position": 18232096, "ref_allele": "G", "alt_allele": "A",
                      "gene": "SHMT1", "functional_class": "missense_variant", "maf_global": 0.31},
        "traits": [
            {
                "trait": "Folate-Mediated One-Carbon Metabolism",
                "risk_allele": "A",
                "odds_ratio": 1.3,
                "beta": None,
                "p_value": 0.01,
                "effect_description": "The SHMT1 C1420T variant (rs1979277) is a missense polymorphism (Leu474Phe) in cytoplasmic serine hydroxymethyltransferase, which provides one-carbon units for DNA synthesis and methylation by converting serine to glycine. The A allele may alter the balance between thymidylate synthesis and homocysteine remethylation. Parental carrier status has been associated with increased neural tube defect risk in offspring.",
                "effect_summary": "Altered folate metabolism",
                "evidence_level": "medium",
                "source_pmid": "28762673",
                "source_title": "Interaction between maternal and paternal SHMT1 C1420T predisposes to neural tube defects in the fetus",
            },
        ],
    },
]

# Remove duplicate entries (e.g., rs4988235 appears twice)
_seen: set[str] = set()
_deduped: list[dict] = []
for entry in SEED_SNPS:
    if entry["rsid"] not in _seen and "fallback" in entry:
        _seen.add(entry["rsid"])
        _deduped.append(entry)
SEED_SNPS = _deduped

# Append pharmacogenomic SNP catalog (~76 additional variants)
SEED_SNPS.extend(PGX_SEED_SNPS)


# ---------------------------------------------------------------------------
# MyVariant.info API fetcher
# ---------------------------------------------------------------------------

# ClinVar significance severity ordering (highest first)
CLINVAR_SEVERITY = [
    "pathogenic",
    "likely_pathogenic",
    "risk_factor",
    "association",
    "drug_response",
    "uncertain_significance",
    "likely_benign",
    "benign",
]

# ClinVar review_status → star count
REVIEW_STATUS_STARS: dict[str, int] = {
    "practice guideline": 4,
    "reviewed by expert panel": 4,
    "criteria provided, multiple submitters, no conflicts": 3,
    "criteria provided, single submitter": 1,
    "criteria provided, conflicting interpretations": 1,
    "no assertion criteria provided": 0,
}


def _parse_clinvar(hit: dict) -> dict:
    """Extract ClinVar significance, conditions, review stars, allele ID, and HGVS."""
    clinvar = hit.get("clinvar", {})
    if not clinvar:
        return {}

    rcv_list = clinvar.get("rcv", [])
    if isinstance(rcv_list, dict):
        rcv_list = [rcv_list]

    # Pick most severe significance
    best_sig = None
    best_rank = len(CLINVAR_SEVERITY)
    best_stars = 0
    conditions: set[str] = set()

    for rcv in rcv_list:
        sig = rcv.get("clinical_significance", "")
        if isinstance(sig, str):
            sig_lower = sig.lower().replace(" ", "_")
        else:
            continue

        # Track conditions
        cond_list = rcv.get("conditions", [])
        if isinstance(cond_list, dict):
            cond_list = [cond_list]
        for cond in cond_list:
            name = cond.get("name")
            if name and name.lower() != "not provided":
                conditions.add(name)

        # Check severity ranking
        for i, sev in enumerate(CLINVAR_SEVERITY):
            if sev in sig_lower:
                if i < best_rank:
                    best_rank = i
                    best_sig = CLINVAR_SEVERITY[i]
                break

        # Review stars
        review = rcv.get("review_status", "")
        stars = REVIEW_STATUS_STARS.get(review, 0)
        if stars > best_stars:
            best_stars = stars

    # HGVS notation
    hgvs = clinvar.get("hgvs", {})
    hgvs_coding_list = hgvs.get("coding", [])
    hgvs_protein_list = hgvs.get("protein", [])
    if isinstance(hgvs_coding_list, str):
        hgvs_coding_list = [hgvs_coding_list]
    if isinstance(hgvs_protein_list, str):
        hgvs_protein_list = [hgvs_protein_list]

    result: dict = {}
    if best_sig:
        result["clinvar_significance"] = best_sig
        result["clinvar_conditions"] = "; ".join(sorted(conditions)) if conditions else None
        result["clinvar_review_stars"] = best_stars

    allele_id = clinvar.get("allele_id")
    if allele_id is not None:
        result["clinvar_allele_id"] = int(allele_id) if not isinstance(allele_id, int) else allele_id

    if hgvs_coding_list:
        result["hgvs_coding"] = hgvs_coding_list[0][:255]
    if hgvs_protein_list:
        result["hgvs_protein"] = hgvs_protein_list[0][:255]

    return result


def _safe_float(val) -> float | None:
    """Extract a float from a value that might be a list."""
    if val is None:
        return None
    if isinstance(val, list):
        val = val[0] if val else None
    if val is None:
        return None
    try:
        return float(val)
    except (ValueError, TypeError):
        return None


async def fetch_variant_info(rsid: str, client: httpx.AsyncClient) -> dict | None:
    """Fetch variant annotation from MyVariant.info."""
    try:
        resp = await client.get(
            MYVARIANT_API,
            params={
                "q": rsid,
                "fields": (
                    "dbsnp.chrom,dbsnp.hg19,dbsnp.hg38,dbsnp.ref,dbsnp.alt,"
                    "dbsnp.gene.symbol,dbsnp.vartype,"
                    "gnomad_genome.af,"
                    "cadd.phred,cadd.consequence,cadd.sift,cadd.polyphen,"
                    "dbnsfp.revel,"
                    "clinvar.rcv,clinvar.hgvs,clinvar.allele_id"
                ),
                "size": 1,
            },
            timeout=15,
        )
        resp.raise_for_status()
        data = resp.json()
        hits = data.get("hits", [])
        if not hits:
            return None
        hit = hits[0]

        dbsnp = hit.get("dbsnp", {})
        hg19 = dbsnp.get("hg19", {})
        hg38 = dbsnp.get("hg38", {})
        gene_info = dbsnp.get("gene")

        # Gene can be a list or a dict
        gene = None
        if isinstance(gene_info, list) and gene_info:
            gene = gene_info[0].get("symbol")
        elif isinstance(gene_info, dict):
            gene = gene_info.get("symbol")

        # Alt allele can be a list
        alt = dbsnp.get("alt")
        if isinstance(alt, list):
            alt = alt[0] if alt else None

        # Functional class from CADD
        cadd = hit.get("cadd", {})
        consequence = cadd.get("consequence")
        if isinstance(consequence, list):
            consequence = consequence[0] if consequence else None

        # MAF from gnomAD (global)
        gnomad = hit.get("gnomad_genome", {})
        af_data = gnomad.get("af", {})
        if not isinstance(af_data, dict):
            af_data = {}
        maf = af_data.get("af")

        # CADD PHRED score
        cadd_phred = _safe_float(cadd.get("phred"))

        # SIFT (embedded in CADD)
        sift = cadd.get("sift", {})
        if not isinstance(sift, dict):
            sift = {}
        sift_category = sift.get("cat")
        sift_score = _safe_float(sift.get("val"))

        # PolyPhen (embedded in CADD)
        polyphen = cadd.get("polyphen", {})
        if not isinstance(polyphen, dict):
            polyphen = {}
        polyphen_category = polyphen.get("cat")
        polyphen_score = _safe_float(polyphen.get("val"))

        # REVEL (from dbNSFP)
        dbnsfp = hit.get("dbnsfp", {})
        revel = dbnsfp.get("revel", {})
        if not isinstance(revel, dict):
            revel = {}
        revel_score = _safe_float(revel.get("score"))

        # gnomAD population frequencies
        gnomad_afr = _safe_float(af_data.get("af_afr"))
        gnomad_eas = _safe_float(af_data.get("af_eas"))
        gnomad_nfe = _safe_float(af_data.get("af_nfe"))
        gnomad_sas = _safe_float(af_data.get("af_sas"))
        gnomad_amr = _safe_float(af_data.get("af_amr"))
        gnomad_fin = _safe_float(af_data.get("af_fin"))
        gnomad_asj = _safe_float(af_data.get("af_asj"))

        # ClinVar
        clinvar_data = _parse_clinvar(hit)

        result = {
            "chrom": str(dbsnp.get("chrom", "")),
            "position": hg19.get("start"),
            "position_grch38": hg38.get("start"),
            "ref_allele": dbsnp.get("ref"),
            "alt_allele": alt,
            "gene": gene,
            "functional_class": consequence,
            "maf_global": maf,
            # Pathogenicity scores
            "cadd_phred": cadd_phred,
            "sift_category": sift_category,
            "sift_score": sift_score,
            "polyphen_category": polyphen_category,
            "polyphen_score": polyphen_score,
            "revel_score": revel_score,
            # gnomAD population frequencies
            "gnomad_afr": gnomad_afr,
            "gnomad_eas": gnomad_eas,
            "gnomad_nfe": gnomad_nfe,
            "gnomad_sas": gnomad_sas,
            "gnomad_amr": gnomad_amr,
            "gnomad_fin": gnomad_fin,
            "gnomad_asj": gnomad_asj,
        }
        # Merge ClinVar fields
        result.update(clinvar_data)

        return result
    except Exception as e:
        log.warning("MyVariant.info fetch failed for %s: %s", rsid, e)
        return None


# ---------------------------------------------------------------------------
# Database operations
# ---------------------------------------------------------------------------

async def upsert_snp(session: AsyncSession, rsid: str, data: dict) -> None:
    """Upsert a single SNP record."""
    values = {
        "rsid": rsid,
        "chrom": data["chrom"],
        "position": data["position"],
        "position_grch38": data.get("position_grch38"),
        "ref_allele": data["ref_allele"],
        "alt_allele": data["alt_allele"],
        "gene": data["gene"],
        "functional_class": data["functional_class"],
        "maf_global": data["maf_global"],
        # Pathogenicity scores
        "cadd_phred": data.get("cadd_phred"),
        "sift_category": data.get("sift_category"),
        "sift_score": data.get("sift_score"),
        "polyphen_category": data.get("polyphen_category"),
        "polyphen_score": data.get("polyphen_score"),
        "revel_score": data.get("revel_score"),
        # ClinVar
        "clinvar_significance": data.get("clinvar_significance"),
        "clinvar_conditions": data.get("clinvar_conditions"),
        "clinvar_review_stars": data.get("clinvar_review_stars"),
        "clinvar_allele_id": data.get("clinvar_allele_id"),
        # HGVS
        "hgvs_coding": data.get("hgvs_coding"),
        "hgvs_protein": data.get("hgvs_protein"),
        # gnomAD population frequencies
        "gnomad_afr": data.get("gnomad_afr"),
        "gnomad_eas": data.get("gnomad_eas"),
        "gnomad_nfe": data.get("gnomad_nfe"),
        "gnomad_sas": data.get("gnomad_sas"),
        "gnomad_amr": data.get("gnomad_amr"),
        "gnomad_fin": data.get("gnomad_fin"),
        "gnomad_asj": data.get("gnomad_asj"),
    }
    # Remove rsid from update set (it's the PK); skip None values to preserve
    # API-enriched data (CADD, ClinVar, gnomAD pop freqs) on re-seed
    update_set = {k: v for k, v in values.items() if k != "rsid" and v is not None}
    stmt = pg_insert(Snp).values(**values).on_conflict_do_update(
        index_elements=["rsid"],
        set_=update_set,
    )
    await session.execute(stmt)


async def insert_trait_association(
    session: AsyncSession, rsid: str, trait_data: dict
) -> bool:
    """Insert a trait association if it doesn't already exist. Returns True if inserted."""
    # Check for existing
    existing = await session.execute(
        select(SnpTraitAssociation).where(
            SnpTraitAssociation.rsid == rsid,
            SnpTraitAssociation.trait == trait_data["trait"],
        )
    )
    existing_row = existing.scalar_one_or_none()
    if existing_row is not None:
        # Update mutable fields on existing records when seed data has changed
        for field in ("risk_allele", "odds_ratio", "beta", "p_value",
                      "effect_description", "effect_summary", "evidence_level",
                      "source_pmid", "source_title"):
            new_val = trait_data.get(field)
            if new_val is not None and new_val != "" and getattr(existing_row, field, None) != new_val:
                setattr(existing_row, field, new_val)
        return False

    assoc = SnpTraitAssociation(
        rsid=rsid,
        trait=trait_data["trait"],
        risk_allele=trait_data["risk_allele"],
        odds_ratio=trait_data.get("odds_ratio"),
        beta=trait_data.get("beta"),
        p_value=trait_data.get("p_value"),
        effect_description=trait_data.get("effect_description"),
        effect_summary=trait_data.get("effect_summary"),
        evidence_level=trait_data["evidence_level"],
        source_pmid=trait_data.get("source_pmid"),
        source_title=trait_data.get("source_title"),
        extraction_method="manual",
        extracted_at=datetime.now(timezone.utc),
    )
    session.add(assoc)
    return True


# ---------------------------------------------------------------------------
# Main pipeline
# ---------------------------------------------------------------------------

async def run_seed(*, offline: bool = False, dry_run: bool = False) -> None:
    engine = create_async_engine(settings.database_url, pool_size=5)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with httpx.AsyncClient() as client:
        snp_count = 0
        trait_count = 0
        api_hits = 0
        api_misses = 0

        async with async_session() as session:
            # Pre-fetch existing SNPs to skip unnecessary API calls on re-runs
            existing_result = await session.execute(select(Snp.rsid))
            existing_rsids = {row.rsid for row in existing_result}
            skipped = 0

            for entry in SEED_SNPS:
                rsid = entry["rsid"]
                fallback = entry["fallback"]
                traits = entry.get("traits", [])

                # Skip API call for SNPs already in the database
                already_exists = rsid in existing_rsids

                # Fetch from API or use fallback
                variant_data = None
                if not offline and not already_exists:
                    variant_data = await fetch_variant_info(rsid, client)

                if variant_data:
                    api_hits += 1
                    # Fill in missing fields from fallback
                    for key in fallback:
                        if variant_data.get(key) is None:
                            variant_data[key] = fallback[key]
                elif already_exists:
                    skipped += 1
                    variant_data = dict(fallback)
                else:
                    api_misses += 1
                    variant_data = dict(fallback)

                if dry_run:
                    cadd = variant_data.get("cadd_phred")
                    clinvar = variant_data.get("clinvar_significance")
                    pops = "yes" if variant_data.get("gnomad_afr") is not None else "no"
                    status = "EXISTS" if already_exists else "NEW"
                    log.info(
                        "[DRY RUN] [%s] %s — %s (%s:%s %s>%s) MAF=%.3f CADD=%s ClinVar=%s PopFreqs=%s — %d traits",
                        status,
                        rsid,
                        variant_data.get("gene", "?"),
                        variant_data.get("chrom", "?"),
                        variant_data.get("position", "?"),
                        variant_data.get("ref_allele", "?"),
                        variant_data.get("alt_allele", "?"),
                        variant_data.get("maf_global") or 0,
                        f"{cadd:.1f}" if cadd else "—",
                        clinvar or "—",
                        pops,
                        len(traits),
                    )
                    for t in traits:
                        log.info("  - %s (evidence: %s)", t["trait"], t["evidence_level"])
                    continue

                # Always upsert to apply corrected fallback data (position, alleles, MAF);
                # non-None filter in upsert_snp preserves API-enriched fields
                await upsert_snp(session, rsid, variant_data)
                snp_count += 1

                # Insert trait associations (always check — may have new traits)
                for trait_data in traits:
                    inserted = await insert_trait_association(session, rsid, trait_data)
                    if inserted:
                        trait_count += 1

            if not dry_run:
                await session.commit()

        if dry_run:
            log.info("\n[DRY RUN] Would process %d SNPs (%d already exist, %d new)",
                     len(SEED_SNPS), skipped, len(SEED_SNPS) - skipped)
            log.info("API calls needed: %d", len(SEED_SNPS) - skipped)
        else:
            log.info("Processed %d SNPs (%d skipped, %d new) and %d new trait associations",
                     snp_count, skipped, api_hits + api_misses, trait_count)
            log.info("API hits: %d, fallbacks: %d, skipped (existing): %d", api_hits, api_misses, skipped)

    await engine.dispose()


def main():
    parser = argparse.ArgumentParser(description="Seed SNP pages with curated data")
    parser.add_argument("--offline", action="store_true", help="Skip API calls, use fallback values only")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be inserted without writing to DB")
    args = parser.parse_args()

    asyncio.run(run_seed(offline=args.offline, dry_run=args.dry_run))


if __name__ == "__main__":
    main()
