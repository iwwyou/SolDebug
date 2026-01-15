#!/usr/bin/env python3
"""
RQ2 Mutation Experiments - CORRECT VERSION
Combines: Base Annotation + Mutated Function + Z3 Ranges
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
PROJECT_ROOT = SCRIPT_DIR.parent.parent
Z3_ANNOT_DIR = SCRIPT_DIR / "RQ2_Mutated_Annotations"
MUTATED_DIR = SCRIPT_DIR / "Mutated_Contracts"
BASE_ANNOT_DIR = PROJECT_ROOT / "dataset" / "json" / "annotation"
RESULTS_DIR = SCRIPT_DIR / "RQ2_Mutated_Results"
OUTPUT_CSV = RESULTS_DIR / "rq2_correct_results.csv"

CONTRACTS = {
    "GovStakingStorage_c": {
        "annot": "GovStakingStorage_c_annot.json",
        "function": "updateRewardMultiplier",
        "f90_target": "info.rewardMultiplier"
    },
    "GreenHouse_c": {
        "annot": "GreenHouse_c_annot.json",
        "function": "_calculateFees",
        "f90_target": "net"
    },
    "HubPool_c": {
        "annot": "HubPool_c_annot.json",
        "function": "_allocateLpAndProtocolFees",
        "f90_target": "pooledTokens[l1Token].undistributedLpFees"
    },
    "Lock_c": {
        "annot": "Lock_c_annot.json",
        "function": "pending",
        "f90_target": "_pending"
    },
    "LockupContract_c": {
        "annot": "LockupContract_c_annot.json",
        "function": "_getReleasedAmount",
        "f90_target": "releasedAmount"
    },
    "PoolKeeper_c": {
        "annot": "PoolKeeper_c_annot.json",
        "function": "keeperTip",
        "f90_target": "keeperTip"
    },
    "ThorusBond_c": {
        "annot": "ThorusBond_c_annot.json",
        "function": "claimablePayout",
        "f90_target": "None"
    }
}

def get_base_contract(filename: str):
    """Extract base contract name from Z3 annotation filename"""
    match = re.match(r'([A-Za-z_]+_c)_', filename)
    if match:
        return match.group(1)
    return None

def parse_mutation_info(filename: str):
    """Parse mutation type, pattern, delta from filename"""
    parts = filename.replace('.json', '').split('_')

    # Find pattern and delta
    pattern = None
    delta = None
    for i, p in enumerate(parts):
        if p in ['overlap', 'diff']:
            pattern = p
        if p.startswith('d') and len(p) > 1 and p[1:].isdigit():
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

def get_mutated_function_file(base_contract, mutation_type, func_name):
    """Get mutated function file path"""
    filename = f"{base_contract}_{func_name}_{mutation_type}.sol"
    return MUTATED_DIR / filename

def parse_z3_ranges(z3_annot, multiplier=1, pattern="overlap", delta=1):
    """
    Parse Z3 ranges and apply transformation based on pattern

    Handles negative values by shifting to non-negative range first.
    Example: [-30,45] -> [0,75] (shift +30, preserve gap=75)

    For GovStakingStorage (multiplier > 1):
        Scales base values proportionally to handle large divisions
        Example: [105,106] with multiplier=10000000 -> [1050000105, 1050000106]

    For other contracts (multiplier == 1):
        - overlap pattern: All variables get same base (100)
          Example: [60,141] -> [100,181], [60,141] -> [100,181]
        - diff pattern: Each variable gets increasing offset to prevent underflow
          Example: [60,141] -> [100,181], [60,141] -> [300,381], [60,141] -> [500,581]
          Spacing = gap + 20 + delta
    """
    ranges = []
    base_offset = 100  # Starting point for non-multiplier mode

    for idx, rec in enumerate(z3_annot):
        code = rec.get("code", "")
        if "@StateVar" in code or "@LocalVar" in code or "@GlobalVar" in code:
            match = re.search(r'\[(-?\d+),(-?\d+)\]', code)
            if match:
                low = int(match.group(1))
                high = int(match.group(2))
                gap = high - low

                # Step 1: Handle negative values - shift to non-negative
                # uint256 and block.timestamp cannot be negative
                if low < 0:
                    shift = -low  # Amount to shift to make low = 0
                    low += shift
                    high += shift
                    # Now low = 0, high = original_high + shift, gap preserved

                if multiplier > 1:
                    # GovStakingStorage mode: scale proportionally
                    new_low = low + low * multiplier
                    new_high = new_low + gap
                else:
                    # Standard mode: apply pattern-based offset
                    if pattern == "overlap":
                        # All variables start at same base
                        new_low = base_offset
                        new_high = base_offset + gap
                    else:  # diff
                        # Each variable gets increasing offset
                        # Spacing ensures no overlap and prevents underflow in subtraction
                        spacing = gap + 20 + delta
                        new_low = base_offset + idx * spacing
                        new_high = new_low + gap

                ranges.append((new_low, new_high))
    return ranges

def replace_function_in_base_annotation(base_annot, mutated_func_code, func_name):
    """
    Replace target function in base annotation with mutated function code

    Base annotation structure:
    - One record contains the entire function (startLine to endLine)
    - Multiple records for function internals (same line range)
    - Debugging annotations come after (startLine >= function endLine)

    Strategy:
    1. Find function record: "function {func_name}("
    2. Replace that record with mutated function
    3. Skip all records where startLine is within the original function's line range
    4. Keep debugging annotations (they start at or after function endLine)
    """
    result = []
    func_pattern = rf'function\s+{re.escape(func_name)}\s*\('
    function_found = False
    function_end_line = None

    for idx, rec in enumerate(base_annot):
        code = rec["code"]

        # Find the main function record
        if not function_found and re.search(func_pattern, code):
            function_found = True
            function_end_line = rec["endLine"]

            # Replace with mutated function
            result.append({
                **rec,
                "code": mutated_func_code,
                "endLine": rec["startLine"] + mutated_func_code.count('\n')
            })
            continue

        # Skip function body records (startLine < function_end_line)
        if function_found and function_end_line is not None:
            # If this record is part of the function body (not debugging annotation)
            if rec["startLine"] < function_end_line:
                continue
            # If this is at function end line, check if it's debugging annotation
            elif rec["startLine"] == function_end_line:
                if code.strip().startswith("// @"):
                    # This is a debugging annotation, keep it
                    result.append(rec)
                else:
                    # This is still function body, skip it
                    continue
            else:
                # Past function, keep everything
                result.append(rec)
        else:
            # Before function, keep everything
            result.append(rec)

    return result

def apply_z3_ranges_to_annotation(base_annot, z3_ranges, debug_log=False):
    """Apply Z3 ranges to debugging annotations"""
    modified = []
    range_idx = 0

    for rec in base_annot:
        code = rec["code"]
        stripped = code.lstrip()

        if stripped.startswith("// @StateVar") or stripped.startswith("// @LocalVar") or stripped.startswith("// @GlobalVar"):
            match = re.match(r'(// @\w+Var\s+[\w.\[\]]+\s*=\s*)\[(-?\d+),(-?\d+)\]', code)
            if match and range_idx < len(z3_ranges):
                prefix = match.group(1)
                old_low, old_high = int(match.group(2)), int(match.group(3))
                new_low, new_high = z3_ranges[range_idx]
                new_code = f"{prefix}[{new_low},{new_high}];"

                if debug_log:
                    var_name = prefix.strip().split()[-1].rstrip('=').strip()
                    print(f"  [Z3] {var_name}: [{old_low},{old_high}] -> [{new_low},{new_high}]")

                modified.append({**rec, "code": new_code})
                range_idx += 1
                continue

        modified.append(rec)

    return modified

def main():
    print("=" * 70)
    print("RQ2 MUTATION EXPERIMENTS - CORRECT VERSION")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()

    RESULTS_DIR.mkdir(exist_ok=True)

    # Get all Z3 annotation files
    z3_annot_files = sorted(Z3_ANNOT_DIR.glob("*.json"))
    total = len(z3_annot_files)
    print(f"[+] Found {total} Z3 annotation files\n")

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
            print(f"[{idx}/{total}] [SKIP] Unknown contract: {filename}")
            failed += 1
            continue

        contract_info = CONTRACTS[base_contract]
        mutation_type, pattern, delta = parse_mutation_info(filename)

        multiplier_info = " [MULTIPLIER x10M]" if base_contract == "GovStakingStorage_c" else ""
        print(f"[{idx}/{total}] {base_contract} | {mutation_type} | {pattern} d={delta}{multiplier_info}")

        try:
            start_time = time.time()

            # Load base annotation
            base_annot_file = BASE_ANNOT_DIR / contract_info["annot"]
            with open(base_annot_file, 'r', encoding='utf-8') as f:
                base_annot = json.load(f)

            # Load Z3 annotation
            with open(z3_annot_file, 'r', encoding='utf-8') as f:
                z3_annot = json.load(f)

            # Load mutated function
            mutated_func_file = get_mutated_function_file(
                base_contract, mutation_type, contract_info["function"]
            )

            if not mutated_func_file.exists():
                print(f"  [SKIP] Mutated function not found: {mutated_func_file.name}")
                failed += 1
                continue

            with open(mutated_func_file, 'r', encoding='utf-8') as f:
                mutated_func_code = f.read().strip()

            # Step 1: Replace function in base annotation
            modified_annot = replace_function_in_base_annotation(
                base_annot, mutated_func_code, contract_info["function"]
            )

            # Step 2: Apply Z3 ranges (with pattern and multiplier)
            # GovStakingStorage divides by 1 week (604800) and 100000, so we need large base values
            # Other contracts use pattern-based offset to prevent underflow
            multiplier = 10000000 if base_contract == "GovStakingStorage_c" else 1
            z3_ranges = parse_z3_ranges(z3_annot, multiplier, pattern, delta)

            # Enable debug logging for first few experiments or specific contracts
            enable_log = (idx <= 5 or base_contract in ("GreenHouse_c", "HubPool_c", "Lock_c", "ThorusBond_c", "LockupContract_c"))
            final_annot = apply_z3_ranges_to_annotation(modified_annot, z3_ranges, debug_log=enable_log)

            # Step 3: Run experiment
            results = simulate_inputs(final_annot)
            exec_time = time.time() - start_time

            if results is None:
                print(f"  [FAIL] simulate_inputs returned None")
                success = False
                f90_width = None
                converged = False
                num_intervals = 0
            else:
                # Enable debug for ThorusBond_c to see return expression
                debug_intervals = (base_contract == "ThorusBond_c" and enable_log)
                intervals = extract_intervals(results, debug_print=debug_intervals)
                num_intervals = len(intervals)

                # Extract F90 for target variable
                target_var = contract_info["f90_target"]

                # Return expressions typically appear with key "None" in analysis results
                # So f90_target can be set to "None" directly
                if target_var in intervals:
                    info = intervals[target_var]
                    f90_width = info['width']
                    converged = info['finite']
                else:
                    # Target not found - try fuzzy matching or show available variables
                    if num_intervals == 0:
                        if enable_log:
                            print(f"  [WARN] No intervals found. Target: {target_var}")
                    else:
                        # Try fuzzy matching (e.g., ends with target)
                        fuzzy_match = None
                        for var_name in intervals.keys():
                            if target_var in var_name or var_name.endswith(target_var.split('.')[-1]):
                                fuzzy_match = var_name
                                break

                        if fuzzy_match:
                            info = intervals[fuzzy_match]
                            f90_width = info['width']
                            converged = info['finite']
                            if enable_log:
                                print(f"  [INFO] Target not found, using fuzzy match: {fuzzy_match}")
                        else:
                            f90_width = None
                            converged = False
                            if enable_log:
                                print(f"  [WARN] Target {target_var} not found. Available: {list(intervals.keys())[:5]}")

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
