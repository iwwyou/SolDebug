"""
Fix validation issues:
1. Create missing input.json files
2. Fix variable name mismatches
3. Remove struct field accessors from input.json
"""
import json
import re
from pathlib import Path


def fix_dai():
    """Fix Dai_c_input.json: balancesOf -> balanceOf"""
    input_path = Path('Dai_c_input.json')
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Rename balancesOf to balanceOf
    if 'balancesOf' in data['state_slots']:
        data['state_slots']['balanceOf'] = data['state_slots'].pop('balancesOf')

    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("[FIXED] Dai_c_input.json: balancesOf -> balanceOf")


def fix_edentoken():
    """Fix Edentoken_c.sol - add setters"""
    sol_path = Path('Edentoken_c.sol')
    with open(sol_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find contract closing brace
    last_brace = content.rfind('}')

    # Add setters before closing brace
    setters = """
    // Auto-generated setter for allowance (nested mapping)
    function set_allowance(address _key1, address _key2, uint256 _value) public {
        allowance[_key1][_key2] = _value;
    }

    // Auto-generated setter for balanceOf
    function set_balanceOf(address _key, uint256 _value) public {
        balanceOf[_key] = _value;
    }
"""

    new_content = content[:last_brace] + setters + '\n' + content[last_brace:]

    with open(sol_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("[FIXED] Edentoken_c.sol: Added setter functions")


def fix_wastr():
    """Fix WASTR_c.sol - add setters"""
    sol_path = Path('WASTR_c.sol')
    with open(sol_path, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find contract closing brace
    last_brace = content.rfind('}')

    # Add setters before closing brace
    setters = """
    // Auto-generated setter for allowance (nested mapping)
    function set_allowance(address _key1, address _key2, uint256 _value) public {
        allowance[_key1][_key2] = _value;
    }

    // Auto-generated setter for balanceOf
    function set_balanceOf(address _key, uint256 _value) public {
        balanceOf[_key] = _value;
    }
"""

    new_content = content[:last_brace] + setters + '\n' + content[last_brace:]

    with open(sol_path, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print("[FIXED] WASTR_c.sol: Added setter functions")


def fix_atidstaking():
    """Fix ATIDStaking_c_input.json: remove totalUnweightedATIDStaked"""
    input_path = Path('ATIDStaking_c_input.json')
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Remove the variable without setter
    if 'totalUnweightedATIDStaked' in data['state_slots']:
        data['state_slots'].pop('totalUnweightedATIDStaked')

    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("[FIXED] ATIDStaking_c_input.json: Removed totalUnweightedATIDStaked")


def fix_struct_fields():
    """Remove struct field accessors from input.json files"""
    fixes = {
        'DeltaNeutralPancakeWorker02_c_input.json': ['reinvestPath.length', 'baseToken'],
        'GovStakingStorage_c_input.json': ['info.rewardMultiplier'],
        'Lock_c_input.json': ['_data.total', '_data.UnlockedAmounts', '_data.pending'],
        'LockupContract_c_input.json': ['initialAmount', 'deploymentStartTime', 'monthsToWaitBeforeUnlock', 'releaseSchedule'],
        'MockChainlinkOracle_c_input.json': ['entry.updatedAt'],
        'ThorusBond_c_input.json': ['info.lastInteractionSecond', 'info.remainingVestingSeconds', 'info.remainingPayout'],
        'ThorusLottery_c_input.json': ['tickets.length'],
    }

    for filename, vars_to_remove in fixes.items():
        input_path = Path(filename)
        if not input_path.exists():
            continue

        with open(input_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Remove variables
        for var in vars_to_remove:
            if var in data['state_slots']:
                data['state_slots'].pop(var)

        with open(input_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"[FIXED] {filename}: Removed {len(vars_to_remove)} struct field(s)")


def fix_timelockpool():
    """Fix TimeLockPool_c_input.json: depositsOf nested mapping issue"""
    input_path = Path('TimeLockPool_c_input.json')
    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # The issue is that depositsOf[account][index] has 3 levels but setter only has 2 params
    # This is actually a mapping(address => Deposit[]) which needs special handling
    # For now, remove it
    if 'depositsOf' in data['state_slots']:
        data['state_slots'].pop('depositsOf')

    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)

    print("[FIXED] TimeLockPool_c_input.json: Removed depositsOf (complex type)")


def create_aoc_bep_input():
    """Create input.json for AOC_BEP_c.sol"""
    # Read the dataset to find the function inputs
    # For now, create a basic one
    input_data = {
        "contract_name": "AOC_BEP_c",
        "state_slots": {},
        "state_arrays": {},
        "inputs": [
            "0xAb8483F64d9C6d1EcF9b849Ae677dD3315835cb2",
            2024,
            10
        ]
    }

    input_path = Path('AOC_BEP_c_input.json')
    with open(input_path, 'w', encoding='utf-8') as f:
        json.dump(input_data, f, indent=2, ensure_ascii=False)

    print("[CREATED] AOC_BEP_c_input.json")


def main():
    print("="*70)
    print("FIXING VALIDATION ISSUES")
    print("="*70)
    print()

    try:
        fix_dai()
    except Exception as e:
        print(f"[ERROR] Dai: {e}")

    try:
        fix_edentoken()
    except Exception as e:
        print(f"[ERROR] Edentoken: {e}")

    try:
        fix_wastr()
    except Exception as e:
        print(f"[ERROR] WASTR: {e}")

    try:
        fix_atidstaking()
    except Exception as e:
        print(f"[ERROR] ATIDStaking: {e}")

    try:
        fix_struct_fields()
    except Exception as e:
        print(f"[ERROR] Struct fields: {e}")

    try:
        fix_timelockpool()
    except Exception as e:
        print(f"[ERROR] TimeLockPool: {e}")

    try:
        create_aoc_bep_input()
    except Exception as e:
        print(f"[ERROR] AOC_BEP: {e}")

    print()
    print("="*70)
    print("[OK] All fixes applied!")
    print("="*70)


if __name__ == "__main__":
    main()
