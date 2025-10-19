// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract TimeLockPool {
    
    struct Deposit {
        uint256 amount;
        uint64 start;
        uint64 end;
    }

    mapping(address => Deposit[]) public depositsOf;
    
    function getTotalDeposit(address _account) public returns(uint256) {
        uint256 total;
        for(uint256 i = 0; i < depositsOf[_account].length; i++) {
            total += depositsOf[_account][i].amount;
        }
        return total;
    }
}