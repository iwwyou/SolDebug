#!/usr/bin/env python3
"""
RQ3: Loop Analysis Experiments

Evaluates annotation-guided adaptive widening for loop analysis on 5 benchmark contracts.
Each contract demonstrates a different loop pattern:
- Pattern 1: Constant-bounded loops (AOC_BEP)
- Pattern 2: Annotation-enabled convergence (Balancer, Core)
- Pattern 3: Uninitialized local variables (TimeLockPool)
- Pattern 4: Data-dependent accumulation (AvatarArtMarketPlace)
"""

import json
import sys
import os

# Add parent directories to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from Interpreter.Engine import simulate_inputs

# RQ3 test cases
RQ3_CONTRACTS = {
    "AOC_BEP": {
        "file": "AOC_BEP_c_annot.json",
        "function": "updateUserInfo",
        "pattern": "Pattern 1: Constant-bounded loops",
        "expected": "userInfo[account].level in [1,4]"
    },
    "Balancer": {
        "file": "Balancer_c_annot.json",
        "function": "_addActionBuilderAt",
        "pattern": "Pattern 2: Annotation-enabled convergence",
        "expected": "i in [0,1]"
    },
    "Core": {
        "file": "Core_c_annot.json",
        "function": "revokeStableMaster",
        "pattern": "Pattern 2: Annotation-enabled convergence",
        "expected": "i in [0,2]"
    },
    "TimeLockPool": {
        "file": "TimeLockPool_c_annot.json",
        "function": "getTotalDeposit",
        "pattern": "Pattern 3: Uninitialized local variables",
        "expected": "i in [0,3], total = TOP (uninitialized)"
    },
    "AvatarArtMarketPlace": {
        "file": "AvatarArtMarketPlace_c_annot.json",
        "function": "_removeFromTokens",
        "pattern": "Pattern 4: Data-dependent accumulation",
        "expected": "tokenIndex in [0,3], resultIndex widened to [0,inf]"
    }
}


def run_single_experiment(contract_name: str, annotation_file: str):
    """Run analysis on a single contract"""
    print(f"\n{'='*60}")
    print(f"Contract: {contract_name}")
    print(f"File: {annotation_file}")
    print(f"{'='*60}")

    # Load annotation file
    annotation_path = os.path.join(os.path.dirname(__file__), annotation_file)
    with open(annotation_path, 'r') as f:
        test_inputs = json.load(f)

    # Run analysis
    simulate_inputs(test_inputs)


def main():
    print("RQ3: Loop Analysis Experiments")
    print("="*60)

    # Run all experiments
    for contract_name, info in RQ3_CONTRACTS.items():
        print(f"\n{contract_name}:")
        print(f"  Function: {info['function']}")
        print(f"  Pattern: {info['pattern']}")
        print(f"  Expected: {info['expected']}")

        run_single_experiment(contract_name, info['file'])

        print("\n" + "-"*60)


if __name__ == "__main__":
    main()
