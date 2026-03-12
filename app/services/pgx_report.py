"""PGX PDF report generator — produces a downloadable pharmacogenomics report.

Generates a styled PDF containing:
- Summary table split into Drug Metabolism / Drug Response (Gene | Phenotype | Diplotype | Variants Found)
- Detailed gene-by-gene section (description, clinical note, drugs, defining variants, panel SNPs with genotypes)
- Methods section
- Disclaimers
"""

from __future__ import annotations

import io
import logging
from typing import TYPE_CHECKING

from xml.sax.saxutils import escape

if TYPE_CHECKING:
    from app.schemas import PgxRow
from datetime import datetime, timezone

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    HRFlowable,
    PageBreak,
    KeepTogether,
)

log = logging.getLogger(__name__)

# Colour palette
_DARK = colors.HexColor("#1a1a2e")
_GREY = colors.HexColor("#555555")
_LIGHT_GREY = colors.HexColor("#e0e0e0")
_ROW_ALT = colors.HexColor("#f9f9f9")
_HEADER_BG = colors.HexColor("#f5f5f5")
_HIGHLIGHT_PM = colors.HexColor("#fef2f2")   # faint red for PM/Positive
_HIGHLIGHT_IM = colors.HexColor("#fffbeb")   # faint amber for IM

# Phenotypes that warrant highlighting
_ACTIONABLE_KEYWORDS = {
    "poor metabolizer", "ultra-rapid metabolizer", "ultrarapid metabolizer",
    "positive", "deficient", "reduced",
    "high warfarin sensitivity", "warfarin resistance",
    "unfavorable", "poor activity",
    "slow acetylator",
}
_MODERATE_KEYWORDS = {
    "intermediate metabolizer", "intermediate acetylator",
    "intermediate", "decreased function",
}

# Genes whose PGx relevance is drug response rather than drug metabolism.
_DRUG_RESPONSE_GENES = {
    # HLA markers
    "HLA-B_5701", "HLA-B_5801", "HLA-A_3101",
    # Transporters
    "SLCO1B1", "SLC15A2", "SLC22A2", "SLCO1B3", "SLCO2B1", "ABCB1", "ABCG2",
    # Drug targets & response modifiers
    "VKORC1", "MTHFR", "IFNL3", "IFNL4", "CYP2C_cluster",
    # Receptors & signaling
    "OPRM1", "HTR2A", "HTR2C", "DRD2", "ANKK1", "ADRA2A", "ADRB1", "ADRB2",
    "GRK4", "GRK5", "GRIK4",
    # Coagulation factors
    "F5", "F2",
    # Safety / disease genes
    "G6PD", "RYR1", "CACNA1S", "CFTR",
    # DNA repair
    "XPC",
}


def _is_actionable(phenotype: str) -> bool:
    p = phenotype.lower()
    return any(kw in p for kw in _ACTIONABLE_KEYWORDS)


def _is_moderate(phenotype: str) -> bool:
    p = phenotype.lower()
    return any(kw in p for kw in _MODERATE_KEYWORDS)


# Drug → therapeutic area mapping (retained for backward compatibility / tests)
_DRUG_AREAS: dict[str, str] = {
    "amitriptyline": "Behavioral Health", "citalopram": "Behavioral Health",
    "clomipramine": "Behavioral Health", "clozapine": "Behavioral Health",
    "desipramine": "Behavioral Health", "doxepin": "Behavioral Health",
    "escitalopram": "Behavioral Health", "fluvoxamine": "Behavioral Health",
    "imipramine": "Behavioral Health", "nortriptyline": "Behavioral Health",
    "paroxetine": "Behavioral Health", "sertraline": "Behavioral Health",
    "venlafaxine": "Behavioral Health", "duloxetine": "Behavioral Health",
    "aripiprazole": "Behavioral Health", "risperidone": "Behavioral Health",
    "haloperidol": "Behavioral Health", "olanzapine": "Behavioral Health",
    "perphenazine": "Behavioral Health", "thioridazine": "Behavioral Health",
    "atomoxetine": "Behavioral Health", "vortioxetine": "Behavioral Health",
    "brexpiprazole": "Behavioral Health", "iloperidone": "Behavioral Health",
    "diazepam": "Behavioral Health", "trimipramine": "Behavioral Health",
    "fluphenazine": "Behavioral Health", "bupropion": "Behavioral Health",
    "methylphenidate": "Behavioral Health", "guanfacine": "Behavioral Health",
    "amphetamine": "Behavioral Health", "modafinil": "Behavioral Health",
    "phenobarbital": "Behavioral Health", "phenytoin": "Behavioral Health",
    "carbamazepine": "Behavioral Health", "oxcarbazepine": "Behavioral Health",
    "lamotrigine": "Behavioral Health", "valproic acid": "Behavioral Health",
    "lorazepam": "Behavioral Health", "oxazepam": "Behavioral Health",
    "warfarin": "Cardiology", "clopidogrel": "Cardiology",
    "simvastatin": "Cardiology", "atorvastatin": "Cardiology",
    "rosuvastatin": "Cardiology", "lovastatin": "Cardiology",
    "pravastatin": "Cardiology", "fluvastatin": "Cardiology",
    "propafenone": "Cardiology", "metoprolol": "Cardiology",
    "atenolol": "Cardiology", "carvedilol": "Cardiology",
    "nebivolol": "Cardiology", "propranolol": "Cardiology",
    "amlodipine": "Cardiology", "heparin": "Cardiology",
    "enoxaparin": "Cardiology",
    "codeine": "Pain Management", "tramadol": "Pain Management",
    "morphine": "Pain Management", "oxycodone": "Pain Management",
    "hydrocodone": "Pain Management", "fentanyl": "Pain Management",
    "celecoxib": "Pain Management", "ibuprofen": "Pain Management",
    "flurbiprofen": "Pain Management", "meloxicam": "Pain Management",
    "tamoxifen": "Oncology", "fluorouracil": "Oncology",
    "capecitabine": "Oncology", "irinotecan": "Oncology",
    "tegafur": "Oncology", "azathioprine": "Oncology",
    "mercaptopurine": "Oncology", "thioguanine": "Oncology",
    "efavirenz": "Infectious Disease", "nevirapine": "Infectious Disease",
    "abacavir": "Infectious Disease", "voriconazole": "Infectious Disease",
    "isoniazid": "Infectious Disease", "dapsone": "Infectious Disease",
    "primaquine": "Infectious Disease", "chloroquine": "Infectious Disease",
    "tacrolimus": "Immunology", "sirolimus": "Immunology",
    "cyclosporine": "Immunology", "allopurinol": "Immunology",
    "sulfasalazine": "Immunology",
    "omeprazole": "Gastroenterology", "pantoprazole": "Gastroenterology",
    "lansoprazole": "Gastroenterology", "esomeprazole": "Gastroenterology",
    "metformin": "Endocrinology",
    "caffeine": "Other", "theophylline": "Pulmonology",
    "albuterol": "Pulmonology", "salmeterol": "Pulmonology",
    "rasburicase": "Hematology",
}


def _get_drug_area(drug_name: str) -> str:
    """Return therapeutic area for a drug name (case-insensitive match)."""
    return _DRUG_AREAS.get(drug_name.lower(), "Other")


def _is_non_normal(phenotype: str | None) -> bool:
    """Match the frontend isNonNormal() logic."""
    if not phenotype:
        return False
    p = phenotype.lower()
    return "normal" not in p and p != "negative" and p != "typical"


def _coverage_color(tested: int, total: int) -> colors.Color:
    """Return a color reflecting variant coverage quality."""
    if total == 0:
        return colors.HexColor("#dc2626")  # red
    pct = tested / total
    if pct >= 1.0:
        return colors.HexColor("#15803d")  # green
    if pct >= 0.5:
        return colors.HexColor("#ca8a04")  # yellow
    if pct >= 0.25:
        return colors.HexColor("#ea580c")  # orange
    return colors.HexColor("#dc2626")  # red


def generate_pgx_report_pdf(
    analysis: dict,
    pgx_results: list[PgxRow],
    gene_definitions: dict[str, dict],
    drug_annotations: dict[str, list[str]],
    star_allele_rsids: dict[str, list[str]] | None = None,
    defining_variants: dict[str, dict[str, list[dict]]] | None = None,
) -> bytes:
    """Generate a PGX PDF report and return it as bytes.

    Args:
        analysis: Analysis metadata (chip_type, variant_count, etc.)
        pgx_results: List of PGX result dicts (from fetch_pgx_rows).
        gene_definitions: gene -> {description, calling_method}
        drug_annotations: gene -> [drug names]
        star_allele_rsids: gene -> [rsIDs tested] (panel SNPs)
        defining_variants: gene -> {allele: [{rsid, variant_allele}, ...]}

    Returns:
        PDF file content as bytes.
    """
    from app.services.pgx_matcher import PGX_SKIP_GENES

    pgx_results = [r for r in pgx_results if r.get("gene") not in PGX_SKIP_GENES]

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=letter,
        topMargin=0.75 * inch,
        bottomMargin=0.75 * inch,
        leftMargin=0.75 * inch,
        rightMargin=0.75 * inch,
    )

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        "ReportTitle", parent=styles["Title"],
        fontSize=22, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "SectionHead", parent=styles["Heading2"],
        fontSize=14, spaceBefore=16, spaceAfter=8, textColor=_DARK,
    ))
    styles.add(ParagraphStyle(
        "SubSection", parent=styles["Heading3"],
        fontSize=11, spaceBefore=10, spaceAfter=4, textColor=_DARK,
    ))
    styles.add(ParagraphStyle(
        "Small", parent=styles["Normal"],
        fontSize=8, textColor=colors.grey,
    ))
    styles.add(ParagraphStyle(
        "Disclaimer", parent=styles["Normal"],
        fontSize=7.5, textColor=colors.grey, spaceBefore=12, leading=10,
    ))
    styles.add(ParagraphStyle(
        "Body", parent=styles["Normal"],
        fontSize=9, leading=12, spaceBefore=2, spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "GeneHead", parent=styles["Normal"],
        fontSize=11, leading=14, spaceBefore=10, spaceAfter=3,
        textColor=_DARK,
    ))
    cell_style = ParagraphStyle(
        "CellText", parent=styles["Normal"], fontSize=9, leading=11,
    )
    cell_style_small = ParagraphStyle(
        "CellSmall", parent=styles["Normal"], fontSize=8, leading=10,
    )

    story: list = []

    # --- Title ---
    story.append(Paragraph(
        "genewizard.net — Pharmacogenomics Report", styles["ReportTitle"],
    ))
    story.append(Paragraph(
        f"Generated {datetime.now(timezone.utc).strftime('%B %d, %Y at %H:%M UTC')}",
        styles["Small"],
    ))
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", color=_LIGHT_GREY))
    story.append(Spacer(1, 12))

    # --- Analysis Summary ---
    story.append(Paragraph("Analysis Summary", styles["SectionHead"]))
    summary_data = [
        ["Chip Type", analysis.get("chip_type") or "Unknown"],
        ["Variants Analyzed", f"{(analysis.get('variant_count') or 0):,}"],
        ["Genes Tested", str(len(pgx_results))],
    ]
    summary_table = Table(summary_data, colWidths=[1.8 * inch, 4.5 * inch])
    summary_table.setStyle(TableStyle([
        ("FONTSIZE", (0, 0), (-1, -1), 10),
        ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
        ("TEXTCOLOR", (0, 0), (0, -1), _GREY),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
    ]))
    story.append(summary_table)
    story.append(Spacer(1, 16))

    # --- Split into metabolism vs response ---
    metabolism = [r for r in pgx_results if r["gene"] not in _DRUG_RESPONSE_GENES]
    response = [r for r in pgx_results if r["gene"] in _DRUG_RESPONSE_GENES]

    def _build_summary_table(results: list[PgxRow]) -> Table:
        """Build a summary table for a group of results."""
        header = ["Gene", "Phenotype", "Diplotype", "Variants Found"]
        rows = [header]
        for r in results:
            coverage_str = f"{r['n_variants_tested']}/{r['n_variants_total']}"
            rows.append([
                r["gene"],
                Paragraph(escape(r["phenotype"] or "—"), cell_style),
                Paragraph(escape(r["diplotype"] or "—"), cell_style),
                coverage_str,
            ])

        col_widths = [1.2 * inch, 2.6 * inch, 1.6 * inch, 1.0 * inch]
        tbl = Table(rows, colWidths=col_widths)

        cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#333333")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#cccccc")),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e8e8e8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ("ALIGN", (3, 0), (3, -1), "CENTER"),
        ]

        # Highlight rows and color-code coverage
        for idx, r in enumerate(results, start=1):
            phenotype = r.get("phenotype") or ""
            if _is_non_normal(phenotype):
                if _is_actionable(phenotype):
                    cmds.append(("BACKGROUND", (0, idx), (-1, idx), _HIGHLIGHT_PM))
                elif _is_moderate(phenotype):
                    cmds.append(("BACKGROUND", (0, idx), (-1, idx), _HIGHLIGHT_IM))
            # Coverage color
            cov_color = _coverage_color(r["n_variants_tested"], r["n_variants_total"])
            cmds.append(("TEXTCOLOR", (3, idx), (3, idx), cov_color))
            cmds.append(("FONTNAME", (3, idx), (3, idx), "Helvetica-Bold"))

        tbl.setStyle(TableStyle(cmds))
        return tbl

    # =====================================================================
    # PART 1: Summary Tables
    # =====================================================================
    if metabolism:
        story.append(Paragraph("Drug Metabolism", styles["SectionHead"]))
        story.append(Paragraph(
            "Enzymes that break down or activate medications in your body. "
            "Variants can make you metabolize drugs faster or slower than expected.",
            styles["Body"],
        ))
        story.append(Spacer(1, 6))
        story.append(_build_summary_table(metabolism))

    if response:
        story.append(Spacer(1, 12))
        story.append(Paragraph("Drug Response", styles["SectionHead"]))
        story.append(Paragraph(
            "Receptors, transporters, immune markers, and other genes that affect "
            "how you respond to medications.",
            styles["Body"],
        ))
        story.append(Spacer(1, 6))
        story.append(_build_summary_table(response))

    if not pgx_results:
        story.append(Paragraph(
            "No pharmacogenomics results available.", styles["Normal"],
        ))

    # =====================================================================
    # PART 2: Detailed Gene-by-Gene Section
    # =====================================================================
    story.append(PageBreak())
    story.append(Paragraph("Detailed Results", styles["SectionHead"]))

    sorted_results = sorted(pgx_results, key=lambda r: r["gene"])
    star_allele_rsids = star_allele_rsids or {}
    defining_variants = defining_variants or {}

    for r in sorted_results:
        gene = r["gene"]
        gene_def = gene_definitions.get(gene, {})
        phenotype = r.get("phenotype") or "Unknown"
        diplotype = r.get("diplotype") or "—"

        gene_elements: list = []

        # Gene heading with phenotype + diplotype
        gene_elements.append(Paragraph(
            f"<b>{escape(gene)}</b> — {escape(phenotype)}"
            f"  <font size='9'>({escape(diplotype)})</font>",
            styles["GeneHead"],
        ))

        # Gene description
        desc = gene_def.get("description")
        if desc:
            gene_elements.append(Paragraph(escape(desc), styles["Body"]))

        # Clinical note
        note = r.get("clinical_note")
        if note:
            gene_elements.append(Paragraph(
                f"<i>{escape(note)}</i>", styles["Body"],
            ))

        # Activity score + coverage on same line
        info_parts = []
        act = r.get("activity_score")
        if act is not None:
            info_parts.append(f"Activity score: {act}")
        n_tested = r.get("n_variants_tested", 0)
        n_total = r.get("n_variants_total", 0)
        if n_total > 0:
            info_parts.append(f"Variants tested: {n_tested}/{n_total}")
        info_parts.append(f"Calling method: {r.get('calling_method', '—')}")
        if info_parts:
            gene_elements.append(Paragraph(
                " &nbsp;|&nbsp; ".join(info_parts), styles["Body"],
            ))

        # Drugs affected
        drugs = r.get("drugs_affected")
        if drugs:
            gene_elements.append(Paragraph(
                f"<b>Drugs affected:</b> {escape(drugs)}", styles["Body"],
            ))

        # Defining variants (the specific SNPs that led to the function call)
        gene_dv = defining_variants.get(gene)
        if gene_dv:
            dv_parts = []
            for allele, variants in gene_dv.items():
                rsid_strs = [f"{v['rsid']} ({v['variant_allele']})" for v in variants]
                dv_parts.append(f"<b>{escape(allele)}</b>: {', '.join(escape(s) for s in rsid_strs)}")
            gene_elements.append(Paragraph(
                "<b>Defining variants:</b> " + " &nbsp;| &nbsp;".join(dv_parts),
                styles["Body"],
            ))

        # Panel SNPs with genotypes
        panel_rsids = star_allele_rsids.get(gene, [])
        variant_genos = r.get("variant_genotypes") or {}
        if panel_rsids:
            snp_parts = []
            for rsid in sorted(set(panel_rsids)):
                geno = variant_genos.get(rsid)
                if geno:
                    snp_parts.append(f"{rsid} ({geno})")
                else:
                    snp_parts.append(f"{rsid} (—)")
            gene_elements.append(Paragraph(
                f"<b>Panel SNPs ({len(set(panel_rsids))}):</b> "
                + f"<font size='7.5'>{escape(', '.join(snp_parts))}</font>",
                styles["Body"],
            ))

        gene_elements.append(Spacer(1, 4))
        gene_elements.append(HRFlowable(
            width="100%", color=colors.HexColor("#e8e8e8"), thickness=0.25,
        ))

        story.append(KeepTogether(gene_elements))

    # =====================================================================
    # Methods
    # =====================================================================
    story.append(Spacer(1, 16))
    story.append(Paragraph("Methods", styles["SectionHead"]))

    story.append(Paragraph(
        "Gene Wizard performs pharmacogenomic analysis by comparing user genotype data against "
        "curated star allele definitions. Diplotypes are "
        "inferred from detected star alleles using a greedy matching algorithm. Metabolizer "
        "phenotypes are assigned based on CPIC consensus function-pair mappings.",
        styles["Body"],
    ))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<b>Calling Methods:</b><br/>"
        "• <b>Activity Score:</b> Each allele is assigned a numeric activity score; "
        "the sum determines metabolizer phenotype (CPIC thresholds).<br/>"
        "• <b>Simple:</b> Allele functions are mapped directly to phenotype via "
        "consensus function-pair tables.<br/>"
        "• <b>Count:</b> Slow-function alleles are counted to determine acetylator "
        "phenotype (NAT2).<br/>"
        "• <b>Binary:</b> Presence/absence of risk variant (HLA markers, Factor V "
        "Leiden, G6PD).",
        styles["Body"],
    ))

    story.append(Spacer(1, 8))
    story.append(Paragraph(
        "<b>Analytical Limitations:</b><br/>"
        "• CYP2D6 gene deletions (*5) and duplications (*1xN, *2xN) cannot be detected "
        "from SNP array or standard VCF data. Copy number variants require depth-of-coverage "
        "analysis from whole genome sequencing BAM files.<br/>"
        "• Multi-SNP haplotypes (e.g., TPMT *3A) are inferred using a greedy algorithm "
        "that may not resolve all phasing ambiguities in complex cases.<br/>"
        "• Star allele assignments assume the absence of untested variants equals the "
        "reference (*1) allele. Novel or rare variants not in the tested panel may be missed.",
        styles["Body"],
    ))

    # =====================================================================
    # Disclaimers
    # =====================================================================
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", color=_LIGHT_GREY))
    story.append(Paragraph(
        "<b>Important Disclaimers</b><br/><br/>"
        "This report is for informational purposes only and is NOT a clinical "
        "pharmacogenomics test. Results have not been validated in a CLIA-certified "
        "laboratory.<br/><br/>"
        "Results should be confirmed with a clinical-grade pharmacogenomic test before "
        "making any prescribing decisions. Do not alter or discontinue any medication "
        "based solely on this report.<br/><br/>"
        "CYP2D6 gene deletions and duplications cannot be detected from SNP array or "
        "standard VCF data. The absence of a detected variant does not confirm wild-type "
        "status if the variant was not tested.<br/><br/>"
        "Please consult a healthcare provider or pharmacist for medical interpretation "
        "of these results.<br/><br/>"
        "Gene Wizard",
        styles["Disclaimer"],
    ))

    doc.build(story)
    return buf.getvalue()
