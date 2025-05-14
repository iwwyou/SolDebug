contract PoolKeeper {
    uint256 public constant BASE_TIP = 5; // 5% base tip
    uint256 public constant TIP_DELTA_PER_BLOCK = 5; // 5% increase per block
    uint256 public constant BLOCK_TIME = 13; /* in seconds */    
    uint256 public constant MAX_TIP = 100; /* maximum keeper tip */
    
    function keeperTip(uint256 _savedPreviousUpdatedTimestamp, uint256 _poolInterval) public view returns (uint256) {
        /* the number of blocks that have elapsed since the given pool's updateInterval passed */
        uint256 elapsedBlocksNumerator = (block.timestamp - (_savedPreviousUpdatedTimestamp + _poolInterval));

        uint256 keeperTip = BASE_TIP + (TIP_DELTA_PER_BLOCK * elapsedBlocksNumerator) / BLOCK_TIME;

        // In case of network outages or otherwise, we want to cap the tip so that the keeper cost isn't unbounded
        if (keeperTip > MAX_TIP) {
            return MAX_TIP;
        } else {
            return keeperTip;
        }
    }
}