// Problem 5: Lock (Complexity: High)
// Nested conditions + complex arithmetic
// Original: dataset/contraction/Lock_c.sol

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

/*
[Input]
total = 10000
unlockedAmounts = 2000
pendingAmount = 500
estUnlock = 400
currentTime = 2500
startLock = 1000
lockedTime = 3000
unlockDuration = 500

[Question] What is the return value (result)?

[Solution]
totalLockRemain = 10000 - 2000 - 500 = 7500

totalLockRemain > 0? Yes (7500 > 0)
  currentTime >= startLock + lockedTime? 2500 >= 1000 + 3000? 2500 >= 4000? No, go to else
    nUnlock = (3000 - (2500 - 1000) - 1) / 500 + 1
            = (3000 - 1500 - 1) / 500 + 1
            = 1499 / 500 + 1
            = 2 + 1 = 3
    result = 7500 - 400 * 3 = 7500 - 1200 = 6300

pendingAmount > 0? Yes (500 > 0)
  result = 6300 + 500 = 6800

[Answer] 6800
*/
