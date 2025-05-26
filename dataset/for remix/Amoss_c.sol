// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Amoss {
    /* ────────── 원본 상태 변수 ────────── */
    uint256 private _totalSupply = 1 * 10 ** (9 + 18); // 1 billion * 10¹⁸
    mapping(address => uint256) private _balances;

    /* ────────── ✅ 테스트용 Setter ────────── */

    /// @notice 임의 주소의 잔액을 강제로 설정 (테스트 전용)
    function _setBalance(address account, uint256 amount) external {
        _balances[account] = amount;
    }

    /// @notice totalSupply 값까지 강제로 맞춰야 할 때 사용 (옵션)
    function _setTotalSupply(uint256 amount) external {
        _totalSupply = amount;
    }

    /* ────────── 원본 내부 훅 ────────── */
    function _beforeTokenTransfer(address from, address to, uint256 amount) internal virtual {}
    function _afterTokenTransfer(address from, address to, uint256 amount) internal virtual {}

    /* ────────── 원본 burn 로직 ────────── */
    function _burn(address account, uint256 amount) internal virtual {
        require(account != address(0), "ERC20: burn from the zero address");

        _beforeTokenTransfer(account, address(0), amount);

        uint256 accountBalance = _balances[account];
        require(accountBalance >= amount, "ERC20: burn amount exceeds balance");

        unchecked {
            _balances[account] = accountBalance - amount;
        }
        _totalSupply -= amount;

        _afterTokenTransfer(account, address(0), amount);
    }
}
