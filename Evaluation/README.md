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
├── analyze_complex_arithmetic.py   # Complex arithmetic analysis
├── parse_analysis_log.py           # Log parser for analysis results
├── read_evaluation_dataset.py      # Dataset loader
└── run_single_experiment.py        # Single experiment runner
```

## RQ1: Debugging Latency

**Goal**: Compare debugging latency between SolQDebug and Remix IDE across varying function complexity and input widths.

### Dataset
- 30 functions from real-world contracts
- Test-case widths: Δ ∈ {0, 2, 5, 10}
- Total: 120 measurements for SolQDebug, 30 for Remix

### Running RQ1 Experiments

```bash
cd Evaluation/RQ1_Latency
python remix_benchmark.py  # Benchmark Remix IDE (requires Remix running)
```

### Expected Results
- **SolQDebug**: 0.03-5.09 seconds (median: 0.15s)
- **Remix**: 25.1-124.6 seconds (median: 53.0s)
- SolQDebug maintains sub-second latency regardless of complexity

## RQ2: Annotation Pattern Impact

**Goal**: Evaluate how annotation structure affects precision in complex arithmetic operations.

### Annotation Patterns
1. **overlap**: All input variables share common base range (e.g., [100, 100+Δ])
2. **diff**: Input variables have disjoint ranges

### Running RQ2 Experiments

```bash
cd Evaluation/RQ2_Mutation
python run_mutation_experiments.py
```

### Expected Results
- **overlap**: Progressive precision improvement with wider inputs (F90: 12.0 → 4.8)
- **diff**: Near-constant inflation (F90 ≈ 13-14)

## RQ3: Loop Analysis

**Goal**: Identify patterns causing precision loss in loop-containing functions.

### Patterns Analyzed
1. **Bounded iterations with dependent updates**: Precise convergence
2. **Unbounded iterations**: Divergence without annotations
3. **Multiplication in loop**: Exponential interval growth
4. **Data-dependent accumulation**: Imprecise due to data dependencies

### Running RQ3 Experiments

```bash
python analyze_complex_arithmetic.py
```

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
python remix_benchmark.py

# RQ2: Annotation patterns
cd ../RQ2_Mutation
python run_mutation_experiments.py

# RQ3: Loop analysis
cd ..
python analyze_complex_arithmetic.py
```

## Notes

- Remix benchmarks require Remix IDE to be running locally
- Some experiments may take several hours to complete
- Results are saved in CSV format for further analysis

## Contact

For issues or questions about the evaluation:
- Open an issue on GitHub
- Contact: iwwyou@korea.ac.kr
