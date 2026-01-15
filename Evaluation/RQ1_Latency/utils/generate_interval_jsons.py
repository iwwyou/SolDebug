"""
Generate interval-adjusted JSON files for SolQDebug benchmark.
Creates 4 versions of each annotation JSON (interval 0, 2, 5, 10).
"""

import json
import os
import re
from pathlib import Path

# Source and destination paths
SOURCE_DIR = Path(__file__).parent.parent.parent / "dataset" / "json" / "annotation"
DEST_BASE_DIR = Path(__file__).parent / "json_intervals"

INTERVALS = [0, 2, 5, 10]


def build_memory_var_mapping(json_data):
    """
    코드에서 'memory 변수명 = 매핑[키]' 또는 'storage 변수명 = 매핑[키]' 패턴을 찾아
    로컬 변수명 -> 원본 매핑 경로 매핑을 생성.

    예: "LockedData memory _data = data[_account];"
        → {"_data": "data[_account]"}
    """
    var_to_source = {}

    for record in json_data:
        code = record.get("code", "")

        # Skip annotation lines
        if code.strip().startswith("// @"):
            continue

        # Pattern: (Type) (memory|storage) (varName) = (mapping)[key];
        # Examples:
        #   LockedData memory _data = data[_account];
        #   UserInfo storage info = userInfo[user];
        #   UserInfo memory info = userInfo[user];
        pattern = r'\b(\w+)\s+(?:memory|storage)\s+(\w+)\s*=\s*(\w+)\[([^\]]+)\]'

        match = re.search(pattern, code)
        if match:
            # type_name = match.group(1)  # LockedData, UserInfo
            var_name = match.group(2)     # _data, info
            mapping_name = match.group(3) # data, userInfo
            key_expr = match.group(4)     # _account, user

            source_path = f"{mapping_name}[{key_expr}]"
            var_to_source[var_name] = source_path

    return var_to_source


def transform_local_var_annotations(json_data, var_to_source):
    """
    로컬 변수에 대한 annotation을 원본 매핑 경로로 변환.

    예: "// @StateVar _data.total = [700,800];"
        → "// @StateVar data[_account].total = [700,800];"
    """
    if not var_to_source:
        return json_data

    transformed_data = []

    for record in json_data:
        code = record.get("code", "")
        new_record = record.copy()

        # Only process annotation lines
        if code.strip().startswith("// @") and "BEGIN" not in code and "END" not in code:
            # Check each local variable
            for var_name, source_path in var_to_source.items():
                # Pattern: @StateVar varName.member = value
                # or: @StateVar varName = value (without member)

                # With member access: _data.total -> data[_account].total
                member_pattern = rf'(@StateVar\s+){var_name}\.(\w+)(\s*=)'
                if re.search(member_pattern, code):
                    code = re.sub(
                        member_pattern,
                        rf'\g<1>{source_path}.\g<2>\g<3>',
                        code
                    )

        new_record["code"] = code
        transformed_data.append(new_record)

    return transformed_data


def adjust_interval_value(match, interval):
    """
    Adjust [min, max] interval to [min, min+interval].
    Example: [100, 150] with interval=5 -> [100, 105]
    """
    min_val = int(match.group(1))
    # interval 0 means single value (min = max)
    new_max = min_val + interval
    return f"[{min_val},{new_max}]"


def adjust_array_value(match, interval, is_address=False):
    """
    Adjust array to have (1 + interval) elements.
    Example: array [1,2,3] with interval=5 -> array [1,2,3,4,5,6]
    """
    prefix = match.group(1)  # "array " or "arrayAddress"
    elements_str = match.group(2)  # "[1,2,3]"

    # Parse existing elements
    elements_str_clean = elements_str.strip('[]')
    if elements_str_clean:
        existing_elements = [x.strip() for x in elements_str_clean.split(',')]
    else:
        existing_elements = []

    # Target count: 1 + interval (minimum 1)
    target_count = max(1, 1 + interval)

    if len(existing_elements) >= target_count:
        # Truncate to target count
        new_elements = existing_elements[:target_count]
    else:
        # Extend with sequential numbers
        new_elements = existing_elements.copy()
        # Find the max number to continue from
        max_num = 0
        for elem in existing_elements:
            try:
                max_num = max(max_num, int(elem))
            except ValueError:
                pass

        while len(new_elements) < target_count:
            max_num += 1
            new_elements.append(str(max_num))

    return f"{prefix}[{','.join(new_elements)}]"


def adjust_annotation_code(code, interval):
    """
    Adjust annotation code based on interval.
    Handles: [min,max], array [...], arrayAddress[...]
    Preserves: symbolicAddress, symbolicBytes, any
    """
    # Skip non-annotation lines
    if not code.strip().startswith("// @"):
        return code

    # Skip BEGIN/END markers
    if "BEGIN" in code or "END" in code:
        return code

    # Pattern for interval values: [number, number]
    # Matches: [100,150], [0, 5], [ 10 , 20 ]
    interval_pattern = r'\[\s*(\d+)\s*,\s*\d+\s*\]'

    # Pattern for array: array [1,2,3] or array[1,2,3]
    array_pattern = r'(array\s*)\[([^\]]*)\]'

    # Pattern for arrayAddress: arrayAddress[1,2,3]
    array_address_pattern = r'(arrayAddress)\[([^\]]*)\]'

    # Check for symbolic/any - don't modify these
    if 'symbolicAddress' in code or 'symbolicBytes' in code or '= any' in code:
        return code

    # Adjust arrayAddress first (more specific pattern)
    code = re.sub(
        array_address_pattern,
        lambda m: adjust_array_value(m, interval, is_address=True),
        code
    )

    # Adjust array
    code = re.sub(
        array_pattern,
        lambda m: adjust_array_value(m, interval, is_address=False),
        code
    )

    # Adjust interval values (but not inside arrays - already handled)
    # Only match standalone intervals, not part of array
    if 'array' not in code.lower():
        code = re.sub(
            interval_pattern,
            lambda m: adjust_interval_value(m, interval),
            code
        )

    return code


def needs_index_adjustment(json_data):
    """
    Check if this JSON has array + index pattern that needs coordinated adjustment.
    Returns tuple: (array_var_name, index_var_name) or None
    """
    array_vars = []
    index_vars = []

    for record in json_data:
        code = record.get("code", "")
        if not code.strip().startswith("// @"):
            continue

        # Find array variables
        if "array" in code.lower() and "= array" in code.lower():
            # Extract variable name
            match = re.search(r'@\w+\s+(\w+)\s*=\s*array', code, re.IGNORECASE)
            if match:
                array_vars.append(match.group(1))

        # Find index variable (LocalVar with exact name 'index')
        if "@LocalVar" in code:
            match = re.search(r'@LocalVar\s+(index)\s*=', code)
            if match:
                index_vars.append(match.group(1))

    return (array_vars, index_vars) if array_vars and index_vars else None


def adjust_index_for_array(code, interval, array_length):
    """
    Adjust index variable to trigger loop proportional to interval.
    index = array_length + interval makes additionalCount = interval + 1
    """
    if "@LocalVar" not in code:
        return code

    # Pattern: exactly "index = [min, max]" (not ticketIndex, tokenIndex, etc.)
    pattern = r'(@LocalVar\s+)(index)(\s*=\s*)\[\s*\d+\s*,\s*\d+\s*\]'

    # index = array_length + interval
    # This makes additionalCount = (array_length + interval) - array_length + 1 = interval + 1
    new_index = array_length + interval

    code = re.sub(
        pattern,
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}[{new_index},{new_index}]",
        code
    )

    return code


def adjust_thorus_lottery_index(code, interval, array_length):
    """
    ThorusLottery specific: adjust ticketIndex to match ticketNumbers array length.
    ticketIndex should be in range [0, array_length - 1]
    """
    if "@LocalVar" not in code or "ticketIndex" not in code:
        return code

    # Pattern: ticketIndex = [min, max]
    pattern = r'(@LocalVar\s+)(ticketIndex)(\s*=\s*)\[\s*\d+\s*,\s*\d+\s*\]'

    # ticketIndex should be valid array index: [0, array_length - 1]
    max_index = max(0, array_length - 1)

    code = re.sub(
        pattern,
        lambda m: f"{m.group(1)}{m.group(2)}{m.group(3)}[0,{max_index}]",
        code
    )

    return code


def process_json_file(source_path, interval):
    """
    Process a single JSON file and adjust for given interval.
    """
    with open(source_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # ★ Step 0: 로컬 변수 -> 원본 매핑 경로 변환 (soundness 유지)
    var_to_source = build_memory_var_mapping(data)
    if var_to_source:
        data = transform_local_var_annotations(data, var_to_source)

    # Calculate array length for this interval (for index adjustment)
    array_length = max(1, 1 + interval)

    # Check if this file needs coordinated array/index adjustment
    adjustment_info = needs_index_adjustment(data)

    # Check for special cases
    filename = source_path.name
    is_thorus_lottery = "ThorusLottery" in filename
    is_mock_chainlink = "MockChainlinkOracle" in filename

    # Process each record
    adjusted_data = []
    for record in data:
        new_record = record.copy()
        code = record.get("code", "")

        # Adjust annotation code
        new_code = adjust_annotation_code(code, interval)

        # Additional adjustment for index variables if needed
        if adjustment_info and "@LocalVar" in code and "index" in code.lower():
            new_code = adjust_index_for_array(new_code, interval, array_length)

        # ThorusLottery specific: adjust ticketIndex
        if is_thorus_lottery and "@LocalVar" in code and "ticketIndex" in code:
            new_code = adjust_thorus_lottery_index(new_code, interval, array_length)

        new_record["code"] = new_code
        adjusted_data.append(new_record)

    # MockChainlinkOracle specific: replace entry.updatedAt with entries[i].updatedAt
    if is_mock_chainlink:
        adjusted_data = process_mock_chainlink_oracle(adjusted_data, interval)

    return adjusted_data


def process_mock_chainlink_oracle(data, interval):
    """
    MockChainlinkOracle specific processing:
    - Replace entry.updatedAt with entries[0].updatedAt in ANNOTATIONS ONLY
    - For interval > 0, add entries[1..interval].updatedAt annotations
    """
    new_data = []

    for i, record in enumerate(data):
        code = record.get("code", "")

        # Only process annotation lines (starting with "// @")
        is_annotation = code.strip().startswith("// @")

        # Find and fix the entry.updatedAt annotation ONLY
        if is_annotation and "entry.updatedAt" in code:
            # Replace entry.updatedAt with entries[0].updatedAt
            new_code = code.replace("entry.updatedAt", "entries[0].updatedAt")
            new_record = record.copy()
            new_record["code"] = new_code
            new_data.append(new_record)

            # Add additional entries for interval > 0
            for idx in range(1, interval + 1):
                additional_record = record.copy()
                additional_record["code"] = code.replace("entry.updatedAt", f"entries[{idx}].updatedAt")
                new_data.append(additional_record)
        else:
            new_data.append(record)

    return new_data


def generate_all_interval_jsons():
    """
    Generate all interval-adjusted JSON files.
    """
    # Create destination directories
    for interval in INTERVALS:
        dest_dir = DEST_BASE_DIR / f"interval_{interval}"
        dest_dir.mkdir(parents=True, exist_ok=True)

    # Get all source JSON files
    source_files = sorted(SOURCE_DIR.glob("*_annot.json"))

    print(f"Source directory: {SOURCE_DIR}")
    print(f"Destination base: {DEST_BASE_DIR}")
    print(f"Found {len(source_files)} JSON files")
    print(f"Generating for intervals: {INTERVALS}")
    print("=" * 60)

    for source_file in source_files:
        filename = source_file.name
        contract_name = filename.replace("_c_annot.json", "").replace("_annot.json", "")

        print(f"\nProcessing: {contract_name}")

        for interval in INTERVALS:
            try:
                # Process and adjust
                adjusted_data = process_json_file(source_file, interval)

                # Save to destination
                dest_dir = DEST_BASE_DIR / f"interval_{interval}"
                dest_file = dest_dir / filename

                with open(dest_file, 'w', encoding='utf-8') as f:
                    json.dump(adjusted_data, f, indent=2, ensure_ascii=False)

                print(f"  [OK] interval_{interval}/{filename}")

            except Exception as e:
                print(f"  [ERROR] interval_{interval}/{filename}: {e}")

    print("\n" + "=" * 60)
    print("Generation complete!")
    print(f"Total files generated: {len(source_files) * len(INTERVALS)}")


def verify_generation():
    """
    Verify generated files and show sample adjustments.
    """
    print("\n" + "=" * 60)
    print("VERIFICATION: Sample adjustments")
    print("=" * 60)

    # Pick a sample file with various annotation types
    sample_files = ["ThorusBond_c_annot.json", "AvatarArtMarketPlace_c_annot.json", "Balancer_c_annot.json"]

    for sample_file in sample_files:
        source_path = SOURCE_DIR / sample_file
        if not source_path.exists():
            continue

        print(f"\n--- {sample_file} ---")

        with open(source_path, 'r', encoding='utf-8') as f:
            original = json.load(f)

        # Show original annotations
        print("Original annotations:")
        for record in original:
            code = record.get("code", "")
            if code.strip().startswith("// @") and "BEGIN" not in code and "END" not in code:
                print(f"  {code.strip()}")

        # Show adjusted for each interval
        for interval in INTERVALS:
            dest_path = DEST_BASE_DIR / f"interval_{interval}" / sample_file
            if dest_path.exists():
                with open(dest_path, 'r', encoding='utf-8') as f:
                    adjusted = json.load(f)

                print(f"\nInterval {interval}:")
                for record in adjusted:
                    code = record.get("code", "")
                    if code.strip().startswith("// @") and "BEGIN" not in code and "END" not in code:
                        print(f"  {code.strip()}")


if __name__ == "__main__":
    generate_all_interval_jsons()
    verify_generation()
