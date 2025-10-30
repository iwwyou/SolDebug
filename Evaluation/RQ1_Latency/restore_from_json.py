"""
Restore CSV from JSON and clean data
"""
import pandas as pd
import json
import os

# Get script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_file = os.path.join(script_dir, 'remix_benchmark_results.csv')
json_file = os.path.join(script_dir, 'remix_benchmark_results.json')

# Read JSON
with open(json_file, 'r', encoding='utf-8') as f:
    json_data = json.load(f)

print(f'Original JSON entries: {len(json_data)}')

# Clean JSON data
numeric_columns = ['setup_time_ms', 'compile_time_ms', 'deploy_time_ms', 'state_slot_setup_time_ms',
                   'num_state_slots', 'num_state_arrays', 'execution_time_ms', 'debug_open_time_ms',
                   'byteop_count', 'jump_to_end_time_ms', 'total_time_ms', 'pure_debug_time_ms',
                   'annotation_targets', 'expected_state_slots', 'run_number']

json_clean = []
for i, entry in enumerate(json_data):
    print(f'\nEntry {i}: {entry.get("contract_name")} - success={entry.get("success")} - byteop={entry.get("byteop_count")}')

    # Skip failed entries
    success_val = entry.get('success')
    if success_val in [True, 1.0, '1.0', 'True']:
        # Fix data types
        for key in numeric_columns:
            if key in entry and entry[key] is not None:
                try:
                    entry[key] = float(entry[key])
                except (ValueError, TypeError):
                    print(f'  [WARNING] Cannot convert {key}={entry[key]} to float')
                    entry[key] = None

        entry['success'] = 1.0
        entry['error'] = None
        json_clean.append(entry)
    else:
        print(f'  [SKIP] Failed entry: {entry.get("contract_name")}')

print(f'\n=== Summary ===')
print(f'Total entries: {len(json_data)}')
print(f'Successful entries: {len(json_clean)}')
print(f'Removed: {len(json_data) - len(json_clean)} entries')

# Create DataFrame from clean JSON
df_clean = pd.DataFrame(json_clean)
print(f'\nDataFrame shape: {df_clean.shape}')
print(f'Unique contracts: {df_clean["contract_name"].nunique()}')

# Save cleaned CSV
df_clean.to_csv(csv_file, index=False)
print(f'[OK] CSV saved: {len(df_clean)} rows')

# Save cleaned JSON
with open(json_file, 'w', encoding='utf-8') as f:
    json.dump(json_clean, f, indent=2)
print(f'[OK] JSON saved: {len(json_clean)} entries')
