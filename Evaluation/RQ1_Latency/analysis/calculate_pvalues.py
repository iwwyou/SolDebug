"""
Calculate p-values for SolQDebug vs Remix comparison at interval 0.
Uses Wilcoxon signed-rank test for paired samples.

Usage:
    python calculate_pvalues.py
"""

import csv
from pathlib import Path
from scipy import stats
import numpy as np

RESULTS_DIR = Path(__file__).parent
NUM_RUNS = 5


def load_solqdebug_runs():
    """Load SolQDebug individual run data for interval 0."""
    # {contract: [run1, run2, run3, run4, run5]}
    data = {}

    for run_id in range(1, NUM_RUNS + 1):
        filepath = RESULTS_DIR / f"solqdebug_results_interval0_run{run_id}.csv"

        if not filepath.exists():
            print(f"Warning: {filepath} not found")
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row['success'] == 'True':
                    contract = row['contract_name']
                    latency = float(row['latency_s'])

                    if contract not in data:
                        data[contract] = []
                    data[contract].append(latency)

    return data


def load_remix_runs():
    """Load Remix individual run data."""
    # {contract: [run1, run2, run3, run4, run5]}
    data = {}

    for run_id in range(1, NUM_RUNS + 1):
        filepath = RESULTS_DIR / f"remix_results_run{run_id}.csv"

        if not filepath.exists():
            print(f"Warning: {filepath} not found")
            continue

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('success', 'True') == 'True' and row.get('pure_debug_time_ms'):
                    try:
                        contract = row['contract_name']
                        latency_ms = float(row['pure_debug_time_ms'])
                        latency_s = latency_ms / 1000.0

                        if contract not in data:
                            data[contract] = []
                        data[contract].append(latency_s)
                    except (ValueError, KeyError):
                        continue

    return data


def calculate_pvalues():
    """Calculate p-values using Wilcoxon signed-rank test."""
    print("Loading data...")

    solqdebug_data = load_solqdebug_runs()
    remix_data = load_remix_runs()

    print(f"  SolQDebug contracts: {len(solqdebug_data)}")
    print(f"  Remix contracts: {len(remix_data)}")

    # Name mapping for matching
    name_mapping = {
        'LockupContract': 'LockupContract_c.sol',
        'Edentoken': 'EdenToken',
        'OptimisticGrants': 'OptimisiticGrants',
        'AvatarArtMarketPlace': 'AvatarArtMarketplace',
    }

    results = []

    print("\n" + "=" * 80)
    print(f"{'Contract':<35} {'SolQDebug(s)':<14} {'Remix(s)':<14} {'p-value':<12} {'Sig'}")
    print("=" * 80)

    for contract in sorted(solqdebug_data.keys()):
        solq_runs = solqdebug_data[contract]

        # Find matching Remix data
        remix_contract = name_mapping.get(contract, contract)
        remix_runs = remix_data.get(remix_contract)

        if not remix_runs:
            # Try original name
            remix_runs = remix_data.get(contract)

        if not remix_runs or len(solq_runs) != NUM_RUNS or len(remix_runs) != NUM_RUNS:
            print(f"{contract:<35} {'N/A':<14} {'N/A':<14} {'N/A':<12} -")
            continue

        solq_mean = np.mean(solq_runs)
        remix_mean = np.mean(remix_runs)

        # Wilcoxon signed-rank test
        # alternative='less' because we expect SolQDebug < Remix
        try:
            statistic, p_value = stats.wilcoxon(solq_runs, remix_runs, alternative='less')
        except Exception as e:
            print(f"{contract:<35} {solq_mean:<14.4f} {remix_mean:<14.2f} {'Error':<12} -")
            continue

        # Significance level
        if p_value < 0.001:
            sig = "***"
        elif p_value < 0.01:
            sig = "**"
        elif p_value < 0.05:
            sig = "*"
        else:
            sig = "ns"

        print(f"{contract:<35} {solq_mean:<14.4f} {remix_mean:<14.2f} {p_value:<12.6f} {sig}")

        results.append({
            'contract': contract,
            'solqdebug_mean': solq_mean,
            'solqdebug_std': np.std(solq_runs, ddof=1),
            'remix_mean': remix_mean,
            'remix_std': np.std(remix_runs, ddof=1),
            'p_value': p_value,
            'significance': sig
        })

    print("=" * 80)
    print("\nSignificance levels: *** p<0.001, ** p<0.01, * p<0.05, ns: not significant")

    # Save results
    output_file = RESULTS_DIR / "pvalue_results.csv"
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'contract', 'solqdebug_mean', 'solqdebug_std',
            'remix_mean', 'remix_std', 'p_value', 'significance'
        ])
        writer.writeheader()
        writer.writerows(results)

    print(f"\nResults saved to: {output_file}")

    # Summary statistics
    significant_count = sum(1 for r in results if r['significance'] != 'ns')
    total_count = len(results)

    print(f"\n" + "=" * 80)
    print("SUMMARY")
    print("=" * 80)
    print(f"Total contracts compared: {total_count}")
    print(f"Statistically significant (p<0.05): {significant_count} ({100*significant_count/total_count:.1f}%)")

    # Overall test: Are SolQDebug latencies consistently lower?
    all_solq = [r['solqdebug_mean'] for r in results]
    all_remix = [r['remix_mean'] for r in results]

    overall_stat, overall_p = stats.wilcoxon(all_solq, all_remix, alternative='less')
    print(f"\nOverall Wilcoxon test (n={len(all_solq)} contracts):")
    print(f"  p-value: {overall_p:.2e}")
    if overall_p < 0.001:
        print(f"  Result: SolQDebug is significantly faster than Remix (p < 0.001)")

    return results


if __name__ == "__main__":
    print("=" * 80)
    print("P-Value Calculation: SolQDebug vs Remix (Interval 0)")
    print("=" * 80)

    calculate_pvalues()
