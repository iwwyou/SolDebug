#!/usr/bin/env python3
"""
Run RQ2 experiments with Z3-generated SAT inputs
Combines Z3 annotations with full contract structure
"""
import sys
import json
import csv
import time
from pathlib import Path
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from run_rq2_simple import simulate_inputs, extract_intervals

# Configuration
SCRIPT_DIR = Path(__file__).parent
PROJECT_ROOT = SCRIPT_DIR.parent
Z3_INPUT_DIR = SCRIPT_DIR / "RQ2_Z3_Focused"
ANNOTATION_DIR = PROJECT_ROOT / "dataset/json/annotation"
RESULTS_DIR = SCRIPT_DIR / "RQ2_Z3_Results"
OUTPUT_CSV = RESULTS_DIR / "rq2_z3_results.csv"

CONTRACTS = [
    "GovStakingStorage_c",
    "GreenHouse_c",
    "HubPool_c",
    "Lock_c",
    "LockupContract_c",
    "PoolKeeper_c",
    "ThorusBond_c"
]

def parse_z3_ranges(z3_annot: List[Dict]) -> List[tuple]:
    """
    Parse Z3-generated ranges from annotation JSON
    Returns list of (low, high) tuples in order
    """
    import re
    ranges = []

    for rec in z3_annot:
        code = rec["code"]
        # Match pattern: // @XxxVar name = [low,high];
        match = re.search(r'\[(\d+),(\d+)\]', code)
        if match:
            low = int(match.group(1))
            high = int(match.group(2))
            ranges.append((low, high))

    return ranges

def apply_z3_ranges_to_annotation(base_annot: List[Dict], z3_ranges: List[tuple]) -> List[Dict]:
    """
    Apply Z3-generated ranges to base annotation
    Similar to modify_annotation_intervals but uses Z3-validated ranges
    """
    import re
    modified = []
    range_idx = 0

    for rec in base_annot:
        code = rec["code"]
        stripped = code.lstrip()

        # Check if it's a variable annotation within @Debugging section
        if stripped.startswith("// @StateVar") or stripped.startswith("// @LocalVar") or stripped.startswith("// @GlobalVar"):
            # Extract pattern: // @XxxVar name = [low,high];
            match = re.match(r'(// @\w+Var\s+[\w.\[\]]+\s*=\s*)\[(\d+),(\d+)\]', code)
            if match and range_idx < len(z3_ranges):
                prefix = match.group(1)
                new_low, new_high = z3_ranges[range_idx]
                new_code = f"{prefix}[{new_low},{new_high}];"
                modified.append({**rec, "code": new_code})
                range_idx += 1
                continue

        # Keep other records as-is
        modified.append(rec)

    return modified

def run_single_z3_experiment(contract: str, pattern: str, delta: int) -> Dict:
    """Run single experiment with Z3 input"""
    # Load base annotation
    base_annot_file = ANNOTATION_DIR / f"{contract}_annot.json"
    if not base_annot_file.exists():
        return {
            'contract': contract,
            'pattern': pattern,
            'delta': delta,
            'success': False,
            'error': f'Base annotation not found: {base_annot_file}',
            'execution_time': 0
        }

    # Load Z3 annotation
    z3_annot_file = Z3_INPUT_DIR / f"{contract}_{pattern}_d{delta}_z3.json"
    if not z3_annot_file.exists():
        return {
            'contract': contract,
            'pattern': pattern,
            'delta': delta,
            'success': False,
            'error': f'Z3 annotation not found: {z3_annot_file}',
            'execution_time': 0
        }

    try:
        with open(base_annot_file, 'r', encoding='utf-8') as f:
            base_annot = json.load(f)

        with open(z3_annot_file, 'r', encoding='utf-8') as f:
            z3_annot = json.load(f)

        # Parse Z3-generated ranges
        z3_ranges = parse_z3_ranges(z3_annot)

        # Apply Z3 ranges to base annotation
        modified_annot = apply_z3_ranges_to_annotation(base_annot, z3_ranges)

        # Run experiment
        start_time = time.time()
        results = simulate_inputs(modified_annot)
        end_time = time.time()

        # Extract intervals
        intervals = extract_intervals(results)

        # Compute metrics
        finite_count = sum(1 for v in intervals.values() if v['finite'])
        infinite_count = len(intervals) - finite_count

        widths = [v['width'] for v in intervals.values() if v['finite']]
        avg_width = sum(widths) / len(widths) if widths else float('inf')
        max_width = max(widths) if widths else float('inf')

        # F90
        if widths:
            widths_sorted = sorted(widths)
            f90_idx = int(len(widths_sorted) * 0.9)
            f90 = widths_sorted[f90_idx] if f90_idx < len(widths_sorted) else widths_sorted[-1]
        else:
            f90 = float('inf')

        return {
            'contract': contract,
            'pattern': pattern,
            'delta': delta,
            'execution_time': end_time - start_time,
            'num_intervals': len(intervals),
            'finite_count': finite_count,
            'infinite_count': infinite_count,
            'avg_width': avg_width,
            'max_width': max_width,
            'f90': f90,
            'success': True
        }

    except Exception as e:
        import traceback
        return {
            'contract': contract,
            'pattern': pattern,
            'delta': delta,
            'success': False,
            'error': f'{str(e)}\n{traceback.format_exc()}'[:200],
            'execution_time': 0
        }

def main():
    print("=" * 70)
    print("RQ2 EXPERIMENTS WITH Z3 SAT INPUTS")
    print("=" * 70)

    RESULTS_DIR.mkdir(exist_ok=True)

    # Calculate total experiments
    deltas = [1, 3, 6, 10, 15]
    patterns = ["overlap", "diff"]
    total = len(CONTRACTS) * len(deltas) * len(patterns)

    print(f"\nTotal experiments: {total}")
    print(f"Contracts: {len(CONTRACTS)}")
    print(f"Using Z3-generated SAT inputs\n")

    all_results = []
    exp_num = 0

    for contract in CONTRACTS:
        print(f"\n[CONTRACT] {contract}")
        print("-" * 60)

        for delta in deltas:
            for pattern in patterns:
                exp_num += 1
                exp_id = f"{contract}_d{delta}_{pattern}"

                print(f"  [{exp_num}/{total}] {exp_id}...", end=" ", flush=True)

                result = run_single_z3_experiment(contract, pattern, delta)
                all_results.append(result)

                if result['success']:
                    f90 = result['f90']
                    f90_str = f"{f90:.1f}" if f90 != float('inf') else "inf"
                    print(f"OK ({result['execution_time']:.2f}s, F90={f90_str})")
                else:
                    error_msg = result.get('error', 'Unknown')[:40]
                    print(f"FAIL: {error_msg}")

    # Save results
    print(f"\n{'='*70}")
    print(f"Saving results to {OUTPUT_CSV}...")

    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        if all_results:
            fieldnames = list(all_results[0].keys())
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(all_results)

    print(f"[DONE] Saved {len(all_results)} results")

    # Summary
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
        print(f"Average time: {avg_time:.2f}s")

        # Pattern comparison
        overlap_results = [r for r in successful if r['pattern'] == 'overlap']
        diff_results = [r for r in successful if r['pattern'] == 'diff']

        overlap_finite = [r for r in overlap_results if r['f90'] != float('inf')]
        diff_finite = [r for r in diff_results if r['f90'] != float('inf')]

        print(f"\nPattern comparison:")
        print(f"  Overlap: {len(overlap_finite)}/{len(overlap_results)} finite")
        print(f"  Diff: {len(diff_finite)}/{len(diff_results)} finite")

        if overlap_finite and diff_finite:
            avg_overlap = sum(r['f90'] for r in overlap_finite) / len(overlap_finite)
            avg_diff = sum(r['f90'] for r in diff_finite) / len(diff_finite)

            print(f"\nF90 averages:")
            print(f"  Overlap: {avg_overlap:.2f}")
            print(f"  Diff: {avg_diff:.2f}")
            print(f"  Ratio: {avg_diff/avg_overlap:.2f}x")

if __name__ == "__main__":
    start = time.time()
    main()
    end = time.time()
    print(f"\nTotal time: {end - start:.2f}s")
