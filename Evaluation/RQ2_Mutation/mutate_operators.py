#!/usr/bin/env python3
"""
Automatic operator mutation for RQ2 experiments
Creates mutated versions of contracts with operator changes
"""
import re
from pathlib import Path
from typing import Dict, List

MUTATIONS = {
    'sub_to_add': {
        'description': 'Change - to +',
        'pattern': r'(\w+)\s*-\s*(\w+)',
        'replacement': r'\1 + \2'
    },
    'add_to_sub': {
        'description': 'Change + to -',
        'pattern': r'(\w+)\s*\+\s*(\w+)',
        'replacement': r'\1 - \2'
    },
    'swap_add_sub': {
        'description': 'Swap + and -',
        'pattern': r'([+-])',
        'replacement': lambda m: '+' if m.group(1) == '-' else '-'
    },
    'swap_mul_div': {
        'description': 'Swap * and /',
        'pattern': r'([*/])',
        'replacement': lambda m: '*' if m.group(1) == '/' else '/'
    }
}

def mutate_line(line: str, mutation_type: str) -> str:
    """Apply mutation to a single line"""
    if mutation_type not in MUTATIONS:
        return line

    mut = MUTATIONS[mutation_type]
    pattern = mut['pattern']
    replacement = mut['replacement']

    return re.sub(pattern, replacement, line)

def mutate_contract_at_line(
    sol_file: Path,
    target_line: int,
    mutation_type: str
) -> str:
    """
    Mutate a specific line in the contract
    Returns the mutated contract source code
    """
    lines = sol_file.read_text(encoding='utf-8').split('\n')

    if target_line <= 0 or target_line > len(lines):
        raise ValueError(f"Line {target_line} out of range (1-{len(lines)})")

    # Line numbers are 1-indexed
    idx = target_line - 1
    original_line = lines[idx]
    mutated_line = mutate_line(original_line, mutation_type)

    lines[idx] = mutated_line

    return '\n'.join(lines)

def create_mutated_contract_json(
    sol_file: Path,
    mutation_type: str,
    output_dir: Path
) -> Dict:
    """
    Create mutated contract as incremental JSON updates
    Returns dict with contract structure and mutations
    """
    # For now, just mutate the whole contract
    # In a more sophisticated version, we'd only mutate the target function

    lines = sol_file.read_text(encoding='utf-8').split('\n')

    # Create JSON representation
    events = []
    for i, line in enumerate(lines, start=1):
        # Check if this line has operators that should be mutated
        should_mutate = False
        if mutation_type in ['sub_to_add', 'add_to_sub']:
            should_mutate = '+' in line or '-' in line
        elif mutation_type == 'swap_mul_div':
            should_mutate = '*' in line or '/' in line

        # Apply mutation if needed
        final_line = mutate_line(line, mutation_type) if should_mutate else line

        events.append({
            "code": final_line,
            "startLine": i,
            "endLine": i,
            "event": "add"
        })

    return events

def test_mutation():
    """Test mutation functions"""
    test_cases = [
        ("uint256 x = a - b;", "sub_to_add", "uint256 x = a + b;"),
        ("uint256 x = a + b;", "add_to_sub", "uint256 x = a - b;"),
        ("uint256 x = a * b / c;", "swap_mul_div", "uint256 x = a / b * c;"),
    ]

    print("Testing mutations...")
    for original, mut_type, expected in test_cases:
        result = mutate_line(original, mut_type)
        status = "[OK]" if result == expected else "[FAIL]"
        print(f"{status} {mut_type}:")
        print(f"  Original: {original}")
        print(f"  Expected: {expected}")
        print(f"  Got:      {result}")

if __name__ == "__main__":
    test_mutation()
