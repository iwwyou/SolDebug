// Problem 4: LockupContract (Complexity: High)
// Time-based calculation + multiple conditions
// Original: dataset/contraction/LockupContract_c.sol

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

/*
[Input]
currentTime = 15000000
deploymentStartTime = 10000000
monthsToWait = 3
secondsInMonth = 1000000
initialAmount = 24000
releaseSchedule = 12

[Question] What is the return value?

[Solution]
unlockTimestamp = 10000000 + (3 * 1000000) = 10000000 + 3000000 = 13000000

currentTime < unlockTimestamp? 15000000 < 13000000? No, continue

monthsSinceUnlock = ((15000000 - 13000000) / 1000000) + 1 = (2000000 / 1000000) + 1 = 2 + 1 = 3
monthlyReleaseAmount = 24000 / 12 = 2000
releasedAmount = 2000 * 3 = 6000

releasedAmount > initialAmount? 6000 > 24000? No

return releasedAmount = 6000

[Answer] 6000
*/
