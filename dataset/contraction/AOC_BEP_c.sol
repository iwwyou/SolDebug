contract AOC_BEP {
    struct UserInfo {
        uint256 balance;
        uint256 level;
        uint256 year;
        uint256 month;
    }

    struct Level {
        uint256 start;
        uint256 end;
        uint256 percentage;
    }

    mapping(address => UserInfo) public userInfo;
    mapping(uint256 => Level) public levels;

    uint256 private _totalSupply;

    function updateUserInfo(address account, uint256 year, uint256 month) internal {
        userInfo[account].balance = _balances[account];
        userInfo[account].year = year;
        userInfo[account].month = month;
        for(uint256 i = 1; i <= 4; i++) {
            if(i == 4) {
                userInfo[account].level = i;
                break;
            }
            if(block.timestamp >= levels[i].start && block.timestamp <= levels[i].end) {
                userInfo[account].level = i;
                break;
            }
        }
    }

    function _mint(address account, uint256 amount) internal virtual {
        require(account != address(0), "BEP20: mint to the zero address");
        _totalSupply += amount;
        _balances[account] += amount;        
    }

    function _burn(address account, uint256 amount) internal virtual {
        require(account != address(0), "BEP20: burn from the zero address");
        uint256 accountBalance = _balances[account];
        require(accountBalance >= amount, "BEP20: burn amount exceeds balance");
        _balances[account] = accountBalance - amount;
        _totalSupply -= amount;        
    }
}
