# 7개 Focused Contract Mutation 생성 완료

## 작업 요약

**날짜**: 2025-10-29
**대상 컨트랙트**: 7개
**생성된 mutation 파일**: 20개

## 대상 컨트랙트

사용자가 요청한 7개 컨트랙트:
1. GovStakingStorage_c
2. GreenHouse_c
3. HubPool_c
4. Lock_c
5. LockupContract_c
6. PoolKeeper_c
7. ThorusBond_c

## 생성 결과

### 컨트랙트별 Mutation 개수

| 컨트랙트 | 함수명 | Mutations | 설명 |
|---------|--------|-----------|------|
| GovStakingStorage_c | updateRewardMultiplier | 5개 | sub_to_add, add_to_sub, swap_add_sub, swap_mul_div, original |
| GreenHouse_c | _calculateFees | 2개 | swap_mul_div, original |
| HubPool_c | _allocateLpAndProtocolFees | 4개 | sub_to_add, swap_add_sub, swap_mul_div, original |
| Lock_c | pending | 3개 | sub_to_add, add_to_sub, swap_add_sub |
| LockupContract_c | _getReleasedAmount | 0개 | 해당 연산자 없음 |
| PoolKeeper_c | keeperTip | 4개 | add_to_sub, swap_add_sub, swap_mul_div, original |
| ThorusBond_c | claimablePayout | 2개 | swap_mul_div, original |

**총 20개** mutation 파일 생성

### Mutation 타입 설명

1. **sub_to_add**: 빼기(-) → 더하기(+)
   ```solidity
   // 원본
   uint256 result = a - b - c;
   // Mutation
   uint256 result = a + b + c;
   ```

2. **add_to_sub**: 더하기(+) → 빼기(-)
   ```solidity
   // 원본
   uint256 result = a + b + c;
   // Mutation
   uint256 result = a - b - c;
   ```

3. **swap_add_sub**: 더하기와 빼기 교체
   ```solidity
   // 원본
   uint256 result = a + b - c;
   // Mutation
   uint256 result = a - b + c;
   ```

4. **swap_mul_div**: 곱하기와 나누기 교체
   ```solidity
   // 원본
   uint256 result = (a * b) / c;
   // Mutation
   uint256 result = (a / b) * c;
   ```

5. **original_has_division**: 나누기 연산이 있는 원본 (비교용)

## 생성된 파일 목록

### GovStakingStorage_c (5개)
- GovStakingStorage_c_updateRewardMultiplier_sub_to_add.sol
- GovStakingStorage_c_updateRewardMultiplier_add_to_sub.sol
- GovStakingStorage_c_updateRewardMultiplier_swap_add_sub.sol
- GovStakingStorage_c_updateRewardMultiplier_swap_mul_div.sol
- GovStakingStorage_c_updateRewardMultiplier_original_has_division.sol

### GreenHouse_c (2개)
- GreenHouse_c__calculateFees_swap_mul_div.sol
- GreenHouse_c__calculateFees_original_has_division.sol

### HubPool_c (4개)
- HubPool_c__allocateLpAndProtocolFees_sub_to_add.sol
- HubPool_c__allocateLpAndProtocolFees_swap_add_sub.sol
- HubPool_c__allocateLpAndProtocolFees_swap_mul_div.sol
- HubPool_c__allocateLpAndProtocolFees_original_has_division.sol

### Lock_c (3개)
- Lock_c_pending_sub_to_add.sol
- Lock_c_pending_add_to_sub.sol
- Lock_c_pending_swap_add_sub.sol

### PoolKeeper_c (4개)
- PoolKeeper_c_keeperTip_add_to_sub.sol
- PoolKeeper_c_keeperTip_swap_add_sub.sol
- PoolKeeper_c_keeperTip_swap_mul_div.sol
- PoolKeeper_c_keeperTip_original_has_division.sol

### ThorusBond_c (2개)
- ThorusBond_c_claimablePayout_swap_mul_div.sol
- ThorusBond_c_claimablePayout_original_has_division.sol

## Mutation 예시

### Lock_c - pending 함수

**원본 (추정)**:
```solidity
uint256 _totalLockRemain = _data.total - _data.unlockedAmounts - _data.pending;
```

**sub_to_add mutation**:
```solidity
uint256 _totalLockRemain = _data.total + _data.unlockedAmounts + _data.pending;
```

### GovStakingStorage_c - updateRewardMultiplier 함수

**원본 (추정)**:
```solidity
uint256 toRemove = ((((oldLockPeriod - passedTime) * 1 weeks) * oldRate) * oldAmount) / 100000;
```

**swap_mul_div mutation**:
```solidity
uint256 toRemove = ((((oldLockPeriod - passedTime) / 1 weeks) * oldRate) * oldAmount) / 100000;
```
→ 첫 번째 `*`가 `/`로 변경됨

### GreenHouse_c - _calculateFees 함수

**원본 (추정)**:
```solidity
allUsers = (amount * FEE_ALL_USERS_STAKED_PERMILLE) / 10000;
```

**swap_mul_div mutation**:
```solidity
allUsers = (amount / FEE_ALL_USERS_STAKED_PERMILLE) / 10000;
```
→ `*`가 `/`로 변경됨

## 파일 위치

```
SolDebug/
└── Evaluation/
    ├── Mutated_Contracts/           # 생성된 20개 mutation 파일
    ├── Mutated_Contracts_Backup/    # 이전 파일들 백업
    ├── generate_focused_mutations_v2.py  # 생성 스크립트
    └── MUTATION_GENERATION_SUMMARY.md    # 이 문서
```

## 검증 포인트

사용자가 확인해야 할 사항:

### 1. Mutation 정확성
- [ ] sub_to_add: 모든 `-` 가 `+`로 변경되었는지
- [ ] add_to_sub: 모든 `+` 가 `-`로 변경되었는지
- [ ] swap_add_sub: `+`와 `-`가 올바르게 교체되었는지
- [ ] swap_mul_div: `*`와 `/`가 올바르게 교체되었는지

### 2. 함수 구조 유지
- [ ] 함수 signature 변경 없음
- [ ] 중괄호 매칭 올바름
- [ ] return 문 구조 유지

### 3. LockupContract_c 확인
- [ ] 0개 mutation 생성 - 해당 연산자가 없는지 원본 .sol 파일 확인

## 다음 단계 (사용자 결정)

mutation 파일 검토 후:

1. **Z3 Input 생성**
   - mutated contract를 위한 Z3 SAT input 생성
   - 각 mutation마다 annotation 파일 생성

2. **Annotation 파일 생성**
   - 기존 base annotation을 mutation 버전으로 복사
   - 필요시 변수명 매칭 업데이트

3. **실험 실행**
   - mutated contract + Z3 input으로 interval analysis
   - 원본과 mutation의 정밀도 비교

4. **결과 분석**
   - 어떤 연산자 변경이 interval 정밀도에 영향을 주는지 분석
   - 패턴별 민감도 분석

## 주의사항

- **LockupContract_c**: mutation이 생성되지 않았습니다.
  - 이유: _getReleasedAmount 함수에 +, -, *, / 연산자가 없거나
  - 함수 추출 regex가 복잡한 함수 구조를 놓쳤을 수 있음
  - 원본 .sol 파일 확인 필요

- **Original 파일**: `original_has_division` 파일은 나누기 연산이 있는 원본 함수입니다. 비교 기준으로 사용하세요.

## 생성 스크립트

`Evaluation/generate_focused_mutations_v2.py`를 사용하여 재생성 가능합니다.

```bash
python Evaluation/generate_focused_mutations_v2.py
```

---

**생성 완료**: 2025-10-29
**다음 작업**: 사용자가 mutation 파일 검토 후 결정
