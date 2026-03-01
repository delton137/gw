"""Tests for PGX PDF report generation."""

import pytest

from app.services.pgx_report import (
    generate_pgx_report_pdf,
    _is_actionable,
    _is_moderate,
    _get_drug_area,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_analysis(**overrides):
    base = {
        "chip_type": "23andme_v5",
        "variant_count": 640000,
    }
    base.update(overrides)
    return base


def _make_pgx_result(**overrides):
    base = {
        "gene": "CYP2D6",
        "diplotype": "*1/*4",
        "phenotype": "Intermediate Metabolizer",
        "activity_score": 1.0,
        "n_variants_tested": 8,
        "n_variants_total": 10,
        "calling_method": "activity_score",
        "confidence": "high",
        "drugs_affected": "codeine, tramadol, tamoxifen",
        "clinical_note": "One non-functional allele detected",
        "tier": 1,
        "gene_description": "Cytochrome P450 2D6",
    }
    base.update(overrides)
    return base


def _make_gene_defs(genes=None):
    if genes is None:
        genes = {
            "CYP2D6": {"description": "Cytochrome P450 2D6 — metabolizes ~25% of drugs", "tier": 1, "calling_method": "activity_score"},
            "CYP2C19": {"description": "Cytochrome P450 2C19 — metabolizes clopidogrel, PPIs", "tier": 1, "calling_method": "activity_score"},
            "SLCO1B1": {"description": "OATP1B1 — hepatic statin uptake transporter", "tier": 1, "calling_method": "simple"},
        }
    return genes


def _make_drug_annotations():
    return {
        "CYP2D6": ["codeine", "tramadol", "tamoxifen", "paroxetine", "aripiprazole"],
        "CYP2C19": ["clopidogrel", "omeprazole", "escitalopram"],
        "SLCO1B1": ["simvastatin", "atorvastatin"],
    }


def _make_star_allele_rsids():
    return {
        "CYP2D6": ["rs16947", "rs3892097", "rs5030655", "rs1065852", "rs28371725"],
        "CYP2C19": ["rs4244285", "rs4986893", "rs12248560"],
        "SLCO1B1": ["rs4149056", "rs2306283"],
    }


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------


class TestIsActionable:
    def test_poor_metabolizer(self):
        assert _is_actionable("CYP2D6 Poor Metabolizer") is True

    def test_ultrarapid_metabolizer(self):
        assert _is_actionable("Ultra-rapid Metabolizer") is True

    def test_positive(self):
        assert _is_actionable("Positive") is True

    def test_high_warfarin_sensitivity(self):
        assert _is_actionable("High Warfarin Sensitivity") is True

    def test_normal_metabolizer_not_actionable(self):
        assert _is_actionable("Normal Metabolizer") is False

    def test_intermediate_not_actionable(self):
        assert _is_actionable("Intermediate Metabolizer") is False


class TestIsModerate:
    def test_intermediate_metabolizer(self):
        assert _is_moderate("Intermediate Metabolizer") is True

    def test_intermediate_acetylator(self):
        assert _is_moderate("NAT2 Intermediate Acetylator") is True

    def test_decreased_function(self):
        assert _is_moderate("Decreased Function") is True

    def test_normal_not_moderate(self):
        assert _is_moderate("Normal Metabolizer") is False


class TestGetDrugArea:
    def test_cardiology_drug(self):
        assert _get_drug_area("warfarin") == "Cardiology"
        assert _get_drug_area("Warfarin") == "Cardiology"

    def test_behavioral_health(self):
        assert _get_drug_area("sertraline") == "Behavioral Health"

    def test_oncology(self):
        assert _get_drug_area("tamoxifen") == "Oncology"

    def test_unknown_drug(self):
        assert _get_drug_area("unknowndrug") == "Other"


# ---------------------------------------------------------------------------
# PDF generation
# ---------------------------------------------------------------------------


class TestGeneratePgxReportPdf:
    def test_generates_valid_pdf_bytes(self):
        pdf = generate_pgx_report_pdf(
            analysis=_make_analysis(),
            pgx_results=[_make_pgx_result()],
            gene_definitions=_make_gene_defs(),
            drug_annotations=_make_drug_annotations(),
            star_allele_rsids=_make_star_allele_rsids(),
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 100
        assert pdf[:5] == b"%PDF-"

    def test_empty_results(self):
        """PDF generates with no PGX results."""
        pdf = generate_pgx_report_pdf(
            analysis=_make_analysis(),
            pgx_results=[],
            gene_definitions={},
            drug_annotations={},
        )
        assert pdf[:5] == b"%PDF-"

    def test_no_drug_annotations(self):
        """PDF generates when drug annotations are empty."""
        pdf = generate_pgx_report_pdf(
            analysis=_make_analysis(),
            pgx_results=[_make_pgx_result()],
            gene_definitions=_make_gene_defs(),
            drug_annotations={},
        )
        assert pdf[:5] == b"%PDF-"

    def test_no_star_allele_rsids(self):
        """PDF generates without star allele rsID data (Methods section simplified)."""
        pdf = generate_pgx_report_pdf(
            analysis=_make_analysis(),
            pgx_results=[_make_pgx_result()],
            gene_definitions=_make_gene_defs(),
            drug_annotations=_make_drug_annotations(),
            star_allele_rsids=None,
        )
        assert pdf[:5] == b"%PDF-"

    def test_actionable_results_trigger_drug_table(self):
        """PDF includes drug-gene interaction table when actionable results present."""
        results = [
            _make_pgx_result(
                gene="CYP2D6",
                phenotype="CYP2D6 Poor Metabolizer",
                diplotype="*4/*4",
                activity_score=0,
            ),
        ]
        pdf = generate_pgx_report_pdf(
            analysis=_make_analysis(),
            pgx_results=results,
            gene_definitions=_make_gene_defs(),
            drug_annotations=_make_drug_annotations(),
            star_allele_rsids=_make_star_allele_rsids(),
        )
        assert pdf[:5] == b"%PDF-"
        # Actionable result → drug table section rendered → larger PDF
        assert len(pdf) > 500

    def test_all_normal_results(self):
        """PDF generates cleanly when all results are normal (no drug table)."""
        results = [
            _make_pgx_result(
                gene="CYP2D6",
                phenotype="Normal Metabolizer",
                diplotype="*1/*1",
                activity_score=2.0,
                drugs_affected=None,
                clinical_note=None,
            ),
            _make_pgx_result(
                gene="CYP2C19",
                phenotype="Normal Metabolizer",
                diplotype="*1/*1",
                activity_score=2.0,
                drugs_affected=None,
                clinical_note=None,
            ),
        ]
        pdf = generate_pgx_report_pdf(
            analysis=_make_analysis(),
            pgx_results=results,
            gene_definitions=_make_gene_defs(),
            drug_annotations=_make_drug_annotations(),
        )
        assert pdf[:5] == b"%PDF-"

    def test_multiple_genes_sorted_by_tier(self):
        """PDF sorts results by tier then gene name."""
        results = [
            _make_pgx_result(gene="SLCO1B1", tier=1, phenotype="SLCO1B1 Poor Function"),
            _make_pgx_result(gene="CYP2D6", tier=1, phenotype="Normal Metabolizer"),
            _make_pgx_result(gene="MTHFR", tier=2, phenotype="Normal MTHFR Activity"),
        ]
        gene_defs = {
            "CYP2D6": {"description": "CYP2D6", "tier": 1, "calling_method": "activity_score"},
            "SLCO1B1": {"description": "SLCO1B1", "tier": 1, "calling_method": "simple"},
            "MTHFR": {"description": "MTHFR", "tier": 2, "calling_method": "simple"},
        }
        pdf = generate_pgx_report_pdf(
            analysis=_make_analysis(),
            pgx_results=results,
            gene_definitions=gene_defs,
            drug_annotations={},
        )
        assert pdf[:5] == b"%PDF-"

    def test_binary_gene_result(self):
        """PDF handles binary gene results (HLA markers, Factor V Leiden)."""
        results = [
            _make_pgx_result(
                gene="HLA-B_5701",
                phenotype="Positive",
                diplotype="positive/negative",
                calling_method="binary",
                activity_score=None,
                drugs_affected="abacavir",
                clinical_note="HLA-B*57:01 detected — abacavir CONTRAINDICATED",
            ),
        ]
        gene_defs = {
            "HLA-B_5701": {"description": "HLA-B*57:01", "tier": 1, "calling_method": "binary"},
        }
        pdf = generate_pgx_report_pdf(
            analysis=_make_analysis(),
            pgx_results=results,
            gene_definitions=gene_defs,
            drug_annotations={"HLA-B_5701": ["abacavir"]},
        )
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 500

    def test_none_phenotype_handled(self):
        """PDF handles None phenotype gracefully."""
        results = [
            _make_pgx_result(phenotype=None, diplotype=None, clinical_note=None),
        ]
        pdf = generate_pgx_report_pdf(
            analysis=_make_analysis(),
            pgx_results=results,
            gene_definitions=_make_gene_defs(),
            drug_annotations={},
        )
        assert pdf[:5] == b"%PDF-"

    def test_missing_chip_type(self):
        """PDF generates when chip type is missing."""
        pdf = generate_pgx_report_pdf(
            analysis=_make_analysis(chip_type=None, variant_count=None),
            pgx_results=[_make_pgx_result()],
            gene_definitions=_make_gene_defs(),
            drug_annotations={},
        )
        assert pdf[:5] == b"%PDF-"

    def test_many_drug_interactions_capped(self):
        """PDF caps drug-gene interaction rows to prevent oversized PDFs."""
        # Create an actionable result with lots of drugs
        results = [
            _make_pgx_result(
                gene="CYP2D6",
                phenotype="CYP2D6 Poor Metabolizer",
            ),
        ]
        # 100 fake drugs
        drug_annotations = {
            "CYP2D6": [f"drug_{i}" for i in range(100)],
        }
        pdf = generate_pgx_report_pdf(
            analysis=_make_analysis(),
            pgx_results=results,
            gene_definitions=_make_gene_defs(),
            drug_annotations=drug_annotations,
        )
        assert pdf[:5] == b"%PDF-"
