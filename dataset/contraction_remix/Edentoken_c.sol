// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract EdenToken {    
    mapping (address => mapping (address => uint256)) public allowance;
    
    mapping (address => uint256) public balanceOf;

    function _transferTokens(address from, address to, uint256 value) public {
        require(to != address(0), "Eden::_transferTokens: cannot transfer to the zero address");

        balanceOf[from] = balanceOf[from] - value;
        balanceOf[to] = balanceOf[to] + value;        
    }

    function transferFrom(address src, address dst, uint256 amount) external returns (bool) {
        address spender = msg.sender;
        uint256 spenderAllowance = allowance[src][spender];

        if (spender != src && spenderAllowance != type(uint256).max) {
            uint256 newAllowance = spenderAllowance - amount;
            allowance[src][spender] = newAllowance;            
        }

        _transferTokens(src, dst, amount);
        return true;
    }

    // Auto-generated setter for allowance (nested mapping)
    function set_allowance(address _key1, address _key2, uint256 _value) public {
        allowance[_key1][_key2] = _value;
    }

    // Auto-generated setter for balanceOf
    function set_balanceOf(address _key, uint256 _value) public {
        balanceOf[_key] = _value;
    }

}