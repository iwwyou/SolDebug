// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract BEP20 {
    mapping (address=>uint256) balances;    

    mapping (address=>mapping (address=>uint256)) allowed;

    function transferFrom(address _from,address _to,uint256 _amount) public returns (bool success) {
        require (balances[_from]>=_amount&&allowed[_from][msg.sender]>=_amount&&_amount>0&&balances[_to]+_amount>balances[_to]);
        balances[_from]-=_amount;
        allowed[_from][msg.sender]-=_amount;
        balances[_to]+=_amount;        
        return true;
    }    

    // Auto-generated setter for allowed (nested mapping)
    function set_allowed(address _key1, address _key2, uint256 _value) public {
        allowed[_key1][_key2] = _value;
    }

    // Auto-generated setter for balances (mapping)
    function set_balances(address _key, uint256 _value) public {
        balances[_key] = _value;
    }
}