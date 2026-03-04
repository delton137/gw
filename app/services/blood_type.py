"""Blood type determination from genotype data using RBCeq2 allele definitions.

Determines ABO type, Rh antigens, and extended blood group antigens from
SNP array or VCF genotype data. Uses the curated ISBT allele database from
RBCeq2 (Australian Red Cross Lifeblood, MIT License).

Key design decisions:
- Position-based matching (works for VCFs with "." rsIDs)
- Also supports rsID-based matching (for DTC chip data)
- Special handling for ABO c.261delG (rs8176719) which DTC chips report
  as G/- but VCFs represent as an indel at position 136132908 (GRCh37)
- RhD positive/negative cannot be determined from SNP arrays or short-read
  WGS (requires long-read sequencing for RHD gene deletion detection)

Allele definitions from RBCeq2 v2.4.1
Copyright (c) 2025 Australian Red Cross Lifeblood — MIT License
"""

from __future__ import annotations

import csv
import logging
from dataclasses import dataclass, field
from pathlib import Path

import polars as pl

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Database loading
# ---------------------------------------------------------------------------

# Systems relevant for DTC / short-read WGS users.
# RHD excluded (requires long-read for gene deletion detection).
# HPA, C4A/C4B, and other specialized systems excluded.
INCLUDED_SYSTEMS = frozenset({
    "ABO", "RHCE", "KEL", "FY", "JK",
    "GYPA", "GYPB",  # MNS system
    "FUT1", "FUT2",  # Lewis / Secretor
    "DI", "DO", "CO", "LU", "SC", "YT", "IN", "CROM", "KN",
})

# Map system prefixes to user-friendly display names
SYSTEM_DISPLAY_NAMES = {
    "ABO": "ABO",
    "RHCE": "Rh (CE)",
    "KEL": "Kell",
    "FY": "Duffy",
    "JK": "Kidd",
    "GYPA": "MNS (MN)",
    "GYPB": "MNS (Ss)",
    "FUT1": "Lewis",
    "FUT2": "Secretor",
    "DI": "Diego",
    "DO": "Dombrock",
    "CO": "Colton",
    "LU": "Lutheran",
    "SC": "Scianna",
    "YT": "Cartwright",
    "IN": "Indian",
    "CROM": "Cromer",
    "KN": "Knops",
}

# ABO c.261delG position — the critical frameshift variant.
# In VCF terms: ref=T, alt=TC (an insertion) at these positions.
# A and B alleles HAVE this insertion (T→TC). O alleles have reference (T).
# DTC chips report this as rs8176719: G = functional (A/B), - = O deletion.
ABO_261DELG_POS_GRCH37 = 136132908
ABO_261DELG_POS_GRCH38 = 133257521
ABO_261DELG_CHROM = "9"

# rsIDs that DTC chips report as deletion alleles (not standard ACGT).
# These need special extraction from raw genotype content before parsing.
BLOOD_TYPE_DELETION_RSIDS = frozenset({"rs8176719"})


@dataclass(frozen=True)
class AlleleDefinition:
    """A single ISBT allele definition from the database."""
    genotype: str           # e.g. "ABO*A1.01", "FY*02"
    genotype_alt: str       # e.g. "ABO*A", "FY*B"
    system: str             # e.g. "ABO", "FY", "KEL"
    sub_type: str           # e.g. "ABO*A", "FY*02"
    phenotype_alt: str      # e.g. "A1", "Fy(a-),Fy(b+)"
    phenotype_change: str   # e.g. "A1", "Fy(b+)"
    chrom: str              # e.g. "9", "1"
    is_reference: bool      # Reference allele for this system
    is_antithetical: bool   # Part of an antithetical pair
    weight: int             # Ranking weight (higher = more common)
    is_lane: bool           # Lane variant (reference = meaningful)
    # Each variant is (position, ref_allele, alt_allele) or (position, "ref", None)
    variants_grch37: tuple[tuple[int, str, str | None], ...]
    variants_grch38: tuple[tuple[int, str, str | None], ...]
    has_indel: bool         # True if any variant is an indel (multi-char ref or alt)
    note: str


def _parse_variant_str(variant_str: str) -> tuple[int, str, str | None]:
    """Parse a variant string like '136131322_G_T' or '136132908_ref'.

    Returns (position, ref_allele, alt_allele) or (position, 'ref', None).
    """
    variant_str = variant_str.strip()
    if variant_str.endswith("_ref"):
        pos = int(variant_str[:-4])
        return (pos, "ref", None)
    parts = variant_str.split("_")
    pos = int(parts[0])
    ref = parts[1]
    alt = parts[2] if len(parts) > 2 else ""
    return (pos, ref, alt)


def _load_db() -> list[AlleleDefinition]:
    """Load and parse the RBCeq2 allele database."""
    db_path = Path(__file__).parent.parent / "data" / "rbceq2_db.tsv"
    alleles: list[AlleleDefinition] = []

    with open(db_path, newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            sub_type = row["Sub_type"]
            system = sub_type.split("*")[0] if "*" in sub_type else sub_type
            if system not in INCLUDED_SYSTEMS:
                continue

            chrom = row["Chrom"].replace("chr", "")

            # Parse GRCh37 variants
            grch37_str = row["GRCh37"].strip('"')
            grch38_str = row["GRCh38"].strip('"')

            try:
                variants_37 = tuple(
                    _parse_variant_str(v)
                    for v in grch37_str.split(",")
                    if v.strip()
                )
                variants_38 = tuple(
                    _parse_variant_str(v)
                    for v in grch38_str.split(",")
                    if v.strip()
                )
            except (ValueError, IndexError):
                continue  # Skip malformed entries

            # Check for indels (multi-char ref or alt)
            has_indel = False
            for pos, ref, alt in variants_37:
                if ref != "ref" and (len(ref) > 1 or (alt and len(alt) > 1)):
                    has_indel = True
                    break

            weight_str = row.get("Weight_of_genotype", "").strip()
            weight = int(weight_str) if weight_str.isdigit() else 1

            alleles.append(AlleleDefinition(
                genotype=row["Genotype"],
                genotype_alt=row.get("Genotype_alt", ""),
                system=system,
                sub_type=sub_type,
                phenotype_alt=row.get("Phenotype_alt_change", "") or row.get("Phenotype_alt", "") or "",
                phenotype_change=row.get("Phenotype_change", "") or "",
                chrom=chrom,
                is_reference=row.get("Reference_genotype", "").strip().lower() == "yes",
                is_antithetical=row.get("Antithetical", "").strip().lower() == "yes",
                weight=weight,
                is_lane=row.get("Lane", "").strip().upper() == "TRUE",
                variants_grch37=variants_37,
                variants_grch38=variants_38,
                has_indel=has_indel,
                note=row.get("Note", ""),
            ))

    log.info(f"Loaded {len(alleles)} blood group allele definitions from RBCeq2 database")
    return alleles


# Module-level singleton — loaded once at import time.
_DB: list[AlleleDefinition] = _load_db()


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class BloodTypeResult:
    """Blood type determination result."""
    abo_genotype: str           # ISBT notation: "ABO*A1.01/ABO*O.01.01"
    abo_phenotype: str          # "A", "B", "AB", "O"
    rh_c_antigen: str | None    # "C/c", "c/c", etc.
    rh_e_antigen: str | None    # "E/e", "e/e", etc.
    rh_cw_antigen: bool | None
    kell_phenotype: str | None
    mns_phenotype: str | None
    duffy_phenotype: str | None
    kidd_phenotype: str | None
    secretor_status: str | None
    display_type: str           # "A", "O", "AB" (just ABO phenotype)
    n_variants_tested: int
    n_variants_total: int
    n_systems_determined: int   # how many blood group systems resolved
    confidence: str             # "high" / "medium" / "low"
    confidence_note: str | None
    systems: dict = field(default_factory=dict)  # system → {genotype, phenotype}


# ---------------------------------------------------------------------------
# Core matching
# ---------------------------------------------------------------------------

def _build_user_lookups(
    user_df: pl.DataFrame,
    genome_build: str,
    deletion_genotypes: dict[str, tuple[str, str]] | None,
) -> tuple[dict[tuple[str, int], tuple[str, str]], set[tuple[str, int]], bool]:
    """Build position-based lookup from user genotype data.

    Returns:
        pos_lookup: (chrom, position) → (allele1, allele2)
        user_positions: set of all (chrom, position) in user data
        has_261delg_functional: whether user has functional allele at 261delG
            True = at least one G (functional, supports A/B)
            False = homozygous deletion (O/O)
            None = not genotyped
    """
    # Position-based lookup
    pos_lookup: dict[tuple[str, int], tuple[str, str]] = {}
    user_positions: set[tuple[str, int]] = set()

    _chroms = user_df["chrom"].to_list()
    _positions = user_df["position"].to_list()
    _a1s = user_df["allele1"].to_list()
    _a2s = user_df["allele2"].to_list()
    for chrom, pos, a1, a2 in zip(_chroms, _positions, _a1s, _a2s):
        key = (str(chrom), int(pos))
        pos_lookup[key] = (a1, a2)
        user_positions.add(key)

    # Handle the ABO 261delG from DTC deletion genotypes (rs8176719)
    # DTC chips report: G = functional (A/B), - = O deletion
    delg_pos = ABO_261DELG_POS_GRCH37 if genome_build != "GRCh38" else ABO_261DELG_POS_GRCH38
    has_261delg_info = None  # None = not genotyped

    if deletion_genotypes and "rs8176719" in deletion_genotypes:
        a1, a2 = deletion_genotypes["rs8176719"]
        g_count = (a1 == "G") + (a2 == "G")
        del_count = (a1 == "-") + (a2 == "-")

        if del_count == 2:
            # Homozygous O — no functional allele at this position.
            # In RBCeq2 terms: reference at 136132908 (no T→TC insertion).
            # We DON'T add to pos_lookup (absence = reference = O).
            has_261delg_info = "OO"
        elif g_count >= 1 and del_count >= 1:
            # Heterozygous: one functional, one O.
            # In RBCeq2 terms: het T→TC insertion.
            # Add as a synthetic indel entry so A/B alleles can match.
            pos_lookup[(ABO_261DELG_CHROM, delg_pos)] = ("T", "TC")
            user_positions.add((ABO_261DELG_CHROM, delg_pos))
            has_261delg_info = "het"
        elif g_count == 2:
            # Homozygous functional (A/A, A/B, or B/B).
            pos_lookup[(ABO_261DELG_CHROM, delg_pos)] = ("TC", "TC")
            user_positions.add((ABO_261DELG_CHROM, delg_pos))
            has_261delg_info = "func"

    return pos_lookup, user_positions, has_261delg_info


def _variant_matches(
    pos: int,
    ref: str,
    alt: str | None,
    chrom: str,
    pos_lookup: dict[tuple[str, int], tuple[str, str]],
    user_positions: set[tuple[str, int]],
) -> str | None:
    """Check if a single variant definition matches the user's data.

    Returns:
        "hom_alt" - user is homozygous for the alt allele
        "het" - user is heterozygous (one ref, one alt)
        "hom_ref" - user is homozygous reference (only valid for _ref variants)
        None - variant not present or doesn't match
    """
    key = (chrom, pos)

    if alt is None:
        # This is a _ref variant: position should be reference (absent or hom ref)
        if key not in user_positions:
            # Position not in data = assumed reference (especially for microarray)
            return "hom_ref"
        # Position IS in data — check if it's homozygous reference
        a1, a2 = pos_lookup[key]
        if a1 == ref or a2 == ref:
            # The user has a variant call at this position, so NOT purely reference.
            # But for _ref matching, we need the position to be reference.
            # If the user is het at a Lane position, the ref side supports the _ref allele.
            return "het"  # het at a _ref position = one copy supports this allele
        return "hom_ref"  # shouldn't reach here normally

    # Standard variant: check if user has the alt allele at this position
    if key not in pos_lookup:
        return None  # position not genotyped

    a1, a2 = pos_lookup[key]

    # For indel variants (multi-char ref or alt), use string matching
    has_alt_1 = (a1 == alt)
    has_alt_2 = (a2 == alt)
    has_ref_1 = (a1 == ref)
    has_ref_2 = (a2 == ref)

    if has_alt_1 and has_alt_2:
        return "hom_alt"
    if (has_alt_1 and has_ref_2) or (has_ref_1 and has_alt_2):
        return "het"
    if (has_alt_1 or has_alt_2):
        return "het"  # one alt allele present (other may be different alt)
    return None


def _match_alleles(
    pos_lookup: dict[tuple[str, int], tuple[str, str]],
    user_positions: set[tuple[str, int]],
    genome_build: str,
) -> dict[str, list[tuple[AlleleDefinition, int]]]:
    """Match user variants against all allele definitions.

    Returns: system → list of (allele_def, match_count) for alleles where
    ALL defining variants match.
    """
    matched: dict[str, list[tuple[AlleleDefinition, int]]] = {}
    variants_key = "variants_grch38" if genome_build == "GRCh38" else "variants_grch37"

    for allele in _DB:
        variants = getattr(allele, variants_key)
        if not variants:
            continue

        all_match = True
        n_matched = 0

        for pos, ref, alt in variants:
            result = _variant_matches(
                pos, ref, alt, allele.chrom, pos_lookup, user_positions,
            )
            if result is None:
                all_match = False
                break
            n_matched += 1

        if all_match and n_matched > 0:
            system = allele.system
            if system not in matched:
                matched[system] = []
            matched[system].append((allele, n_matched))

    return matched


def _select_best_alleles(
    matched: dict[str, list[tuple[AlleleDefinition, int]]],
) -> dict[str, list[AlleleDefinition]]:
    """For each system, select the best allele(s) using weight ranking.

    Keeps top-2 alleles (diploid) prioritizing:
    1. Most defining variants matched
    2. Highest weight
    3. Reference alleles as tiebreaker
    """
    result: dict[str, list[AlleleDefinition]] = {}

    for system, allele_matches in matched.items():
        # Sort by (n_variants desc, weight desc, is_reference desc)
        sorted_alleles = sorted(
            allele_matches,
            key=lambda x: (x[1], x[0].weight, x[0].is_reference),
            reverse=True,
        )

        # Keep up to 2 best alleles (diploid)
        best = []
        seen_genotypes = set()
        for allele, n in sorted_alleles:
            if allele.genotype not in seen_genotypes:
                best.append(allele)
                seen_genotypes.add(allele.genotype)
            if len(best) >= 2:
                break

        if best:
            result[system] = best

    return result


# ---------------------------------------------------------------------------
# Phenotype formatting
# ---------------------------------------------------------------------------

def _format_abo(alleles: list[AlleleDefinition]) -> tuple[str, str, str]:
    """Format ABO result from matched alleles.

    Returns (isbt_genotype, simple_genotype, phenotype).
    """
    if not alleles:
        return ("", "", "")

    # Get the phenotype category for each allele
    def _abo_class(a: AlleleDefinition) -> str:
        sub = a.sub_type
        if "ABO*O" in sub:
            return "O"
        if "ABO*B" in sub:
            return "B"
        if "ABO*A" in sub:
            return "A"
        return "A"  # default

    classes = [_abo_class(a) for a in alleles[:2]]
    while len(classes) < 2:
        classes.append(classes[0])  # homozygous

    classes.sort()
    simple_geno = f"{classes[0]}/{classes[1]}"

    # Phenotype
    has_a = "A" in classes
    has_b = "B" in classes
    if has_a and has_b:
        phenotype = "AB"
    elif has_b:
        phenotype = "B"
    elif has_a:
        phenotype = "A"
    else:
        phenotype = "O"

    # ISBT genotype
    isbt_parts = [a.genotype for a in alleles[:2]]
    if len(isbt_parts) == 1:
        isbt_parts.append(isbt_parts[0])
    isbt_geno = "/".join(sorted(isbt_parts))

    return isbt_geno, simple_geno, phenotype


def _format_antithetical(
    alleles: list[AlleleDefinition],
    system: str,
) -> str | None:
    """Format result for antithetical pair systems (Duffy, Kidd, Kell, etc.)."""
    if not alleles:
        return None

    phenotypes = set()
    for a in alleles[:2]:
        pheno = a.phenotype_alt or a.phenotype_change
        if pheno:
            phenotypes.add(pheno.strip('"'))

    return " | ".join(sorted(phenotypes)) if phenotypes else None


def _format_rhce(alleles: list[AlleleDefinition]) -> tuple[str | None, str | None, bool | None]:
    """Format RHCE result into C/c, E/e, and Cw antigens."""
    if not alleles:
        return None, None, None

    c_antigen = None
    e_antigen = None
    cw = None

    # Collect all phenotype info
    for a in alleles[:2]:
        pheno = (a.phenotype_alt or "").strip('"').lower()
        # Parse Rh phenotype strings like "C+,c-,E-,e+,Cw-"
        for part in pheno.split(","):
            part = part.strip()
            if part.startswith("c+") or part.startswith("c-"):
                pass  # handled below
            if "cw+" in part.lower():
                cw = True
            elif "cw-" in part.lower():
                if cw is None:
                    cw = False

    # Simplified: use sub_type to determine C/c and E/e
    for a in alleles[:2]:
        sub = a.sub_type
        if "RHCE*01" in sub:   # ce (little c, little e)
            if c_antigen is None:
                c_antigen = "c"
            elif "C" not in c_antigen:
                c_antigen = "C/c" if c_antigen == "c" else c_antigen
            if e_antigen is None:
                e_antigen = "e"
            elif "E" not in e_antigen:
                e_antigen = "E/e" if e_antigen == "e" else e_antigen
        elif "RHCE*02" in sub:  # Ce (big C, little e)
            if c_antigen is None:
                c_antigen = "C"
            elif "c" in c_antigen and "C" not in c_antigen:
                c_antigen = "C/c"
            if e_antigen is None:
                e_antigen = "e"
            elif "E" in e_antigen and "e" not in e_antigen:
                e_antigen = "E/e"
        elif "RHCE*03" in sub:  # cE (little c, big E)
            if c_antigen is None:
                c_antigen = "c"
            elif "C" in c_antigen and "c" not in c_antigen:
                c_antigen = "C/c"
            if e_antigen is None:
                e_antigen = "E"
            elif "e" in e_antigen and "E" not in e_antigen:
                e_antigen = "E/e"
        elif "RHCE*04" in sub:  # CE (big C, big E)
            if c_antigen is None:
                c_antigen = "C"
            elif "c" in c_antigen and "C" not in c_antigen:
                c_antigen = "C/c"
            if e_antigen is None:
                e_antigen = "E"
            elif "e" in e_antigen and "E" not in e_antigen:
                e_antigen = "E/e"

    return c_antigen, e_antigen, cw


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def determine_blood_type(
    user_df: pl.DataFrame,
    genome_build: str = "GRCh37",
    deletion_genotypes: dict[str, tuple[str, str]] | None = None,
) -> BloodTypeResult | None:
    """Determine blood type from parsed genotype data.

    Uses the RBCeq2 curated ISBT allele database for position-based
    variant matching. Supports both DTC chip data (via rsID → position
    mapping) and VCF data (direct position matching).

    Args:
        user_df: Polars DataFrame with columns [rsid, chrom, position, allele1, allele2].
        genome_build: "GRCh37" or "GRCh38".
        deletion_genotypes: Optional dict of rsid → (allele1, allele2) for
            variants that include deletion alleles ("-") filtered by the parser.
            Used for rs8176719 (ABO 261delG) from DTC chip data.

    Returns:
        BloodTypeResult or None if insufficient data for ABO determination.
    """
    try:
        # Build position-based lookup
        pos_lookup, user_positions, delg_info = _build_user_lookups(
            user_df, genome_build, deletion_genotypes,
        )

        if not pos_lookup and delg_info is None:
            log.info("Blood type: no variants in user data")
            return None

        # Match all alleles against user data
        matched = _match_alleles(pos_lookup, user_positions, genome_build)

        # Check ABO specifically
        abo_matched = matched.get("ABO")
        if not abo_matched and delg_info is None:
            log.info("Blood type: no ABO alleles matched — cannot determine blood type")
            return None

        # Handle ABO when only deletion info is available (no positional ABO matches)
        if not abo_matched and delg_info == "OO":
            # User is O/O based on DTC deletion data
            # Find the O reference allele from DB
            o_alleles = [a for a in _DB if a.system == "ABO" and "ABO*O" in a.sub_type]
            if o_alleles:
                matched["ABO"] = [(o_alleles[0], 1)]

        # Select best alleles per system
        best = _select_best_alleles(matched)

        if "ABO" not in best:
            # Still no ABO after filtering — try DTC-based determination
            if delg_info == "OO":
                # Synthesize minimal O result
                pass
            else:
                log.info("Blood type: no ABO alleles survived filtering")
                return None

        # Count variants tested
        all_db_positions = set()
        for allele in _DB:
            variants = allele.variants_grch37 if genome_build != "GRCh38" else allele.variants_grch38
            for pos, ref, alt in variants:
                all_db_positions.add((allele.chrom, pos))
        n_total = len(all_db_positions)
        n_tested = len(user_positions & all_db_positions)

        # Format ABO
        abo_alleles = best.get("ABO", [])
        abo_isbt, abo_simple, abo_phenotype = _format_abo(abo_alleles)

        # If ABO still empty but we have deletion info, use simple logic
        if not abo_phenotype and delg_info:
            if delg_info == "OO":
                abo_isbt = "ABO*O/ABO*O"
                abo_simple = "O/O"
                abo_phenotype = "O"
            elif delg_info == "func":
                abo_isbt = "ABO*A/ABO*A"
                abo_simple = "A/A"
                abo_phenotype = "A"
            elif delg_info == "het":
                abo_isbt = "ABO*A/ABO*O"
                abo_simple = "A/O"
                abo_phenotype = "A"

        if not abo_phenotype:
            log.info("Blood type: could not determine ABO phenotype")
            return None

        # Format RHCE
        rhce_alleles = best.get("RHCE", [])
        rh_c, rh_e, rh_cw = _format_rhce(rhce_alleles)

        # Format extended systems
        kell = _format_antithetical(best.get("KEL", []), "KEL")
        duffy = _format_antithetical(best.get("FY", []), "FY")
        kidd = _format_antithetical(best.get("JK", []), "JK")
        secretor = _format_antithetical(best.get("FUT2", []), "FUT2")

        # MNS from GYPA + GYPB
        mns_parts = []
        gypa = _format_antithetical(best.get("GYPA", []), "GYPA")
        gypb = _format_antithetical(best.get("GYPB", []), "GYPB")
        if gypa:
            mns_parts.append(gypa)
        if gypb:
            mns_parts.append(gypb)
        mns = " ".join(mns_parts) if mns_parts else None

        # Display type: just ABO phenotype (RhD caveat shown separately in UI)
        display_type = abo_phenotype

        # Build systems dict
        systems: dict[str, dict[str, str]] = {}
        for sys_name, alleles_list in best.items():
            display_name = SYSTEM_DISPLAY_NAMES.get(sys_name, sys_name)
            geno = "/".join(a.genotype for a in alleles_list[:2])
            pheno = " | ".join(
                (a.phenotype_alt or a.phenotype_change or "").strip('"')
                for a in alleles_list[:2]
                if (a.phenotype_alt or a.phenotype_change)
            )
            systems[display_name] = {"genotype": geno, "phenotype": pheno}

        # Confidence
        notes: list[str] = [
            "Rh D positive/negative status cannot be determined from genotyping "
            "chip data because Rh-negative is typically caused by a complete RHD "
            "gene deletion, which SNP arrays cannot detect."
        ]

        has_abo = "ABO" in best or delg_info is not None
        has_rh = "RHCE" in best
        n_systems = len(best)

        if has_abo and has_rh and n_systems >= 4:
            confidence = "high"
        elif has_abo and (has_rh or n_systems >= 2):
            confidence = "medium"
        else:
            confidence = "low"

        confidence_note = " ".join(notes) if notes else None

        return BloodTypeResult(
            abo_genotype=abo_isbt or abo_simple,
            abo_phenotype=abo_phenotype,
            rh_c_antigen=rh_c,
            rh_e_antigen=rh_e,
            rh_cw_antigen=rh_cw,
            kell_phenotype=kell,
            mns_phenotype=mns,
            duffy_phenotype=duffy,
            kidd_phenotype=kidd,
            secretor_status=secretor,
            display_type=display_type,
            n_variants_tested=n_tested,
            n_variants_total=n_total,
            n_systems_determined=len(best),
            confidence=confidence,
            confidence_note=confidence_note,
            systems=systems,
        )

    except Exception as e:
        log.error(f"Blood type determination failed: {e}", exc_info=True)
        return None
