// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract GovStakingStorage {    
    uint256 totalRewardMultiplier;
    
    struct UserInfo {
        uint256 amount; 
        uint256 lockStart; 
        uint256 lockPeriod; 
        uint256 lastClaimed; 
        uint256 unclaimedAmount; 
        uint256 rewardRate; 
        uint256 rewardMultiplier; 
        uint256 userRewardPerTokenPaid; 
        uint256 index;
    }

    mapping(address => UserInfo) public userInfo;    
    mapping(address => bool) public allowed;

    modifier isAllowed() {
        require(allowed[msg.sender], "sender is not allowed to write");
        _;
    }

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
        uint256 toRemove = ((((oldLockPeriod - passedTime) / 1 weeks) *
            oldRate) * oldAmount) / 100000;
        uint256 toAdd = (((newLockPeriod / 1 weeks) * newRate) * newAmount) /
            100000;
        info.rewardMultiplier = info.rewardMultiplier + toAdd - toRemove;
        totalRewardMultiplier = totalRewardMultiplier + toAdd - toRemove;
    }

    // Setter for allowed mapping
    function set_allowed(address _key, bool _value) public {
        allowed[_key] = _value;
    }

    // Setter for totalRewardMultiplier
    function set_totalRewardMultiplier(uint256 _value) public {
        totalRewardMultiplier = _value;
    }
    
    

    

    // Auto-generated setter for userInfo (mapping)
    function set_userInfo(address _key, UserInfo memory _value) public {
        userInfo[_key] = _value;
    }
}