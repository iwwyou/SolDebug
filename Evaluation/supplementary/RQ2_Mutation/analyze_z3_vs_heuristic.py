#!/usr/bin/env python3
"""
Compare Z3-based results with heuristic-based results
"""
import pandas as pd
from pathlib import Path

# Load both result sets
z3_results = pd.read_csv("Evaluation/RQ2_Z3_Results/rq2_z3_results.csv")
heuristic_results = pd.read_csv("Evaluation/RQ2_Results/rq2_batch_results.csv")

# Filter heuristic results to only the 7 focused contracts
FOCUSED_CONTRACTS = [
    "GovStakingStorage_c",
    "GreenHouse_c",
    "HubPool_c",
    "Lock_c",
    "LockupContract_c",
    "PoolKeeper_c",
    "ThorusBond_c"
]

heuristic_results = heuristic_results[heuristic_results['contract'].isin(FOCUSED_CONTRACTS)]

print("=" * 80)
print("Z3 vs HEURISTIC COMPARISON")
print("=" * 80)

print(f"\nDataset sizes:")
print(f"  Z3: {len(z3_results)} experiments")
print(f"  Heuristic: {len(heuristic_results)} experiments")

# Overall statistics
print(f"\n" + "=" * 80)
print("OVERALL STATISTICS")
print("=" * 80)

for method, df in [("Z3", z3_results), ("Heuristic", heuristic_results)]:
    print(f"\n{method}:")
    print(f"  Success rate: {df['success'].mean()*100:.1f}%")

    # Separate by pattern
    overlap = df[df['pattern'] == 'overlap']
    diff = df[df['pattern'] == 'diff']

    # Calculate finite ratios
    if len(overlap) > 0:
        overlap_finite_ratio = (overlap['finite_count'] / overlap['num_intervals']).mean() if overlap['num_intervals'].sum() > 0 else 0
    else:
        overlap_finite_ratio = 0

    if len(diff) > 0:
        diff_finite_ratio = (diff['finite_count'] / diff['num_intervals']).mean() if diff['num_intervals'].sum() > 0 else 0
    else:
        diff_finite_ratio = 0

    print(f"  Overlap finite ratio: {overlap_finite_ratio*100:.1f}%")
    print(f"  Diff finite ratio: {diff_finite_ratio*100:.1f}%")

    # F90 statistics (filter out inf values)
    # Convert f90 to numeric, handling very large numbers
    overlap_f90 = pd.to_numeric(overlap['f90'], errors='coerce')
    diff_f90 = pd.to_numeric(diff['f90'], errors='coerce')

    overlap_finite_f90 = overlap_f90[~overlap_f90.isna() & (overlap_f90 != float('inf'))]
    diff_finite_f90 = diff_f90[~diff_f90.isna() & (diff_f90 != float('inf'))]

    # Also filter out MAX_UINT256-like values
    MAX_THRESHOLD = 1e70
    overlap_finite_f90 = overlap_finite_f90[overlap_finite_f90 < MAX_THRESHOLD]
    diff_finite_f90 = diff_finite_f90[diff_finite_f90 < MAX_THRESHOLD]

    if len(overlap_finite_f90) > 0:
        print(f"  Overlap avg F90: {overlap_finite_f90.mean():.2e}")
    else:
        print(f"  Overlap avg F90: inf (no finite cases)")

    if len(diff_finite_f90) > 0:
        print(f"  Diff avg F90: {diff_finite_f90.mean():.2e}")
    else:
        print(f"  Diff avg F90: inf (no finite cases)")

# Per-contract comparison
print(f"\n" + "=" * 80)
print("PER-CONTRACT COMPARISON")
print("=" * 80)

for contract in FOCUSED_CONTRACTS:
    print(f"\n[{contract}]")

    z3_contract = z3_results[z3_results['contract'] == contract]
    heur_contract = heuristic_results[heuristic_results['contract'] == contract]

    if len(heur_contract) == 0:
        print(f"  No heuristic data available")
        continue

    # Compare overlap pattern
    z3_overlap = z3_contract[z3_contract['pattern'] == 'overlap']
    heur_overlap = heur_contract[heur_contract['pattern'] == 'overlap']

    if len(z3_overlap) > 0 and len(heur_overlap) > 0:
        z3_finite = (z3_overlap['finite_count'] / z3_overlap['num_intervals']).mean() if z3_overlap['num_intervals'].sum() > 0 else 0
        heur_finite = (heur_overlap['finite_count'] / heur_overlap['num_intervals']).mean() if heur_overlap['num_intervals'].sum() > 0 else 0

        print(f"  Overlap finite ratio: Z3={z3_finite*100:.0f}% vs Heuristic={heur_finite*100:.0f}%")

    # Compare diff pattern
    z3_diff = z3_contract[z3_contract['pattern'] == 'diff']
    heur_diff = heur_contract[heur_contract['pattern'] == 'diff']

    if len(z3_diff) > 0 and len(heur_diff) > 0:
        z3_finite = (z3_diff['finite_count'] / z3_diff['num_intervals']).mean() if z3_diff['num_intervals'].sum() > 0 else 0
        heur_finite = (heur_diff['finite_count'] / heur_diff['num_intervals']).mean() if heur_diff['num_intervals'].sum() > 0 else 0

        print(f"  Diff finite ratio: Z3={z3_finite*100:.0f}% vs Heuristic={heur_finite*100:.0f}%")

# Delta comparison
print(f"\n" + "=" * 80)
print("DELTA COMPARISON")
print("=" * 80)

for delta in [1, 3, 6, 10, 15]:
    print(f"\n[Delta = {delta}]")

    z3_delta = z3_results[z3_results['delta'] == delta]
    heur_delta = heuristic_results[heuristic_results['delta'] == delta]

    for method, df in [("Z3", z3_delta), ("Heur", heur_delta)]:
        if len(df) > 0:
            finite_ratio = (df['finite_count'] / df['num_intervals']).mean() if df['num_intervals'].sum() > 0 else 0
            print(f"  {method}: {finite_ratio*100:.1f}% finite")

print("\n" + "=" * 80)
print("SUMMARY")
print("=" * 80)

z3_total_finite = (z3_results['finite_count'] / z3_results['num_intervals']).mean() if z3_results['num_intervals'].sum() > 0 else 0
heur_total_finite = (heuristic_results['finite_count'] / heuristic_results['num_intervals']).mean() if heuristic_results['num_intervals'].sum() > 0 else 0

print(f"\nOverall finite ratio:")
print(f"  Z3: {z3_total_finite*100:.1f}%")
print(f"  Heuristic: {heur_total_finite*100:.1f}%")

z3_f90 = pd.to_numeric(z3_results['f90'], errors='coerce')
heur_f90 = pd.to_numeric(heuristic_results['f90'], errors='coerce')

MAX_THRESHOLD = 1e70
z3_finite_f90 = z3_f90[~z3_f90.isna() & (z3_f90 != float('inf')) & (z3_f90 < MAX_THRESHOLD)]
heur_finite_f90 = heur_f90[~heur_f90.isna() & (heur_f90 != float('inf')) & (heur_f90 < MAX_THRESHOLD)]

print(f"\nF90 (finite cases only, excluding divergent):")
if len(z3_finite_f90) > 0:
    print(f"  Z3: {z3_finite_f90.mean():.2e} (median: {z3_finite_f90.median():.2e})")
else:
    print(f"  Z3: No finite cases")

if len(heur_finite_f90) > 0:
    print(f"  Heuristic: {heur_finite_f90.mean():.2e} (median: {heur_finite_f90.median():.2e})")
else:
    print(f"  Heuristic: No finite cases")

print("\n" + "=" * 80)
