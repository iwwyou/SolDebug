"""
Convert benchmark results from milliseconds to seconds
"""
import pandas as pd

# Read CSV
df = pd.read_csv('Evaluation/soldebug_benchmark_results.csv')

# Convert ms to s (keep numeric precision)
def ms_to_s(val):
    if val == 'N/A':
        return val
    try:
        return f"{float(val) / 1000:.6f}"
    except:
        return val

df['SolQDebug_Latency_s'] = df['SolQDebug_Latency_ms'].apply(ms_to_s)
df['Remix_PureDebug_s'] = df['Remix_PureDebug_ms'].apply(ms_to_s)
df['Remix_Total_s'] = df['Remix_Total_ms'].apply(ms_to_s)

# Create new dataframe with seconds
df_seconds = df[['Contract', 'Function', 'ByteOp_Count', 'Input_Range',
                 'SolQDebug_Latency_s', 'Remix_PureDebug_s', 'Remix_Total_s']]

# Save
df_seconds.to_csv('Evaluation/soldebug_benchmark_results_seconds.csv', index=False)

print("Converted to seconds: Evaluation/soldebug_benchmark_results_seconds.csv")
print(f"Total rows: {len(df_seconds)}")
