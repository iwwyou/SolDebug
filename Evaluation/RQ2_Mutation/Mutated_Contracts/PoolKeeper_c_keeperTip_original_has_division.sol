function keeperTip(uint256 _savedPreviousUpdatedTimestamp, uint256 _poolInterval) public view returns (uint256) {
    uint256 elapsedBlocksNumerator = (block.timestamp - (_savedPreviousUpdatedTimestamp + _poolInterval));

    uint256 keeperTip = BASE_TIP + (TIP_DELTA_PER_BLOCK * elapsedBlocksNumerator) / BLOCK_TIME;

    if (keeperTip > MAX_TIP) {
        return MAX_TIP;
    } else {
        return keeperTip;
    }
}
