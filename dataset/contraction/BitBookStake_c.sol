contract BitBookStake {
    mapping(uint256 => mapping(uint256 => uint256)) private getPercentage;
    
    function viewFeePercentage(uint256 _from,uint256 _to)public view returns(uint256){
        require((_from == 1 && _to == 3) || (_from == 3 && _to == 10) || (_from == 10 && _to == 30) || (_from == 30 && _to == 90) ,"BitBook stake :: give correct days pair" );
        return getPercentage[_from][_to];
    }
}