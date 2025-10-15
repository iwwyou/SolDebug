"""
Generate input JSON files for Remix benchmark from annotation files
"""
import json
import re
from pathlib import Path

# Remix test accounts (default accounts in Remix VM)
REMIX_ACCOUNTS = [
    "0x5B38Da6a701c568545dCfcB03FcB875f56beddC4",
    "0xAb8483F64d9C6d1EcF9b849Ae677dD3315835cb2",
    "0x4B20993Bc481177ec7E8f571ceCaE8A9e22C02db",
    "0x78731D3Ca6b7E34aC0F824c42a7cC18A495cabaB",
    "0x617F2E2fD72FD9D5503197092aC168c91465E7f2",
    "0x17F6AD8Ef982297579C203069C1DbfFE4348c372",
]

def parse_annotation_file(annot_file):
    """Extract StateVar and LocalVar from annotation file"""
    with open(annot_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    state_vars = {}
    local_vars = {}
    global_vars = {}

    for entry in data:
        code = entry.get('code', '')

        # StateVar pattern
        match = re.search(r'// @StateVar\s+(\S+)\s*=\s*(.+?);', code)
        if match:
            var_name = match.group(1)
            var_value = match.group(2).strip()
            state_vars[var_name] = var_value

        # LocalVar pattern
        match = re.search(r'// @LocalVar\s+(\S+)\s*=\s*(.+?);', code)
        if match:
            var_name = match.group(1)
            var_value = match.group(2).strip()
            local_vars[var_name] = var_value

        # GlobalVar pattern (we'll skip these for now)
        match = re.search(r'// @GlobalVar\s+(\S+)\s*=\s*(.+?);', code)
        if match:
            var_name = match.group(1)
            var_value = match.group(2).strip()
            global_vars[var_name] = var_value

    return state_vars, local_vars, global_vars

def parse_value(value_str):
    """Convert annotation value to Remix-compatible value"""
    value_str = value_str.strip()

    # Pattern 1: Interval [min, max] → use first value
    match = re.match(r'\[(\d+),\s*\d+\]', value_str)
    if match:
        return int(match.group(1))

    # Pattern 2: any → true (for bool)
    if value_str.lower() == 'any':
        return True

    # Pattern 3: symbolicAddress N → Remix Account[N]
    match = re.search(r'symbolicaddress\s+(\d+)', value_str, re.IGNORECASE)
    if match:
        account_num = int(match.group(1))
        if account_num < len(REMIX_ACCOUNTS):
            return REMIX_ACCOUNTS[account_num]
        else:
            return REMIX_ACCOUNTS[1]  # Default to Account 1

    # Pattern 4: array [1,2,3] → list
    match = re.match(r'array\s*\[(.+)\]', value_str, re.IGNORECASE)
    if match:
        values_str = match.group(1)
        values = [int(v.strip()) for v in values_str.split(',')]
        return values

    # Pattern 5: arrayAddress[1,2,3] → list of addresses
    match = re.match(r'arrayaddress\s*\[(.+)\]', value_str, re.IGNORECASE)
    if match:
        indices_str = match.group(1)
        indices = [int(v.strip()) for v in indices_str.split(',')]
        return [REMIX_ACCOUNTS[i] if i < len(REMIX_ACCOUNTS) else REMIX_ACCOUNTS[1] for i in indices]

    # Pattern 6: symbolicBytes → skip (complex type)
    if 'symbolicbytes' in value_str.lower():
        return None  # Skip complex types

    # Pattern 7: Single value
    match = re.match(r'^\d+$', value_str)
    if match:
        return int(value_str)

    # Unknown pattern
    return None

def generate_input_file(annot_file, output_dir):
    """Generate input JSON for a contract"""
    contract_name = annot_file.stem.replace('_annot', '')

    print(f"\n{'='*70}")
    print(f"Processing: {contract_name}")
    print(f"{'='*70}")

    try:
        state_vars, local_vars, global_vars = parse_annotation_file(annot_file)

        if not state_vars and not local_vars:
            print("  No annotations found - skipping")
            return False

        # Parse state variables
        state_slots = {}
        state_arrays = {}

        for var_name, var_value in state_vars.items():
            parsed_value = parse_value(var_value)

            if parsed_value is None:
                print(f"  [SKIP] StateVar {var_name} = {var_value} (complex/unsupported)")
                continue

            # Check if it's an array
            if isinstance(parsed_value, list):
                state_arrays[var_name] = parsed_value
                print(f"  [ARRAY] StateVar {var_name} = {parsed_value}")
            else:
                state_slots[var_name] = parsed_value
                print(f"  [STATE] StateVar {var_name} = {parsed_value}")

        # Parse local variables (function inputs)
        inputs = []
        for var_name, var_value in local_vars.items():
            parsed_value = parse_value(var_value)

            if parsed_value is None:
                print(f"  [SKIP] LocalVar {var_name} = {var_value} (complex/unsupported)")
                continue

            inputs.append(parsed_value)
            print(f"  [INPUT] LocalVar {var_name} = {parsed_value}")

        # Create output JSON
        output_data = {
            "contract_name": contract_name,
            "state_slots": state_slots,
            "state_arrays": state_arrays,
            "inputs": inputs
        }

        # Save to file
        output_file = output_dir / f"{contract_name}_input.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, indent=2)

        print(f"\n  [OK] Generated: {output_file.name}")
        print(f"    - State slots: {len(state_slots)}")
        print(f"    - State arrays: {len(state_arrays)}")
        print(f"    - Inputs: {len(inputs)}")

        return True

    except Exception as e:
        print(f"  [ERROR] Failed to process: {e}")
        import traceback
        traceback.print_exc()
        return False

def main():
    annot_dir = Path('json/annotation')
    output_dir = Path('contraction_remix')

    if not annot_dir.exists():
        print(f"ERROR: {annot_dir} does not exist")
        return

    print("="*70)
    print("GENERATING REMIX INPUT FILES FROM ANNOTATIONS")
    print("="*70)

    annot_files = sorted(annot_dir.glob('*_annot.json'))
    print(f"\nFound {len(annot_files)} annotation files")

    success_count = 0

    for annot_file in annot_files:
        if generate_input_file(annot_file, output_dir):
            success_count += 1

    print("\n" + "="*70)
    print(f"SUMMARY: Generated {success_count} / {len(annot_files)} input files")
    print(f"Output directory: {output_dir}")
    print("="*70)

if __name__ == "__main__":
    main()
