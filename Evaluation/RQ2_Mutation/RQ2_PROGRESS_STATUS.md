# RQ2 Experiment Progress Status

**Last updated**: 2025-10-29

---

## ✅ Completed Tasks

### 1. Contract Selection ✓
**7 focused contracts** selected for RQ2 mutation analysis:
- GovStakingStorage_c
- GreenHouse_c
- HubPool_c
- Lock_c
- LockupContract_c
- PoolKeeper_c
- ThorusBond_c

### 2. Mutation Generation ✓
**25 mutated contract files** generated:
- GovStakingStorage_c: 5 mutations
- GreenHouse_c: 2 mutations
- HubPool_c: 4 mutations (fixed truncation issues)
- Lock_c: 3 mutations (fixed truncation issues)
- LockupContract_c: 5 mutations (manually created)
- PoolKeeper_c: 4 mutations (fixed truncation issues)
- ThorusBond_c: 2 mutations

**Files**: `Evaluation/Mutated_Contracts/` (25 .sol files)
**Documentation**: `MUTATION_FIX_SUMMARY.md`, `MUTATION_GENERATION_SUMMARY.md`

### 3. F90 Measurement Plan ✓
**Complete specification** for all 7 contracts:
- Exact variables to measure F90 on
- Branch coverage requirements
- Semantic constraints for Z3

**File**: `Evaluation/F90_MEASUREMENT_PLAN.md`

### 4. Z3 Constraint Design ✓
**All 7 contracts** have updated semantic constraints:
- GovStakingStorage_c: Standard constraints (passedTime < oldLockPeriod)
- GreenHouse_c: Standard constraints (amount > 0)
- **HubPool_c**: `bundleLpFees > 0` ← **NEW**
- **Lock_c**: `_data.pending > 0` ← **NEW**
- LockupContract_c: Standard constraints with branch coverage
- **PoolKeeper_c**: `timestamp >= savedPrevious + poolInterval` ← **NEW**
- ThorusBond_c: Standard constraints with branch coverage

**File**: `Evaluation/z3_rq2_focused.py`
**Documentation**: `Z3_CONSTRAINTS_UPDATE_SUMMARY.md`

### 5. Z3 SAT Input Generation ✓
**70 Z3-validated annotation files** generated:
- 7 contracts × 2 patterns (overlap/diff) × 5 deltas (1,3,6,10,15)
- 100% success rate (all SAT)
- Lock_c, PoolKeeper_c: Widened ranges to satisfy constraints
- HubPool_c: Standard ranges work

**Files**: `Evaluation/RQ2_Z3_Focused/` (70 JSON files)
**Documentation**: `Z3_INPUT_GENERATION_SUMMARY.md`

### 6. Initial Z3 Experiments ✓
**70 experiments on original contracts** completed:
- 60.7% finite convergence (170/280 intervals)
- Results saved to `Evaluation/RQ2_Z3_Results/rq2_z3_results.csv`

---

## ⏭️ Next Steps

### Step 1: Create Annotation Files for Mutated Contracts
**Goal**: Generate annotations for 25 mutated contracts using Z3 ranges

**Approach**:
1. For each mutated contract, identify the corresponding base annotation
2. Apply Z3 ranges from the 70 generated JSON files
3. Create 70 annotations per mutated contract (70 × 25 = 1,750 files)

**Script needed**: Similar to `run_z3_experiments.py` but for mutation files

**Files to create**: `Evaluation/RQ2_Mutated_Annotations/` (1,750 JSON files)

### Step 2: Run Experiments on Mutated Contracts
**Goal**: Execute interval analysis on all mutated contracts

**Total experiments**: 70 × 25 = 1,750 experiments

**For each experiment**:
1. Load mutated contract
2. Apply Z3 annotation
3. Run interval analysis
4. Extract F90 for specified variable only
5. Record convergence (finite/infinite)

**Output**: CSV file with columns:
- contract, mutation_type, pattern, delta, variable, f90_width, converged

### Step 3: Compare Original vs Mutated
**Goal**: Analyze how operator mutations affect interval precision

**Metrics to compute**:
- F90 width distribution (original vs mutated)
- Convergence rate (finite % for original vs mutated)
- Per-mutation impact (which mutations cause most imprecision?)
- Per-contract sensitivity (which contracts most affected by mutations?)

**Analysis questions**:
1. Do mutations consistently increase interval width?
2. Which mutation types cause most imprecision? (sub_to_add, swap_mul_div, etc.)
3. Do Z3 constraints help maintain precision even with mutations?
4. How does pattern (overlap vs diff) interact with mutations?

### Step 4: Create Visualizations
**Goal**: Present results clearly

**Plots to create**:
1. Box plots: F90 width by mutation type
2. Bar charts: Convergence rate by contract
3. Heatmaps: Contract × Mutation type impact
4. Line plots: F90 width by delta (original vs mutated)

---

## File Organization

### Completed Files
```
Evaluation/
├── Mutated_Contracts/           # 25 .sol files ✓
├── RQ2_Z3_Focused/              # 70 Z3 JSON annotations ✓
├── RQ2_Z3_Results/              # 70 original contract results ✓
├── F90_MEASUREMENT_PLAN.md      ✓
├── MUTATION_FIX_SUMMARY.md      ✓
├── MUTATION_GENERATION_SUMMARY.md ✓
├── Z3_CONSTRAINTS_UPDATE_SUMMARY.md ✓
├── Z3_INPUT_GENERATION_SUMMARY.md ✓
├── z3_rq2_focused.py            ✓
├── run_z3_experiments.py        ✓
└── generate_focused_mutations_v2.py ✓
```

### Files to Create
```
Evaluation/
├── RQ2_Mutated_Annotations/     # 1,750 JSON files ⏭️
├── RQ2_Mutated_Results/         # CSV results ⏭️
├── create_mutated_annotations.py ⏭️
├── run_mutated_experiments.py   ⏭️
└── analyze_mutation_impact.py   ⏭️
```

---

## Detailed Next Task

### Task: Create Annotations for Mutated Contracts

**Input**:
- `Evaluation/Mutated_Contracts/` (25 files)
- `Evaluation/RQ2_Z3_Focused/` (70 files)
- Mutation → Original contract mapping

**Process**:
For each of 25 mutated contracts:
1. Identify base contract (e.g., `Lock_c_pending_sub_to_add.sol` → `Lock_c`)
2. For each of 70 Z3 annotations for that base contract:
   - Load Z3 annotation JSON
   - Create annotation for mutated contract
   - Adjust line numbers if needed
   - Save to `RQ2_Mutated_Annotations/`

**Output**:
- 1,750 JSON annotation files
- Naming: `{contract}_{mutation}_{pattern}_d{delta}_z3.json`
- Example: `Lock_c_pending_sub_to_add_overlap_d1_z3.json`

**Script structure**:
```python
import json
from pathlib import Path

MUTATED_DIR = Path("Evaluation/Mutated_Contracts")
Z3_DIR = Path("Evaluation/RQ2_Z3_Focused")
OUTPUT_DIR = Path("Evaluation/RQ2_Mutated_Annotations")

# Mapping: mutated file → base contract
MUTATION_MAPPING = {
    "GovStakingStorage_c_updateRewardMultiplier_sub_to_add.sol": "GovStakingStorage_c",
    "Lock_c_pending_sub_to_add.sol": "Lock_c",
    # ... etc for all 25 mutations
}

for mutated_file, base_contract in MUTATION_MAPPING.items():
    # Find all Z3 annotations for this base contract
    z3_files = Z3_DIR.glob(f"{base_contract}_*.json")

    for z3_file in z3_files:
        # Load Z3 annotation
        z3_annot = json.load(open(z3_file))

        # Create annotation for mutated contract
        # (same ranges, possibly adjusted line numbers)
        mutated_annot = z3_annot.copy()

        # Save
        output_name = z3_file.stem.replace(base_contract, mutated_file.stem)
        output_path = OUTPUT_DIR / f"{output_name}.json"
        json.dump(mutated_annot, open(output_path, 'w'), indent=2)
```

---

## Estimated Completion Time

- **Annotation creation**: ~1 hour (scripting + generation)
- **Experiment execution**: ~12-24 hours (1,750 experiments)
- **Analysis**: ~2-4 hours (data processing + visualization)

**Total**: 1-2 days

---

## Key Success Metrics

1. ✓ All 25 mutations have complete code (no truncation)
2. ✓ All 70 Z3 inputs satisfy semantic constraints
3. ⏭️ All 1,750 mutated experiments complete successfully
4. ⏭️ F90 measurements available for all specified variables
5. ⏭️ Clear comparison between original and mutated precision

---

**Status**: Ready for Step 1 (Annotation creation for mutated contracts)
**Blockers**: None
**Next action**: Create `create_mutated_annotations.py` script
