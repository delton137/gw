"""Scan all PGS Catalog scores and classify their license fields."""

import csv
import sys
import time

import httpx

API_URL = "https://www.pgscatalog.org/rest/score/all"
BOILERPLATE_PREFIX = "PGS obtained from the Catalog should be cited appropriately"
PAGE_SIZE = 100


def classify_license(text: str) -> str:
    if not text:
        return "none"
    low = text.lower()
    if low.startswith(BOILERPLATE_PREFIX.lower()):
        return "standard"
    if "cc0" in low or "public domain" in low:
        return "cc0"
    if "non-commercial" in low or "cc-by-nc" in low or "cc by-nc" in low:
        return "cc-by-nc"
    if "cc-by" in low or "cc by" in low or "creative commons attribution" in low:
        return "cc-by"
    return "other"


def main():
    client = httpx.Client(timeout=30, headers={"Accept": "application/json"})
    offset = 0
    total = None
    scores = []

    while True:
        resp = client.get(API_URL, params={"limit": PAGE_SIZE, "offset": offset, "format": "json"})
        resp.raise_for_status()
        data = resp.json()

        if total is None:
            total = data["count"]
            print(f"Total scores in catalog: {total}")

        results = data.get("results", [])
        if not results:
            break

        for s in results:
            pub = s.get("publication") or {}
            scores.append({
                "id": s.get("id", ""),
                "name": s.get("name", ""),
                "trait": s.get("trait_reported", ""),
                "variants": s.get("variants_number", 0),
                "license": s.get("license", ""),
                "license_class": classify_license(s.get("license", "")),
                "first_author": pub.get("firstauthor", ""),
                "journal": pub.get("journal", ""),
                "year": (pub.get("date_publication") or "")[:4],
            })

        offset += PAGE_SIZE
        print(f"  fetched {min(offset, total)}/{total}", end="\r")
        if offset >= total:
            break
        time.sleep(0.5)

    print()

    # Summary
    from collections import Counter
    counts = Counter(s["license_class"] for s in scores)
    print("\n=== License Classification Summary ===")
    for cls, n in counts.most_common():
        print(f"  {cls:15s} {n:>5d}")

    # Non-standard scores
    non_standard = [s for s in scores if s["license_class"] != "standard"]
    if non_standard:
        print(f"\n=== Non-Standard Licensed Scores ({len(non_standard)}) ===")
        print(f"{'ID':<12} {'Variants':>8}  {'Class':<10} {'Trait':<50} License Text")
        print("-" * 140)
        for s in sorted(non_standard, key=lambda x: -(x["variants"] or 0)):
            trait = (s["trait"] or "")[:50]
            lic = (s["license"] or "")[:80]
            print(f"{s['id']:<12} {s['variants'] or 0:>8}  {s['license_class']:<10} {trait:<50} {lic}")

    # Dump CSV
    csv_path = "pgs_license_scan.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=["id", "name", "trait", "variants", "license_class", "license", "first_author", "journal", "year"])
        w.writeheader()
        w.writerows(sorted(scores, key=lambda x: x["id"]))
    print(f"\nFull results written to {csv_path}")


if __name__ == "__main__":
    main()
