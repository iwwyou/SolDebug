#!/usr/bin/env python3
"""
Generate RQ2 experiments using actual annotation targets from evaluation_dataset.xlsx
Creates proper annotation JSONs with correct variable types (SV/LV/GV)
"""
import pandas as pd
import json
import re
from pathlib import Path
from typing import Dict, List, Tuple

# Configuration
DATASET_FILE = Path("dataset/evaluation_dataset.xlsx")
PATTERNS_JSON = Path("Evaluation/complex_arithmetic_patterns.json")
OUTPUT_DIR = Path("Evaluation/RQ2_Extended_v2")
DELTAS = [1, 3, 6, 10, 15]
ANNOTATION_PATTERNS = ["overlap", "diff"]

def parse_target_variables(target_str: str) -> Dict[str, List[str]]:
    """
    Parse target variable string from xlsx
    Format: "GV : var1, var2\nSV : var3\nLV : var4, var5"
    """
    if pd.isna(target_str):
        return {}

    result = {'GV': [], 'SV': [], 'LV': []}

    # Split by newlines
    lines = target_str.split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Match pattern: "TYPE : var1, var2, ..."
        match = re.match(r'(GV|SV|LV)\s*[:：]\s*(.+)', line)
        if match:
            var_type = match.group(1)
            vars_str = match.group(2).strip()

            # Split by comma and clean
            variables = [v.strip() for v in vars_str.split(',')]

            # Fix common typos
            variables = [v.replace('timsetamp', 'timestamp') for v in variables]
            variables = [v.replace('balancesOf', 'balanceOf') for v in variables]  # Potential typo

            result[var_type].extend(variables)

    return result

def generate_interval_ranges(pattern: str, delta: int, num_vars: int) -> List[Tuple[int, int]]:
    """Generate interval ranges based on pattern"""
    if pattern == "overlap":
        base = 100
        return [(base, base + delta) for _ in range(num_vars)]
    else:  # diff
        ranges = []
        for i in range(num_vars):
            base = 100 + i * (delta + 20)  # More separation
            ranges.append((base, base + delta))
        return ranges

def create_annotation_json(
    contract_name: str,
    func_name: str,
    target_vars: Dict[str, List[str]],
    mutation_type: str,
    delta: int,
    pattern: str,
    func_line: int
) -> List[Dict]:
    """
    Create annotation JSON events similar to Lock_c_annot.json format
    """
    events = []

    # Collect all variables
    all_vars = []
    var_types = []

    for var_type in ['GV', 'SV', 'LV']:
        for var in target_vars.get(var_type, []):
            all_vars.append(var)
            var_types.append(var_type)

    if not all_vars:
        return []

    # Generate ranges
    ranges = generate_interval_ranges(pattern, delta, len(all_vars))

    # Create annotation events
    current_line = func_line

    # BEGIN marker
    events.append({
        "code": f"// @Debugging BEGIN",
        "startLine": current_line,
        "endLine": current_line,
        "event": "add"
    })
    current_line += 1

    # Variable annotations
    var_type_map = {
        'GV': '@GlobalVar',
        'SV': '@StateVar',
        'LV': '@LocalVar'
    }

    for var, var_type, (low, high) in zip(all_vars, var_types, ranges):
        annotation = f"// {var_type_map[var_type]} {var} = [{low},{high}];"
        events.append({
            "code": annotation,
            "startLine": current_line,
            "endLine": current_line,
            "event": "add"
        })
        current_line += 1

    # END marker
    events.append({
        "code": "// @Debugging END",
        "startLine": current_line,
        "endLine": current_line,
        "event": "add"
    })

    return events

def load_evaluation_dataset() -> pd.DataFrame:
    """Load evaluation dataset xlsx"""
    df = pd.read_excel(DATASET_FILE, header=1)  # Header at row 1
    return df

def load_complex_patterns() -> Dict:
    """Load analyzed complex arithmetic patterns"""
    with open(PATTERNS_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)

def match_contract_to_dataset(contract_name: str, df: pd.DataFrame) -> pd.DataFrame:
    """Find matching rows in dataset for contract"""
    # Match by contract name (column 3)
    matched = df[df.iloc[:, 3].str.contains(contract_name.replace('_c', ''), case=False, na=False)]
    return matched

def main():
    print("=" * 70)
    print("RQ2 EXTENDED WITH ACTUAL ANNOTATION TARGETS")
    print("=" * 70)

    # Load data
    print("\n[+] Loading evaluation dataset...")
    df = load_evaluation_dataset()
    print(f"    Found {len(df)} contracts in dataset")

    print("\n[+] Loading complex arithmetic patterns...")
    patterns = load_complex_patterns()
    print(f"    Found {len(patterns)} contracts with complex arithmetic")

    OUTPUT_DIR.mkdir(exist_ok=True)

    total_experiments = 0
    generated_files = []

    # For each contract with complex arithmetic
    for contract_name, contract_data in patterns.items():
        print(f"\n[CONTRACT] {contract_name}")

        # Find in evaluation dataset
        matched_df = match_contract_to_dataset(contract_name, df)

        if matched_df.empty:
            print(f"  [WARNING] No match in evaluation dataset, skipping")
            continue

        for func_data in contract_data['functions']:
            func_name = func_data['function_name']
            func_line = func_data['line_number']

            # Find matching function in dataset
            func_match = matched_df[matched_df.iloc[:, 4].str.contains(func_name, case=False, na=False)]

            if func_match.empty:
                print(f"  [WARNING] Function {func_name} not in dataset, skipping")
                continue

            # Get target variables from Column 9
            target_vars_str = func_match.iloc[0, 9]
            target_vars = parse_target_variables(target_vars_str)

            total_vars = sum(len(v) for v in target_vars.values())
            if total_vars == 0:
                print(f"  [WARNING] No target variables for {func_name}, skipping")
                continue

            print(f"  [+] {func_name}() - {total_vars} variables")
            print(f"      GV: {len(target_vars.get('GV', []))}, "
                  f"SV: {len(target_vars.get('SV', []))}, "
                  f"LV: {len(target_vars.get('LV', []))}")

            # Generate experiments for each mutation
            for mutation_data in func_data['possible_mutations']:
                for mutation in mutation_data['mutations']:
                    mutation_type = mutation['type']

                    for delta in DELTAS:
                        for ann_pattern in ANNOTATION_PATTERNS:
                            # Create annotation JSON
                            annotations = create_annotation_json(
                                contract_name,
                                func_name,
                                target_vars,
                                mutation_type,
                                delta,
                                ann_pattern,
                                func_line
                            )

                            if not annotations:
                                continue

                            # Save to file
                            filename = f"{contract_name}_{func_name}_{mutation_type}_d{delta}_{ann_pattern}.json"
                            filepath = OUTPUT_DIR / filename

                            with open(filepath, 'w', encoding='utf-8') as f:
                                json.dump(annotations, f, indent=2)

                            generated_files.append({
                                'contract': contract_name,
                                'function': func_name,
                                'mutation': mutation_type,
                                'delta': delta,
                                'pattern': ann_pattern,
                                'file': str(filepath),
                                'num_variables': total_vars
                            })

                            total_experiments += 1

    # Save experiment index
    index_file = OUTPUT_DIR / "experiment_index.json"
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_experiments': total_experiments,
            'experiments': generated_files
        }, f, indent=2)

    print("\n" + "=" * 70)
    print("[SUMMARY]")
    print(f"  Total experiments: {total_experiments}")
    print(f"  Output directory: {OUTPUT_DIR}")
    print(f"  Index file: {index_file}")
    print("\n[DONE] Ready for execution!")

if __name__ == "__main__":
    main()
