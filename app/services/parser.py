"""Genotype file parser for 23andMe, AncestryDNA, and VCF formats.

Parses raw genotype files into a normalized Polars DataFrame with columns:
[rsid, chrom, position, allele1, allele2]

Raw file content is never persisted — only held in memory during parsing.
Uses Polars native CSV reader for performance (handles 400MB+ files in seconds).
"""

from __future__ import annotations

import gzip
import io
import logging

import polars as pl

from app.config import settings

log = logging.getLogger(__name__)

# Chip version detection by approximate variant count
CHIP_VERSIONS = [
    (3_000_000, 100_000_000, "wgs"),
    (900_000, 1_100_000, "23andme_v5"),
    (600_000, 900_000, "23andme_v4"),
    (500_000, 600_000, "23andme_v3"),
    (300_000, 500_000, "ancestrydna_v2"),
    (100_000, 300_000, "ancestrydna_v1"),
]

_VALID_ALLELES = ["A", "C", "G", "T"]
_NOCALL_LIST = ["-", "0", ".", "D", "I", "--", "00", "DD", "II", "DI", "ID"]


class ParseError(Exception):
    """Raised when a genotype file cannot be parsed."""


def detect_format(header_lines: list[str]) -> str:
    """Detect file format from the first non-comment lines."""
    for line in header_lines:
        if line.startswith("##fileformat=VCF"):
            return "vcf"

    for line in header_lines:
        stripped = line.strip()
        if stripped.startswith(">locus\t"):
            return "cgi"

    for line in header_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        cols = stripped.split("\t")
        if len(cols) == 5 and cols[0].startswith("rs"):
            return "ancestrydna"
        if len(cols) == 4 and cols[0].startswith("rs"):
            return "23andme"

    raise ParseError("Unable to detect genotype file format from header lines")


_WGS_SOURCES = frozenset({
    "gatk", "deepvariant", "strelka", "dragen",
    "haplotypecaller", "octopus", "freebayes",
})

_IMPUTATION_SOURCES = frozenset({
    "beagle", "minimac", "minimac3", "minimac4",
    "impute2", "impute4", "impute5", "pbwt",
})


def extract_vcf_header_meta(content: str) -> dict:
    """Extract metadata from VCF header lines for WGS and imputation detection.

    Scans ## lines (typically <1 KB even for large VCFs) and returns:
    - contig_count: number of ##contig= lines
    - has_wgs_source: whether ##source= mentions a known WGS variant caller
    - is_imputed: whether the VCF was produced by imputation software
    """
    contig_count = 0
    has_wgs_source = False
    is_imputed = False

    for line in content.split("\n"):
        if not line.startswith("##"):
            break
        if line.startswith("##contig="):
            contig_count += 1
        elif line.startswith("##source="):
            source_lower = line.lower()
            if any(s in source_lower for s in _WGS_SOURCES):
                has_wgs_source = True
            if any(s in source_lower for s in _IMPUTATION_SOURCES):
                is_imputed = True
        elif line.startswith("##INFO=<ID=IMP,") or line.startswith("##INFO=<ID=DR2,"):
            is_imputed = True

    return {"contig_count": contig_count, "has_wgs_source": has_wgs_source, "is_imputed": is_imputed}


def detect_chip_version(variant_count: int, vcf_meta: dict | None = None) -> str:
    """Guess chip version from total variant count.

    For VCF files, optional header metadata (contig count, source caller)
    can confirm WGS status at lower variant counts (1.1M–3M range).
    """
    for low, high, name in CHIP_VERSIONS:
        if low <= variant_count < high:
            return name

    # Header-confirmed WGS: variant count in the 1.1M–3M gap with
    # VCF header evidence (≥22 contigs or known WGS caller)
    if vcf_meta and variant_count >= 1_100_000:
        if vcf_meta.get("contig_count", 0) >= 22 or vcf_meta.get("has_wgs_source"):
            return "wgs"

    return "unknown"


def parse_23andme(content: str) -> pl.DataFrame:
    """Parse 23andMe format genotype file using Polars CSV reader."""
    try:
        df = pl.read_csv(
            io.StringIO(content),
            separator="\t",
            has_header=False,
            comment_prefix="#",
            new_columns=["rsid", "chrom", "position", "genotype"],
            schema={"rsid": pl.Utf8, "chrom": pl.Utf8, "position": pl.Int64, "genotype": pl.Utf8},
            ignore_errors=True,
            truncate_ragged_lines=True,
        )
    except Exception as e:
        raise ParseError("Failed to parse 23andMe file") from e

    # Filter to rs* variants, non-null genotypes, valid lengths, no no-calls
    df = df.filter(
        pl.col("rsid").str.starts_with("rs")
        & pl.col("genotype").is_not_null()
        & pl.col("genotype").str.len_chars().is_between(1, 2)
        & ~pl.col("genotype").is_in(_NOCALL_LIST)
    )

    # Split genotype into allele1, allele2
    df = df.with_columns(
        pl.col("genotype").str.slice(0, 1).alias("allele1"),
        pl.when(pl.col("genotype").str.len_chars() == 2)
        .then(pl.col("genotype").str.slice(1, 1))
        .otherwise(pl.col("genotype").str.slice(0, 1))
        .alias("allele2"),
    )

    # Filter to valid ACGT alleles only
    df = df.filter(
        pl.col("allele1").is_in(_VALID_ALLELES)
        & pl.col("allele2").is_in(_VALID_ALLELES)
    )

    df = df.select("rsid", "chrom", "position", "allele1", "allele2")

    if len(df) == 0:
        raise ParseError("No valid variants found in 23andMe file")

    return df


def parse_ancestrydna(content: str) -> pl.DataFrame:
    """Parse AncestryDNA format genotype file using Polars CSV reader."""
    try:
        df = pl.read_csv(
            io.StringIO(content),
            separator="\t",
            has_header=False,
            comment_prefix="#",
            new_columns=["rsid", "chrom", "position", "allele1", "allele2"],
            schema={
                "rsid": pl.Utf8,
                "chrom": pl.Utf8,
                "position": pl.Int64,
                "allele1": pl.Utf8,
                "allele2": pl.Utf8,
            },
            ignore_errors=True,
            truncate_ragged_lines=True,
        )
    except Exception as e:
        raise ParseError("Failed to parse AncestryDNA file") from e

    df = df.filter(
        pl.col("rsid").str.starts_with("rs")
        & pl.col("allele1").is_in(_VALID_ALLELES)
        & pl.col("allele2").is_in(_VALID_ALLELES)
    )

    if len(df) == 0:
        raise ParseError("No valid variants found in AncestryDNA file")

    return df


def parse_cgi(content: str) -> pl.DataFrame:
    """Parse Complete Genomics var-ASM/masterVar format using Polars CSV reader.

    CGI format stores two rows per diploid variant (one per allele). This function
    filters to high-quality SNPs, extracts rsIDs from the xRef column, and
    pivots allele rows into a single row per variant.

    Coordinates are 0-based half-open in the file; converted to 1-based here.
    """
    # Skip header section: # comments, blank lines, and the >locus column header.
    # This prevents Polars from mis-detecting column count on blank/header lines.
    header_end = content.find("\n>locus\t")
    if header_end >= 0:
        data_start = content.find("\n", header_end + 1)
        if data_start >= 0:
            content = content[data_start + 1:]

    try:
        # Only read the 9 columns we need (of 14 total)
        df = pl.read_csv(
            io.StringIO(content),
            separator="\t",
            has_header=False,
            columns=[0, 2, 3, 4, 6, 7, 8, 11, 13],
            ignore_errors=True,
            truncate_ragged_lines=True,
            infer_schema_length=0,
        )
    except Exception as e:
        raise ParseError("Failed to parse Complete Genomics file") from e

    if df.width < 9:
        raise ParseError("Complete Genomics file has too few columns")

    df = df.rename(dict(zip(df.columns, [
        "locus", "allele", "chromosome", "begin",
        "varType", "reference", "alleleSeq", "varQuality", "xRef",
    ])))

    # Filter to high-quality SNPs with valid single-base alleles
    df = df.filter(
        (pl.col("varType") == "snp")
        & (pl.col("varQuality") == "VQHIGH")
        & pl.col("alleleSeq").is_in(_VALID_ALLELES)
        & pl.col("reference").is_in(_VALID_ALLELES)
    )

    # Extract first rsID from xRef (format: "dbsnp.NNN:rsXXXXXX;...")
    df = df.with_columns(
        pl.col("xRef").str.extract(r"(rs\d+)", 1).alias("rsid"),
    )
    df = df.filter(pl.col("rsid").is_not_null())

    # Convert 0-based half-open begin to 1-based position; strip chr prefix
    df = df.with_columns(
        (pl.col("begin").cast(pl.Int64) + 1).alias("position"),
        pl.col("chromosome").str.replace(r"^chr", "").alias("chrom"),
    )

    # Separate allele 1 and allele 2 rows
    a1 = df.filter(pl.col("allele") == "1").select(
        "locus", "rsid", "chrom", "position", "reference",
        pl.col("alleleSeq").alias("allele1"),
    )
    a2 = df.filter(pl.col("allele") == "2").select(
        "locus",
        pl.col("alleleSeq").alias("allele2"),
        pl.col("rsid").alias("_rsid2"),
        pl.col("chrom").alias("_chrom2"),
        pl.col("position").alias("_pos2"),
        pl.col("reference").alias("_ref2"),
    )

    # Full outer join to pair alleles by locus number
    result = a1.join(a2, on="locus", how="full", coalesce=True)

    # Fill metadata from whichever allele row is present (het sites)
    result = result.with_columns(
        pl.coalesce("rsid", "_rsid2").alias("rsid"),
        pl.coalesce("chrom", "_chrom2").alias("chrom"),
        pl.coalesce("position", "_pos2").alias("position"),
        pl.coalesce("reference", "_ref2").alias("reference"),
    )

    # For het sites, the missing allele is the reference base
    result = result.with_columns(
        pl.col("allele1").fill_null(pl.col("reference")),
        pl.col("allele2").fill_null(pl.col("reference")),
    )

    result = result.filter(
        pl.col("allele1").is_in(_VALID_ALLELES)
        & pl.col("allele2").is_in(_VALID_ALLELES)
    )

    # Handle "all" allele rows (both alleles identical) if any exist for SNPs
    a_all = df.filter(pl.col("allele") == "all")
    if a_all.height > 0:
        a_all = a_all.select(
            "rsid", "chrom", "position",
            pl.col("alleleSeq").alias("allele1"),
            pl.col("alleleSeq").alias("allele2"),
        )
        result = pl.concat([
            result.select("rsid", "chrom", "position", "allele1", "allele2"),
            a_all,
        ])
    else:
        result = result.select("rsid", "chrom", "position", "allele1", "allele2")

    result = result.unique(subset=["rsid"], keep="first")

    if len(result) == 0:
        raise ParseError("No valid variants found in Complete Genomics file")

    return result


def parse_vcf(content: str) -> pl.DataFrame:
    """Parse VCF format genotype file using Polars CSV reader."""
    # VCF standard: CHROM(0) POS(1) ID(2) REF(3) ALT(4) QUAL(5) FILTER(6) INFO(7) FORMAT(8) SAMPLE(9+)
    # Only read the 6 columns we need — skipping QUAL/FILTER/INFO/FORMAT saves ~2 GB
    # for whole-genome VCFs where the INFO field is enormous.
    try:
        df = pl.read_csv(
            io.StringIO(content),
            separator="\t",
            has_header=False,
            comment_prefix="#",
            columns=[0, 1, 2, 3, 4, 9],
            ignore_errors=True,
            truncate_ragged_lines=True,
            infer_schema_length=0,  # read everything as strings first
        )
    except Exception as e:
        raise ParseError("Failed to parse VCF file") from e

    if df.width < 6:
        raise ParseError("No valid variants found in VCF file")

    # Rename selected columns by position
    df = df.rename(dict(zip(df.columns, ["chrom", "pos", "rsid", "ref", "alt", "sample"])))

    # Filter: biallelic, single-char REF/ALT (SNPs only)
    # Note: WGS VCFs often have "." as the ID — rsid lookup happens later via chrom+pos
    df = df.filter(
        ~pl.col("alt").str.contains(",")
        & pl.col("ref").is_in(_VALID_ALLELES)
        & pl.col("alt").is_in(_VALID_ALLELES)
    )

    # Extract GT field — GT is almost always the first FORMAT field per VCF spec
    # Extract the first colon-delimited field from sample as GT
    df = df.with_columns(
        pl.col("sample").str.split(":").list.get(0).alias("gt"),
    )

    # Normalize phased (|) to unphased (/)
    df = df.with_columns(pl.col("gt").str.replace_all(r"\|", "/"))

    # Filter to valid genotypes: diploid (0/0, 0/1, 1/0, 1/1) or
    # haploid (0, 1) for hemizygous calls on chrX/chrY in males
    df = df.filter(pl.col("gt").str.contains(r"^[01](/[01])?$"))

    # Normalise haploid calls to diploid by duplicating the allele
    # e.g. "1" -> "1/1", "0" -> "0/0"
    df = df.with_columns(
        pl.when(pl.col("gt").str.len_chars() == 1)
        .then(pl.col("gt") + "/" + pl.col("gt"))
        .otherwise(pl.col("gt"))
        .alias("gt")
    )

    # Extract allele indices and map to actual alleles
    df = df.with_columns(
        pl.col("gt").str.split("/").list.get(0).cast(pl.Int32).alias("idx1"),
        pl.col("gt").str.split("/").list.get(1).cast(pl.Int32).alias("idx2"),
    )

    df = df.with_columns(
        pl.when(pl.col("idx1") == 0).then(pl.col("ref")).otherwise(pl.col("alt")).alias("allele1"),
        pl.when(pl.col("idx2") == 0).then(pl.col("ref")).otherwise(pl.col("alt")).alias("allele2"),
    )

    # Drop homozygous-reference variants (0/0) — they carry no information for any
    # downstream analysis (traits, PGx, PRS, carrier, ancestry) and can balloon
    # memory for imputed genomes (87% of variants are hom-ref, ~27M rows).
    # PRS scoring and ancestry estimation already treat missing = hom-ref.
    pre_filter = len(df)
    df = df.filter(~((pl.col("idx1") == 0) & (pl.col("idx2") == 0)))
    if len(df) < pre_filter:
        log.info(f"Filtered {pre_filter - len(df):,} hom-ref variants ({len(df):,} remaining)")

    # Strip chr prefix, cast position
    df = df.with_columns(
        pl.col("chrom").str.replace(r"^chr", "").alias("chrom"),
        pl.col("pos").cast(pl.Int64).alias("position"),
    )

    df = df.select("rsid", "chrom", "position", "allele1", "allele2")

    if len(df) == 0:
        raise ParseError("No valid variants found in VCF file")

    return df


# Well-known SNP positions for genome build detection (quick check)
# Format: (rsid, chrom, grch37_pos, grch38_pos)
_BUILD_MARKERS = [
    ("rs429358", "19", 45411941, 44908684),   # APOE
    ("rs7412",   "19", 45412079, 44908822),   # APOE
    ("rs1426654", "15", 48426484, 48413169),  # SLC24A5
    ("rs12913832", "15", 28365618, 28120472), # HERC2 (eye color)
    ("rs1805007",  "16", 89986117, 89919709), # MC1R (red hair)
]

# Extended build detection markers — one per chromosome, verified from DB.
# High EUR AF (0.2-0.8) so likely present in variant-only VCFs.
# All have different GRCh37 vs GRCh38 positions.
# Format: (chrom, grch37_pos, grch38_pos)
_BUILD_MARKERS_EXTENDED = [
    ("1", 242545088, 242381786),   # rs78304837
    ("2", 66281811, 66054677),     # rs1601255
    ("3", 68719119, 68669968),     # rs1875829
    ("4", 83531025, 82609872),     # rs34506254
    ("5", 66706856, 67411028),     # rs32025
    ("6", 137613369, 137292232),   # rs2780657
    ("7", 149381716, 149684625),   # rs1101865
    ("8", 5369603, 5512081),       # rs1526343
    ("9", 111621807, 108859527),   # rs72758341
    ("10", 130302353, 128504089),  # rs12249711
    ("11", 130055763, 130185868),  # rs683229
    ("12", 74592111, 74198331),    # rs1402971
    ("13", 36401746, 35827609),    # rs9574698
    ("14", 28337919, 27868713),    # rs8005944
    ("15", 54787671, 54495473),    # rs622459
    ("16", 24049614, 24038293),    # rs2046893
    ("17", 41513164, 43435796),    # rs12601585
    ("18", 35771878, 38191914),    # rs4261614
    ("19", 3397564, 3397566),      # rs4806929
    ("20", 45744355, 47115716),    # rs3787249
]


def detect_genome_build(user_df: pl.DataFrame) -> str:
    """Detect whether user genotype data uses GRCh37 or GRCh38 coordinates.

    Uses two strategies:
    1. Quick check: match well-known SNP positions or rsIDs (works for arrays)
    2. Statistical check: for VCFs where specific markers may be absent,
       sample many user positions and vote on which build they match

    Returns "GRCh37", "GRCh38", or "unknown".
    """
    if "position" not in user_df.columns:
        return "unknown"

    votes_37 = 0
    votes_38 = 0

    # Strategy 1: Check well-known markers by position or rsid
    for rsid, chrom, pos37, pos38 in _BUILD_MARKERS:
        match = user_df.filter(
            (pl.col("chrom") == chrom) & (pl.col("position").is_in([pos37, pos38]))
        )
        if match.height == 0:
            match = user_df.filter(pl.col("rsid") == rsid)
            if match.height == 0:
                continue

        pos = match["position"][0]
        if pos == pos37:
            votes_37 += 1
        elif pos == pos38:
            votes_38 += 1

    if votes_37 > 0 or votes_38 > 0:
        if votes_38 > votes_37:
            return "GRCh38"
        elif votes_37 > votes_38:
            return "GRCh37"

    # Strategy 2: Statistical — check extended markers by position only
    # This handles variant-only VCFs where specific rsIDs may be absent
    for chrom, pos37, pos38 in _BUILD_MARKERS_EXTENDED:
        if pos37 == pos38:
            continue  # Same position in both builds — not informative
        match37 = user_df.filter(
            (pl.col("chrom") == chrom) & (pl.col("position") == pos37)
        )
        match38 = user_df.filter(
            (pl.col("chrom") == chrom) & (pl.col("position") == pos38)
        )
        if match37.height > 0:
            votes_37 += 1
        if match38.height > 0:
            votes_38 += 1

    if votes_38 > votes_37:
        return "GRCh38"
    elif votes_37 > votes_38:
        return "GRCh37"
    return "unknown"


ALLOWED_EXTENSIONS = {".txt", ".csv", ".tsv", ".vcf", ".vcf.gz", ".vcf.zip", ".zip", ".txt.gz", ".tsv.gz"}


def validate_filename(filename: str) -> None:
    """Reject files that don't have a recognized genotype file extension."""
    name = filename.lower()
    if not any(name.endswith(ext) for ext in ALLOWED_EXTENSIONS):
        raise ParseError(
            f"Unsupported file type. Accepted extensions: {', '.join(sorted(ALLOWED_EXTENSIONS))}"
        )


def decompress_if_gzipped(data: bytes) -> str:
    """Decompress gzipped data or decode plain text bytes."""
    if data[:2] == b"\x1f\x8b":
        decompressed = gzip.decompress(data)
        if len(decompressed) > settings.max_decompressed_size:
            raise ParseError(f"Decompressed file exceeds {settings.max_decompressed_size // (1024*1024)} MB size limit")
        return decompressed.decode("utf-8", errors="replace")
    return data.decode("utf-8", errors="replace")


def parse_genotype_file(content: str | bytes) -> tuple[pl.DataFrame, str, str]:
    """Parse a genotype file and return (DataFrame, format, chip_version).

    The DataFrame has columns: [rsid, chrom, position, allele1, allele2].
    Accepts either a string or bytes (which may be gzipped).
    """
    if isinstance(content, bytes):
        content = decompress_if_gzipped(content)

    header_lines = content.split("\n", 50)[:50]
    fmt = detect_format(header_lines)

    vcf_meta = None
    if fmt == "23andme":
        df = parse_23andme(content)
    elif fmt == "ancestrydna":
        df = parse_ancestrydna(content)
    elif fmt == "vcf":
        df = parse_vcf(content)
        vcf_meta = extract_vcf_header_meta(content)
    elif fmt == "cgi":
        df = parse_cgi(content)
    else:
        raise ParseError(f"Unsupported format: {fmt}")

    chip_version = detect_chip_version(len(df), vcf_meta=vcf_meta)
    return df, fmt, chip_version


def extract_raw_genotypes(
    content: str, fmt: str, target_rsids: set[str],
) -> dict[str, tuple[str, str]]:
    """Extract raw genotypes for specific rsIDs, preserving deletion alleles.

    The main parser filters out non-ACGT alleles (including "-" deletions).
    This function does a targeted scan for specific rsIDs and preserves
    deletion alleles like "-" which DTC chips report for indel variants
    (e.g., rs8176719 for the ABO 261delG).

    Args:
        content: Raw file content string.
        fmt: File format ("23andme", "ancestrydna", "vcf").
        target_rsids: Set of rsIDs to extract.

    Returns:
        Dict mapping rsid → (allele1, allele2) for found variants.
    """
    if not target_rsids or fmt in ("vcf", "cgi"):
        return {}

    result: dict[str, tuple[str, str]] = {}

    for line in content.split("\n"):
        if line.startswith("#") or not line.strip():
            continue

        parts = line.split("\t")
        if len(parts) < 4:
            continue

        rsid = parts[0].strip()
        if rsid not in target_rsids:
            continue

        if fmt == "23andme":
            # 23andMe: rsid, chrom, position, genotype
            genotype = parts[3].strip()
            if len(genotype) == 2:
                result[rsid] = (genotype[0], genotype[1])
            elif len(genotype) == 1:
                result[rsid] = (genotype[0], genotype[0])
        elif fmt == "ancestrydna":
            # AncestryDNA: rsid, chrom, position, allele1, allele2
            if len(parts) >= 5:
                result[rsid] = (parts[3].strip(), parts[4].strip())

        if len(result) == len(target_rsids):
            break  # Found all targets

    return result
