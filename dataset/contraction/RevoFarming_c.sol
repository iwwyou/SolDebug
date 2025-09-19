contract RevoFarming {
    
    struct FarmingPool {
        string name;
        uint256 poolIndex;
        uint256 startTime;
        uint256 periodFinish;
        uint256 rewardRate;
        uint256 rewardsDuration;
        uint256 lastUpdateTime;
        uint256 rewardPerTokenStored;
        uint256 totalLpStaked;
    }

    uint256 public poolIndex;
    mapping(uint256 => FarmingPool) public farmingPools;
    
    function getAllPools() external view returns(FarmingPool[] memory){
        FarmingPool[] memory poolsToReturn = new FarmingPool[](poolIndex);
        for(uint256 i = 0; i < poolIndex; i++){
            poolsToReturn[i] = farmingPools[i];
        }
        
        return poolsToReturn;
    }
}