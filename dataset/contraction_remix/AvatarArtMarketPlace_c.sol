// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract AvatarArtMarketplace {
    uint256[] public _tokens;
    
    function _removeFromTokens(uint tokenId) public view returns(uint256[] memory){
        uint256 tokenCount = _tokens.length;
        uint256[] memory result = new uint256[](tokenCount-1);
        uint256 resultIndex = 0;
        for(uint tokenIndex = 0; tokenIndex < tokenCount; tokenIndex++){
            uint tokenItemId = _tokens[tokenIndex];
            if(tokenItemId != tokenId){
                result[resultIndex] = tokenItemId;
                resultIndex++;
            }
        }
        
        return result;
    }

    // Auto-generated setter for array _tokens
    function _addTokensAt(uint256 _value, uint256 _index) public {
        uint256 currentLength = _tokens.length;

        if (currentLength == 0 || currentLength - 1 < _index) {
            uint256 additionalCount = _index - currentLength + 1;
            for (uint256 i = 0; i < additionalCount; i++) {
                _tokens.push();
            }
        }
        _tokens[_index] = _value;
    }

}