# RQ2 Extended Experiment Framework

## Overview

This framework extends the original RQ2 experiment (Lock.sol) to **all contracts in dataset/contraction** with complex arithmetic operations. The goal is to investigate how **operator mutations** and **interval annotation structure** (overlap vs diff) affect interval analysis precision across diverse arithmetic patterns.

---

## Generated Artifacts

### 1. Analysis Results
- **`complex_arithmetic_patterns.json`**: Identified 23 complex arithmetic expressions across 12 contracts
  - Total operators: 13 (GovStakingStorage_c, most complex) to 2 (simpler cases)
  - Mutation types: `swap_add_sub`, `add_to_sub`, `sub_to_add`, `swap_mul_div`, `has_division`

### 2. Experiment Test Cases
- **Directory**: `Evaluation/RQ2_Extended_v2/`
- **Total experiments**: 480 test cases
- **Format**: `{Contract}_{Function}_{Mutation}_d{Delta}_{Pattern}.json`
  - Delta (Δ): 1, 3, 6, 10, 15 (interval width)
  - Pattern: `overlap` (ranges overlap), `diff` (disjoint ranges)

### 3. Experiment Index
- **File**: `RQ2_Extended_v2/experiment_index.json`
- Contains metadata for all 480 experiments

---

## Experiment Coverage

| Contract | Function | Variables | Mutation Types | Test Cases |
|----------|----------|-----------|----------------|------------|
| GovStakingStorage_c | updateRewardMultiplier | 9 (2 SV, 7 LV) | 5 types | 130 |
| GreenHouse_c | _calculateFees | 1 (LV) | 3 types | 60 |
| Lock_c | pending | 7 (1 GV, 6 SV) | 1 type | 10 |
| Dai_c | transferFrom | 6 (3 SV, 3 LV) | 2 types | 40 |
| HubPool_c | _allocateLpAndProtocolFees | 6 (4 SV, 2 LV) | 2 types | 20 |
| ... | ... | ... | ... | ... |

**Total**: 11 contracts, 11 functions, 480 experiments

---

## Annotation Format

Each experiment generates a JSON annotation file with format:

```json
[
  {
    "code": "// @Debugging BEGIN",
    "startLine": N,
    "endLine": N,
    "event": "add"
  },
  {
    "code": "// @GlobalVar variable = [low, high];",
    "startLine": N+1,
    "endLine": N+1,
    "event": "add"
  },
  {
    "code": "// @StateVar variable = [low, high];",
    ...
  },
  {
    "code": "// @LocalVar variable = [low, high];",
    ...
  },
  {
    "code": "// @Debugging END",
    ...
  }
]
```

### Interval Generation Strategy

**Overlap Pattern** (all variables in similar range):
```
var1 = [100, 100+Δ]
var2 = [100, 100+Δ]
var3 = [100, 100+Δ]
...
```

**Diff Pattern** (disjoint ranges):
```
var1 = [100, 100+Δ]
var2 = [126, 126+Δ]
var3 = [152, 152+Δ]
...
```
(Gap = 20 between ranges)

---

## Experimental Variables

### Independent Variables
1. **Operator Mutation Type**:
   - `sub_to_add`: Change subtraction to addition
   - `add_to_sub`: Change addition to subtraction
   - `swap_add_sub`: Swap + and -
   - `swap_mul_div`: Swap * and /
   - `has_division`: Test division normalization patterns

2. **Interval Width (Δ)**: 1, 3, 6, 10, 15

3. **Annotation Pattern**: `overlap` vs `diff`

### Dependent Variables (to measure)
- Interval width of output variables
- Precision degradation (F90 - 90th percentile inflation)
- Whether intervals remain finite
- Analysis time/responsiveness

---

## Next Steps: Running Experiments

### Step 1: Operator Mutation
For each experiment, create a mutated version of the contract:

**Example: Lock_c, pending(), sub_to_add**
```solidity
// Original:
uint256 _totalLockRemain = _data.total - _data.unlockedAmounts - _data.pending;

// Mutated (sub_to_add):
uint256 _totalLockRemain = _data.total + _data.unlockedAmounts + _data.pending;
```

**Options**:
1. Manual mutation (original Lock experiment approach)
2. Automated AST-based mutation (recommended for 480 experiments)

### Step 2: Run SolQDebug
For each mutated contract + annotation JSON:

```bash
# Pseudo-command (adjust to your actual tool)
soldebug analyze \
  --contract dataset/contraction/{Contract}_mutated.sol \
  --annotation RQ2_Extended_v2/{Contract}_{Function}_{Mutation}_d{Delta}_{Pattern}.json \
  --output results/{experiment_id}.json
```

### Step 3: Collect Results
Parse SolQDebug output to extract:
- Output interval ranges for key variables
- Precision metrics (F90, interval width)
- Execution time

### Step 4: Analysis
Generate CSV similar to `pending_convert_result.csv`:

| Contract | Function | Mutation | Delta | Pattern | Output_Low | Output_High | Width | Finite | F90 |
|----------|----------|----------|-------|---------|------------|-------------|-------|--------|-----|
| Lock_c   | pending  | sub_to_add | 3   | overlap | 100 | 150 | 50 | True | 2.5 |
| ...      | ...      | ...      | ... | ...     | ... | ... | ... | ... | ... |

Then run `rq2_make_and_plot.py` style analysis.

---

## Research Questions

### RQ2.1: Operator Sensitivity
**Does interval annotation structure affect precision differently for different operator mutations?**

Hypothesis: Addition-heavy mutations may be less sensitive to annotation structure than subtraction-heavy ones.

### RQ2.2: Arithmetic Pattern Generalization
**Does the Lock.sol finding (overlap > diff for precision) generalize to other arithmetic patterns?**

Test across:
- Time normalization (Lock_c, LockupContract_c)
- Fee calculation (GreenHouse_c, HubPool_c)
- Complex multi-operator expressions (GovStakingStorage_c)

### RQ2.3: Complexity vs Sensitivity
**Do more complex arithmetic expressions show higher sensitivity to annotation structure?**

Compare F90 variance across:
- Simple (2-3 operators)
- Medium (4-6 operators)
- Complex (7+ operators, like GovStakingStorage_c)

---

## File Structure

```
Evaluation/
├── analyze_complex_arithmetic.py          # Step 1: Find complex patterns
├── generate_rq2_with_targets.py           # Step 2: Generate test cases
├── run_rq2_batch.py                       # Step 3: Batch execution (TODO)
├── complex_arithmetic_patterns.json       # Analysis output
├── annotation_targets.json                # Parsed from xlsx
├── RQ2_Extended_v2/
│   ├── experiment_index.json              # Master index
│   └── *.json (480 files)                 # Annotation files
└── RQ2_EXPERIMENT_README.md              # This file
```

---

## Comparison to Original RQ2

| Aspect | Original (Lock) | Extended (This) |
|--------|----------------|-----------------|
| Contracts | 1 | 11 |
| Functions | 1 (pending) | 11 |
| Mutations | 1 (sub→add) | 5 types |
| Test cases | ~20 | 480 |
| Variables/function | 7 | 1-9 (average 5) |
| Constraint solving | Z3 SAT | Heuristic ranges |

**Trade-off**: Original used Z3 to ensure semantically valid inputs. This version uses heuristic range generation for scalability. Consider adding Z3 validation for key experiments if needed.

---

## Tips for Execution

1. **Start Small**: Test framework with 1-2 contracts first (e.g., Lock_c, GreenHouse_c)

2. **Parallelize**: 480 experiments are embarrassingly parallel - use multiprocessing

3. **Mutation Automation**: Consider building an AST-based mutator:
   ```python
   def mutate_operator(sol_file, line_num, old_op, new_op):
       # Parse AST, locate operator, replace, serialize
       ...
   ```

4. **Result Validation**: Cross-check a few experiments manually to ensure correctness

5. **Incremental Analysis**: Generate intermediate plots after each contract to catch issues early

---

## Expected Insights

1. **Generalization**: Does "overlap > diff" hold across diverse patterns?

2. **Operator-Specific Strategies**: Are some operators less sensitive to annotation structure?

3. **Practical Guidelines**: "For division-heavy code, use overlap; for addition chains, structure matters less"

4. **Tool Feedback**: Can SolQDebug auto-suggest annotation structures based on detected patterns?

---

## Contact & Questions

Generated: 2025-10-29
Framework by: Claude Code
Based on: Original Lock.sol RQ2 experiment

For questions about experiment execution, refer to original Lock experiment code in:
- `Evaluation/LockTest/LockConvertTest.py`
- `Evaluation/LockTest/rq2_make_and_plot.py`
