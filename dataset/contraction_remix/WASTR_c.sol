// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract WASTLR {
    mapping (address => uint256) public balanceOf;
    mapping (address => mapping (address => uint256)) public allowance;
    
    function withdrawFrom(address from, address payable to, uint256 value) external {
        if (from != msg.sender) {         
            uint256 allowed = allowance[from][msg.sender];
            if (allowed != type(uint256).max) {
                require(allowed >= value, "WASTR: request exceeds allowance");
                uint256 reduced = allowed - value;
                allowance[from][msg.sender] = reduced;             
            }
        }        
     
        uint256 balance = balanceOf[from];
        require(balance >= value, "WASTR: burn amount exceeds balance");
        balanceOf[from] = balance - value; 
             
        (bool success, ) = to.call{value: value}("");
        require(success, "WASTR: Ether transfer failed");
    }
}