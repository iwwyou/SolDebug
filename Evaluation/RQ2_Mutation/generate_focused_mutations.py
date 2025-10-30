#!/usr/bin/env python3
"""
7개 focused 컨트랙트만 mutation 생성
"""
import pandas as pd
import re
from pathlib import Path

# 7개 focused contracts
FOCUSED_CONTRACTS = [
    "GovStakingStorage_c",
    "GreenHouse_c",
    "HubPool_c",
    "Lock_c",
    "LockupContract_c",
    "PoolKeeper_c",
    "ThorusBond_c"
]

# 데이터셋 로드
DATASET_FILE = "dataset/evaluation_Dataset.xlsx"
df = pd.read_excel(DATASET_FILE, header=1)  # Header at row 1

# 7개 컨트랙트만 필터링
df_focused = df[df['Contract'].isin(FOCUSED_CONTRACTS)].copy()

print("=" * 80)
print("7개 Focused Contract Mutation 생성")
print("=" * 80)

print(f"\n필터링 결과:")
print(f"  전체 데이터셋: {len(df)} 항목")
print(f"  Focused 컨트랙트: {len(df_focused)} 항목")
print(f"\n대상 컨트랙트:")
for contract in FOCUSED_CONTRACTS:
    count = len(df_focused[df_focused['Contract'] == contract])
    if count > 0:
        func = df_focused[df_focused['Contract'] == contract]['Function'].iloc[0]
        pattern = df_focused[df_focused['Contract'] == contract]['Complex Pattern'].iloc[0]
        print(f"  - {contract:25s} | {func:30s} | {pattern}")
    else:
        print(f"  - {contract:25s} | [데이터셋에 없음]")

# Mutation 함수들
def mutate_sub_to_add(code):
    """빼기(-)를 더하기(+)로 변경"""
    return re.sub(r'(\w+)\s*-\s*(\w+)', r'\1 + \2', code)

def mutate_add_to_sub(code):
    """더하기(+)를 빼기(-)로 변경"""
    return re.sub(r'(\w+)\s*\+\s*(\w+)', r'\1 - \2', code)

def mutate_swap_add_sub(code):
    """더하기와 빼기 교체"""
    # 임시 마커 사용
    temp = re.sub(r'(\w+)\s*\+\s*(\w+)', r'\1 ___PLUS___ \2', code)
    temp = re.sub(r'(\w+)\s*-\s*(\w+)', r'\1 + \2', temp)
    return re.sub(r'___PLUS___', '-', temp)

def mutate_swap_mul_div(code):
    """곱하기와 나누기 교체"""
    # 임시 마커 사용
    temp = re.sub(r'(\w+)\s*\*\s*(\w+)', r'\1 ___MUL___ \2', code)
    temp = re.sub(r'(\w+)\s*/\s*(\w+)', r'\1 * \2', temp)
    return re.sub(r'___MUL___', '/', temp)

def has_division(code):
    """나누기 연산이 있는지 확인"""
    return '/' in code and not '//' in code  # 주석 제외

# Mutation 정의
MUTATIONS = {
    'sub_to_add': (mutate_sub_to_add, lambda c: '-' in c),
    'add_to_sub': (mutate_add_to_sub, lambda c: '+' in c),
    'swap_add_sub': (mutate_swap_add_sub, lambda c: '+' in c and '-' in c),
    'swap_mul_div': (mutate_swap_mul_div, lambda c: '*' in c and '/' in c),
    'has_division': (lambda c: c, has_division),  # 원본 유지, 단순 표시용
}

# 출력 디렉토리
OUTPUT_DIR = Path("Evaluation/Mutated_Contracts")
OUTPUT_DIR.mkdir(exist_ok=True)

print(f"\n" + "=" * 80)
print("Mutation 생성 시작")
print("=" * 80)

total_generated = 0
mutation_summary = []

for idx, row in df_focused.iterrows():
    contract = row['Contract']
    function = row['Function']
    pattern = row['Complex Pattern']
    original_code = row['Original Function Code']

    if pd.isna(original_code):
        print(f"\n[SKIP] {contract} - 코드 없음")
        continue

    print(f"\n[{contract}] {function}")
    print(f"  패턴: {pattern}")

    generated_for_contract = []

    for mutation_name, (mutator, checker) in MUTATIONS.items():
        # 해당 mutation이 적용 가능한지 확인
        if not checker(original_code):
            continue

        # Mutation 적용
        mutated_code = mutator(original_code)

        # 원본과 동일하면 스킵
        if mutated_code == original_code and mutation_name != 'has_division':
            continue

        # 파일명 생성
        filename = f"{contract}_{function}_{mutation_name}.sol"
        filepath = OUTPUT_DIR / filename

        # 파일 저장
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(mutated_code)

        total_generated += 1
        generated_for_contract.append(mutation_name)
        print(f"    ✓ {mutation_name:20s} -> {filename}")

    mutation_summary.append({
        'contract': contract,
        'function': function,
        'pattern': pattern,
        'mutations': ', '.join(generated_for_contract),
        'count': len(generated_for_contract)
    })

print(f"\n" + "=" * 80)
print("생성 완료")
print("=" * 80)

print(f"\n총 {total_generated}개 mutation 파일 생성")
print(f"출력 디렉토리: {OUTPUT_DIR}")

# 요약 테이블
print(f"\n" + "=" * 80)
print("컨트랙트별 Mutation 요약")
print("=" * 80)

summary_df = pd.DataFrame(mutation_summary)
if len(summary_df) > 0:
    for _, row in summary_df.iterrows():
        print(f"\n{row['contract']}")
        print(f"  함수: {row['function']}")
        print(f"  패턴: {row['pattern']}")
        print(f"  Mutations ({row['count']}개): {row['mutations']}")

# CSV로 저장
summary_csv = OUTPUT_DIR.parent / "mutation_summary_focused.csv"
if len(summary_df) > 0:
    summary_df.to_csv(summary_csv, index=False, encoding='utf-8')
    print(f"\n요약 저장: {summary_csv}")

print(f"\n" + "=" * 80)
print("다음 단계:")
print("  1. Evaluation/Mutated_Contracts/ 에서 생성된 파일 확인")
print("  2. 각 mutation이 의도한 대로 변경되었는지 검토")
print("  3. 검토 후 Z3 input 생성 및 실험 진행")
print("=" * 80)
