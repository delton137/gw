#!/usr/bin/env python3
"""Score HGDP+1kGP reference panel for all 14 PGS and compute EUR percentiles.

Also computes the user's corrected score (with hom-ref corrections).
"""
import gzip
import json
import os
import subprocess
import sys
import numpy as np
from statistics import NormalDist

FORMATTED_DIR = "/media/dan/500Gb/work2/e5/16d539f0feac65e67a3e67c959512a/formatted"
REF_PANEL = "/media/dan/500Gb/work/ancestry/ref_extracted/GRCh37_HGDP+1kGP_ALL"
AFREQ_FILE = "/tmp/pgs_score/pgs_freq.afreq"  # Only for PGS005170
WORK_DIR = "/tmp/pgs_ref"
USER_VCF = "/home/dan/Dropbox/AA_DOCUMENTS/AAA_medical/genetic/raw_genome/DTC7U778.autosomes.vcf.gz"

PGS_IDS = [
    "PGS002249", "PGS000002", "PGS000001", "PGS004228",
    "PGS000018", "PGS004590", "PGS002035", "PGS000003",
    "PGS002280", "PGS005170", "PGS000039", "PGS003992",
    "PGS004008", "PGS002753",
]

# User's software results
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

# pgsc_calc raw scores (from aggregated_scores.txt.gz)
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


def create_scoring_file(pgs_id):
    """Create PLINK2 scoring file with both ID orderings from formatted PGS file."""
    formatted = os.path.join(FORMATTED_DIR, f"normalised_{pgs_id}_hmPOS_GRCh37.txt.gz")
    if not os.path.exists(formatted):
        # Try alternative location
        alt = f"/media/dan/500Gb/work2/07/0d7dc30872f144a20c5fb4efa34707/normalised_{pgs_id}_hmPOS_GRCh37.txt.gz"
        if os.path.exists(alt):
            formatted = alt
        else:
            print(f"  ERROR: Formatted file not found for {pgs_id}")
            return None, 0

    scoring_file = os.path.join(WORK_DIR, f"{pgs_id}_scoring.tsv")
    n_variants = 0

    with gzip.open(formatted, 'rt') as fin, open(scoring_file, 'w') as fout:
        header = fin.readline()  # skip header
        fout.write("ID\teffect_allele\tweight\n")
        for line in fin:
            parts = line.strip().split('\t')
            chrom = parts[0]
            pos = parts[1]
            effect = parts[2]
            other = parts[3]
            weight = parts[4]
            # Write both orderings so one matches the reference panel pvar
            fout.write(f"{chrom}:{pos}:{effect}:{other}\t{effect}\t{weight}\n")
            fout.write(f"{chrom}:{pos}:{other}:{effect}\t{effect}\t{weight}\n")
            n_variants += 1

    return scoring_file, n_variants


def score_reference_panel(pgs_id, scoring_file):
    """Run PLINK2 to score the reference panel."""
    out_prefix = os.path.join(WORK_DIR, f"{pgs_id}_ref")

    cmd = [
        "docker", "run", "--rm",
        "-v", f"{os.path.dirname(REF_PANEL)}:/ref:ro",
        "-v", f"{WORK_DIR}:/work",
        "ghcr.io/pgscatalog/plink2:2.00a5.10", "plink2",
        "--pfile", f"/ref/{os.path.basename(REF_PANEL)}", "vzs",
        "--score", f"/work/{os.path.basename(scoring_file)}", "header-read", "cols=+scoresums", "no-mean-imputation",
        "--out", f"/work/{pgs_id}_ref",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    if result.returncode != 0:
        print(f"  PLINK2 error: {result.stderr[-500:]}")
        return None

    sscore_file = f"{out_prefix}.sscore"
    if not os.path.exists(sscore_file):
        print(f"  ERROR: sscore file not found")
        return None

    return sscore_file


def parse_sscore(sscore_file):
    """Parse PLINK2 sscore file and return per-ancestry distributions."""
    scores_by_pop = {}
    with open(sscore_file) as f:
        header = f.readline().strip().split('\t')
        score_col = header.index("weight_SUM")
        pop_col = header.index("SuperPop") if "SuperPop" in header else None
        for line in f:
            parts = line.strip().split('\t')
            score = float(parts[score_col])
            pop = parts[pop_col] if pop_col is not None else "ALL"
            scores_by_pop.setdefault(pop, []).append(score)

    result = {}
    for pop, scores in scores_by_pop.items():
        arr = np.array(scores)
        result[pop] = {
            "n": len(arr),
            "mean": float(np.mean(arr)),
            "std": float(np.std(arr)),
            "min": float(np.min(arr)),
            "max": float(np.max(arr)),
        }
    return result


def main():
    # Load user VCF positions (for hom-ref correction)
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

    # Process each PGS
    all_results = {}
    for pgs_id in PGS_IDS:
        print(f"\n{'='*60}")
        print(f"Processing {pgs_id}...")

        # Check if reference panel scores already exist (e.g., PGS005170)
        existing_sscore = os.path.join(WORK_DIR, f"{pgs_id}_ref.sscore")
        if pgs_id == "PGS005170" and os.path.exists("/tmp/pgs_score/ref_scores.sscore"):
            existing_sscore = "/tmp/pgs_score/ref_scores.sscore"
            print(f"  Using existing reference panel scores")

        if not os.path.exists(existing_sscore) or pgs_id != "PGS005170":
            # Create scoring file
            print(f"  Creating scoring file...")
            scoring_file, n_variants = create_scoring_file(pgs_id)
            if scoring_file is None:
                continue
            print(f"  {n_variants} variants (×2 orderings = {n_variants*2} entries)")

            # Score reference panel
            print(f"  Scoring reference panel...")
            sscore_file = score_reference_panel(pgs_id, scoring_file)
            if sscore_file is None:
                continue

            # Clean up large scoring file to save disk
            os.remove(scoring_file)
        else:
            sscore_file = existing_sscore

        # Parse reference panel scores
        dists = parse_sscore(sscore_file)
        eur = dists.get("EUR", {})
        if not eur:
            print(f"  ERROR: No EUR data")
            continue

        print(f"  EUR: mean={eur['mean']:.6f}, std={eur['std']:.6f} (n={eur['n']})")

        # Compute corrected user score with hom-ref correction
        formatted = os.path.join(FORMATTED_DIR, f"normalised_{pgs_id}_hmPOS_GRCh37.txt.gz")
        if not os.path.exists(formatted):
            formatted = f"/media/dan/500Gb/work2/07/0d7dc30872f144a20c5fb4efa34707/normalised_{pgs_id}_hmPOS_GRCh37.txt.gz"

        # Read PGS variants and compute hom-ref correction
        pgs_variants = {}
        with gzip.open(formatted, 'rt') as f:
            f.readline()  # skip header
            for line in f:
                parts = line.strip().split('\t')
                key = (parts[0], parts[1])
                pgs_variants[key] = (parts[2], parts[3], float(parts[4]))

        # Load reference allele info from afreq (if available) or use a simpler approach
        # For the correction, we need REF at each position from the reference panel
        # We already have the sscore from the reference panel - let's use the ref panel afreq
        afreq_file = os.path.join(WORK_DIR, f"{pgs_id}_ref.afreq")

        # Run PLINK2 --freq if not done yet
        if not os.path.exists(afreq_file):
            # Create ID list for extraction
            id_file = os.path.join(WORK_DIR, f"{pgs_id}_ids.txt")
            with open(id_file, 'w') as f:
                for (chrom, pos), (effect, other, weight) in pgs_variants.items():
                    f.write(f"{chrom}:{pos}:{effect}:{other}\n")
                    f.write(f"{chrom}:{pos}:{other}:{effect}\n")

            cmd = [
                "docker", "run", "--rm",
                "-v", f"{os.path.dirname(REF_PANEL)}:/ref:ro",
                "-v", f"{WORK_DIR}:/work",
                "ghcr.io/pgscatalog/plink2:2.00a5.10", "plink2",
                "--pfile", f"/ref/{os.path.basename(REF_PANEL)}", "vzs",
                "--extract", f"/work/{pgs_id}_ids.txt",
                "--freq",
                "--out", f"/work/{pgs_id}_ref",
            ]
            print(f"  Extracting REF alleles from reference panel...")
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
            os.remove(id_file)

        # Parse afreq to get REF alleles
        ref_alleles = {}
        if os.path.exists(afreq_file):
            with open(afreq_file) as f:
                f.readline()  # skip header
                for line in f:
                    parts = line.strip().split('\t')
                    chrom = parts[0]
                    id_parts = parts[1].split(':')
                    pos = id_parts[1]
                    ref_alleles[(chrom, pos)] = parts[2]  # REF column

        # Compute hom-ref correction
        pgscalc_sum = PGSCALC_SUMS.get(pgs_id, 0)
        correction = 0.0
        n_missing = 0
        n_eff_ref = 0
        n_eff_alt = 0
        n_unknown = 0

        for key, (effect, other, weight) in pgs_variants.items():
            if key in user_positions:
                continue  # Present in VCF, already scored
            n_missing += 1
            if key not in ref_alleles:
                n_unknown += 1
                continue
            if effect == ref_alleles[key]:
                correction += 2 * weight
                n_eff_ref += 1
            else:
                n_eff_alt += 1

        corrected_score = pgscalc_sum + correction
        print(f"  Missing hom-ref: {n_missing} (effect=REF: {n_eff_ref}, effect=ALT: {n_eff_alt}, unknown: {n_unknown})")
        print(f"  pgsc_calc SUM: {pgscalc_sum:.6f}")
        print(f"  Hom-ref correction: {correction:.6f}")
        print(f"  Corrected score: {corrected_score:.6f}")

        # Compute z-score and percentile
        if eur['std'] > 0:
            z = (corrected_score - eur['mean']) / eur['std']
            pct = NormalDist().cdf(z) * 100

            # Also compute empirical percentile
            eur_scores = []
            with open(sscore_file) as f:
                header = f.readline().strip().split('\t')
                score_col = header.index("weight_SUM")
                pop_col = header.index("SuperPop") if "SuperPop" in header else None
                for line in f:
                    parts = line.strip().split('\t')
                    if pop_col and parts[pop_col] == "EUR":
                        eur_scores.append(float(parts[score_col]))
            eur_arr = np.array(eur_scores)
            empirical_pct = float(np.sum(eur_arr <= corrected_score) / len(eur_arr) * 100)
        else:
            z = 0
            pct = 50
            empirical_pct = 50

        print(f"  z-score: {z:.4f}")
        print(f"  Normal percentile: {pct:.1f}%")
        print(f"  Empirical percentile: {empirical_pct:.1f}%")

        user = USER_RESULTS.get(pgs_id, {})
        print(f"  User's software: score={user.get('score')}, percentile={user.get('pct')}")

        all_results[pgs_id] = {
            "pgscalc_sum": pgscalc_sum,
            "correction": correction,
            "corrected_score": corrected_score,
            "eur_mean": eur['mean'],
            "eur_std": eur['std'],
            "z": z,
            "normal_pct": pct,
            "empirical_pct": empirical_pct,
            "user_score": user.get('score'),
            "user_pct": user.get('pct'),
            "n_variants": len(pgs_variants),
            "n_missing": n_missing,
            "n_eff_ref": n_eff_ref,
        }

    # Save results
    with open(os.path.join(WORK_DIR, "results.json"), 'w') as f:
        json.dump(all_results, f, indent=2, default=str)

    # Print comparison table
    print(f"\n\n{'='*120}")
    print("COMPARISON TABLE")
    print(f"{'='*120}")
    print(f"{'PGS':<12} {'Variants':>10} {'pgsc_calc':>12} {'Corrected':>12} {'User Score':>12} {'EUR Mean':>12} {'EUR Std':>10} {'Emp Pct':>8} {'User Pct':>9}")
    print(f"{'-'*12} {'-'*10} {'-'*12} {'-'*12} {'-'*12} {'-'*12} {'-'*10} {'-'*8} {'-'*9}")

    for pgs_id in PGS_IDS:
        r = all_results.get(pgs_id)
        if not r:
            continue
        pct_str = f"{r['empirical_pct']:.1f}%"
        user_pct = r['user_pct']
        user_pct_str = f"{user_pct}%" if isinstance(user_pct, (int, float)) else str(user_pct)
        print(f"{pgs_id:<12} {r['n_variants']:>10,} {r['pgscalc_sum']:>12.4f} {r['corrected_score']:>12.4f} {r['user_score']:>12.4f} {r['eur_mean']:>12.4f} {r['eur_std']:>10.4f} {pct_str:>8} {user_pct_str:>9}")


if __name__ == "__main__":
    main()
