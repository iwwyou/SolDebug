# F90 측정 대상 변수 및 제약식 계획

## 개요
각 컨트랙트별로 mutation 실험 후 F90 precision을 측정할 **핵심 변수**와 **Z3 제약식 요구사항**을 정리합니다.

---

## 1. GovStakingStorage_c

### 연산자 변경 대상 문장
```solidity
uint256 toRemove = ((((oldLockPeriod - passedTime) / 1 weeks) * oldRate) * oldAmount) / 100000;
uint256 toAdd = (((newLockPeriod / 1 weeks) * newRate) * newAmount) / 100000;
info.rewardMultiplier = info.rewardMultiplier - toAdd - toRemove;
```

### F90 측정 변수
**`info.rewardMultiplier`**

### 이유
- `toRemove`와 `toAdd`가 모두 `info.rewardMultiplier`에 반영됨
- `totalRewardMultiplier`는 `info.rewardMultiplier`와 동일하므로 측정 불필요

### Mutation 파일
- `GovStakingStorage_c_updateRewardMultiplier_sub_to_add.sol`
- `GovStakingStorage_c_updateRewardMultiplier_add_to_sub.sol`
- `GovStakingStorage_c_updateRewardMultiplier_swap_add_sub.sol`
- `GovStakingStorage_c_updateRewardMultiplier_swap_mul_div.sol`
- `GovStakingStorage_c_updateRewardMultiplier_original_has_division.sol`

### Z3 제약식
기존 제약식 유지:
```python
s.add(vars[3] > 0)  # estUnlock > 0
s.add(vars[7] > 0)  # unlockDuration > 0
s.add(vars[0] >= vars[1] + vars[2])  # total >= unlocked + pending
```

---

## 2. GreenHouse_c

### 연산자 변경 대상 문장
```solidity
allUsers = (amount * FEE_ALL_USERS_STAKED_PERMILLE) / 10000;
bonusPool = (amount * FEE_BONUS_POOL_PERMILLE) / 10000;
partner = (amount * FEE_PARTNER_WALLET_PERMILLE) / 10000;
referral = (amount * FEE_REFERRAL_PERMILLE) / 10000;
platform = (amount * FEE_PLATFORM_WALLET_PERMILLE) / 10000;
net = amount - allUsers - bonusPool - partner - referral - platform;
```

### F90 측정 변수
**`net`**

### 이유
- `net`만 보면 위에 계산된 모든 변수들의 통합적인 결과를 볼 수 있음

### Mutation 파일
- `GreenHouse_c__calculateFees_swap_mul_div.sol`
- `GreenHouse_c__calculateFees_original_has_division.sol`

### Z3 제약식
기존 제약식 유지:
```python
s.add(vars[0] > 0)  # amount > 0
s.add(vars[0] < 1000000)  # reasonable upper bound
```

---

## 3. ThorusBond_c

### 연산자 변경 대상 문장
```solidity
uint256 secondsSinceLastInteraction = block.timestamp - info.lastInteractionSecond;
return info.remainingPayout * secondsSinceLastInteraction / info.remainingVestingSeconds;
```

### F90 측정 변수
**return 문 자체**
```solidity
return info.remainingPayout * secondsSinceLastInteraction / info.remainingVestingSeconds;
```

### 추가 요구사항 ⚠️
**분기 커버리지 보장**:
```solidity
if (secondsSinceLastInteraction > info.remainingVestingSeconds)
```
→ **true 분기, false 분기 모두 도달 가능**하도록 제약식 생성

이 조건 이후에 목표 return 문에 도달해야 함.

### Mutation 파일
- `ThorusBond_c_claimablePayout_swap_mul_div.sol`
- `ThorusBond_c_claimablePayout_original_has_division.sol`

### Z3 제약식 (수정 필요)
```python
# 기존
s.add(vars[2] > 0)  # remainingVestingSeconds > 0
s.add(vars[3] >= 0)  # remainingPayout >= 0
s.add(vars[0] >= vars[1])  # timestamp >= lastInteraction

# 추가: 분기 커버리지
# secondsSinceLastInteraction = block.timestamp - info.lastInteractionSecond
# 조건: secondsSinceLastInteraction > info.remainingVestingSeconds
# → 이 조건이 true/false 둘 다 가능하도록

# 방법: secondsSinceLastInteraction 값이 remainingVestingSeconds 근처에 있도록
# vars[0] = block.timestamp
# vars[1] = lastInteractionSecond
# vars[2] = remainingVestingSeconds
# secondsSinceLastInteraction = vars[0] - vars[1]

# 예: remainingVestingSeconds가 [60,143]이면
#     secondsSinceLastInteraction도 [50,150] 정도로 설정
#     → 일부는 조건 true, 일부는 false
```

---

## 4. LockupContract_c

### 연산자 변경 대상 문장
```solidity
uint unlockTimestamp = deploymentStartTime + (monthsToWaitBeforeUnlock * SECONDS_IN_ONE_MONTH);
uint monthsSinceUnlock = ((block.timestamp - unlockTimestamp) / SECONDS_IN_ONE_MONTH) + 1;
uint monthlyReleaseAmount = initialAmount / releaseSchedule;
uint releasedAmount = monthlyReleaseAmount * monthsSinceUnlock;
```

### F90 측정 변수
**`releasedAmount`** (return 직전)
```solidity
return releasedAmount;
```

### 추가 요구사항 ⚠️
**분기 커버리지 보장**:
```solidity
if (releasedAmount > initialAmount)
```
→ **true 분기, false 분기 모두 도달 가능**하도록 제약식 생성

이 조건 이후에 목표 return 문에 도달해야 함.

### Mutation 파일
- `LockupContract_c__getReleasedAmount_sub_to_add.sol`
- `LockupContract_c__getReleasedAmount_add_to_sub.sol`
- `LockupContract_c__getReleasedAmount_swap_add_sub.sol`
- `LockupContract_c__getReleasedAmount_swap_mul_div.sol`
- `LockupContract_c__getReleasedAmount_original_has_division.sol`

### Z3 제약식 (수정 필요)
```python
# 기존
s.add(vars[1] > 0)  # initialAmount > 0
s.add(vars[3] >= 0)  # monthsToWaitBeforeUnlock >= 0
s.add(vars[4] > 0)  # releaseSchedule > 0
s.add(vars[0] >= vars[2])  # timestamp >= deploymentStartTime

# 추가: 분기 커버리지
# releasedAmount = monthlyReleaseAmount * monthsSinceUnlock
# monthlyReleaseAmount = initialAmount / releaseSchedule
# 조건: releasedAmount > initialAmount

# 방법: initialAmount와 releaseSchedule 범위를 조정하여
#       일부 경우 releasedAmount > initialAmount (true)
#       일부 경우 releasedAmount <= initialAmount (false)

# 예: initialAmount = [100, 150]
#     releaseSchedule = [5, 10]
#     monthsSinceUnlock에 따라 releasedAmount가 달라짐
```

---

## 5. Lock_c

### 연산자 변경 대상 문장
```solidity
uint256 _totalLockRemain = _data.total - _data.unlockedAmounts - _data.pending;
uint256 _nUnlock = (lockedTime - (block.timestamp - startLock) - 1) / unlockDuration + 1;
_pending = _totalLockRemain - _data.estUnlock * _nUnlock;
```

### F90 측정 변수
**`_pending`** (최종 return 직전)
```solidity
if (_data.pending > 0) {
    _pending += _data.pending;  // ← 여기서의 _pending
}
```

### 추가 요구사항 ⚠️

#### 요구사항 1: `_data.pending` 값 보장
```solidity
if (_data.pending > 0) {
```
→ 이 조건이 true가 되어야 최종 `_pending` 값을 볼 수 있음
→ **`_data.pending`이 `[0,0]`이 되면 안됨**

#### 요구사항 2: `_totalLockRemain` 값 보장
```solidity
if (_totalLockRemain > 0) {
```
→ `_data.total`이 `[0,0]`만 아니면 됨 (즉, `[0,~]`은 상관없음)

#### 요구사항 3: 분기 커버리지
```solidity
if (block.timestamp >= startLock + lockedTime) {
    // if 분기
} else {
    // else 분기
}
```
→ **if, else 둘 다 분기 도달 가능**하도록
→ `block.timestamp` 값이 `startLock + lockedTime`의 min, max 사이에 들어가면 됨

### Mutation 파일
- `Lock_c_pending_sub_to_add.sol`
- `Lock_c_pending_add_to_sub.sol`
- `Lock_c_pending_swap_add_sub.sol`

### Z3 제약식 (수정 필요)
```python
# 기존
s.add(vars[3] > 0)  # estUnlock > 0
s.add(vars[7] > 0)  # unlockDuration > 0
s.add(vars[0] >= vars[1] + vars[2])  # total >= unlocked + pending

# 추가 제약

# 1. _data.pending이 [0,0]이 되지 않도록
s.add(vars[2] > 0)  # pending > 0 (또는 범위의 max가 0이 아니도록)

# 2. _data.total이 [0,0]만 아니면 됨
# 이미 vars[0] >= vars[1] + vars[2]로 보장됨 (total >= unlocked + pending)

# 3. 분기 커버리지: block.timestamp와 startLock + lockedTime
# vars[4] = block.timestamp
# vars[5] = startLock
# vars[6] = lockedTime
# 조건: block.timestamp >= startLock + lockedTime

# 방법: timestamp 범위를 startLock + lockedTime 근처로
# 예: startLock = [100, 150], lockedTime = [100, 150]
#     → startLock + lockedTime = [200, 300]
#     timestamp = [180, 320]으로 설정
#     → 일부는 조건 true, 일부는 false
```

---

## 6. HubPool_c

### 연산자 변경 대상 문장
```solidity
uint256 protocolFeesCaptured = (bundleLpFees * protocolFeeCapturePct) / 1e18;
uint256 lpFeesCaptured = bundleLpFees - protocolFeesCaptured;
pooledTokens[l1Token].undistributedLpFees += lpFeesCaptured;
pooledTokens[l1Token].utilizedReserves += int256(lpFeesCaptured);
```

### F90 측정 변수
**`pooledTokens[l1Token].undistributedLpFees`**

### 이유
- 위의 모든 연산들이 `undistributedLpFees`에 반영됨

### 추가 요구사항 ⚠️
**`lpFeesCaptured > 0` 조건 보장**:
```solidity
if (lpFeesCaptured > 0) {
    pooledTokens[l1Token].undistributedLpFees += lpFeesCaptured;  // ← 여기서 측정
```
→ 이 조건이 **true**가 되어야 `undistributedLpFees` 값 측정 가능
→ **`lpFeesCaptured`가 `[0,0]`이 되면 안됨**

### Mutation 파일
- `HubPool_c__allocateLpAndProtocolFees_sub_to_add.sol`
- `HubPool_c__allocateLpAndProtocolFees_swap_add_sub.sol`
- `HubPool_c__allocateLpAndProtocolFees_swap_mul_div.sol`
- `HubPool_c__allocateLpAndProtocolFees_original_has_division.sol`

### Z3 제약식 (수정 필요)
```python
# 기존
s.add(v >= 0) for v in vars  # All non-negative
s.add(vars[0] <= 100)  # protocolFeeCapturePct is percentage

# 추가: lpFeesCaptured > 0 보장
# lpFeesCaptured = bundleLpFees - protocolFeesCaptured
# protocolFeesCaptured = (bundleLpFees * protocolFeeCapturePct) / 1e18
# 조건: lpFeesCaptured > 0
# → bundleLpFees > protocolFeesCaptured
# → bundleLpFees > (bundleLpFees * protocolFeeCapturePct) / 1e18
# → bundleLpFees가 충분히 커야 함

# vars[1] = l1Token (address)
# vars[2] = pooledTokens[l1Token].undistributedLpFees
# vars[3] = pooledTokens[l1Token].utilizedReserves
# vars[4] = unclaimedAccumulatedProtocolFees[l1Token]
# vars[5] = bundleLpFees
# vars[0] = protocolFeeCapturePct

s.add(vars[5] > 0)  # bundleLpFees > 0
# 이렇게 하면 lpFeesCaptured = bundleLpFees - (bundleLpFees * protocolFeeCapturePct) / 1e18
# protocolFeeCapturePct가 작으면 lpFeesCaptured > 0 보장됨
```

---

## 7. PoolKeeper_c

### 연산자 변경 대상 문장
```solidity
uint256 elapsedBlocksNumerator = (block.timestamp - (_savedPreviousUpdatedTimestamp + _poolInterval));
uint256 keeperTip = BASE_TIP + (TIP_DELTA_PER_BLOCK * elapsedBlocksNumerator) / BLOCK_TIME;
```

### F90 측정 변수
**return 문 자체**
```solidity
else {
    return keeperTip;  // ← 여기서의 keeperTip
}
```

### 추가 요구사항 ⚠️
**분기 커버리지 보장**:
```solidity
if (keeperTip > MAX_TIP) {
    return MAX_TIP;
} else {
    return keeperTip;  // ← 이 값을 봐야 함
}
```
→ **true 분기, false 분기 모두 도달 가능**하도록
→ `keeperTip`이 무조건 MAX_TIP보다 크지 않도록

### Mutation 파일
- `PoolKeeper_c_keeperTip_add_to_sub.sol`
- `PoolKeeper_c_keeperTip_swap_add_sub.sol`
- `PoolKeeper_c_keeperTip_swap_mul_div.sol`
- `PoolKeeper_c_keeperTip_original_has_division.sol`

### Z3 제약식 (수정 필요)
```python
# 기존
s.add(vars[1] > 0)  # _savedPreviousUpdatedTimestamp > 0
s.add(vars[2] > 0)  # _poolInterval > 0
s.add(vars[0] >= vars[1])  # timestamp >= previous

# 추가: 분기 커버리지
# keeperTip = BASE_TIP + (TIP_DELTA_PER_BLOCK * elapsedBlocksNumerator) / BLOCK_TIME
# 조건: keeperTip > MAX_TIP
# BASE_TIP = 5, TIP_DELTA_PER_BLOCK = 5, BLOCK_TIME = 13, MAX_TIP = 100

# elapsedBlocksNumerator = block.timestamp - (_savedPreviousUpdatedTimestamp + _poolInterval)
# vars[0] = block.timestamp
# vars[1] = _savedPreviousUpdatedTimestamp
# vars[2] = _poolInterval

# keeperTip이 MAX_TIP(100) 근처에 오도록 elapsedBlocksNumerator 조정
# keeperTip = 5 + (5 * elapsedBlocksNumerator) / 13 = 100
# → 5 * elapsedBlocksNumerator / 13 = 95
# → elapsedBlocksNumerator ≈ 247

# 범위를 200~300 정도로 설정하면:
# - 일부는 keeperTip < MAX_TIP (false, else 분기)
# - 일부는 keeperTip > MAX_TIP (true, if 분기)
```

---

## 구현 계획

### 1단계: Z3 제약식 업데이트
- `Evaluation/z3_rq2_focused.py` 수정
- ThorusBond, LockupContract, Lock에 분기 커버리지 제약 추가

### 2단계: Z3 SAT Input 재생성
- 수정된 제약식으로 70개(또는 mutation 포함 더 많은) input 생성

### 3단계: Annotation 생성
- Mutated contract를 위한 annotation 파일 생성
- 기존 base annotation을 복사하고 Z3 range 적용

### 4단계: 실험 실행
- Original vs Mutated 비교
- F90 측정 (지정된 변수만)

### 5단계: 결과 분석
- 각 mutation이 F90에 미치는 영향 분석
- 어떤 연산자 변경이 precision에 가장 큰 영향을 주는지 파악

---

## 변수 매핑 (Z3 constraints 작성용)

### ThorusBond_c
```
vars[0] = block.timestamp
vars[1] = info.lastInteractionSecond
vars[2] = info.remainingVestingSeconds
vars[3] = info.remainingPayout
```

### LockupContract_c
```
vars[0] = block.timestamp
vars[1] = initialAmount
vars[2] = deploymentStartTime
vars[3] = monthsToWaitBeforeUnlock
vars[4] = releaseSchedule
```

### Lock_c
```
vars[0] = _data.total
vars[1] = _data.unlockedAmounts
vars[2] = _data.pending
vars[3] = _data.estUnlock
vars[4] = block.timestamp
vars[5] = startLock
vars[6] = lockedTime
vars[7] = unlockDuration
```

---

## 측정 대상 변수 요약

| 컨트랙트 | F90 측정 변수 | 분기 커버리지 요구 | 특이사항 |
|---------|-------------|----------------|---------|
| GovStakingStorage | `info.rewardMultiplier` | 없음 | toRemove/toAdd 통합 |
| GreenHouse | `net` | 없음 | 모든 fee 계산 통합 |
| ThorusBond | return 문 자체 | ⚠️ if 양쪽 분기 | secondsSinceLastInteraction 조건 |
| LockupContract | `releasedAmount` | ⚠️ if 양쪽 분기 | releasedAmount > initialAmount 조건 |
| Lock | `_pending` (최종) | ⚠️ if/else 양쪽 분기 | pending > 0, timestamp 조건 |

---

## 다음 단계 대기 중

**HubPool_c**와 **PoolKeeper_c**는 다음 챗에서 논의 예정입니다.

---

**작성일**: 2025-10-29
**상태**: ThorusBond, LockupContract, Lock의 Z3 제약식 수정 필요
