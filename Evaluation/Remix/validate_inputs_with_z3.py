"""
Input Validation Script using Z3
Validates that input files satisfy contract require conditions
"""

import json
import os
import re
from pathlib import Path
from z3 import *

def load_contract_code(sol_file):
    """Load Solidity contract code"""
    contract_path = os.path.join('..', '..', 'dataset', 'contraction_remix', sol_file)
    if not os.path.exists(contract_path):
        return None
    with open(contract_path, 'r', encoding='utf-8') as f:
        return f.read()

def load_input_file(input_file):
    """Load input JSON file"""
    input_path = os.path.join('..', '..', 'dataset', 'contraction_remix', input_file)
    if not os.path.exists(input_path):
        return None
    with open(input_path, 'r', encoding='utf-8') as f:
        return json.load(f)

def extract_function_and_require(contract_code, function_name):
    """Extract function definition and require conditions"""
    # Find function definition
    pattern = rf'function\s+{re.escape(function_name)}\s*\([^)]*\)[^{{]*\{{[^}}]*require\s*\([^;]+\);'
    match = re.search(pattern, contract_code, re.DOTALL)

    if not match:
        return None, None

    function_def = match.group(0)

    # Extract require condition
    require_pattern = r'require\s*\(([^;]+)\);'
    require_match = re.search(require_pattern, function_def)

    if not require_match:
        return function_def, None

    require_condition = require_match.group(1).strip()
    return function_def, require_condition

def parse_function_params(function_def):
    """Parse function parameters"""
    param_pattern = r'function\s+\w+\s*\(([^)]*)\)'
    match = re.search(param_pattern, function_def)
    if not match:
        return []

    params_str = match.group(1)
    params = []
    for param in params_str.split(','):
        param = param.strip()
        if param:
            parts = param.split()
            if len(parts) >= 2:
                param_type = parts[0]
                param_name = parts[1]
                params.append({'type': param_type, 'name': param_name})

    return params

def validate_with_z3_simple(require_condition, state_slots, inputs, params):
    """
    Simple validation: check if numeric comparisons can be satisfied

    This is a simplified version that handles common patterns like:
    - balances[_from] >= _amount
    - allowed[_from][msg.sender] >= _amount
    - _amount > 0
    """

    issues = []

    # Create a mapping of parameter names to input values
    param_values = {}
    for i, param in enumerate(params):
        if i < len(inputs):
            param_values[param['name']] = inputs[i]

    # Check common patterns

    # Pattern 1: allowed[_from][msg.sender] >= _amount
    if 'allowed[_from][msg.sender]>=_amount' in require_condition.replace(' ', ''):
        _from = param_values.get('_from')
        _amount = param_values.get('_amount')

        if _from and _amount:
            # Check if allowed[_from][msg.sender] is set
            allowed_map = state_slots.get('allowed', {})
            if _from in allowed_map:
                # msg.sender is unknown, but we can check if ANY value is >= _amount
                max_allowed = max(allowed_map[_from].values()) if allowed_map[_from] else 0
                if max_allowed < _amount:
                    issues.append({
                        'condition': f'allowed[_from][msg.sender] >= _amount',
                        'problem': f'Max allowed value ({max_allowed}) < _amount ({_amount})',
                        'suggestion': f'Set allowed[{_from}][msg.sender] >= {_amount}'
                    })
            else:
                issues.append({
                    'condition': f'allowed[_from][msg.sender] >= _amount',
                    'problem': f'No allowed mapping for _from={_from}',
                    'suggestion': f'Add allowed[{_from}][msg.sender] in state_slots'
                })

    # Pattern 2: balances[_from] >= _amount
    if 'balances[_from]>=_amount' in require_condition.replace(' ', ''):
        _from = param_values.get('_from')
        _amount = param_values.get('_amount')

        if _from and _amount:
            balances_map = state_slots.get('balances', {})
            balance = balances_map.get(_from, 0)
            if balance < _amount:
                issues.append({
                    'condition': f'balances[_from] >= _amount',
                    'problem': f'balance ({balance}) < _amount ({_amount})',
                    'suggestion': f'Set balances[{_from}] >= {_amount}'
                })

    # Pattern 3: _amount > 0
    if '_amount>0' in require_condition.replace(' ', ''):
        _amount = param_values.get('_amount')
        if _amount is not None and _amount <= 0:
            issues.append({
                'condition': '_amount > 0',
                'problem': f'_amount = {_amount} is not > 0',
                'suggestion': 'Set _amount to a positive value'
            })

    # Pattern 4: overflow check balances[_to] + _amount > balances[_to]
    if 'balances[_to]+_amount>balances[_to]' in require_condition.replace(' ', ''):
        _amount = param_values.get('_amount')
        if _amount is not None and _amount <= 0:
            issues.append({
                'condition': 'balances[_to] + _amount > balances[_to]',
                'problem': f'_amount = {_amount} would fail overflow check',
                'suggestion': 'Set _amount to a positive value'
            })

    return issues

def validate_all_inputs():
    """Validate all input files"""
    # Load dataset to get function names
    import pandas as pd
    dataset_path = os.path.join('..', '..', 'dataset', 'evaluation_Dataset.xlsx')
    df = pd.read_excel(dataset_path, header=0)
    df.columns = ['Index', 'Size_KB', 'Sol_File_Name', 'Contract_Name', 'Function_Name',
                  'Original_Function_Line', 'Annotation_Targets', 'State_Slots', 'ByteOp',
                  'Target_Variables']

    # Remove Korean header if present
    if len(df) > 0 and df.iloc[0]['Size_KB'] == '용량':
        df = df.iloc[1:].reset_index(drop=True)

    all_issues = []

    for idx, row in df.iterrows():
        contract_name = row['Contract_Name']
        sol_file = row['Sol_File_Name']
        function_name = row['Function_Name']

        # Skip if function_name is NaN or not a string
        if pd.isna(function_name) or not isinstance(function_name, str):
            print(f"\n[{idx+1}/{len(df)}] Skipping {contract_name}: function_name is invalid")
            continue

        # Generate file names
        contract_filename = sol_file.replace('.sol', '_c.sol')
        input_filename = sol_file.replace('.sol', '_c_input.json')

        print(f"\n{'='*60}")
        print(f"[{idx+1}/{len(df)}] Validating: {contract_name}.{function_name}")
        print(f"{'='*60}")

        # Load contract code
        contract_code = load_contract_code(contract_filename)
        if not contract_code:
            print(f"  [SKIP] Contract file not found: {contract_filename}")
            continue

        # Load input file
        input_data = load_input_file(input_filename)
        if not input_data:
            print(f"  [SKIP] Input file not found: {input_filename}")
            continue

        # Extract function and require condition
        function_def, require_condition = extract_function_and_require(contract_code, function_name)
        if not require_condition:
            print(f"  [SKIP] No require condition found in function")
            continue

        print(f"  Function: {function_name}")
        print(f"  Require: {require_condition[:100]}...")

        # Parse function parameters
        params = parse_function_params(function_def)
        print(f"  Parameters: {[p['name'] for p in params]}")

        # Get state and inputs
        state_slots = input_data.get('state_slots', {})
        inputs = input_data.get('inputs', [])

        print(f"  Inputs: {inputs}")

        # Validate with z3 (simplified)
        issues = validate_with_z3_simple(require_condition, state_slots, inputs, params)

        if issues:
            print(f"  [WARNING] Found {len(issues)} potential issue(s):")
            for issue in issues:
                print(f"    - Condition: {issue['condition']}")
                print(f"      Problem: {issue['problem']}")
                print(f"      Suggestion: {issue['suggestion']}")

            all_issues.append({
                'contract': contract_name,
                'function': function_name,
                'file': input_filename,
                'issues': issues
            })
        else:
            print(f"  [OK] No obvious issues detected")

    # Summary
    print(f"\n{'='*60}")
    print(f"VALIDATION SUMMARY")
    print(f"{'='*60}")
    print(f"Total contracts checked: {len(df)}")
    print(f"Contracts with potential issues: {len(all_issues)}")

    if all_issues:
        print(f"\nContracts requiring attention:")
        for item in all_issues:
            print(f"  - {item['contract']}.{item['function']}")
            print(f"    File: {item['file']}")
            print(f"    Issues: {len(item['issues'])}")

    return all_issues

if __name__ == "__main__":
    try:
        import z3
        print("Z3 is installed!")
        print(f"Z3 version: {z3.get_version_string()}")
    except ImportError:
        print("Z3 is not installed. Install with: pip install z3-solver")
        print("Running validation with simplified checks...")

    issues = validate_all_inputs()

    # Save issues to file
    if issues:
        output_file = 'input_validation_issues.json'
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(issues, f, indent=2)
        print(f"\nIssues saved to: {output_file}")
