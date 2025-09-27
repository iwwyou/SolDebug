#!/usr/bin/env python3
import json
import os
import glob

def fix_json_file(filepath):
    """Fix a single JSON annotation file"""
    print(f"Processing: {os.path.basename(filepath)}")

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

    # Step 4: Get the startLine of the first debug annotation for BEGIN/END placement
    first_debug_line = data[debug_start_idx]['startLine']

    # Step 5: Add // @Debugging BEGIN before first debug annotation
    begin_entry = {
        "code": "// @Debugging BEGIN",
        "startLine": first_debug_line,
        "endLine": first_debug_line,
        "event": "add"
    }
    data.insert(debug_start_idx, begin_entry)

    # Step 6: Add // @Debugging END after last debug annotation (index shifted by 1)
    end_entry = {
        "code": "// @Debugging END",
        "startLine": first_debug_line,
        "endLine": first_debug_line,
        "event": "add"
    }
    data.insert(debug_end_idx + 2, end_entry)  # +1 for the BEGIN insertion, +1 for after last debug

    # Write back to file
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print(f"  [OK] Successfully updated {os.path.basename(filepath)}")
    return True

def main():
    annotation_dir = r"C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\dataset\json\annotation"
    json_files = glob.glob(os.path.join(annotation_dir, "*.json"))

    print(f"Found {len(json_files)} JSON files to process")
    print("=" * 50)

    success_count = 0
    for json_file in json_files:
        try:
            if fix_json_file(json_file):
                success_count += 1
        except Exception as e:
            print(f"  [ERROR] Error processing {os.path.basename(json_file)}: {e}")

    print("=" * 50)
    print(f"Successfully processed {success_count}/{len(json_files)} files")

if __name__ == "__main__":
    main()