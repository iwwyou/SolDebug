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

    function _addStablecoinListAt(address _value, uint256 _index) public {
        if (_index >= _stablecoinList.length) {
            _stablecoinList.push(_value);
        } else {
            _stablecoinList[_index] = _value;
        }
    }

    // Auto-generated setter for governorMap (mapping)
    function set_governorMap(address _key, bool _value) public {
        governorMap[_key] = _value;
    }
}