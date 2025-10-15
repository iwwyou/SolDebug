"""
Add array setter functions to all contracts in contraction_remix folder
"""
import re
from pathlib import Path

def parse_contract_arrays(sol_content):
    """Find all array state variables in the contract"""
    arrays = []

    # Pattern: type[] visibility name;
    # Examples: uint256[] public tokens; address[] private owners;
    pattern = r'(\w+)\[\]\s+(public|private|internal)?\s*(\w+);'

    for match in re.finditer(pattern, sol_content):
        var_type = match.group(1)
        visibility = match.group(2) or 'internal'
        var_name = match.group(3)

        arrays.append({
            'type': var_type,
            'name': var_name,
            'visibility': visibility
        })

    return arrays

def has_array_setter(sol_content, array_name):
    """Check if array setter function already exists"""
    # Pattern: function _add{ArrayName}At or function set_{arrayName}
    pattern1 = rf'function\s+_add{array_name[0].upper() + array_name[1:]}At'
    pattern2 = rf'function\s+set_{array_name}'

    return bool(re.search(pattern1, sol_content, re.IGNORECASE)) or \
           bool(re.search(pattern2, sol_content, re.IGNORECASE))

def generate_array_setter(array_info):
    """Generate setter function for array"""
    var_type = array_info['type']
    var_name = array_info['name']

    # Function name: _add{ArrayName}At (capitalize first letter)
    func_name = f"_add{var_name[0].upper() + var_name[1:]}At"

    # Handle special case: if name starts with underscore
    if var_name.startswith('_'):
        func_name = f"_add{var_name[1].upper() + var_name[2:]}At"

    setter_code = f"""
    // Auto-generated setter for array {var_name}
    function {func_name}({var_type} _value, uint256 _index) public {{
        uint256 currentLength = {var_name}.length;

        if (currentLength == 0 || currentLength - 1 < _index) {{
            uint256 additionalCount = _index - currentLength + 1;
            for (uint256 i = 0; i < additionalCount; i++) {{
                {var_name}.push();
            }}
        }}
        {var_name}[_index] = _value;
    }}
"""

    return setter_code

def add_setters_to_contract(sol_file):
    """Add missing array setters to a contract file"""
    print(f"\n{'='*70}")
    print(f"Processing: {sol_file.name}")
    print(f"{'='*70}")

    with open(sol_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Parse contract to find arrays
    arrays = parse_contract_arrays(content)

    if not arrays:
        print("  No arrays found")
        return False

    print(f"  Found {len(arrays)} array(s):")
    for arr in arrays:
        print(f"    - {arr['type']}[] {arr['name']}")

    # Check which arrays need setters
    arrays_needing_setters = []
    for arr in arrays:
        if not has_array_setter(content, arr['name']):
            arrays_needing_setters.append(arr)
            print(f"  → {arr['name']}: needs setter")
        else:
            print(f"  → {arr['name']}: already has setter")

    if not arrays_needing_setters:
        print("  All arrays already have setters!")
        return False

    # Generate setters
    print(f"\n  Generating {len(arrays_needing_setters)} setter(s)...")
    new_setters = []
    for arr in arrays_needing_setters:
        setter_code = generate_array_setter(arr)
        new_setters.append(setter_code)

    # Insert setters before the last closing brace
    # Find the last } in the file (contract closing)
    last_brace_pos = content.rfind('}')

    if last_brace_pos == -1:
        print("  ERROR: Could not find closing brace")
        return False

    # Insert setters before the last brace
    new_content = content[:last_brace_pos] + '\n'.join(new_setters) + '\n' + content[last_brace_pos:]

    # Write back
    with open(sol_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"  ✓ Added {len(new_setters)} setter function(s)")
    return True

def main():
    remix_dir = Path('contraction_remix')

    if not remix_dir.exists():
        print(f"ERROR: Directory {remix_dir} does not exist")
        return

    print("="*70)
    print("ADDING ARRAY SETTERS TO REMIX CONTRACTS")
    print("="*70)

    sol_files = list(remix_dir.glob('*.sol'))
    print(f"\nFound {len(sol_files)} Solidity files")

    modified_count = 0

    for sol_file in sorted(sol_files):
        try:
            if add_setters_to_contract(sol_file):
                modified_count += 1
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\n" + "="*70)
    print(f"SUMMARY: Modified {modified_count} / {len(sol_files)} contracts")
    print("="*70)

if __name__ == "__main__":
    main()
