// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract Lock {
    struct LockedData {
        uint256 total;
        uint256 pending;
        uint256 estUnlock;
        uint256 unlockedAmounts;
    }

    mapping(address => LockedData) public data;
    uint256 public startLock;
    uint256 public unlockDuration = 30 days;
    uint256 public lockedTime = 6 * 30 days;

    function pending(address _account) public returns(uint256 _pending) {
        LockedData memory _data = data[_account];
        uint256 _totalLockRemain =  _data.total - _data.unlockedAmounts - _data.pending;
        if (_totalLockRemain > 0) {
            if (block.timestamp >= startLock + lockedTime) {
                _pending = _totalLockRemain;
            } 
            else {
                uint256 _nUnlock = (lockedTime - (block.timestamp - startLock) - 1) / unlockDuration + 1;
                _pending = _totalLockRemain - _data.estUnlock * _nUnlock;
            }
        }
        if (_data.pending > 0) {
            _pending += _data.pending;
        }
    }

    // Auto-generated setter for startLock
    function set_startLock(uint256 _value) public {
        startLock = _value;
    }

    // Auto-generated setter for unlockDuration
    function set_unlockDuration(uint256 _value) public {
        unlockDuration = _value;
    }

    // Auto-generated setter for lockedTime
    function set_lockedTime(uint256 _value) public {
        lockedTime = _value;
    }
}

