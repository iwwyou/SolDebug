// SPDX-License-Identifier: MIT
pragma solidity ^0.8.0;

contract AvatarArtMarketplace {
    uint256[] internal _tokens;

    function _removeFromTokens(uint tokenId) internal view returns(uint256[] memory){
        // @Param _tokens = array [1, 2, 3]; tokenId = [4, 4]
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
}
