"""
3D Visualization of Benchmark Results
X: ByteOp Count, Y: Input Range, Z: Latency
Comparing SolQDebug vs Remix Pure Debug
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from matplotlib import cm

def load_data():
    """Load benchmark data"""
    df = pd.read_csv('Evaluation/soldebug_benchmark_results_seconds.csv')

    # Filter out N/A values
    df = df[df['Remix_PureDebug_s'] != 'N/A'].copy()

    # Convert to numeric
    df['ByteOp_Count'] = pd.to_numeric(df['ByteOp_Count'], errors='coerce')
    df['SolQDebug_Latency_s'] = pd.to_numeric(df['SolQDebug_Latency_s'], errors='coerce')
    df['Remix_PureDebug_s'] = pd.to_numeric(df['Remix_PureDebug_s'], errors='coerce')

    # Drop any rows with NaN
    df = df.dropna(subset=['ByteOp_Count', 'SolQDebug_Latency_s', 'Remix_PureDebug_s'])

    return df

def create_3d_scatter(df, save_path='3d_benchmark_scatter.png'):
    """
    Create 3D scatter plot (points only, no lines)
    Less cluttered, good for overview
    """
    fig = plt.figure(figsize=(14, 10))
    ax = fig.add_subplot(111, projection='3d')

    # Extract data
    x = df['ByteOp_Count'].values
    y = df['Input_Range'].values
    z_solq = df['SolQDebug_Latency_s'].values
    z_remix = df['Remix_PureDebug_s'].values

    # Plot SolQDebug
    scatter1 = ax.scatter(x, y, z_solq,
                         c='#1f77b4', marker='o', s=50, alpha=0.7,
                         label='SolQDebug', edgecolors='black', linewidth=0.5)

    # Plot Remix
    scatter2 = ax.scatter(x, y, z_remix,
                         c='#ff7f0e', marker='^', s=50, alpha=0.7,
                         label='Remix Pure Debug', edgecolors='black', linewidth=0.5)

    # Labels
    ax.set_xlabel('ByteOp Count', fontsize=12, fontweight='bold')
    ax.set_ylabel('Input Range', fontsize=12, fontweight='bold')
    ax.set_zlabel('Latency (seconds)', fontsize=12, fontweight='bold')
    ax.set_title('3D Benchmark Comparison: SolQDebug vs Remix\n(Scatter Plot)',
                 fontsize=14, fontweight='bold', pad=20)

    # Legend
    ax.legend(loc='upper left', fontsize=11)

    # Grid
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Saved scatter plot to {save_path}")
    plt.close()

def create_3d_connected(df, save_path='3d_benchmark_connected.png'):
    """
    Create 3D plot with lines connecting same contract across different input ranges
    More detailed but potentially cluttered
    """
    fig = plt.figure(figsize=(16, 12))
    ax = fig.add_subplot(111, projection='3d')

    # Group by contract
    contracts = df['Contract'].unique()

    # Use colormap for contracts
    n_contracts = len(contracts)

    for i, contract in enumerate(contracts):
        contract_df = df[df['Contract'] == contract].sort_values('Input_Range')

        if len(contract_df) == 0:
            continue

        x = contract_df['ByteOp_Count'].values
        y = contract_df['Input_Range'].values
        z_solq = contract_df['SolQDebug_Latency_s'].values
        z_remix = contract_df['Remix_PureDebug_s'].values

        # Plot SolQDebug with lines (blue tones)
        ax.plot(x, y, z_solq, color='#1f77b4', alpha=0.3, linewidth=1)
        ax.scatter(x, y, z_solq, c='#1f77b4', marker='o', s=30, alpha=0.6,
                  edgecolors='black', linewidth=0.3)

        # Plot Remix with lines (orange tones)
        ax.plot(x, y, z_remix, color='#ff7f0e', alpha=0.3, linewidth=1)
        ax.scatter(x, y, z_remix, c='#ff7f0e', marker='^', s=30, alpha=0.6,
                  edgecolors='black', linewidth=0.3)

    # Create custom legend
    from matplotlib.lines import Line2D
    legend_elements = [
        Line2D([0], [0], marker='o', color='w', label='SolQDebug',
               markerfacecolor='#1f77b4', markersize=10, markeredgecolor='black'),
        Line2D([0], [0], marker='^', color='w', label='Remix Pure Debug',
               markerfacecolor='#ff7f0e', markersize=10, markeredgecolor='black')
    ]

    # Labels
    ax.set_xlabel('ByteOp Count', fontsize=12, fontweight='bold')
    ax.set_ylabel('Input Range', fontsize=12, fontweight='bold')
    ax.set_zlabel('Latency (seconds)', fontsize=12, fontweight='bold')
    ax.set_title('3D Benchmark Comparison: SolQDebug vs Remix\n(Connected by Contract)',
                 fontsize=14, fontweight='bold', pad=20)

    # Legend
    ax.legend(handles=legend_elements, loc='upper left', fontsize=11)

    # Grid
    ax.grid(True, alpha=0.3)

    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Saved connected plot to {save_path}")
    plt.close()

def create_3d_separate_subplots(df, save_path='3d_benchmark_separate.png'):
    """
    Create two separate 3D plots side by side
    Clearer comparison, no overlapping
    """
    fig = plt.figure(figsize=(18, 8))

    # Subplot 1: SolQDebug
    ax1 = fig.add_subplot(121, projection='3d')
    x = df['ByteOp_Count'].values
    y = df['Input_Range'].values
    z_solq = df['SolQDebug_Latency_s'].values

    scatter1 = ax1.scatter(x, y, z_solq,
                          c=z_solq, cmap='Blues', marker='o', s=50,
                          alpha=0.7, edgecolors='black', linewidth=0.5)
    ax1.set_xlabel('ByteOp Count', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Input Range', fontsize=11, fontweight='bold')
    ax1.set_zlabel('Latency (s)', fontsize=11, fontweight='bold')
    ax1.set_title('SolQDebug', fontsize=13, fontweight='bold', pad=15)
    ax1.grid(True, alpha=0.3)
    fig.colorbar(scatter1, ax=ax1, shrink=0.5, aspect=5, pad=0.1)

    # Subplot 2: Remix
    ax2 = fig.add_subplot(122, projection='3d')
    z_remix = df['Remix_PureDebug_s'].values

    scatter2 = ax2.scatter(x, y, z_remix,
                          c=z_remix, cmap='Oranges', marker='^', s=50,
                          alpha=0.7, edgecolors='black', linewidth=0.5)
    ax2.set_xlabel('ByteOp Count', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Input Range', fontsize=11, fontweight='bold')
    ax2.set_zlabel('Latency (s)', fontsize=11, fontweight='bold')
    ax2.set_title('Remix Pure Debug', fontsize=13, fontweight='bold', pad=15)
    ax2.grid(True, alpha=0.3)
    fig.colorbar(scatter2, ax=ax2, shrink=0.5, aspect=5, pad=0.1)

    # Match viewing angles
    ax2.view_init(elev=ax1.elev, azim=ax1.azim)

    plt.suptitle('3D Benchmark Comparison (Side by Side)',
                 fontsize=15, fontweight='bold', y=0.98)
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Saved separate subplots to {save_path}")
    plt.close()

def create_2d_heatmap_comparison(df, save_path='2d_benchmark_heatmap.png'):
    """
    Create 2D heatmap for easier reading
    Shows ByteOp vs Input Range with latency as color
    """
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(18, 7))

    # Pivot data for heatmap
    pivot_solq = df.pivot_table(values='SolQDebug_Latency_s',
                                 index='Input_Range',
                                 columns='ByteOp_Count',
                                 aggfunc='mean')
    pivot_remix = df.pivot_table(values='Remix_PureDebug_s',
                                  index='Input_Range',
                                  columns='ByteOp_Count',
                                  aggfunc='mean')

    # SolQDebug heatmap
    im1 = ax1.imshow(pivot_solq, aspect='auto', cmap='Blues', origin='lower')
    ax1.set_xlabel('ByteOp Count Index', fontsize=12, fontweight='bold')
    ax1.set_ylabel('Input Range', fontsize=12, fontweight='bold')
    ax1.set_title('SolQDebug Latency Heatmap', fontsize=13, fontweight='bold')
    ax1.set_yticks(range(len(pivot_solq.index)))
    ax1.set_yticklabels(pivot_solq.index)
    plt.colorbar(im1, ax=ax1, label='Latency (s)')

    # Remix heatmap
    im2 = ax2.imshow(pivot_remix, aspect='auto', cmap='Oranges', origin='lower')
    ax2.set_xlabel('ByteOp Count Index', fontsize=12, fontweight='bold')
    ax2.set_ylabel('Input Range', fontsize=12, fontweight='bold')
    ax2.set_title('Remix Pure Debug Latency Heatmap', fontsize=13, fontweight='bold')
    ax2.set_yticks(range(len(pivot_remix.index)))
    ax2.set_yticklabels(pivot_remix.index)
    plt.colorbar(im2, ax=ax2, label='Latency (s)')

    plt.suptitle('2D Heatmap Comparison', fontsize=15, fontweight='bold')
    plt.tight_layout()
    plt.savefig(save_path, dpi=300, bbox_inches='tight')
    print(f"Saved 2D heatmap to {save_path}")
    plt.close()

def print_statistics(df):
    """Print summary statistics"""
    print("\n" + "="*60)
    print("BENCHMARK STATISTICS")
    print("="*60)

    print(f"\nTotal measurements: {len(df)}")
    print(f"Unique contracts: {df['Contract'].nunique()}")
    print(f"ByteOp Count range: {df['ByteOp_Count'].min():.0f} - {df['ByteOp_Count'].max():.0f}")
    print(f"Input Range values: {sorted(df['Input_Range'].unique())}")

    print("\n--- SolQDebug Latency ---")
    print(f"  Mean: {df['SolQDebug_Latency_s'].mean():.3f} s")
    print(f"  Median: {df['SolQDebug_Latency_s'].median():.3f} s")
    print(f"  Min: {df['SolQDebug_Latency_s'].min():.3f} s")
    print(f"  Max: {df['SolQDebug_Latency_s'].max():.3f} s")

    print("\n--- Remix Pure Debug Latency ---")
    print(f"  Mean: {df['Remix_PureDebug_s'].mean():.3f} s")
    print(f"  Median: {df['Remix_PureDebug_s'].median():.3f} s")
    print(f"  Min: {df['Remix_PureDebug_s'].min():.3f} s")
    print(f"  Max: {df['Remix_PureDebug_s'].max():.3f} s")

    print("\n--- Speedup (Remix / SolQDebug) ---")
    speedup = df['Remix_PureDebug_s'] / df['SolQDebug_Latency_s']
    print(f"  Mean speedup: {speedup.mean():.1f}x")
    print(f"  Median speedup: {speedup.median():.1f}x")
    print(f"  Min speedup: {speedup.min():.1f}x")
    print(f"  Max speedup: {speedup.max():.1f}x")
    print("="*60)

def main():
    """Generate all visualizations"""
    print("Loading data...")
    df = load_data()

    print_statistics(df)

    print("\nGenerating visualizations...")
    print("This may take a minute...\n")

    # Option 1: Simple scatter (recommended for overview)
    create_3d_scatter(df, 'Evaluation/3d_benchmark_scatter.png')

    # Option 2: Connected by contract (potentially cluttered but detailed)
    create_3d_connected(df, 'Evaluation/3d_benchmark_connected.png')

    # Option 3: Separate subplots (clearest comparison)
    create_3d_separate_subplots(df, 'Evaluation/3d_benchmark_separate.png')

    # Bonus: 2D heatmap (easier to read patterns)
    create_2d_heatmap_comparison(df, 'Evaluation/2d_benchmark_heatmap.png')

    print("\n" + "="*60)
    print("All visualizations generated successfully!")
    print("="*60)
    print("\nFiles created:")
    print("  1. Evaluation/3d_benchmark_scatter.png      - Simple scatter plot")
    print("  2. Evaluation/3d_benchmark_connected.png    - With connecting lines")
    print("  3. Evaluation/3d_benchmark_separate.png     - Side-by-side comparison")
    print("  4. Evaluation/2d_benchmark_heatmap.png      - 2D heatmap view")
    print("\nRecommendation:")
    print("  - For presentations: Use #3 (separate subplots) or #1 (scatter)")
    print("  - For detailed analysis: Use #2 (connected)")
    print("  - For pattern recognition: Use #4 (heatmap)")

if __name__ == "__main__":
    main()
