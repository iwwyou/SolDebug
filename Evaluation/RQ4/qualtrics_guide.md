# RQ4: Human-Centric Evaluation - Qualtrics Survey Guide

## Overview

This experiment evaluates whether SolQDebug helps developers understand smart contract code behavior.

### Experimental Design
- **Independent Variable**: Tool usage (Control: manual calculation, Treatment: SolQDebug)
- **Dependent Variables**: Response time, Accuracy
- **Between-subject design**: Different participants for each group

---

## Survey Structure

### Part 1: Demographics (2 min)
1. Programming experience (years)
2. Solidity/Smart contract experience (None / Beginner / Intermediate / Advanced)
3. Current role (Student / Developer / Researcher / Other)

### Part 2: Practice Problem (2 min)
- Simple example to familiarize with format
- Not included in analysis

### Part 3: Main Problems (5 problems)
- Qualtrics Timing feature enabled for each question
- Order: Randomized or fixed (Low → High complexity)

### Part 4: Post-survey (Optional)
- Confidence rating (1-5)
- Difficulty rating (1-5)
- Open feedback

---

## Problems Summary

| # | Name | Complexity | Key Features | Answer |
|---|------|------------|--------------|--------|
| 1 | GreenHouse | Low | Pure arithmetic (6 vars) | 7651 |
| 2 | HubPool | Medium | 2 conditions + dependency chain | 954 |
| 3 | PercentageFeeModel | Medium-High | Nested if-else | 85 |
| 4 | LockupContract | High | Time-based + conditions | 6000 |
| 5 | Lock | High | Nested conditions + complex arithmetic | 6800 |

---

## Qualtrics Setup Instructions

### 1. Create Survey
- New Survey → "SolQDebug Human-Centric Evaluation"

### 2. For Each Problem Page:
1. Add **Image** block: Screenshot of code
2. Add **Text** block: Input values
3. Add **Text Entry** question: "What is the return value?"
4. Add **Timing** question (hidden): Auto-records page time

### 3. Timing Configuration
- Survey Flow → Add "Timing" element
- Settings: First Click, Last Click, Page Submit, Click Count

### 4. Randomization (Optional)
- Survey Flow → Randomizer → Present problems in random order

---

## Code Images for Qualtrics

### Problem 1: GreenHouse
```solidity
function calculateFees(
    uint256 amount,
    uint256 feeAllUsers,
    uint256 feeBonus,
    uint256 feePartner,
    uint256 feeReferral,
    uint256 feePlatform
) returns (uint256 net) {
    uint256 allUsers = (amount * feeAllUsers) / 10000;
    uint256 bonusPool = (amount * feeBonus) / 10000;
    uint256 partner = (amount * feePartner) / 10000;
    uint256 referral = (amount * feeReferral) / 10000;
    uint256 platform = (amount * feePlatform) / 10000;
    net = amount - allUsers - bonusPool - partner - referral - platform;
}
```

**Input:**
```
amount = 8500
feeAllUsers = 700
feeBonus = 100
feePartner = 50
feeReferral = 50
feePlatform = 100
```

**Question:** What is the return value (net)?
**Answer:** 7651

---

### Problem 2: HubPool
```solidity
function allocateFees(
    uint256 bundleFees,
    uint256 capturePct,
    uint256 undistributedFees,
    uint256 utilizedReserves,
    uint256 unclaimedFees
) returns (uint256) {
    uint256 protocolFees = (bundleFees * capturePct) / 100;
    uint256 lpFees = bundleFees - protocolFees;

    if (lpFees > 0) {
        undistributedFees += lpFees;
        utilizedReserves += lpFees;
    }

    if (protocolFees > 0) {
        unclaimedFees += protocolFees + undistributedFees - utilizedReserves;
    }

    return unclaimedFees;
}
```

**Input:**
```
bundleFees = 1847
capturePct = 30
undistributedFees = 500
utilizedReserves = 200
unclaimedFees = 100
```

**Question:** What is the return value?
**Answer:** 954

---

### Problem 3: PercentageFeeModel
```solidity
function getEarlyWithdrawFeeAmount(
    uint256 withdrawnAmount,
    bool isDepositOverridden,
    uint256 depositFee,
    bool isPoolOverridden,
    uint256 poolFee,
    uint256 defaultFee
) returns (uint256 feeAmount) {
    uint256 feeRate;

    if (isDepositOverridden) {
        feeRate = depositFee;
    } else {
        if (isPoolOverridden) {
            feeRate = poolFee;
        } else {
            feeRate = defaultFee;
        }
    }

    feeAmount = (withdrawnAmount * feeRate) / 1000;
}
```

**Input:**
```
withdrawnAmount = 2450
isDepositOverridden = false
depositFee = 50
isPoolOverridden = true
poolFee = 35
defaultFee = 25
```

**Question:** What is the return value (feeAmount)?
**Answer:** 85

---

### Problem 4: LockupContract
```solidity
function getReleasedAmount(
    uint256 currentTime,
    uint256 deploymentStartTime,
    uint256 monthsToWait,
    uint256 secondsInMonth,
    uint256 initialAmount,
    uint256 releaseSchedule
) returns (uint256) {
    uint256 unlockTimestamp = deploymentStartTime + (monthsToWait * secondsInMonth);

    if (currentTime < unlockTimestamp) {
        return 0;
    }

    uint256 monthsSinceUnlock = ((currentTime - unlockTimestamp) / secondsInMonth) + 1;
    uint256 monthlyReleaseAmount = initialAmount / releaseSchedule;
    uint256 releasedAmount = monthlyReleaseAmount * monthsSinceUnlock;

    if (releasedAmount > initialAmount) {
        return initialAmount;
    }

    return releasedAmount;
}
```

**Input:**
```
currentTime = 15000000
deploymentStartTime = 10000000
monthsToWait = 3
secondsInMonth = 1000000
initialAmount = 24000
releaseSchedule = 12
```

**Question:** What is the return value?
**Answer:** 6000

---

### Problem 5: Lock
```solidity
function pending(
    uint256 total,
    uint256 unlockedAmounts,
    uint256 pendingAmount,
    uint256 estUnlock,
    uint256 currentTime,
    uint256 startLock,
    uint256 lockedTime,
    uint256 unlockDuration
) returns (uint256 result) {
    uint256 totalLockRemain = total - unlockedAmounts - pendingAmount;

    if (totalLockRemain > 0) {
        if (currentTime >= startLock + lockedTime) {
            result = totalLockRemain;
        } else {
            uint256 nUnlock = (lockedTime - (currentTime - startLock) - 1) / unlockDuration + 1;
            result = totalLockRemain - estUnlock * nUnlock;
        }
    }

    if (pendingAmount > 0) {
        result += pendingAmount;
    }
}
```

**Input:**
```
total = 10000
unlockedAmounts = 2000
pendingAmount = 500
estUnlock = 400
currentTime = 2500
startLock = 1000
lockedTime = 3000
unlockDuration = 500
```

**Question:** What is the return value (result)?
**Answer:** 6800

---

## Data Analysis Plan

### Metrics
1. **Response Time**: Qualtrics timing data (seconds)
2. **Accuracy**: Correct/Incorrect (binary)

### Analysis
1. Compare mean response time: Control vs Treatment
2. Compare accuracy rate: Control vs Treatment
3. Analyze by complexity level
4. Statistical tests: t-test or Mann-Whitney U

### Expected Results
- Treatment group (SolQDebug) shows:
  - Lower response time
  - Higher accuracy
  - Effect size increases with problem complexity
