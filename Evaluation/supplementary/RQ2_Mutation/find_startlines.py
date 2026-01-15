#!/usr/bin/env python3
"""Find startLine for @Debugging BEGIN in each base annotation"""
import json
from pathlib import Path

base_dir = Path("dataset/json/annotation")
contracts = {
    "GovStakingStorage_c": "GovStakingStorage_c_annot.json",
    "GreenHouse_c": "GreenHouse_c_annot.json",
    "HubPool_c": "HubPool_c_annot.json",
    "Lock_c": "Lock_c_annot.json",
    "LockupContract_c": "LockupContract_c_annot.json",
    "PoolKeeper_c": "PoolKeeper_c_annot.json",
    "ThorusBond_c": "ThorusBond_c_annot.json"
}

print("Contract StartLines:")
print("=" * 50)

start_lines = {}
for contract, annot_file in contracts.items():
    file_path = base_dir / annot_file
    if file_path.exists():
        with open(file_path, 'r', encoding='utf-8') as f:
            annot = json.load(f)

        # Find @Debugging BEGIN
        for rec in annot:
            if "@Debugging BEGIN" in rec.get("code", ""):
                start_line = rec['startLine']
                start_lines[contract] = start_line
                print(f"{contract:25s}: {start_line}")
                break
    else:
        print(f"{contract:25s}: FILE NOT FOUND")

print("\n" + "=" * 50)
print(f"Found {len(start_lines)} contracts")

# Save to JSON for later use
output = Path("Evaluation/RQ2_Mutation/contract_startlines.json")
with open(output, 'w', encoding='utf-8') as f:
    json.dump(start_lines, f, indent=2)
print(f"Saved to: {output}")
