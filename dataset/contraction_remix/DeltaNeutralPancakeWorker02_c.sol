// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract DeltaNeutralPancakeWorker02 {
    address public wNative;
    address public cake;
    address public baseToken;
    address[] public reinvestPath;
    
    function getReinvestPath() public returns (address[] memory) {
        if (reinvestPath.length != 0) {
            return reinvestPath;
        }
        address[] memory path;
        if (baseToken == wNative) {
            path = new address[](2);
            path[0] = address(cake);
            path[1] = address(wNative);
        } else {
            path = new address[](3);
            path[0] = address(cake);
            path[1] = address(wNative);
            path[2] = address(baseToken);
        }
        return path;
    }    

    // Auto-generated setter for wNative
    function set_wNative(address _value) public {
        wNative = _value;
    }

    // Auto-generated setter for cake
    function set_cake(address _value) public {
        cake = _value;
    }

    // Auto-generated setter for baseToken
    function set_baseToken(address _value) public {
        baseToken = _value;
    }

    // Auto-generated setter for reinvestPath (array)
    function _addReinvestPathAt(address _value, uint256 _index) public {
        if (_index >= reinvestPath.length) {
            reinvestPath.push(_value);
        } else {
            reinvestPath[_index] = _value;
        }
    }
}