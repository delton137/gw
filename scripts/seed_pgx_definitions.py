"""Seed pharmacogenomics knowledge-base tables.

Loads gene definitions, star allele definitions, and diplotype phenotype mappings
from scripts/_pgx_allele_definitions.py into the pgx_* tables.  Also merges
expanded star allele definitions from app/data/pgx_alleles.json 

Usage:
    python -m scripts.seed_pgx_definitions           # insert to database
    python -m scripts.seed_pgx_definitions --dry-run  # print what would be inserted
"""

from __future__ import annotations

import argparse
import asyncio
import json
import logging
from pathlib import Path

from sqlalchemy import text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from app.config import settings
from app.models.base import Base
from app.models.pgx import (
    PgxDiplotypePhenotype,
    PgxDrugGuideline,
    PgxGeneDefinition,
    PgxStarAlleleDefinition,
)
from app.models.snp import Snp
from scripts._pgx_allele_definitions import (
    PGX_DIPLOTYPE_PHENOTYPES,
    PGX_GENE_DEFS,
    PGX_STAR_ALLELES,
)

PGX_ALLELES_JSON = Path(__file__).parent.parent / "app" / "data" / "pgx_alleles.json"
GUIDELINES_JSON = Path(__file__).parent.parent / "app" / "data" / "cpic_dpwg_guidelines.json"

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)


def _merge_pgx_alleles(curated: list[dict]) -> list[dict]:
    """Merge PGx allele definitions from pgx_alleles.json with curated definitions.

    Curated definitions take priority:
    - Exact (gene, star_allele, rsid) matches: curated version is kept.
    - Cross-source single-SNP duplicates: Stargazer single-SNP alleles whose
      (gene, rsid, variant_allele) already exists under a curated allele are
      removed to prevent double-counting in diplotype assignment.
    """
    if not PGX_ALLELES_JSON.exists():
        log.warning("PGx alleles JSON not found at %s — using curated only", PGX_ALLELES_JSON)
        return curated

    data = json.loads(PGX_ALLELES_JSON.read_text())
    sg_alleles = data.get("alleles", [])
    if not sg_alleles:
        return curated

    # Build set of valid gene names from curated gene definitions
    valid_genes = {gd["gene"] for gd in PGX_GENE_DEFS}

    # Build set of curated (gene, star_allele, rsid) triples for deduplication
    curated_keys: set[tuple[str, str, str]] = set()
    for sa in curated:
        curated_keys.add((sa["gene"], sa["star_allele"], sa["rsid"]))

    # Build set of curated (gene, rsid, variant_allele) triples — used to
    # detect Stargazer single-SNP alleles that duplicate a curated variant
    # under a different star_allele name (e.g. DPYD *S15 == *13).
    curated_variants: set[tuple[str, str, str]] = set()
    for sa in curated:
        curated_variants.add((sa["gene"], sa["rsid"], sa["variant_allele"]))

    # Identify which Stargazer alleles are single-SNP (only one row per allele)
    sg_by_star: dict[tuple[str, str], int] = {}
    for sa in sg_alleles:
        key = (sa["gene"], sa["star_allele"])
        sg_by_star[key] = sg_by_star.get(key, 0) + 1

    merged = list(curated)
    added = 0
    skipped_orphans = 0
    skipped_duplicates = 0
    for sa in sg_alleles:
        if sa["gene"] not in valid_genes:
            skipped_orphans += 1
            continue
        key = (sa["gene"], sa["star_allele"], sa["rsid"])
        if key in curated_keys:
            continue
        # Skip single-SNP Stargazer alleles that duplicate a curated variant
        star_key = (sa["gene"], sa["star_allele"])
        if sg_by_star.get(star_key, 0) == 1:
            var_key = (sa["gene"], sa["rsid"], sa["variant_allele"])
            if var_key in curated_variants:
                skipped_duplicates += 1
                continue
        curated_keys.add(key)
        merged.append(sa)
        added += 1

    if skipped_orphans:
        log.info("Skipped %d PGx alleles with no gene definition", skipped_orphans)
    if skipped_duplicates:
        log.info(
            "Skipped %d Stargazer alleles that duplicate curated variants "
            "(same gene+rsid+variant_allele under different star_allele name)",
            skipped_duplicates,
        )

    # Validate: warn about remaining single-SNP alleles sharing a variant
    _validate_no_single_snp_duplicates(merged)

    log.info("Merged %d PGx alleles (curated: %d, new: %d, total: %d)",
             len(sg_alleles), len(curated), added, len(merged))
    return merged


def _validate_no_single_snp_duplicates(alleles: list[dict]) -> None:
    """Warn if any single-SNP alleles share (gene, rsid, variant_allele).

    Multi-SNP alleles sharing a variant are expected (e.g. CYP2D6 *2A has
    multiple defining variants, some shared with *2). Only single-SNP alleles
    that overlap pose a double-counting risk.
    """
    by_star: dict[tuple[str, str], list[dict]] = {}
    for a in alleles:
        key = (a["gene"], a["star_allele"])
        by_star.setdefault(key, []).append(a)

    single_snp_map: dict[tuple[str, str, str], list[str]] = {}
    for (gene, star), defs in by_star.items():
        if len(defs) == 1:
            d = defs[0]
            var_key = (gene, d["rsid"], d["variant_allele"])
            single_snp_map.setdefault(var_key, []).append(star)

    issues = 0
    for (gene, rsid, var), stars in sorted(single_snp_map.items()):
        if len(stars) > 1:
            issues += 1
            log.warning(
                "Duplicate single-SNP alleles: %s %s (variant=%s) -> %s",
                gene, rsid, var, ", ".join(sorted(stars)),
            )
    if issues:
        log.warning(
            "%d single-SNP allele duplicate group(s) found — these may cause "
            "double-counting in diplotype assignment", issues,
        )


def _load_pgx_variants() -> list[dict]:
    """Load SNP variant info from pgx_alleles.json for seeding into snps table."""
    if not PGX_ALLELES_JSON.exists():
        return []
    data = json.loads(PGX_ALLELES_JSON.read_text())
    return data.get("variants", [])


async def seed_pgx(session: AsyncSession, *, dry_run: bool = False) -> None:
    """Upsert all PGX definitions into the database."""

    # 1. Gene definitions
    log.info(f"Seeding {len(PGX_GENE_DEFS)} gene definitions...")
    for gd in PGX_GENE_DEFS:
        if dry_run:
            log.info(f"  [dry-run] Gene: {gd['gene']} ({gd['calling_method']})")
            continue
        stmt = pg_insert(PgxGeneDefinition).values(
            gene=gd["gene"],
            calling_method=gd["calling_method"],
            default_allele=gd["default_allele"],
            description=gd["description"],
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["gene"],
            set_={
                "calling_method": stmt.excluded.calling_method,
                "default_allele": stmt.excluded.default_allele,
                "description": stmt.excluded.description,
            },
        )
        await session.execute(stmt)
    if not dry_run:
        await session.commit()
    log.info(f"  {'[dry-run] ' if dry_run else ''}Gene definitions done.")

    # 2. Star allele definitions (curated + pgx_alleles.json merged)
    all_alleles = _merge_pgx_alleles(PGX_STAR_ALLELES)
    log.info(f"Seeding {len(all_alleles)} star allele definitions...")
    if dry_run:
        genes_seen: set[str] = set()
        for sa in all_alleles:
            genes_seen.add(sa["gene"])
        log.info(f"  [dry-run] {len(all_alleles)} alleles across {len(genes_seen)} genes")
    else:
        # Delete existing and re-insert (simpler than upsert for rows without natural PK)
        await session.execute(text("DELETE FROM pgx_star_allele_definitions"))
        for sa in all_alleles:
            session.add(PgxStarAlleleDefinition(
                gene=sa["gene"],
                star_allele=sa["star_allele"],
                rsid=sa["rsid"],
                variant_allele=sa["variant_allele"],
                function=sa["function"],
                activity_score=sa.get("activity_score"),
                clinical_significance=sa.get("clinical_significance"),
                source=sa.get("source"),
            ))
        await session.commit()
    log.info(f"  {'[dry-run] ' if dry_run else ''}Star allele definitions done.")

    # 3. Diplotype phenotype mappings
    log.info(f"Seeding {len(PGX_DIPLOTYPE_PHENOTYPES)} diplotype phenotype mappings...")
    if dry_run:
        genes_seen = set()
        for dp in PGX_DIPLOTYPE_PHENOTYPES:
            genes_seen.add(dp["gene"])
        log.info(f"  [dry-run] {len(PGX_DIPLOTYPE_PHENOTYPES)} mappings across {len(genes_seen)} genes")
    else:
        await session.execute(text("DELETE FROM pgx_diplotype_phenotypes"))
        for dp in PGX_DIPLOTYPE_PHENOTYPES:
            session.add(PgxDiplotypePhenotype(
                gene=dp["gene"],
                function_pair=dp["function_pair"],
                phenotype=dp["phenotype"],
                description=dp.get("description"),
            ))
        await session.commit()
    log.info(f"  {'[dry-run] ' if dry_run else ''}Diplotype phenotype mappings done.")

    # 4. Seed PGX-defining variants into snps table
    sg_variants = _load_pgx_variants()
    if sg_variants:
        log.info(f"Seeding {len(sg_variants)} PGX-defining variants into snps table...")
        if not dry_run:
            seeded = 0
            for v in sg_variants:
                rsid = v["rsid"]
                stmt = pg_insert(Snp).values(
                    rsid=rsid,
                    gene=v.get("gene"),
                    chrom=v.get("chrom"),
                    position=v.get("position"),
                    ref_allele=v.get("ref_allele"),
                    alt_allele=v.get("alt_allele"),
                    functional_class=v.get("functional_class"),
                )
                stmt = stmt.on_conflict_do_nothing(index_elements=["rsid"])
                result = await session.execute(stmt)
                if result.rowcount and result.rowcount > 0:
                    seeded += 1
            await session.commit()
            log.info(f"  Seeded {seeded} new SNP records ({len(sg_variants) - seeded} already existed)")
        else:
            log.info(f"  [dry-run] Would seed up to {len(sg_variants)} SNP records")

    # 5. Seed CPIC/DPWG drug guidelines
    guidelines_data: list[dict] = []
    if GUIDELINES_JSON.exists():
        guidelines_data = json.loads(GUIDELINES_JSON.read_text())
        log.info(f"Seeding {len(guidelines_data)} CPIC/DPWG drug guidelines...")
        if not dry_run:
            await session.execute(text("DELETE FROM pgx_drug_guidelines"))
            for g in guidelines_data:
                session.add(PgxDrugGuideline(
                    source=g["source"],
                    gene=g["gene"],
                    drug=g["drug"],
                    lookup_type=g["lookup_type"],
                    lookup_value=g["lookup_value"],
                    activity_score_min=g.get("activity_score_min"),
                    activity_score_max=g.get("activity_score_max"),
                    recommendation=g["recommendation"],
                    implication=g.get("implication"),
                    strength=g.get("strength"),
                    alternate_drug=g.get("alternate_drug", False),
                    pmid=g.get("pmid"),
                ))
            await session.commit()
        else:
            cpic_count = sum(1 for g in guidelines_data if g["source"] == "CPIC")
            dpwg_count = sum(1 for g in guidelines_data if g["source"] == "DPWG")
            log.info(f"  [dry-run] {cpic_count} CPIC + {dpwg_count} DPWG guidelines")
        log.info(f"  {'[dry-run] ' if dry_run else ''}Drug guidelines done.")
    else:
        log.warning("CPIC/DPWG guidelines JSON not found at %s — skipping", GUIDELINES_JSON)

    # Summary
    log.info("--- PGX Seed Summary ---")
    log.info(f"  Gene definitions:      {len(PGX_GENE_DEFS)}")
    log.info(f"  Star allele defs:      {len(all_alleles)} (curated: {len(PGX_STAR_ALLELES)}, pgx_alleles.json: {len(all_alleles) - len(PGX_STAR_ALLELES)})")
    log.info(f"  Diplotype phenotypes:  {len(PGX_DIPLOTYPE_PHENOTYPES)}")
    unique_rsids = {sa["rsid"] for sa in all_alleles}
    log.info(f"  Unique rsIDs:          {len(unique_rsids)}")
    unique_genes = {sa["gene"] for sa in all_alleles}
    log.info(f"  Genes with alleles:    {len(unique_genes)}")
    log.info(f"  PGX SNP variants:      {len(sg_variants)}")
    log.info(f"  Drug guidelines:       {len(guidelines_data)}")


async def main() -> None:
    parser = argparse.ArgumentParser(description="Seed PGX knowledge-base tables")
    parser.add_argument("--dry-run", action="store_true", help="Print what would be inserted")
    args = parser.parse_args()

    engine = create_async_engine(settings.database_url, echo=False)
    async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    async with async_session() as session:
        await seed_pgx(session, dry_run=args.dry_run)

    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
