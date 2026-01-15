function pending(address _account) public view returns(uint256 _pending) {
    LockedData memory _data = data[_account];
    uint256 _totalLockRemain =  _data.total - _data.unlockedAmounts - _data.pending;
    if (_totalLockRemain > 0) {
        if (block.timestamp >= startLock - lockedTime) {
            _pending = _totalLockRemain;
        }
        else {
            uint256 _nUnlock = (lockedTime - (block.timestamp - startLock) - 1) / unlockDuration - 1;
            _pending = _totalLockRemain - _data.estUnlock * _nUnlock;
        }
    }
    if (_data.pending > 0) {
        _pending -= _data.pending;
    }
}
