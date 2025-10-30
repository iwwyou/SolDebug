function claimablePayout(address user) public view returns (uint256) {
        UserInfo memory info = userInfo[user];
        uint256 secondsSinceLastInteraction = block.timestamp - info.lastInteractionSecond;
        
        if(secondsSinceLastInteraction > info.remainingVestingSeconds)
            return info.remainingPayout;
        return info.remainingPayout / secondsSinceLastInteraction * info.remainingVestingSeconds;
    }