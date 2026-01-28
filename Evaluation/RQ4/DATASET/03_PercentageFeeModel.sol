// Problem 3: PercentageFeeModel (Complexity: Medium-High)
// Nested if-else + arithmetic
// Original: dataset/contraction/PercentageFeeModel_c.sol

function getEarlyWithdrawFeeAmount(
    uint256 withdrawnAmount,
    bool isDepositOverridden,
    uint256 depositFee,
    bool isPoolOverridden,
    uint256 poolFee,
    uint256 defaultFee
) returns (uint256 feeAmount) {
    uint256 feeRate;

    if (isDepositOverridden) {
        feeRate = depositFee;
    } else {
        if (isPoolOverridden) {
            feeRate = poolFee;
        } else {
            feeRate = defaultFee;
        }
    }

    feeAmount = (withdrawnAmount * feeRate) / 1000;
}

/*
[Input]
withdrawnAmount = 2450
isDepositOverridden = false
depositFee = 50
isPoolOverridden = true
poolFee = 35
defaultFee = 25

[Question] What is the return value (feeAmount)?

[Solution]
isDepositOverridden = false, so go to else branch
  isPoolOverridden = true, so:
    feeRate = poolFee = 35

feeAmount = (2450 * 35) / 1000 = 85750 / 1000 = 85

[Answer] 85
*/
