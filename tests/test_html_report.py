"""Tests for HTML report generation."""

from app.services.html_report import generate_html_report


# ---------------------------------------------------------------------------
# Fixture helpers
# ---------------------------------------------------------------------------

def _analysis(**overrides):
    base = {
        "chip_type": "23andme_v5",
        "variant_count": 640000,
        "filename": "genome_John_Doe.txt",
        "genome_build": "GRCh37",
        "file_format": "23andme",
        "created_at": "2025-01-15T12:00:00+00:00",
        "pipeline_fast_seconds": 12.3,
        "is_imputed": False,
    }
    base.update(overrides)
    return base


def _ancestry():
    return {
        "superpopulations": {"EUR": 0.85, "AFR": 0.10, "EAS": 0.05},
        "populations": {"CEU": 0.50, "GBR": 0.35, "YRI": 0.10, "CHB": 0.05},
        "n_markers_used": 45000,
        "n_markers_total": 128097,
        "coverage_quality": "high",
        "is_admixed": False,
    }


def _carrier_status(**overrides):
    base = {
        "n_genes_screened": 10,
        "n_carrier_genes": 1,
        "n_affected_flags": 0,
        "results_json": {
            "CFTR": {
                "gene": "CFTR",
                "condition": "Cystic Fibrosis",
                "status": "carrier",
                "inheritance": "AR",
                "severity": "Severe",
                "condition_description": "Inherited disorder affecting lungs and digestive system.",
                "variants_detected": [
                    {
                        "name": "F508del",
                        "rsid": "rs75527207",
                        "genotype": "AG",
                        "classification": "Pathogenic",
                        "hgvs_p": "p.Phe508del",
                    },
                ],
                "carrier_frequencies": {"European": "1 in 25", "African": "1 in 65"},
            },
            "HBB": {
                "gene": "HBB",
                "condition": "Sickle Cell Disease",
                "status": "not_detected",
                "inheritance": "AR",
                "severity": "Severe",
                "variants_detected": [],
            },
        },
    }
    base.update(overrides)
    return base


def _pgx_result(**overrides):
    base = {
        "gene": "CYP2D6",
        "diplotype": "*1/*4",
        "allele1": "*1",
        "allele2": "*4",
        "phenotype": "Intermediate Metabolizer",
        "activity_score": 1.0,
        "confidence": "high",
        "n_variants_tested": 18,
        "n_variants_total": 20,
        "calling_method": "activity_score",
        "drugs_affected": "codeine, tramadol",
        "clinical_note": "Reduced CYP2D6 activity",
        "gene_description": "Major drug metabolizing enzyme.",
        "variant_genotypes": {"rs1234": "AG", "rs5678": "CC"},
        "guidelines": {
            "cpic": [{"drug": "codeine", "recommendation": "Use alternative analgesic", "strength": "strong", "pmid": "12345"}],
            "dpwg": [],
        },
    }
    base.update(overrides)
    return base


def _prs_result(**overrides):
    base = {
        "pgs_id": "PGS000001",
        "trait_name": "Coronary Artery Disease",
        "percentile": 72.5,
        "percentile_lower": 65.0,
        "percentile_upper": 80.0,
        "z_score": 0.62,
        "raw_score": 0.0045,
        "absolute_risk": 0.15,
        "population_risk": 0.10,
        "risk_category": "moderate",
        "ancestry_group_used": "EUR",
        "n_variants_matched": 500,
        "n_variants_total": 600,
        "coverage_quality": "high",
        "reported_auc": 0.81,
        "publication_pmid": "30104374",
        "publication_doi": None,
    }
    base.update(overrides)
    return base


def _trait_hit(**overrides):
    base = {
        "rsid": "rs429358",
        "gene": "APOE",
        "user_genotype": "CT",
        "trait": "Alzheimer's Disease",
        "effect_description": "APOE e4 allele associated with increased Alzheimer's risk.",
        "risk_level": "increased",
        "evidence_level": "high",
    }
    base.update(overrides)
    return base


def _gwas_score(**overrides):
    base = {
        "study_id": "GWAS001",
        "trait": "Type 2 Diabetes",
        "category": "metabolic",
        "citation": "Smith et al. 2023",
        "pmid": "99999",
        "percentile": 65.3,
        "n_variants_matched": 200,
        "n_variants_total": 250,
        "ancestry_group_used": "EUR",
        "raw_score": 0.003,
    }
    base.update(overrides)
    return base


def _clinvar_hit(**overrides):
    base = {
        "rsid": "rs121908757",
        "gene": "BRCA2",
        "user_genotype": "AG",
        "clinvar_significance": "pathogenic",
        "clinvar_conditions": "Hereditary breast and ovarian cancer syndrome",
        "review_stars": 3,
    }
    base.update(overrides)
    return base


def _empty(**kw):
    """Call generate_html_report with all-empty data, with optional overrides."""
    defaults = dict(
        analysis=_analysis(),
        ancestry=None,
        carrier_status=None,
        pgx_results=[],
        pgx_star_allele_rsids={},
        pgx_defining_variants={},
        clinvar_counts={},
        clinvar_hits=[],
        prs_results=[],
        prs_status="not_available",
        gwas_categories={},
        gwas_status="not_available",
        trait_hits=[],
        snpedia_count=0,
    )
    defaults.update(kw)
    return generate_html_report(**defaults)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestHtmlReport:

    def test_generates_valid_html(self):
        html = _empty()
        assert "<!DOCTYPE html>" in html
        assert "genewizard.net" in html
        assert "Analysis Summary" in html

    def test_empty_results_omits_optional_sections(self):
        html = _empty()
        # Check section headings (id="...") are not present — avoids false matches in disclaimers
        assert 'id="ancestry"' not in html
        assert 'id="carrier"' not in html
        assert 'id="pgx"' not in html
        assert 'id="clinvar"' not in html
        assert 'id="prs"' not in html
        assert 'id="gwas"' not in html
        assert 'id="traits"' not in html

    def test_ancestry_bars_rendered(self):
        html = _empty(ancestry=_ancestry())
        assert "Genetic Ancestry" in html
        assert "European" in html
        assert "85.0%" in html
        # Small populations below 2% should be omitted (EAS is 5% so included)
        assert "East Asian" in html

    def test_carrier_screening(self):
        html = _empty(carrier_status=_carrier_status())
        assert "Carrier Screening" in html
        assert "CFTR" in html
        assert "Cystic Fibrosis" in html
        assert "rs75527207" in html
        assert "1 in 25" in html  # carrier frequency

    def test_pgx_metabolism_response_split(self):
        metabolism_gene = _pgx_result(gene="CYP2D6")
        response_gene = _pgx_result(gene="VKORC1", phenotype="High Warfarin Sensitivity")
        html = _empty(pgx_results=[metabolism_gene, response_gene])
        assert "Drug Metabolism" in html
        assert "Drug Response" in html
        assert "CYP2D6" in html
        assert "VKORC1" in html

    def test_pgx_guidelines_shown(self):
        html = _empty(pgx_results=[_pgx_result()])
        assert "CPIC" in html
        assert "codeine" in html
        assert "Use alternative" in html

    def test_pgx_actionable_highlighting(self):
        pm = _pgx_result(phenotype="Poor Metabolizer")
        html = _empty(pgx_results=[pm])
        assert "row-actionable" in html

    def test_clinvar_section(self):
        counts = {"pathogenic": 2, "likely_pathogenic": 1, "benign": 50}
        hits = [_clinvar_hit(), _clinvar_hit(rsid="rs999")]
        html = _empty(clinvar_counts=counts, clinvar_hits=hits)
        assert "ClinVar Annotations" in html
        assert "BRCA2" in html
        assert "★★★☆" in html  # 3 stars

    def test_clinvar_cap_overflow(self):
        counts = {"pathogenic": 150}
        hits = [_clinvar_hit(rsid=f"rs{i}") for i in range(150)]
        html = _empty(clinvar_counts=counts, clinvar_hits=hits)
        assert "50 more actionable" in html

    def test_prs_results_shown(self):
        html = _empty(prs_results=[_prs_result()], prs_status="ready")
        assert "Polygenic Risk Scores" in html
        assert "Coronary Artery Disease" in html
        assert "72.5%" in html
        assert "65.0" in html  # CI lower

    def test_prs_computing_message(self):
        html = _empty(prs_status="computing")
        assert "currently being computed" in html

    def test_gwas_grouped_by_category(self):
        categories = {
            "metabolic": [_gwas_score()],
            "cardiovascular": [_gwas_score(trait="CAD", category="cardiovascular")],
        }
        html = _empty(gwas_categories=categories, gwas_status="ready")
        assert "GWAS Risk Scores" in html
        assert "Metabolic" in html
        assert "Cardiovascular" in html
        assert "Type 2 Diabetes" in html

    def test_gwas_computing_message(self):
        html = _empty(gwas_status="computing")
        assert "currently being computed" in html

    def test_trait_hits_grouped_by_risk(self):
        hits = [
            _trait_hit(rsid="rs1", risk_level="increased"),
            _trait_hit(rsid="rs2", risk_level="moderate"),
            _trait_hit(rsid="rs3", risk_level="typical"),
        ]
        html = _empty(trait_hits=hits)
        assert "Increased Risk" in html
        assert "Moderate Risk" in html
        assert "Typical Risk" in html

    def test_typical_traits_capped(self):
        hits = [_trait_hit(rsid=f"rs{i}", risk_level="typical") for i in range(200)]
        html = _empty(trait_hits=hits)
        assert "100 more typical-risk" in html

    def test_snpedia_count(self):
        html = _empty(snpedia_count=5432)
        assert "SNPedia Variants" in html
        assert "5,432" in html

    def test_xss_escaping(self):
        html = _empty(analysis=_analysis(filename="<script>alert('xss')</script>"))
        assert "<script>" not in html
        assert "&lt;script&gt;" in html

    def test_print_styles_present(self):
        html = _empty()
        assert "@media print" in html

    def test_toc_anchors_match_sections(self):
        """All TOC links should have matching section ids."""
        html = _empty(
            ancestry=_ancestry(),
            carrier_status=_carrier_status(),
            pgx_results=[_pgx_result()],
            clinvar_counts={"pathogenic": 1},
            clinvar_hits=[_clinvar_hit()],
            prs_results=[_prs_result()],
            prs_status="ready",
            gwas_categories={"metabolic": [_gwas_score()]},
            gwas_status="ready",
            trait_hits=[_trait_hit()],
            snpedia_count=100,
        )
        import re
        toc_links = re.findall(r'href="#([^"]+)"', html)
        section_ids = re.findall(r'id="([^"]+)"', html)
        for link in toc_links:
            assert link in section_ids, f"TOC link #{link} has no matching section"

    def test_all_sections_populated(self):
        """Smoke test with all sections having data."""
        html = _empty(
            ancestry=_ancestry(),
            carrier_status=_carrier_status(),
            pgx_results=[_pgx_result()],
            pgx_star_allele_rsids={"CYP2D6": ["rs1234", "rs5678"]},
            pgx_defining_variants={"CYP2D6": {"*4": [{"rsid": "rs3892097", "variant_allele": "A"}]}},
            clinvar_counts={"pathogenic": 1, "benign": 10},
            clinvar_hits=[_clinvar_hit()],
            prs_results=[_prs_result()],
            prs_status="ready",
            gwas_categories={"metabolic": [_gwas_score()]},
            gwas_status="ready",
            trait_hits=[_trait_hit()],
            snpedia_count=5000,
        )
        for section in [
            "Analysis Summary", "Genetic Ancestry", "Carrier Screening",
            "Pharmacogenomics", "ClinVar Annotations", "Polygenic Risk Scores",
            "GWAS Risk Scores", "SNP Trait Associations", "SNPedia Variants",
            "Important Disclaimers",
        ]:
            assert section in html, f"Missing section: {section}"

    def test_variant_count_formatted(self):
        html = _empty(analysis=_analysis(variant_count=640000))
        assert "640,000" in html

    def test_commaformat_filter(self):
        html = _empty(analysis=_analysis(variant_count=1234567))
        assert "1,234,567" in html
