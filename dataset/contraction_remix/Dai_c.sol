// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract Dai {
    mapping (address => uint) public wards;
    
    uint256 public totalSupply;
    mapping (address => uint) public balanceOf;
    mapping (address => mapping (address => uint)) public allowance;    
    
    function add(uint x, uint y) public returns (uint z) {
        require((z = x + y) >= x);
    }
    function sub(uint x, uint y) public returns (uint z) {
        require((z = x - y) <= x);
    }

    function transferFrom(address src, address dst, uint wad) public returns (bool) {
        require(balanceOf[src] >= wad, "Dai/insufficient-balance");
        if (src != msg.sender && allowance[src][msg.sender] != type(uint256).max) {
            require(allowance[src][msg.sender] >= wad, "Dai/insufficient-allowance");
            allowance[src][msg.sender] = sub(allowance[src][msg.sender], wad);
        }
        balanceOf[src] = sub(balanceOf[src], wad);
        balanceOf[dst] = add(balanceOf[dst], wad);
       
        return true;
    }
    

    

    

    

    // Auto-generated setter for allowance (nested mapping)
    function set_allowance(address _key1, address _key2, uint _value) public {
        allowance[_key1][_key2] = _value;
    }

    // Auto-generated setter for wards (mapping)
    function set_wards(address _key, uint _value) public {
        wards[_key] = _value;
    }

    // Auto-generated setter for balanceOf (mapping)
    function set_balanceOf(address _key, uint _value) public {
        balanceOf[_key] = _value;
    }

    // Auto-generated setter for totalSupply
    function set_totalSupply(uint256 _value) public {
        totalSupply = _value;
    }
}