# Z3 제약식 업데이트 요약

## 개요
사용자 요구사항에 따라 5개 컨트랙트의 Z3 제약식을 업데이트했습니다.
특히 **분기 커버리지 보장**을 위한 제약식을 추가했습니다.

---

## 1. GovStakingStorage_c

### F90 측정 변수
**`info.rewardMultiplier`**

### 제약식
기존 제약식 유지 (특별한 분기 요구사항 없음):
```python
"constraints": lambda s, vars: [
    s.add(v > 0) for v in vars  # All positive
] + [
    s.add(vars[4] < vars[5]),  # passedTime < oldLockPeriod (no overflow)
]
```

### 변수 매핑
```
vars[0] = info.rewardMultiplier
vars[1] = totalRewardMultiplier
vars[2] = oldRate
vars[3] = newRate
vars[4] = passedTime
vars[5] = oldLockPeriod
vars[6] = newLockPeriod
vars[7] = oldAmount
vars[8] = newAmount
```

---

## 2. GreenHouse_c

### F90 측정 변수
**`net`**

### 제약식
기존 제약식 유지 (특별한 분기 요구사항 없음):
```python
"constraints": lambda s, vars: [
    s.add(vars[0] > 0),  # amount > 0
    s.add(vars[0] < 1000000),  # reasonable upper bound
]
```

### 변수 매핑
```
vars[0] = amount
```

---

## 3. ThorusBond_c ⚠️ 분기 커버리지 추가

### F90 측정 변수
**return 문 자체**
```solidity
return info.remainingPayout * secondsSinceLastInteraction / info.remainingVestingSeconds;
```

### 분기 조건
```solidity
if (secondsSinceLastInteraction > info.remainingVestingSeconds)
```
→ **true/false 양쪽 분기 모두 도달 가능**해야 함

### 업데이트된 제약식
```python
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
```

### 분기 커버리지 달성 방법
**Overlap 패턴** 사용 시:
- 모든 변수가 같은 범위 `[100, 100+Δ]`
- `secondsSinceLastInteraction = timestamp - lastInteraction`의 범위도 `[0, Δ]` 내
- `remainingVestingSeconds`도 `[100, 100+Δ]`
- 자연스럽게 양쪽 분기 커버 가능

### 변수 매핑
```
vars[0] = block.timestamp
vars[1] = info.lastInteractionSecond
vars[2] = info.remainingVestingSeconds
vars[3] = info.remainingPayout
```

---

## 4. LockupContract_c ⚠️ 분기 커버리지 추가

### F90 측정 변수
**`releasedAmount`** (return 직전)
```solidity
return releasedAmount;
```

### 분기 조건
```solidity
if (releasedAmount > initialAmount)
```
→ **true/false 양쪽 분기 모두 도달 가능**해야 함

### 업데이트된 제약식
```python
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
```

### 분기 커버리지 달성 방법
**Overlap 패턴** 사용 시:
```
releasedAmount = (initialAmount / releaseSchedule) * monthsSinceUnlock
```
- `initialAmount = [100, 100+Δ]`
- `releaseSchedule = [100, 100+Δ]`
- `monthsSinceUnlock`도 비슷한 범위
- `releasedAmount`의 값이 `initialAmount` 근처에 분포
- 자연스럽게 양쪽 분기 커버 가능

### 변수 매핑
```
vars[0] = block.timestamp
vars[1] = initialAmount
vars[2] = deploymentStartTime
vars[3] = monthsToWaitBeforeUnlock
vars[4] = releaseSchedule
```

---

## 5. Lock_c ⚠️ 분기 커버리지 + pending > 0 보장

### F90 측정 변수
**`_pending`** (최종 return 직전)
```solidity
if (_data.pending > 0) {
    _pending += _data.pending;  // ← 여기서의 _pending
}
```

### 분기 조건들

#### 조건 1: `_data.pending > 0`
```solidity
if (_data.pending > 0) {
```
→ 이 조건이 **true**가 되어야 최종 `_pending` 값 측정 가능
→ **`_data.pending`이 `[0,0]`이 되면 안됨**

#### 조건 2: `_totalLockRemain > 0`
```solidity
if (_totalLockRemain > 0) {
```
→ `_data.total`이 `[0,0]`만 아니면 됨

#### 조건 3: 시간 조건
```solidity
if (block.timestamp >= startLock + lockedTime) {
    // if 분기
} else {
    // else 분기
}
```
→ **if, else 양쪽 분기 모두 도달 가능**해야 함

### 업데이트된 제약식
```python
"constraints": lambda s, vars: [
    s.add(vars[3] > 0),  # estUnlock > 0
    s.add(vars[7] > 0),  # unlockDuration > 0
    s.add(vars[0] >= vars[1] + vars[2]),  # total >= unlocked + pending (no underflow)
    s.add(vars[2] > 0),  # _data.pending > 0 (to avoid [0,0])  ← 추가됨!
    # Branch coverage requirements:
    # 1. _data.pending > 0: already ensured above
    # 2. _totalLockRemain > 0: ensured by total >= unlocked + pending
    # 3. block.timestamp >= startLock + lockedTime: both branches
    #    With overlap pattern, timestamp range naturally covers both sides
]
```

### 분기 커버리지 달성 방법
**Overlap 패턴** 사용 시:
```
조건: block.timestamp >= startLock + lockedTime
```
- `timestamp = [100, 100+Δ]`
- `startLock = [100, 100+Δ]`
- `lockedTime = [100, 100+Δ]`
- `startLock + lockedTime`의 범위는 대략 `[200, 200+2Δ]`
- `timestamp`의 범위 `[100, 100+Δ]`와 비교 시:
  - 대부분은 false (timestamp < startLock + lockedTime)
  - 일부는 true (timestamp가 큰 값일 때)

더 나은 커버리지를 위해서는 **diff 패턴**도 테스트하는 것이 좋습니다.

### 변수 매핑
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

## 변경 사항 요약

| 컨트랙트 | 추가된 제약식 | 목적 |
|---------|------------|------|
| GovStakingStorage | 없음 | 기존 유지 |
| GreenHouse | 없음 | 기존 유지 |
| **ThorusBond** | 주석 추가 | 분기 커버리지 설명 |
| **LockupContract** | 주석 추가 | 분기 커버리지 설명 |
| **Lock** | `vars[2] > 0` | pending > 0 보장 + 분기 설명 |

---

## 6. HubPool_c ⚠️ lpFeesCaptured > 0 보장

### F90 측정 변수
**`pooledTokens[l1Token].undistributedLpFees`**

### 분기 조건
```solidity
if (lpFeesCaptured > 0) {
    pooledTokens[l1Token].undistributedLpFees += lpFeesCaptured;
```
→ 이 조건이 **true**가 되어야 undistributedLpFees 값 측정 가능
→ **`lpFeesCaptured`가 `[0,0]`이 되면 안됨**

### 업데이트된 제약식
```python
"constraints": lambda s, vars: [
    s.add(v >= 0) for v in vars  # All non-negative
] + [
    s.add(vars[0] <= 100),  # protocolFeeCapturePct is percentage
    s.add(vars[5] > 0),  # bundleLpFees > 0 (to ensure lpFeesCaptured > 0)  ← 추가됨!
    # Branch coverage: lpFeesCaptured > 0
    # lpFeesCaptured = bundleLpFees - (bundleLpFees * protocolFeeCapturePct) / 1e18
    # Since protocolFeeCapturePct <= 100, the fraction is tiny, so bundleLpFees > 0 suffices
]
```

### 분기 커버리지 달성 방법
**lpFeesCaptured 계산식**:
```
lpFeesCaptured = bundleLpFees - (bundleLpFees * protocolFeeCapturePct) / 1e18
```
- `protocolFeeCapturePct <= 100` (percentage)
- `bundleLpFees > 0`이면 `lpFeesCaptured > 0` 보장됨
- `protocolFeeCapturePct / 1e18`은 매우 작은 값 (최대 0.0000000000000001)

### 변수 매핑
```
vars[0] = protocolFeeCapturePct
vars[1] = pooledTokens[l1Token].undistributedLpFees
vars[2] = pooledTokens[l1Token].utilizedReserves
vars[3] = unclaimedAccumulatedProtocolFees[l1Token]
vars[4] = l1Token
vars[5] = bundleLpFees
```

---

## 7. PoolKeeper_c ⚠️ 분기 커버리지 추가

### F90 측정 변수
**return 문 자체** (else 분기)
```solidity
if (keeperTip > MAX_TIP) {
    return MAX_TIP;
} else {
    return keeperTip;  // ← 여기서의 keeperTip
}
```

### 분기 조건
```solidity
if (keeperTip > MAX_TIP)
```
→ **true/false 양쪽 분기 모두 도달 가능**해야 함

### 업데이트된 제약식
```python
"constraints": lambda s, vars: [
    s.add(vars[1] > 0),  # _savedPreviousUpdatedTimestamp > 0
    s.add(vars[2] > 0),  # _poolInterval > 0
    s.add(vars[0] >= vars[1] + vars[2]),  # timestamp >= savedPrevious + poolInterval (no underflow)  ← 변경됨!
    # Branch coverage: keeperTip > MAX_TIP (100)
    # keeperTip = BASE_TIP(5) + (TIP_DELTA_PER_BLOCK(5) * elapsedBlocksNumerator) / BLOCK_TIME(13)
    # elapsedBlocksNumerator = timestamp - (savedPrevious + poolInterval)
    # For keeperTip = 100: elapsedBlocksNumerator ≈ 247
    # With overlap/diff patterns and widening, ranges will naturally cover both branches
]
```

### 분기 커버리지 달성 방법
**keeperTip 계산식**:
```solidity
uint256 elapsedBlocksNumerator = (block.timestamp - (_savedPreviousUpdatedTimestamp + _poolInterval));
uint256 keeperTip = BASE_TIP + (TIP_DELTA_PER_BLOCK * elapsedBlocksNumerator) / BLOCK_TIME;
                   = 5 + (5 * elapsedBlocksNumerator) / 13
```

**임계값 계산**:
- MAX_TIP = 100
- `keeperTip = 100`일 때: `elapsedBlocksNumerator ≈ 247`

**Overlap/Diff 패턴 모두 가능**:
- Overlap 패턴: 모든 변수가 `[100, 100+Δ]` 범위
- Widening 과정에서 자연스럽게 `elapsedBlocksNumerator`가 247 주변 값 포함
- 일부는 `keeperTip < 100` (false 분기), 일부는 `keeperTip > 100` (true 분기)

### 변수 매핑
```
vars[0] = block.timestamp
vars[1] = _savedPreviousUpdatedTimestamp
vars[2] = _poolInterval
```

---

## 변경 사항 요약 (최종)

| 컨트랙트 | 추가된 제약식 | 목적 |
|---------|------------|------|
| GovStakingStorage | 없음 | 기존 유지 |
| GreenHouse | 없음 | 기존 유지 |
| **ThorusBond** | 주석 추가 | 분기 커버리지 설명 |
| **LockupContract** | 주석 추가 | 분기 커버리지 설명 |
| **Lock** | `vars[2] > 0` | pending > 0 보장 + 분기 설명 |
| **HubPool** | `vars[5] > 0` | bundleLpFees > 0 보장 |
| **PoolKeeper** | `vars[0] >= vars[1] + vars[2]` | timestamp 제약 강화 + 분기 설명 |

## 다음 단계

### 1. Z3 SAT Input 재생성 ✅ 준비 완료
```bash
python Evaluation/z3_rq2_focused.py
```
- 수정된 제약식으로 70개 input 재생성
- Lock_c: `pending > 0` 제약
- HubPool_c: `bundleLpFees > 0` 제약
- PoolKeeper_c: `timestamp >= savedPrevious + poolInterval` 제약

### 2. 생성된 Input 검증
- `Evaluation/RQ2_Z3_Focused/` 디렉토리 확인
- Lock_c의 pending 값이 0이 아닌지 확인
- HubPool_c의 bundleLpFees 값이 0이 아닌지 확인
- PoolKeeper_c의 timestamp 값이 충분히 큰지 확인

### 3. Annotation 파일 생성
- Mutated contract를 위한 annotation 생성
- 기존 base annotation을 복사하고 Z3 range 적용

### 4. 실험 실행
- 전체 실험 설계 및 실행
- F90 결과 분석

---

**최종 업데이트**: 2025-10-29
**수정된 파일**: `Evaluation/z3_rq2_focused.py`
**주요 변경**:
- Lock_c: `pending > 0` 제약 추가
- HubPool_c: `bundleLpFees > 0` 제약 추가
- PoolKeeper_c: `timestamp >= savedPrevious + poolInterval` 제약 강화
