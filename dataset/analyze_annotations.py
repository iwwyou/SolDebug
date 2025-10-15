"""
Analyze all annotation files to identify types and value patterns
"""
import json
import re
from pathlib import Path
from collections import defaultdict

def extract_annotation_info(annotation_file):
    """Extract @StateVar, @LocalVar, @GlobalVar from annotation file"""
    with open(annotation_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    annotations = {
        'StateVar': [],
        'LocalVar': [],
        'GlobalVar': []
    }

    for entry in data:
        code = entry.get('code', '')

        # Match patterns like: // @StateVar varName = value;
        for var_type in ['StateVar', 'LocalVar', 'GlobalVar']:
            pattern = rf'// @{var_type}\s+(\S+)\s*=\s*(.+?);'
            match = re.search(pattern, code)
            if match:
                var_name = match.group(1)
                var_value = match.group(2).strip()
                annotations[var_type].append({
                    'name': var_name,
                    'value': var_value
                })

    return annotations

def analyze_value_pattern(value_str):
    """Analyze what kind of value pattern this is"""
    value_str = value_str.strip()

    # Pattern 1: Interval [min, max]
    if re.match(r'\[\d+,\s*\d+\]', value_str):
        return 'interval', value_str

    # Pattern 2: any
    if value_str.lower() == 'any':
        return 'any', value_str

    # Pattern 3: symbolicAddress N
    if 'symbolicaddress' in value_str.lower():
        return 'symbolicAddress', value_str

    # Pattern 4: Single value
    if re.match(r'^\d+$', value_str):
        return 'single_value', value_str

    # Pattern 5: Complex (everything else)
    return 'complex', value_str

def main():
    annotation_dir = Path('json/annotation')

    # Statistics
    all_types = defaultdict(int)
    value_patterns = defaultdict(int)
    complex_examples = []

    print("="*70)
    print("ANNOTATION ANALYSIS")
    print("="*70)

    # Process all annotation files
    for annot_file in sorted(annotation_dir.glob('*_annot.json')):
        contract_name = annot_file.stem.replace('_annot', '')
        print(f"\n{'='*70}")
        print(f"Contract: {contract_name}")
        print(f"{'='*70}")

        try:
            annotations = extract_annotation_info(annot_file)

            for var_type in ['StateVar', 'LocalVar', 'GlobalVar']:
                if annotations[var_type]:
                    print(f"\n{var_type}s:")
                    for var in annotations[var_type]:
                        pattern_type, pattern_value = analyze_value_pattern(var['value'])
                        print(f"  - {var['name']} = {var['value']}")
                        print(f"    → Pattern: {pattern_type}")

                        # Track statistics
                        all_types[var_type] += 1
                        value_patterns[pattern_type] += 1

                        # Collect complex examples
                        if pattern_type == 'complex':
                            complex_examples.append({
                                'contract': contract_name,
                                'var_type': var_type,
                                'name': var['name'],
                                'value': var['value']
                            })

        except Exception as e:
            print(f"  [ERROR] Failed to process: {e}")

    # Print summary
    print("\n" + "="*70)
    print("SUMMARY STATISTICS")
    print("="*70)

    print("\nVariable Types:")
    for var_type, count in sorted(all_types.items()):
        print(f"  {var_type}: {count}")

    print("\nValue Patterns:")
    for pattern, count in sorted(value_patterns.items(), key=lambda x: -x[1]):
        print(f"  {pattern}: {count}")

    if complex_examples:
        print("\n" + "="*70)
        print("COMPLEX VALUE EXAMPLES (need special handling)")
        print("="*70)
        for ex in complex_examples[:20]:  # Show first 20
            print(f"\n{ex['contract']} - {ex['var_type']}: {ex['name']}")
            print(f"  Value: {ex['value']}")

    print("\n" + "="*70)

if __name__ == "__main__":
    main()
