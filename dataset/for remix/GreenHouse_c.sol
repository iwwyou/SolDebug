contract GreenHouse {
    uint256 constant internal BONUS_POOL_NEW_STAKEHOLDER_TIME_ADDITION = 900; 
    uint256 constant internal BONUS_POOL_TIMER_INITIAL = 21600;
    uint256 internal _bonusPoolLeaderboardFirst = 1;
    uint256 internal _bonusPoolLeaderboardLast = 0;
    uint256 internal _bonusPoolLastDistributedAt = 0;
    uint256 internal _bonusPoolTimer;
    mapping(uint256 => address) internal _bonusPoolLeaderboard;
    mapping(address => uint256) internal _bonusPoolLeaderboardPositionsCount;    

    /* ───────────────  ✅ Setter / Helper  ─────────────── */

    /// @notice 리더보드 포인터을 직접 설정
    function _setLeaderboardPointers(uint256 first, uint256 last) external {
        _bonusPoolLeaderboardFirst = first;
        _bonusPoolLeaderboardLast  = last;
    }

    /// @notice 마지막 분배 시각 및 타이머 직접 설정
    function _setBonusPoolTiming(uint256 lastDistributedAt, uint256 timer) external {
        _bonusPoolLastDistributedAt = lastDistributedAt;
        _bonusPoolTimer             = timer;
    }

    /// @notice 특정 인덱스의 리더보드 주소를 덮어쓰기
    function _setLeaderboardEntry(uint256 index, address who) external {
        _bonusPoolLeaderboard[index] = who;
    }

    /// @notice 주소별 리더보드 포지션 카운트를 직접 설정
    function _setLeaderboardCount(address who, uint256 count) external {
        _bonusPoolLeaderboardPositionsCount[who] = count;
    }

    /// @notice 리더보드 전부 초기화 (pop 루프 대신 원상 복구용)
    function _clearLeaderboard() external {
        while (_bonusPoolLeaderboardUsersCount() > 0) {
            _bonusPoolLeaderboardPop();
        }
        // 포인터를 원상 복구
        _bonusPoolLeaderboardFirst = 1;
        _bonusPoolLeaderboardLast  = 0;
    }

    /// @notice 리더보드에 주소 push (내부 push 래핑)
    function _pushToLeaderboard(address who) external {
        _bonusPoolLeaderboardPush(who);
    }

    /// @notice 리더보드 첫 주소 pop (내부 pop 래핑)
    function _popFromLeaderboard() external {
        require(_bonusPoolLeaderboardUsersCount() > 0, "empty");
        _bonusPoolLeaderboardPop();
    }

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