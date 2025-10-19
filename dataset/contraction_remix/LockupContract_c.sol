// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract LockupContract {
    uint constant public SECONDS_IN_ONE_MONTH = 2628000;
    uint public initialAmount;
    uint public deploymentStartTime;
    uint public monthsToWaitBeforeUnlock;
    uint public releaseSchedule;
    
    function _getReleasedAmount() public returns (uint) {
        uint unlockTimestamp = deploymentStartTime + (monthsToWaitBeforeUnlock * SECONDS_IN_ONE_MONTH);
        if (block.timestamp < unlockTimestamp) {
            return 0;
        }
        uint monthsSinceUnlock = ((block.timestamp - unlockTimestamp) / SECONDS_IN_ONE_MONTH) + 1;
        uint monthlyReleaseAmount = initialAmount / releaseSchedule;
        uint releasedAmount = monthlyReleaseAmount * monthsSinceUnlock;
        
        if (releasedAmount > initialAmount){
            return initialAmount;
        }

        return releasedAmount;
    }

    // Setter for initialAmount
    function set_initialAmount(uint _value) public {
        initialAmount = _value;
    }

    // Setter for deploymentStartTime
    function set_deploymentStartTime(uint _value) public {
        deploymentStartTime = _value;
    }

    // Setter for monthsToWaitBeforeUnlock
    function set_monthsToWaitBeforeUnlock(uint _value) public {
        monthsToWaitBeforeUnlock = _value;
    }

    // Setter for releaseSchedule
    function set_releaseSchedule(uint _value) public {
        releaseSchedule = _value;
    }
}