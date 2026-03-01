"""Carrier status screening from genotype data.

Matches user variants against a curated panel of pathogenic variants for
autosomal recessive (and co-dominant) conditions. Determines carrier status,
potential affected status, and flags compound heterozygotes.

Panel loaded from app/data/carrier_panel.json — includes per-gene metadata,
variant definitions, clinical notes, and limitations.

Matching strategy:
  1. Try rsid-based lookup (works for 23andMe, AncestryDNA, annotated VCFs)
  2. Fall back to chrom+position lookup (works for unannotated WGS VCFs)
  3. Validate alleles against expected ref/pathogenic to catch strand issues
"""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

log = logging.getLogger(__name__)

_PANEL_PATH = Path(__file__).resolve().parent.parent / "data" / "carrier_panel.json"

# Singleton panel cache
_panel: dict | None = None

# Nucleotide complement for strand validation
_COMPLEMENT = {"A": "T", "T": "A", "C": "G", "G": "C"}


def _load_panel() -> dict:
    global _panel
    if _panel is None:
        with open(_PANEL_PATH) as f:
            _panel = json.load(f)
        log.info(
            "Carrier panel loaded: %d genes, %d variants",
            len(_panel["genes"]),
            sum(len(g["variants"]) for g in _panel["genes"]),
        )
    return _panel


@dataclass
class CarrierVariantResult:
    """Result for a single variant within a gene."""

    rsid: str
    name: str
    genotype: str  # user's genotype e.g. "AG"
    pathogenic_allele: str
    pathogenic_allele_count: int  # 0, 1, or 2
    classification: str  # pathogenic, risk_factor
    hgvs_p: str | None = None
    population_frequency: float | None = None


@dataclass
class CarrierGeneResult:
    """Result for carrier screening of a single gene."""

    gene: str
    condition: str
    inheritance: str
    severity: str
    status: str  # not_detected, carrier, likely_affected, potential_compound_het
    variants_detected: list[CarrierVariantResult] = field(default_factory=list)
    variants_tested: int = 0
    total_variants_screened: int = 0
    total_pathogenic_alleles: int = 0
    carrier_frequencies: dict[str, str] = field(default_factory=dict)
    condition_description: str = ""
    treatment_summary: str = ""
    penetrance_note: str = ""
    key_pmids: list[int] = field(default_factory=list)
    limitations: str = ""
    clinical_note: str = ""

    def to_dict(self) -> dict:
        return {
            "gene": self.gene,
            "condition": self.condition,
            "inheritance": self.inheritance,
            "severity": self.severity,
            "status": self.status,
            "variants_detected": [
                {
                    "rsid": v.rsid,
                    "name": v.name,
                    "genotype": v.genotype,
                    "pathogenic_allele": v.pathogenic_allele,
                    "pathogenic_allele_count": v.pathogenic_allele_count,
                    "classification": v.classification,
                    "hgvs_p": v.hgvs_p,
                    "population_frequency": v.population_frequency,
                }
                for v in self.variants_detected
            ],
            "variants_tested": self.variants_tested,
            "total_variants_screened": self.total_variants_screened,
            "total_pathogenic_alleles": self.total_pathogenic_alleles,
            "carrier_frequencies": self.carrier_frequencies,
            "condition_description": self.condition_description,
            "treatment_summary": self.treatment_summary,
            "penetrance_note": self.penetrance_note,
            "key_pmids": self.key_pmids,
            "limitations": self.limitations,
            "clinical_note": self.clinical_note,
        }


def _complement(allele: str) -> str:
    """Return the complement of a nucleotide sequence."""
    return "".join(_COMPLEMENT.get(c, c) for c in allele)


def _resolve_alleles(
    allele1: str, allele2: str, ref_allele: str, pathogenic_allele: str,
) -> tuple[str, str] | None:
    """Validate and optionally strand-correct user alleles.

    Returns (corrected_a1, corrected_a2) or None if alleles don't match
    either strand. For simple SNPs, detects opposite-strand genotypes
    and flips them. Skips strand-ambiguous SNPs (A/T or C/G) where the
    pathogenic allele is the complement of the reference allele.
    """
    # Skip no-call genotypes
    if not allele1 or not allele2 or allele1 in ("-", "0") or allele2 in ("-", "0"):
        return None

    # For multi-base alleles (indels), skip strand validation — just use as-is
    if len(ref_allele) > 1 or len(pathogenic_allele) > 1:
        return allele1, allele2

    expected = {ref_allele, pathogenic_allele}
    user_alleles = {allele1, allele2}

    # Check if user alleles match expected alleles (correct strand)
    if user_alleles <= expected:
        return allele1, allele2

    # Check if user alleles match complement (opposite strand)
    complement_expected = {_complement(ref_allele), _complement(pathogenic_allele)}
    if user_alleles <= complement_expected:
        # Check for strand-ambiguous SNPs (A/T or C/G)
        if expected == complement_expected:
            # Ambiguous — can't determine strand. Skip this variant.
            return None
        # Flip to correct strand
        return _complement(allele1), _complement(allele2)

    # Alleles don't match either strand (e.g., triallelic SNP or data issue)
    return None


def _count_allele(genotype: str, allele: str) -> int:
    """Count occurrences of an allele in a genotype string.

    Handles both simple SNPs (e.g. genotype "AG", allele "A" → 1)
    and indels where the allele may be longer than 1 character.
    For indels on DTC arrays, the genotype may be reported as e.g. "DI"
    (deletion/insertion) or the actual bases.
    """
    if not genotype or genotype in ("--", "00", "??", "NC", ""):
        return 0

    # For simple single-char alleles, count in the 2-char genotype
    if len(allele) == 1 and len(genotype) == 2:
        return genotype.count(allele)

    # For indels, check if genotype matches the allele pattern
    # DTC arrays often report indel genotypes differently
    return genotype.count(allele)


def determine_carrier_status(
    user_df: pl.DataFrame,
    genome_build: str = "GRCh37",
) -> list[CarrierGeneResult]:
    """Determine carrier status across all genes in the panel.

    Args:
        user_df: Polars DataFrame with columns [rsid, chrom, position, allele1, allele2]
        genome_build: Genome build of the input data ("GRCh37" or "GRCh38").
            Used for position-based matching when rsid matching fails.

    Returns:
        List of CarrierGeneResult, one per gene in the panel.
    """
    panel = _load_panel()

    # Build rsid → (allele1, allele2) lookup from user data
    rsid_lookup: dict[str, tuple[str, str]] = {}
    # Build (chrom, position) → (allele1, allele2) lookup for VCF fallback
    pos_lookup: dict[tuple[str, int], tuple[str, str]] = {}

    for row in user_df.iter_rows(named=True):
        rsid = row["rsid"]
        a1 = row.get("allele1", "")
        a2 = row.get("allele2", "")
        if not a1 or not a2:
            continue

        if rsid and rsid != ".":
            rsid_lookup[rsid] = (a1, a2)

        chrom = str(row.get("chrom", "")).replace("chr", "")
        pos = row.get("position")
        if chrom and pos:
            pos_lookup[(chrom, int(pos))] = (a1, a2)

    # Choose which position field to use based on genome build
    pos_field = "position_grch38" if genome_build == "GRCh38" else "position"

    results: list[CarrierGeneResult] = []

    for gene_def in panel["genes"]:
        gene = gene_def["gene"]
        variants = gene_def["variants"]
        detected: list[CarrierVariantResult] = []
        total_pathogenic = 0
        distinct_pathogenic_variants = 0
        n_tested = 0

        for var_def in variants:
            rsid = var_def["rsid"]
            ref_allele = var_def.get("ref_allele", "")
            pathogenic_allele = var_def["pathogenic_allele"]

            # Strategy 1: rsid-based lookup
            alleles = rsid_lookup.get(rsid)

            # Strategy 2: position-based fallback (for VCFs with "." rsids)
            if alleles is None:
                var_chrom = str(var_def.get("chrom", "")).replace("chr", "")
                var_pos = var_def.get(pos_field) or var_def.get("position")
                if var_chrom and var_pos:
                    alleles = pos_lookup.get((var_chrom, int(var_pos)))

            if alleles is None:
                continue

            n_tested += 1
            a1, a2 = alleles

            # Validate alleles against expected ref/pathogenic (strand correction)
            if ref_allele:
                resolved = _resolve_alleles(a1, a2, ref_allele, pathogenic_allele)
                if resolved is None:
                    # Alleles don't match expected — likely strand-ambiguous or data issue
                    log.debug(
                        "Carrier %s/%s: skipping — alleles %s%s don't match "
                        "expected ref=%s/path=%s on either strand",
                        gene, rsid, a1, a2, ref_allele, pathogenic_allele,
                    )
                    continue
                a1, a2 = resolved

            geno = a1 + a2
            count = _count_allele(geno, pathogenic_allele)

            if count > 0:
                detected.append(CarrierVariantResult(
                    rsid=rsid,
                    name=var_def["name"],
                    genotype=geno,
                    pathogenic_allele=pathogenic_allele,
                    pathogenic_allele_count=count,
                    classification=var_def["classification"],
                    hgvs_p=var_def.get("hgvs_p"),
                    population_frequency=var_def.get("population_frequency"),
                ))
                total_pathogenic += count
                distinct_pathogenic_variants += 1

        # Classify status
        if total_pathogenic == 0:
            status = "not_detected"
            clinical_note = (
                f"No pathogenic variants detected in {gene} from the "
                f"{len(variants)} variant(s) tested. Note: a negative result "
                f"does not eliminate carrier risk — see limitations."
            )
        elif total_pathogenic == 1:
            status = "carrier"
            var = detected[0]
            clinical_note = (
                f"Carrier of one {gene} pathogenic variant ({var.name}). "
                f"{gene_def.get('condition', '')} is inherited in an "
                f"{gene_def.get('inheritance', 'autosomal recessive').replace('_', ' ')} pattern. "
                f"Carriers are typically unaffected but can pass the variant to children. "
                f"If a reproductive partner is also a carrier, each pregnancy has a 25% chance of an affected child."
            )
        elif total_pathogenic >= 2 and distinct_pathogenic_variants >= 2:
            # Two different variants — could be compound het (trans) or cis
            status = "potential_compound_het"
            var_names = ", ".join(v.name for v in detected)
            clinical_note = (
                f"Two different pathogenic variants detected in {gene}: {var_names}. "
                f"If these variants are on different chromosomes (compound heterozygosity), "
                f"this individual may be affected by {gene_def.get('condition', '')}. "
                f"If both are on the same chromosome, this individual is a carrier only. "
                f"Phase cannot be determined from SNP array data — clinical confirmation "
                f"with segregation analysis or sequencing is strongly recommended."
            )
        elif total_pathogenic >= 2:
            # Homozygous for a single variant
            status = "likely_affected"
            var = detected[0]
            clinical_note = (
                f"Homozygous for {gene} pathogenic variant {var.name} "
                f"({var.pathogenic_allele_count} copies detected). "
                f"This genotype is associated with {gene_def.get('condition', '')}. "
                f"Clinical evaluation and genetic counseling are strongly recommended."
            )
        else:
            status = "not_detected"
            clinical_note = ""

        results.append(CarrierGeneResult(
            gene=gene,
            condition=gene_def["condition"],
            inheritance=gene_def["inheritance"],
            severity=gene_def["severity"],
            status=status,
            variants_detected=detected,
            variants_tested=n_tested,
            total_variants_screened=len(variants),
            total_pathogenic_alleles=total_pathogenic,
            carrier_frequencies=gene_def.get("carrier_frequencies", {}),
            condition_description=gene_def.get("condition_description", ""),
            treatment_summary=gene_def.get("treatment_summary", ""),
            penetrance_note=gene_def.get("penetrance_note", ""),
            key_pmids=gene_def.get("key_pmids", []),
            limitations=gene_def.get("limitations", ""),
            clinical_note=clinical_note,
        ))

    return results
