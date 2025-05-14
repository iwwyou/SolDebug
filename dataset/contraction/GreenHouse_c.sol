contract GreenHouse {
    uint256 constant internal BONUS_POOL_NEW_STAKEHOLDER_TIME_ADDITION = 900; 
    uint256 constant internal BONUS_POOL_TIMER_INITIAL = 21600;
    uint256 internal _bonusPoolLeaderboardLast = 0;
    uint256 internal _bonusPoolLastDistributedAt=0;
    uint256 internal _bonusPoolTimer;
    mapping(uint256 => address) internal _bonusPoolLeaderboard;
    mapping(address => uint256) internal _bonusPoolLeaderboardPositionsCount;    

    function bonusRewardPoolCountdown() public view returns(uint256) {      
        uint256 timeSinceLastDistributed = block.timestamp - _bonusPoolLastDistributedAt;
        if (timeSinceLastDistributed >= _bonusPoolTimer) {
            return 0;
        }
        return _bonusPoolTimer - timeSinceLastDistributed;
    }

    function _bonusPoolLeaderboardPush(address value) internal {
        _bonusPoolLeaderboardLast++;
        _bonusPoolLeaderboard[_bonusPoolLeaderboardLast] = value;
        _bonusPoolLeaderboardPositionsCount[value] += 1;
        if((bonusRewardPoolCountdown()+BONUS_POOL_NEW_STAKEHOLDER_TIME_ADDITION) >= BONUS_POOL_TIMER_INITIAL){
            _bonusPoolTimer += 0;
        } else {
            _bonusPoolTimer += BONUS_POOL_NEW_STAKEHOLDER_TIME_ADDITION;
        }
       
    }
}