// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract ThorusBond {
    
    struct UserInfo {
        uint256 remainingPayout;
        uint256 remainingVestingSeconds;
        uint256 lastInteractionSecond;
    }
    mapping(address => UserInfo) public userInfo;
    
    function claimablePayout(address user) public returns (uint256) {
        UserInfo memory info = userInfo[user];
        uint256 secondsSinceLastInteraction = block.timestamp - info.lastInteractionSecond;
        
        if(secondsSinceLastInteraction > info.remainingVestingSeconds)
            return info.remainingPayout;
        return info.remainingPayout * secondsSinceLastInteraction / info.remainingVestingSeconds;
    }
}