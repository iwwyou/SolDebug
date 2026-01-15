#!/usr/bin/env python3
"""
Detailed visualization of RQ2 results from parsed intervals
"""
import pandas as pd
import matplotlib.pyplot as plt
import numpy as np
from pathlib import Path

# Configuration
INPUT_CSV = Path("Evaluation/RQ2_Results/rq2_detailed_intervals.csv")
OUTPUT_DIR = Path("Evaluation/RQ2_Results")

def main():
    # Load data
    df = pd.read_csv(INPUT_CSV)

    # Replace inf with NaN
    df['f90'] = df['f90'].replace([np.inf, -np.inf], np.nan)
    df['avg_width'] = df['avg_width'].replace([np.inf, -np.inf], np.nan)

    print("=" * 70)
    print("RQ2 DETAILED ANALYSIS")
    print("=" * 70)

    # Overall stats
    print(f"\nTotal experiments: {len(df)}")
    print(f"Contracts: {df['contract'].nunique()}")
    print(f"Deltas: {sorted(df['delta'].unique())}")

    # Pattern comparison
    print("\n" + "=" * 70)
    print("OVERLAP vs DIFF")
    print("=" * 70)

    for pattern in ['overlap', 'diff']:
        pattern_df = df[df['pattern'] == pattern]
        finite_df = pattern_df[pattern_df['f90'].notna()]

        print(f"\n[{pattern.upper()}]")
        print(f"  Total: {len(pattern_df)}")
        print(f"  Finite: {len(finite_df)} ({len(finite_df)/len(pattern_df)*100:.1f}%)")

        if not finite_df.empty:
            print(f"  F90 - Mean: {finite_df['f90'].mean():.2f}")
            print(f"  F90 - Median: {finite_df['f90'].median():.2f}")
            print(f"  F90 - Min: {finite_df['f90'].min():.2f}")
            print(f"  F90 - Max: {finite_df['f90'].max():.2f}")
            print(f"  Avg Width - Mean: {finite_df['avg_width'].mean():.2f}")

    # Calculate ratio
    overlap_df = df[df['pattern'] == 'overlap']
    diff_df = df[df['pattern'] == 'diff']

    overlap_finite = overlap_df[overlap_df['f90'].notna()]
    diff_finite = diff_df[diff_df['f90'].notna()]

    if not overlap_finite.empty and not diff_finite.empty:
        overlap_f90 = overlap_finite['f90'].mean()
        diff_f90 = diff_finite['f90'].mean()
        ratio = diff_f90 / overlap_f90

        print(f"\n{'=' * 70}")
        print(f"PRECISION RATIO: Diff is {ratio:.2f}x LESS precise than Overlap")
        print(f"{'=' * 70}")

    # Per-contract analysis
    print("\n" + "=" * 70)
    print("PER-CONTRACT ANALYSIS")
    print("=" * 70)

    for contract in sorted(df['contract'].unique()):
        contract_df = df[df['contract'] == contract]

        print(f"\n[{contract}]")

        for pattern in ['overlap', 'diff']:
            pattern_df = contract_df[contract_df['pattern'] == pattern]
            finite_count = len(pattern_df[pattern_df['f90'].notna()])
            total = len(pattern_df)

            print(f"  {pattern:8s}: {finite_count}/{total} finite", end="")

            if finite_count > 0:
                avg_f90 = pattern_df[pattern_df['f90'].notna()]['f90'].mean()
                print(f" (F90={avg_f90:.1f})")
            else:
                print()

    # Delta impact
    print("\n" + "=" * 70)
    print("DELTA IMPACT")
    print("=" * 70)

    for delta in sorted(df['delta'].unique()):
        delta_df = df[df['delta'] == delta]

        print(f"\n[Delta = {delta}]")

        for pattern in ['overlap', 'diff']:
            pattern_df = delta_df[delta_df['pattern'] == pattern]
            finite_count = len(pattern_df[pattern_df['f90'].notna()])
            total = len(pattern_df)

            print(f"  {pattern:8s}: {finite_count}/{total} finite", end="")

            if finite_count > 0:
                avg_f90 = pattern_df[pattern_df['f90'].notna()]['f90'].mean()
                print(f" (F90={avg_f90:.1f})")
            else:
                print()

    # Visualization
    print("\n" + "=" * 70)
    print("GENERATING VISUALIZATIONS")
    print("=" * 70)

    fig, axes = plt.subplots(2, 2, figsize=(14, 10))

    # Plot 1: Finite ratio by contract
    ax = axes[0, 0]
    contracts = sorted(df['contract'].unique())
    x = np.arange(len(contracts))
    width = 0.35

    overlap_ratios = []
    diff_ratios = []

    for contract in contracts:
        contract_df = df[df['contract'] == contract]

        overlap_contract = contract_df[contract_df['pattern'] == 'overlap']
        diff_contract = contract_df[contract_df['pattern'] == 'diff']

        overlap_ratio = len(overlap_contract[overlap_contract['f90'].notna()]) / len(overlap_contract) if len(overlap_contract) > 0 else 0
        diff_ratio = len(diff_contract[diff_contract['f90'].notna()]) / len(diff_contract) if len(diff_contract) > 0 else 0

        overlap_ratios.append(overlap_ratio)
        diff_ratios.append(diff_ratio)

    ax.bar(x - width/2, overlap_ratios, width, label='overlap', alpha=0.8, color='steelblue')
    ax.bar(x + width/2, diff_ratios, width, label='diff', alpha=0.8, color='coral')

    ax.set_xlabel('Contract', fontsize=12)
    ax.set_ylabel('Finite Ratio', fontsize=12)
    ax.set_title('Finite Interval Ratio by Contract', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(contracts, rotation=45, ha='right', fontsize=9)
    ax.legend()
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_ylim([0, 1.1])

    # Plot 2: F90 by delta
    ax = axes[0, 1]

    for pattern in ['overlap', 'diff']:
        pattern_df = df[df['pattern'] == pattern]
        grouped = pattern_df.groupby('delta')['f90'].mean()

        ax.plot(grouped.index, grouped.values, marker='o', label=pattern, linewidth=2, markersize=8)

    ax.set_xlabel('Delta (Δ)', fontsize=12)
    ax.set_ylabel('F90 (90th percentile width)', fontsize=12)
    ax.set_title('Precision vs Input Width', fontsize=14, fontweight='bold')
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3)
    ax.set_yscale('log')

    # Plot 3: Boxplot comparison
    ax = axes[1, 0]

    finite_df = df[df['f90'].notna()]

    if not finite_df.empty:
        overlap_f90 = finite_df[finite_df['pattern'] == 'overlap']['f90']
        diff_f90 = finite_df[finite_df['pattern'] == 'diff']['f90']

        bp = ax.boxplot([overlap_f90, diff_f90],
                        labels=['Overlap', 'Diff'],
                        patch_artist=True,
                        notch=True)

        colors = ['steelblue', 'coral']
        for patch, color in zip(bp['boxes'], colors):
            patch.set_facecolor(color)
            patch.set_alpha(0.7)

    ax.set_ylabel('F90', fontsize=12)
    ax.set_title('F90 Distribution Comparison', fontsize=14, fontweight='bold')
    ax.grid(True, alpha=0.3, axis='y')
    ax.set_yscale('log')

    # Plot 4: Finite count by delta
    ax = axes[1, 1]

    deltas = sorted(df['delta'].unique())
    overlap_finite = []
    diff_finite = []

    for delta in deltas:
        delta_df = df[df['delta'] == delta]

        overlap_count = len(delta_df[(delta_df['pattern'] == 'overlap') & (delta_df['f90'].notna())])
        diff_count = len(delta_df[(delta_df['pattern'] == 'diff') & (delta_df['f90'].notna())])

        overlap_finite.append(overlap_count)
        diff_finite.append(diff_count)

    x = np.arange(len(deltas))
    width = 0.35

    ax.bar(x - width/2, overlap_finite, width, label='overlap', alpha=0.8, color='steelblue')
    ax.bar(x + width/2, diff_finite, width, label='diff', alpha=0.8, color='coral')

    ax.set_xlabel('Delta (Δ)', fontsize=12)
    ax.set_ylabel('Number of Finite Results', fontsize=12)
    ax.set_title('Finite Results by Input Width', fontsize=14, fontweight='bold')
    ax.set_xticks(x)
    ax.set_xticklabels(deltas)
    ax.legend(fontsize=11)
    ax.grid(True, alpha=0.3, axis='y')

    plt.tight_layout()

    output_file = OUTPUT_DIR / "rq2_detailed_analysis.pdf"
    plt.savefig(output_file, dpi=300, bbox_inches='tight')
    print(f"\n[+] Plot saved to {output_file}")

    # Save summary table
    summary = []
    for contract in sorted(df['contract'].unique()):
        for delta in sorted(df['delta'].unique()):
            for pattern in ['overlap', 'diff']:
                row_df = df[(df['contract'] == contract) &
                           (df['delta'] == delta) &
                           (df['pattern'] == pattern)]

                if not row_df.empty:
                    row = row_df.iloc[0]
                    summary.append({
                        'contract': contract,
                        'delta': delta,
                        'pattern': pattern,
                        'finite_count': row['finite_count'],
                        'total_vars': row['total_vars'],
                        'f90': row['f90'] if pd.notna(row['f90']) else 'inf',
                        'avg_width': row['avg_width'] if pd.notna(row['avg_width']) else 'inf'
                    })

    summary_df = pd.DataFrame(summary)
    summary_file = OUTPUT_DIR / "rq2_summary_table.csv"
    summary_df.to_csv(summary_file, index=False)
    print(f"[+] Summary table saved to {summary_file}")

    print("\n" + "=" * 70)
    print("[DONE]")
    print("=" * 70)

if __name__ == "__main__":
    main()
