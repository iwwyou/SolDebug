contract QANX {
    struct Lock {
        uint256 tokenAmount;    // HOW MANY TOKENS ARE LOCKED
        uint32 hardLockUntil;   // UNTIL WHEN NO LOCKED TOKENS CAN BE ACCESSED
        uint32 softLockUntil;   // UNTIL WHEN LOCKED TOKENS CAN BE GRADUALLY RELEASED
        uint8 allowedHops;      // HOW MANY TRANSFERS LEFT WITH SAME LOCK PARAMS
        uint32 lastUnlock;      // LAST GRADUAL UNLOCK TIME (SOFTLOCK PERIOD)
        uint256 unlockPerSec;   // HOW MANY TOKENS ARE UNLOCKABLE EACH SEC FROM HL -> SL
    }

    mapping (address => Lock) private _locks;
    
    function unlockableBalanceOf(address account) public view virtual returns (uint256) {
        if(block.timestamp < _locks[account].hardLockUntil) {
            return 0;
        }
        
        if(block.timestamp > _locks[account].softLockUntil) {
            return _locks[account].tokenAmount;
        }
        
        return (block.timestamp - _locks[account].lastUnlock) * _locks[account].unlockPerSec;
    }

    function unlock(address account) external returns (bool) {        
        uint256 unlockable = unlockableBalanceOf(account);
        
        require(unlockable > 0 && _locks[account].tokenAmount > 0 && block.timestamp > _locks[account].hardLockUntil, "No unlockable tokens!");
        
        _locks[account].lastUnlock = uint32(block.timestamp);
        _locks[account].tokenAmount = _locks[account].tokenAmount - unlockable;
        _balances[account] = _balances[account] + unlockable;
        
        if(_locks[account].tokenAmount == 0){
            delete _locks[account];            
        }
       
        return true;
    }
}