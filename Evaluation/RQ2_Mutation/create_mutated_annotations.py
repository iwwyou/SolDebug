#!/usr/bin/env python3
"""
Create annotation files for mutated contracts using Z3 ranges
Generates 1,750 annotation files (25 mutations × 70 Z3 inputs)
"""
import json
import re
from pathlib import Path

# Directories
MUTATED_DIR = Path("Evaluation/Mutated_Contracts")
Z3_DIR = Path("Evaluation/RQ2_Z3_Focused")
OUTPUT_DIR = Path("Evaluation/RQ2_Mutated_Annotations")

# Extract base contract name from mutation filename
def get_base_contract(mutation_filename: str) -> str:
    """
    Extract base contract name from mutation filename
    Examples:
        Lock_c_pending_sub_to_add.sol → Lock_c
        HubPool_c__allocateLpAndProtocolFees_swap_mul_div.sol → HubPool_c
    """
    # Pattern: ContractName_functionName_mutationType.sol
    match = re.match(r'([A-Za-z_]+_c)_', mutation_filename)
    if match:
        return match.group(1)
    raise ValueError(f"Could not extract base contract from: {mutation_filename}")

def main():
    print("=" * 70)
    print("MUTATED CONTRACT ANNOTATION GENERATOR")
    print("=" * 70)

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Get all mutation files
    mutation_files = sorted(MUTATED_DIR.glob("*.sol"))
    print(f"\n[+] Found {len(mutation_files)} mutation files")

    total_generated = 0

    for mutation_file in mutation_files:
        mutation_name = mutation_file.stem  # filename without .sol
        base_contract = get_base_contract(mutation_file.name)

        print(f"\n[{base_contract}] Processing: {mutation_name}")

        # Find all Z3 annotations for this base contract
        z3_files = sorted(Z3_DIR.glob(f"{base_contract}_*.json"))

        if not z3_files:
            print(f"  [WARNING] No Z3 annotations found for {base_contract}")
            continue

        print(f"  Found {len(z3_files)} Z3 annotations")

        # Copy each Z3 annotation for this mutation
        for z3_file in z3_files:
            # Load Z3 annotation
            with open(z3_file, 'r', encoding='utf-8') as f:
                z3_annot = json.load(f)

            # Create output filename
            # Example: Lock_c_overlap_d1_z3.json → Lock_c_pending_sub_to_add_overlap_d1_z3.json
            z3_suffix = z3_file.name.replace(f"{base_contract}_", "")  # overlap_d1_z3.json
            output_name = f"{mutation_name}_{z3_suffix}"
            output_path = OUTPUT_DIR / output_name

            # Save annotation (same content as base, line numbers stay the same)
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(z3_annot, f, indent=2)

            total_generated += 1

        print(f"  Generated {len(z3_files)} annotations")

    print("\n" + "=" * 70)
    print(f"[DONE] Generated {total_generated} annotation files")
    print(f"[+] Output directory: {OUTPUT_DIR}")
    print("=" * 70)

if __name__ == "__main__":
    main()
