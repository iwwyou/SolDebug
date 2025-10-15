// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract BitBookStake {
    mapping(uint256 => mapping(uint256 => uint256)) public getPercentage;
    
    function viewFeePercentage(uint256 _from,uint256 _to)public view returns(uint256){
        require((_from == 1 && _to == 3) || (_from == 3 && _to == 10) || (_from == 10 && _to == 30) || (_from == 30 && _to == 90) ,"BitBook stake :: give correct days pair" );
        return getPercentage[_from][_to];
    }


    // Auto-generated setter for getPercentage (nested mapping)
    function set_getPercentage(uint256 _key1, uint256 _key2, uint256 _value) public {
        getPercentage[_key1][_key2] = _value;
    }
}