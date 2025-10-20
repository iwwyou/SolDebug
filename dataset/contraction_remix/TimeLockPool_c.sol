// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract TimeLockPool {
    
    struct Deposit {
        uint256 amount;
        uint64 start;
        uint64 end;
    }

    mapping(address => Deposit[]) public depositsOf;

    function _addDepositsOfAt(address _account, uint256 _amount, uint64 _start, uint64 _end, uint256 index) public {
        uint256 currentLength = depositsOf[_account].length;

        if (currentLength == 0 || currentLength - 1 < index) {
            uint256 additionalCount = index - currentLength + 1;
            for (uint8 i = 0; i < additionalCount; i++) {
                depositsOf[_account].push();
            }
        }
        depositsOf[_account][index].amount = _amount;
        depositsOf[_account][index].start = _start;
        depositsOf[_account][index].end = _end;
    }

    function getTotalDeposit(address _account) public returns(uint256) {
        uint256 total;
        for(uint256 i = 0; i < depositsOf[_account].length; i++) {
            total += depositsOf[_account][i].amount;
        }
        return total;
    }
    
}