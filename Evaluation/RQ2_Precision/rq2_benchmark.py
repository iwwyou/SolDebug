"""
RQ2: Precision Benchmark - Overlap vs Diff Pattern Comparison

This script evaluates how annotation patterns (overlap vs diff) affect
the precision of interval analysis on Lock.sol's compound arithmetic operations.

- Overlap pattern: All input variables share overlapping ranges [0,Δ]
- Diff pattern: Each input variable has disjoint ranges [k*offset, k*offset+Δ]

Usage:
    python rq2_benchmark.py                    # Run all experiments
    python rq2_benchmark.py --delta 1         # Specific delta
    python rq2_benchmark.py --pattern overlap # Specific pattern
"""

import sys
import os
import json
import time
import csv
import re
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

# RQ2 Parameters
DELTAS = [1, 3, 6, 10, 15]
PATTERNS = ["overlap", "diff"]

# Lock.sol annotation variables (for overlap/diff generation)
LOCK_VARS = [
    ("StateVar", "_data.total", 200),
    ("StateVar", "_data.unlockedAmounts", 0),
    ("StateVar", "_data.pending", 0),
    ("StateVar", "_data.estUnlock", 0),
    ("GlobalVar", "block.timestamp", 0),
    ("StateVar", "startLock", 0),
    ("StateVar", "lockedTime", 20000001),  # Fixed value
    ("StateVar", "unlockDuration", 2592001),  # Fixed value
]


def create_fresh_analyzer():
    """Create a fresh ContractAnalyzer instance for each test."""
    contract_analyzer = ContractAnalyzer()
    snapman = contract_analyzer.snapman
    batch_mgr = DebugBatchManager(contract_analyzer, snapman)
    return contract_analyzer, batch_mgr


def generate_annotation(delta: int, pattern: str) -> list:
    """
    Generate annotation records for overlap or diff pattern.

    Overlap: All variables have range [base, base+delta]
    Diff: Variables have disjoint ranges with offset between them
    """
    annotations = []
    offset = delta + 10  # Gap between disjoint ranges

    annotations.append({
        "code": "// @Debugging BEGIN",
        "startLine": 15,
        "endLine": 15,
        "event": "add"
    })

    line = 16
    for idx, (var_type, var_name, base_value) in enumerate(LOCK_VARS):
        # Fixed values (lockedTime, unlockDuration) don't change
        if var_name in ["lockedTime", "unlockDuration"]:
            low = high = base_value
        elif pattern == "overlap":
            low = base_value
            high = base_value + delta
        else:  # diff
            low = base_value + idx * offset
            high = low + delta

        code = f"// @{var_type} {var_name} = [{low},{high}];"
        annotations.append({
            "code": code,
            "startLine": line,
            "endLine": line,
            "event": "add"
        })
        line += 1

    annotations.append({
        "code": "// @Debugging END",
        "startLine": line,
        "endLine": line,
        "event": "add"
    })

    return annotations


def load_lock_contract_base() -> list:
    """Load Lock.sol contract code (without annotations) from RQ1."""
    lock_file = RQ1_JSON_DIR / "Lock_c_annot.json"

    with open(lock_file, 'r', encoding='utf-8') as f:
        records = json.load(f)

    # Filter out annotation records (keep only contract code)
    base_records = []
    for rec in records:
        code = rec["code"].strip()
        if not code.startswith("// @"):
            base_records.append(rec)

    return base_records


def create_experiment_input(delta: int, pattern: str) -> list:
    """Create full experiment input by combining contract base + annotations."""
    base_records = load_lock_contract_base()
    annotations = generate_annotation(delta, pattern)
    return base_records + annotations


def simulate_inputs(records, contract_analyzer, batch_mgr):
    """Run analysis and collect results."""
    in_testcase = False
    results = {}

    for idx, rec in enumerate(records):
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

            analysis = contract_analyzer.get_line_analysis(s, e)
            if analysis:
                for ln, recs in analysis.items():
                    if ln not in results:
                        results[ln] = []
                    results[ln].extend(recs)
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
            try:
                tree = ParserHelpers.generate_parse_tree(code, ctx, True)
                EnhancedSolidityVisitor(contract_analyzer).visit(tree)
            except Exception:
                pass

        analysis = contract_analyzer.get_line_analysis(s, e)
        if analysis:
            for ln, recs in analysis.items():
                if ln not in results:
                    results[ln] = []
                results[ln].extend(recs)

    return results


def extract_output_intervals(results: dict) -> dict:
    """Extract interval widths from analysis results."""
    MAX_UINT256 = 115792089237316195423570985008687907853269984665640564039457584007913129639935
    intervals = {}

    for line_num, records in results.items():
        for rec in records:
            vars_info = rec.get('vars', {})
            for var_name, var_data in vars_info.items():
                if isinstance(var_data, dict):
                    interval = var_data.get('interval')
                    if interval and isinstance(interval, (list, tuple)) and len(interval) == 2:
                        low, high = interval
                elif isinstance(var_data, str):
                    match = re.match(r'\[([^,]+),([^]]+)\]', var_data)
                    if match:
                        low_str, high_str = match.group(1), match.group(2)
                        try:
                            low = int(low_str) if low_str != 'None' else None
                            high = int(high_str) if high_str != 'None' else None
                        except ValueError:
                            continue
                    else:
                        continue
                else:
                    continue

                if low is None or high is None:
                    width = float('inf')
                elif high >= MAX_UINT256:
                    width = float('inf')
                else:
                    width = high - low

                intervals[f"{line_num}:{var_name}"] = {
                    'low': low,
                    'high': high,
                    'width': width,
                    'line': line_num
                }

    return intervals


def run_single_experiment(delta: int, pattern: str) -> dict:
    """Run a single experiment and return results."""
    records = create_experiment_input(delta, pattern)
    contract_analyzer, batch_mgr = create_fresh_analyzer()

    start_time = time.perf_counter()
    results = simulate_inputs(records, contract_analyzer, batch_mgr)
    end_time = time.perf_counter()

    intervals = extract_output_intervals(results)

    # Calculate precision metrics
    finite_widths = [v['width'] for v in intervals.values() if v['width'] != float('inf')]

    return {
        'delta': delta,
        'pattern': pattern,
        'latency_s': end_time - start_time,
        'num_outputs': len(intervals),
        'num_finite': len(finite_widths),
        'avg_width': sum(finite_widths) / len(finite_widths) if finite_widths else float('inf'),
        'max_width': max(finite_widths) if finite_widths else float('inf'),
        'intervals': intervals
    }


def run_benchmark(deltas=None, patterns=None, run_id=1):
    """Run RQ2 benchmark suite."""
    if deltas is None:
        deltas = DELTAS
    if patterns is None:
        patterns = PATTERNS

    print(f"\n{'='*60}")
    print(f"RQ2: Precision Benchmark (Overlap vs Diff)")
    print(f"Run ID: {run_id}")
    print(f"Deltas: {deltas}")
    print(f"Patterns: {patterns}")
    print(f"{'='*60}\n")

    all_results = []

    for delta in deltas:
        for pattern in patterns:
            print(f"[Delta={delta}, Pattern={pattern}]...", end=" ", flush=True)

            try:
                result = run_single_experiment(delta, pattern)
                print(f"OK (latency={result['latency_s']:.4f}s, avg_width={result['avg_width']:.1f})")
                all_results.append(result)
            except Exception as e:
                print(f"FAILED: {e}")
                all_results.append({
                    'delta': delta,
                    'pattern': pattern,
                    'latency_s': 0,
                    'num_outputs': 0,
                    'num_finite': 0,
                    'avg_width': float('inf'),
                    'max_width': float('inf'),
                    'error': str(e)
                })

    # Save results
    output_file = RESULTS_DIR / f"rq2_results_run{run_id}.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'delta', 'pattern', 'latency_s', 'num_outputs',
            'num_finite', 'avg_width', 'max_width'
        ])
        writer.writeheader()
        for r in all_results:
            writer.writerow({k: v for k, v in r.items() if k != 'intervals' and k != 'error'})

    # Print summary
    print(f"\n{'='*60}")
    print(f"SUMMARY")
    print(f"{'='*60}")

    for pattern in patterns:
        pattern_results = [r for r in all_results if r['pattern'] == pattern]
        avg_widths = [r['avg_width'] for r in pattern_results if r['avg_width'] != float('inf')]
        if avg_widths:
            print(f"{pattern.upper()}: avg_width mean = {sum(avg_widths)/len(avg_widths):.1f}")

    print(f"\nResults saved to: {output_file}")
    print(f"{'='*60}\n")

    return all_results


if __name__ == "__main__":
    args = sys.argv[1:]

    deltas = None
    patterns = None
    run_id = 1

    i = 0
    while i < len(args):
        if args[i] == '--delta' and i + 1 < len(args):
            deltas = [int(args[i + 1])]
            i += 2
        elif args[i] == '--pattern' and i + 1 < len(args):
            patterns = [args[i + 1]]
            i += 2
        elif args[i] == '--run-id' and i + 1 < len(args):
            run_id = int(args[i + 1])
            i += 2
        elif args[i] in ['--help', '-h']:
            print(__doc__)
            sys.exit(0)
        else:
            i += 1

    run_benchmark(deltas, patterns, run_id)
