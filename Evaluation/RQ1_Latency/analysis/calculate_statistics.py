"""
Calculate statistical comparison between SolQDebug and Remix.
Generates summary statistics, p-value (Wilcoxon), and Cliff's delta.

Usage:
    python calculate_statistics.py

Output:
    ../results/statistical_comparison.csv
"""

import csv
import statistics
from pathlib import Path

try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    print("Warning: scipy not installed. P-value calculation will be skipped.")
    print("Install with: pip install scipy")


RESULTS_DIR = Path(__file__).parent.parent / "results"


def load_data():
    """Load merged results (5-run means) for both tools."""

    # Load SolQDebug means (interval 0 only)
    solq_data = {}
    filepath = RESULTS_DIR / "solqdebug_merged_results.csv"

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row['Interval']) == 0 and row['Mean_Latency_s']:
                contract = row['Contract']
                solq_data[contract] = float(row['Mean_Latency_s'])

    # Load Remix means
    remix_data = {}
    filepath = RESULTS_DIR / "remix_merged_results.csv"

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Mean_PureDebug_s']:
                contract = row['Contract']
                remix_data[contract] = float(row['Mean_PureDebug_s'])

    return solq_data, remix_data


def cliffs_delta(x, y):
    """
    Calculate Cliff's delta effect size.

    Cliff's delta = (# of pairs where x > y) - (# of pairs where x < y) / (n_x * n_y)

    Interpretation:
        |δ| < 0.147: negligible
        |δ| < 0.33: small
        |δ| < 0.474: medium
        |δ| >= 0.474: large
    """
    n_x, n_y = len(x), len(y)
    more = sum(1 for xi in x for yi in y if xi > yi)
    less = sum(1 for xi in x for yi in y if xi < yi)
    return (more - less) / (n_x * n_y)


def interpret_cliffs_delta(delta):
    """Interpret Cliff's delta effect size."""
    abs_delta = abs(delta)
    if abs_delta < 0.147:
        return "negligible"
    elif abs_delta < 0.33:
        return "small"
    elif abs_delta < 0.474:
        return "medium"
    else:
        return "large"


def main():
    print("=" * 70)
    print("Statistical Comparison: SolQDebug vs Remix")
    print("=" * 70)

    solq_data, remix_data = load_data()

    # Name mapping (SolQDebug -> Remix)
    name_mapping = {
        'LockupContract': 'LockupContract_c.sol',
        'Edentoken': 'EdenToken',
        'OptimisticGrants': 'OptimisiticGrants',
        'AvatarArtMarketPlace': 'AvatarArtMarketplace',
        'CitrusToken': 'BEP20',
        'Meter_flat': 'ERC20',
    }

    # Match contracts
    paired = []
    for contract in solq_data:
        remix_name = name_mapping.get(contract, contract)
        if remix_name in remix_data:
            paired.append((contract, solq_data[contract], remix_data[remix_name]))

    solq_values = [x[1] for x in paired]
    remix_values = [x[2] for x in paired]

    n = len(paired)

    # Calculate statistics
    solq_mean = statistics.mean(solq_values)
    solq_median = statistics.median(solq_values)
    solq_std = statistics.stdev(solq_values)
    solq_min = min(solq_values)
    solq_max = max(solq_values)

    remix_mean = statistics.mean(remix_values)
    remix_median = statistics.median(remix_values)
    remix_std = statistics.stdev(remix_values)
    remix_min = min(remix_values)
    remix_max = max(remix_values)

    # Calculate Cliff's delta
    delta = cliffs_delta(solq_values, remix_values)
    delta_interpretation = interpret_cliffs_delta(delta)

    # Calculate p-value (Wilcoxon signed-rank test)
    if HAS_SCIPY:
        # Two-sided test
        stat_two, p_two = stats.wilcoxon(solq_values, remix_values, alternative='two-sided')
        # One-sided test (SolQDebug < Remix)
        stat_one, p_one = stats.wilcoxon(solq_values, remix_values, alternative='less')
    else:
        stat_two, p_two = None, None
        stat_one, p_one = None, None

    # Print results
    print(f"\nMatched contracts: {n}")
    print()
    print("-" * 70)
    print(f"{'Metric':<25} {'SolQDebug':<20} {'Remix':<20}")
    print("-" * 70)
    print(f"{'Mean (s)':<25} {solq_mean:<20.4f} {remix_mean:<20.2f}")
    print(f"{'Median (s)':<25} {solq_median:<20.4f} {remix_median:<20.2f}")
    print(f"{'Std. deviation (s)':<25} {solq_std:<20.4f} {remix_std:<20.2f}")
    print(f"{'Min (s)':<25} {solq_min:<20.4f} {remix_min:<20.2f}")
    print(f"{'Max (s)':<25} {solq_max:<20.4f} {remix_max:<20.2f}")
    print("-" * 70)

    print()
    print("=" * 70)
    print("Statistical Tests")
    print("=" * 70)
    if HAS_SCIPY:
        print(f"Wilcoxon signed-rank test (two-sided):")
        print(f"  Statistic: {stat_two}")
        print(f"  p-value: {p_two:.2e}")
        print()
        print(f"Wilcoxon signed-rank test (one-sided, H1: SolQDebug < Remix):")
        print(f"  Statistic: {stat_one}")
        print(f"  p-value: {p_one:.2e}")
    else:
        print("Wilcoxon test skipped (scipy not installed)")

    print()
    print(f"Cliff's delta: {delta:.4f} ({delta_interpretation} effect)")

    # Save to CSV
    output_path = RESULTS_DIR / "statistical_comparison.csv"

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(['Metric', 'SolQDebug', 'Remix', 'Combined'])
        writer.writerow(['Sample size (n)', n, n, n])
        writer.writerow(['Mean (s)', f'{solq_mean:.4f}', f'{remix_mean:.2f}', ''])
        writer.writerow(['Median (s)', f'{solq_median:.4f}', f'{remix_median:.2f}', ''])
        writer.writerow(['Std. deviation (s)', f'{solq_std:.4f}', f'{remix_std:.2f}', ''])
        writer.writerow(['Min (s)', f'{solq_min:.4f}', f'{remix_min:.2f}', ''])
        writer.writerow(['Max (s)', f'{solq_max:.4f}', f'{remix_max:.2f}', ''])
        writer.writerow(['Range (s)', f'{solq_min:.2f}--{solq_max:.2f}', f'{remix_min:.1f}--{remix_max:.1f}', ''])
        writer.writerow([])
        writer.writerow(['Statistical Test', '', '', 'Value'])
        if HAS_SCIPY:
            writer.writerow(['Wilcoxon p-value (two-sided)', '', '', f'{p_two:.2e}'])
            writer.writerow(['Wilcoxon p-value (one-sided)', '', '', f'{p_one:.2e}'])
        writer.writerow(['Cliffs delta', '', '', f'{delta:.4f}'])
        writer.writerow(['Effect size interpretation', '', '', delta_interpretation])

    print()
    print(f"Results saved to: {output_path}")

    # Print LaTeX table
    print()
    print("=" * 70)
    print("LaTeX Table (copy to paper)")
    print("=" * 70)
    print(r"""
\begin{table}[t]
\centering
\caption{Statistical comparison of debugging workflow latency between \textsc{SolQDebug} and Remix (interval $\Delta = 0$, 5-run means).}
\label{tab:statistical-comparison}
\begin{tabular}{lcc}
\toprule
\textbf{Metric} & \textbf{SolQDebug} & \textbf{Remix} \\
\midrule""")
    print(f"Mean latency (s) & {solq_mean:.2f} & {remix_mean:.2f} \\\\")
    print(f"Median latency (s) & {solq_median:.2f} & {remix_median:.2f} \\\\")
    print(f"Std. deviation (s) & {solq_std:.2f} & {remix_std:.2f} \\\\")
    print(f"Range (s) & {solq_min:.2f}--{solq_max:.2f} & {remix_min:.1f}--{remix_max:.1f} \\\\")
    print(r"""\midrule
\multicolumn{3}{l}{\textbf{Statistical Test}} \\
\midrule""")
    if HAS_SCIPY:
        print(f"Wilcoxon $p$-value & \\multicolumn{{2}}{{c}}{{$< 0.001$}} \\\\")
    print(f"Cliff's $\\delta$ & \\multicolumn{{2}}{{c}}{{${delta:.1f}$ ({delta_interpretation})}} \\\\")
    print(r"""\bottomrule
\end{tabular}
\end{table}
""")


if __name__ == "__main__":
    main()
