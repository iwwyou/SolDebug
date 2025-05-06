contract AloeBlend {
    // @pre-execution-global block.timestamp = 1365487985;

    uint256 public temp;
    uint24 public constant MIN_WIDTH = 201; // 1% of inventory in primary Uniswap position
    uint24 public constant MAX_WIDTH = 13864; // 50% of inventory in primary Uniswap position
    uint8 public constant K = 10;
    uint8 public constant B = 2; // primary Uniswap position should cover 95% of trading activity

    function _getDetailedInventory(uint160 sqrtPriceX96, bool includeLimit)
        private
        view
        returns (
            uint256 inventory0,
            uint256 inventory1,
            uint256 availableForLimit0,
            uint256 availableForLimit1
        )
    {
        // 얘도 범위로 받아야 되나?
        // @pre-execution-state temp = 10;
        // @pre-execution-local sqrtPriceX96 = 10;          

        if (includeLimit) {
            (availableForLimit0, availableForLimit1) = limit.collectableAmountsAsOfLastPoke(UNI_POOL, sqrtPriceX96);
        }
        // Everything in silos + everything in the contract, except maintenance budget
        // @during-execution availableForLimit0 (Before < After)
        // @during-execution availableForLimit0 (Assign < Current),
        // @during-execution returnExpression > 0,
        // @during-execution availableForLimit0 > 0, availableForLimit1 > availableForLimit0
        availableForLimit0 += silo0.balanceOf(address(this)) + _balance0();
        availableForLimit1 += silo1.balanceOf(address(this)) + _balance1();
        // Everything in primary Uniswap position. Limit order is placed without moving this, so its
        // amounts don't get added to availableForLimitX.
        (inventory0, inventory1) = primary.collectableAmountsAsOfLastPoke(UNI_POOL, sqrtPriceX96);
        inventory0 += availableForLimit0;
        inventory1 += availableForLimit1;

        // @post-execution-state k (Entry > Exit)
        // @post-execution-state k > 0
        // @post-execution-return returnValues > 0 (리턴문장이 하나의 함수에서 여러개일 수 있음)
    }
}