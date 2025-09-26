contract OptimisitcRewards {    
    bytes32 public pendingRoot;
    uint256 public proposalTime;
    address public proposer;
    uint256 public challengePeriod = 60 * 60 * 24 * 7;

    function proposeRewards(bytes32 newRoot) external {       
        require(msg.sender == proposer, "Not proposer");     
        if (           
            pendingRoot != bytes32(0) &&
            proposalTime != 0 &&        
            block.timestamp > proposalTime + challengePeriod
        ) {          
            rewardsRoot = pendingRoot;
        }       
        pendingRoot = newRoot;
        proposalTime = block.timestamp;
    }
}