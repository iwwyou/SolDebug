"""
SolQDebug Latency Benchmark - Edit-Trace Replay Script

This script replays pre-recorded edit traces (JSON files) that simulate
interactive debugging sessions in SolQDebug. Each JSON file contains a
sequence of code edits and debug annotations that mimic realistic developer
activity during debugging.

The benchmark evaluates 30 smart contracts and measures the latency of
SolQDebug's incremental analysis for each.

Usage:
    python solqdebug_benchmark.py                          # Default: interval=0, run-id=1
    python solqdebug_benchmark.py --interval 5             # Specify interval
    python solqdebug_benchmark.py --interval 0 --run-id 2  # Specify both

Prerequisites:
    1. Clone the repository:
       git clone https://github.com/iwwyou/SolDebug.git
       cd SolDebug

    2. Install dependencies:
       cd Evaluation/RQ1_Latency
       install_dependencies.bat        (Windows)
       pip install antlr4-python3-runtime py-solc-x networkx  (Manual)

    3. Run the benchmark:
       python solqdebug_benchmark.py

Output:
    Results are saved to 'results/solqdebug_results_interval{N}_run{M}.csv'
"""

import sys
import os
import json
import time
import csv
from pathlib import Path

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


def create_fresh_analyzer():
    """Create a fresh ContractAnalyzer instance for each test."""
    contract_analyzer = ContractAnalyzer()
    snapman = contract_analyzer.snapman
    batch_mgr = DebugBatchManager(contract_analyzer, snapman)
    return contract_analyzer, batch_mgr


def simulate_inputs(records, contract_analyzer, batch_mgr, verbose=False):
    """
    Simulate user inputs from JSON records.
    Returns True if successful, False otherwise.
    """
    in_testcase = False

    for idx, rec in enumerate(records):
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)

        if verbose:
            print(f"  [{idx+1}/{len(records)}] Line {s}-{e}: {code[:50]}...")

        stripped = code.lstrip()

        # BEGIN / END
        if stripped.startswith("// @Debugging BEGIN"):
            batch_mgr.reset()
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            batch_mgr.flush()
            in_testcase = False
            continue

        # Debug annotations (@StateVar, @GlobalVar, etc.)
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

        # Regular Solidity code
        if code.strip():
            ctx = contract_analyzer.get_current_context_type()
            tree = ParserHelpers.generate_parse_tree(code, ctx, True)
            EnhancedSolidityVisitor(contract_analyzer).visit(tree)

        # Get line analysis (optional, for verification)
        analysis = contract_analyzer.get_line_analysis(s, e)

    return True


def run_single_benchmark(json_path, verbose=False):
    """
    Run benchmark on a single JSON file.
    Returns: (success, latency_seconds, error_message)
    """
    try:
        # Load JSON
        with open(json_path, 'r', encoding='utf-8') as f:
            records = json.load(f)

        # Create fresh analyzer for each test
        contract_analyzer, batch_mgr = create_fresh_analyzer()

        # Measure latency
        start_time = time.perf_counter()
        success = simulate_inputs(records, contract_analyzer, batch_mgr, verbose)
        end_time = time.perf_counter()

        latency = end_time - start_time
        return True, latency, None

    except Exception as e:
        return False, 0.0, str(e)


def extract_contract_info(json_filename):
    """Extract contract name and function name from JSON filename."""
    # Format: ContractName_c_annot.json
    name = json_filename.replace("_c_annot.json", "").replace("_annot.json", "")
    return name


def run_benchmark_suite(interval, run_id, verbose=False):
    """
    Run benchmark on all JSON files for a given interval.

    Args:
        interval: Interval value (0, 2, 5, or 10)
        run_id: Run identifier for output filename
        verbose: Print detailed progress
    """
    json_dir = JSON_INTERVALS_DIR / f"interval_{interval}"

    if not json_dir.exists():
        print(f"ERROR: Directory not found: {json_dir}")
        print("Please run generate_interval_jsons.py first.")
        sys.exit(1)

    json_files = sorted(json_dir.glob("*_annot.json"))

    if not json_files:
        print(f"ERROR: No JSON files found in {json_dir}")
        sys.exit(1)

    print(f"\n{'='*60}")
    print(f"SolQDebug Benchmark Suite")
    print(f"Interval: {interval}")
    print(f"Run ID: {run_id}")
    print(f"Total contracts: {len(json_files)}")
    print(f"{'='*60}\n")

    results = []

    for idx, json_path in enumerate(json_files):
        contract_name = extract_contract_info(json_path.name)

        print(f"[{idx+1}/{len(json_files)}] {contract_name}...", end=" ", flush=True)

        success, latency, error = run_single_benchmark(json_path, verbose)

        if success:
            print(f"OK ({latency:.4f}s)")
            results.append({
                'contract_name': contract_name,
                'interval': interval,
                'run_id': run_id,
                'latency_s': latency,
                'success': True,
                'error': None
            })
        else:
            print(f"FAILED: {error}")
            results.append({
                'contract_name': contract_name,
                'interval': interval,
                'run_id': run_id,
                'latency_s': 0.0,
                'success': False,
                'error': error
            })

    # Save results
    output_file = RESULTS_DIR / f"solqdebug_results_interval{interval}_run{run_id}.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=['contract_name', 'interval', 'run_id', 'latency_s', 'success', 'error'])
        writer.writeheader()
        writer.writerows(results)

    # Print summary
    successful = [r for r in results if r['success']]
    failed = [r for r in results if not r['success']]

    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")
    print(f"Total: {len(results)}")
    print(f"Success: {len(successful)}")
    print(f"Failed: {len(failed)}")

    if successful:
        latencies = [r['latency_s'] for r in successful]
        print(f"\nLatency Statistics (successful runs):")
        print(f"  Mean: {sum(latencies)/len(latencies):.4f}s")
        print(f"  Min:  {min(latencies):.4f}s")
        print(f"  Max:  {max(latencies):.4f}s")

    if failed:
        print(f"\nFailed contracts:")
        for r in failed:
            print(f"  - {r['contract_name']}: {r['error']}")

    print(f"\nResults saved to: {output_file}")
    print(f"{'='*60}\n")

    return results


def print_usage():
    print("Usage: python solqdebug_benchmark.py [options]")
    print("")
    print("Options:")
    print("  --interval N  Interval value: 0, 2, 5, or 10 (default: 0)")
    print("  --run-id M    Run identifier for multiple runs (default: 1)")
    print("  --verbose     Print detailed progress")
    print("")
    print("Examples:")
    print("  python solqdebug_benchmark.py                      # Run with defaults")
    print("  python solqdebug_benchmark.py --interval 5         # Interval 5")
    print("  python solqdebug_benchmark.py --interval 0 --run-id 2 --verbose")


if __name__ == "__main__":
    args = sys.argv[1:]

    interval = None
    run_id = None
    verbose = False

    # Parse arguments
    i = 0
    while i < len(args):
        if args[i] == '--interval' and i + 1 < len(args):
            interval = int(args[i + 1])
            i += 2
        elif args[i] == '--run-id' and i + 1 < len(args):
            run_id = int(args[i + 1])
            i += 2
        elif args[i] == '--verbose':
            verbose = True
            i += 1
        elif args[i] in ['--help', '-h']:
            print_usage()
            sys.exit(0)
        else:
            print(f"Unknown argument: {args[i]}")
            print_usage()
            sys.exit(1)

    # Default values if not specified
    if interval is None:
        interval = 0
    if run_id is None:
        run_id = 1

    if interval not in [0, 2, 5, 10]:
        print(f"ERROR: Invalid interval {interval}. Must be 0, 2, 5, or 10")
        sys.exit(1)

    # Run benchmark
    run_benchmark_suite(interval, run_id, verbose)
