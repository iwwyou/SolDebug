// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract DapiServer {
    uint256 public constant HUNDRED_PERCENT = 1e8;

    function calculateUpdateInPercentage(int224 initialValue, int224 updatedValue) public pure returns (uint256 updateInPercentage) {
        int256 delta = int256(updatedValue) - int256(initialValue);
        uint256 absoluteDelta = delta > 0 ? uint256(delta) : uint256(-delta);
        uint256 absoluteInitialValue = initialValue > 0 ? uint256(int256(initialValue)) : uint256(-int256(initialValue));
        
        if (absoluteInitialValue == 0) {
            absoluteInitialValue = 1;
        }
        updateInPercentage = (absoluteDelta * HUNDRED_PERCENT) / absoluteInitialValue;
    }
}