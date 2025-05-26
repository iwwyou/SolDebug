// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Lock {
    struct LockedData {
        uint256 total;            // 총 잠금 금액
        uint256 pending;          // 출금 대기 중
        uint256 estUnlock;        // 분할 해제 예상 금액(1회)
        uint256 unlockedAmounts;  // 이미 해제된 금액
    }

    mapping(address => LockedData) public data;

    uint256 public startLock;                 // 잠금 시작 시각
    uint256 public unlockDuration = 30 days;  // 분할 간격
    uint256 public lockedTime     = 6 * 30 days; // 전체 잠금 기간

    /* ──────────── ✅ 테스트용 Setter ──────────── */

    /// @notice startLock 타임스탬프를 강제로 설정
    function _setStartLock(uint256 timestamp) external {
        startLock = timestamp;
    }

    /// @notice 잠금 파라미터(분할 간격·전체 기간) 변경
    function _setLockParams(uint256 _unlockDuration, uint256 _lockedTime) external {
        unlockDuration = _unlockDuration;
        lockedTime     = _lockedTime;
    }

    /// @notice 특정 계정의 LockedData 구조체를 통째로 주입
    function _setLockedData(
        address account,
        uint256 total,
        uint256 pending_,
        uint256 estUnlock_,
        uint256 unlockedAmounts_
    ) external {
        data[account] = LockedData({
            total: total,
            pending: pending_,
            estUnlock: estUnlock_,
            unlockedAmounts: unlockedAmounts_
        });
    }

    /* ──────────── 원본 로직 ──────────── */
    function pending(address _account) public view returns (uint256 _pending) {
        LockedData memory _data = data[_account];

        uint256 _totalLockRemain = _data.total
                                 - _data.unlockedAmounts
                                 - _data.pending;

        if (_totalLockRemain > 0) {
            if (block.timestamp >= startLock + lockedTime) {
                _pending = _totalLockRemain;
            } else {
                uint256 _nUnlock =
                    (lockedTime - (block.timestamp - startLock) - 1)
                    / unlockDuration
                    + 1;

                _pending = _totalLockRemain - _data.estUnlock * _nUnlock;
            }
        }

        if (_data.pending > 0) {
            _pending += _data.pending;
        }
    }
}
