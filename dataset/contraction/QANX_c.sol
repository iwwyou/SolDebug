contract QANX {
    struct Lock {
        uint256 tokenAmount;    
        uint32 hardLockUntil;   
        uint32 softLockUntil;   
        uint8 allowedHops;      
        uint32 lastUnlock;      
        uint256 unlockPerSec;   
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