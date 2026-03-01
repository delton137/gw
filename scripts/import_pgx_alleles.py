"""Import star allele definitions from Stargazer v2.0.3 database.

Parses Stargazer's TSV files, maps GRCh38 positions to rsIDs, and generates
app/data/stargazer_alleles.json for use by seed_pgx_definitions.py.

Usage:
    python -m scripts.import_stargazer_alleles [--dry-run]
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import sys
from collections import defaultdict
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

STARGAZER_DIR = Path(__file__).parent.parent / "stargazer-grc38-2.0.3" / "stargazer"
OUTPUT_PATH = Path(__file__).parent.parent / "app" / "data" / "stargazer_alleles.json"

# ---------------------------------------------------------------------------
# Stargazer phenotyper category → our calling_method mapping
# From stargazer/phenotyper.py ptcallers dict
# ---------------------------------------------------------------------------

PHENOTYPE_GENES = {
    "abcb1", "cacna1s", "cftr", "g6pd", "gstm1", "gstp1", "gstt1",
    "ifnl3", "nat1", "nat2", "por", "ptgis", "ryr1", "sult1a1",
    "tbxas1", "ugt1a4", "ugt2b7", "ugt2b15", "ugt2b17", "vkorc1", "xpc",
}

METABOLIZER_GENES = {
    "cyp1a1", "cyp1a2", "cyp1b1", "cyp2a6", "cyp2a13", "cyp2b6", "cyp2c8",
    "cyp2c9", "cyp2c19", "cyp2d6", "cyp2e1", "cyp2f1", "cyp2j2", "cyp2r1",
    "cyp2s1", "cyp2w1", "cyp3a4", "cyp3a5", "cyp3a7", "cyp3a43",
    "cyp4a11", "cyp4a22", "cyp4b1", "cyp4f2", "cyp17a1", "cyp19a1",
    "cyp26a1", "dpyd", "nudt15", "tpmt", "ugt1a1", "slc15a2", "slc22a2",
}

TRANSPORTER_GENES = {"slco1b1", "slco1b3", "slco2b1"}

# Stargazer phenotype field → our function vocabulary
PHENOTYPE_TO_FUNCTION = {
    "normal_function": "normal_function",
    "no_function": "no_function",
    "decreased_function": "decreased_function",
    "increased_function": "increased_function",
    "unknown_function": "uncertain_function",
    "uncertain_function": "uncertain_function",
}


def _map_phenotype(phenotype: str) -> str:
    """Map Stargazer's phenotype field to our function vocabulary."""
    if phenotype in PHENOTYPE_TO_FUNCTION:
        return PHENOTYPE_TO_FUNCTION[phenotype]
    # CFTR uses Class_I, Class_II, etc. — treat as uncertain
    if phenotype.startswith("Class_") or "&" in phenotype:
        return "uncertain_function"
    return "uncertain_function"


def _determine_calling_method(gene_lower: str) -> str:
    """Determine calling method based on Stargazer's phenotyper category."""
    if gene_lower in METABOLIZER_GENES:
        return "activity_score"
    if gene_lower in TRANSPORTER_GENES:
        return "activity_score"
    if gene_lower in PHENOTYPE_GENES:
        return "simple"
    return "simple"


def _parse_allele_change(change: str) -> tuple[str, str]:
    """Parse '42126611:C>G' → ('C', 'G') i.e. (ref, alt).

    Also handles indels like '117559591:TCTT>T'.
    """
    _, alleles = change.split(":")
    ref, alt = alleles.split(">")
    return ref, alt


def build_snp_mapping() -> tuple[dict, dict]:
    """Parse snp_table.tsv → (gene,pos)→rsid mapping and variant info.

    Returns:
        (pos_to_rsid, variant_info)
        pos_to_rsid: {(gene, grc38_pos): rsid}
        variant_info: {rsid: {gene, chrom, position, ref_allele, alt_allele, ...}}
    """
    snp_path = STARGAZER_DIR / "snp_table.tsv"
    if not snp_path.exists():
        log.error("snp_table.tsv not found at %s", snp_path)
        sys.exit(1)

    pos_to_rsid: dict[tuple[str, str], str] = {}
    variant_info: dict[str, dict] = {}

    with open(snp_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            gene = row["gene"]
            pos = row["grc38_pos"]
            rsid = row["rs_id"]

            if rsid and rsid != ".":
                pos_to_rsid[(gene, pos)] = rsid

                # Store variant info for SNP page seeding (keep first occurrence per rsid)
                if rsid not in variant_info:
                    variant_info[rsid] = {
                        "rsid": rsid,
                        "gene": gene.upper(),
                        "chrom": "",  # filled from gene_table
                        "position": int(pos),
                        "ref_allele": row["wt_allele"],
                        "alt_allele": row["var_allele"],
                        "functional_class": row.get("sequence_ontology", ""),
                    }

    log.info("Loaded %d position→rsID mappings from snp_table.tsv", len(pos_to_rsid))
    return pos_to_rsid, variant_info


def build_gene_metadata() -> dict[str, dict]:
    """Parse gene_table.tsv → gene metadata."""
    gene_path = STARGAZER_DIR / "gene_table.tsv"
    if not gene_path.exists():
        log.error("gene_table.tsv not found at %s", gene_path)
        sys.exit(1)

    genes: dict[str, dict] = {}
    with open(gene_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            gene_lower = row["name"]
            gene_type = row["type"]
            if gene_type != "target":
                continue  # Skip paralogs and control genes

            chrom = row["chr"].replace("chr", "")
            genes[gene_lower] = {
                "gene": gene_lower.upper(),
                "chromosome": chrom,
                "transcript": row["transcript"],
                "strand": row["strand"],
                "calling_method": _determine_calling_method(gene_lower),
            }

    log.info("Loaded %d target gene definitions from gene_table.tsv", len(genes))
    return genes


def build_star_alleles(
    pos_to_rsid: dict[tuple[str, str], str],
    gene_meta: dict[str, dict],
) -> tuple[list[dict], dict[str, int]]:
    """Parse star_table.tsv → allele definitions with rsIDs.

    Returns:
        (alleles, stats)
        alleles: list of allele definition dicts
        stats: per-gene count of mapped alleles
    """
    star_path = STARGAZER_DIR / "star_table.tsv"
    if not star_path.exists():
        log.error("star_table.tsv not found at %s", star_path)
        sys.exit(1)

    alleles: list[dict] = []
    stats: dict[str, int] = defaultdict(int)
    skipped_sv = 0
    skipped_ref = 0
    skipped_no_rsid = 0
    skipped_long_allele = 0
    total_rows = 0

    with open(star_path) as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            total_rows += 1
            gene = row["gene"]
            sv = row["sv"]
            core = row["grc38_core"]
            name = row["name"]
            phenotype = row["phenotype"]
            score_str = row["score"]

            # Skip structural variant alleles
            if sv and sv != ".":
                skipped_sv += 1
                continue

            # Skip reference (*1) and empty alleles
            if core in ("ref", "."):
                skipped_ref += 1
                continue

            # Skip genes not in our target list
            if gene not in gene_meta:
                continue

            # Parse activity score
            try:
                score = float(score_str)
            except (ValueError, TypeError):
                score = None
            if score is not None and score <= -100:
                score = None  # -100 = unknown in Stargazer

            # Map function
            function = _map_phenotype(phenotype)

            # Parse core variants and look up rsIDs
            variants = core.split(",")
            variant_rsids: list[tuple[str, str, str]] = []  # (rsid, ref, alt)
            all_mapped = True

            for v in variants:
                pos = v.split(":")[0]
                ref, alt = _parse_allele_change(v)
                rsid = pos_to_rsid.get((gene, pos))

                if not rsid:
                    all_mapped = False
                    break

                variant_rsids.append((rsid, ref, alt))

            if not all_mapped:
                skipped_no_rsid += 1
                continue

            # Skip alleles with very long variant alleles (indels/repeats — not on SNP arrays)
            if any(len(alt) > 10 for _, _, alt in variant_rsids):
                skipped_long_allele += 1
                continue

            # Generate allele definition rows (one per variant)
            gene_upper = gene_meta[gene]["gene"]
            for rsid, ref_allele, alt_allele in variant_rsids:
                alleles.append({
                    "gene": gene_upper,
                    "star_allele": name,
                    "rsid": rsid,
                    "variant_allele": alt_allele,
                    "function": function,
                    "activity_score": score,
                    "source": "Stargazer",
                })

            stats[gene_upper] += 1

    log.info(
        "Parsed %d star alleles: %d mapped, %d skipped (SV=%d, ref=%d, no_rsid=%d, long_allele=%d)",
        total_rows,
        sum(stats.values()),
        skipped_sv + skipped_ref + skipped_no_rsid + skipped_long_allele,
        skipped_sv,
        skipped_ref,
        skipped_no_rsid,
        skipped_long_allele,
    )

    return alleles, dict(stats)


def main():
    parser = argparse.ArgumentParser(description="Import Stargazer star allele definitions")
    parser.add_argument("--dry-run", action="store_true", help="Print stats without writing output")
    args = parser.parse_args()

    if not STARGAZER_DIR.exists():
        log.error("Stargazer directory not found at %s", STARGAZER_DIR)
        sys.exit(1)

    # Step 1: Build position → rsID mapping
    pos_to_rsid, variant_info = build_snp_mapping()

    # Step 2: Build gene metadata
    gene_meta = build_gene_metadata()

    # Step 3: Build star allele definitions
    alleles, stats = build_star_alleles(pos_to_rsid, gene_meta)

    # Step 4: Fill chromosome info in variant_info from gene_meta
    gene_chrom: dict[str, str] = {}
    for gene_lower, meta in gene_meta.items():
        gene_chrom[gene_lower.upper()] = meta["chromosome"]

    for rsid, info in variant_info.items():
        if not info["chrom"] and info["gene"] in gene_chrom:
            info["chrom"] = gene_chrom[info["gene"]]

    # Filter variant_info to only include rsIDs used in allele definitions
    used_rsids = {a["rsid"] for a in alleles}
    filtered_variants = [v for rsid, v in variant_info.items() if rsid in used_rsids]

    # Build gene definitions for output
    gene_defs = {}
    for gene_lower, meta in sorted(gene_meta.items()):
        gene_upper = meta["gene"]
        if gene_upper in stats:  # Only include genes with mapped alleles
            gene_defs[gene_upper] = {
                "chromosome": meta["chromosome"],
                "transcript": meta["transcript"],
                "calling_method": meta["calling_method"],
            }

    # Summary
    print(f"\n{'Gene':>12} {'Alleles':>8} {'Method':>16}")
    print("-" * 40)
    for gene in sorted(stats.keys()):
        method = gene_defs.get(gene, {}).get("calling_method", "?")
        print(f"{gene:>12} {stats[gene]:>8} {method:>16}")
    print("-" * 40)
    print(f"{'TOTAL':>12} {sum(stats.values()):>8}")
    print(f"\nUnique rsIDs: {len(used_rsids)}")
    print(f"Variant info records: {len(filtered_variants)}")
    print(f"Genes with alleles: {len(gene_defs)}")

    if args.dry_run:
        log.info("Dry run — not writing output")
        return

    # Write output
    output = {
        "source": "Stargazer v2.0.3 (GRCh38)",
        "genes": gene_defs,
        "alleles": alleles,
        "variants": filtered_variants,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT_PATH.write_text(json.dumps(output, indent=2, sort_keys=False))
    log.info("Wrote %s (%d allele rows, %d variants)", OUTPUT_PATH, len(alleles), len(filtered_variants))


if __name__ == "__main__":
    main()
