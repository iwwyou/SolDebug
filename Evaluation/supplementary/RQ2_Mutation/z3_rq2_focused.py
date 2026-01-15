#!/usr/bin/env python3
"""
Z3-based RQ2 experiment for 7 focused contracts
Similar to LockConvertTest.py but generalized
"""
import json
import itertools
from pathlib import Path
from z3 import *

# Configuration
CONTRACTS = [
    "GovStakingStorage_c",
    "GreenHouse_c",
    "HubPool_c",
    "Lock_c",
    "LockupContract_c",
    "PoolKeeper_c",
    "ThorusBond_c"
]

DELTAS = [1, 3, 6, 10, 15]
PATTERNS = ["overlap", "diff"]
MAX_TRIES = 40
OUTPUT_DIR = Path("Evaluation/RQ2_Z3_Focused")

# Contract-specific metadata (from evaluation_dataset.xlsx)
CONTRACT_METADATA = {
    "GovStakingStorage_c": {
        "function": "updateRewardMultiplier",
        "variables": [
            ("info.rewardMultiplier", "state"),
            ("totalRewardMultiplier", "state"),
            ("oldRate", "local"),
            ("newRate", "local"),
            ("passedTime", "local"),
            ("oldLockPeriod", "local"),
            ("newLockPeriod", "local"),
            ("oldAmount", "local"),
            ("newAmount", "local"),
        ],
        "constraints": lambda s, vars: [
            s.add(v > 0) for v in vars  # All positive
        ] + [
            s.add(vars[4] < vars[5]),  # passedTime < oldLockPeriod (no overflow)
        ]
    },
    "GreenHouse_c": {
        "function": "_calculateFees",
        "variables": [
            ("amount", "local"),
        ],
        "constraints": lambda s, vars: [
            s.add(vars[0] > 0),  # amount > 0
            s.add(vars[0] < 1000000),  # reasonable upper bound
        ]
    },
    "HubPool_c": {
        "function": "_allocateLpAndProtocolFees",
        "variables": [
            ("protocolFeeCapturePct", "state"),
            ("pooledTokens[l1Token].undistributedLpFees", "state"),
            ("pooledTokens[l1Token].utilizedReserves", "state"),
            ("unclaimedAccumulatedProtocolFees[l1Token]", "state"),
            ("l1Token", "local"),
            ("bundleLpFees", "local"),
        ],
        "constraints": lambda s, vars: [
            s.add(v >= 0) for v in vars  # All non-negative
        ] + [
            s.add(vars[0] <= 100),  # protocolFeeCapturePct is percentage
            s.add(vars[5] > 0),  # bundleLpFees > 0 (to ensure lpFeesCaptured > 0)
            # Branch coverage: lpFeesCaptured > 0
            # lpFeesCaptured = bundleLpFees - (bundleLpFees * protocolFeeCapturePct) / 1e18
            # Since protocolFeeCapturePct <= 100, the fraction is tiny, so bundleLpFees > 0 suffices
        ]
    },
    "Lock_c": {
        "function": "pending",
        "variables": [
            ("_data.total", "state"),
            ("_data.unlockedAmounts", "state"),
            ("_data.pending", "state"),
            ("_data.estUnlock", "state"),
            ("block.timestamp", "global"),
            ("startLock", "state"),
            ("lockedTime", "state"),
            ("unlockDuration", "state"),
        ],
        "constraints": lambda s, vars: [
            s.add(vars[3] > 0),  # estUnlock > 0
            s.add(vars[7] > 0),  # unlockDuration > 0
            s.add(vars[0] >= vars[1] + vars[2]),  # total >= unlocked + pending (no underflow)
            s.add(vars[2] > 0),  # _data.pending > 0 (to avoid [0,0])
            # Branch coverage requirements:
            # 1. _data.pending > 0: already ensured above
            # 2. _totalLockRemain > 0: ensured by total >= unlocked + pending
            # 3. block.timestamp >= startLock + lockedTime: both branches
            #    With overlap pattern, timestamp range naturally covers both sides
        ]
    },
    "LockupContract_c": {
        "function": "_getReleasedAmount",
        "variables": [
            ("block.timestamp", "global"),
            ("initialAmount", "state"),
            ("deploymentStartTime", "state"),
            ("monthsToWaitBeforeUnlock", "state"),
            ("releaseSchedule", "state"),
        ],
        "constraints": lambda s, vars: [
            s.add(vars[1] > 0),  # initialAmount > 0
            s.add(vars[3] >= 0),  # monthsToWaitBeforeUnlock >= 0
            s.add(vars[4] > 0),  # releaseSchedule > 0
            s.add(vars[0] >= vars[2]),  # timestamp >= deploymentStartTime
            # Branch coverage: releasedAmount > initialAmount
            # releasedAmount = (initialAmount / releaseSchedule) * monthsSinceUnlock
            # Condition: releasedAmount > initialAmount
            # → monthsSinceUnlock > releaseSchedule
            # With overlap pattern, ranges naturally allow both branches
        ]
    },
    "PoolKeeper_c": {
        "function": "keeperTip",
        "variables": [
            ("block.timestamp", "global"),
            ("_savedPreviousUpdatedTimestamp", "local"),
            ("_poolInterval", "local"),
        ],
        "constraints": lambda s, vars: [
            s.add(vars[1] > 0),  # _savedPreviousUpdatedTimestamp > 0
            s.add(vars[2] > 0),  # _poolInterval > 0
            s.add(vars[0] >= vars[1] + vars[2]),  # timestamp >= savedPrevious + poolInterval (no underflow)
            # Branch coverage: keeperTip > MAX_TIP (100)
            # keeperTip = BASE_TIP(5) + (TIP_DELTA_PER_BLOCK(5) * elapsedBlocksNumerator) / BLOCK_TIME(13)
            # elapsedBlocksNumerator = timestamp - (savedPrevious + poolInterval)
            # For keeperTip = 100: elapsedBlocksNumerator ≈ 247
            # With overlap/diff patterns and widening, ranges will naturally cover both branches
        ]
    },
    "ThorusBond_c": {
        "function": "claimablePayout",
        "variables": [
            ("block.timestamp", "global"),
            ("info.lastInteractionSecond", "state"),
            ("info.remainingVestingSeconds", "state"),
            ("info.remainingPayout", "state"),
        ],
        "constraints": lambda s, vars: [
            s.add(vars[2] > 0),  # remainingVestingSeconds > 0
            s.add(vars[3] >= 0),  # remainingPayout >= 0
            s.add(vars[0] >= vars[1]),  # timestamp >= lastInteraction
            # Branch coverage: secondsSinceLastInteraction > remainingVestingSeconds
            # secondsSinceLastInteraction = vars[0] - vars[1]
            # To hit both branches, we need some cases where:
            #   (vars[0] - vars[1]) > vars[2]  (true branch)
            #   (vars[0] - vars[1]) <= vars[2] (false branch)
            # This is naturally satisfied if timestamp and lastInteraction ranges overlap with remainingVestingSeconds
        ]
    },
}

TAG = {"state": "@StateVar", "global": "@GlobalVar", "local": "@LocalVar"}

def off(i, d):
    """Offset function for diff pattern"""
    base = i * (d + 20)
    return (base, base + d)

def build_ranges(contract_name: str, pat: str, d: int):
    """Build interval ranges based on pattern"""
    metadata = CONTRACT_METADATA[contract_name]
    num_vars = len(metadata["variables"])

    if pat == "overlap":
        # All variables in overlapping range
        return [(100, 100 + d) for _ in range(num_vars)]
    else:  # diff
        # Variables in disjoint ranges
        return [off(i, d) for i in range(num_vars)]

def mk_solver(contract_name: str, ranges):
    """Create Z3 solver with constraints"""
    metadata = CONTRACT_METADATA[contract_name]
    num_vars = len(metadata["variables"])

    # Create Z3 variables
    var_names = [f"v{i}" for i in range(num_vars)]
    z3_vars = [Int(name) for name in var_names]

    s = Solver()

    # Add range constraints
    for var, (lo, hi) in zip(z3_vars, ranges):
        s.add(var >= lo, var <= hi)

    # Add semantic constraints
    if "constraints" in metadata:
        metadata["constraints"](s, z3_vars)

    return s

def widen(ranges):
    """Widen ranges if SAT fails"""
    return [(lo - 10, hi + 10) for lo, hi in ranges]

def generate_annotation_json(contract_name: str, pat: str, d: int, ranges):
    """Generate annotation JSON in standard format"""
    metadata = CONTRACT_METADATA[contract_name]

    events = []
    cur_line = 1  # Will be adjusted based on actual function line

    # BEGIN marker
    events.append({
        "code": "// @Debugging BEGIN",
        "startLine": cur_line,
        "endLine": cur_line,
        "event": "add"
    })
    cur_line += 1

    # Variable annotations
    for (var_name, var_type), (lo, hi) in zip(metadata["variables"], ranges):
        tag = TAG[var_type]
        events.append({
            "code": f"// {tag} {var_name} = [{lo},{hi}];",
            "startLine": cur_line,
            "endLine": cur_line,
            "event": "add"
        })
        cur_line += 1

    # END marker
    events.append({
        "code": "// @Debugging END",
        "startLine": cur_line,
        "endLine": cur_line,
        "event": "add"
    })

    return events

def main():
    print("=" * 70)
    print("Z3-BASED RQ2 INPUT GENERATOR (7 Focused Contracts)")
    print("=" * 70)

    OUTPUT_DIR.mkdir(exist_ok=True)

    total_generated = 0
    failed = []

    for contract in CONTRACTS:
        print(f"\n[CONTRACT] {contract}")
        print("-" * 60)

        for pat, d in itertools.product(PATTERNS, DELTAS):
            print(f"  {pat:8s} Δ={d:2d}...", end=" ", flush=True)

            ranges = build_ranges(contract, pat, d)

            # Try to find SAT solution
            sat_found = False
            for attempt in range(MAX_TRIES):
                if mk_solver(contract, ranges).check() == sat:
                    sat_found = True
                    break
                ranges = widen(ranges)

            if not sat_found:
                print("[UNSAT]")
                failed.append((contract, pat, d))
                continue

            # Generate annotation JSON
            annot_json = generate_annotation_json(contract, pat, d, ranges)

            # Save
            output_file = OUTPUT_DIR / f"{contract}_{pat}_d{d}_z3.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(annot_json, f, indent=2)

            total_generated += 1

            # Show ranges
            ranges_str = ", ".join([f"[{lo},{hi}]" for lo, hi in ranges[:3]])
            print(f"[SAT] ({ranges_str}...)")

    print("\n" + "=" * 70)
    print(f"[DONE] Generated {total_generated} SAT inputs")

    if failed:
        print(f"\n[FAILED] {len(failed)} cases could not find SAT:")
        for contract, pat, d in failed:
            print(f"  - {contract} {pat} Δ={d}")

    print(f"\n[+] Output directory: {OUTPUT_DIR}")
    print("=" * 70)

if __name__ == "__main__":
    main()
