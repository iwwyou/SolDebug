// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract Claim {
    mapping(address => uint256) public claimable;
    mapping(address => bool) public claimedOnce;

    uint256 locktime;
    uint256 startTime = 0;
    
    function getCurrentClaimAmount(address user) public returns (uint256) {
        if (!claimedOnce[user] && block.timestamp < (startTime + locktime)) {
            return (claimable[user] * 30) / 100;
        } else if (block.timestamp >= (startTime + locktime)) {
            return claimable[user];
        }
        return 0;
    }
}