"""
SolQDebug Latency Benchmark - Edit-Trace Replay Script

This script replays pre-recorded edit traces (JSON files) that simulate
interactive debugging sessions in SolQDebug. Each JSON file contains a
sequence of code edits and debug annotations that mimic realistic developer
activity during debugging.

Usage:
    python run_all_benchmarks.py                    # Full benchmark (4 intervals x 5 runs)
    python run_all_benchmarks.py --runs 5           # 5 runs per interval
    python run_all_benchmarks.py --intervals 0 2    # Only intervals 0 and 2
    python run_all_benchmarks.py --runs 1 --intervals 0  # Quick test (1 run, interval 0)

Prerequisites:
    1. Clone the repository: git clone https://github.com/iwwyou/SolDebug.git
    2. Install dependencies: pip install antlr4-python3-runtime
    3. Run from repository root or Evaluation/RQ1_Latency directory

Output:
    Results are saved to the 'results/' subdirectory as CSV files.
"""

import sys
import os
import json
import time
import csv
import statistics
from pathlib import Path
from datetime import datetime

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers

# Paths
JSON_INTERVALS_DIR = Path(__file__).parent / "json_intervals"
RESULTS_DIR = Path(__file__).parent / "results"

# Default configuration
DEFAULT_INTERVALS = [0, 2, 5, 10]
DEFAULT_RUNS = 5  # 5 runs for statistical validity


def create_fresh_analyzer():
    """Create a fresh ContractAnalyzer instance for each test."""
    contract_analyzer = ContractAnalyzer()
    snapman = contract_analyzer.snapman
    batch_mgr = DebugBatchManager(contract_analyzer, snapman)
    return contract_analyzer, batch_mgr


def simulate_inputs(records, contract_analyzer, batch_mgr):
    """Simulate user inputs from JSON records."""
    in_testcase = False

    for rec in records:
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)

        stripped = code.lstrip()

        if stripped.startswith("// @Debugging BEGIN"):
            batch_mgr.reset()
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            batch_mgr.flush()
            in_testcase = False
            continue

        if stripped.startswith("// @"):
            if ev == "add":
                batch_mgr.add_line(code, s, e)
            elif ev == "modify":
                batch_mgr.modify_line(code, s, e)
            elif ev == "delete":
                batch_mgr.delete_line(s)

            if not in_testcase:
                batch_mgr.flush()
            continue

        if code.strip():
            ctx = contract_analyzer.get_current_context_type()
            tree = ParserHelpers.generate_parse_tree(code, ctx, True)
            EnhancedSolidityVisitor(contract_analyzer).visit(tree)

        contract_analyzer.get_line_analysis(s, e)

    return True


def run_single_benchmark(json_path):
    """Run benchmark on a single JSON file."""
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            records = json.load(f)

        contract_analyzer, batch_mgr = create_fresh_analyzer()

        start_time = time.perf_counter()
        simulate_inputs(records, contract_analyzer, batch_mgr)
        end_time = time.perf_counter()

        return True, end_time - start_time, None

    except Exception as e:
        return False, 0.0, str(e)


def run_all_benchmarks(intervals=None, num_runs=None):
    """
    Run benchmarks for all intervals and runs.

    Args:
        intervals: List of intervals to test (default: [0, 2, 5, 10])
        num_runs: Number of runs per interval (default: 10)
    """
    intervals = intervals or DEFAULT_INTERVALS
    num_runs = num_runs or DEFAULT_RUNS

    # Create results directory
    RESULTS_DIR.mkdir(parents=True, exist_ok=True)

    # Timestamp for this benchmark session
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    print("=" * 70)
    print("SolQDebug Full Benchmark Suite")
    print("=" * 70)
    print(f"Intervals: {intervals}")
    print(f"Runs per interval: {num_runs}")
    print(f"Timestamp: {timestamp}")
    print("=" * 70)
    print()

    all_results = []
    total_benchmarks = len(intervals) * num_runs
    current_benchmark = 0

    for interval in intervals:
        json_dir = JSON_INTERVALS_DIR / f"interval_{interval}"

        if not json_dir.exists():
            print(f"[ERROR] Directory not found: {json_dir}")
            continue

        json_files = sorted(json_dir.glob("*_annot.json"))

        if not json_files:
            print(f"[ERROR] No JSON files found in {json_dir}")
            continue

        print(f"\n{'='*70}")
        print(f"INTERVAL {interval}")
        print(f"{'='*70}")

        interval_results = []

        for run_id in range(1, num_runs + 1):
            current_benchmark += 1
            progress = f"[{current_benchmark}/{total_benchmarks}]"

            print(f"\n{progress} Interval {interval}, Run {run_id}/{num_runs}")
            print("-" * 50)

            run_results = []

            for idx, json_path in enumerate(json_files):
                contract_name = json_path.name.replace("_c_annot.json", "").replace("_annot.json", "")

                print(f"  [{idx+1}/{len(json_files)}] {contract_name}...", end=" ", flush=True)

                success, latency, error = run_single_benchmark(json_path)

                if success:
                    print(f"OK ({latency:.4f}s)")
                    result = {
                        'contract_name': contract_name,
                        'interval': interval,
                        'run_id': run_id,
                        'latency_s': latency,
                        'success': True,
                        'error': None
                    }
                else:
                    print(f"FAILED: {error}")
                    result = {
                        'contract_name': contract_name,
                        'interval': interval,
                        'run_id': run_id,
                        'latency_s': 0.0,
                        'success': False,
                        'error': error
                    }

                run_results.append(result)
                interval_results.append(result)
                all_results.append(result)

            # Save individual run results (format matches merge_results.py expectation)
            run_output = RESULTS_DIR / f"solqdebug_results_interval{interval}_run{run_id}.csv"
            save_results_csv(run_results, run_output)

            # Print run summary
            successful = [r for r in run_results if r['success']]
            if successful:
                latencies = [r['latency_s'] for r in successful]
                total_time = sum(latencies)
                print(f"\n  Run {run_id} Summary: {len(successful)}/{len(run_results)} success, Total: {total_time:.2f}s")

        # Save interval results
        interval_output = RESULTS_DIR / f"solqdebug_results_interval{interval}_all_runs.csv"
        save_results_csv(interval_results, interval_output)

        # Print interval summary
        print_interval_summary(interval, interval_results, num_runs)

    # Save all results
    all_output = RESULTS_DIR / f"all_results_{timestamp}.csv"
    save_results_csv(all_results, all_output)

    # Generate and save summary statistics
    summary_output = RESULTS_DIR / f"summary_{timestamp}.csv"
    generate_summary_statistics(all_results, intervals, num_runs, summary_output)

    print("\n" + "=" * 70)
    print("BENCHMARK COMPLETE")
    print("=" * 70)
    print(f"Results directory: {RESULTS_DIR}")
    print(f"All results: {all_output.name}")
    print(f"Summary: {summary_output.name}")
    print("=" * 70)

    return all_results


def save_results_csv(results, output_path):
    """Save results to CSV file."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['contract_name', 'interval', 'run_id', 'latency_s', 'success', 'error'])
        writer.writeheader()
        writer.writerows(results)


def print_interval_summary(interval, results, num_runs):
    """Print summary statistics for an interval."""
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print(f"\n{'='*50}")
    print(f"INTERVAL {interval} SUMMARY ({num_runs} runs)")
    print(f"{'='*50}")
    print(f"Total tests: {len(results)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(failed)}")

    if successful:
        latencies = [r['latency_s'] for r in successful]
        print(f"\nLatency Statistics:")
        print(f"  Mean:   {statistics.mean(latencies):.4f}s")
        print(f"  Median: {statistics.median(latencies):.4f}s")
        print(f"  Stdev:  {statistics.stdev(latencies):.4f}s" if len(latencies) > 1 else "  Stdev:  N/A")
        print(f"  Min:    {min(latencies):.4f}s")
        print(f"  Max:    {max(latencies):.4f}s")

    if failed:
        print(f"\nFailed tests:")
        unique_failures = {}
        for r in failed:
            key = (r['contract_name'], r['error'])
            if key not in unique_failures:
                unique_failures[key] = 0
            unique_failures[key] += 1

        for (name, error), count in unique_failures.items():
            print(f"  - {name} ({count}x): {error[:50]}...")


def generate_summary_statistics(all_results, intervals, num_runs, output_path):
    """Generate summary statistics per contract per interval."""
    summary = []

    # Get unique contract names
    contract_names = sorted(set(r['contract_name'] for r in all_results))

    for contract_name in contract_names:
        for interval in intervals:
            # Filter results for this contract and interval
            filtered = [r for r in all_results
                       if r['contract_name'] == contract_name
                       and r['interval'] == interval
                       and r['success']]

            if filtered:
                latencies = [r['latency_s'] for r in filtered]
                summary.append({
                    'contract_name': contract_name,
                    'interval': interval,
                    'num_runs': len(latencies),
                    'mean_latency_s': statistics.mean(latencies),
                    'median_latency_s': statistics.median(latencies),
                    'stdev_latency_s': statistics.stdev(latencies) if len(latencies) > 1 else 0,
                    'min_latency_s': min(latencies),
                    'max_latency_s': max(latencies),
                    'success_rate': len(filtered) / num_runs
                })
            else:
                # All runs failed for this contract/interval
                summary.append({
                    'contract_name': contract_name,
                    'interval': interval,
                    'num_runs': 0,
                    'mean_latency_s': 0,
                    'median_latency_s': 0,
                    'stdev_latency_s': 0,
                    'min_latency_s': 0,
                    'max_latency_s': 0,
                    'success_rate': 0
                })

    # Save summary
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'contract_name', 'interval', 'num_runs',
            'mean_latency_s', 'median_latency_s', 'stdev_latency_s',
            'min_latency_s', 'max_latency_s', 'success_rate'
        ])
        writer.writeheader()
        writer.writerows(summary)

    # Print overall summary
    print("\n" + "=" * 70)
    print("OVERALL SUMMARY BY INTERVAL")
    print("=" * 70)

    for interval in intervals:
        interval_data = [s for s in summary if s['interval'] == interval and s['num_runs'] > 0]
        if interval_data:
            all_means = [s['mean_latency_s'] for s in interval_data]
            print(f"\nInterval {interval}:")
            print(f"  Contracts tested: {len(interval_data)}")
            print(f"  Average mean latency: {statistics.mean(all_means):.4f}s")
            print(f"  Total mean latency: {sum(all_means):.4f}s")


def print_usage():
    print("Usage: python run_all_benchmarks.py [options]")
    print("")
    print("Options:")
    print("  --runs N          Number of runs per interval (default: 10)")
    print("  --intervals N...  Intervals to test (default: 0 2 5 10)")
    print("  --help, -h        Show this help message")
    print("")
    print("Examples:")
    print("  python run_all_benchmarks.py                    # Full benchmark (4 intervals x 10 runs)")
    print("  python run_all_benchmarks.py --runs 5           # 5 runs per interval")
    print("  python run_all_benchmarks.py --intervals 0 2    # Only intervals 0 and 2")
    print("  python run_all_benchmarks.py --runs 3 --intervals 0  # Quick test")


if __name__ == "__main__":
    args = sys.argv[1:]

    intervals = None
    num_runs = None

    i = 0
    while i < len(args):
        if args[i] == '--runs' and i + 1 < len(args):
            num_runs = int(args[i + 1])
            i += 2
        elif args[i] == '--intervals':
            intervals = []
            i += 1
            while i < len(args) and not args[i].startswith('--'):
                intervals.append(int(args[i]))
                i += 1
        elif args[i] in ['--help', '-h']:
            print_usage()
            sys.exit(0)
        else:
            print(f"Unknown argument: {args[i]}")
            print_usage()
            sys.exit(1)

    # Run benchmarks
    run_all_benchmarks(intervals, num_runs)
