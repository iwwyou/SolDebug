# SolQDebug Evaluation

This directory contains scripts and data to reproduce the experimental results from the paper.

## Overview

The evaluation consists of three research questions:

- **RQ1**: How does SolQDebug's debugging latency compare to Remix IDE?
- **RQ2**: What is the impact of annotation patterns on analysis precision?
- **RQ3**: How does SolQDebug handle loops and which patterns cause precision loss?

## Directory Structure

```
Evaluation/
├── RQ1_Latency/                    # Latency comparison experiments
├── RQ2_Mutation/                   # Annotation pattern experiments
│   └── LockTest/                   # Main RQ2 experiment (Lock.sol)
├── RQ3_Loops/                      # Loop analysis experiments
├── analyze_complex_arithmetic.py   # Complex arithmetic analysis
├── parse_analysis_log.py           # Log parser for analysis results
├── read_evaluation_dataset.py      # Dataset loader
└── run_single_experiment.py        # Single experiment runner
```

## RQ1: Debugging Latency

**Goal**: Compare debugging workflow latency between SolQDebug and Remix IDE.

### Dataset
- 30 functions from real-world contracts

### Running RQ1 Experiments

```bash
cd RQ1_Latency
install_dependencies.bat   # Install dependencies (Windows)
python solqdebug_benchmark.py
```

See [RQ1_Latency/README.md](RQ1_Latency/README.md) for details.

### Results
- **SolQDebug**: mean 0.24s, median 0.09s
- **Remix**: mean 54.62s, median 51.68s
- Statistical significance: Wilcoxon test, p < 0.001

## RQ2: Annotation Pattern Impact

**Goal**: Evaluate how annotation structure affects precision in complex arithmetic operations involving multiplication and division.

### Key Insight
Real-world smart contracts frequently use multiplication and division for computing financial quantities (rewards, fees, vesting schedules). These operations amplify interval widths due to the combinatorial nature of interval arithmetic.

### Annotation Patterns
1. **overlap (safe)**: All input variables share common base range (e.g., [100, 100+Δ])
   - Extreme products remain closer to midpoint, limiting interval expansion
2. **diff**: Input variables have disjoint ranges (e.g., [100, 100+Δ], [300, 300+Δ], [500, 500+Δ])
   - Disjoint ranges maximize distance between endpoint combinations

### Main Experiment: Lock.sol
The primary RQ2 experiment uses the `pending()` function from `Lock.sol`:

```bash
cd Evaluation/RQ2_Mutation/LockTest
python LockTest.py           # Run experiments
python rq2_make_and_plot.py  # Generate F90 plot (fig_pending_f90.pdf)
```

**Files**:
- `pending_safe_*.json`: Annotations with overlap pattern (Δ = 1, 3, 6, 10, 15)
- `pending_diff_*.json`: Annotations with diff pattern (Δ = 1, 3, 6, 10, 15)
- `rq2_precision.csv`: F90 measurement results
- `fig_pending_f90.pdf`: Figure for the paper (Figure 10)

### Expected Results
- **overlap**: F90 decreases from 12.0 → 4.8 as Δ increases (1 → 10)
- **diff**: F90 remains constant (~13-14) regardless of input width

### Additional Contracts with Similar Patterns
Similar patterns observed in:
- GovStakingStorage (reward computations)
- GreenHouse, HubPool (fee calculations)
- LockupContract (vesting schedules)
- ThorusBond (proportional payouts)

Overlapping annotations consistently yield tighter precision than disjoint ranges across these contracts.

## RQ3: Loop Analysis

**Goal**: Evaluate the effectiveness of annotation-guided adaptive widening for loop analysis.

### Benchmark Functions
Five loop-containing functions from the benchmark dataset:
- `updateUserInfo` (AOC_BEP)
- `_addActionBuilderAt` (Balancer)
- `revokeStableMaster` (Core)
- `getTotalDeposit` (TimeLockPool)
- `_removeFromTokens` (AvatarArtMarketPlace)

### Loop Patterns

**Pattern 1: Constant-Bounded Loops with Simple Updates**
- Example: AOC_BEP's `updateUserInfo` with `for (i = 1; i <= 4; i++)`
- Result: Precise interval `userInfo[account].level` ∈ [1,4]

**Pattern 2: Annotation-Enabled Convergence**
- Example: Balancer's `_addActionBuilderAt`, Core's `revokeStableMaster`
- With annotations, loop bounds become concrete, enabling precise convergence
- Result: `i = [0,1]` for Balancer, `i = [0,2]` for Core

**Pattern 3: Uninitialized Local Variables (Developer-Fixable)**
- Example: TimeLockPool's `getTotalDeposit` declares `uint256 total;` without initialization
- Result: `total` remains TOP despite precise loop bound
- Fix: Initialize `total = 0` explicitly

**Pattern 4: Data-Dependent Accumulation**
- Example: AvatarArtMarketPlace's `_removeFromTokens`
- Conditional increments based on array comparisons
- Result: Loop index precise, but `resultIndex` widened to [0,∞]

### Running RQ3 Experiments

```bash
cd Evaluation/RQ3_Loops
python run_rq3_experiments.py
```

**Files**:
- `*_c_annot.json`: Annotation files for each contract
- `run_rq3_experiments.py`: Script to run all loop analysis experiments

## Utility Scripts

### `run_single_experiment.py`
Run a single contract analysis:
```bash
python run_single_experiment.py --contract ContractName --function functionName
```

### `parse_analysis_log.py`
Parse and aggregate analysis logs:
```bash
python parse_analysis_log.py --log analysis.log --output results.csv
```

### `read_evaluation_dataset.py`
Load and inspect the benchmark dataset:
```bash
python read_evaluation_dataset.py
```

## Data Files

The evaluation uses contracts from `../dataset/dataset_all/` directory. Ensure the dataset is properly set up before running experiments.

## Reproducing Paper Results

To reproduce all results from the paper:

```bash
# RQ1: Latency comparison
cd RQ1_Latency
python solqdebug_benchmark.py

# RQ2: Annotation patterns
cd ../RQ2_Mutation/LockTest
python LockTest.py

# RQ3: Loop analysis
cd ../../RQ3_Loops
python run_rq3_experiments.py
```

## Notes

- Remix benchmarks require Remix IDE to be running locally
- Some experiments may take several hours to complete
- Results are saved in CSV format for further analysis

## Contact

For issues or questions about the evaluation:
- Open an issue on GitHub
- Contact: iwwyou@korea.ac.kr
