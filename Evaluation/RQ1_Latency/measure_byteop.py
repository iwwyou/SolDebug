"""
ByteOp Measurement Utility

Measures the number of EVM opcodes executed for each function in the dataset.
Updates the evaluation_Dataset.xlsx with ByteOp counts.
"""

import pandas as pd
from remix_benchmark import RemixBenchmark
from pathlib import Path
import time


def measure_byteop_for_contract(benchmark, contract_path, function_name):
    """
    Measure ByteOp count for a single contract function

    Args:
        benchmark: RemixBenchmark instance
        contract_path: Path to contract file
        function_name: Function to test

    Returns:
        ByteOp count (int) or None if failed
    """
    try:
        # Load contract code
        with open(contract_path, 'r', encoding='utf-8') as f:
            contract_code = f.read()

        # Measure (minimal version - just get ByteOp)
        print(f"  Measuring ByteOp for {function_name}...")

        # Create and compile contract
        benchmark._create_contract_file(contract_code)
        benchmark._compile_contract()
        benchmark._deploy_contract()

        # Execute function (with no inputs for now)
        benchmark._execute_function(function_name, inputs=None)

        # Open debugger
        benchmark._open_debugger()

        # Get total steps (ByteOp count)
        byteop_count = benchmark._get_total_steps()

        return byteop_count

    except Exception as e:
        print(f"  ✗ Error measuring ByteOp: {e}")
        return None


def update_dataset_with_byteop(dry_run=False):
    """
    Measure ByteOp for all contracts and update dataset

    Args:
        dry_run: If True, don't save changes to Excel
    """
    # Load dataset
    df = pd.read_excel('dataset/evaluation_Dataset.xlsx', header=0)
    df.columns = ['Index', 'Size_KB', 'Sol_File_Name', 'Contract_Name', 'Function_Name',
                  'Original_Function_Line', 'Annotation_Targets', 'State_Slots', 'ByteOp',
                  'Target_Variables']

    # Remove header row if exists
    if df.iloc[0]['Size_KB'] == '용량':
        df = df.iloc[1:].reset_index(drop=True)

    print(f"\n{'='*60}")
    print(f"ByteOp Measurement for {len(df)} contracts")
    print(f"{'='*60}\n")

    # Initialize benchmark
    benchmark = RemixBenchmark(headless=False)

    byteop_results = []

    for idx, row in df.iterrows():
        contract_name = row['Contract_Name']
        sol_file = row['Sol_File_Name']
        function_name = row['Function_Name']

        print(f"\n[{idx + 1}/{len(df)}] {contract_name}.{function_name}")

        # Check if ByteOp already measured
        current_byteop = row['ByteOp']
        if pd.notna(current_byteop) and current_byteop > 0:
            print(f"  ℹ ByteOp already measured: {int(current_byteop)}")
            byteop_results.append(int(current_byteop))
            continue

        # Find contract file
        contract_path = Path(f"dataset/contraction/{sol_file.replace('.sol', '_c.sol')}")
        if not contract_path.exists():
            print(f"  ⚠ Contract file not found: {contract_path}")
            byteop_results.append(None)
            continue

        # Measure ByteOp
        byteop = measure_byteop_for_contract(benchmark, contract_path, function_name)

        if byteop is not None:
            print(f"  ✓ ByteOp measured: {byteop}")
            byteop_results.append(byteop)
        else:
            print(f"  ✗ Failed to measure ByteOp")
            byteop_results.append(None)

        # Reset for next contract
        benchmark.reset()
        time.sleep(2)

    # Close browser
    benchmark.close()

    # Update dataframe
    df['ByteOp'] = byteop_results

    # Save results
    if not dry_run:
        # Save to new file first (backup)
        df.to_excel('dataset/evaluation_Dataset_with_byteop.xlsx', index=False)
        print(f"\n✓ Results saved to: dataset/evaluation_Dataset_with_byteop.xlsx")
        print(f"  (Original file preserved)")
    else:
        print(f"\n[DRY RUN] Would save to: dataset/evaluation_Dataset_with_byteop.xlsx")

    # Print summary
    print(f"\n{'='*60}")
    print(f"ByteOp Measurement Summary")
    print(f"{'='*60}")
    measured = sum(1 for x in byteop_results if x is not None)
    print(f"Successfully measured: {measured}/{len(df)}")
    if measured > 0:
        valid_byteops = [x for x in byteop_results if x is not None]
        print(f"Average ByteOp: {sum(valid_byteops) / len(valid_byteops):.0f}")
        print(f"Min ByteOp: {min(valid_byteops)}")
        print(f"Max ByteOp: {max(valid_byteops)}")
    print(f"{'='*60}\n")

    return df


def quick_byteop_estimate():
    """
    Quick ByteOp estimation based on function size (without running Remix)

    This is a rough estimation for planning purposes.
    Actual ByteOp should be measured with Remix for accuracy.
    """
    df = pd.read_excel('dataset/evaluation_Dataset.xlsx', header=0)
    df.columns = ['Index', 'Size_KB', 'Sol_File_Name', 'Contract_Name', 'Function_Name',
                  'Original_Function_Line', 'Annotation_Targets', 'State_Slots', 'ByteOp',
                  'Target_Variables']

    if df.iloc[0]['Size_KB'] == '용량':
        df = df.iloc[1:].reset_index(drop=True)

    estimates = []

    for idx, row in df.iterrows():
        line_range = row['Original_Function_Line']

        if isinstance(line_range, str) and '-' in line_range:
            try:
                start, end = line_range.split('-')
                lines = int(end) - int(start) + 1

                # Rough heuristic:
                # - Simple assignment: ~5 opcodes
                # - Arithmetic operation: ~3-10 opcodes
                # - Storage read/write: ~5-10 opcodes
                # - Function call: ~10-30 opcodes
                # Average: ~5-7 opcodes per line of Solidity

                estimated_byteop = lines * 6  # Conservative estimate

                estimates.append(estimated_byteop)
            except:
                estimates.append(50)  # Default
        else:
            estimates.append(50)  # Default

    df['ByteOp_Estimated'] = estimates

    # Save
    df.to_csv('byteop_estimates.csv', index=False)

    print(f"\n{'='*60}")
    print(f"Quick ByteOp Estimation")
    print(f"{'='*60}")
    print(f"Average estimated ByteOp: {sum(estimates) / len(estimates):.0f}")
    print(f"Min estimated ByteOp: {min(estimates)}")
    print(f"Max estimated ByteOp: {max(estimates)}")
    print(f"\n⚠ Note: These are rough estimates!")
    print(f"  For accurate measurements, use update_dataset_with_byteop()")
    print(f"{'='*60}\n")

    return df


if __name__ == "__main__":
    import sys

    if len(sys.argv) > 1 and sys.argv[1] == '--estimate':
        # Quick estimation mode
        quick_byteop_estimate()
    else:
        # Full measurement mode
        print("\nStarting ByteOp measurement...")
        print("This will take a while (~30 contracts × 30 seconds each = ~15 minutes)")
        print("\nPress Ctrl+C to cancel\n")

        try:
            time.sleep(3)
            df = update_dataset_with_byteop(dry_run=False)
        except KeyboardInterrupt:
            print("\n\nMeasurement cancelled by user")
