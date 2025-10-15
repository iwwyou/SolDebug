// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract Dripper {
    struct Drip {
        uint64 lastCollect; 
        uint192 perBlock; 
    }
    
    function _availableFunds(uint256 _balance, Drip memory _drip)
        public
        view
        returns (uint256)
    {
        uint256 elapsed = block.timestamp - _drip.lastCollect;
        uint256 allowed = (elapsed * _drip.perBlock);
        return (allowed > _balance) ? _balance : allowed;
    }
}