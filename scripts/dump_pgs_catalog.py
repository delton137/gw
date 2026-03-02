"""Download full PGS Catalog metadata: scores + performance metrics → CSV.

Outputs: pgs_catalog_full.csv

Usage:
    python -m scripts.dump_pgs_catalog
"""

from __future__ import annotations

import asyncio
import csv
import logging
import sys
from collections import defaultdict

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

API_BASE = "https://www.pgscatalog.org/rest"
PAGE_SIZE = 100  # max allowed by PGS Catalog API


async def paginate(client: httpx.AsyncClient, url: str) -> list[dict]:
    """Paginate through a PGS Catalog REST endpoint with retry on 503."""
    results = []
    page_url = f"{url}{'&' if '?' in url else '?'}limit={PAGE_SIZE}"
    while page_url:
        for attempt in range(5):
            resp = await client.get(page_url)
            if resp.status_code == 503:
                wait = 5 * (attempt + 1)
                log.warning(f"  503 at offset {len(results)}, retrying in {wait}s...")
                await asyncio.sleep(wait)
                continue
            resp.raise_for_status()
            break
        else:
            raise RuntimeError(f"Failed after 5 retries at {page_url}")
        data = resp.json()
        results.extend(data.get("results", []))
        page_url = data.get("next")
        if len(results) % 500 == 0 or not page_url:
            log.info(f"  fetched {len(results)} / {data.get('count', '?')}")
        await asyncio.sleep(0.3)  # rate limit courtesy
    return results


async def main() -> None:
    async with httpx.AsyncClient(timeout=60) as client:
        # ── 1. Fetch all scores ──────────────────────────────────────────
        log.info("Fetching all PGS scores...")
        scores = await paginate(client, f"{API_BASE}/score/all")
        log.info(f"Total scores: {len(scores)}")

        # ── 2. Fetch all performance metrics ─────────────────────────────
        log.info("Fetching all performance metrics...")
        perfs = await paginate(client, f"{API_BASE}/performance/all")
        log.info(f"Total performance entries: {len(perfs)}")

    # ── 3. Index performance by PGS ID ───────────────────────────────
    perf_by_pgs: dict[str, list[dict]] = defaultdict(list)
    for p in perfs:
        pgs_id = p.get("associated_pgs_id")
        if pgs_id:
            perf_by_pgs[pgs_id].append(p)

    # ── 4. Build rows ────────────────────────────────────────────────
    rows = []
    for score in scores:
        pgs_id = score.get("id", "")
        trait_name = score.get("trait_reported", "")
        efo_ids = ", ".join(
            t.get("id", "") for t in (score.get("trait_efo") or [])
        )
        n_variants = score.get("variants_number", "")

        pub = score.get("publication") or {}
        pmid = pub.get("PMID") or pub.get("pmid") or ""
        doi = pub.get("doi", "")
        pub_title = pub.get("title", "")
        pub_authors = pub.get("firstauthor", "")
        pub_journal = pub.get("journal", "")
        pub_date = pub.get("date_publication", "")

        license_text = score.get("license", "")

        ancestry_dev = ", ".join(
            s.get("ancestry_broad", "")
            for sg in (score.get("samples_development") or [])
            for s in ([sg] if isinstance(sg, dict) else [])
        )

        # Collect performance metrics for this score
        score_perfs = perf_by_pgs.get(pgs_id, [])
        has_perf = len(score_perfs) > 0

        # Extract best metrics across all validation studies
        best_auc = None
        best_auroc = None
        best_c_index = None
        best_or = None
        best_hr = None
        best_beta = None
        all_metric_names = set()
        n_perf_entries = len(score_perfs)
        n_with_metrics = 0

        for perf in score_perfs:
            metrics = perf.get("performance_metrics") or []
            if metrics:
                n_with_metrics += 1
            for m in metrics:
                name = m.get("name_short") or m.get("name") or ""
                est = m.get("estimate")
                all_metric_names.add(name)

                if est is None:
                    continue

                try:
                    val = float(est)
                except (ValueError, TypeError):
                    continue

                name_lower = name.lower()
                if "auroc" in name_lower or name_lower == "auc":
                    if best_auroc is None or val > best_auroc:
                        best_auroc = val
                elif name_lower == "c-index" or "c-statistic" in name_lower:
                    if best_c_index is None or val > best_c_index:
                        best_c_index = val
                elif name_lower == "or" or "odds ratio" in name_lower:
                    if best_or is None or val > best_or:
                        best_or = val
                elif name_lower == "hr" or "hazard" in name_lower:
                    if best_hr is None or val > best_hr:
                        best_hr = val
                elif name_lower == "beta" or name_lower == "β":
                    if best_beta is None or abs(val) > abs(best_beta):
                        best_beta = val

        rows.append({
            "pgs_id": pgs_id,
            "trait_reported": trait_name,
            "trait_efo_ids": efo_ids,
            "n_variants": n_variants,
            "development_ancestry": ancestry_dev,
            "pmid": str(pmid),
            "doi": doi,
            "first_author": pub_authors,
            "journal": pub_journal,
            "pub_date": pub_date,
            "pub_title": pub_title,
            "license": license_text,
            "n_performance_entries": n_perf_entries,
            "n_entries_with_metrics": n_with_metrics,
            "has_case_control_data": "yes" if best_auroc is not None or best_c_index is not None else "no",
            "best_auroc": best_auroc,
            "best_c_index": best_c_index,
            "best_odds_ratio": best_or,
            "best_hazard_ratio": best_hr,
            "best_beta": best_beta,
            "all_metric_types": ", ".join(sorted(all_metric_names)) if all_metric_names else "",
        })

    # ── 5. Write CSV ─────────────────────────────────────────────────
    rows.sort(key=lambda r: r["pgs_id"])
    outfile = "pgs_catalog_full.csv"
    fieldnames = list(rows[0].keys())
    with open(outfile, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)

    # Summary stats
    with_auroc = sum(1 for r in rows if r["best_auroc"] is not None)
    with_cindex = sum(1 for r in rows if r["best_c_index"] is not None)
    with_any_perf = sum(1 for r in rows if r["n_entries_with_metrics"] > 0)
    log.info(f"\nWritten {len(rows)} scores to {outfile}")
    log.info(f"  {with_auroc} have AUROC/AUC")
    log.info(f"  {with_cindex} have C-index")
    log.info(f"  {with_any_perf} have any performance metrics")
    log.info(f"  {len(rows) - with_any_perf} have NO metrics at all")


if __name__ == "__main__":
    asyncio.run(main())
