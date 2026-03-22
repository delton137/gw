"""HTML report generator — produces a self-contained downloadable HTML report.

Generates a styled HTML file containing all analysis results:
analysis summary, genetic ancestry, carrier screening, pharmacogenomics
(with CPIC/DPWG guidelines), ClinVar annotations, polygenic risk scores,
GWAS risk scores, SNP trait associations, and SNPedia variant summary.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from jinja2 import Environment, FileSystemLoader, select_autoescape

from app.services.pgx_report import (
    _ACTIONABLE_KEYWORDS,
    _DRUG_RESPONSE_GENES,
    _MODERATE_KEYWORDS,
)

_TEMPLATE_DIR = Path(__file__).resolve().parent.parent / "templates"
_env = Environment(
    loader=FileSystemLoader(str(_TEMPLATE_DIR)),
    autoescape=select_autoescape(["html"]),
)

# Superpopulation display metadata
SUPERPOP_NAMES = {
    "AFR": "African",
    "EUR": "European",
    "EAS": "East Asian",
    "SAS": "South Asian",
    "AMR": "Americas / Latino",
}

SUPERPOP_COLORS = {
    "AFR": "#10b981",
    "EUR": "#f59e0b",
    "EAS": "#8b5cf6",
    "SAS": "#f43f5e",
    "AMR": "#0ea5e9",
}

# Max rows for large sections
_CLINVAR_ACTIONABLE_CAP = 100
_TYPICAL_TRAIT_CAP = 100


def _commaformat(value: Any) -> str:
    """Format number with comma thousands separator."""
    try:
        return f"{int(value):,}"
    except (ValueError, TypeError):
        return str(value)


_env.filters["commaformat"] = _commaformat


def _annotate_pgx_highlight(results: list[dict]) -> None:
    """Set _highlight on each PGx result for row color coding."""
    for r in results:
        p = (r.get("phenotype") or "").lower()
        if any(kw in p for kw in _ACTIONABLE_KEYWORDS):
            r["_highlight"] = "actionable"
        elif any(kw in p for kw in _MODERATE_KEYWORDS):
            r["_highlight"] = "moderate"
        else:
            r["_highlight"] = "normal"


def generate_html_report(
    analysis: dict,
    ancestry: dict | None,
    carrier_status: dict | None,
    pgx_results: list[dict],
    pgx_star_allele_rsids: dict[str, list[str]],
    pgx_defining_variants: dict[str, dict[str, list[dict]]],
    clinvar_counts: dict[str, int],
    clinvar_hits: list[dict],
    prs_results: list[dict],
    prs_status: str,
    gwas_categories: dict[str, list[dict]],
    gwas_status: str,
    trait_hits: list[dict],
    snpedia_count: int,
) -> str:
    """Generate a comprehensive HTML report and return it as a string.

    All arguments are plain dicts/lists — the route handler is responsible
    for database queries.  This function is pure and side-effect-free.
    """
    template = _env.get_template("comprehensive_report.html")

    # Ancestry bars — sorted superpopulations >= 2%
    ancestry_bars = None
    if ancestry and "superpopulations" in ancestry:
        superpops = ancestry["superpopulations"]
        ancestry_bars = sorted(
            [(code, frac) for code, frac in superpops.items() if frac >= 0.02],
            key=lambda x: x[1],
            reverse=True,
        )

    # PGx: annotate highlight + split metabolism vs response
    _annotate_pgx_highlight(pgx_results)
    pgx_metabolism = [r for r in pgx_results if r["gene"] not in _DRUG_RESPONSE_GENES]
    pgx_response = [r for r in pgx_results if r["gene"] in _DRUG_RESPONSE_GENES]

    # Trait hits: group by risk level
    trait_groups: dict[str, list[dict]] = {"increased": [], "moderate": [], "typical": []}
    for hit in trait_hits:
        level = hit.get("risk_level", "typical")
        trait_groups.setdefault(level, []).append(hit)

    typical_total = len(trait_groups.get("typical", []))
    typical_capped = trait_groups.get("typical", [])[:_TYPICAL_TRAIT_CAP]
    typical_overflow = max(0, typical_total - _TYPICAL_TRAIT_CAP)

    # ClinVar: cap actionable hits
    clinvar_overflow = max(0, len(clinvar_hits) - _CLINVAR_ACTIONABLE_CAP)
    clinvar_capped = clinvar_hits[:_CLINVAR_ACTIONABLE_CAP]
    clinvar_total = sum(clinvar_counts.values())

    return template.render(
        generated_at=datetime.now(timezone.utc).strftime("%B %d, %Y at %H:%M UTC"),
        analysis=analysis,
        ancestry=ancestry,
        ancestry_bars=ancestry_bars,
        superpop_names=SUPERPOP_NAMES,
        superpop_colors=SUPERPOP_COLORS,
        carrier_status=carrier_status,
        pgx_metabolism=pgx_metabolism,
        pgx_response=pgx_response,
        pgx_star_allele_rsids=pgx_star_allele_rsids,
        pgx_defining_variants=pgx_defining_variants,
        clinvar_counts=clinvar_counts,
        clinvar_hits=clinvar_capped,
        clinvar_overflow=clinvar_overflow,
        clinvar_total=clinvar_total,
        prs_results=prs_results,
        prs_status=prs_status,
        gwas_categories=gwas_categories,
        gwas_status=gwas_status,
        trait_increased=trait_groups.get("increased", []),
        trait_moderate=trait_groups.get("moderate", []),
        trait_typical=typical_capped,
        typical_overflow=typical_overflow,
        snpedia_count=snpedia_count,
    )
