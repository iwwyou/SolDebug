#!/usr/bin/env python3
"""
Run RQ2 mutation experiments with fixed Z3 annotations
Uses base annotations + fixed Z3 ranges approach
"""
import sys
import json
import csv
import time
import re
from pathlib import Path
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Evaluation.RQ2_Mutation.run_rq2_simple import simulate_inputs, extract_intervals

# Configuration
SCRIPT_DIR = Path(__file__).parent
Z3_ANNOT_DIR = SCRIPT_DIR / "RQ2_Mutated_Annotations"
BASE_ANNOT_DIR = Path("dataset/json/annotation")
RESULTS_DIR = SCRIPT_DIR / "RQ2_Mutated_Results"
OUTPUT_CSV = RESULTS_DIR / "mutated_z3_results_final.csv"

CONTRACTS = {
    "GovStakingStorage_c": {"annot": "GovStakingStorage_c_annot.json", "f90_target": "info.rewardMultiplier"},
    "GreenHouse_c": {"annot": "GreenHouse_c_annot.json", "f90_target": "net"},
    "HubPool_c": {"annot": "HubPool_c_annot.json", "f90_target": "pooledTokens[l1Token].undistributedLpFees"},
    "Lock_c": {"annot": "Lock_c_annot.json", "f90_target": "_pending"},
    "LockupContract_c": {"annot": "LockupContract_c_annot.json", "f90_target": "releasedAmount"},
    "PoolKeeper_c": {"annot": "PoolKeeper_c_annot.json", "f90_target": "keeperTip"},
    "ThorusBond_c": {"annot": "ThorusBond_c_annot.json", "f90_target": "return"}
}

def get_base_contract(filename: str) -> str:
    match = re.match(r'([A-Za-z_]+_c)_', filename)
    if match:
        return match.group(1)
    return None

def parse_z3_ranges(z3_annot):
    ranges = []
    for rec in z3_annot:
        code = rec.get("code", "")
        if "@StateVar" in code or "@LocalVar" in code or "@GlobalVar" in code:
            match = re.search(r'\[(\d+),(\d+)\]', code)
            if match:
                ranges.append((int(match.group(1)), int(match.group(2))))
    return ranges

def apply_z3_ranges_to_annotation(base_annot, z3_ranges):
    modified = []
    range_idx = 0

    for rec in base_annot:
        code = rec["code"]
        stripped = code.lstrip()

        if stripped.startswith("// @StateVar") or stripped.startswith("// @LocalVar") or stripped.startswith("// @GlobalVar"):
            match = re.match(r'(// @\w+Var\s+[\w.\[\]]+\s*=\s*)\[(\d+),(\d+)\]', code)
            if match and range_idx < len(z3_ranges):
                prefix = match.group(1)
                new_low, new_high = z3_ranges[range_idx]
                new_code = f"{prefix}[{new_low},{new_high}];"
                modified.append({**rec, "code": new_code})
                range_idx += 1
                continue

        modified.append(rec)
    return modified

def parse_mutation_info(filename: str):
    """Parse mutation type, pattern, delta from filename"""
    parts = filename.replace('.json', '').split('_')

    # Find pattern and delta
    pattern = None
    delta = None
    for i, p in enumerate(parts):
        if p in ['overlap', 'diff']:
            pattern = p
        if p.startswith('d') and p[1:].isdigit():
            delta = int(p[1:])

    # Determine mutation type
    if "sub_to_add" in filename:
        mutation_type = "sub_to_add"
    elif "add_to_sub" in filename:
        mutation_type = "add_to_sub"
    elif "swap_add_sub" in filename:
        mutation_type = "swap_add_sub"
    elif "swap_mul_div" in filename:
        mutation_type = "swap_mul_div"
    elif "original_has_division" in filename:
        mutation_type = "original_has_division"
    else:
        mutation_type = "unknown"

    return mutation_type, pattern, delta

def main():
    print("=" * 70)
    print("RQ2 MUTATION EXPERIMENTS WITH FIXED Z3 ANNOTATIONS")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    RESULTS_DIR.mkdir(exist_ok=True)

    # Get all Z3 annotation files
    z3_annot_files = sorted(Z3_ANNOT_DIR.glob("*.json"))
    total = len(z3_annot_files)
    print(f"\n[+] Found {total} Z3 annotation files")

    # Prepare CSV
    with open(OUTPUT_CSV, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['contract', 'mutation_type', 'pattern', 'delta', 'f90_target',
                        'f90_width', 'converged', 'num_intervals', 'exec_time', 'success'])

    completed = 0
    failed = 0

    for idx, z3_annot_file in enumerate(z3_annot_files, 1):
        filename = z3_annot_file.name

        # Get base contract
        base_contract = get_base_contract(filename)
        if not base_contract or base_contract not in CONTRACTS:
            print(f"\n[{idx}/{total}] [SKIP] Unknown contract: {filename}")
            failed += 1
            continue

        contract_info = CONTRACTS[base_contract]
        mutation_type, pattern, delta = parse_mutation_info(filename)

        print(f"\n[{idx}/{total}] {base_contract} | {mutation_type} | {pattern} d={delta}")

        try:
            start_time = time.time()

            # Load base annotation
            base_annot_file = BASE_ANNOT_DIR / contract_info["annot"]
            with open(base_annot_file, 'r', encoding='utf-8') as f:
                base_annot = json.load(f)

            # Load Z3 annotation
            with open(z3_annot_file, 'r', encoding='utf-8') as f:
                z3_annot = json.load(f)

            # Apply Z3 ranges
            z3_ranges = parse_z3_ranges(z3_annot)
            modified_annot = apply_z3_ranges_to_annotation(base_annot, z3_ranges)

            # Run experiment
            results = simulate_inputs(modified_annot)
            exec_time = time.time() - start_time

            if results is None:
                print(f"  [FAIL] simulate_inputs returned None")
                success = False
                f90_width = None
                converged = False
                num_intervals = 0
            else:
                intervals = extract_intervals(results)
                num_intervals = len(intervals)

                # Extract F90 for target variable
                target_var = contract_info["f90_target"]
                if target_var in intervals:
                    info = intervals[target_var]
                    f90_width = info['width']
                    converged = info['finite']
                else:
                    f90_width = None
                    converged = False

                success = True
                print(f"  [OK] Intervals: {num_intervals}, F90: {f90_width}, Converged: {converged}, Time: {exec_time:.2f}s")

            completed += 1

        except Exception as e:
            exec_time = time.time() - start_time
            print(f"  [ERROR] {str(e)[:100]}")
            success = False
            f90_width = None
            converged = False
            num_intervals = 0
            failed += 1

        # Write to CSV
        with open(OUTPUT_CSV, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                base_contract,
                mutation_type,
                pattern,
                delta,
                contract_info["f90_target"],
                f90_width if f90_width is not None else "",
                converged,
                num_intervals,
                f"{exec_time:.2f}",
                success
            ])

    print("\n" + "=" * 70)
    print(f"[DONE] Completed: {completed}/{total}")
    print(f"[FAIL] Failed: {failed}")
    print(f"[+] Results saved to: {OUTPUT_CSV}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    main()
