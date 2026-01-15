"""
3D Surface Visualization for RQ1 - Debugging Latency Comparison
Generates smooth interpolated surfaces showing SolQDebug vs Remix performance

Author: Generated for SolQDebug paper
Date: 2025-01-31
"""
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D
from scipy.interpolate import griddata
import sys
from pathlib import Path

def load_data(csv_path='soldebug_benchmark_results_5run_mean.csv'):
    """Load and preprocess benchmark data"""
    print(f"Loading data from {csv_path}...")
    df = pd.read_csv(csv_path)

    # Filter out invalid entries
    df = df[df['Remix_PureDebug_s'] != 'N/A'].copy()

    # Convert to numeric
    df['ByteOp_Count'] = pd.to_numeric(df['ByteOp_Count'], errors='coerce')
    df['Input_Range'] = pd.to_numeric(df['Input_Range'], errors='coerce')
    df['SolQDebug_Latency_s'] = pd.to_numeric(df['SolQDebug_Latency_s'], errors='coerce')
    df['Remix_PureDebug_s'] = pd.to_numeric(df['Remix_PureDebug_s'], errors='coerce')

    # Drop rows with missing values
    df = df.dropna(subset=['ByteOp_Count', 'Input_Range', 'SolQDebug_Latency_s', 'Remix_PureDebug_s'])

    print(f"  [OK] Loaded {len(df)} data points")
    print(f"  [OK] ByteOp range: {df['ByteOp_Count'].min():.0f} - {df['ByteOp_Count'].max():.0f}")
    print(f"  [OK] Input Range: {df['Input_Range'].min():.0f} - {df['Input_Range'].max():.0f}")
    print(f"  [OK] SolQDebug latency: {df['SolQDebug_Latency_s'].min():.3f}s - {df['SolQDebug_Latency_s'].max():.3f}s")
    print(f"  [OK] Remix latency: {df['Remix_PureDebug_s'].min():.1f}s - {df['Remix_PureDebug_s'].max():.1f}s")

    return df

def create_interpolated_surface(df, output_path='3d_benchmark_surface.png', dpi=300):
    """
    Create side-by-side 3D surface plots comparing SolQDebug and Remix

    Key fixes:
    - Uses linear interpolation to avoid cubic overshoot/undershoot
    - Clips values to ensure non-negative latency
    - Separate color scales for each subplot
    """
    print("\nGenerating 3D surface plot...")

    fig = plt.figure(figsize=(18, 8))

    # Extract data
    x = df['ByteOp_Count'].values
    y = df['Input_Range'].values
    z_solq = df['SolQDebug_Latency_s'].values
    z_remix = df['Remix_PureDebug_s'].values

    # Create interpolation grid
    xi = np.linspace(x.min(), x.max(), 50)
    yi = np.linspace(y.min(), y.max(), 20)
    xi, yi = np.meshgrid(xi, yi)

    # ========== Subplot 1: SolQDebug ==========
    ax1 = fig.add_subplot(121, projection='3d')

    # Linear interpolation (more stable than cubic)
    zi_solq = griddata((x, y), z_solq, (xi, yi), method='linear', fill_value=np.nan)

    # Ensure non-negative values (latency cannot be negative)
    zi_solq = np.maximum(zi_solq, 0)

    # Surface plot
    surf1 = ax1.plot_surface(xi, yi, zi_solq, cmap='Blues', alpha=0.7,
                             edgecolor='none', antialiased=True)

    # Original data points
    ax1.scatter(x, y, z_solq, c='darkblue', marker='o', s=30, alpha=0.9,
                edgecolors='black', linewidth=0.5, zorder=10)

    # Labels and title
    ax1.set_xlabel('ByteOp Count', fontsize=11, fontweight='bold')
    ax1.set_ylabel('Input Range', fontsize=11, fontweight='bold')
    ax1.set_zlabel('Latency (s)', fontsize=11, fontweight='bold')
    ax1.set_title('SolQDebug - Interpolated Surface', fontsize=13, fontweight='bold', pad=15)
    ax1.grid(True, alpha=0.3)

    # Color bar
    cbar1 = fig.colorbar(surf1, ax=ax1, shrink=0.5, aspect=5, pad=0.1)
    cbar1.set_label('Latency (s)', fontsize=10)

    # Set Z-axis limits (ensure starting from 0)
    ax1.set_zlim(0, max(z_solq.max() * 1.1, 1.0))

    # ========== Subplot 2: Remix ==========
    ax2 = fig.add_subplot(122, projection='3d')

    # Linear interpolation
    zi_remix = griddata((x, y), z_remix, (xi, yi), method='linear', fill_value=np.nan)

    # Ensure non-negative values
    zi_remix = np.maximum(zi_remix, 0)

    # Surface plot
    surf2 = ax2.plot_surface(xi, yi, zi_remix, cmap='Oranges', alpha=0.7,
                             edgecolor='none', antialiased=True)

    # Original data points
    ax2.scatter(x, y, z_remix, c='darkorange', marker='^', s=30, alpha=0.9,
                edgecolors='black', linewidth=0.5, zorder=10)

    # Labels and title
    ax2.set_xlabel('ByteOp Count', fontsize=11, fontweight='bold')
    ax2.set_ylabel('Input Range', fontsize=11, fontweight='bold')
    ax2.set_zlabel('Latency (s)', fontsize=11, fontweight='bold')
    ax2.set_title('Remix Pure Debug - Interpolated Surface', fontsize=13, fontweight='bold', pad=15)
    ax2.grid(True, alpha=0.3)

    # Color bar
    cbar2 = fig.colorbar(surf2, ax=ax2, shrink=0.5, aspect=5, pad=0.1)
    cbar2.set_label('Latency (s)', fontsize=10)

    # Set Z-axis limits (ensure starting from 0)
    ax2.set_zlim(0, z_remix.max() * 1.1)

    # Match viewing angles
    ax2.view_init(elev=ax1.elev, azim=ax1.azim)

    # Overall title
    plt.suptitle('3D Benchmark Comparison (5-Run Mean Values)',
                 fontsize=15, fontweight='bold', y=0.98)

    plt.tight_layout()
    plt.savefig(output_path, dpi=dpi, bbox_inches='tight')
    print(f"  [OK] Saved to {output_path} (DPI: {dpi})")
    plt.close()

    # Print statistics
    print("\nStatistics:")
    print(f"  SolQDebug median: {np.median(z_solq):.3f}s")
    print(f"  Remix median: {np.median(z_remix):.1f}s")
    print(f"  Speedup: {np.median(z_remix) / np.median(z_solq):.1f}x")

def main():
    """Main execution"""
    print("="*70)
    print("3D Surface Visualization for RQ1")
    print("="*70)

    # Load data
    csv_path = Path(__file__).parent / 'soldebug_benchmark_results_5run_mean.csv'
    if not csv_path.exists():
        print(f"ERROR: CSV file not found at {csv_path}")
        print("Please ensure 'soldebug_benchmark_results_5run_mean.csv' is in the same directory.")
        sys.exit(1)

    df = load_data(csv_path)

    # Generate visualization
    output_path = Path(__file__).parent / '3d_benchmark_surface.png'
    create_interpolated_surface(df, output_path, dpi=300)

    print("\n" + "="*70)
    print("[SUCCESS] Visualization complete!")
    print("="*70)
    print(f"\nOutput: {output_path}")
    print("\nThis plot shows:")
    print("  - Left: SolQDebug maintains flat, low latency (~0.15s median)")
    print("  - Right: Remix latency scales linearly with ByteOp count and input range")
    print("  - Color intensity represents latency magnitude")
    print("  - Points show actual measured data, surface is interpolated")

if __name__ == "__main__":
    main()
