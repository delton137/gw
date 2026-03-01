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

    Curated definitions take priority: if a (gene, star_allele, rsid) triple
    exists in both, the curated version is kept.
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

    merged = list(curated)
    added = 0
    skipped_orphans = 0
    for sa in sg_alleles:
        if sa["gene"] not in valid_genes:
            skipped_orphans += 1
            continue
        key = (sa["gene"], sa["star_allele"], sa["rsid"])
        if key in curated_keys:
            continue
        curated_keys.add(key)
        merged.append(sa)
        added += 1

    if skipped_orphans:
        log.info("Skipped %d PGx alleles with no gene definition", skipped_orphans)

    log.info("Merged %d PGx alleles (curated: %d, new: %d, total: %d)",
             len(sg_alleles), len(curated), added, len(merged))
    return merged


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
