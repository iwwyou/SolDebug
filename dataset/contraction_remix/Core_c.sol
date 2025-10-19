// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract Core {
    mapping(address => bool) public governorMap;

    address[] public _stablecoinList;

    modifier onlyGovernor() {
        require(governorMap[msg.sender], "1");
        _;
    }

    function revokeStableMaster(address stableMaster) external onlyGovernor {
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

    // Auto-generated setter for array _stablecoinList
    function _addStablecoinListAt(address _value, uint256 _index) public {
        uint256 currentLength = _stablecoinList.length;

        if (currentLength == 0 || currentLength - 1 < _index) {
            uint256 additionalCount = _index - currentLength + 1;
            for (uint256 i = 0; i < additionalCount; i++) {
                _stablecoinList.push();
            }
        }
        _stablecoinList[_index] = _value;
    }

}