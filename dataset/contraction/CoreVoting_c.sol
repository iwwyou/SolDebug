contract CoreVoting {
    uint256 public baseQuroum;

    mapping(address => mapping(bytes4 => uint256)) private _quorums;

    function quorums(address target, bytes4 functionSelector) public view returns (uint256) {
        uint256 storedQuorum = _quorums[target][functionSelector];

        if (storedQuorum == 0) {
            return baseQuorum;
        } else {
            return storedQuorum;
        }
    }
}