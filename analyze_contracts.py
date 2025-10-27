import os
import re
from pathlib import Path

contraction_dir = Path("dataset/contraction")

stats = {
    'total': 0,
    'loc': [],
    'has_struct': 0,
    'struct_fields': [],
    'has_mapping': 0,
    'has_array': 0,
    'has_loop': 0,
    'has_nested_mapping': 0,
    'function_calls': 0,
    'has_modifier': 0,
    'nested_conditionals': 0
}

for file in contraction_dir.glob("*_c.sol"):
    stats['total'] += 1

    with open(file, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
        lines = content.split('\n')
        stats['loc'].append(len([l for l in lines if l.strip()]))

        # Struct analysis
        struct_matches = re.findall(r'struct\s+\w+\s*\{([^}]*)\}', content, re.DOTALL)
        if struct_matches:
            stats['has_struct'] += 1
            for struct_body in struct_matches:
                fields = len([l for l in struct_body.split(';') if l.strip()])
                if fields > 0:
                    stats['struct_fields'].append(fields)

        # Data structures
        if re.search(r'\bmapping\s*\(', content):
            stats['has_mapping'] += 1
        if re.search(r'\[\]\s+', content) or re.search(r'\bpush\(', content):
            stats['has_array'] += 1
        if re.search(r'mapping\s*\([^)]*mapping', content):
            stats['has_nested_mapping'] += 1

        # Control flow
        if re.search(r'\bfor\s*\(|\bwhile\s*\(', content):
            stats['has_loop'] += 1

        # Function calls (internal)
        internal_calls = len(re.findall(r'(\w+)\s*\([^)]*\)\s*;', content))
        if internal_calls > 5:  # Arbitrary threshold
            stats['function_calls'] += 1

        # Modifiers
        if re.search(r'\bmodifier\s+\w+', content):
            stats['has_modifier'] += 1

        # Nested conditionals (very rough estimate)
        if content.count('if (') >= 3:
            stats['nested_conditionals'] += 1

print("=== Contract Analysis ===")
print(f"Total contracts: {stats['total']}")
print(f"\nLOC Statistics:")
print(f"  Range: {min(stats['loc'])} - {max(stats['loc'])}")
print(f"  Average: {sum(stats['loc'])/len(stats['loc']):.1f}")
print(f"\nData Structure Complexity:")
print(f"  Contracts with structs: {stats['has_struct']} ({stats['has_struct']/stats['total']*100:.0f}%)")
if stats['struct_fields']:
    print(f"  Struct fields range: {min(stats['struct_fields']}-{max(stats['struct_fields'])}")
    large_structs = len([f for f in stats['struct_fields'] if f >= 5])
    print(f"  Structs with 5+ fields: {large_structs}")
print(f"  Contracts with mappings: {stats['has_mapping']} ({stats['has_mapping']/stats['total']*100:.0f}%)")
print(f"  Contracts with arrays: {stats['has_array']} ({stats['has_array']/stats['total']*100:.0f}%)")
print(f"  Contracts with nested mappings: {stats['has_nested_mapping']}")
print(f"\nControl Flow Complexity:")
print(f"  Contracts with loops: {stats['has_loop']}")
print(f"  Contracts with modifiers: {stats['has_modifier']}")
print(f"  Contracts with multiple conditionals: {stats['nested_conditionals']}")
