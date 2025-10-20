// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract AvatarArtMarketplace {
    uint256[] public _tokens;
    
    function _removeFromTokens(uint tokenId) public returns(uint256[] memory){
        uint256 tokenCount = _tokens.length;
        uint256[] memory result = new uint256[](tokenCount);
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

    function _addTokensAt(uint256 _value, uint256 _index) public {
        if (_index >= _tokens.length) {
            _tokens.push(_value);
        } else {
            _tokens[_index] = _value;
        }
    }
}