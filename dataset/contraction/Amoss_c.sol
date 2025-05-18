contract Amoss {
    uint256 private _totalSupply = 1*10**(9+18);    
    mapping(address => uint256) private _balances;    

    function _beforeTokenTransfer(address from, address to, uint256 amount) internal virtual {        
    }

    function _afterTokenTransfer(address from, address to, uint256 amount) internal virtual {        
    }

    function _burn(address account, uint256 amount) internal virtual {
        require(account != address(0), "ERC20: burn from the zero address");
        _beforeTokenTransfer(account, address(0), amount);
        uint256 accountBalance = _balances[account];
        require(accountBalance >= amount, "ERC20: burn amount exceeds balance");
        unchecked {
            _balances[account] = accountBalance - amount;
        }
        _totalSupply -= amount;
        _afterTokenTransfer(account, address(0), amount);
    }
}