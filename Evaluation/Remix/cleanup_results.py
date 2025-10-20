"""
Script to clean up remix benchmark results:
1. Remove failed entries
2. Fix data type issues
"""
import pandas as pd
import json
import os

# Get script directory
script_dir = os.path.dirname(os.path.abspath(__file__))
csv_file = os.path.join(script_dir, 'remix_benchmark_results.csv')
json_file = os.path.join(script_dir, 'remix_benchmark_results.json')

# Read CSV
df = pd.read_csv(csv_file)
print(f'Original CSV rows: {len(df)}')

# Read JSON
with open(json_file, 'r', encoding='utf-8') as f:
    json_data = json.load(f)
print(f'Original JSON entries: {len(json_data)}')

# Identify problematic rows
print('\n=== Problematic Rows ===')
problematic = df[(df['success'] == 0.0) | (df['success'] == False) | (df['error'].notna())]
print(problematic[['contract_name', 'function_name', 'success', 'byteop_count', 'error']])

# Remove failed entries (success != True and success != 1.0)
print('\n=== Cleaning Data ===')
print(f'Success column unique values: {df["success"].unique()}')
print(f'Success column dtype: {df["success"].dtype}')

# Filter for successful runs (success is True, 1.0, or "True" string)
df_clean = df[(df['success'] == True) | (df['success'] == 1.0) | (df['success'] == '1.0') | (df['success'] == 'True')].copy()
print(f'Rows after removing failures: {len(df_clean)}')

# Fix data types
print('\n=== Fixing Data Types ===')
numeric_columns = ['setup_time_ms', 'compile_time_ms', 'deploy_time_ms', 'state_slot_setup_time_ms',
                   'num_state_slots', 'num_state_arrays', 'execution_time_ms', 'debug_open_time_ms',
                   'byteop_count', 'jump_to_end_time_ms', 'total_time_ms', 'pure_debug_time_ms',
                   'annotation_targets', 'expected_state_slots', 'run_number']

for col in numeric_columns:
    if col in df_clean.columns:
        df_clean[col] = pd.to_numeric(df_clean[col], errors='coerce')
        print(f'  {col}: {df_clean[col].dtype}')

# Convert success to numeric
df_clean['success'] = 1.0

# Remove error column or set to None
df_clean['error'] = None

# Save cleaned CSV
df_clean.to_csv(csv_file, index=False)
print(f'\n[OK] Cleaned CSV saved: {len(df_clean)} rows')

# Clean JSON data
json_clean = []
for entry in json_data:
    # Skip failed entries
    if entry.get('success') in [True, 1.0, '1.0']:
        # Fix data types
        for key in numeric_columns:
            if key in entry and entry[key] is not None:
                try:
                    entry[key] = float(entry[key])
                except (ValueError, TypeError):
                    entry[key] = None

        entry['success'] = 1.0
        entry['error'] = None
        json_clean.append(entry)

# Save cleaned JSON
with open(json_file, 'w', encoding='utf-8') as f:
    json.dump(json_clean, f, indent=2)
print(f'[OK] Cleaned JSON saved: {len(json_clean)} entries')

print('\n=== Summary ===')
print(f'Removed {len(df) - len(df_clean)} failed entries')
print(f'Final dataset: {len(df_clean)} successful runs')
print(f'Unique contracts: {df_clean["contract_name"].nunique()}')
