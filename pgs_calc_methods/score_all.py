#!/usr/bin/env python3
"""Score reference panel subset for all 14 PGS and compute EUR percentiles."""
import gzip
import json
import os
import subprocess
import sys
import numpy as np
from statistics import NormalDist

FORMATTED_DIR = "/media/dan/500Gb/work2/e5/16d539f0feac65e67a3e67c959512a/formatted"
REF_SUBSET = "/tmp/pgs_ref/ref_pgs_subset"  # .pgen/.pvar.zst/.psam
AFREQ_FILE = "/tmp/pgs_ref/ref_pgs_subset.afreq"
WORK_DIR = "/tmp/pgs_ref"
USER_VCF = "/home/dan/Dropbox/AA_DOCUMENTS/AAA_medical/genetic/raw_genome/DTC7U778.autosomes.vcf.gz"

PGS_IDS = [
    "PGS002249", "PGS000002", "PGS000001", "PGS004228",
    "PGS000018", "PGS004590", "PGS002035", "PGS000003",
    "PGS002280", "PGS005170", "PGS000039", "PGS003992",
    "PGS004008", "PGS002753",
]

USER_RESULTS = {
    "PGS002249": {"score": 140.6, "pct": 87},
    "PGS000002": {"score": 0.9513, "pct": 84},
    "PGS000001": {"score": 0.7931, "pct": 77},
    "PGS004228": {"score": -19.45, "pct": 73},
    "PGS000018": {"score": -0.3186, "pct": 51},
    "PGS004590": {"score": -3.215, "pct": 49},
    "PGS002035": {"score": -0.00009423, "pct": 20},
    "PGS000003": {"score": 0.07720, "pct": 17},
    "PGS002280": {"score": 4.745, "pct": 15},
    "PGS005170": {"score": 2.150, "pct": 8},
    "PGS000039": {"score": 12.53, "pct": 8},
    "PGS003992": {"score": -0.2424, "pct": 4},
    "PGS004008": {"score": -0.3733, "pct": 3},
    "PGS002753": {"score": -0.5427, "pct": "< 1"},
}

PGSCALC_SUMS = {
    "PGS000001": 0.40124899999999997,
    "PGS000002": 0.524557,
    "PGS000003": -0.1570722,
    "PGS000018": 9.15401,
    "PGS000039": 1.285808,
    "PGS002035": -9.423409999999999e-05,
    "PGS002249": 108.7561,
    "PGS002280": 2.5178000000000003,
    "PGS002753": -0.5350113,
    "PGS003992": -0.1337651,
    "PGS004008": -0.1040576,
    "PGS004228": -4.0769,
    "PGS004590": -0.0406,
    "PGS005170": 2.3138199999999998,
}

os.makedirs(WORK_DIR, exist_ok=True)


def load_ref_alleles():
    """Load REF alleles from the subset afreq file."""
    ref_alleles = {}  # (chr, pos) -> REF
    print("Loading reference alleles from afreq...")
    with open(AFREQ_FILE) as f:
        f.readline()  # skip header
        for line in f:
            parts = line.split('\t', 4)
            chrom = parts[0]
            id_parts = parts[1].split(':')
            pos = id_parts[1]
            ref_alleles[(chrom, pos)] = parts[2]
    print(f"  Loaded REF alleles for {len(ref_alleles)} positions")
    return ref_alleles


def create_scoring_file(pgs_id):
    """Create PLINK2 scoring file with both ID orderings."""
    formatted = os.path.join(FORMATTED_DIR, f"normalised_{pgs_id}_hmPOS_GRCh37.txt.gz")
    scoring_file = os.path.join(WORK_DIR, f"{pgs_id}_scoring.tsv")
    n_variants = 0
    variants = []

    n_skipped = 0
    with gzip.open(formatted, 'rt') as fin, open(scoring_file, 'w') as fout:
        header = fin.readline().strip().split('\t')
        col = {name: i for i, name in enumerate(header)}
        fout.write("ID\teffect_allele\tweight\n")
        for line in fin:
            parts = line.strip().split('\t')
            if len(parts) < 5:
                n_skipped += 1
                continue
            chrom = parts[col['chr_name']]
            pos = parts[col['chr_position']]
            effect = parts[col['effect_allele']]
            other = parts[col.get('other_allele', 3)]
            weight_s = parts[col['effect_weight']]
            if not chrom or not pos:
                n_skipped += 1
                continue
            try:
                weight = float(weight_s)
            except ValueError:
                n_skipped += 1
                continue
            fout.write(f"{chrom}:{pos}:{effect}:{other}\t{effect}\t{weight_s}\n")
            fout.write(f"{chrom}:{pos}:{other}:{effect}\t{effect}\t{weight_s}\n")
            variants.append((chrom, pos, effect, other, weight))
            n_variants += 1
    if n_skipped:
        print(f"  Skipped {n_skipped} rows with missing chr/pos or bad weight")

    return scoring_file, n_variants, variants


def score_reference(pgs_id, scoring_file):
    """Score the reference panel SUBSET (fast, ~2.2GB pgen)."""
    cmd = [
        "docker", "run", "--rm",
        "-v", f"{WORK_DIR}:/work",
        "ghcr.io/pgscatalog/plink2:2.00a5.10", "plink2",
        "--pfile", "/work/ref_pgs_subset", "vzs",
        "--score", f"/work/{os.path.basename(scoring_file)}", "header-read", "cols=+scoresums", "no-mean-imputation",
        "--out", f"/work/{pgs_id}_ref",
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    if result.returncode != 0:
        print(f"  PLINK2 error: {result.stderr[-500:]}")
        return None
    return os.path.join(WORK_DIR, f"{pgs_id}_ref.sscore")


def parse_sscore_eur(sscore_file):
    """Parse sscore file and return EUR scores array."""
    eur_scores = []
    with open(sscore_file) as f:
        header = f.readline().strip().split('\t')
        score_col = header.index("weight_SUM")
        pop_col = header.index("SuperPop")
        for line in f:
            parts = line.strip().split('\t')
            if parts[pop_col] == "EUR":
                eur_scores.append(float(parts[score_col]))
    return np.array(eur_scores)


def main():
    sys.stdout.reconfigure(line_buffering=True)

    # Load REF alleles
    ref_alleles = load_ref_alleles()

    # Load user VCF positions
    print("Loading user VCF positions...")
    user_positions = set()
    proc = subprocess.Popen(
        ['zcat', USER_VCF], stdout=subprocess.PIPE, text=True, bufsize=1024*1024
    )
    for line in proc.stdout:
        if line[0] == '#':
            continue
        tab1 = line.index('\t')
        tab2 = line.index('\t', tab1 + 1)
        user_positions.add((line[:tab1], line[tab1+1:tab2]))
    proc.wait()
    print(f"  User VCF positions: {len(user_positions)}")

    all_results = {}

    for pgs_id in PGS_IDS:
        print(f"\n{'='*60}")
        print(f"Processing {pgs_id}...")

        # Create scoring file
        print(f"  Creating scoring file...")
        scoring_file, n_variants, variants = create_scoring_file(pgs_id)
        print(f"  {n_variants} variants")

        # Score reference panel subset
        print(f"  Scoring reference panel subset...")
        sscore_file = score_reference(pgs_id, scoring_file)

        # Clean up scoring file to save disk
        if os.path.exists(scoring_file):
            os.remove(scoring_file)

        if sscore_file is None or not os.path.exists(sscore_file):
            print(f"  ERROR: Scoring failed")
            continue

        # Parse EUR scores
        eur_scores = parse_sscore_eur(sscore_file)
        eur_mean = float(np.mean(eur_scores))
        eur_std = float(np.std(eur_scores))
        print(f"  EUR (n={len(eur_scores)}): mean={eur_mean:.6f}, std={eur_std:.6f}")

        # Compute hom-ref correction for user
        pgscalc_sum = PGSCALC_SUMS.get(pgs_id, 0)
        correction = 0.0
        n_missing = 0
        n_eff_ref = 0
        n_eff_alt = 0

        for chrom, pos, effect, other, weight in variants:
            if (chrom, pos) in user_positions:
                continue
            n_missing += 1
            ref = ref_alleles.get((chrom, pos))
            if ref is None:
                continue
            if effect == ref:
                correction += 2 * weight
                n_eff_ref += 1
            else:
                n_eff_alt += 1

        corrected_score = pgscalc_sum + correction
        pct_missing = n_missing / n_variants * 100 if n_variants > 0 else 0

        # Compute percentiles
        if eur_std > 0:
            z = (corrected_score - eur_mean) / eur_std
            normal_pct = NormalDist().cdf(z) * 100
            empirical_pct = float(np.sum(eur_scores <= corrected_score) / len(eur_scores) * 100)
        else:
            z = normal_pct = empirical_pct = 0

        user = USER_RESULTS.get(pgs_id, {})
        print(f"  Missing: {n_missing}/{n_variants} ({pct_missing:.0f}%), eff=REF: {n_eff_ref}, eff=ALT: {n_eff_alt}")
        print(f"  pgsc_calc SUM: {pgscalc_sum:.6f}, correction: {correction:.6f}")
        print(f"  Corrected score: {corrected_score:.6f}")
        print(f"  z={z:.3f}, empirical_pct={empirical_pct:.1f}%")
        print(f"  User: score={user.get('score')}, pct={user.get('pct')}")

        all_results[pgs_id] = {
            "n_variants": n_variants,
            "pgscalc_sum": pgscalc_sum,
            "correction": correction,
            "corrected_score": corrected_score,
            "eur_mean": eur_mean,
            "eur_std": eur_std,
            "z": z,
            "empirical_pct": empirical_pct,
            "user_score": user.get('score'),
            "user_pct": user.get('pct'),
            "n_missing": n_missing,
            "n_eff_ref": n_eff_ref,
        }

    # Save results
    with open(os.path.join(WORK_DIR, "results.json"), 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    # Print comparison table
    print(f"\n\n{'='*140}")
    print("COMPARISON: User Software vs pgsc_calc + Empirical EUR Reference")
    print(f"{'='*140}")
    hdr = f"{'PGS':<12} {'Variants':>10} {'User Score':>12} {'pgsc_calc':>12} {'Corrected':>12} {'EUR Mean':>12} {'EUR Std':>10} {'Emp%':>6} {'User%':>6} {'Match?':>7}"
    print(hdr)
    print("-" * len(hdr))

    for pgs_id in PGS_IDS:
        r = all_results.get(pgs_id)
        if not r:
            continue
        emp_pct = f"{r['empirical_pct']:.0f}"
        user_pct = str(r['user_pct'])
        # Compare user score vs corrected
        if isinstance(r['user_score'], (int, float)):
            score_diff = abs(r['user_score'] - r['corrected_score'])
            if r['eur_std'] > 0:
                diff_z = score_diff / r['eur_std']
            else:
                diff_z = 0
            match = "~" if diff_z < 0.5 else "!!" if diff_z > 2 else "?"
        else:
            match = "?"
        print(f"{pgs_id:<12} {r['n_variants']:>10,} {r['user_score']:>12.4f} {r['pgscalc_sum']:>12.4f} {r['corrected_score']:>12.4f} {r['eur_mean']:>12.4f} {r['eur_std']:>10.4f} {emp_pct:>6} {user_pct:>6} {match:>7}")


if __name__ == "__main__":
    main()
