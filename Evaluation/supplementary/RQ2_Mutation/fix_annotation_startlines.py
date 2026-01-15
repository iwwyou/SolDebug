#!/usr/bin/env python3
"""Fix startLine/endLine in mutated annotations"""
import json
import re
from pathlib import Path

# Load contract startlines
with open("Evaluation/RQ2_Mutation/contract_startlines.json", 'r') as f:
    CONTRACT_STARTLINES = json.load(f)

ANNOT_DIR = Path("Evaluation/RQ2_Mutation/RQ2_Mutated_Annotations")

def get_base_contract(filename: str) -> str:
    """Extract base contract name from filename"""
    match = re.match(r'([A-Za-z_]+_c)_', filename)
    if match:
        return match.group(1)
    return None

def fix_startlines(annot_file: Path):
    """Fix startLine/endLine in annotation file"""
    # Get base contract
    base_contract = get_base_contract(annot_file.name)
    if not base_contract or base_contract not in CONTRACT_STARTLINES:
        return False

    # Get correct start line
    correct_start = CONTRACT_STARTLINES[base_contract]

    # Load annotation
    with open(annot_file, 'r', encoding='utf-8') as f:
        annot = json.load(f)

    # Fix startLine/endLine
    # Current: starts at 1
    # Target: starts at correct_start
    offset = correct_start - 1

    for rec in annot:
        rec['startLine'] += offset
        rec['endLine'] += offset

    # Save fixed annotation
    with open(annot_file, 'w', encoding='utf-8') as f:
        json.dump(annot, f, indent=2)

    return True

def main():
    print("=" * 70)
    print("FIXING ANNOTATION STARTLINES")
    print("=" * 70)

    annot_files = sorted(ANNOT_DIR.glob("*.json"))
    print(f"\n[+] Found {len(annot_files)} annotation files")

    fixed = 0
    failed = 0

    for idx, annot_file in enumerate(annot_files, 1):
        if fix_startlines(annot_file):
            fixed += 1
            if idx % 50 == 0:
                print(f"  [{idx}/{len(annot_files)}] Fixed...")
        else:
            failed += 1
            print(f"  [ERROR] Could not fix: {annot_file.name}")

    print("\n" + "=" * 70)
    print(f"[DONE] Fixed: {fixed}, Failed: {failed}")
    print("=" * 70)

if __name__ == "__main__":
    main()
