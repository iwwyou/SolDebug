"""
Automatically add missing setter functions to all contracts
This script:
1. Reads each input.json file
2. Finds the corresponding .sol file
3. Parses variable types from the .sol file
4. Generates appropriate setter functions based on variable types
5. Adds setters to the .sol file if they don't exist
"""
import json
import re
from pathlib import Path


def extract_struct_names(sol_content):
    """Extract all struct type names from struct definitions"""
    struct_names = set()

    # Find all struct blocks
    struct_pattern = r'struct\s+(\w+)\s*\{'
    for match in re.finditer(struct_pattern, sol_content, re.DOTALL):
        struct_names.add(match.group(1))

    return struct_names


def extract_struct_field_names(sol_content):
    """Extract all field names from struct definitions"""
    field_names = set()

    # Find all struct blocks
    struct_pattern = r'struct\s+\w+\s*\{([^}]+)\}'
    for match in re.finditer(struct_pattern, sol_content, re.DOTALL):
        struct_body = match.group(1)
        # Extract field declarations: type fieldName;
        field_pattern = r'\s*\w+\s+(\w+)\s*;'
        for field_match in re.finditer(field_pattern, struct_body):
            field_names.add(field_match.group(1))

    return field_names


def extract_all_state_variables(sol_content):
    """
    Extract all state variables from .sol file (contract-level only)
    Returns: list of variable names and their type info
    """
    variables = []

    # Remove comments
    sol_content_clean = re.sub(r'//.*', '', sol_content)
    sol_content_clean = re.sub(r'/\*.*?\*/', '', sol_content_clean, flags=re.DOTALL)

    # Get struct names and field names
    struct_names = extract_struct_names(sol_content_clean)
    struct_fields = extract_struct_field_names(sol_content_clean)

    # Extract contract body (between contract Name { ... })
    contract_match = re.search(r'contract\s+\w+\s*\{(.*)\}', sol_content_clean, re.DOTALL)
    if not contract_match:
        return variables

    contract_body = contract_match.group(1)

    # Remove all struct blocks
    contract_body = re.sub(r'struct\s+\w+\s*\{[^}]+\}', '', contract_body, flags=re.DOTALL)

    # Remove all function blocks (more aggressive removal)
    contract_body = re.sub(r'function\s+\w+[^{]*\{(?:[^{}]|\{[^}]*\})*\}', '', contract_body, flags=re.DOTALL)

    # Remove all modifier blocks
    contract_body = re.sub(r'modifier\s+\w+[^{]*\{(?:[^{}]|\{[^}]*\})*\}', '', contract_body, flags=re.DOTALL)

    # Now extract mappings and variables from the cleaned contract body

    # Pattern for nested mapping
    nested_mapping_pattern = r'mapping\s*\(\s*(\w+)\s*=>\s*mapping\s*\(\s*(\w+)\s*=>\s*(\w+)\s*\)\s*\)\s*(?:public\s+|private\s+|internal\s+)?(\w+)\s*;'
    for match in re.finditer(nested_mapping_pattern, contract_body):
        variables.append({
            'type': 'nested_mapping',
            'key1_type': match.group(1),
            'key2_type': match.group(2),
            'value_type': match.group(3),
            'var_name': match.group(4)
        })

    # Pattern for simple mapping (including struct types)
    simple_mapping_pattern = r'mapping\s*\(\s*(\w+)\s*=>\s*(\w+)\s*\)\s*(?:public\s+|private\s+|internal\s+)?(\w+)\s*;'
    for match in re.finditer(simple_mapping_pattern, contract_body):
        var_name = match.group(3)
        value_type = match.group(2)
        # Skip if already added (nested mapping)
        if not any(v['var_name'] == var_name for v in variables):
            variables.append({
                'type': 'mapping',
                'key_type': match.group(1),
                'value_type': value_type,
                'var_name': var_name,
                'is_struct': value_type in struct_names
            })

    # Pattern for dynamic arrays (e.g., address[] public reinvestPath;)
    array_pattern = r'^\s*(\w+)\[\]\s+(?:public\s+|private\s+|internal\s+)?(\w+)\s*(?:=\s*[^;]+)?;'
    for match in re.finditer(array_pattern, contract_body, re.MULTILINE):
        element_type = match.group(1)
        var_name = match.group(2)
        # Skip if already added
        if not any(v['var_name'] == var_name for v in variables):
            variables.append({
                'type': 'array',
                'element_type': element_type,
                'var_name': var_name
            })

    # Pattern for simple type (but skip arrays as they're handled separately)
    # Only match lines that look like state variable declarations
    simple_type_pattern = r'^\s*(\w+)\s+(?:public\s+|private\s+|internal\s+)?(\w+)\s*(?:=\s*[^;]+)?;'
    for match in re.finditer(simple_type_pattern, contract_body, re.MULTILINE):
        var_type = match.group(1)
        var_name = match.group(2)
        # Skip mapping, struct, contract keywords, Solidity keywords, struct fields, and already added variables
        reserved_keywords = ['mapping', 'struct', 'contract', 'function', 'modifier', 'event',
                            'return', 'memory', 'storage', 'calldata', 'if', 'else', 'for',
                            'while', 'do', 'break', 'continue', 'throw', 'emit', 'require',
                            'assert', 'revert', 'true', 'false', 'constant', 'immutable']
        if var_type not in reserved_keywords and var_name not in reserved_keywords and \
           var_name not in struct_fields and \
           not any(v['var_name'] == var_name for v in variables):
            variables.append({
                'type': 'simple',
                'value_type': var_type,
                'var_name': var_name
            })

    return variables


def parse_variable_from_sol(sol_content, var_name):
    """
    Parse variable type from Solidity code
    Returns: type information (simple, mapping, nested_mapping)
    """
    # Try to find variable declaration
    # Patterns:
    # - uint256 public varname;
    # - mapping(address => uint256) public varname;
    # - mapping(address => mapping(address => uint256)) public varname;

    # Escape special regex characters in var_name
    escaped_var_name = re.escape(var_name)

    # Pattern for nested mapping
    nested_mapping_pattern = rf'mapping\s*\(\s*(\w+)\s*=>\s*mapping\s*\(\s*(\w+)\s*=>\s*(\w+)\s*\)\s*\)\s*(?:public\s+|private\s+|internal\s+)?{escaped_var_name}'
    match = re.search(nested_mapping_pattern, sol_content)
    if match:
        return {
            'type': 'nested_mapping',
            'key1_type': match.group(1),
            'key2_type': match.group(2),
            'value_type': match.group(3),
            'var_name': var_name
        }

    # Pattern for simple mapping (including struct types)
    simple_mapping_pattern = rf'mapping\s*\(\s*(\w+)\s*=>\s*(\w+)\s*\)\s*(?:public\s+|private\s+|internal\s+)?{escaped_var_name}'
    match = re.search(simple_mapping_pattern, sol_content)
    if match:
        return {
            'type': 'mapping',
            'key_type': match.group(1),
            'value_type': match.group(2),
            'var_name': var_name
        }

    # Pattern for simple type
    simple_type_pattern = rf'(\w+)\s+(?:public\s+|private\s+|internal\s+)?{escaped_var_name}'
    match = re.search(simple_type_pattern, sol_content)
    if match:
        return {
            'type': 'simple',
            'value_type': match.group(1),
            'var_name': var_name
        }

    # Not found - try to infer from input.json value type
    return None


def infer_type_from_value(var_name, value):
    """
    Infer variable type from input.json value structure
    """
    if isinstance(value, dict):
        # Check if nested mapping
        first_value = next(iter(value.values()))
        if isinstance(first_value, dict):
            # Nested mapping
            return {
                'type': 'nested_mapping',
                'key1_type': 'address',
                'key2_type': 'address',
                'value_type': 'uint256',
                'var_name': var_name
            }
        else:
            # Simple mapping
            return {
                'type': 'mapping',
                'key_type': 'address',
                'value_type': 'uint256',
                'var_name': var_name
            }
    else:
        # Simple type
        if isinstance(value, bool):
            value_type = 'bool'
        elif isinstance(value, int):
            value_type = 'uint256'
        elif isinstance(value, str) and value.startswith('0x'):
            value_type = 'address'
        else:
            value_type = 'uint256'

        return {
            'type': 'simple',
            'value_type': value_type,
            'var_name': var_name
        }


def generate_setter_function(var_info):
    """
    Generate setter function code based on variable type
    """
    var_name = var_info['var_name']

    if var_info['type'] == 'nested_mapping':
        key1_type = var_info['key1_type']
        key2_type = var_info['key2_type']
        value_type = var_info['value_type']

        return f"""
    // Auto-generated setter for {var_name} (nested mapping)
    function set_{var_name}({key1_type} _key1, {key2_type} _key2, {value_type} _value) public {{
        {var_name}[_key1][_key2] = _value;
    }}"""

    elif var_info['type'] == 'mapping':
        key_type = var_info['key_type']
        value_type = var_info['value_type']
        is_struct = var_info.get('is_struct', False)

        # Add memory keyword for struct types
        value_param = f"{value_type} memory _value" if is_struct else f"{value_type} _value"

        return f"""
    // Auto-generated setter for {var_name} (mapping)
    function set_{var_name}({key_type} _key, {value_param}) public {{
        {var_name}[_key] = _value;
    }}"""

    elif var_info['type'] == 'array':
        element_type = var_info['element_type']

        return f"""
    // Auto-generated setter for {var_name} (array)
    function set_{var_name}(uint256 _index, {element_type} _value) public {{
        // Expand array if necessary
        while ({var_name}.length <= _index) {{
            {var_name}.push();
        }}
        {var_name}[_index] = _value;
    }}"""

    else:  # simple
        value_type = var_info['value_type']

        return f"""
    // Auto-generated setter for {var_name}
    function set_{var_name}({value_type} _value) public {{
        {var_name} = _value;
    }}"""


def check_setter_exists(sol_content, var_name):
    """Check if setter function already exists"""
    pattern = rf'function\s+set_{re.escape(var_name)}\s*\('
    return re.search(pattern, sol_content) is not None


def add_setters_to_contract(sol_path, input_path):
    """
    Add missing setter functions to a contract
    """
    print(f"\n{'='*70}")
    print(f"Processing: {sol_path.name}")
    print(f"{'='*70}")

    # Read .sol file
    try:
        with open(sol_path, 'r', encoding='utf-8') as f:
            sol_content = f.read()
    except Exception as e:
        print(f"  [ERROR] Could not read .sol file: {e}")
        return False

    # Extract all state variables from .sol file
    all_variables = extract_all_state_variables(sol_content)

    if not all_variables:
        print(f"  [SKIP] No state variables found in .sol file")
        return False

    print(f"  Found {len(all_variables)} state variable(s) in .sol file")

    # Generate setters for each variable
    setters_to_add = []

    for var_info in all_variables:
        var_name = var_info['var_name']

        # Check if setter already exists
        if check_setter_exists(sol_content, var_name):
            print(f"  [SKIP] Setter already exists for: {var_name}")
            continue

        # Generate setter
        setter_code = generate_setter_function(var_info)
        setters_to_add.append(setter_code)
        print(f"  [ADD] Setter for {var_name} ({var_info['type']}: {var_info.get('key_type', '')}{' => ' if var_info.get('key_type') else ''}{var_info.get('value_type', '')})")

    if not setters_to_add:
        print(f"  [OK] All setters already exist")
        return False

    # Find the last closing brace of the contract
    last_brace = sol_content.rfind('}')
    if last_brace == -1:
        print(f"  [ERROR] Could not find contract closing brace")
        return False

    # Insert setters before the closing brace
    new_content = sol_content[:last_brace] + '\n'.join(setters_to_add) + '\n' + sol_content[last_brace:]

    # Write back to file
    try:
        with open(sol_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print(f"  [OK] Added {len(setters_to_add)} setter(s)")
        return True
    except Exception as e:
        print(f"  [ERROR] Could not write to .sol file: {e}")
        return False


def main():
    remix_dir = Path(__file__).parent.parent / 'contraction_remix'

    print("="*70)
    print("ADDING MISSING SETTER FUNCTIONS")
    print("="*70)

    # Find all _input.json files
    input_files = sorted(remix_dir.glob('*_c_input.json'))
    print(f"\nFound {len(input_files)} input.json files")

    modified_count = 0

    for input_file in input_files:
        # Get corresponding .sol file
        sol_file = input_file.with_name(input_file.name.replace('_input.json', '.sol'))

        if not sol_file.exists():
            print(f"\n[ERROR] .sol file not found: {sol_file.name}")
            continue

        try:
            if add_setters_to_contract(sol_file, input_file):
                modified_count += 1
        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n" + "="*70)
    print(f"SUMMARY: Modified {modified_count} / {len(input_files)} contracts")
    print("="*70)


if __name__ == "__main__":
    main()
