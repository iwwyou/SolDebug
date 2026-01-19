"""
RQ3: Loop Analysis Benchmark

This script evaluates annotation-guided adaptive widening for loop analysis
on 5 benchmark contracts with diverse loop patterns:

- Pattern 1: Constant-bounded loops (AOC_BEP)
- Pattern 2: Annotation-enabled convergence (Balancer, Core)
- Pattern 3: Uninitialized local variables (TimeLockPool)
- Pattern 4: Data-dependent accumulation (AvatarArtMarketPlace)

Usage:
    python rq3_benchmark.py                    # Run all 5 contracts
    python rq3_benchmark.py --contract AOC_BEP # Specific contract
    python rq3_benchmark.py --run-id 2         # Specify run ID
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
RQ1_JSON_DIR = PROJECT_ROOT / "Evaluation" / "RQ1_Latency" / "json_intervals" / "interval_0"
RESULTS_DIR = Path(__file__).parent / "results"
RESULTS_DIR.mkdir(exist_ok=True)

# RQ3 Loop Contracts
RQ3_CONTRACTS = {
    "AOC_BEP": {
        "file": "AOC_BEP_c_annot.json",
        "function": "updateUserInfo",
        "pattern": "Pattern 1: Constant-bounded loops",
        "expected": "userInfo[account].level in [1,4]"
    },
    "Balancer": {
        "file": "Balancer_c_annot.json",
        "function": "_addActionBuilderAt",
        "pattern": "Pattern 2: Annotation-enabled convergence",
        "expected": "i in [0,1]"
    },
    "Core": {
        "file": "Core_c_annot.json",
        "function": "revokeStableMaster",
        "pattern": "Pattern 2: Annotation-enabled convergence",
        "expected": "i in [0,2]"
    },
    "TimeLockPool": {
        "file": "TimeLockPool_c_annot.json",
        "function": "getTotalDeposit",
        "pattern": "Pattern 3: Uninitialized local variables",
        "expected": "i in [0,3], total = TOP (uninitialized)"
    },
    "AvatarArtMarketPlace": {
        "file": "AvatarArtMarketPlace_c_annot.json",
        "function": "_removeFromTokens",
        "pattern": "Pattern 4: Data-dependent accumulation",
        "expected": "tokenIndex in [0,3], resultIndex widened to [0,inf]"
    }
}


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

        analysis = contract_analyzer.get_line_analysis(s, e)

    return True


def run_single_benchmark(json_path, verbose=False):
    """
    Run benchmark on a single JSON file.
    Returns: (success, latency_seconds, error_message)
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            records = json.load(f)

        contract_analyzer, batch_mgr = create_fresh_analyzer()

        start_time = time.perf_counter()
        success = simulate_inputs(records, contract_analyzer, batch_mgr, verbose)
        end_time = time.perf_counter()

        latency = end_time - start_time
        return True, latency, None

    except Exception as e:
        return False, 0.0, str(e)


def run_benchmark(contracts=None, run_id=1, verbose=False):
    """
    Run RQ3 benchmark on loop contracts.

    Args:
        contracts: List of contract names to test (default: all 5)
        run_id: Run identifier for output filename
        verbose: Print detailed progress
    """
    if contracts is None:
        contracts = list(RQ3_CONTRACTS.keys())

    print(f"\n{'='*60}")
    print(f"RQ3: Loop Analysis Benchmark")
    print(f"Run ID: {run_id}")
    print(f"Contracts: {len(contracts)}")
    print(f"{'='*60}\n")

    results = []

    for idx, contract_name in enumerate(contracts):
        if contract_name not in RQ3_CONTRACTS:
            print(f"[{idx+1}/{len(contracts)}] {contract_name}... SKIPPED (not in RQ3)")
            continue

        info = RQ3_CONTRACTS[contract_name]
        json_path = RQ1_JSON_DIR / info['file']

        if not json_path.exists():
            print(f"[{idx+1}/{len(contracts)}] {contract_name}... FAILED (file not found)")
            results.append({
                'contract_name': contract_name,
                'function': info['function'],
                'pattern': info['pattern'],
                'run_id': run_id,
                'latency_s': 0.0,
                'success': False,
                'error': 'File not found'
            })
            continue

        print(f"[{idx+1}/{len(contracts)}] {contract_name} ({info['function']})...", end=" ", flush=True)

        success, latency, error = run_single_benchmark(json_path, verbose)

        if success:
            print(f"OK ({latency:.4f}s)")
            results.append({
                'contract_name': contract_name,
                'function': info['function'],
                'pattern': info['pattern'],
                'expected': info['expected'],
                'run_id': run_id,
                'latency_s': latency,
                'success': True,
                'error': None
            })
        else:
            print(f"FAILED: {error}")
            results.append({
                'contract_name': contract_name,
                'function': info['function'],
                'pattern': info['pattern'],
                'expected': info['expected'],
                'run_id': run_id,
                'latency_s': 0.0,
                'success': False,
                'error': error
            })

    # Save results
    output_file = RESULTS_DIR / f"rq3_results_run{run_id}.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'contract_name', 'function', 'pattern', 'expected',
            'run_id', 'latency_s', 'success', 'error'
        ])
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
        print(f"\nLatency Statistics:")
        print(f"  Mean: {sum(latencies)/len(latencies):.4f}s")
        print(f"  Min:  {min(latencies):.4f}s")
        print(f"  Max:  {max(latencies):.4f}s")

    print(f"\nLoop Patterns Tested:")
    for r in successful:
        print(f"  - {r['contract_name']}: {r['pattern']}")

    if failed:
        print(f"\nFailed contracts:")
        for r in failed:
            print(f"  - {r['contract_name']}: {r['error']}")

    print(f"\nResults saved to: {output_file}")
    print(f"{'='*60}\n")

    return results


if __name__ == "__main__":
    args = sys.argv[1:]

    contracts = None
    run_id = 1
    verbose = False

    i = 0
    while i < len(args):
        if args[i] == '--contract' and i + 1 < len(args):
            contracts = [args[i + 1]]
            i += 2
        elif args[i] == '--run-id' and i + 1 < len(args):
            run_id = int(args[i + 1])
            i += 2
        elif args[i] == '--verbose':
            verbose = True
            i += 1
        elif args[i] in ['--help', '-h']:
            print(__doc__)
            sys.exit(0)
        else:
            i += 1

    run_benchmark(contracts, run_id, verbose)
