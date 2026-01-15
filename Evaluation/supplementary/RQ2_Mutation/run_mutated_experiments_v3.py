#!/usr/bin/env python3
"""
Run interval analysis experiments on mutated contracts with Z3 annotations
Uses contract file replacement approach
"""
import json
import re
import sys
import time
import shutil
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
TEMP_CONTRACT_DIR = Path("Evaluation/Temp_Contracts")

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

def replace_function_in_contract(base_contract_code: str, mutated_func_code: str, func_name: str) -> str:
    """Replace function in contract source code"""
    # Pattern to match entire function
    pattern = rf'function\s+{re.escape(func_name)}\s*\([^)]*\)[^{{]*\{{(?:[^{{}}]|{{[^{{}}]*}})*}}'

    # Try to find and replace
    match = re.search(pattern, base_contract_code, re.DOTALL)
    if not match:
        # Try more permissive pattern
        pattern = rf'function\s+{re.escape(func_name)}\s*\([\s\S]*?\n\s*}}'
        match = re.search(pattern, base_contract_code, re.DOTALL)

    if match:
        return base_contract_code[:match.start()] + mutated_func_code + base_contract_code[match.end():]

    # If still not found, return original (will fail later)
    return base_contract_code

def create_full_mutated_contract(base_contract_file: Path, mutated_func_file: Path, func_name: str, output_file: Path):
    """Create full contract with mutated function"""
    # Read base contract
    with open(base_contract_file, 'r', encoding='utf-8') as f:
        base_code = f.read()

    # Read mutated function
    with open(mutated_func_file, 'r', encoding='utf-8') as f:
        mutated_func = f.read().strip()

    # Replace function
    mutated_contract = replace_function_in_contract(base_code, mutated_func, func_name)

    # Write to temp file
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write(mutated_contract)

def parse_contract_to_annotation(contract_file: Path) -> List[Dict]:
    """Parse contract file into annotation format"""
    with open(contract_file, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    records = []
    for idx, line in enumerate(lines, 1):
        records.append({
            "code": line.rstrip('\n'),
            "startLine": idx,
            "endLine": idx,
            "event": "add"
        })

    return records

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

def insert_z3_annotations(contract_annot: List[Dict], z3_annot: List[Dict]) -> List[Dict]:
    """Insert Z3 debugging annotations into contract annotation"""
    # Find @Debugging BEGIN/END in Z3 annotation
    z3_debug_records = []
    in_debug = False
    for rec in z3_annot:
        code = rec.get("code", "")
        if "@Debugging BEGIN" in code:
            in_debug = True
            z3_debug_records.append(rec)
            continue
        if "@Debugging END" in code:
            z3_debug_records.append(rec)
            break
        if in_debug:
            z3_debug_records.append(rec)

    # Insert at beginning
    result = []
    result.extend(z3_debug_records)
    result.extend(contract_annot)

    # Adjust line numbers
    offset = len(z3_debug_records)
    for rec in contract_annot:
        rec["startLine"] += offset
        rec["endLine"] += offset

    return result

def extract_f90_metric(intervals: Dict, target_var: str) -> tuple:
    """Extract F90 metric for target variable"""
    if target_var not in intervals:
        return None, False

    info = intervals[target_var]
    return info['width'], info['finite']

def main():
    print("=" * 70)
    print("MUTATED CONTRACT EXPERIMENT RUNNER (v3 - File Replacement)")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    OUTPUT_DIR.mkdir(exist_ok=True)
    TEMP_CONTRACT_DIR.mkdir(exist_ok=True)

    # Prepare CSV output
    csv_file = OUTPUT_DIR / "mutated_experiments_results_v3.csv"
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

        try:
            start_time = time.time()

            # Create full mutated contract
            base_contract_file = BASE_CONTRACT_DIR / contract_info["file"]
            temp_contract_file = TEMP_CONTRACT_DIR / f"{mutation_pattern}_{pattern}_d{delta}.sol"

            create_full_mutated_contract(
                base_contract_file,
                mutation_file,
                contract_info["function"],
                temp_contract_file
            )

            # Parse mutated contract to annotation format
            contract_annot = parse_contract_to_annotation(temp_contract_file)

            # Load Z3 annotation
            with open(annot_file, 'r', encoding='utf-8') as f:
                z3_annot = json.load(f)

            # Insert Z3 debugging annotations
            final_annot = insert_z3_annotations(contract_annot, z3_annot)

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

    # Cleanup temp files
    print("\n[+] Cleaning up temporary contract files...")
    shutil.rmtree(TEMP_CONTRACT_DIR, ignore_errors=True)

if __name__ == "__main__":
    main()
