// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract CoreVoting {
    uint256 public baseQuorum;
    mapping(address => mapping(bytes4 => uint256)) public _quorums;
    
    function quorums(address target, bytes4 functionSelector)
        public returns (uint256)
    {
        uint256 storedQuorum = _quorums[target][functionSelector];

        if (storedQuorum == 0) {
            return baseQuorum;
        } else {
            return storedQuorum;
        }
    }

    // Auto-generated setter for baseQuorum
    function set_baseQuorum(uint256 _value) public {
        baseQuorum = _value;
    }

    // Auto-generated setter for _quorums (nested mapping)
    function set__quorums(address _key1, bytes4 _key2, uint256 _value) public {
        _quorums[_key1][_key2] = _value;
    }
}