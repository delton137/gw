#!/usr/bin/env python3
"""
Stage 1: Literature Triage via Claude Code CLI.

Classifies papers, extracts summaries, and lists rsids mentioned.
Each paper lives in its own folder containing the pdf/md and output JSONs.
Claude reads the paper via Read tool and writes result.json via Write tool.

Usage:
    python stage1_triage.py --reorganize              # One-time: move flat files into folders
    python stage1_triage.py --tag v1 --limit 100      # Pilot run
    python stage1_triage.py --tag v1                   # Full run
    python stage1_triage.py --tag v1 --concurrency 8   # More parallelism
    python stage1_triage.py --tag v1 --reprocess-failures
"""

from __future__ import annotations

import argparse
import csv
import json
import logging
import re
import signal
import subprocess
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%H:%M:%S",
)
log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Graceful shutdown
# ---------------------------------------------------------------------------

_shutdown_requested = False
_running_processes: dict[int, subprocess.Popen] = {}


def _signal_handler(signum, frame):
    global _shutdown_requested
    if not _shutdown_requested:
        _shutdown_requested = True
        print("\n\nShutdown requested. Finishing current papers...", file=sys.stderr)
        for process in list(_running_processes.values()):
            if process.poll() is None:
                try:
                    process.send_signal(signal.SIGINT)
                except Exception:
                    pass
    else:
        print("\nForce quit.", file=sys.stderr)
        sys.exit(1)


signal.signal(signal.SIGINT, _signal_handler)

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

PAPERS_DIR = Path("/media/dan/500Gb/snpedia_pdfs")
METADATA_CSV = Path(__file__).parent / "snpedia_papers_metadata.csv"
PROMPT_FILE = Path(__file__).parent / "stage1_system_prompt.md"

MODEL = "haiku"
CONCURRENCY = 4
MAX_TURNS = 25
TIMEOUT = 180  # 3 min per paper

VALID_CLASSIFICATIONS = {
    "association_study", "meta_analysis", "review",
    "functional_study", "case_report", "methods", "other",
}


# ---------------------------------------------------------------------------
# Metadata
# ---------------------------------------------------------------------------

def load_metadata() -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    with open(METADATA_CSV, newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            doi = row.get("doi", "").strip()
            if doi:
                lookup[doi] = {
                    "pmid": row.get("pmid", "").strip() or None,
                    "title": row.get("title", "").strip() or None,
                    "year": int(row["year"]) if row.get("year", "").strip() else None,
                    "journal": row.get("journal", "").strip() or None,
                    "authors": row.get("authors", "").strip() or None,
                }
    return lookup


# ---------------------------------------------------------------------------
# File helpers
# ---------------------------------------------------------------------------

def doi_to_dirname(doi: str) -> str:
    return doi.replace("/", "--")


def dirname_to_doi(dirname: str) -> str:
    return dirname.replace("--", "/")


def reorganize_flat_to_folders():
    """Move flat pdf/md files into per-paper subdirectories (one-time)."""
    files = list(PAPERS_DIR.glob("*.*"))
    stems: dict[str, list[Path]] = {}
    for f in files:
        if f.is_file() and f.suffix in (".pdf", ".md"):
            stems.setdefault(f.stem, []).append(f)

    log.info(f"Reorganizing {len(stems)} papers into folders...")
    moved = 0
    for stem, paths in stems.items():
        folder = PAPERS_DIR / stem
        folder.mkdir(exist_ok=True)
        for p in paths:
            dest = folder / f"paper{p.suffix}"
            if not dest.exists():
                p.rename(dest)
                moved += 1
    log.info(f"Moved {moved} files into {len(stems)} folders.")


def discover_paper_dirs() -> list[Path]:
    """Find paper dirs by globbing for paper.md and paper.pdf directly."""
    dirs = set()
    for pattern in ("*/paper.md", "*/paper.pdf"):
        for p in PAPERS_DIR.glob(pattern):
            dirs.add(p.parent)
    return sorted(dirs)


def get_paper_file(paper_dir: Path) -> Path | None:
    md = paper_dir / "paper.md"
    if md.exists():
        return md
    pdf = paper_dir / "paper.pdf"
    if pdf.exists():
        return pdf
    return None


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_and_fix(data: dict) -> tuple[dict, list[str]]:
    warnings = []

    cls = data.get("classification", "")
    if cls and cls.lower() in VALID_CLASSIFICATIONS:
        data["classification"] = cls.lower()
    elif cls:
        warnings.append(f"invalid classification '{cls}'")
        data["classification"] = "other"

    hoa = data.get("has_original_associations")
    if not isinstance(hoa, bool):
        data["has_original_associations"] = bool(hoa) if hoa is not None else False

    rsids = data.get("rsids_mentioned", [])
    if isinstance(rsids, list):
        clean = []
        for r in rsids:
            if isinstance(r, str):
                m = re.match(r"(rs\d+)", r.strip().lower())
                if m:
                    clean.append(m.group(1))
        data["rsids_mentioned"] = sorted(set(clean))
    else:
        data["rsids_mentioned"] = []

    # Validate genes — uppercase, deduplicate
    genes = data.get("genes_mentioned", [])
    if isinstance(genes, list):
        data["genes_mentioned"] = sorted(set(
            g.strip().upper() for g in genes if isinstance(g, str) and g.strip()
        ))
    else:
        data["genes_mentioned"] = []

    # Validate variants — ensure each is a dict with gene + variant
    variants = data.get("variants_mentioned", [])
    if isinstance(variants, list):
        clean_variants = []
        for v in variants:
            if isinstance(v, dict) and v.get("gene") and v.get("variant"):
                clean_variants.append({
                    "gene": str(v["gene"]).strip().upper(),
                    "variant": str(v["variant"]).strip(),
                })
        data["variants_mentioned"] = clean_variants
    else:
        data["variants_mentioned"] = []

    traits = data.get("traits_studied", [])
    if isinstance(traits, list):
        data["traits_studied"] = sorted(set(
            t.strip() for t in traits if isinstance(t, str) and t.strip()
        ))
    else:
        data["traits_studied"] = []

    val = data.get("sample_size_approx")
    if val is not None:
        try:
            data["sample_size_approx"] = int(float(str(val)))
            if data["sample_size_approx"] <= 0:
                data["sample_size_approx"] = None
        except (ValueError, TypeError):
            data["sample_size_approx"] = None

    if data.get("classification") in ("review", "methods", "case_report") and data.get("has_original_associations"):
        warnings.append("classification/association mismatch — overriding")
        data["has_original_associations"] = False

    return data, warnings


# ---------------------------------------------------------------------------
# Claude CLI call
# ---------------------------------------------------------------------------

def call_claude(paper_path: Path, paper_dir: Path, doi: str) -> dict:
    """Call Claude Code CLI to read a paper and write result.json.

    Claude reads the file via Read tool and writes result.json via Write tool.
    All paths are absolute for reliability.
    """
    abs_paper = str(paper_path.resolve())
    abs_result = str((paper_dir / "result.json").resolve())

    # Clean any stale result.json
    result_path = paper_dir / "result.json"
    if result_path.exists():
        result_path.unlink()

    user_prompt = (
        f"Paper DOI: {doi}\n"
        f"Read the file at {abs_paper} and write result.json to {abs_result}"
    )

    cmd = [
        "claude",
        "--print",
        "--output-format", "json",
        "--model", MODEL,
        "--max-turns", str(MAX_TURNS),
        "--system-prompt-file", str(PROMPT_FILE),
        "--allowedTools", "Read", "Write",
        "--dangerously-skip-permissions",
        user_prompt,
    ]

    thread_id = threading.current_thread().ident
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    _running_processes[thread_id] = process

    try:
        stdout, stderr = process.communicate(timeout=TIMEOUT)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()
        raise RuntimeError(f"Timeout processing {doi}")
    finally:
        _running_processes.pop(thread_id, None)

    if process.returncode != 0:
        raise RuntimeError(f"CLI error for {doi}: {stderr[:300]}")

    # Parse CLI envelope for usage stats
    cli_output = json.loads(stdout)
    usage = {
        "input_tokens": cli_output.get("usage", {}).get("input_tokens", 0),
        "output_tokens": cli_output.get("usage", {}).get("output_tokens", 0),
        "cost_usd": cli_output.get("total_cost_usd", 0),
        "duration_ms": cli_output.get("duration_ms", 0),
    }

    # Read result.json written by the agent
    if not result_path.exists():
        raise RuntimeError(
            f"Agent did not write result.json for {doi}. "
            f"Output: {cli_output.get('result', '')[:300]}"
        )

    # Retry for filesystem flush
    for attempt in range(3):
        try:
            extraction = json.loads(result_path.read_text())
            break
        except json.JSONDecodeError:
            if attempt < 2:
                time.sleep(0.5)
            else:
                raise RuntimeError(f"Invalid JSON in result.json for {doi}")

    # Clean up result.json (we save our own tagged version)
    result_path.unlink(missing_ok=True)

    return {"extraction": extraction, **usage}


# ---------------------------------------------------------------------------
# Process single paper
# ---------------------------------------------------------------------------

def process_paper(paper_dir: Path, metadata: dict | None, tag: str) -> dict | None:
    if _shutdown_requested:
        return None

    output_path = paper_dir / f"stage1_{tag}.json"
    if output_path.exists():
        return None

    paper_path = get_paper_file(paper_dir)
    if paper_path is None:
        return None

    doi = dirname_to_doi(paper_dir.name)

    try:
        cli_result = call_claude(paper_path, paper_dir, doi)
        result = cli_result["extraction"]
        result, warnings = validate_and_fix(result)
        if warnings:
            result["_validation_warnings"] = warnings

        result["doi"] = doi
        if metadata:
            for key in ("pmid", "title", "year", "journal", "authors"):
                result[key] = metadata.get(key)
        else:
            for key in ("pmid", "title", "year", "journal", "authors"):
                result[key] = None

        result["content_type"] = "pdf" if paper_path.suffix == ".pdf" else "markdown"
        result["tag"] = tag
        result["input_tokens"] = cli_result["input_tokens"]
        result["output_tokens"] = cli_result["output_tokens"]
        result["cost_usd"] = cli_result["cost_usd"]
        result["duration_ms"] = cli_result["duration_ms"]

        output_path.write_text(json.dumps(result, indent=2, ensure_ascii=False))
        return result

    except Exception as e:
        log.error(f"Error {doi}: {e}")
        error_path = paper_dir / f"stage1_{tag}.error.json"
        error_path.write_text(json.dumps({"doi": doi, "error": str(e)}, indent=2))
        return None


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def run(tag: str, limit: int | None = None, concurrency: int = CONCURRENCY, reprocess_failures: bool = False):
    log.info("Loading metadata...")
    metadata_lookup = load_metadata()
    log.info(f"Loaded metadata for {len(metadata_lookup)} papers")

    log.info("Discovering paper directories...")
    all_dirs = discover_paper_dirs()
    log.info(f"Found {len(all_dirs)} paper directories")

    if reprocess_failures:
        for d in all_dirs:
            err = d / f"stage1_{tag}.error.json"
            if err.exists():
                err.unlink()

    dirs = [d for d in all_dirs if not (d / f"stage1_{tag}.json").exists()]
    already_done = len(all_dirs) - len(dirs)
    if already_done:
        log.info(f"Skipping {already_done} already processed for tag '{tag}'")

    if limit:
        dirs = dirs[:limit]

    if not dirs:
        log.info("Nothing to process.")
        return

    log.info(f"Processing {len(dirs)} papers | tag='{tag}' | concurrency={concurrency} | max_turns={MAX_TURNS}")

    stats = {
        "processed": 0, "classifications": {}, "has_associations": 0,
        "total_rsids": 0, "total_cost": 0.0, "errors": 0,
        "content_types": {"markdown": 0, "pdf": 0},
    }
    t0 = time.time()
    lock = threading.Lock()

    def process_and_track(paper_dir: Path):
        if _shutdown_requested:
            return
        doi = dirname_to_doi(paper_dir.name)
        metadata = metadata_lookup.get(doi)
        title_short = (metadata.get("title", "") or doi)[:60] if metadata else doi[:60]

        result = process_paper(paper_dir, metadata, tag)
        if result is None:
            return

        with lock:
            stats["processed"] += 1
            n = stats["processed"]
            ct = result.get("content_type", "unknown")
            stats["content_types"][ct] = stats["content_types"].get(ct, 0) + 1

            cls = result.get("classification", "unknown")
            stats["classifications"][cls] = stats["classifications"].get(cls, 0) + 1
            n_rsids = len(result.get("rsids_mentioned", []))
            has_assoc = result.get("has_original_associations", False)
            if has_assoc:
                stats["has_associations"] += 1
            stats["total_rsids"] += n_rsids
            stats["total_cost"] += result.get("cost_usd", 0)
            duration_s = result.get("duration_ms", 0) / 1000

            n_variants = len(result.get("variants_mentioned", []))
            summary = result.get("summary", "")[:150]
            assoc_flag = "ASSOC" if has_assoc else "     "
            log.info(
                f"[{n}/{len(dirs)}] {assoc_flag} {cls:<20s} "
                f"{n_rsids:>3d} rsids  {n_variants:>2d} variants  {duration_s:>5.1f}s  "
                f"{title_short}"
            )
            log.info(f"    {summary}")

            if n % 20 == 0:
                elapsed = time.time() - t0
                rate = n / elapsed
                remaining = (len(dirs) - n) / rate if rate > 0 else 0
                log.info(
                    f"--- {n}/{len(dirs)} done "
                    f"({rate:.1f}/s, ~{remaining/60:.0f}m left) | "
                    f"assoc: {stats['has_associations']} | "
                    f"rsids: {stats['total_rsids']} | "
                    f"errors: {stats['errors']} | "
                    f"cost: ${stats['total_cost']:.2f}"
                )

    with ThreadPoolExecutor(max_workers=concurrency) as executor:
        futures = {executor.submit(process_and_track, d): d for d in dirs}
        for future in as_completed(futures):
            if _shutdown_requested:
                executor.shutdown(wait=False, cancel_futures=True)
                break
            try:
                future.result()
            except Exception as e:
                with lock:
                    stats["errors"] += 1
                log.error(f"Unhandled: {e}")

    elapsed = time.time() - t0
    log.info("=" * 60)
    log.info(f"Stage 1 complete: {stats['processed']} papers in {elapsed:.0f}s")
    log.info(f"Content types: {json.dumps(stats['content_types'])}")
    log.info(f"Classifications: {json.dumps(stats['classifications'], indent=2)}")
    log.info(f"Papers with original associations: {stats['has_associations']}")
    log.info(f"Total rsids extracted: {stats['total_rsids']}")
    log.info(f"Errors: {stats['errors']}")
    log.info(f"Total cost: ${stats['total_cost']:.2f}")


def main():
    parser = argparse.ArgumentParser(description="Stage 1: Literature triage via Claude Code CLI")
    parser.add_argument("--tag", type=str, help="Tag for output files (required)")
    parser.add_argument("--limit", type=int, help="Process only first N papers")
    parser.add_argument("--concurrency", type=int, default=CONCURRENCY)
    parser.add_argument("--reprocess-failures", action="store_true")
    parser.add_argument("--reorganize", action="store_true", help="Move flat files into folders (one-time)")
    args = parser.parse_args()

    if args.reorganize:
        reorganize_flat_to_folders()
        return

    if not args.tag:
        parser.error("--tag is required (e.g. --tag v1)")

    run(tag=args.tag, limit=args.limit, concurrency=args.concurrency, reprocess_failures=args.reprocess_failures)


if __name__ == "__main__":
    main()
