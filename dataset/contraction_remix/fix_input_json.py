"""
Fix all input.json files to use dict format for mapping types
This script converts entries like "_balances[account]": 1000 to "_balances": {"0xAddress": 1000}
"""
import json
import re
from pathlib import Path


def parse_mapping_key(key_str):
    """
    Parse mapping key string like "balances[addr]" or "allowance[addr1][addr2]"
    Returns: (var_name, keys)
    Example: "balances[src]" -> ("balances", ["src"])
    Example: "allowance[src][dst]" -> ("allowance", ["src", "dst"])
    """
    # Match pattern: varname[key1][key2]...
    match = re.match(r'(\w+)(\[.+\])+', key_str)
    if not match:
        return None, []

    var_name = match.group(1)
    # Extract all [key] parts
    keys = re.findall(r'\[([^\]]+)\]', key_str)
    return var_name, keys


def resolve_variable_to_address(var_name, inputs):
    """
    Map variable names to actual addresses from inputs
    Common patterns:
    - account, src, _from -> inputs[0]
    - dst, _to -> inputs[1]
    - msg.sender, spender -> inputs[1] or inputs[0]
    """
    var_lower = var_name.lower()

    # First address (usually sender/from/account)
    if var_lower in ['account', 'src', '_from', 'from', 'sender', 'owner']:
        return inputs[0] if len(inputs) > 0 else None

    # Second address (usually receiver/to/spender)
    if var_lower in ['dst', '_to', 'to', 'recipient', 'spender']:
        return inputs[1] if len(inputs) > 1 else None

    # msg.sender usually maps to second address in transferFrom pattern
    if var_lower == 'msg.sender':
        return inputs[1] if len(inputs) > 1 else inputs[0] if len(inputs) > 0 else None

    # Default: try to use as is if it looks like an address
    if var_name.startswith('0x'):
        return var_name

    # Otherwise, return the first input address as fallback
    return inputs[0] if len(inputs) > 0 else None


def convert_state_slots(state_slots, inputs):
    """
    Convert state_slots from old format to new dict format
    Old: {"_balances[account]": 1000}
    New: {"_balances": {"0xAddress": 1000}}
    """
    new_state_slots = {}

    for key, value in state_slots.items():
        var_name, keys = parse_mapping_key(key)

        if not keys:
            # Simple variable (no brackets)
            new_state_slots[key] = value
        elif len(keys) == 1:
            # Simple mapping: varname[key]
            if var_name not in new_state_slots:
                new_state_slots[var_name] = {}

            # Resolve variable name to address
            resolved_key = resolve_variable_to_address(keys[0], inputs)
            if resolved_key:
                new_state_slots[var_name][resolved_key] = value
        elif len(keys) == 2:
            # Nested mapping: varname[key1][key2]
            if var_name not in new_state_slots:
                new_state_slots[var_name] = {}

            # Resolve both keys to addresses
            resolved_key1 = resolve_variable_to_address(keys[0], inputs)
            resolved_key2 = resolve_variable_to_address(keys[1], inputs)

            if resolved_key1 and resolved_key2:
                if resolved_key1 not in new_state_slots[var_name]:
                    new_state_slots[var_name][resolved_key1] = {}
                new_state_slots[var_name][resolved_key1][resolved_key2] = value

    return new_state_slots


def fix_input_json(json_path):
    """Fix a single input.json file"""
    print(f"\nProcessing: {json_path.name}")

    with open(json_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    state_slots = data.get('state_slots', {})
    inputs = data.get('inputs', [])

    # Check if any mapping exists
    has_mapping = any('[' in key for key in state_slots.keys())

    if not has_mapping:
        print(f"  → No mappings found, skipping")
        return False

    print(f"  → Found mapping(s): {[k for k in state_slots.keys() if '[' in k]}")

    # Convert state slots
    new_state_slots = convert_state_slots(state_slots, inputs)

    # Update data
    data['state_slots'] = new_state_slots

    # Write back to file
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  [OK] Fixed successfully")
    print(f"  -> New state_slots: {json.dumps(new_state_slots, indent=4)}")
    return True


def main():
    remix_dir = Path(__file__).parent

    print("="*70)
    print("FIXING INPUT.JSON FILES - MAPPING FORMAT")
    print("="*70)

    json_files = list(remix_dir.glob('*_input.json'))
    print(f"\nFound {len(json_files)} input.json files")

    fixed_count = 0
    for json_file in sorted(json_files):
        try:
            if fix_input_json(json_file):
                fixed_count += 1
        except Exception as e:
            print(f"  [ERROR] {e}")

    print("\n" + "="*70)
    print(f"SUMMARY: Fixed {fixed_count} / {len(json_files)} files")
    print("="*70)


if __name__ == "__main__":
    main()
