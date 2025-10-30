#!/usr/bin/env python3
"""
Run interval analysis experiments on mutated contracts with Z3 annotations
Executes 250 experiments (25 mutations × 10 Z3 inputs each)
"""
import json
import re
import sys
from pathlib import Path
from datetime import datetime

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from run_rq2_simple import run_experiment, extract_intervals

# Configuration
MUTATED_DIR = Path("Evaluation/Mutated_Contracts")
ANNOT_DIR = Path("Evaluation/RQ2_Mutated_Annotations")
OUTPUT_DIR = Path("Evaluation/RQ2_Mutated_Results")
BASE_ANNOT_DIR = Path("dataset/annotation")

# Contract metadata for base annotations
CONTRACT_BASE_FILES = {
    "GovStakingStorage_c": "dataset/contraction/GovStakingStorage_c.sol",
    "GreenHouse_c": "dataset/contraction/GreenHouse_c.sol",
    "HubPool_c": "dataset/contraction/HubPool_c.sol",
    "Lock_c": "dataset/contraction/Lock_c.sol",
    "LockupContract_c": "dataset/contraction/LockupContract_c.sol",
    "PoolKeeper_c": "dataset/contraction/PoolKeeper_c.sol",
    "ThorusBond_c": "dataset/contraction/ThorusBond_c.sol",
}

CONTRACT_BASE_ANNOTS = {
    "GovStakingStorage_c": "dataset/annotation/GovStakingStorage_c.json",
    "GreenHouse_c": "dataset/annotation/GreenHouse_c.json",
    "HubPool_c": "dataset/annotation/HubPool_c.json",
    "Lock_c": "dataset/annotation/Lock_c.json",
    "LockupContract_c": "dataset/annotation/LockupContract_c.json",
    "PoolKeeper_c": "dataset/annotation/PoolKeeper_c.json",
    "ThorusBond_c": "dataset/annotation/ThorusBond_c.json",
}

# F90 measurement targets
F90_TARGETS = {
    "GovStakingStorage_c": "info.rewardMultiplier",
    "GreenHouse_c": "net",
    "HubPool_c": "pooledTokens[l1Token].undistributedLpFees",
    "Lock_c": "_pending",
    "LockupContract_c": "releasedAmount",
    "PoolKeeper_c": "keeperTip",
    "ThorusBond_c": "return",  # Special case
}

def get_base_contract(mutation_filename: str) -> str:
    """Extract base contract name from mutation filename"""
    match = re.match(r'([A-Za-z_]+_c)_', mutation_filename)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract base contract from: {mutation_filename}")

def parse_z3_ranges(z3_annot):
    """Parse Z3 ranges from annotation JSON"""
    ranges = []
    for rec in z3_annot:
        code = rec.get("code", "")
        if "@StateVar" in code or "@LocalVar" in code or "@GlobalVar" in code:
            match = re.search(r'\[(\d+),(\d+)\]', code)
            if match:
                ranges.append((int(match.group(1)), int(match.group(2))))
    return ranges

def apply_z3_ranges_to_annotation(base_annot, z3_ranges):
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

def extract_f90_metric(intervals, target_var):
    """Extract F90 metric for target variable"""
    if target_var not in intervals:
        return None, False

    info = intervals[target_var]
    return info['width'], info['finite']

def main():
    print("=" * 70)
    print("MUTATED CONTRACT EXPERIMENT RUNNER")
    print("=" * 70)
    print(f"Start time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Prepare CSV output
    csv_file = OUTPUT_DIR / "mutated_experiments_results.csv"
    csv_headers = ["contract", "mutation_file", "mutation_type", "pattern", "delta", "target_var", "f90_width", "converged", "num_intervals", "status"]

    with open(csv_file, 'w', encoding='utf-8') as f:
        f.write(",".join(csv_headers) + "\n")

    # Get all annotation files
    annot_files = sorted(ANNOT_DIR.glob("*.json"))
    total_experiments = len(annot_files)
    print(f"\n[+] Found {total_experiments} annotation files")

    completed = 0
    failed = 0

    for idx, annot_file in enumerate(annot_files, 1):
        annot_name = annot_file.stem  # e.g., Lock_c_pending_sub_to_add_overlap_d1_z3

        # Parse filename
        # Pattern: {contract}_{function}_{mutation_type}_{pattern}_d{delta}_z3
        parts = annot_name.split('_')

        # Extract base contract and mutation file
        base_contract = get_base_contract(annot_name)

        # Find corresponding mutation file
        mutation_pattern = annot_name.replace(f"_{parts[-3]}_d{parts[-1].replace('z3', '').strip('_')}_z3", "")
        mutation_file = MUTATED_DIR / f"{mutation_pattern}.sol"

        if not mutation_file.exists():
            print(f"[{idx}/{total_experiments}] [SKIP] Mutation file not found: {mutation_file.name}")
            failed += 1
            continue

        # Extract pattern and delta
        pattern = parts[-3]  # overlap or diff
        delta_str = parts[-2]  # d1, d3, etc.
        delta = int(delta_str[1:])

        # Extract mutation type
        mutation_type = "_".join([p for p in parts if p not in ['overlap', 'diff'] and not p.startswith('d') and p != 'z3'])
        mutation_type = mutation_type.replace(f"{base_contract}_", "").replace(annot_name.split('_')[1] + "_", "")

        print(f"\n[{idx}/{total_experiments}] {base_contract} | {mutation_type} | {pattern} d={delta}")
        print(f"  Mutation: {mutation_file.name}")

        # Load base annotation
        base_annot_file = Path(CONTRACT_BASE_ANNOTS[base_contract])
        if not base_annot_file.exists():
            print(f"  [ERROR] Base annotation not found: {base_annot_file}")
            failed += 1
            continue

        with open(base_annot_file, 'r', encoding='utf-8') as f:
            base_annot = json.load(f)

        # Load Z3 annotation
        with open(annot_file, 'r', encoding='utf-8') as f:
            z3_annot = json.load(f)

        # Apply Z3 ranges to base annotation
        z3_ranges = parse_z3_ranges(z3_annot)
        modified_annot = apply_z3_ranges_to_annotation(base_annot, z3_ranges)

        # Run experiment
        try:
            results = run_experiment(str(mutation_file), modified_annot)

            if results is None:
                print(f"  [FAIL] Experiment returned None")
                status = "failed"
                f90_width = None
                converged = False
                num_intervals = 0
            else:
                intervals = extract_intervals(results)
                target_var = F90_TARGETS[base_contract]
                f90_width, converged = extract_f90_metric(intervals, target_var)
                num_intervals = len(intervals)
                status = "success"

                print(f"  [OK] Intervals: {num_intervals}, F90: {f90_width}, Converged: {converged}")

            completed += 1

        except Exception as e:
            print(f"  [ERROR] {str(e)}")
            status = "error"
            f90_width = None
            converged = False
            num_intervals = 0
            failed += 1

        # Write to CSV
        with open(csv_file, 'a', encoding='utf-8') as f:
            row = [
                base_contract,
                mutation_file.name,
                mutation_type,
                pattern,
                delta,
                F90_TARGETS[base_contract],
                f90_width if f90_width is not None else "",
                converged,
                num_intervals,
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
