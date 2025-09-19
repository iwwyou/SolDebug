contract Balancer {
    address[] public actionBuilders;
    
    function _addActionBuilderAt(address actionBuilder, uint256 index) internal {
        uint256 currentLength = actionBuilders.length;
        
        if (currentLength == 0 || currentLength - 1 < index) {
            uint256 additionalCount = index - currentLength + 1;
            for (uint8 i = 0; i < additionalCount; i++) {
                actionBuilders.push();                
            }
        }
        actionBuilders[index] = actionBuilder;       
    }
}