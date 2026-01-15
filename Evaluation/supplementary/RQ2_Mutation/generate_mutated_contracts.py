#!/usr/bin/env python3
"""
Generate mutated versions of contracts for inspection
Creates separate .sol files with mutations applied
"""
import json
import re
from pathlib import Path
from typing import Dict, List

# Configuration
EXPERIMENT_INDEX = Path("Evaluation/RQ2_Extended_v2/experiment_index.json")
CONTRACT_DIR = Path("dataset/contraction")
OUTPUT_DIR = Path("Evaluation/Mutated_Contracts")

def apply_mutation_to_code(code: str, mutation_type: str) -> str:
    """Apply operator mutation to code"""
    if mutation_type == 'sub_to_add':
        # Change - to + (preserve -- and ->)
        result = re.sub(r'(\w+)\s*-\s*(\w+)', r'\1 + \2', code)
        return result
    elif mutation_type == 'add_to_sub':
        # Change + to -
        result = re.sub(r'(\w+)\s*\+\s*(\w+)', r'\1 - \2', code)
        return result
    elif mutation_type == 'swap_add_sub':
        # Preserve ++ and --
        temp = code.replace('++', '@PLUSPLUS@').replace('--', '@MINUSMINUS@')
        temp = temp.replace('->', '@ARROW@')
        temp = temp.replace('+', '@PLUS@').replace('-', '@MINUS@')
        temp = temp.replace('@PLUS@', '-').replace('@MINUS@', '+')
        temp = temp.replace('@PLUSPLUS@', '++').replace('@MINUSMINUS@', '--')
        temp = temp.replace('@ARROW@', '->')
        return temp
    elif mutation_type == 'swap_mul_div':
        temp = code.replace('*', '@MUL@').replace('/', '@DIV@')
        temp = temp.replace('@MUL@', '/').replace('@DIV@', '*')
        return temp
    else:
        return code

def mutate_contract_function(
    contract_file: Path,
    function_name: str,
    mutation_type: str
) -> str:
    """
    Mutate specific function in contract
    Returns mutated contract source
    """
    content = contract_file.read_text(encoding='utf-8')
    lines = content.split('\n')

    # Find function boundaries
    in_target_function = False
    brace_count = 0
    mutated_lines = []

    for line in lines:
        stripped = line.strip()

        # Detect function start
        if f'function {function_name}' in line:
            in_target_function = True
            mutated_lines.append(line)
            continue

        # Track braces
        if in_target_function:
            brace_count += line.count('{') - line.count('}')

            # Apply mutation if in function body
            if any(op in line for op in ['+', '-', '*', '/']):
                mutated_line = apply_mutation_to_code(line, mutation_type)
                mutated_lines.append(mutated_line)
            else:
                mutated_lines.append(line)

            # Check if function ended
            if brace_count == 0 and '}' in line:
                in_target_function = False
        else:
            mutated_lines.append(line)

    return '\n'.join(mutated_lines)

def main():
    print("=" * 70)
    print("MUTATED CONTRACT GENERATOR")
    print("=" * 70)

    # Load experiment index
    with open(EXPERIMENT_INDEX, 'r', encoding='utf-8') as f:
        index_data = json.load(f)

    experiments = index_data['experiments']

    # Group by contract + function + mutation
    unique_mutations = {}
    for exp in experiments:
        key = (exp['contract'], exp['function'], exp['mutation'])
        if key not in unique_mutations:
            unique_mutations[key] = exp

    print(f"\nTotal unique mutations: {len(unique_mutations)}")
    print(f"(Each mutation will be applied once, not per delta/pattern)")

    OUTPUT_DIR.mkdir(exist_ok=True)

    # Create summary document
    summary_lines = ["# Mutated Contracts Summary\n\n"]
    summary_lines.append("Generated: " + str(Path.cwd()) + "\n\n")

    mutation_count = 0

    for (contract, function, mutation), exp in unique_mutations.items():
        contract_file = CONTRACT_DIR / f"{contract}.sol"

        if not contract_file.exists():
            print(f"[SKIP] {contract}.sol not found")
            continue

        print(f"\n[{mutation_count+1}/{len(unique_mutations)}] {contract}.{function}() - {mutation}")

        # Create mutated version
        mutated_code = mutate_contract_function(contract_file, function, mutation)

        # Save to file
        output_filename = f"{contract}_{function}_{mutation}.sol"
        output_path = OUTPUT_DIR / output_filename

        with open(output_path, 'w', encoding='utf-8') as f:
            f.write(f"// MUTATED CONTRACT: {contract}\n")
            f.write(f"// Function: {function}\n")
            f.write(f"// Mutation: {mutation}\n")
            f.write(f"// Original: {contract_file}\n")
            f.write("\n")
            f.write(mutated_code)

        print(f"  [+] Saved to {output_filename}")

        # Add to summary
        summary_lines.append(f"## {contract}.{function}() - `{mutation}`\n\n")
        summary_lines.append(f"- **File**: `{output_filename}`\n")
        summary_lines.append(f"- **Original**: `{contract}.sol`\n")
        summary_lines.append(f"- **Mutation Type**: {mutation}\n")

        # Extract and show the mutated lines
        original_lines = contract_file.read_text(encoding='utf-8').split('\n')
        mutated_lines = mutated_code.split('\n')

        # Find differences
        diffs = []
        for i, (orig, mut) in enumerate(zip(original_lines, mutated_lines)):
            if orig != mut and any(op in orig for op in ['+', '-', '*', '/']):
                diffs.append((i+1, orig.strip(), mut.strip()))

        if diffs:
            summary_lines.append(f"\n**Changes** ({len(diffs)} lines modified):\n\n")
            for line_num, orig, mut in diffs[:5]:  # Show first 5
                summary_lines.append(f"Line {line_num}:\n")
                summary_lines.append(f"```solidity\n")
                summary_lines.append(f"- {orig}\n")
                summary_lines.append(f"+ {mut}\n")
                summary_lines.append(f"```\n\n")

        summary_lines.append("---\n\n")
        mutation_count += 1

    # Save summary
    summary_file = OUTPUT_DIR / "MUTATIONS_SUMMARY.md"
    with open(summary_file, 'w', encoding='utf-8') as f:
        f.writelines(summary_lines)

    print(f"\n{'='*70}")
    print(f"[DONE] Generated {mutation_count} mutated contracts")
    print(f"[+] Output directory: {OUTPUT_DIR}")
    print(f"[+] Summary: {summary_file}")
    print("=" * 70)

if __name__ == "__main__":
    main()
