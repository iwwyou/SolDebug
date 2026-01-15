#!/usr/bin/env python3
"""
7개 focused 컨트랙트만 mutation 생성 (간단 버전)
dataset/contraction/ 의 원본 .sol 파일에서 대상 함수를 추출하여 mutation
"""
import re
from pathlib import Path

# 7개 focused contracts와 해당 함수명
CONTRACTS_INFO = {
    "GovStakingStorage_c": {
        "sol_file": "dataset/contraction/GovStakingStorage_c.sol",
        "function": "updateRewardMultiplier",
        "patterns": ["add", "sub", "mul", "div"]
    },
    "GreenHouse_c": {
        "sol_file": "dataset/contraction/GreenHouse_c.sol",
        "function": "_calculateFees",
        "patterns": ["mul", "div"]
    },
    "HubPool_c": {
        "sol_file": "dataset/contraction/HubPool_c.sol",
        "function": "_allocateLpAndProtocolFees",
        "patterns": ["add", "mul", "div"]
    },
    "Lock_c": {
        "sol_file": "dataset/contraction/Lock_c.sol",
        "function": "pending",
        "patterns": ["add", "sub", "mul", "div"]
    },
    "LockupContract_c": {
        "sol_file": "dataset/contraction/LockupContract_c.sol",
        "function": "_getReleasedAmount",
        "patterns": ["add", "sub", "mul", "div"]
    },
    "PoolKeeper_c": {
        "sol_file": "dataset/contraction/PoolKeeper_c.sol",
        "function": "keeperTip",
        "patterns": ["sub", "div"]
    },
    "ThorusBond_c": {
        "sol_file": "dataset/contraction/ThorusBond_c.sol",
        "function": "claimablePayout",
        "patterns": ["mul", "div"]
    }
}

# Mutation 함수들
def mutate_sub_to_add(code):
    """빼기(-)를 더하기(+)로 변경"""
    return re.sub(r'(\w+)\s*-\s*(\w+)', r'\1 + \2', code)

def mutate_add_to_sub(code):
    """더하기(+)를 빼기(-)로 변경"""
    return re.sub(r'(\w+)\s*\+\s*(\w+)', r'\1 - \2', code)

def mutate_swap_add_sub(code):
    """더하기와 빼기 교체"""
    temp = re.sub(r'(\w+)\s*\+\s*(\w+)', r'\1 ___PLUS___ \2', code)
    temp = re.sub(r'(\w+)\s*-\s*(\w+)', r'\1 + \2', temp)
    return re.sub(r'___PLUS___', '-', temp)

def mutate_swap_mul_div(code):
    """곱하기와 나누기 교체"""
    temp = re.sub(r'(\w+)\s*\*\s*(\w+)', r'\1 ___MUL___ \2', code)
    temp = re.sub(r'(\w+)\s*/\s*(\w+)', r'\1 * \2', temp)
    return re.sub(r'___MUL___', '/', temp)

def extract_function_code(sol_file: Path, function_name: str) -> str:
    """Extract function code from .sol file"""
    if not sol_file.exists():
        return None

    with open(sol_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Find function
    pattern = rf'function\s+{function_name}\s*\([^)]*\)[^{{]*\{{[^}}]*\}}'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(0)

    # Try with more flexible pattern
    pattern = rf'function\s+{function_name}[^{{]*\{{(?:[^{{}}]|\{{[^{{}}]*\}})*\}}'
    match = re.search(pattern, content, re.DOTALL)

    if match:
        return match.group(0)

    return None

# 출력 디렉토리
OUTPUT_DIR = Path("Evaluation/Mutated_Contracts")
OUTPUT_DIR.mkdir(exist_ok=True)

print("=" * 80)
print("7개 Focused Contract Mutation 생성 (간단 버전)")
print("=" * 80)

total_generated = 0
summary = []

for contract, info in CONTRACTS_INFO.items():
    sol_file = Path(info["sol_file"])
    function = info["function"]
    patterns = info["patterns"]

    print(f"\n[{contract}]")
    print(f"  함수: {function}")
    print(f"  패턴: {', '.join(patterns)}")

    # Extract function code
    code = extract_function_code(sol_file, function)

    if not code:
        print(f"  [FAIL] 함수 추출 실패")
        summary.append({
            'contract': contract,
            'function': function,
            'status': 'FAILED',
            'reason': 'Function not found'
        })
        continue

    print(f"  [OK] 함수 추출 성공 ({len(code)} chars)")

    mutations_generated = []

    # Apply mutations based on detected patterns
    if 'sub' in patterns or 'add' in patterns:
        # sub_to_add
        if '-' in code:
            mutated = mutate_sub_to_add(code)
            if mutated != code:
                filename = f"{contract}_{function}_sub_to_add.sol"
                with open(OUTPUT_DIR / filename, 'w', encoding='utf-8') as f:
                    f.write(mutated)
                mutations_generated.append('sub_to_add')
                total_generated += 1
                print(f"    [+] sub_to_add")

        # add_to_sub
        if '+' in code:
            mutated = mutate_add_to_sub(code)
            if mutated != code:
                filename = f"{contract}_{function}_add_to_sub.sol"
                with open(OUTPUT_DIR / filename, 'w', encoding='utf-8') as f:
                    f.write(mutated)
                mutations_generated.append('add_to_sub')
                total_generated += 1
                print(f"    [+] add_to_sub")

        # swap_add_sub
        if '+' in code and '-' in code:
            mutated = mutate_swap_add_sub(code)
            if mutated != code:
                filename = f"{contract}_{function}_swap_add_sub.sol"
                with open(OUTPUT_DIR / filename, 'w', encoding='utf-8') as f:
                    f.write(mutated)
                mutations_generated.append('swap_add_sub')
                total_generated += 1
                print(f"    [+] swap_add_sub")

    if 'mul' in patterns or 'div' in patterns:
        # swap_mul_div
        if '*' in code and '/' in code:
            mutated = mutate_swap_mul_div(code)
            if mutated != code:
                filename = f"{contract}_{function}_swap_mul_div.sol"
                with open(OUTPUT_DIR / filename, 'w', encoding='utf-8') as f:
                    f.write(mutated)
                mutations_generated.append('swap_mul_div')
                total_generated += 1
                print(f"    [+] swap_mul_div")

    # Save original as well (for has_division marker)
    if 'div' in patterns and '/' in code:
        filename = f"{contract}_{function}_original_has_division.sol"
        with open(OUTPUT_DIR / filename, 'w', encoding='utf-8') as f:
            f.write(code)
        mutations_generated.append('original_has_division')
        total_generated += 1
        print(f"    [+] original_has_division (marker)")

    summary.append({
        'contract': contract,
        'function': function,
        'mutations': mutations_generated,
        'count': len(mutations_generated),
        'status': 'OK'
    })

print(f"\n" + "=" * 80)
print("생성 완료")
print("=" * 80)

print(f"\n총 {total_generated}개 mutation 파일 생성")
print(f"출력 디렉토리: {OUTPUT_DIR.resolve()}")

# 요약 출력
print(f"\n" + "=" * 80)
print("컨트랙트별 요약")
print("=" * 80)

for s in summary:
    print(f"\n{s['contract']}")
    print(f"  함수: {s['function']}")
    print(f"  상태: {s['status']}")
    if s['status'] == 'OK':
        print(f"  생성된 mutations ({s['count']}개): {', '.join(s['mutations'])}")
    else:
        print(f"  실패 이유: {s.get('reason', 'Unknown')}")

print(f"\n" + "=" * 80)
print("다음 단계:")
print("  1. Evaluation/Mutated_Contracts/ 에서 생성된 파일 확인")
print("  2. 각 mutation이 의도한 대로 변경되었는지 검토")
print("  3. 검토 후 annotation 생성 및 실험 진행 결정")
print("=" * 80)
