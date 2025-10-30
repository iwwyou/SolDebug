function _allocateLpAndProtocolFees(address l1Token, uint256 bundleLpFees) internal {
    uint256 protocolFeesCaptured = (bundleLpFees * protocolFeeCapturePct) / 1e18;
    uint256 lpFeesCaptured = bundleLpFees - protocolFeesCaptured;

    if (lpFeesCaptured > 0) {
        pooledTokens[l1Token].undistributedLpFees += lpFeesCaptured;
        pooledTokens[l1Token].utilizedReserves += int256(lpFeesCaptured);
    }

    if (protocolFeesCaptured > 0)  {
        unclaimedAccumulatedProtocolFees[l1Token] += protocolFeesCaptured;
    }
}
