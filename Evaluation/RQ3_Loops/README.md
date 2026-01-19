# RQ3: Loop Analysis Benchmark

This directory contains benchmark scripts for evaluating annotation-guided adaptive widening on loop constructs.

## Quick Start

```bash
# 1. Navigate to the directory
cd SolDebug/Evaluation/RQ3_Loops

# 2. Run the benchmark
python rq3_benchmark.py
```

## Main Script

### `rq3_benchmark.py`

Evaluates loop analysis on 5 benchmark contracts with diverse loop patterns:
- **Pattern 1 (Constant-bounded):** AOC_BEP
- **Pattern 2 (Annotation-enabled):** Balancer, Core
- **Pattern 3 (Uninitialized locals):** TimeLockPool
- **Pattern 4 (Data-dependent):** AvatarArtMarketPlace

**Usage:**
```bash
python rq3_benchmark.py                      # Run all 5 contracts
python rq3_benchmark.py --contract AOC_BEP   # Specific contract
python rq3_benchmark.py --run-id 2           # Specify run ID
python rq3_benchmark.py --verbose            # Detailed output
```

## Output

Results are saved as CSV files in `results/` with the following columns:
- `contract_name`: Name of the smart contract
- `function`: Target function containing the loop
- `pattern`: Loop pattern category
- `latency_s`: Measured latency in seconds
- `success`: Whether the benchmark succeeded
