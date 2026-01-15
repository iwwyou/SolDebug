#!/usr/bin/env python3
"""
Analyze and visualize RQ2 batch experiment results
Similar to rq2_make_and_plot.py but for extended experiments
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Configuration
RESULTS_CSV = Path("Evaluation/RQ2_Results/rq2_batch_results.csv")
OUTPUT_DIR = Path("Evaluation/RQ2_Results")
OUTPUT_SUMMARY = OUTPUT_DIR / "rq2_summary.csv"
OUTPUT_PLOT = OUTPUT_DIR / "rq2_comparison.pdf"

def load_results():
    """Load experiment results from CSV"""
    df = pd.read_csv(RESULTS_CSV)
    return df

def analyze_results(df):
    """Analyze results and generate summary"""
    print("=" * 70)
    print("RQ2 RESULTS ANALYSIS")
    print("=" * 70)

    # Filter successful experiments
    successful = df[df['success'] == True].copy()
    print(f"\nTotal experiments: {len(df)}")
    print(f"Successful: {len(successful)}")
    print(f"Failed: {len(df) - len(successful)}")

    if successful.empty:
        print("[WARNING] No successful experiments!")
        return None

    # Replace inf values with NaN for analysis
    successful['f90'] = successful['f90'].replace([np.inf, -np.inf], np.nan)
    successful['avg_width'] = successful['avg_width'].replace([np.inf, -np.inf], np.nan)

    # Group by pattern
    print("\n" + "=" * 70)
    print("PATTERN COMPARISON")
    print("=" * 70)

    for pattern in ['overlap', 'diff']:
        pattern_df = successful[successful['pattern'] == pattern]

        if not pattern_df.empty:
            finite_f90 = pattern_df[pattern_df['f90'].notna()]

            print(f"\n[{pattern.upper()}]")
            print(f"  Experiments: {len(pattern_df)}")
            print(f"  Finite F90: {len(finite_f90)} / {len(pattern_df)}")

            if not finite_f90.empty:
                print(f"  F90 - Mean: {finite_f90['f90'].mean():.2f}")
                print(f"  F90 - Median: {finite_f90['f90'].median():.2f}")
                print(f"  F90 - Min: {finite_f90['f90'].min():.2f}")
                print(f"  F90 - Max: {finite_f90['f90'].max():.2f}")

    # Compare overlap vs diff
    print("\n" + "=" * 70)
    print("OVERLAP vs DIFF")
    print("=" * 70)

    overlap = successful[successful['pattern'] == 'overlap']
    diff = successful[successful['pattern'] == 'diff']

    if not overlap.empty and not diff.empty:
        overlap_finite = overlap[overlap['f90'].notna()]
        diff_finite = diff[diff['f90'].notna()]

        if not overlap_finite.empty and not diff_finite.empty:
            overlap_f90 = overlap_finite['f90'].mean()
            diff_f90 = diff_finite['f90'].mean()

            print(f"\nF90 (Average):")
            print(f"  Overlap: {overlap_f90:.2f}")
            print(f"  Diff: {diff_f90:.2f}")
            print(f"  Ratio (diff/overlap): {diff_f90/overlap_f90:.2f}x")
            print(f"\n  => Diff is {diff_f90/overlap_f90:.2f}x less precise than Overlap")

        # Finite ratio comparison
        overlap_finite_ratio = len(overlap[overlap['f90'].notna()]) / len(overlap)
        diff_finite_ratio = len(diff[diff['f90'].notna()]) / len(diff)

        print(f"\nFinite Ratio:")
        print(f"  Overlap: {overlap_finite_ratio:.1%}")
        print(f"  Diff: {diff_finite_ratio:.1%}")

    # Per-contract analysis
    print("\n" + "=" * 70)
    print("PER-CONTRACT RESULTS")
    print("=" * 70)

    for contract in successful['contract'].unique():
        contract_df = successful[successful['contract'] == contract]

        print(f"\n[{contract}]")

        for pattern in ['overlap', 'diff']:
            pattern_df = contract_df[contract_df['pattern'] == pattern]
            finite_count = len(pattern_df[pattern_df['f90'].notna()])

            print(f"  {pattern:8s}: {finite_count}/{len(pattern_df)} finite", end="")

            if finite_count > 0:
                avg_f90 = pattern_df[pattern_df['f90'].notna()]['f90'].mean()
                print(f" (F90={avg_f90:.1f})")
            else:
                print()

    # Group by delta
    print("\n" + "=" * 70)
    print("DELTA IMPACT")
    print("=" * 70)

    summary_by_delta = successful.groupby(['delta', 'pattern']).agg({
        'f90': lambda x: x[x.notna()].mean() if x.notna().any() else np.nan,
        'finite_count': 'mean',
        'execution_time': 'mean'
    }).reset_index()

    print("\n", summary_by_delta.to_string())

    # Save summary
    summary_by_delta.to_csv(OUTPUT_SUMMARY, index=False)
    print(f"\n[+] Summary saved to {OUTPUT_SUMMARY}")

    return successful

def plot_results(df):
    """Generate visualization plots"""
    if df is None or df.empty:
        print("[WARNING] No data to plot")
        return

    # Filter for finite F90 values
    finite_df = df[df['f90'].notna()].copy()

    if finite_df.empty:
        print("[WARNING] No finite F90 values to plot")
        return

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Plot 1: F90 vs Delta (by pattern)
    ax = axes[0, 0]
    for pattern in ['overlap', 'diff']:
        pattern_df = finite_df[finite_df['pattern'] == pattern]
        grouped = pattern_df.groupby('delta')['f90'].mean()
        ax.plot(grouped.index, grouped.values, marker='o', label=pattern, linewidth=2)

    ax.set_xlabel('Delta (Δ)', fontsize=12)
    ax.set_ylabel('F90 (90th percentile width)', fontsize=12)
    ax.set_title('F90 vs Input Width', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)

    # Plot 2: Finite Ratio vs Delta
    ax = axes[0, 1]
    for pattern in ['overlap', 'diff']:
        pattern_df = df[df['pattern'] == pattern]
        grouped = pattern_df.groupby('delta').apply(
            lambda x: len(x[x['f90'].notna()]) / len(x)
        )
        ax.plot(grouped.index, grouped.values, marker='s', label=pattern, linewidth=2)

    ax.set_xlabel('Delta (Δ)', fontsize=12)
    ax.set_ylabel('Finite Ratio', fontsize=12)
    ax.set_title('Finite Interval Ratio vs Input Width', fontsize=14, fontweight='bold')
    ax.legend()
    ax.grid(True, alpha=0.3)
    ax.set_ylim([0, 1.1])

    # Plot 3: Per-contract F90 comparison
    ax = axes[1, 0]
    contracts = finite_df['contract'].unique()
    x = np.arange(len(contracts))
    width = 0.35

    overlap_vals = [finite_df[(finite_df['contract'] == c) & (finite_df['pattern'] == 'overlap')]['f90'].mean()
                    for c in contracts]
    diff_vals = [finite_df[(finite_df['contract'] == c) & (finite_df['pattern'] == 'diff')]['f90'].mean()
                 for c in contracts]

    ax.bar(x - width/2, overlap_vals, width, label='overlap', alpha=0.8)
    ax.bar(x + width/2, diff_vals, width, label='diff', alpha=0.8)

    ax.set_xlabel('Contract', fontsize=12)
    ax.set_ylabel('Average F90', fontsize=12)
    ax.set_title('F90 by Contract', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(contracts, rotation=45, ha='right')
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')

    # Plot 4: Execution time vs Delta
    ax = axes[1, 1]
    grouped = df.groupby(['delta', 'pattern'])['execution_time'].mean().unstack()
    grouped.plot(kind='bar', ax=ax, alpha=0.8)

    ax.set_xlabel('Delta (Δ)', fontsize=12)
    ax.set_ylabel('Execution Time (s)', fontsize=12)
    ax.set_title('Performance vs Input Width', fontsize=14, fontweight='bold')
    ax.legend(title='Pattern')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_xticklabels(ax.get_xticklabels(), rotation=0)

    plt.tight_layout()
    plt.savefig(OUTPUT_PLOT, dpi=300, bbox_inches='tight')
    print(f"[+] Plot saved to {OUTPUT_PLOT}")

def main():
    if not RESULTS_CSV.exists():
        print(f"[ERROR] Results file not found: {RESULTS_CSV}")
        print("Please run run_rq2_batch.py first")
        return

    # Load results
    print(f"Loading results from {RESULTS_CSV}...")
    df = load_results()

    # Analyze
    analyzed_df = analyze_results(df)

    # Plot
    if analyzed_df is not None:
        print("\nGenerating visualizations...")
        plot_results(analyzed_df)

    print("\n" + "=" * 70)
    print("[DONE] Analysis complete!")
    print("=" * 70)

if __name__ == "__main__":
    main()
