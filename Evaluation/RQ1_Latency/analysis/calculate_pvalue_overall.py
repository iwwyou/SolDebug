"""
Calculate overall p-value for SolQDebug vs Remix comparison.
Uses contract means as samples for Wilcoxon signed-rank test.

Usage:
    python calculate_pvalue_overall.py
"""

import csv
from pathlib import Path
from scipy import stats
import numpy as np

RESULTS_DIR = Path(__file__).parent


def load_merged_results():
    """Load merged results (5-run means) for both tools."""

    # Load SolQDebug means (interval 0 only)
    solqdebug_means = {}
    filepath = RESULTS_DIR / "solqdebug_merged_results.csv"

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if int(row['Interval']) == 0 and row['Mean_Latency_s']:
                contract = row['Contract']
                solqdebug_means[contract] = float(row['Mean_Latency_s'])

    # Load Remix means
    remix_means = {}
    filepath = RESULTS_DIR / "remix_merged_results.csv"

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            if row['Mean_PureDebug_s']:
                contract = row['Contract']
                remix_means[contract] = float(row['Mean_PureDebug_s'])

    return solqdebug_means, remix_means


def main():
    print("=" * 70)
    print("Overall P-Value Calculation: SolQDebug vs Remix")
    print("=" * 70)

    solqdebug_means, remix_means = load_merged_results()

    print(f"\nSolQDebug contracts: {len(solqdebug_means)}")
    print(f"Remix contracts: {len(remix_means)}")

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
    paired_data = []

    print("\n" + "-" * 70)
    print(f"{'Contract':<35} {'SolQDebug(s)':<15} {'Remix(s)':<15}")
    print("-" * 70)

    for contract in sorted(solqdebug_means.keys()):
        solq = solqdebug_means[contract]

        # Find matching Remix
        remix_name = name_mapping.get(contract, contract)
        remix = remix_means.get(remix_name) or remix_means.get(contract)

        if remix:
            paired_data.append((contract, solq, remix))
            print(f"{contract:<35} {solq:<15.6f} {remix:<15.2f}")
        else:
            print(f"{contract:<35} {solq:<15.6f} {'(no Remix)':<15}")

    print("-" * 70)
    print(f"Matched contracts: {len(paired_data)}")

    # Extract paired values
    solq_values = [x[1] for x in paired_data]
    remix_values = [x[2] for x in paired_data]

    # Wilcoxon signed-rank test
    statistic, p_value = stats.wilcoxon(solq_values, remix_values, alternative='less')

    print("\n" + "=" * 70)
    print("STATISTICAL TEST RESULTS")
    print("=" * 70)
    print(f"Test: Wilcoxon signed-rank test (one-sided)")
    print(f"H0: SolQDebug latency >= Remix latency")
    print(f"H1: SolQDebug latency < Remix latency")
    print(f"Sample size (n): {len(paired_data)} contracts")
    print(f"Test statistic: {statistic}")
    print(f"p-value: {p_value:.2e}")

    if p_value < 0.001:
        print(f"\nResult: HIGHLY SIGNIFICANT (p < 0.001) ***")
    elif p_value < 0.01:
        print(f"\nResult: VERY SIGNIFICANT (p < 0.01) **")
    elif p_value < 0.05:
        print(f"\nResult: SIGNIFICANT (p < 0.05) *")
    else:
        print(f"\nResult: NOT SIGNIFICANT (p >= 0.05)")

    # Summary statistics
    print("\n" + "=" * 70)
    print("SUMMARY STATISTICS")
    print("=" * 70)
    print(f"SolQDebug mean: {np.mean(solq_values):.4f}s")
    print(f"SolQDebug median: {np.median(solq_values):.4f}s")
    print(f"Remix mean: {np.mean(remix_values):.2f}s")
    print(f"Remix median: {np.median(remix_values):.2f}s")
    print(f"Mean speedup: {np.mean(remix_values) / np.mean(solq_values):.1f}x")
    print(f"Median speedup: {np.median(remix_values) / np.median(solq_values):.1f}x")

    # Paper-ready statement
    print("\n" + "=" * 70)
    print("PAPER-READY STATEMENT")
    print("=" * 70)
    print(f"\"Across {len(paired_data)} smart contracts, SolQDebug demonstrated")
    print(f"significantly lower debugging workflow latency than Remix")
    print(f"(Wilcoxon signed-rank test, n={len(paired_data)}, p = {p_value:.2e}).\"")

    print("\n" + "=" * 70)
    print("P-VALUE EXPLANATION (for paper)")
    print("=" * 70)
    print("""
The p-value represents the probability of observing results at least
as extreme as the measured data, assuming the null hypothesis is true [1].
A p-value below 0.05 indicates statistical significance, meaning the
observed difference is unlikely to have occurred by chance.

[1] Wasserstein, R.L. and Lazar, N.A., 2016. The ASA statement on
    p-values: context, process, and purpose. The American Statistician,
    70(2), pp.129-133.

Alternative citation:
[1] Fisher, R.A., 1925. Statistical methods for research workers.
    Oliver and Boyd, Edinburgh.
""")

    print("=" * 70)
    print("TABLE FORMAT (for paper)")
    print("=" * 70)
    print(f"""
| Metric                  | SolQDebug      | Remix          |
|-------------------------|----------------|----------------|
| Mean Latency (s)        | {np.mean(solq_values):.3f}          | {np.mean(remix_values):.2f}          |
| Median Latency (s)      | {np.median(solq_values):.3f}          | {np.median(remix_values):.2f}          |
| Std Dev (s)             | {np.std(solq_values):.3f}          | {np.std(remix_values):.2f}          |
| n (contracts)           | {len(paired_data)}             | {len(paired_data)}             |
| p-value                 | {p_value:.2e} (Wilcoxon test)   |
""")


if __name__ == "__main__":
    main()
