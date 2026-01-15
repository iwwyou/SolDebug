# RQ1: Latency Benchmark

This directory contains the edit-trace replay scripts used to evaluate SolQDebug's debugging workflow latency.

## Quick Start

```bash
# 1. Clone the repository
git clone https://github.com/iwwyou/SolDebug.git
cd SolDebug/Evaluation/RQ1_Latency

# 2. Install dependencies (Windows)
install_dependencies.bat

# Or manually:
pip install antlr4-python3-runtime py-solc-x networkx

# 3. Run the benchmark (30 contracts)
python solqdebug_benchmark.py
```

## Main Script

### `solqdebug_benchmark.py`

Replays pre-recorded edit traces that simulate interactive debugging sessions. Evaluates 30 smart contracts and outputs latency measurements to `results/`.

## Directory Structure

```
RQ1_Latency/
├── solqdebug_benchmark.py    # Main benchmark script
├── install_dependencies.bat  # Dependency installer (Windows)
├── README.md                 # This file
├── json_intervals/           # Pre-recorded edit traces (JSON)
├── results/                  # Benchmark results (CSV)
└── ...
```

## Output

Results are saved as CSV files in `results/` with the following columns:
- `contract_name`: Name of the smart contract
- `latency_s`: Measured latency in seconds
- `success`: Whether the benchmark succeeded
