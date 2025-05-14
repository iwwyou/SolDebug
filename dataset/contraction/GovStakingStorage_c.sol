contract GovStakingStorage {
    uint256 totalLockedGogo;
    uint256 totalRewardRates;
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
    address[] public userList;

    modifier isAllowed() {
        require(allowed[msg.sender], "sender is not allowed to write");
        _;
    }

    function removeUser(address user) external isAllowed {
        require(userInfo[user].index != 0, "user does not exist");
        if (userList.length > 1) {
            address lastAddress = userList[userList.length - 1];
            uint256 oldIndex = userInfo[user].index;
            userList[oldIndex] = lastAddress;
            userInfo[lastAddress].index = oldIndex;
        }
        userList.pop();
        totalRewardMultiplier -= userInfo[user].rewardMultiplier;
        delete userInfo[user];
    }

    function updateRewardMultiplier(address user, uint256 oldRate, uint256 newRate, uint256 passedTime, uint256 oldLockPeriod, uint256 newLockPeriod, uint256 oldAmount, uint256 newAmount) external isAllowed {
        UserInfo storage info = userInfo[user];
        uint256 toRemove = ((((oldLockPeriod - passedTime) / 1 weeks) * oldRate) * oldAmount) / 100000;
        uint256 toAdd = (((newLockPeriod / 1 weeks) * newRate) * newAmount) / 100000;
        info.rewardMultiplier = info.rewardMultiplier + toAdd - toRemove;
        totalRewardMultiplier = totalRewardMultiplier + toAdd - toRemove;
    }

    function addRewardMultiplier(address user, uint256 rate, uint256 period, uint256 amount) external isAllowed {
        UserInfo storage info = userInfo[user];
        info.rewardMultiplier += ((((rate * period) / 1 weeks) * amount)) / 100000;
        totalRewardMultiplier += ((((rate * period) / 1 weeks) * amount)) / 100000;
    }

    function getUserInfoByIndex(uint256 from, uint256 to) external view returns (UserInfo[] memory) {
        uint256 to_ = to > userList.length ? userList.length : to;
        UserInfo[] memory result = new UserInfo[](to - from);
        for (uint256 i = 0; i < to_ - from; i++) {
            result[i] = userInfo[userList[i + from]];
        }
        return result;
    }
}