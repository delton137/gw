"""PGX PDF report generator — produces a downloadable pharmacogenomics report.

Generates a styled PDF modeled after the Invitae clinical PGX report containing:
- Results summary table (Gene / Phenotype / Diplotype / Confidence)
- Detailed gene-by-gene interpretations with clinical notes
- Drug-gene interaction table grouped by therapeutic area
- Methods section listing tested variants per gene
- Disclaimers and limitations
"""

from __future__ import annotations

import io
import json
import logging
from typing import TYPE_CHECKING
from xml.sax.saxutils import escape

if TYPE_CHECKING:
    from app.schemas import PgxRow
from datetime import datetime, timezone
from pathlib import Path

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


def _is_actionable(phenotype: str) -> bool:
    p = phenotype.lower()
    return any(kw in p for kw in _ACTIONABLE_KEYWORDS)


def _is_moderate(phenotype: str) -> bool:
    p = phenotype.lower()
    return any(kw in p for kw in _MODERATE_KEYWORDS)


# ---------------------------------------------------------------------------
# Drug → therapeutic area mapping (curated list for common PGX drugs)
# ---------------------------------------------------------------------------
_DRUG_AREAS: dict[str, str] = {
    # Behavioral Health
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
    # Cardiology
    "warfarin": "Cardiology", "clopidogrel": "Cardiology",
    "simvastatin": "Cardiology", "atorvastatin": "Cardiology",
    "rosuvastatin": "Cardiology", "lovastatin": "Cardiology",
    "pravastatin": "Cardiology", "fluvastatin": "Cardiology",
    "propafenone": "Cardiology", "metoprolol": "Cardiology",
    "atenolol": "Cardiology", "carvedilol": "Cardiology",
    "nebivolol": "Cardiology", "propranolol": "Cardiology",
    "amlodipine": "Cardiology", "heparin": "Cardiology",
    "enoxaparin": "Cardiology",
    # Pain / Analgesia
    "codeine": "Pain Management", "tramadol": "Pain Management",
    "morphine": "Pain Management", "oxycodone": "Pain Management",
    "hydrocodone": "Pain Management", "fentanyl": "Pain Management",
    "celecoxib": "Pain Management", "ibuprofen": "Pain Management",
    "flurbiprofen": "Pain Management", "meloxicam": "Pain Management",
    # Oncology
    "tamoxifen": "Oncology", "fluorouracil": "Oncology",
    "capecitabine": "Oncology", "irinotecan": "Oncology",
    "tegafur": "Oncology", "azathioprine": "Oncology",
    "mercaptopurine": "Oncology", "thioguanine": "Oncology",
    # Infectious Disease
    "efavirenz": "Infectious Disease", "nevirapine": "Infectious Disease",
    "abacavir": "Infectious Disease", "voriconazole": "Infectious Disease",
    "isoniazid": "Infectious Disease", "dapsone": "Infectious Disease",
    "primaquine": "Infectious Disease", "chloroquine": "Infectious Disease",
    # Immunology / Rheumatology
    "tacrolimus": "Immunology", "sirolimus": "Immunology",
    "cyclosporine": "Immunology", "allopurinol": "Immunology",
    "sulfasalazine": "Immunology",
    # Gastroenterology
    "omeprazole": "Gastroenterology", "pantoprazole": "Gastroenterology",
    "lansoprazole": "Gastroenterology", "esomeprazole": "Gastroenterology",
    # Endocrinology
    "metformin": "Endocrinology",
    # Other
    "caffeine": "Other", "theophylline": "Pulmonology",
    "albuterol": "Pulmonology", "salmeterol": "Pulmonology",
    "rasburicase": "Hematology",
}


def _get_drug_area(drug_name: str) -> str:
    """Return therapeutic area for a drug name (case-insensitive match)."""
    return _DRUG_AREAS.get(drug_name.lower(), "Other")


def generate_pgx_report_pdf(
    analysis: dict,
    pgx_results: list[PgxRow],
    gene_definitions: dict[str, dict],
    drug_annotations: dict[str, list[str]],
    star_allele_rsids: dict[str, list[str]] | None = None,
) -> bytes:
    """Generate a PGX PDF report and return it as bytes.

    Args:
        analysis: Analysis metadata (chip_type, variant_count, etc.)
        pgx_results: List of PGX result dicts (from results endpoint).
        gene_definitions: gene -> {description, calling_method}
        drug_annotations: gene -> [drug names]
        star_allele_rsids: gene -> [rsIDs tested] (for Methods section)

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
        "InterpretBody", parent=styles["Normal"],
        fontSize=9, leading=12, spaceBefore=2, spaceAfter=6,
    ))

    story: list = []

    # --- Title ---
    story.append(Paragraph(
        "GeneWizard.ai — Pharmacogenomics Report", styles["ReportTitle"],
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

    # --- Results Summary Table ---
    story.append(Paragraph("Pharmacogenomics Results", styles["SectionHead"]))

    if pgx_results:
        cell_style = ParagraphStyle(
            "CellText", parent=styles["Normal"], fontSize=9, leading=11,
        )
        res_header = ["Gene", "Phenotype", "Diplotype", "Confidence"]
        res_rows = [res_header]
        for r in pgx_results:
            res_rows.append([
                r["gene"],
                Paragraph(escape(r["phenotype"] or "—"), cell_style),
                Paragraph(escape(r["diplotype"] or "—"), cell_style),
                (r.get("confidence") or "—").capitalize(),
            ])

        col_widths = [1.2 * inch, 2.8 * inch, 1.8 * inch, 0.9 * inch]
        res_table = Table(res_rows, colWidths=col_widths)

        # Build style commands
        table_cmds = [
            ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, -1), 9),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.HexColor("#333333")),
            ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#cccccc")),
            ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e8e8e8")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]

        # Highlight actionable rows
        for idx, r in enumerate(pgx_results, start=1):
            phenotype = r.get("phenotype") or ""
            if _is_actionable(phenotype):
                table_cmds.append(("BACKGROUND", (0, idx), (-1, idx), _HIGHLIGHT_PM))
            elif _is_moderate(phenotype):
                table_cmds.append(("BACKGROUND", (0, idx), (-1, idx), _HIGHLIGHT_IM))

        res_table.setStyle(TableStyle(table_cmds))
        story.append(res_table)
    else:
        story.append(Paragraph(
            "No pharmacogenomics results available.", styles["Normal"],
        ))

    # --- Detailed Interpretations ---
    story.append(PageBreak())
    story.append(Paragraph("Detailed Interpretations", styles["SectionHead"]))

    sorted_results = sorted(pgx_results, key=lambda r: r["gene"])

    all_pmids: set[str] = set()
    for r in sorted_results:
        gene = r["gene"]
        gene_def = gene_definitions.get(gene, {})

        # Gene heading
        phenotype = r.get("phenotype") or "Unknown"
        diplotype = r.get("diplotype") or "—"
        story.append(Paragraph(
            f"<b>{escape(gene)}</b> — {escape(phenotype)} ({escape(diplotype)})",
            styles["Normal"],
        ))

        # Build interpretation paragraph
        parts = []

        # Clinical note
        note = r.get("clinical_note")
        if note:
            parts.append(escape(note))

        # Gene description from definitions
        desc = gene_def.get("description")
        if desc:
            parts.append(escape(desc))

        # Activity score (for CYP genes)
        act = r.get("activity_score")
        if act is not None:
            parts.append(f"Activity score: {act}")

        # Coverage
        n_tested = r.get("n_variants_tested", 0)
        n_total = r.get("n_variants_total", 0)
        if n_total > 0:
            parts.append(f"Variant coverage: {n_tested}/{n_total} tested")

        # Drugs affected
        drugs = r.get("drugs_affected")
        if drugs:
            parts.append(f"<b>Drugs affected:</b> {escape(drugs)}")

        text_content = ". ".join(p.rstrip(".") for p in parts if p) + "."
        story.append(Paragraph(text_content, styles["InterpretBody"]))

        # CPIC/DPWG guidelines
        guidelines = r.get("guidelines") or {}
        cpic_items = guidelines.get("cpic", [])
        dpwg_items = guidelines.get("dpwg", [])

        if cpic_items:
            cpic_parts = []
            for g in cpic_items[:5]:
                item = f"<i>{escape(g['drug'].capitalize())}</i>: {escape(g['recommendation'])}"
                if g.get("strength"):
                    item += f" ({escape(g['strength'])})"
                pmid = g.get("pmid")
                if pmid:
                    item += f" [PMID {pmid}]"
                    all_pmids.add(pmid)
                cpic_parts.append(item)
            story.append(Paragraph(
                f"<b>CPIC Guideline:</b> " + " | ".join(cpic_parts),
                styles["InterpretBody"],
            ))

        if dpwg_items:
            dpwg_parts = []
            for g in dpwg_items[:5]:
                item = f"<i>{escape(g['drug'].capitalize())}</i>: {escape(g['recommendation'])}"
                pmid = g.get("pmid")
                if pmid:
                    item += f" [PMID {pmid}]"
                    all_pmids.add(pmid)
                dpwg_parts.append(item)
            story.append(Paragraph(
                f"<b>DPWG Guideline:</b> " + " | ".join(dpwg_parts),
                styles["InterpretBody"],
            ))

    # --- Drug-Gene Interaction Table ---
    actionable = [r for r in pgx_results if _is_actionable(r.get("phenotype") or "")]
    if actionable:
        story.append(Spacer(1, 12))
        story.append(Paragraph("Drug-Gene Interactions", styles["SectionHead"]))
        story.append(Paragraph(
            "Medications potentially affected by your pharmacogenomic results. "
            "Consult your healthcare provider before making any changes.",
            styles["Normal"],
        ))
        story.append(Spacer(1, 8))

        # Collect drug-gene pairs (skip guideline annotation titles)
        drug_rows_data: list[tuple[str, str, str, str]] = []  # (area, drug, gene, phenotype)
        for r in actionable:
            gene = r["gene"]
            phenotype = r.get("phenotype") or ""
            gene_drugs = drug_annotations.get(gene, [])
            for drug in gene_drugs:
                if drug.lower().startswith("annotation of "):
                    continue
                area = _get_drug_area(drug)
                drug_rows_data.append((area, drug, gene, phenotype))

        # Sort by area then drug
        drug_rows_data.sort(key=lambda x: (x[0], x[1]))

        if drug_rows_data:
            dg_header = ["Therapeutic Area", "Drug", "Gene", "Phenotype"]
            dg_rows = [dg_header]
            for area, drug, gene, phenotype in drug_rows_data[:80]:  # cap
                dg_rows.append([area, drug.capitalize(), gene, phenotype])

            dg_table = Table(
                dg_rows,
                colWidths=[1.5 * inch, 1.8 * inch, 1.2 * inch, 2.2 * inch],
            )
            dg_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), _HEADER_BG),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#cccccc")),
                ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e8e8e8")),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]))
            story.append(dg_table)

            if len(drug_rows_data) > 80:
                story.append(Paragraph(
                    f"... and {len(drug_rows_data) - 80} more drug-gene interactions.",
                    styles["Small"],
                ))

    # --- Methods ---
    story.append(Spacer(1, 16))
    story.append(Paragraph("Methods", styles["SectionHead"]))

    story.append(Paragraph(
        "GeneWizard performs pharmacogenomic analysis by comparing user genotype data against "
        "curated star allele definitions. Diplotypes are "
        "inferred from detected star alleles using a greedy matching algorithm. Metabolizer "
        "phenotypes are assigned based on CPIC consensus function-pair mappings.",
        styles["InterpretBody"],
    ))

    # Variant list per gene
    if star_allele_rsids:
        story.append(Spacer(1, 8))
        story.append(Paragraph("Variants Tested Per Gene", styles["SubSection"]))
        for gene in sorted(star_allele_rsids.keys()):
            rsids = star_allele_rsids[gene]
            if rsids:
                rsid_str = ", ".join(sorted(set(rsids)))
                story.append(Paragraph(
                    f"<b>{escape(gene)}:</b> {escape(rsid_str)}", styles["InterpretBody"],
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
        styles["InterpretBody"],
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
        styles["InterpretBody"],
    ))

    # --- References ---
    if all_pmids:
        story.append(Spacer(1, 8))
        story.append(Paragraph("References", styles["SubSection"]))
        for pmid in sorted(all_pmids):
            story.append(Paragraph(
                f"• PMID {pmid}: https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                styles["InterpretBody"],
            ))

    # --- Disclaimers ---
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
        "We provide open source CPIC and DPWG guidelines but they may not   "
        "reflect the most recent evidence. Pharmacogenomic interpretation "
        "is an evolving field.<br/><br/>"
        "Please consult a healthcare provider or pharmacist for medical interpretation "
        "of these results.<br/><br/>"
        "GeneWizard",
        styles["Disclaimer"],
    ))

    doc.build(story)
    return buf.getvalue()
