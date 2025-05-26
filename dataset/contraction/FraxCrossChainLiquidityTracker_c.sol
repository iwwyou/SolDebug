contract FraxCrossChainLiquidityTracker {
    uint256[] public chain_ids_array;   

    mapping(uint256 => uint256) public frax_minted; 
    mapping(uint256 => uint256) public fxs_minted; 
    mapping(uint256 => uint256) public collat_bridged;   
    
    function totalsAcrossChains() public view returns (uint256 frax_tally, uint256 fxs_tally, uint256 collat_tally) {
        for (uint256 i = 0; i < chain_ids_array.length; i++){
            uint256 chain_id = chain_ids_array[i];
            frax_tally += frax_minted[chain_id];
            fxs_tally += fxs_minted[chain_id];
            collat_tally += collat_bridged[chain_id];
        }
    }
}