#!/usr/bin/env python3
"""
Analyze all contracts in dataset/contraction for complex arithmetic patterns
Extract functions with multiple operators for RQ2 expansion experiments
"""
import re
import json
from pathlib import Path
from collections import defaultdict

DATASET_DIR = Path("dataset/contraction")
OUTPUT_JSON = "Evaluation/complex_arithmetic_patterns.json"

# Patterns to identify complex arithmetic
ARITHMETIC_OPS = r'[\+\-\*/]'
MULTI_OP_PATTERN = re.compile(
    rf'{ARITHMETIC_OPS}.*{ARITHMETIC_OPS}'  # At least 2 operators
)

def extract_functions(sol_file):
    """Extract function definitions and their content"""
    content = sol_file.read_text(encoding='utf-8', errors='ignore')

    # Simple function extraction (handles most cases)
    func_pattern = re.compile(
        r'function\s+(\w+)\s*\([^)]*\)[^{]*\{([^}]+(?:\{[^}]*\}[^}]*)*)\}',
        re.MULTILINE | re.DOTALL
    )

    functions = []
    for match in func_pattern.finditer(content):
        func_name = match.group(1)
        func_body = match.group(2)
        start_pos = match.start()

        # Count line number
        line_num = content[:start_pos].count('\n') + 1

        functions.append({
            'name': func_name,
            'body': func_body,
            'line': line_num,
            'full_match': match.group(0)
        })

    return functions

def analyze_arithmetic_complexity(func_body):
    """Analyze arithmetic operations in function body"""
    lines = func_body.split('\n')
    complex_lines = []

    for i, line in enumerate(lines):
        # Skip comments
        line = re.sub(r'//.*$', '', line)

        # Find lines with multiple operators
        if MULTI_OP_PATTERN.search(line):
            # Count operators
            ops = {
                'add': line.count('+') - line.count('++'),
                'sub': line.count('-') - line.count('--'),
                'mul': line.count('*'),
                'div': line.count('/')
            }

            total_ops = sum(ops.values())
            if total_ops >= 2:
                complex_lines.append({
                    'line_offset': i,
                    'code': line.strip(),
                    'operators': ops,
                    'total_ops': total_ops
                })

    return complex_lines

def identify_operator_mutations(complex_lines):
    """Identify possible operator mutations for experiments"""
    mutations = []

    for line_info in complex_lines:
        ops = line_info['operators']
        possible_mutations = []

        # Suggest operator swaps
        if ops['add'] > 0 and ops['sub'] > 0:
            possible_mutations.append({
                'type': 'swap_add_sub',
                'description': 'Swap + and - operators'
            })

        if ops['add'] > 0:
            possible_mutations.append({
                'type': 'add_to_sub',
                'description': 'Change + to -'
            })

        if ops['sub'] > 0:
            possible_mutations.append({
                'type': 'sub_to_add',
                'description': 'Change - to +'
            })

        if ops['mul'] > 0 and ops['div'] > 0:
            possible_mutations.append({
                'type': 'swap_mul_div',
                'description': 'Swap * and /'
            })

        if ops['div'] > 0:
            possible_mutations.append({
                'type': 'has_division',
                'description': 'Contains division (normalization pattern)'
            })

        if possible_mutations:
            mutations.append({
                'line': line_info,
                'mutations': possible_mutations
            })

    return mutations

def main():
    results = {}

    print("Analyzing all contracts in dataset/contraction...")
    print("=" * 60)

    for sol_file in sorted(DATASET_DIR.glob("*.sol")):
        contract_name = sol_file.stem
        print(f"\n[FILE] {contract_name}")

        functions = extract_functions(sol_file)
        contract_data = []

        for func in functions:
            complex_lines = analyze_arithmetic_complexity(func['body'])

            if complex_lines:
                mutations = identify_operator_mutations(complex_lines)

                func_data = {
                    'function_name': func['name'],
                    'line_number': func['line'],
                    'complex_expressions': len(complex_lines),
                    'total_operators': sum(cl['total_ops'] for cl in complex_lines),
                    'complex_lines': complex_lines,
                    'possible_mutations': mutations
                }

                contract_data.append(func_data)

                print(f"  [+] {func['name']}() - Line {func['line']}")
                print(f"    Complex expressions: {len(complex_lines)}, "
                      f"Total ops: {func_data['total_operators']}")

                # Show example lines
                for cl in complex_lines[:2]:  # First 2 examples
                    print(f"    -> {cl['code'][:80]}...")

        if contract_data:
            results[contract_name] = {
                'file': str(sol_file),
                'functions': contract_data,
                'total_functions': len(contract_data),
                'total_complex_expr': sum(f['complex_expressions'] for f in contract_data)
            }

    # Save results
    output_path = Path(OUTPUT_JSON)
    output_path.write_text(json.dumps(results, indent=2), encoding='utf-8')

    print("\n" + "=" * 60)
    print(f"[SUMMARY]")
    print(f"  Contracts with complex arithmetic: {len(results)}")
    print(f"  Total functions: {sum(r['total_functions'] for r in results.values())}")
    print(f"  Total complex expressions: {sum(r['total_complex_expr'] for r in results.values())}")
    print(f"\n[+] Results saved to: {OUTPUT_JSON}")

if __name__ == "__main__":
    main()
