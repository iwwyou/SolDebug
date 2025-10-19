"""
Validate all contracts before running benchmark:
1. Check if .sol files compile
2. Check if input.json exists
3. Validate setter functions match input.json
"""
import re
import json
from pathlib import Path
import subprocess
import sys


def parse_setters_from_sol(sol_path):
    """Extract setter function signatures from .sol file"""
    with open(sol_path, 'r', encoding='utf-8') as f:
        content = f.read()

    setters = {}

    # Match setter functions: function set_varname(...) public
    pattern = r'function\s+(set_\w+)\s*\(([^)]*)\)\s*public'

    for match in re.finditer(pattern, content):
        func_name = match.group(1)
        params = match.group(2).strip()

        # Parse parameters
        param_list = []
        if params:
            for param in params.split(','):
                param = param.strip()
                # Extract type (first word)
                parts = param.split()
                if len(parts) >= 2:
                    param_type = parts[0]
                    param_list.append(param_type)

        # Extract variable name from function name: set_varname -> varname
        var_name = func_name.replace('set_', '')
        setters[var_name] = {
            'function': func_name,
            'params': param_list,
            'param_count': len(param_list)
        }

    return setters


def validate_contract(sol_path, input_path):
    """Validate a single contract"""
    print(f"\n{'='*70}")
    print(f"Validating: {sol_path.name}")
    print(f"{'='*70}")

    issues = []

    # 1. Check if input.json exists
    if not input_path.exists():
        issues.append(f"[MISSING] input.json file not found")
        print(f"  [ERROR] input.json not found: {input_path.name}")
        return issues

    # 2. Parse setters from .sol
    try:
        setters = parse_setters_from_sol(sol_path)
        print(f"  [OK] Found {len(setters)} setter functions")
    except Exception as e:
        issues.append(f"[PARSE ERROR] Could not parse setters: {e}")
        print(f"  [ERROR] Failed to parse setters: {e}")
        return issues

    # 3. Load input.json
    try:
        with open(input_path, 'r', encoding='utf-8') as f:
            input_data = json.load(f)
        state_slots = input_data.get('state_slots', {})
        print(f"  [OK] Loaded input.json with {len(state_slots)} state slots")
    except Exception as e:
        issues.append(f"[JSON ERROR] Could not load input.json: {e}")
        print(f"  [ERROR] Failed to load input.json: {e}")
        return issues

    # 4. Validate each state slot has matching setter
    for var_name, value in state_slots.items():
        if var_name not in setters:
            issues.append(f"[MISMATCH] Variable '{var_name}' has no setter function")
            print(f"  [ERROR] No setter for: {var_name}")
            continue

        setter_info = setters[var_name]

        # Check parameter count
        if isinstance(value, dict):
            # Mapping type
            # Simple mapping: 2 params (key, value)
            # Nested mapping: 3 params (key1, key2, value)

            # Count nesting level
            sample_value = next(iter(value.values()))
            if isinstance(sample_value, dict):
                # Nested mapping
                expected_params = 3
            else:
                # Simple mapping
                expected_params = 2

            if setter_info['param_count'] != expected_params:
                issues.append(f"[MISMATCH] {var_name}: expected {expected_params} params, got {setter_info['param_count']}")
                print(f"  [ERROR] {var_name}: param count mismatch (expected {expected_params}, got {setter_info['param_count']})")
        else:
            # Simple type: 1 param
            if setter_info['param_count'] != 1:
                issues.append(f"[MISMATCH] {var_name}: expected 1 param, got {setter_info['param_count']}")
                print(f"  [ERROR] {var_name}: param count mismatch (expected 1, got {setter_info['param_count']})")

    # 5. Summary
    if not issues:
        print(f"  [OK] Validation passed!")
    else:
        print(f"  [FAILED] {len(issues)} issue(s) found")

    return issues


def check_compilation(sol_path):
    """Check if contract compiles (basic syntax check)"""
    try:
        # Simple check: look for basic Solidity syntax errors
        with open(sol_path, 'r', encoding='utf-8') as f:
            content = f.read()

        # Check for SPDX license
        if 'SPDX-License-Identifier' not in content:
            return False, "Missing SPDX license"

        # Check for pragma
        if 'pragma solidity' not in content:
            return False, "Missing pragma"

        # Check for contract definition
        if 'contract ' not in content:
            return False, "No contract definition found"

        # Check for balanced braces
        if content.count('{') != content.count('}'):
            return False, "Unbalanced braces"

        return True, "Basic syntax OK"
    except Exception as e:
        return False, f"Error: {e}"


def main():
    remix_dir = Path(__file__).parent

    print("="*70)
    print("CONTRACT VALIDATION SUITE")
    print("="*70)

    # Find all .sol files
    sol_files = sorted(remix_dir.glob('*_c.sol'))
    print(f"\nFound {len(sol_files)} contract files")

    results = {
        'total': len(sol_files),
        'passed': 0,
        'failed': 0,
        'missing_input': 0,
        'compilation_failed': 0,
        'issues': {}
    }

    for sol_file in sol_files:
        # Check compilation
        compile_ok, compile_msg = check_compilation(sol_file)
        if not compile_ok:
            print(f"\n[COMPILE FAIL] {sol_file.name}: {compile_msg}")
            results['compilation_failed'] += 1
            results['issues'][sol_file.name] = [f"Compilation: {compile_msg}"]
            continue

        # Check input.json
        input_file = sol_file.with_name(sol_file.name.replace('.sol', '_input.json'))

        if not input_file.exists():
            print(f"\n[NO INPUT] {sol_file.name}")
            results['missing_input'] += 1
            results['issues'][sol_file.name] = ["Missing input.json"]
            continue

        # Validate
        issues = validate_contract(sol_file, input_file)

        if issues:
            results['failed'] += 1
            results['issues'][sol_file.name] = issues
        else:
            results['passed'] += 1

    # Final summary
    print("\n" + "="*70)
    print("VALIDATION SUMMARY")
    print("="*70)
    print(f"Total contracts:        {results['total']}")
    print(f"Passed validation:      {results['passed']}")
    print(f"Failed validation:      {results['failed']}")
    print(f"Missing input.json:     {results['missing_input']}")
    print(f"Compilation failed:     {results['compilation_failed']}")

    if results['issues']:
        print("\n" + "="*70)
        print("ISSUES FOUND")
        print("="*70)
        for contract, issues in results['issues'].items():
            print(f"\n{contract}:")
            for issue in issues:
                print(f"  - {issue}")

    print("\n" + "="*70)

    # Exit code
    if results['failed'] > 0 or results['compilation_failed'] > 0:
        sys.exit(1)
    else:
        print("[OK] All contracts validated successfully!")
        sys.exit(0)


if __name__ == "__main__":
    main()
