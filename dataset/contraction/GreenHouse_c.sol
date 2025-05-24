contract GreenHouse {
    uint256 constant internal BONUS_POOL_NEW_STAKEHOLDER_TIME_ADDITION = 900; 
    uint256 constant internal BONUS_POOL_TIMER_INITIAL = 21600;
    uint256 internal _bonusPoolLeaderboardFirst = 1;
    uint256 internal _bonusPoolLeaderboardLast = 0;
    uint256 internal _bonusPoolLastDistributedAt = 0;
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

    function _bonusPoolLeaderboardPop() internal {
        address removed = _bonusPoolLeaderboard[_bonusPoolLeaderboardFirst];
        delete _bonusPoolLeaderboard[_bonusPoolLeaderboardFirst];
        _bonusPoolLeaderboardFirst++;
        _bonusPoolLeaderboardPositionsCount[removed]--;
        if (_bonusPoolLeaderboardPositionsCount[removed] == 0) {
            delete _bonusPoolLeaderboardPositionsCount[removed];
        }
    }

    function _bonusPoolLeaderboardUsersCount() internal view returns(uint256) {
        return _bonusPoolLeaderboardLast + 1 - _bonusPoolLeaderboardFirst;
    }

    function _bonusPoolLeaderboardKick(address stakeholder, uint256 positions) internal {      
        uint256 positionsLeftToKick = positions;
        address[] memory leaderboard = new address[](_bonusPoolLeaderboardUsersCount() - positions);
        uint256 ptr = 0;
        for (uint256 i = _bonusPoolLeaderboardFirst; i <= _bonusPoolLeaderboardLast; i++) {
            if (positionsLeftToKick > 0 && _bonusPoolLeaderboard[i] == stakeholder) {
                positionsLeftToKick--;
            } else {
                leaderboard[ptr] = _bonusPoolLeaderboard[i];
                ptr++;
            }
        }
       
        while (_bonusPoolLeaderboardUsersCount() > 0) {
            _bonusPoolLeaderboardPop();
        }

        for (uint256 i = 0; i < leaderboard.length; ++i) {
            _bonusPoolLeaderboardPush(leaderboard[i]);
        }
    }

}