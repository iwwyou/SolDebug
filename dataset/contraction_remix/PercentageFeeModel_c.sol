// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract PercentageFeeModel {
    uint256 public constant PRECISION = 10**18;
    struct FeeOverride {
        bool isOverridden;
        uint256 fee;
    }

    mapping(address => FeeOverride) public earlyWithdrawFeeOverrideForPool;
    mapping(address => mapping(uint64 => FeeOverride)) public earlyWithdrawFeeOverrideForDeposit;
    uint256 public earlyWithdrawFee;
    
    function getEarlyWithdrawFeeAmount(
        address pool,
        uint64 depositID,
        uint256 withdrawnDepositAmount
    ) external returns (uint256 feeAmount) {
        uint256 feeRate;
        FeeOverride memory feeOverrideForDeposit =
            earlyWithdrawFeeOverrideForDeposit[pool][depositID];
        if (feeOverrideForDeposit.isOverridden) {           
            feeRate = feeOverrideForDeposit.fee;
        } else {
            FeeOverride memory feeOverrideForPool =
                earlyWithdrawFeeOverrideForPool[pool];
            if (feeOverrideForPool.isOverridden) {            
                feeRate = feeOverrideForPool.fee;
            } else {              
                feeRate = earlyWithdrawFee;
            }
        }
        return (withdrawnDepositAmount * feeRate) / PRECISION;
    }
}