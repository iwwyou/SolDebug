"""
Create 3D visualization data from 5-run mean values.
Combines SolQDebug and Remix merged results into format for plot_3d_surface.py

Usage:
    python create_3d_data.py
"""

import csv
from pathlib import Path

RESULTS_DIR = Path(__file__).parent
INTERVALS = [0, 2, 5, 10]


def load_solqdebug_means():
    """Load SolQDebug 5-run mean results."""
    data = {}  # {(contract, interval): mean_latency}
    filepath = RESULTS_DIR / "solqdebug_merged_results.csv"

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            contract = row['Contract']
            interval = int(row['Interval'])
            mean_latency = float(row['Mean_Latency_s']) if row['Mean_Latency_s'] else None
            if mean_latency:
                data[(contract, interval)] = mean_latency

    return data


def load_remix_means():
    """Load Remix 5-run mean results (interval 0 only)."""
    data = {}  # {contract: mean_latency}
    filepath = RESULTS_DIR / "remix_merged_results.csv"

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            contract = row['Contract']
            mean_latency = float(row['Mean_PureDebug_s']) if row['Mean_PureDebug_s'] else None
            if mean_latency:
                data[contract] = mean_latency

    return data


def load_byteop_counts():
    """Load ByteOp counts from Remix results."""
    data = {}  # {contract: byteop_count}

    # Try to load from first run file
    filepath = RESULTS_DIR / "remix_results_run1.csv"

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            contract = row['contract_name']
            byteop = row.get('byteop_count', '')
            if byteop:
                try:
                    data[contract] = float(byteop)
                except ValueError:
                    pass

    return data


def load_function_names():
    """Load function names from original benchmark file."""
    data = {}  # {contract: function_name}
    filepath = RESULTS_DIR / "soldebug_benchmark_results_seconds.csv"

    if not filepath.exists():
        return data

    with open(filepath, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            contract = row['Contract']
            func = row.get('Function', '')
            if func and contract not in data:
                data[contract] = func

    return data


def create_3d_data():
    """Create combined data file for 3D visualization."""
    print("Loading data sources...")

    solqdebug_means = load_solqdebug_means()
    remix_means = load_remix_means()
    byteop_counts = load_byteop_counts()
    function_names = load_function_names()

    print(f"  SolQDebug: {len(solqdebug_means)} entries")
    print(f"  Remix: {len(remix_means)} contracts")
    print(f"  ByteOp counts: {len(byteop_counts)} contracts")

    # Get all contracts from SolQDebug results
    contracts = sorted(set(c for c, _ in solqdebug_means.keys()))

    # Create output
    output_file = RESULTS_DIR / "soldebug_benchmark_results_5run_mean.csv"

    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow([
            'Contract', 'Function', 'ByteOp_Count', 'Input_Range',
            'SolQDebug_Latency_s', 'Remix_PureDebug_s'
        ])

        rows_written = 0

        for contract in contracts:
            func_name = function_names.get(contract, '')
            byteop = byteop_counts.get(contract, '')

            # Handle name variations
            if not byteop:
                # Try alternative names
                alt_names = [
                    contract.replace('_', ''),
                    contract + '_c.sol',
                    contract.replace('_c.sol', ''),
                ]
                for alt in alt_names:
                    if alt in byteop_counts:
                        byteop = byteop_counts[alt]
                        break

            remix_base = remix_means.get(contract)
            if not remix_base:
                # Try alternative names
                alt_names = [
                    contract.replace('_', ''),
                    contract + '_c.sol',
                    contract.replace('LockupContract', 'LockupContract_c.sol'),
                    contract.replace('Edentoken', 'EdenToken'),
                    contract.replace('OptimisticGrants', 'OptimisiticGrants'),
                ]
                for alt in alt_names:
                    if alt in remix_means:
                        remix_base = remix_means[alt]
                        break

            for interval in INTERVALS:
                solq_latency = solqdebug_means.get((contract, interval))

                # Calculate Remix latency for this interval
                if remix_base:
                    multiplier = interval if interval > 0 else 1
                    remix_latency = remix_base * multiplier
                else:
                    remix_latency = None

                writer.writerow([
                    contract,
                    func_name,
                    f"{byteop:.1f}" if byteop else '',
                    interval,
                    f"{solq_latency:.6f}" if solq_latency else '',
                    f"{remix_latency:.6f}" if remix_latency else ''
                ])
                rows_written += 1

    print(f"\nOutput saved to: {output_file}")
    print(f"Total rows: {rows_written}")

    return output_file


if __name__ == "__main__":
    print("=" * 60)
    print("Creating 3D Visualization Data from 5-Run Means")
    print("=" * 60)

    create_3d_data()

    print("\nDone!")
