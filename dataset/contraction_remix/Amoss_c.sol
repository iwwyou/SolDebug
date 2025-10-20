// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract Amoss {
    uint256 public _totalSupply = 1*10**(9+18);    
    mapping(address => uint256) public _balances;    

    function _beforeTokenTransfer(address from, address to, uint256 amount) public virtual {        
    }

    function _afterTokenTransfer(address from, address to, uint256 amount) public virtual {        
    }

    function _burn(address account, uint256 amount) public virtual {
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

    

    

    // Auto-generated setter for _balances (mapping)
    function set__balances(address _key, uint256 _value) public {
        _balances[_key] = _value;
    }

    // Auto-generated setter for _totalSupply
    function set__totalSupply(uint256 _value) public {
        _totalSupply = _value;
    }
}