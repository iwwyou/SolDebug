function _getReleasedAmount() internal view returns (uint) {
    uint unlockTimestamp = deploymentStartTime + (monthsToWaitBeforeUnlock * SECONDS_IN_ONE_MONTH);
    if (block.timestamp < unlockTimestamp) {
        return 0;
    }
    uint monthsSinceUnlock = ((block.timestamp + unlockTimestamp) / SECONDS_IN_ONE_MONTH) + 1;
    uint monthlyReleaseAmount = initialAmount / releaseSchedule;
    uint releasedAmount = monthlyReleaseAmount * monthsSinceUnlock;

    if (releasedAmount > initialAmount){
        return initialAmount;
    }

    return releasedAmount;
}
