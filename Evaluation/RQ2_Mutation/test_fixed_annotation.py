#!/usr/bin/env python3
"""Test if fixed annotations work with run_rq2_simple"""
import sys
import json
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from Evaluation.RQ2_Mutation.run_rq2_simple import simulate_inputs, extract_intervals

# Test with one fixed annotation
annot_file = Path("Evaluation/RQ2_Mutation/RQ2_Mutated_Annotations/GovStakingStorage_c_updateRewardMultiplier_sub_to_add_overlap_d1_z3.json")

print("=" * 70)
print("TESTING FIXED ANNOTATION")
print("=" * 70)
print(f"\nTest file: {annot_file.name}")

# Load base annotation
base_annot_file = Path("dataset/json/annotation/GovStakingStorage_c_annot.json")
with open(base_annot_file, 'r', encoding='utf-8') as f:
    base_annot = json.load(f)

# Load Z3 annotation
with open(annot_file, 'r', encoding='utf-8') as f:
    z3_annot = json.load(f)

# Apply Z3 ranges to base annotation (from run_z3_experiments.py approach)
import re

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

z3_ranges = parse_z3_ranges(z3_annot)
print(f"Z3 ranges: {len(z3_ranges)} variables")
print(f"Base annotation: {len(base_annot)} records")

modified_annot = apply_z3_ranges_to_annotation(base_annot, z3_ranges)
print(f"Modified annotation: {len(modified_annot)} records")

# Run experiment
print("\nRunning experiment...")
try:
    results = simulate_inputs(modified_annot)
    if results:
        intervals = extract_intervals(results)
        print(f"\n[SUCCESS] Got {len(intervals)} intervals")

        # Show F90 target
        target_var = "info.rewardMultiplier"
        if target_var in intervals:
            info = intervals[target_var]
            print(f"\nF90 target '{target_var}':")
            print(f"  Interval: [{info['low']}, {info['high']}]")
            print(f"  Width: {info['width']}")
            print(f"  Finite: {info['finite']}")
    else:
        print("\n[FAIL] simulate_inputs returned None")
except Exception as e:
    print(f"\n[ERROR] {str(e)}")
    import traceback
    traceback.print_exc()

print("\n" + "=" * 70)
