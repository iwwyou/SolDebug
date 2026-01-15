"""
Prepare contracts for Remix benchmark by adding:
1. Public wrappers for private/internal functions
2. Setter functions for state variables
"""

import re
import os
from pathlib import Path


class ContractPreparer:
    def __init__(self):
        self.state_variables = []

    def extract_structs(self, contract_code):
        """Extract struct definitions"""
        structs = {}
        struct_pattern = r'struct\s+(\w+)\s*\{'
        matches = re.finditer(struct_pattern, contract_code)

        for match in matches:
            struct_name = match.group(1)
            structs[struct_name] = True

        return structs

    def parse_state_variables(self, contract_code):
        """Extract state variable declarations"""
        variables = []

        # First extract struct definitions
        self.structs = self.extract_structs(contract_code)

        # Match state variable declarations
        # Pattern: type visibility? name;
        # Examples: uint256 public x; mapping(address => uint256) private balances;

        lines = contract_code.split('\n')
        in_contract = False
        brace_count = 0

        for line in lines:
            stripped = line.strip()

            # Track contract scope
            if re.match(r'contract\s+\w+', stripped):
                in_contract = True

            if in_contract:
                brace_count += stripped.count('{') - stripped.count('}')

                # Check if it's a state variable (not inside a function)
                if brace_count == 1:  # At contract level, not inside function
                    # Skip function declarations
                    if 'function' in stripped:
                        continue

                    # Match state variables
                    # Simple types: uint256 varName;
                    simple_match = re.match(r'(uint\d*|int\d*|address|bool|string|bytes\d*)\s+(public|private|internal|constant)?\s*(\w+)\s*(?:=.*)?;', stripped)
                    if simple_match:
                        var_type = simple_match.group(1)
                        var_name = simple_match.group(3)
                        variables.append({
                            'name': var_name,
                            'type': var_type,
                            'is_mapping': False,
                            'is_constant': 'constant' in stripped
                        })
                        continue

                    # Mapping types: mapping(type => type) varName;
                    mapping_match = re.match(r'mapping\s*\((.*?)\)\s+(public|private|internal)?\s*(\w+)\s*;', stripped)
                    if mapping_match:
                        var_name = mapping_match.group(3)
                        mapping_signature = mapping_match.group(1)
                        variables.append({
                            'name': var_name,
                            'type': 'mapping',
                            'mapping_signature': mapping_signature,
                            'is_mapping': True,
                            'is_constant': False
                        })
                        continue

        return variables

    def generate_setters(self, variables):
        """Generate setter functions for state variables"""
        setters = []

        for var in variables:
            if var['is_constant']:
                continue

            if not var['is_mapping']:
                # Simple setter
                setter = f"""
    // Auto-generated setter for {var['name']}
    function set_{var['name']}({var['type']} _value) public {{
        {var['name']} = _value;
    }}"""
                setters.append(setter)
            else:
                # Mapping setter - need to parse the mapping signature
                sig = var['mapping_signature']

                # Handle simple mapping: address => uint256
                simple_mapping = re.match(r'(\w+)\s*=>\s*(.+)', sig)
                if simple_mapping:
                    key_type = simple_mapping.group(1).strip()
                    value_type = simple_mapping.group(2).strip()

                    # Handle nested mapping
                    if 'mapping' in value_type:
                        # Nested mapping: mapping(address => mapping(address => uint256))
                        nested_match = re.match(r'mapping\s*\((.*?)\s*=>\s*(.+?)\)', value_type)
                        if nested_match:
                            key2_type = nested_match.group(1).strip()
                            value2_type = nested_match.group(2).strip()

                            setter = f"""
    // Auto-generated setter for {var['name']} (nested mapping)
    function set_{var['name']}({key_type} _key1, {key2_type} _key2, {value2_type} _value) public {{
        {var['name']}[_key1][_key2] = _value;
    }}"""
                            setters.append(setter)
                    else:
                        # Simple mapping
                        # Check if value_type is a struct (needs memory keyword)
                        memory_keyword = ""
                        if value_type in self.structs:
                            memory_keyword = " memory"

                        setter = f"""
    // Auto-generated setter for {var['name']}
    function set_{var['name']}({key_type} _key, {value_type}{memory_keyword} _value) public {{
        {var['name']}[_key] = _value;
    }}"""
                        setters.append(setter)

        return setters

    def make_functions_public(self, contract_code):
        """Convert private/internal functions to public"""
        # Simply replace the visibility modifiers, preserving everything else
        code = contract_code

        # Replace private with public
        code = re.sub(r'\bprivate\b', 'public', code)

        # Replace internal with public
        code = re.sub(r'\binternal\b', 'public', code)

        # Remove override keyword
        code = re.sub(r'\boverride\b\s*', '', code)

        # Fix uint(-1) to type(uint256).max for Solidity 0.8.0+
        code = re.sub(r'\buint\s*\(\s*-1\s*\)', 'type(uint256).max', code)
        code = re.sub(r'\buint256\s*\(\s*-1\s*\)', 'type(uint256).max', code)

        return code

    def prepare_contract(self, contract_path):
        """Prepare a single contract file"""
        with open(contract_path, 'r', encoding='utf-8') as f:
            original_code = f.read()

        # Parse state variables
        variables = self.parse_state_variables(original_code)

        # Generate setters
        setters = self.generate_setters(variables)

        # Make functions public
        modified_code = self.make_functions_public(original_code)

        # Insert setters before the last closing brace
        if setters:
            # Find the last closing brace
            last_brace_pos = modified_code.rfind('}')
            if last_brace_pos != -1:
                setters_code = '\n'.join(setters)
                modified_code = (
                    modified_code[:last_brace_pos] +
                    '\n' + setters_code + '\n' +
                    modified_code[last_brace_pos:]
                )

        # Add SPDX license identifier and pragma at the beginning
        header = """// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

"""
        modified_code = header + modified_code

        return modified_code


def prepare_all_contracts(source_dir, target_dir):
    """Prepare all contracts in source directory"""
    source_path = Path(source_dir)
    target_path = Path(target_dir)

    # Create target directory
    target_path.mkdir(parents=True, exist_ok=True)

    preparer = ContractPreparer()

    # Process all .sol files
    sol_files = list(source_path.glob('*.sol'))
    print(f"Found {len(sol_files)} Solidity files to process")

    for sol_file in sol_files:
        print(f"\nProcessing: {sol_file.name}")

        try:
            modified_code = preparer.prepare_contract(sol_file)

            # Save to target directory
            target_file = target_path / sol_file.name
            with open(target_file, 'w', encoding='utf-8') as f:
                f.write(modified_code)

            print(f"  [OK] Saved to: {target_file}")
        except Exception as e:
            print(f"  [ERROR] Failed to process {sol_file.name}: {e}")


if __name__ == "__main__":
    import sys

    # Default paths
    source_dir = "../../dataset/contraction"
    target_dir = "../../dataset/contraction_remix"

    if len(sys.argv) > 1:
        source_dir = sys.argv[1]
    if len(sys.argv) > 2:
        target_dir = sys.argv[2]

    print("="*60)
    print("Contract Preparation for Remix Benchmark")
    print("="*60)
    print(f"Source: {source_dir}")
    print(f"Target: {target_dir}")
    print("="*60)

    prepare_all_contracts(source_dir, target_dir)

    print("\n" + "="*60)
    print("[OK] All contracts prepared successfully!")
    print("="*60)
