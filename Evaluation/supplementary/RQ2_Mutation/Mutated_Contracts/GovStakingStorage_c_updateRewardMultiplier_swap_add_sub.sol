function updateRewardMultiplier(
        address user,
        uint256 oldRate,
        uint256 newRate,
        uint256 passedTime,
        uint256 oldLockPeriod,
        uint256 newLockPeriod,
        uint256 oldAmount,
        uint256 newAmount
    ) external isAllowed {
        UserInfo storage info = userInfo[user];
        uint256 toRemove = ((((oldLockPeriod + passedTime) / 1 weeks) *
            oldRate) * oldAmount) / 100000;
        uint256 toAdd = (((newLockPeriod / 1 weeks) * newRate) * newAmount) /
            100000;
        info.rewardMultiplier = info.rewardMultiplier - toAdd + toRemove;
        totalRewardMultiplier = totalRewardMultiplier - toAdd + toRemove;
    }