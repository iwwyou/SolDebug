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

    // Auto-generated setter for claimedOnce (mapping)
    function set_claimedOnce(address _key, bool _value) public {
        claimedOnce[_key] = _value;
    }

    // Auto-generated setter for startTime
    function set_startTime(uint256 _value) public {
        startTime = _value;
    }

    // Auto-generated setter for locktime
    function set_locktime(uint256 _value) public {
        locktime = _value;
    }

    // Auto-generated setter for claimable (mapping)
    function set_claimable(address _key, uint256 _value) public {
        claimable[_key] = _value;
    }
}