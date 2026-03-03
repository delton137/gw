"""Centralized loaders for static data files (pgx_alleles.json, etc.).

Caches are module-level dicts, populated on first access. The underlying JSON
is parsed at most once per genome build.
"""

from __future__ import annotations

import json
from functools import cache
from pathlib import Path

_DATA_DIR = Path(__file__).parent.parent / "data"


@cache
def _load_pgx_alleles_raw() -> dict:
    """Parse pgx_alleles.json once and cache the raw dict."""
    pgx_path = _DATA_DIR / "pgx_alleles.json"
    if not pgx_path.exists():
        return {"variants": []}
    return json.loads(pgx_path.read_text())


# ---------------------------------------------------------------------------
# PGX positions — used by analysis.py (for VCF annotation) and pgx_matcher.py
# ---------------------------------------------------------------------------

_PGX_POS_LIST_CACHE: dict[str, list[tuple[str, str, int]]] = {}
_PGX_POS_DICT_CACHE: dict[str, dict[str, tuple[str, int]]] = {}


def load_pgx_positions_list(genome_build: str = "GRCh38") -> list[tuple[str, str, int]]:
    """Return [(rsid, chrom, position), ...] from pgx_alleles.json.

    Used by analysis.py for VCF position-based rsid annotation.
    """
    if genome_build in _PGX_POS_LIST_CACHE:
        return _PGX_POS_LIST_CACHE[genome_build]

    pos_field = "position_grch37" if genome_build == "GRCh37" else "position"
    data = _load_pgx_alleles_raw()
    _PGX_POS_LIST_CACHE[genome_build] = [
        (v["rsid"], str(v["chrom"]), int(v[pos_field]))
        for v in data.get("variants", [])
        if v.get("rsid") and v.get("chrom") and v.get(pos_field)
    ]
    return _PGX_POS_LIST_CACHE[genome_build]


def load_pgx_positions_dict(genome_build: str = "GRCh38") -> dict[str, tuple[str, int]]:
    """Return {rsid: (chrom, position)} from pgx_alleles.json.

    Used by pgx_matcher.py for position-based genotype lookup.
    """
    if genome_build in _PGX_POS_DICT_CACHE:
        return _PGX_POS_DICT_CACHE[genome_build]

    pos_field = "position_grch37" if genome_build == "GRCh37" else "position"
    data = _load_pgx_alleles_raw()
    cache: dict[str, tuple[str, int]] = {}
    for v in data.get("variants", []):
        rsid = v.get("rsid")
        chrom = v.get("chrom")
        pos = v.get(pos_field)
        if rsid and chrom and pos:
            cache[rsid] = (str(chrom), int(pos))
    _PGX_POS_DICT_CACHE[genome_build] = cache
    return cache


def load_pgx_ref_alleles() -> dict[str, str]:
    """Return {rsid: ref_allele} from pgx_alleles.json.

    Used by pgx_matcher.py for reference allele comparison.
    """
    data = _load_pgx_alleles_raw()
    return {
        v["rsid"]: v["ref_allele"]
        for v in data.get("variants", [])
        if v.get("rsid") and v.get("ref_allele")
    }


# Cache the ref alleles since the function rebuilds the dict each call
_pgx_ref_alleles_cache: dict[str, str] | None = None


def load_pgx_ref_alleles_cached() -> dict[str, str]:
    """Cached version of load_pgx_ref_alleles."""
    global _pgx_ref_alleles_cache
    if _pgx_ref_alleles_cache is None:
        _pgx_ref_alleles_cache = load_pgx_ref_alleles()
    return _pgx_ref_alleles_cache
