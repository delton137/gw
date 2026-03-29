"""Gene variant matcher — maps user variants to genes using genomic coordinates.

Uses an interval tree (NCLS) built from gene coordinate data to find which
gene(s) each user variant falls in. Returns non-reference variants per gene
and per-gene coverage counts.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field

import numpy as np
import polars as pl
from ncls import NCLS
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

log = logging.getLogger(__name__)

# Complement bases for strand-flip detection
_COMP = {"A": "T", "T": "A", "C": "G", "G": "C"}


@dataclass
class GeneVariantHit:
    """A non-reference user variant mapped to a gene."""
    gene: str
    rsid: str | None
    chrom: str
    position: int
    user_genotype: str


@dataclass
class GeneCoverageEntry:
    """Per-gene coverage summary."""
    gene: str
    total_variants_tested: int
    non_reference_count: int


@dataclass
class GeneMatchResult:
    """Combined result of gene variant matching."""
    hits: list[GeneVariantHit] = field(default_factory=list)
    coverage: list[GeneCoverageEntry] = field(default_factory=list)


def _is_hom_ref(allele1: str, allele2: str, ref_allele: str | None) -> bool:
    """Check if genotype is homozygous reference (or complement)."""
    if not ref_allele:
        return False
    if allele1 == ref_allele and allele2 == ref_allele:
        return True
    comp = _COMP.get(ref_allele, "")
    if comp and allele1 == comp and allele2 == comp:
        return True
    return False


async def _load_gene_intervals(
    session: AsyncSession,
    genome_build: str,
) -> tuple[dict[str, tuple[NCLS, list[str], np.ndarray]], int]:
    """Load gene coordinates from DB and build per-chromosome NCLS trees.

    Returns ({chrom: (ncls_tree, gene_names_list, gene_ids_array)}, total_genes).
    """
    if genome_build == "GRCh37":
        start_col, end_col = "start_position_grch37", "end_position_grch37"
    else:
        start_col, end_col = "start_position_grch38", "end_position_grch38"

    result = await session.execute(
        text(f"""
            SELECT symbol, chrom, {start_col} AS start_pos, {end_col} AS end_pos
            FROM genes
            WHERE chrom IS NOT NULL
              AND {start_col} IS NOT NULL
              AND {end_col} IS NOT NULL
        """)
    )
    rows = result.all()
    if not rows:
        return {}, 0

    # Group by chromosome
    by_chrom: dict[str, list[tuple[str, int, int]]] = {}
    for symbol, chrom, start, end in rows:
        by_chrom.setdefault(chrom, []).append((symbol, start, end))

    # Build per-chromosome NCLS trees
    trees: dict[str, tuple[NCLS, list[str], np.ndarray]] = {}
    for chrom, entries in by_chrom.items():
        gene_names = [e[0] for e in entries]
        starts = np.array([e[1] for e in entries], dtype=np.int64)
        ends = np.array([e[2] for e in entries], dtype=np.int64)
        ids = np.arange(len(entries), dtype=np.int64)
        tree = NCLS(starts, ends, ids)
        trees[chrom] = (tree, gene_names, ids)

    log.info(f"Built interval trees for {len(trees)} chromosomes, {len(rows)} genes ({genome_build})")
    return trees, len(rows)


async def match_gene_variants(
    user_df: pl.DataFrame,
    session: AsyncSession,
    genome_build: str = "GRCh37",
) -> GeneMatchResult:
    """Match user variants against gene coordinate intervals.

    Args:
        user_df: DataFrame with columns [rsid, chrom, position, allele1, allele2]
        session: Async database session
        genome_build: "GRCh37" or "GRCh38"

    Returns:
        GeneMatchResult with non-ref variant hits and per-gene coverage.
    """
    t0 = time.perf_counter()

    if user_df.is_empty():
        return GeneMatchResult()

    # Load interval trees
    trees, total_genes = await _load_gene_intervals(session, genome_build)
    if not trees:
        log.warning("No gene coordinates loaded — skipping gene variant matching")
        return GeneMatchResult()

    # Build rsid → ref_allele lookup for hom-ref detection
    user_rsids = user_df["rsid"].to_list()
    ref_allele_lookup: dict[str, str] = {}
    batch_size = 5000
    for i in range(0, len(user_rsids), batch_size):
        batch = user_rsids[i : i + batch_size]
        result = await session.execute(
            text("SELECT rsid, ref_allele FROM snps WHERE rsid = ANY(:rsids) AND ref_allele IS NOT NULL"),
            {"rsids": batch},
        )
        for rsid, ref_allele in result:
            ref_allele_lookup[rsid] = ref_allele

    # Normalize chrom column (strip "chr" prefix)
    df = user_df.with_columns(
        pl.when(pl.col("chrom").str.starts_with("chr"))
        .then(pl.col("chrom").str.slice(3))
        .otherwise(pl.col("chrom"))
        .alias("chrom_norm")
    )

    # Per-gene counters and hits
    gene_total: dict[str, int] = {}
    gene_nonref: dict[str, int] = {}
    hits: list[GeneVariantHit] = []

    # Process per chromosome for vectorized NCLS queries
    for chrom_key, tree_data in trees.items():
        tree, gene_names, gene_ids = tree_data

        # Filter user variants on this chromosome
        chrom_df = df.filter(pl.col("chrom_norm") == chrom_key)
        if chrom_df.is_empty():
            continue

        positions = chrom_df["position"].to_numpy().astype(np.int64)
        query_ids = np.arange(len(positions), dtype=np.int64)

        # Vectorized interval query
        left_idx, right_idx = tree.all_overlaps_both(
            positions, positions + 1, query_ids
        )

        if len(left_idx) == 0:
            continue

        # Extract variant data for matched positions
        rsids = chrom_df["rsid"].to_list()
        allele1s = chrom_df["allele1"].to_list()
        allele2s = chrom_df["allele2"].to_list()

        for li, ri in zip(left_idx, right_idx):
            gene = gene_names[ri]
            rsid = rsids[li]
            a1 = allele1s[li]
            a2 = allele2s[li]
            pos = int(positions[li])

            if not a1 or not a2:
                continue

            genotype = f"{a1}{a2}"
            ref_allele = ref_allele_lookup.get(rsid)
            is_ref = _is_hom_ref(a1, a2, ref_allele) if ref_allele else False

            gene_total[gene] = gene_total.get(gene, 0) + 1

            if not is_ref:
                gene_nonref[gene] = gene_nonref.get(gene, 0) + 1
                hits.append(GeneVariantHit(
                    gene=gene,
                    rsid=rsid if rsid and rsid != "." else None,
                    chrom=chrom_key,
                    position=pos,
                    user_genotype=genotype,
                ))

    # Build coverage entries
    coverage = [
        GeneCoverageEntry(
            gene=gene,
            total_variants_tested=gene_total[gene],
            non_reference_count=gene_nonref.get(gene, 0),
        )
        for gene in gene_total
    ]

    elapsed = time.perf_counter() - t0
    log.info(
        f"Gene variant matching: {len(hits)} non-ref hits across "
        f"{len(gene_nonref)} genes, {len(gene_total)} genes with coverage, "
        f"{elapsed:.2f}s"
    )

    return GeneMatchResult(hits=hits, coverage=coverage)
