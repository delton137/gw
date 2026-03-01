"""Extract CPIC and DPWG drug-gene guidelines from PharmCAT prescribing_guidance.json.

Parses the PharmCAT data into a flat JSON file suitable for seeding into
GeneWizard's pgx_drug_guidelines table.

Usage:
    python -m scripts.extract_cpic_dpwg [--dry-run]
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

PHARMCAT_GUIDANCE = (
    Path(__file__).parent.parent
    / "existing_tools"
    / "PharmCAT"
    / "src"
    / "main"
    / "resources"
    / "org"
    / "pharmcat"
    / "reporter"
    / "prescribing_guidance.json"
)
OUTPUT_PATH = Path(__file__).parent.parent / "app" / "data" / "cpic_dpwg_guidelines.json"

# Genes where lookupKey uses activity score values instead of phenotype names
ACTIVITY_SCORE_GENES = {"CYP2D6", "CYP2C9", "DPYD"}

# LookupKey values to skip (not actionable recommendations)
SKIP_VALUES = {"n/a", "xN combinations", "Indeterminate", "1511 and 1502"}

# Strip HTML tags
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


def _strip_html(html: str) -> str:
    """Remove HTML tags and normalize whitespace."""
    text = _HTML_TAG_RE.sub(" ", html)
    text = text.replace("&quot;", '"').replace("&amp;", "&").replace("&lt;", "<").replace("&gt;", ">")
    text = _WHITESPACE_RE.sub(" ", text).strip()
    return text


def _parse_activity_score_range(value: str) -> tuple[float, float] | None:
    """Parse an activity score lookup value into (min, max) range.

    Examples:
        "0.0" → (0.0, 0.0)
        "1.5" → (1.5, 1.5)
        "≥3.75" → (3.75, 999.0)
    """
    if value.startswith("≥") or value.startswith(">="):
        num_str = value.lstrip("≥>=")
        try:
            return (float(num_str), 999.0)
        except ValueError:
            return None

    try:
        v = float(value)
        return (v, v)
    except ValueError:
        return None


def _truncate_recommendation(text: str, max_sentences: int = 3) -> str:
    """Truncate recommendation text to max_sentences sentences."""
    # Split on sentence boundaries
    sentences = re.split(r"(?<=[.!?])\s+", text)
    if len(sentences) <= max_sentences:
        return text
    return " ".join(sentences[:max_sentences])


def extract_guidelines() -> list[dict]:
    """Parse PharmCAT prescribing_guidance.json into flat guideline records."""
    if not PHARMCAT_GUIDANCE.exists():
        log.error("PharmCAT prescribing_guidance.json not found at %s", PHARMCAT_GUIDANCE)
        sys.exit(1)

    with open(PHARMCAT_GUIDANCE) as f:
        data = json.load(f)

    guidelines: list[dict] = []
    stats: dict[str, int] = defaultdict(int)
    skipped_fda = 0
    skipped_multi_gene = 0
    skipped_no_rec = 0
    skipped_skip_value = 0
    skipped_no_text = 0

    for entry in data["guidelines"]:
        source = entry["guideline"]["source"]

        # Skip FDA label annotations
        if source == "FDA":
            skipped_fda += 1
            continue

        if source not in ("CPIC", "DPWG"):
            continue

        genes = [g["symbol"] for g in entry["guideline"].get("relatedGenes", [])]
        drugs = [c["name"] for c in entry["guideline"].get("relatedChemicals", [])]
        citations = entry.get("citations", [])
        first_pmid = citations[0].get("pmid") if citations else None

        for rec in entry.get("recommendations", []):
            # Get recommendation text
            html = (rec.get("text") or {}).get("html", "")
            if not html:
                skipped_no_text += 1
                continue

            rec_text = _strip_html(html)
            rec_text = _truncate_recommendation(rec_text)

            # Skip empty or non-actionable
            if not rec_text or rec_text.lower().strip() == "no recommendation":
                skipped_no_rec += 1
                continue

            # Get classification/strength
            classification = rec.get("classification") or {}
            strength = classification.get("term")
            if strength in ("No recommendation", "N/A"):
                # Some have useful text despite "N/A" classification (DPWG)
                # Only skip if text is truly non-actionable
                if "no recommendation" in rec_text.lower() and "does not provide" in rec_text.lower():
                    skipped_no_rec += 1
                    continue

            # Get implications
            implications = rec.get("implications", [])
            implication = None
            if implications:
                imp_text = implications[0]
                # Strip gene prefix like "CYP2D6: "
                if ": " in imp_text:
                    implication = imp_text.split(": ", 1)[1]
                else:
                    implication = imp_text
                if implication == "n/a":
                    implication = None

            alternate_drug = rec.get("alternateDrugAvailable", False)

            # Process lookupKey
            for lk in rec.get("lookupKey", []):
                # Skip multi-gene compound keys
                if len(lk) > 1:
                    skipped_multi_gene += 1
                    continue

                for gene, value in lk.items():
                    if not isinstance(value, str):
                        continue

                    if value in SKIP_VALUES:
                        skipped_skip_value += 1
                        continue

                    # Determine lookup type
                    if gene in ACTIVITY_SCORE_GENES:
                        score_range = _parse_activity_score_range(value)
                        if score_range is None:
                            # Phenotype-name fallback for CYP2C9 which uses both
                            lookup_type = "phenotype"
                            activity_score_min = None
                            activity_score_max = None
                        else:
                            lookup_type = "activity_score"
                            activity_score_min, activity_score_max = score_range
                    else:
                        lookup_type = "phenotype"
                        activity_score_min = None
                        activity_score_max = None

                    for drug in drugs:
                        record = {
                            "source": source,
                            "gene": gene,
                            "drug": drug,
                            "lookup_type": lookup_type,
                            "lookup_value": value,
                            "activity_score_min": activity_score_min,
                            "activity_score_max": activity_score_max,
                            "recommendation": rec_text,
                            "implication": implication,
                            "strength": strength if strength not in ("N/A", "No recommendation") else None,
                            "alternate_drug": alternate_drug,
                            "pmid": first_pmid,
                        }
                        guidelines.append(record)
                        stats[f"{source}:{gene}"] += 1

    log.info(
        "Extracted %d raw guideline records (skipped: FDA=%d, multi-gene=%d, no-rec=%d, skip-val=%d, no-text=%d)",
        len(guidelines),
        skipped_fda,
        skipped_multi_gene,
        skipped_no_rec,
        skipped_skip_value,
        skipped_no_text,
    )

    # Deduplicate: keep one record per (source, gene, drug, lookup_value),
    # preferring the one with the strongest classification.
    strength_rank = {"Strong": 3, "Moderate": 2, "Optional": 1}
    deduped: dict[tuple, dict] = {}
    for g in guidelines:
        key = (g["source"], g["gene"], g["drug"], g["lookup_value"])
        existing = deduped.get(key)
        if existing is None:
            deduped[key] = g
        else:
            # Keep the record with the stronger classification
            new_rank = strength_rank.get(g.get("strength") or "", 0)
            old_rank = strength_rank.get(existing.get("strength") or "", 0)
            if new_rank > old_rank:
                deduped[key] = g
            elif new_rank == old_rank and len(g.get("recommendation", "")) > len(existing.get("recommendation", "")):
                deduped[key] = g  # prefer longer (more detailed) text

    guidelines = list(deduped.values())
    log.info("After deduplication: %d unique guideline records", len(guidelines))

    return guidelines


def main():
    parser = argparse.ArgumentParser(description="Extract CPIC/DPWG guidelines from PharmCAT")
    parser.add_argument("--dry-run", action="store_true", help="Print stats without writing output")
    args = parser.parse_args()

    guidelines = extract_guidelines()

    # Summary
    source_gene_counts: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    source_drug_counts: dict[str, set] = defaultdict(set)
    for g in guidelines:
        source_gene_counts[g["source"]][g["gene"]] += 1
        source_drug_counts[g["source"]].add(g["drug"])

    for source in ("CPIC", "DPWG"):
        genes = source_gene_counts.get(source, {})
        drugs = source_drug_counts.get(source, set())
        print(f"\n{source}: {sum(genes.values())} records across {len(genes)} genes, {len(drugs)} drugs")
        print(f"  {'Gene':>12} {'Records':>8}")
        print(f"  {'-'*22}")
        for gene in sorted(genes.keys()):
            print(f"  {gene:>12} {genes[gene]:>8}")

    print(f"\nTotal: {len(guidelines)} guideline records")

    if args.dry_run:
        log.info("Dry run — not writing output")
        return

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(guidelines, indent=2))
    log.info("Wrote %s (%d records)", OUTPUT_PATH, len(guidelines))


if __name__ == "__main__":
    main()
