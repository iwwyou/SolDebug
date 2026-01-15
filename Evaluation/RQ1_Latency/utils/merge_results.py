"""
Merge benchmark results and calculate statistics.
Combines multiple run results into a single CSV with mean, std, 95% CI.

Usage:
    python merge_results.py --solqdebug
    python merge_results.py --remix
    python merge_results.py --all
"""

import sys
import csv
import math
from pathlib import Path
from collections import defaultdict

RESULTS_DIR = Path(__file__).parent
INTERVALS = [0, 2, 5, 10]
NUM_RUNS = 5  # Changed from 10 to 5 for statistical comparison


def calculate_statistics(values):
    """Calculate mean, std, 95% CI, median for a list of values."""
    if not values:
        return None, None, None, None

    n = len(values)
    mean = sum(values) / n

    if n > 1:
        variance = sum((x - mean) ** 2 for x in values) / (n - 1)
        std = math.sqrt(variance)
        # 95% CI = mean +/- 1.96 * (std / sqrt(n))
        ci_95 = 1.96 * (std / math.sqrt(n))
    else:
        std = 0.0
        ci_95 = 0.0

    sorted_values = sorted(values)
    if n % 2 == 0:
        median = (sorted_values[n//2 - 1] + sorted_values[n//2]) / 2
    else:
        median = sorted_values[n//2]

    return mean, std, ci_95, median


def merge_solqdebug_results():
    """Merge SolQDebug results from all intervals and runs."""
    print("\n" + "="*60)
    print("Merging SolQDebug Results")
    print("="*60)

    # Collect all results: {(contract, interval): [latencies]}
    all_data = defaultdict(list)
    files_found = 0
    files_missing = []

    for interval in INTERVALS:
        for run_id in range(1, NUM_RUNS + 1):
            filename = f"solqdebug_results_interval{interval}_run{run_id}.csv"
            filepath = RESULTS_DIR / filename

            if not filepath.exists():
                files_missing.append(filename)
                continue

            files_found += 1

            with open(filepath, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row['success'] == 'True':
                        key = (row['contract_name'], int(row['interval']))
                        all_data[key].append(float(row['latency_s']))

    print(f"Files found: {files_found}")
    if files_missing:
        print(f"Files missing: {len(files_missing)}")
        if len(files_missing) <= 10:
            for f in files_missing:
                print(f"  - {f}")

    # Calculate statistics and write output
    output_file = RESULTS_DIR / "solqdebug_merged_results.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Contract', 'Interval', 'Runs',
            'Mean_Latency_s', 'Std_s', 'CI95_s', 'Median_s',
            'Min_s', 'Max_s'
        ])

        # Sort by contract name then interval
        for (contract, interval) in sorted(all_data.keys()):
            latencies = all_data[(contract, interval)]
            mean, std, ci_95, median = calculate_statistics(latencies)

            writer.writerow([
                contract, interval, len(latencies),
                f"{mean:.6f}" if mean else "",
                f"{std:.6f}" if std else "",
                f"{ci_95:.6f}" if ci_95 else "",
                f"{median:.6f}" if median else "",
                f"{min(latencies):.6f}" if latencies else "",
                f"{max(latencies):.6f}" if latencies else ""
            ])

    print(f"\nOutput saved to: {output_file}")
    print(f"Total contract-interval combinations: {len(all_data)}")

    return output_file


def merge_remix_results():
    """Merge Remix results from all runs."""
    print("\n" + "="*60)
    print("Merging Remix Results")
    print("="*60)

    # Collect all results: {contract: [latencies]}
    all_data = defaultdict(list)
    files_found = 0
    files_missing = []

    for run_id in range(1, NUM_RUNS + 1):
        filename = f"remix_results_run{run_id}.csv"
        filepath = RESULTS_DIR / filename

        if not filepath.exists():
            files_missing.append(filename)
            continue

        files_found += 1

        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if row.get('success', 'True') == 'True' and row.get('pure_debug_time_ms'):
                    try:
                        latency_ms = float(row['pure_debug_time_ms'])
                        latency_s = latency_ms / 1000.0
                        contract = row['contract_name']
                        all_data[contract].append(latency_s)
                    except (ValueError, KeyError):
                        continue

    print(f"Files found: {files_found}")
    if files_missing:
        print(f"Files missing: {len(files_missing)}")
        if len(files_missing) <= 10:
            for f in files_missing:
                print(f"  - {f}")

    # Calculate statistics and write output
    output_file = RESULTS_DIR / "remix_merged_results.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Contract', 'Runs',
            'Mean_PureDebug_s', 'Std_s', 'CI95_s', 'Median_s',
            'Min_s', 'Max_s'
        ])

        for contract in sorted(all_data.keys()):
            latencies = all_data[contract]
            mean, std, ci_95, median = calculate_statistics(latencies)

            writer.writerow([
                contract, len(latencies),
                f"{mean:.6f}" if mean else "",
                f"{std:.6f}" if std else "",
                f"{ci_95:.6f}" if ci_95 else "",
                f"{median:.6f}" if median else "",
                f"{min(latencies):.6f}" if latencies else "",
                f"{max(latencies):.6f}" if latencies else ""
            ])

    print(f"\nOutput saved to: {output_file}")
    print(f"Total contracts: {len(all_data)}")

    return output_file


def create_combined_comparison():
    """Create combined comparison table (SolQDebug vs Remix)."""
    print("\n" + "="*60)
    print("Creating Combined Comparison Table")
    print("="*60)

    solqdebug_file = RESULTS_DIR / "solqdebug_merged_results.csv"
    remix_file = RESULTS_DIR / "remix_merged_results.csv"

    if not solqdebug_file.exists():
        print(f"WARNING: {solqdebug_file} not found. Run --solqdebug first.")
        return None

    if not remix_file.exists():
        print(f"WARNING: {remix_file} not found. Run --remix first.")
        return None

    # Load SolQDebug results
    solqdebug_data = {}  # {(contract, interval): mean_latency}
    with open(solqdebug_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row['Contract'], int(row['Interval']))
            solqdebug_data[key] = float(row['Mean_Latency_s']) if row['Mean_Latency_s'] else None

    # Load Remix results (interval 0 only, then multiply for others)
    remix_base = {}  # {contract: mean_latency}
    with open(remix_file, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            remix_base[row['Contract']] = float(row['Mean_PureDebug_s']) if row['Mean_PureDebug_s'] else None

    # Create combined output
    output_file = RESULTS_DIR / "combined_comparison.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Contract', 'Interval',
            'SolQDebug_Latency_s', 'Remix_PureDebug_s', 'Speedup'
        ])

        contracts = sorted(set(c for c, _ in solqdebug_data.keys()))

        for contract in contracts:
            for interval in INTERVALS:
                solq_latency = solqdebug_data.get((contract, interval))

                # Remix: interval 0 is measured, others are multiplied
                remix_latency = remix_base.get(contract)
                if remix_latency and interval > 0:
                    # Multiply by interval factor (interval 2 -> *2, etc.)
                    multiplier = interval if interval > 0 else 1
                    remix_latency = remix_latency * multiplier

                # Calculate speedup
                speedup = ""
                if solq_latency and remix_latency and solq_latency > 0:
                    speedup = f"{remix_latency / solq_latency:.1f}x"

                writer.writerow([
                    contract, interval,
                    f"{solq_latency:.6f}" if solq_latency else "",
                    f"{remix_latency:.6f}" if remix_latency else "",
                    speedup
                ])

    print(f"\nOutput saved to: {output_file}")
    return output_file


def print_usage():
    print("Usage: python merge_results.py [OPTIONS]")
    print("")
    print("Options:")
    print("  --solqdebug  Merge SolQDebug results")
    print("  --remix      Merge Remix results")
    print("  --combined   Create combined comparison table")
    print("  --all        Run all merge operations")
    print("")
    print("Example workflow:")
    print("  1. Run SolQDebug benchmarks for all intervals and runs")
    print("  2. Run Remix benchmarks for all runs")
    print("  3. python merge_results.py --all")


if __name__ == "__main__":
    args = sys.argv[1:]

    if not args or '--help' in args or '-h' in args:
        print_usage()
        sys.exit(0)

    if '--solqdebug' in args or '--all' in args:
        merge_solqdebug_results()

    if '--remix' in args or '--all' in args:
        merge_remix_results()

    if '--combined' in args or '--all' in args:
        create_combined_comparison()

    print("\nDone!")
