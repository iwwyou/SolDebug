"""
Measure latency for missing contracts with all input ranges
"""
import json
import time
import re
import pandas as pd
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers


def extract_contract_and_function(records):
    contract_name = None
    function_name = None
    for rec in records:
        code = rec['code'].strip()
        if code.startswith('contract '):
            match = re.match(r'contract\s+(\w+)', code)
            if match:
                contract_name = match.group(1)
        if code.startswith('function '):
            match = re.match(r'function\s+(\w+)', code)
            if match:
                function_name = match.group(1)
    return contract_name, function_name


def modify_interval_values(records, delta):
    modified_records = []
    for rec in records.copy():
        code = rec['code']
        if code.strip().startswith('// @'):
            pattern = r'(// @\w+\s+\w+(?:\.\w+)*\s*=\s*)\[(\d+),\s*(\d+)\]'
            match = re.search(pattern, code)
            if match:
                prefix = match.group(1)
                min_val = int(match.group(2))
                original_max = int(match.group(3))
                new_max = original_max + delta
                new_code = re.sub(pattern, f'{prefix}[{min_val},{new_max}]', code)
                rec = rec.copy()
                rec['code'] = new_code
        modified_records.append(rec)
    return modified_records


def simulate_inputs(records):
    contract_analyzer = ContractAnalyzer()
    snapman = contract_analyzer.snapman
    batch_mgr = DebugBatchManager(contract_analyzer, snapman)
    in_testcase = False

    start_time = time.time()

    for idx, rec in enumerate(records):
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)
        stripped = code.lstrip()

        if stripped.startswith("// @Debugging BEGIN"):
            batch_mgr.reset()
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            batch_mgr.flush()
            in_testcase = False
            continue

        if stripped.startswith("// @"):
            if ev == "add":
                batch_mgr.add_line(code, s, e)
            elif ev == "modify":
                batch_mgr.modify_line(code, s, e)
            elif ev == "delete":
                batch_mgr.delete_line(s)
            if not in_testcase:
                batch_mgr.flush()
            continue

        if code.strip():
            ctx = contract_analyzer.get_current_context_type()
            tree = ParserHelpers.generate_parse_tree(code, ctx, True)
            EnhancedSolidityVisitor(contract_analyzer).visit(tree)

    end_time = time.time()
    return (end_time - start_time) * 1000


# Load Remix data
remix_df = pd.read_csv('Evaluation/Remix/remix_benchmark_results.csv')

# Missing files
missing_files = [
    ('Lock_c_annot.json', 'Lock', 'Lock', 'pending'),
    ('LockupContract_c_annot.json', 'LockupContract', 'LockupContract_c.sol', '_getReleasedAmount'),
    ('PoolKeeper_c_annot.json', 'PoolKeeper', 'PoolKeeper', 'keeperTip'),
    ('ThorusBond_c_annot.json', 'ThorusBond', 'ThorusBond', 'claimablePayout')
]

new_rows = []

for filename, sol_name, remix_contract, remix_function in missing_files:
    filepath = f'dataset/json/annotation/{filename}'

    print(f'\nProcessing: {filename}')

    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            records = json.load(f)

        contract, function = extract_contract_and_function(records)
        print(f'  Contract: {contract}, Function: {function}')

        # Get Remix data
        remix_row = remix_df[
            (remix_df['contract_name'] == remix_contract) &
            (remix_df['function_name'] == remix_function)
        ]

        if len(remix_row) == 0:
            print(f'  [WARN] No Remix data found')
            byteop = 'N/A'
            remix_pure = 'N/A'
            remix_total = 'N/A'
        else:
            remix_row = remix_row.iloc[0]
            byteop = remix_row['byteop_count']
            remix_pure = f"{float(remix_row['pure_debug_time_ms']) / 1000:.6f}"
            remix_total = f"{float(remix_row['total_time_ms']) / 1000:.6f}"

        # Test with different max values
        for max_val in [0, 2, 5, 10]:
            modified_records = modify_interval_values(records, max_val)

            try:
                latency_ms = simulate_inputs(modified_records)
                latency_s = f"{latency_ms / 1000:.6f}"
                print(f'  Range {max_val}: {latency_ms:.2f} ms')

                new_rows.append({
                    'Contract': sol_name,
                    'Function': function,
                    'ByteOp_Count': byteop,
                    'Input_Range': max_val,
                    'SolQDebug_Latency_s': latency_s,
                    'Remix_PureDebug_s': remix_pure,
                    'Remix_Total_s': remix_total
                })
            except Exception as e:
                print(f'  Range {max_val}: ERROR - {e}')

    except Exception as e:
        print(f'  ERROR loading file: {e}')

# Load existing CSV and append
df = pd.read_csv('Evaluation/soldebug_benchmark_results_seconds.csv')
new_df = pd.DataFrame(new_rows)
combined_df = pd.concat([df, new_df], ignore_index=True)

# Sort
combined_df = combined_df.sort_values(['Contract', 'Input_Range']).reset_index(drop=True)

# Save
combined_df.to_csv('Evaluation/soldebug_benchmark_results_seconds.csv', index=False)

print(f'\n' + '='*80)
print(f'Added {len(new_rows)} measurements')
print(f'Total measurements: {len(combined_df)}')
print(f'Unique contracts: {combined_df["Contract"].nunique()}')
