# RQ2: Annotation Precision Benchmark

This directory contains benchmark scripts for evaluating annotation pattern precision on arithmetic operations.

## Quick Start

```bash
# 1. Navigate to the directory
cd SolDebug/Evaluation/RQ2_Precision

# 2. Run the benchmark
python rq2_benchmark.py
```

## Main Script

### `rq2_benchmark.py`

Evaluates overlapping vs. differential annotation patterns on the Lock.sol contract with varying interval widths (delta = 1, 3, 6, 10, 15).

**Usage:**
```bash
python rq2_benchmark.py                    # Run all configurations
python rq2_benchmark.py --delta 3          # Specific delta value
python rq2_benchmark.py --pattern overlap  # Specific pattern only
python rq2_benchmark.py --run-id 2         # Specify run ID
```

## Output

Results are saved as CSV files in `results/` with the following columns:
- `pattern`: Annotation pattern (overlap or diff)
- `delta`: Interval width parameter
- `computed_interval`: Resulting interval from analysis
- `interval_width`: Width of the computed interval
- `latency_s`: Measured latency in seconds
