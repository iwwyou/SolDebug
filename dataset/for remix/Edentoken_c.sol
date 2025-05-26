// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract EdenToken {
    /* ──────────── 원본 상태 변수 ──────────── */
    uint256 public totalSupply;

    mapping(address => mapping(address => uint256)) public allowance;
    mapping(address => uint256) public balanceOf;

    /* ──────────── ✅ 테스트용 Setter ──────────── */

    /// @notice 임의 주소의 잔액을 강제로 설정 (테스트 전용)
    function _setBalance(address account, uint256 amount) external {
        balanceOf[account] = amount;
    }

    /// @notice owner → spender 허용량을 강제로 설정 (테스트 전용)
    function _setAllowance(address owner, address spender, uint256 amount) external {
        allowance[owner][spender] = amount;
    }

    /* ──────────── 내부 전송 로직 ──────────── */
    function _transferTokens(address from, address to, uint256 value) internal {
        require(to != address(0), "Eden::_transferTokens: cannot transfer to the zero address");

        balanceOf[from] = balanceOf[from] - value;
        balanceOf[to]   = balanceOf[to]   + value;
    }

    /* ──────────── 외부 전송 함수 ──────────── */
    function transferFrom(address src, address dst, uint256 amount) external returns (bool) {
        address spender = msg.sender;
        uint256 currentAllowance = allowance[src][spender];

        if (spender != src && currentAllowance != type(uint256).max) {
            allowance[src][spender] = currentAllowance - amount;
        }

        _transferTokens(src, dst, amount);
        return true;
    }
}
