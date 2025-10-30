#!/usr/bin/env python3
"""
Batch RQ2 experiment runner
Runs all experiments defined in experiment_index.json
"""
import sys
import json
import csv
import time
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

# Import run_single_experiment from run_rq2_simple
from run_rq2_simple import run_single_experiment, extract_intervals

# Configuration
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
ANNOTATION_DIR = PROJECT_ROOT / "dataset/json/annotation"
RESULTS_DIR = SCRIPT_DIR / "RQ2_Results"
OUTPUT_CSV = RESULTS_DIR / "rq2_batch_results.csv"

# Contracts to test
CONTRACTS = [
    "Lock_c",
    "GovStakingStorage_c",
    "GreenHouse_c",
    "HubPool_c",
    "Claim_c",
    "Dai_c",
    "LockupContract_c",
    "PoolKeeper_c",
    "ThorusBond_c",
]

DELTAS = [1, 3, 6, 10, 15]
PATTERNS = ["overlap", "diff"]

def main():
    print("=" * 70)
    print("RQ2 BATCH EXPERIMENT RUNNER")
    print("=" * 70)

    RESULTS_DIR.mkdir(exist_ok=True)

    # Collect all results
    all_results = []
    total_experiments = len(CONTRACTS) * len(DELTAS) * len(PATTERNS)

    print(f"\nTotal experiments: {total_experiments}")
    print(f"Contracts: {len(CONTRACTS)}")
    print(f"Deltas: {DELTAS}")
    print(f"Patterns: {PATTERNS}")
    print()

    experiment_num = 0

    for contract in CONTRACTS:
        annot_file = ANNOTATION_DIR / f"{contract}_annot.json"

        if not annot_file.exists():
            print(f"[WARNING] {annot_file} not found, skipping")
            continue

        print(f"\n[CONTRACT] {contract}")
        print("-" * 60)

        for delta in DELTAS:
            for pattern in PATTERNS:
                experiment_num += 1
                exp_id = f"{contract}_d{delta}_{pattern}"

                print(f"  [{experiment_num}/{total_experiments}] {exp_id}...", end=" ")

                try:
                    # Run experiment
                    result = run_single_experiment(annot_file, delta, pattern)

                    # Extract intervals
                    intervals = extract_intervals(result['results'])

                    # Compute metrics
                    finite_count = sum(1 for v in intervals.values() if v['finite'])
                    infinite_count = len(intervals) - finite_count

                    widths = [v['width'] for v in intervals.values() if v['finite']]
                    avg_width = sum(widths) / len(widths) if widths else float('inf')
                    max_width = max(widths) if widths else float('inf')

                    # Calculate F90 (90th percentile)
                    if widths:
                        widths_sorted = sorted(widths)
                        f90_idx = int(len(widths_sorted) * 0.9)
                        f90 = widths_sorted[f90_idx] if f90_idx < len(widths_sorted) else widths_sorted[-1]
                    else:
                        f90 = float('inf')

                    # Store result
                    all_results.append({
                        'contract': contract,
                        'delta': delta,
                        'pattern': pattern,
                        'execution_time': result['execution_time'],
                        'num_variables': result['num_variables'],
                        'num_intervals': len(intervals),
                        'finite_count': finite_count,
                        'infinite_count': infinite_count,
                        'avg_width': avg_width,
                        'max_width': max_width,
                        'f90': f90,
                        'success': True
                    })

                    print(f"OK ({result['execution_time']:.2f}s, F90={f90:.1f})")

                except Exception as e:
                    print(f"FAILED: {e}")
                    all_results.append({
                        'contract': contract,
                        'delta': delta,
                        'pattern': pattern,
                        'execution_time': 0,
                        'num_variables': 0,
                        'num_intervals': 0,
                        'finite_count': 0,
                        'infinite_count': 0,
                        'avg_width': float('inf'),
                        'max_width': float('inf'),
                        'f90': float('inf'),
                        'success': False,
                        'error': str(e)
                    })

    # Save results to CSV
    print(f"\n{'='*70}")
    print(f"Saving results to {OUTPUT_CSV}...")

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        if all_results:
            fieldnames = list(all_results[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)

    print(f"[DONE] Saved {len(all_results)} results")

    # Quick summary
    print(f"\n{'='*70}")
    print("SUMMARY")
    print("=" * 70)

    successful = [r for r in all_results if r['success']]
    failed = [r for r in all_results if not r['success']]

    print(f"Successful: {len(successful)}/{len(all_results)}")
    print(f"Failed: {len(failed)}/{len(all_results)}")

    if successful:
        total_time = sum(r['execution_time'] for r in successful)
        avg_time = total_time / len(successful)
        print(f"Total execution time: {total_time:.2f}s")
        print(f"Average time per experiment: {avg_time:.2f}s")

        # Compare overlap vs diff
        overlap_results = [r for r in successful if r['pattern'] == 'overlap']
        diff_results = [r for r in successful if r['pattern'] == 'diff']

        if overlap_results and diff_results:
            overlap_f90 = [r['f90'] for r in overlap_results if r['f90'] != float('inf')]
            diff_f90 = [r['f90'] for r in diff_results if r['f90'] != float('inf')]

            if overlap_f90 and diff_f90:
                avg_overlap = sum(overlap_f90) / len(overlap_f90)
                avg_diff = sum(diff_f90) / len(diff_f90)

                print(f"\nF90 Comparison:")
                print(f"  Overlap (avg): {avg_overlap:.1f}")
                print(f"  Diff (avg): {avg_diff:.1f}")
                print(f"  Ratio (diff/overlap): {avg_diff/avg_overlap:.2f}x")

if __name__ == "__main__":
    start = time.time()
    main()
    end = time.time()
    print(f"\nTotal time: {end - start:.2f}s")
