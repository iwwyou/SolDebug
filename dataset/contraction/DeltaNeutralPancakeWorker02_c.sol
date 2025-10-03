contract DeltaNeutralPancakeWorker02 {
    address public wNative;
    address public cake;
    address public override baseToken;
    address[] public reinvestPath;
    
    function getReinvestPath() public view returns (address[] memory) {
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
}