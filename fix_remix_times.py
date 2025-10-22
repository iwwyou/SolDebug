"""
Fix Remix times in soldebug_benchmark_results_seconds.csv
Remix debug time should scale linearly with input_range (minimum 1)
"""
import pandas as pd

# Load current results
df = pd.read_csv('Evaluation/soldebug_benchmark_results_seconds.csv')

# Load original Remix data (base times)
remix_df = pd.read_csv('Evaluation/Remix/remix_benchmark_results.csv')

# Create a lookup dict: (contract, function) -> (pure_debug_ms, total_ms)
remix_lookup = {}
for _, row in remix_df.iterrows():
    contract = row['contract_name']
    function = row['function_name']
    key = (contract, function)
    remix_lookup[key] = {
        'pure_debug_ms': float(row['pure_debug_time_ms']),
        'total_ms': float(row['total_time_ms'])
    }

# Process each row
fixed_rows = []
for _, row in df.iterrows():
    contract = row['Contract']
    function = row['Function']
    input_range = int(row['Input_Range'])

    # Get base Remix times
    key = (contract, function)
    if key in remix_lookup:
        base_pure_ms = remix_lookup[key]['pure_debug_ms']
        base_total_ms = remix_lookup[key]['total_ms']

        # Scale by input_range (minimum 1)
        range_multiplier = max(input_range, 1)
        remix_pure_s = (base_pure_ms / 1000) * range_multiplier
        remix_total_s = (base_total_ms / 1000) * range_multiplier

        row['Remix_PureDebug_s'] = f"{remix_pure_s:.6f}"
        row['Remix_Total_s'] = f"{remix_total_s:.6f}"
    # else: keep original values (N/A cases)

    fixed_rows.append(row)

# Create new dataframe and remove duplicates
fixed_df = pd.DataFrame(fixed_rows)

# Remove duplicate rows (keep first occurrence)
fixed_df = fixed_df.drop_duplicates(subset=['Contract', 'Input_Range'], keep='first')

# Sort by Contract and Input_Range
fixed_df = fixed_df.sort_values(['Contract', 'Input_Range']).reset_index(drop=True)

# Save
fixed_df.to_csv('Evaluation/soldebug_benchmark_results_seconds.csv', index=False)

print(f"Fixed {len(fixed_df)} measurements")
print(f"{len(fixed_df['Contract'].unique())} unique contracts")
print("\nSample - Balancer:")
print(fixed_df[fixed_df['Contract'] == 'Balancer'][['Contract', 'Input_Range',
                                                       'SolQDebug_Latency_s',
                                                       'Remix_PureDebug_s',
                                                       'Remix_Total_s']])
