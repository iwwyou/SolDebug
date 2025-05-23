contract EdenToken {
    uint256 public override totalSupply;
    
    mapping (address => mapping (address => uint256)) public override allowance;
    
    mapping (address => uint256) public override balanceOf;

    function _transferTokens(address from, address to, uint256 value) internal {
        require(to != address(0), "Eden::_transferTokens: cannot transfer to the zero address");

        balanceOf[from] = balanceOf[from] - value;
        balanceOf[to] = balanceOf[to] + value;        
    }

    function transferFrom(address src, address dst, uint256 amount) external override returns (bool) {
        address spender = msg.sender;
        uint256 spenderAllowance = allowance[src][spender];

        if (spender != src && spenderAllowance != type(uint256).max) {
            uint256 newAllowance = spenderAllowance - amount;
            allowance[src][spender] = newAllowance;            
        }

        _transferTokens(src, dst, amount);
        return true;
    }
}