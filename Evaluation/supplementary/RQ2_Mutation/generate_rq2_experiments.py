#!/usr/bin/env python3
"""
Generate RQ2 experiments for all complex arithmetic patterns
Creates test case JSONs with interval annotations for different operator mutations
"""
import json
from pathlib import Path
from typing import List, Dict, Tuple

# Configuration
PATTERNS_JSON = "Evaluation/complex_arithmetic_patterns.json"
OUTPUT_DIR = Path("Evaluation/RQ2_Extended")
DELTAS = [1, 3, 6, 10, 15]
ANNOTATION_PATTERNS = ["overlap", "diff"]

# Experiment template
EXPERIMENT_TEMPLATE = {
    "contract": "",
    "function": "",
    "original_line": "",
    "mutation_type": "",
    "delta": 0,
    "pattern": "",
    "test_file": ""
}

def load_patterns():
    """Load analyzed complex arithmetic patterns"""
    with open(PATTERNS_JSON, 'r', encoding='utf-8') as f:
        return json.load(f)

def generate_interval_ranges(pattern: str, delta: int, num_vars: int) -> List[Tuple[int, int]]:
    """
    Generate interval ranges based on pattern and delta
    Similar to Lock experiment but generalized
    """
    if pattern == "overlap":
        # All variables in overlapping ranges
        base = 100
        return [(base, base + delta) for _ in range(num_vars)]
    else:  # diff
        # Variables in distinct, non-overlapping ranges
        ranges = []
        for i in range(num_vars):
            base = 100 + i * (delta + 10)  # Add gap between ranges
            ranges.append((base, base + delta))
        return ranges

def extract_variables_from_expression(code: str) -> List[str]:
    """
    Extract variable names from arithmetic expression
    Simplified heuristic - can be improved
    """
    import re
    # Remove operators and extract potential variable names
    tokens = re.findall(r'\b[a-zA-Z_]\w*\b', code)

    # Filter out keywords and constants
    keywords = {'return', 'uint256', 'uint', 'int256', 'int',
                'if', 'else', 'for', 'while', 'require'}

    variables = []
    for token in tokens:
        if token not in keywords and not token.isupper():  # Skip ALL_CAPS (constants)
            variables.append(token)

    return list(dict.fromkeys(variables))  # Remove duplicates, preserve order

def create_test_case_json(
    contract_name: str,
    func_name: str,
    line_number: int,
    mutation_type: str,
    delta: int,
    pattern: str,
    variables: List[str]
) -> Dict:
    """
    Create test case JSON similar to Lock experiment format
    """
    ranges = generate_interval_ranges(pattern, delta, len(variables))

    # Build annotation events
    events = []
    start_line = line_number

    # Add test case marker
    events.append({
        "code": f"// @TestCase BEGIN: {mutation_type} delta={delta} pattern={pattern}",
        "startLine": start_line,
        "endLine": start_line,
        "event": "add"
    })

    # Add variable annotations
    for i, (var, (low, high)) in enumerate(zip(variables, ranges)):
        start_line += 1
        events.append({
            "code": f"// @StateVar {var} = [{low},{high}]",
            "startLine": start_line,
            "endLine": start_line,
            "event": "add"
        })

    # Add end marker
    start_line += 1
    events.append({
        "code": "// @TestCase END",
        "startLine": start_line,
        "endLine": start_line,
        "event": "add"
    })

    return {
        "metadata": {
            "contract": contract_name,
            "function": func_name,
            "mutation": mutation_type,
            "delta": delta,
            "pattern": pattern,
            "num_variables": len(variables)
        },
        "annotations": events
    }

def generate_experiments_for_contract(contract_name: str, contract_data: Dict) -> List[Dict]:
    """Generate all experiment variations for a contract"""
    experiments = []

    for func_data in contract_data['functions']:
        func_name = func_data['function_name']
        line_num = func_data['line_number']

        for mutation_data in func_data['possible_mutations']:
            line_info = mutation_data['line']
            code = line_info['code']

            # Extract variables
            variables = extract_variables_from_expression(code)
            if not variables:
                continue

            for mutation in mutation_data['mutations']:
                mutation_type = mutation['type']

                # Generate for all delta and pattern combinations
                for delta in DELTAS:
                    for pattern in ANNOTATION_PATTERNS:
                        test_case = create_test_case_json(
                            contract_name,
                            func_name,
                            line_num + line_info['line_offset'],
                            mutation_type,
                            delta,
                            pattern,
                            variables
                        )

                        experiments.append({
                            'contract': contract_name,
                            'function': func_name,
                            'mutation': mutation_type,
                            'delta': delta,
                            'pattern': pattern,
                            'test_case': test_case
                        })

    return experiments

def main():
    print("=" * 70)
    print("RQ2 EXTENDED EXPERIMENT GENERATOR")
    print("=" * 70)

    # Load patterns
    patterns = load_patterns()
    print(f"\n[+] Loaded {len(patterns)} contracts with complex arithmetic")

    # Create output directory
    OUTPUT_DIR.mkdir(exist_ok=True)

    # Generate experiments
    all_experiments = []
    experiment_summary = []

    for contract_name, contract_data in patterns.items():
        print(f"\n[CONTRACT] {contract_name}")

        experiments = generate_experiments_for_contract(contract_name, contract_data)
        all_experiments.extend(experiments)

        # Group by function and mutation type
        func_mutations = {}
        for exp in experiments:
            key = (exp['function'], exp['mutation'])
            func_mutations[key] = func_mutations.get(key, 0) + 1

        for (func, mut), count in func_mutations.items():
            print(f"  {func}() - {mut}: {count} test cases")
            experiment_summary.append({
                'contract': contract_name,
                'function': func,
                'mutation': mut,
                'num_tests': count
            })

    # Save individual test case files
    print(f"\n[SAVING] Generating {len(all_experiments)} test case files...")

    for i, exp in enumerate(all_experiments):
        filename = f"{exp['contract']}_{exp['function']}_{exp['mutation']}_d{exp['delta']}_{exp['pattern']}.json"
        filepath = OUTPUT_DIR / filename

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(exp['test_case']['annotations'], f, indent=2)

    # Save master experiment index
    index_file = OUTPUT_DIR / "experiment_index.json"
    with open(index_file, 'w', encoding='utf-8') as f:
        json.dump({
            'total_experiments': len(all_experiments),
            'contracts': len(patterns),
            'deltas': DELTAS,
            'patterns': ANNOTATION_PATTERNS,
            'experiments': all_experiments
        }, f, indent=2)

    # Save summary
    summary_file = OUTPUT_DIR / "experiment_summary.json"
    with open(summary_file, 'w', encoding='utf-8') as f:
        json.dump(experiment_summary, f, indent=2)

    print(f"\n[SUMMARY]")
    print(f"  Total test cases: {len(all_experiments)}")
    print(f"  Contracts: {len(patterns)}")
    print(f"  Unique functions: {len(set(e['function'] for e in all_experiments))}")
    print(f"  Mutation types: {len(set(e['mutation'] for e in all_experiments))}")
    print(f"\n[+] Output directory: {OUTPUT_DIR}")
    print(f"[+] Index file: {index_file}")
    print(f"[+] Ready for batch execution!")

if __name__ == "__main__":
    main()
