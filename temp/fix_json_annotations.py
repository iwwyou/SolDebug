#!/usr/bin/env python3
import json
import os
import glob
import pandas as pd

def get_target_function_name(filename, excel_data):
    """Get target function name from Excel data for the given filename"""
    sol_filename = filename.replace('_c_annot.json', '')
    matching_rows = excel_data[excel_data['Unnamed: 2'].str.contains(sol_filename, na=False)]

    if matching_rows.empty:
        return None

    return matching_rows.iloc[0]['Unnamed: 4']  # Function Name column

def find_target_function_start_line(json_data, function_name):
    """Find the start line of the target function's first code statement"""
    function_found = False

    for entry in json_data:
        code = entry.get('code', '')

        # Check if this is the function definition
        if f'function {function_name}' in code and '{' in code:
            function_found = True
            continue

        # If we found the function, return the first non-empty, non-bracket code line
        if function_found:
            code_stripped = code.strip()
            if code_stripped and code_stripped != '}' and code_stripped != '\n' and not code_stripped.startswith('//'):
                return entry.get('startLine')

    return None

def fix_json_file(filepath, excel_data):
    """Fix a single JSON annotation file"""
    print(f"Processing: {os.path.basename(filepath)}")

    # Get target function name from Excel data
    filename = os.path.basename(filepath)
    target_function = get_target_function_name(filename, excel_data)

    if target_function is None:
        print(f"  No target function found for {filename}")
        return False

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Step 1: Remove existing @Debugging BEGIN/END entries
    original_length = len(data)
    data = [entry for entry in data if entry.get('code', '') not in ['// @Debugging BEGIN', '// @Debugging END']]
    removed_count = original_length - len(data)
    if removed_count > 0:
        print(f"  Removed {removed_count} existing BEGIN/END entries")

    # Step 2: Find debug annotations (starting with @StateVar, @LocalVar, etc.)
    debug_start_idx = None
    debug_end_idx = None
    debug_indices = []

    for i, entry in enumerate(data):
        code = entry.get('code', '')
        if code.startswith('//') and any(x in code for x in ['@StateVar', '@LocalVar', '@Param', '@Return']):
            if debug_start_idx is None:
                debug_start_idx = i
            debug_end_idx = i
            debug_indices.append(i)

    if debug_start_idx is None:
        print(f"  No debug annotations found in {os.path.basename(filepath)}")
        return False

    # Step 3: Fix spacing in debug annotations: //@StateVar -> // @StateVar
    for i in debug_indices:
        code = data[i]['code']
        if code.startswith('//') and not code.startswith('// '):
            # Add space after //
            if code.startswith('//@'):
                fixed_code = code.replace('//@', '// @', 1)
                data[i]['code'] = fixed_code
                print(f"  Fixed: {code} -> {fixed_code}")

    # Step 4: Find the target function's first code line using the function name
    first_code_line_in_function = find_target_function_start_line(data, target_function)

    if first_code_line_in_function is None:
        print(f"  Could not find target function '{target_function}' first code line")
        return False

    print(f"  Target function: {target_function}, first code line: {first_code_line_in_function}")

    # Step 5: Add // @Debugging BEGIN at the first code line position
    begin_entry = {
        "code": "// @Debugging BEGIN",
        "startLine": first_code_line_in_function,
        "endLine": first_code_line_in_function,
        "event": "add"
    }
    data.insert(debug_start_idx, begin_entry)

    # Step 6: Update all debug annotations and subsequent entries with sequential line numbers
    current_line = first_code_line_in_function + 1
    for i in range(debug_start_idx + 1, debug_end_idx + 2):  # +1 for BEGIN insertion, +1 for inclusive range
        data[i]['startLine'] = current_line
        data[i]['endLine'] = current_line
        current_line += 1

    # Step 7: Add // @Debugging END
    end_entry = {
        "code": "// @Debugging END",
        "startLine": current_line,
        "endLine": current_line,
        "event": "add"
    }
    data.insert(debug_end_idx + 2, end_entry)  # +1 for the BEGIN insertion, +1 for after last debug

    # Write back to file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  [OK] Successfully updated {os.path.basename(filepath)}")
    return True

def main():
    # Load Excel data
    excel_path = r"C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\dataset\evaluation_Dataset.xlsx"
    try:
        excel_data = pd.read_excel(excel_path)
        print(f"Loaded Excel data with {len(excel_data)} rows")
    except Exception as e:
        print(f"Error loading Excel file: {e}")
        return

    annotation_dir = r"C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\dataset\json\annotation"
    json_files = glob.glob(os.path.join(annotation_dir, "*.json"))

    print(f"Found {len(json_files)} JSON files to process")
    print("=" * 50)

    success_count = 0
    for json_file in json_files:
        try:
            if fix_json_file(json_file, excel_data):
                success_count += 1
        except Exception as e:
            print(f"  [ERROR] Error processing {os.path.basename(json_file)}: {e}")

    print("=" * 50)
    print(f"Successfully processed {success_count}/{len(json_files)} files")

if __name__ == "__main__":
    main()