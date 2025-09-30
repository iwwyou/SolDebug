#!/usr/bin/env python3
"""
Generate annotation JSON files from original JSON files and Excel evaluation data.
"""

import json
import pandas as pd
import re
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional

def parse_target_variables(target_var_text: str) -> List[Tuple[str, str, str]]:
    """
    Parse target variable text from Excel and return list of (type, name, values).

    Args:
        target_var_text: Text like "SV : maintenanceBudget0, maintenanceBudget1 \nLV : earned0, earned1"

    Returns:
        List of tuples: (type, variable_name, default_values)
        where type is 'StateVar' or 'LocalVar'
    """
    if pd.isna(target_var_text) or not target_var_text.strip():
        return []

    variables = []

    # Split by lines and process each
    lines = str(target_var_text).split('\n')

    for line in lines:
        line = line.strip()
        if not line:
            continue

        # Parse SV (State Variable) or LV (Local Variable)
        if line.startswith('SV :') or line.startswith('LV :'):
            var_type = 'StateVar' if line.startswith('SV :') else 'LocalVar'

            # Extract variable names after the colon
            var_part = line.split(':', 1)[1].strip()

            # Split by comma and clean up variable names
            var_names = [name.strip() for name in var_part.split(',') if name.strip()]

            for var_name in var_names:
                # Keep the variable name as is (including mapping keys like [account])
                var_name = var_name.strip()
                if var_name:
                    # Generate default values based on variable type
                    default_values = generate_default_values(var_name, var_type)
                    variables.append((var_type, var_name, default_values))

    return variables

def generate_default_values(var_name: str, var_type: str) -> str:
    """
    Generate default annotation values based on variable name and type.
    """
    # Simple heuristic for generating values
    if 'budget' in var_name.lower():
        return '[100,100]'
    elif 'earned' in var_name.lower():
        return '[50,50]'
    elif 'amount' in var_name.lower():
        return '[10,10]'
    elif 'balance' in var_name.lower():
        return '[1000,1000]'
    elif 'total' in var_name.lower():
        return '[500,500]'
    else:
        return '[1,1]'  # Default values

def find_target_function_start_line(json_data: List[Dict], function_name: str) -> Optional[int]:
    """
    Find the start line of the target function's first code statement.

    Args:
        json_data: JSON data from original file
        function_name: Name of the function to find

    Returns:
        Start line number of the first code statement in the function, or None if not found
    """
    function_found = False

    for entry in json_data:
        code = entry.get('code', '')

        # Check if this is the function definition
        if f'function {function_name}' in code and code.strip().endswith('{'):
            function_found = True
            continue

        # If we found the function, return the first non-empty, non-bracket code line
        if function_found:
            code_stripped = code.strip()
            if code_stripped and code_stripped != '}' and code_stripped != '\n':
                return entry.get('startLine')

    return None

def generate_annotation_json(original_json_path: str, excel_data: pd.DataFrame, output_path: str):
    """
    Generate annotation JSON file from original JSON and Excel data.
    """
    # Load original JSON
    with open(original_json_path, 'r', encoding='utf-8') as f:
        original_data = json.load(f)

    # Extract filename for matching with Excel
    filename = os.path.basename(original_json_path)
    sol_filename = filename.replace('_c.json', '.sol')

    # Find matching row in Excel data
    matching_rows = excel_data[excel_data['Unnamed: 2'].str.contains(sol_filename.replace('.sol', ''), na=False)]

    if matching_rows.empty:
        print(f"Warning: No Excel data found for {sol_filename}")
        # Just copy original data if no match found
        annotated_data = original_data.copy()
    else:
        # Use first matching row
        row = matching_rows.iloc[0]

        # Extract target variables
        target_var_text = row['Unnamed: 9']  # Target Variable column
        function_name = row['Unnamed: 4']    # Function Name column

        variables = parse_target_variables(target_var_text)

        # Copy original data
        annotated_data = original_data.copy()

        if variables:
            # Find the target function's start line
            target_start_line = find_target_function_start_line(original_data, function_name)

            if target_start_line is None:
                print(f"Warning: Could not find function {function_name} in {sol_filename}")
                target_start_line = 7  # Default fallback

            # Add annotations at the end
            annotation_line = target_start_line
            for var_type, var_name, values in variables:
                annotation_code = f"//@{var_type} {var_name} = {values};"
                annotation_entry = {
                    "code": annotation_code,
                    "startLine": annotation_line,
                    "endLine": annotation_line,
                    "event": "add"
                }
                annotated_data.append(annotation_entry)
                annotation_line += 1

    # Write output file
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(annotated_data, f, indent=2, ensure_ascii=False)

    print(f"Generated: {output_path}")

def main():
    """Main function to generate all annotation files."""

    # Load Excel data
    excel_path = 'dataset/evaluation_Dataset.xlsx'
    excel_data = pd.read_excel(excel_path)

    # Input and output directories
    input_dir = 'dataset/json/original'
    output_dir = 'dataset/json/annotation'

    # Process all JSON files in original directory
    original_files = list(Path(input_dir).glob('*.json'))

    print(f"Processing {len(original_files)} files...")

    for original_file in original_files:
        # Generate output filename
        output_filename = original_file.stem + '_annot.json'
        output_path = os.path.join(output_dir, output_filename)

        # Generate annotation file
        generate_annotation_json(str(original_file), excel_data, output_path)

    print(f"Completed! Generated {len(original_files)} annotation files in {output_dir}")

if __name__ == "__main__":
    main()