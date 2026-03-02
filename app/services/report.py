"""PDF report generator — produces a downloadable genomic analysis report.

Generates a styled PDF containing:
- Analysis summary (chip type, variant count, ancestry)
- Carrier screening results
- Trait association hits grouped by risk level
- Disclaimers and methodology notes
"""

from __future__ import annotations

import io
from datetime import datetime, timezone
from xml.sax.saxutils import escape

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
)


# ---------- helpers ----------

_DARK = colors.HexColor("#1a1a2e")
_GREY = colors.HexColor("#555555")
_LIGHT_GREY = colors.HexColor("#e0e0e0")
_ROW_ALT = colors.HexColor("#f9f9f9")
_HEADER_BG = colors.HexColor("#f5f5f5")
_HIGHLIGHT_RED = colors.HexColor("#fef2f2")
_HIGHLIGHT_AMBER = colors.HexColor("#fffbeb")


def _status_label(status: str) -> str:
    return status.replace("_", " ").title()


def _base_table_style() -> list:
    return [
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


# ---------- main generator ----------

def generate_report_pdf(
    analysis: dict,
    carrier_status: dict | None,
    trait_hits: list[dict],
) -> bytes:
    """Generate a PDF report and return it as bytes.

    Args:
        analysis: Analysis metadata (chip_type, variant_count, detected_ancestry, etc.)
        carrier_status: Carrier screening result dict (results_json, n_genes_screened, etc.) or None.
        trait_hits: List of trait hit dicts from the results endpoint.

    Returns:
        PDF file content as bytes.
    """
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
        "ReportTitle",
        parent=styles["Title"],
        fontSize=22,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        "SectionHead",
        parent=styles["Heading2"],
        fontSize=14,
        spaceBefore=16,
        spaceAfter=8,
        textColor=_DARK,
    ))
    styles.add(ParagraphStyle(
        "Small",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.grey,
    ))
    styles.add(ParagraphStyle(
        "Disclaimer",
        parent=styles["Normal"],
        fontSize=7.5,
        textColor=colors.grey,
        spaceBefore=12,
        leading=10,
    ))

    story: list = []

    # --- Title ---
    story.append(Paragraph("genewizard.net — Genomic Analysis Report", styles["ReportTitle"]))
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

    # --- Carrier Screening ---
    if carrier_status:
        story.append(Paragraph("Carrier Screening", styles["SectionHead"]))

        n_screened = carrier_status.get("n_genes_screened", 0)
        n_carrier = carrier_status.get("n_carrier_genes", 0)
        n_affected = carrier_status.get("n_affected_flags", 0)

        if n_affected > 0:
            summary_text = (
                f"{n_screened} genes screened — "
                f"<font color='#b91c1c'><b>{n_affected} gene(s) with affected/likely-affected status</b></font>"
            )
            if n_carrier > 0:
                summary_text += f", {n_carrier} carrier gene(s)"
        elif n_carrier > 0:
            summary_text = (
                f"{n_screened} genes screened — "
                f"<font color='#92400e'><b>{n_carrier} carrier gene(s) detected</b></font>"
            )
        else:
            summary_text = f"{n_screened} genes screened — no pathogenic variants detected"

        story.append(Paragraph(summary_text, styles["Normal"]))
        story.append(Spacer(1, 8))

        # Table of carrier/affected genes
        results_json = carrier_status.get("results_json", {})
        flagged_genes = [
            g for g in results_json.values()
            if g.get("status") not in ("not_detected", None)
        ]

        if flagged_genes:
            # Sort: likely_affected first, then carrier, then others
            status_order = {"likely_affected": 0, "potential_compound_het": 1, "carrier": 2}
            flagged_genes.sort(key=lambda g: status_order.get(g["status"], 9))

            cell_style = ParagraphStyle(
                "CarrierCell", parent=styles["Normal"], fontSize=9, leading=11,
            )
            header = ["Gene", "Condition", "Status", "Inheritance", "Severity"]
            rows = [header]
            for g in flagged_genes:
                rows.append([
                    g.get("gene", ""),
                    Paragraph(escape(g.get("condition", "")), cell_style) if len(g.get("condition", "")) > 30 else g.get("condition", ""),
                    _status_label(g.get("status", "")),
                    Paragraph(escape(g.get("inheritance", "")), cell_style),
                    g.get("severity", ""),
                ])

            carrier_table = Table(rows, colWidths=[0.9 * inch, 2.1 * inch, 1.2 * inch, 1.4 * inch, 1.1 * inch])
            style_cmds = _base_table_style()

            # Highlight rows by status
            for i, g in enumerate(flagged_genes, start=1):
                if g.get("status") in ("likely_affected", "potential_compound_het"):
                    style_cmds.append(("BACKGROUND", (0, i), (-1, i), _HIGHLIGHT_RED))
                elif g.get("status") == "carrier":
                    style_cmds.append(("BACKGROUND", (0, i), (-1, i), _HIGHLIGHT_AMBER))

            carrier_table.setStyle(TableStyle(style_cmds))
            story.append(carrier_table)
            story.append(Spacer(1, 8))

            # Variant details for each flagged gene
            for g in flagged_genes:
                variants = g.get("variants_detected", [])
                if not variants:
                    continue

                story.append(Paragraph(
                    f"<b>{escape(g.get('gene', ''))}</b> — detected variants",
                    styles["Normal"],
                ))
                story.append(Spacer(1, 4))

                var_header = ["rsID", "Genotype", "Classification", "HGVS"]
                var_rows = [var_header]
                for v in variants:
                    var_rows.append([
                        v.get("rsid", ""),
                        v.get("genotype", ""),
                        v.get("classification", ""),
                        v.get("hgvs_p", "") or "",
                    ])

                var_table = Table(var_rows, colWidths=[1.2 * inch, 1.0 * inch, 1.8 * inch, 2.3 * inch])
                var_table.setStyle(TableStyle([
                    ("FONTSIZE", (0, 0), (-1, -1), 8),
                    ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                    ("TEXTCOLOR", (0, 0), (-1, 0), _GREY),
                    ("LINEBELOW", (0, 0), (-1, 0), 0.5, colors.HexColor("#cccccc")),
                    ("LINEBELOW", (0, 1), (-1, -1), 0.25, colors.HexColor("#e8e8e8")),
                    ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                    ("TOPPADDING", (0, 0), (-1, -1), 2),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 2),
                ]))
                story.append(var_table)
                story.append(Spacer(1, 6))

        story.append(Spacer(1, 8))

    # --- Important SNPs ---
    if trait_hits:
        story.append(Paragraph("Important SNPs", styles["SectionHead"]))
        story.append(Paragraph(
            "Individual genetic variants linked to specific traits from published research.",
            styles["Normal"],
        ))
        story.append(Spacer(1, 8))

        # Group by risk level for readability
        for level, label in [("increased", "Increased Risk"), ("moderate", "Moderate Risk"), ("typical", "Typical Risk")]:
            level_hits = [h for h in trait_hits if h["risk_level"] == level]
            if not level_hits:
                continue

            story.append(Paragraph(f"{label} ({len(level_hits)})", styles["Heading4"]))
            story.append(Spacer(1, 4))

            trait_header = ["rsID", "Trait", "Genotype", "Evidence"]
            trait_rows = [trait_header]
            for h in level_hits[:50]:  # Cap at 50 per section to keep PDF reasonable
                trait_rows.append([
                    h["rsid"],
                    h["trait"],
                    h["user_genotype"],
                    h["evidence_level"].capitalize(),
                ])

            trait_table = Table(trait_rows, colWidths=[1.3 * inch, 3.0 * inch, 1.0 * inch, 1.0 * inch])
            trait_table.setStyle(TableStyle(_base_table_style()))
            story.append(trait_table)

            if len(level_hits) > 50:
                story.append(Paragraph(
                    f"... and {len(level_hits) - 50} more {level} risk associations.",
                    styles["Small"],
                ))

            story.append(Spacer(1, 8))

    # --- Disclaimers ---
    story.append(Spacer(1, 12))
    story.append(HRFlowable(width="100%", color=_LIGHT_GREY))
    story.append(Paragraph(
        "<b>Important Disclaimers</b><br/><br/>"
        "This report is for informational and educational purposes only and is not medical advice. "
        "Genetic associations reported here reflect published research findings and do not "
        "diagnose or predict disease with certainty. Many factors beyond genetics — including "
        "lifestyle, environment, and family history — influence health outcomes.<br/><br/>"
        "Carrier screening results indicate whether you carry variants associated with "
        "recessive conditions. Carrier status alone does not mean you are affected. "
        "Consult a genetic counselor for family planning implications.<br/><br/>"
        "Please consult a healthcare provider or genetic counselor for medical interpretation "
        "of these results.<br/><br/>"
        "genewizard.net — genewizard.net",
        styles["Disclaimer"],
    ))

    doc.build(story)
    return buf.getvalue()
