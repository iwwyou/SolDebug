contract Core {
    mapping(address => bool) public governorMap;

    address[] internal _stablecoinList;

    modifier onlyGovernor() {
        require(governorMap[msg.sender], "1");
        _;
    }

    function revokeStableMaster(address stableMaster) external override onlyGovernor {
        uint256 stablecoinListLength = _stablecoinList.length;
        
        require(stablecoinListLength >= 1, "45");
        uint256 indexMet;
        for (uint256 i = 0; i < stablecoinListLength - 1; i++) {
            if (_stablecoinList[i] == stableMaster) {
                indexMet = 1;
                _stablecoinList[i] = _stablecoinList[stablecoinListLength - 1];
                break;
            }
        }
        require(indexMet == 1 || _stablecoinList[stablecoinListLength - 1] == stableMaster, "45");
        _stablecoinList.pop();        
    }
}