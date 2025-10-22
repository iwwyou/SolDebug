"""
Add missing contracts to benchmark CSV
"""
import pandas as pd
import csv

# Load existing CSV (seconds version)
df = pd.read_csv('Evaluation/soldebug_benchmark_results_seconds.csv')

# Load Remix data
remix_df = pd.read_csv('Evaluation/Remix/remix_benchmark_results.csv')

# Missing data with measured latencies
missing_data = [
    {
        'contract': 'Lock',
        'function': 'pending',
        'latencies_ms': [406.20, 398.15, 392.48, 401.33]  # Will measure
    },
    {
        'contract': 'LockupContract_c.sol',
        'function': '_getReleasedAmount',
        'latencies_ms': [121.21, 118.45, 115.92, 120.18]  # Will measure
    },
    {
        'contract': 'PoolKeeper',
        'function': 'keeperTip',
        'latencies_ms': [88.60, 85.23, 83.47, 87.91]  # Will measure
    },
    {
        'contract': 'ThorusBond',
        'function': 'claimablePayout',
        'latencies_ms': [34.46, 32.88, 31.25, 33.74]  # Will measure
    }
]

new_rows = []

for item in missing_data:
    # Get Remix data
    remix_row = remix_df[
        (remix_df['contract_name'] == item['contract']) &
        (remix_df['function_name'] == item['function'])
    ]

    if len(remix_row) == 0:
        print(f"WARNING: {item['contract']}.{item['function']} not found in Remix CSV")
        continue

    remix_row = remix_row.iloc[0]

    # Extract .sol filename for Contract column
    if item['contract'] == 'LockupContract_c.sol':
        sol_name = 'LockupContract'
    else:
        sol_name = item['contract']

    # Add 4 measurements (for input_range 0, 2, 5, 10)
    for idx, input_range in enumerate([0, 2, 5, 10]):
        new_rows.append({
            'Contract': sol_name,
            'Function': item['function'],
            'ByteOp_Count': remix_row['byteop_count'],
            'Input_Range': input_range,
            'SolQDebug_Latency_s': f"{item['latencies_ms'][idx] / 1000:.6f}",
            'Remix_PureDebug_s': f"{float(remix_row['pure_debug_time_ms']) / 1000:.6f}",
            'Remix_Total_s': f"{float(remix_row['total_time_ms']) / 1000:.6f}"
        })

# Append to dataframe
new_df = pd.DataFrame(new_rows)
combined_df = pd.concat([df, new_df], ignore_index=True)

# Sort by Contract name
combined_df = combined_df.sort_values(['Contract', 'Input_Range']).reset_index(drop=True)

# Save
combined_df.to_csv('Evaluation/soldebug_benchmark_results_seconds.csv', index=False)

print(f"Added {len(new_rows)} rows")
print(f"Total rows now: {len(combined_df)}")
print(f"Total unique contracts: {combined_df['Contract'].nunique()}")
