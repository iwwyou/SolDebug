#!/usr/bin/env python3
"""
Generate visualization charts for Z3 experiment results
"""
import pandas as pd
import matplotlib.pyplot as plt
import matplotlib
matplotlib.use('Agg')  # Non-interactive backend

# Load Z3 results
z3_results = pd.read_csv("Evaluation/RQ2_Z3_Results/rq2_z3_results.csv")

# Create figure with subplots
fig, axes = plt.subplots(2, 2, figsize=(14, 10))
fig.suptitle('Z3-Based RQ2 Experiment Results', fontsize=16, fontweight='bold')

# 1. Finite ratio by contract
ax1 = axes[0, 0]
contracts = z3_results.groupby('contract').agg({
    'finite_count': 'sum',
    'num_intervals': 'sum'
}).reset_index()
contracts['finite_ratio'] = contracts['finite_count'] / contracts['num_intervals']
contracts = contracts.sort_values('finite_ratio', ascending=True)

ax1.barh(contracts['contract'], contracts['finite_ratio'] * 100, color='steelblue')
ax1.set_xlabel('Finite Ratio (%)', fontweight='bold')
ax1.set_title('Convergence Rate by Contract', fontweight='bold')
ax1.set_xlim([0, 105])
ax1.grid(axis='x', alpha=0.3)

for i, (contract, ratio) in enumerate(zip(contracts['contract'], contracts['finite_ratio'])):
    ax1.text(ratio * 100 + 2, i, f'{ratio*100:.0f}%', va='center')

# 2. Pattern comparison
ax2 = axes[0, 1]
pattern_stats = z3_results.groupby('pattern').agg({
    'finite_count': 'sum',
    'num_intervals': 'sum'
}).reset_index()
pattern_stats['finite_ratio'] = pattern_stats['finite_count'] / pattern_stats['num_intervals']

colors = ['#66c2a5', '#fc8d62']
bars = ax2.bar(pattern_stats['pattern'], pattern_stats['finite_ratio'] * 100, color=colors)
ax2.set_ylabel('Finite Ratio (%)', fontweight='bold')
ax2.set_title('Overlap vs Diff Pattern', fontweight='bold')
ax2.set_ylim([0, 105])
ax2.grid(axis='y', alpha=0.3)

for bar, ratio in zip(bars, pattern_stats['finite_ratio']):
    height = bar.get_height()
    ax2.text(bar.get_x() + bar.get_width()/2., height + 2,
             f'{ratio*100:.1f}%', ha='center', va='bottom', fontweight='bold')

# 3. Delta vs finite ratio
ax3 = axes[1, 0]
delta_stats = z3_results.groupby(['delta', 'pattern']).agg({
    'finite_count': 'sum',
    'num_intervals': 'sum'
}).reset_index()
delta_stats['finite_ratio'] = delta_stats['finite_count'] / delta_stats['num_intervals']

for pattern in ['overlap', 'diff']:
    data = delta_stats[delta_stats['pattern'] == pattern]
    ax3.plot(data['delta'], data['finite_ratio'] * 100, marker='o',
             label=pattern.capitalize(), linewidth=2, markersize=8)

ax3.set_xlabel('Delta (Δ)', fontweight='bold')
ax3.set_ylabel('Finite Ratio (%)', fontweight='bold')
ax3.set_title('Convergence vs Interval Width', fontweight='bold')
ax3.legend()
ax3.grid(alpha=0.3)
ax3.set_ylim([0, 105])

# 4. Execution time by contract
ax4 = axes[1, 1]
time_stats = z3_results.groupby('contract')['execution_time'].mean().sort_values()

ax4.barh(time_stats.index, time_stats.values, color='coral')
ax4.set_xlabel('Avg Execution Time (s)', fontweight='bold')
ax4.set_title('Performance by Contract', fontweight='bold')
ax4.grid(axis='x', alpha=0.3)

for i, (contract, time) in enumerate(zip(time_stats.index, time_stats.values)):
    ax4.text(time + 0.01, i, f'{time:.2f}s', va='center')

plt.tight_layout()
plt.savefig('Evaluation/RQ2_Z3_Results/z3_results_visualization.png', dpi=150, bbox_inches='tight')
print("[SAVED] Evaluation/RQ2_Z3_Results/z3_results_visualization.png")

# Create detailed per-contract comparison
fig2, axes2 = plt.subplots(2, 4, figsize=(16, 8))
fig2.suptitle('Per-Contract Pattern Comparison (Z3)', fontsize=14, fontweight='bold')

contracts_list = z3_results['contract'].unique()
for idx, contract in enumerate(contracts_list):
    row = idx // 4
    col = idx % 4
    ax = axes2[row, col]

    contract_data = z3_results[z3_results['contract'] == contract]
    pattern_stats = contract_data.groupby('pattern').agg({
        'finite_count': 'sum',
        'num_intervals': 'sum'
    }).reset_index()
    pattern_stats['finite_ratio'] = pattern_stats['finite_count'] / pattern_stats['num_intervals']

    bars = ax.bar(pattern_stats['pattern'], pattern_stats['finite_ratio'] * 100,
                   color=['#66c2a5', '#fc8d62'])
    ax.set_title(contract.replace('_c', ''), fontsize=10, fontweight='bold')
    ax.set_ylim([0, 105])
    ax.set_ylabel('Finite %', fontsize=8)
    ax.grid(axis='y', alpha=0.3)

    for bar, ratio in zip(bars, pattern_stats['finite_ratio']):
        height = bar.get_height()
        ax.text(bar.get_x() + bar.get_width()/2., height + 2,
                f'{ratio*100:.0f}%', ha='center', va='bottom', fontsize=8)

# Remove empty subplot
fig2.delaxes(axes2[1, 3])

plt.tight_layout()
plt.savefig('Evaluation/RQ2_Z3_Results/z3_per_contract_comparison.png', dpi=150, bbox_inches='tight')
print("[SAVED] Evaluation/RQ2_Z3_Results/z3_per_contract_comparison.png")

# Print summary statistics
print("\n" + "=" * 60)
print("Z3 EXPERIMENT SUMMARY STATISTICS")
print("=" * 60)

total_experiments = len(z3_results)
successful = z3_results['success'].sum()
total_intervals = z3_results['num_intervals'].sum()
total_finite = z3_results['finite_count'].sum()

print(f"\nTotal experiments: {total_experiments}")
print(f"Successful: {successful}/{total_experiments} ({successful/total_experiments*100:.1f}%)")
print(f"\nTotal intervals analyzed: {total_intervals}")
print(f"Finite intervals: {total_finite}/{total_intervals} ({total_finite/total_intervals*100:.1f}%)")
print(f"Infinite intervals: {total_intervals - total_finite}/{total_intervals} ({(total_intervals-total_finite)/total_intervals*100:.1f}%)")

print(f"\nAvg execution time: {z3_results['execution_time'].mean():.3f}s")
print(f"Total execution time: {z3_results['execution_time'].sum():.2f}s")

print("\n" + "=" * 60)
print("DONE")
print("=" * 60)
