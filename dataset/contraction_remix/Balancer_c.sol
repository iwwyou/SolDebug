// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract Balancer {
    address[] public actionBuilders;
    
    function _addActionBuilderAt(address actionBuilder, uint256 index) public {
        uint256 currentLength = actionBuilders.length;
        
        if (currentLength == 0 || currentLength - 1 < index) {
            uint256 additionalCount = index - currentLength + 1;
            for (uint8 i = 0; i < additionalCount; i++) {
                actionBuilders.push();                
            }
        }
        actionBuilders[index] = actionBuilder;       
    }

    // Auto-generated setter for array actionBuilders
    function _addActionBuildersAt(address _value, uint256 _index) public {
        uint256 currentLength = actionBuilders.length;

        if (currentLength == 0 || currentLength - 1 < _index) {
            uint256 additionalCount = _index - currentLength + 1;
            for (uint256 i = 0; i < additionalCount; i++) {
                actionBuilders.push();
            }
        }
        actionBuilders[_index] = _value;
    }

}