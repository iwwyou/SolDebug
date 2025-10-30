#!/usr/bin/env python3
"""
Run interval analysis experiments on mutated contracts with Z3 annotations
Uses base contract + function replacement approach
"""
import json
import re
import sys
import time
from pathlib import Path
from datetime import datetime
from typing import Dict, List

sys.path.insert(0, str(Path(__file__).parent.parent))

from run_rq2_simple import simulate_inputs, extract_intervals

# Configuration
MUTATED_DIR = Path("Evaluation/Mutated_Contracts")
ANNOT_DIR = Path("Evaluation/RQ2_Mutated_Annotations")
OUTPUT_DIR = Path("Evaluation/RQ2_Mutated_Results")
BASE_CONTRACT_DIR = Path("dataset/contraction")
BASE_ANNOT_DIR = Path("dataset/json/annotation")

# Contract metadata
CONTRACTS = {
    "GovStakingStorage_c": {
        "file": "GovStakingStorage_c.sol",
        "annot": "GovStakingStorage_c_annot.json",
        "function": "updateRewardMultiplier",
        "f90_target": "info.rewardMultiplier"
    },
    "GreenHouse_c": {
        "file": "GreenHouse_c.sol",
        "annot": "GreenHouse_c_annot.json",
        "function": "_calculateFees",
        "f90_target": "net"
    },
    "HubPool_c": {
        "file": "HubPool_c.sol",
        "annot": "HubPool_c_annot.json",
        "function": "_allocateLpAndProtocolFees",
        "f90_target": "pooledTokens[l1Token].undistributedLpFees"
    },
    "Lock_c": {
        "file": "Lock_c.sol",
        "annot": "Lock_c_annot.json",
        "function": "pending",
        "f90_target": "_pending"
    },
    "LockupContract_c": {
        "file": "LockupContract_c.sol",
        "annot": "LockupContract_c_annot.json",
        "function": "_getReleasedAmount",
        "f90_target": "releasedAmount"
    },
    "PoolKeeper_c": {
        "file": "PoolKeeper_c.sol",
        "annot": "PoolKeeper_c_annot.json",
        "function": "keeperTip",
        "f90_target": "keeperTip"
    },
    "ThorusBond_c": {
        "file": "ThorusBond_c.sol",
        "annot": "ThorusBond_c_annot.json",
        "function": "claimablePayout",
        "f90_target": "return"
    }
}

def get_base_contract(mutation_filename: str) -> str:
    """Extract base contract name from mutation filename"""
    match = re.match(r'([A-Za-z_]+_c)_', mutation_filename)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract base contract from: {mutation_filename}")

def replace_function_in_annotation(base_annot: List[Dict], mutated_func_code: str, func_name: str) -> List[Dict]:
    """Replace function code in annotation records"""
    result = []
    in_function = False
    function_start_pattern = rf'function\s+{re.escape(func_name)}\s*\('

    for rec in base_annot:
        code = rec["code"]

        # Check if this is the start of our target function
        if re.search(function_start_pattern, code):
            in_function = True
            # Replace with mutated function
            result.append({**rec, "code": mutated_func_code})
            continue

        # Skip lines that are part of the original function
        if in_function:
            # Check if we've reached the end of the function (closing brace at same indentation)
            if code.strip() == "}":
                in_function = False
            continue

        result.append(rec)

    return result

def parse_z3_ranges(z3_annot: List[Dict]) -> List[tuple]:
    """Parse Z3 ranges from annotation JSON"""
    ranges = []
    for rec in z3_annot:
        code = rec.get("code", "")
        if "@StateVar" in code or "@LocalVar" in code or "@GlobalVar" in code:
            match = re.search(r'\[(\d+),(\d+)\]', code)
            if match:
                ranges.append((int(match.group(1)), int(match.group(2))))
    return ranges

def apply_z3_ranges_to_annotation(base_annot: List[Dict], z3_ranges: List[tuple]) -> List[Dict]:
    """Apply Z3 ranges to base annotation"""
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

def extract_f90_metric(intervals: Dict, target_var: str) -> tuple:
    """Extract F90 metric for target variable"""
    if target_var not in intervals:
        return None, False

    info = intervals[target_var]
    return info['width'], info['finite']

def main():
    print("=" * 70)
    print("MUTATED CONTRACT EXPERIMENT RUNNER (v2)")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Prepare CSV output
    csv_file = OUTPUT_DIR / "mutated_experiments_results.csv"
    csv_headers = ["contract", "mutation_type", "pattern", "delta", "target_var", "f90_width", "converged", "num_intervals", "exec_time", "status"]

    with open(csv_file, 'w', encoding='utf-8') as f:
        f.write(",".join(csv_headers) + "\n")

    # Get all annotation files
    annot_files = sorted(ANNOT_DIR.glob("*.json"))
    total_experiments = len(annot_files)
    print(f"\n[+] Found {total_experiments} annotation files")

    completed = 0
    failed = 0

    for idx, annot_file in enumerate(annot_files, 1):
        annot_name = annot_file.stem

        # Extract base contract
        base_contract = get_base_contract(annot_name)
        contract_info = CONTRACTS[base_contract]

        # Parse filename for metadata
        parts = annot_name.split('_')
        pattern = parts[-3]  # overlap or diff
        delta_str = parts[-2]  # d1, d3, etc.
        delta = int(delta_str[1:])

        # Extract mutation type
        mutation_pattern = annot_name.replace(f"_{pattern}_d{delta}_z3", "")
        mutation_file = MUTATED_DIR / f"{mutation_pattern}.sol"

        # Determine mutation type
        if "sub_to_add" in annot_name:
            mutation_type = "sub_to_add"
        elif "add_to_sub" in annot_name:
            mutation_type = "add_to_sub"
        elif "swap_add_sub" in annot_name:
            mutation_type = "swap_add_sub"
        elif "swap_mul_div" in annot_name:
            mutation_type = "swap_mul_div"
        elif "original_has_division" in annot_name:
            mutation_type = "original_has_division"
        else:
            mutation_type = "unknown"

        print(f"\n[{idx}/{total_experiments}] {base_contract} | {mutation_type} | {pattern} d={delta}")

        if not mutation_file.exists():
            print(f"  [SKIP] Mutation file not found")
            failed += 1
            continue

        # Load base annotation
        base_annot_file = BASE_ANNOT_DIR / contract_info["annot"]
        if not base_annot_file.exists():
            print(f"  [ERROR] Base annotation not found: {base_annot_file}")
            failed += 1
            continue

        try:
            start_time = time.time()

            # Load annotations
            with open(base_annot_file, 'r', encoding='utf-8') as f:
                base_annot = json.load(f)

            with open(annot_file, 'r', encoding='utf-8') as f:
                z3_annot = json.load(f)

            # Load mutated function code
            with open(mutation_file, 'r', encoding='utf-8') as f:
                mutated_func_code = f.read().strip()

            # Replace function in annotation
            modified_annot = replace_function_in_annotation(base_annot, mutated_func_code, contract_info["function"])

            # Apply Z3 ranges
            z3_ranges = parse_z3_ranges(z3_annot)
            final_annot = apply_z3_ranges_to_annotation(modified_annot, z3_ranges)

            # Run experiment
            results = simulate_inputs(final_annot)
            exec_time = time.time() - start_time

            if results is None:
                print(f"  [FAIL] Experiment returned None")
                status = "failed"
                f90_width = None
                converged = False
                num_intervals = 0
            else:
                intervals = extract_intervals(results)
                target_var = contract_info["f90_target"]
                f90_width, converged = extract_f90_metric(intervals, target_var)
                num_intervals = len(intervals)
                status = "success"

                print(f"  [OK] Intervals: {num_intervals}, F90: {f90_width}, Converged: {converged}, Time: {exec_time:.2f}s")

            completed += 1

        except Exception as e:
            exec_time = time.time() - start_time
            print(f"  [ERROR] {str(e)[:100]}")
            status = "error"
            f90_width = None
            converged = False
            num_intervals = 0
            failed += 1

        # Write to CSV
        with open(csv_file, 'a', encoding='utf-8') as f:
            row = [
                base_contract,
                mutation_type,
                pattern,
                delta,
                contract_info["f90_target"],
                f90_width if f90_width is not None else "",
                converged,
                num_intervals,
                f"{exec_time:.2f}",
                status
            ]
            f.write(",".join(map(str, row)) + "\n")

    print("\n" + "=" * 70)
    print(f"[DONE] Completed: {completed}/{total_experiments}")
    print(f"[FAIL] Failed: {failed}")
    print(f"[+] Results saved to: {csv_file}")
    print(f"End time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 70)

if __name__ == "__main__":
    main()
