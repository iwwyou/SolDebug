contract Claim {
    mapping(address => uint256) public claimable;

    uint256 locktime;
    uint256 startTime = 0;

    function getCurrentClaimAmount(address user) public view returns (uint256) {
        if (!claimedOnce[user] && block.timestamp < (startTime + locktime)) {
            return (claimable[user] * 30) / 100;
        } else if (block.timestamp >= (startTime + locktime)) {
            return claimable[user];
        }
        return 0;
    }

}