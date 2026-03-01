"""Tests for PDF report generation."""

import pytest

from app.services.report import generate_report_pdf


class TestGenerateReportPdf:
    def _make_analysis(self, **overrides):
        base = {
            "chip_type": "23andme_v5",
            "variant_count": 640000,
            "detected_ancestry": {"EUR": 0.85, "AFR": 0.10, "EAS": 0.05},
            "ancestry_method": "auto",
            "ancestry_confidence": 0.85,
            "created_at": "2025-01-15T12:00:00+00:00",
        }
        base.update(overrides)
        return base

    def _make_hit(self, **overrides):
        base = {
            "rsid": "rs429358",
            "user_genotype": "CT",
            "trait": "Alzheimer's Disease",
            "effect_description": "Increased risk",
            "risk_level": "moderate",
            "evidence_level": "high",
        }
        base.update(overrides)
        return base

    def _make_carrier_status(self, **overrides):
        base = {
            "n_genes_screened": 42,
            "n_carrier_genes": 1,
            "n_affected_flags": 0,
            "results_json": {
                "CFTR": {
                    "gene": "CFTR",
                    "condition": "Cystic Fibrosis",
                    "inheritance": "AR",
                    "severity": "Severe",
                    "status": "carrier",
                    "variants_detected": [
                        {
                            "rsid": "rs75527207",
                            "name": "F508del",
                            "genotype": "AG",
                            "pathogenic_allele": "G",
                            "pathogenic_allele_count": 1,
                            "classification": "Pathogenic",
                            "hgvs_p": "p.Phe508del",
                            "population_frequency": "0.02",
                        }
                    ],
                    "total_variants_screened": 5,
                    "total_pathogenic_alleles": 1,
                    "carrier_frequencies": {"EUR": "1 in 25"},
                    "condition_description": "Severe lung and digestive disease",
                    "treatment_summary": "Symptomatic management",
                    "penetrance_note": "",
                    "key_pmids": [],
                    "limitations": "",
                    "clinical_note": "",
                },
                "HBB": {
                    "gene": "HBB",
                    "condition": "Sickle Cell Disease",
                    "inheritance": "AR",
                    "severity": "Severe",
                    "status": "not_detected",
                    "variants_detected": [],
                    "total_variants_screened": 3,
                    "total_pathogenic_alleles": 0,
                    "carrier_frequencies": {},
                    "condition_description": "",
                    "treatment_summary": "",
                    "penetrance_note": "",
                    "key_pmids": [],
                    "limitations": "",
                    "clinical_note": "",
                },
            },
        }
        base.update(overrides)
        return base

    def test_generates_valid_pdf_bytes(self):
        pdf = generate_report_pdf(
            self._make_analysis(), None, [self._make_hit()]
        )
        assert isinstance(pdf, bytes)
        assert len(pdf) > 100
        assert pdf[:5] == b"%PDF-"

    def test_empty_results(self):
        """PDF should still generate with no data."""
        pdf = generate_report_pdf(self._make_analysis(), None, [])
        assert pdf[:5] == b"%PDF-"

    def test_no_ancestry(self):
        """PDF generates when ancestry is not detected."""
        pdf = generate_report_pdf(
            self._make_analysis(detected_ancestry=None, ancestry_method="manual"),
            None,
            [],
        )
        assert pdf[:5] == b"%PDF-"

    def test_with_carrier_status(self):
        """PDF includes carrier screening section."""
        pdf = generate_report_pdf(
            self._make_analysis(), self._make_carrier_status(), []
        )
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 500

    def test_with_carrier_status_affected(self):
        """PDF handles affected/likely_affected carrier status."""
        cs = self._make_carrier_status(
            n_affected_flags=1,
            n_carrier_genes=1,
        )
        cs["results_json"]["CFTR"]["status"] = "likely_affected"
        cs["results_json"]["CFTR"]["variants_detected"].append({
            "rsid": "rs121908769",
            "name": "G551D",
            "genotype": "AA",
            "pathogenic_allele": "A",
            "pathogenic_allele_count": 2,
            "classification": "Pathogenic",
            "hgvs_p": "p.Gly551Asp",
            "population_frequency": "0.003",
        })
        pdf = generate_report_pdf(self._make_analysis(), cs, [])
        assert pdf[:5] == b"%PDF-"

    def test_with_carrier_status_no_findings(self):
        """PDF handles carrier screening with no findings."""
        cs = self._make_carrier_status(
            n_carrier_genes=0,
            n_affected_flags=0,
            results_json={
                "HBB": {
                    "gene": "HBB",
                    "condition": "Sickle Cell Disease",
                    "inheritance": "AR",
                    "severity": "Severe",
                    "status": "not_detected",
                    "variants_detected": [],
                    "total_variants_screened": 3,
                    "total_pathogenic_alleles": 0,
                    "carrier_frequencies": {},
                    "condition_description": "",
                    "treatment_summary": "",
                    "penetrance_note": "",
                    "key_pmids": [],
                    "limitations": "",
                    "clinical_note": "",
                },
            },
        )
        pdf = generate_report_pdf(self._make_analysis(), cs, [])
        assert pdf[:5] == b"%PDF-"

    def test_all_sections(self):
        """PDF generates with all sections populated."""
        hits = [
            self._make_hit(rsid="rs1", risk_level="increased"),
            self._make_hit(rsid="rs2", risk_level="moderate"),
            self._make_hit(rsid="rs3", risk_level="typical"),
        ]
        pdf = generate_report_pdf(
            self._make_analysis(),
            self._make_carrier_status(),
            hits,
        )
        assert pdf[:5] == b"%PDF-"
        assert len(pdf) > 1000

    def test_many_trait_hits_capped(self):
        """PDF caps trait hits per section at 50 to keep file reasonable."""
        hits = [self._make_hit(rsid=f"rs{i}", risk_level="increased") for i in range(100)]
        pdf = generate_report_pdf(self._make_analysis(), None, hits)
        assert pdf[:5] == b"%PDF-"

    def test_carrier_long_inheritance_text(self):
        """PDF handles long inheritance text without column overflow."""
        cs = self._make_carrier_status()
        cs["results_json"]["SERPINA1"] = {
            "gene": "SERPINA1",
            "condition": "Alpha-1 Antitrypsin Deficiency",
            "inheritance": "autosomal_codominant",
            "severity": "variable",
            "status": "potential_compound_het",
            "variants_detected": [
                {"rsid": "rs28929474", "genotype": "CT", "classification": "pathogenic", "hgvs_p": "p.Glu342Lys"},
            ],
            "total_variants_screened": 2,
            "total_pathogenic_alleles": 1,
            "carrier_frequencies": {},
            "condition_description": "",
            "treatment_summary": "",
            "penetrance_note": "",
            "key_pmids": [],
            "limitations": "",
            "clinical_note": "",
        }
        cs["n_affected_flags"] = 1
        pdf = generate_report_pdf(self._make_analysis(), cs, [])
        assert pdf[:5] == b"%PDF-"
