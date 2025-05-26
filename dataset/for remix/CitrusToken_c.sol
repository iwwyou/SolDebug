// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract BEP20 {
    mapping(address => uint256) public balances;
    mapping(address => mapping(address => uint256)) public allowed;

    /* ======== ✨ 테스트용 Setter 함수 ======== */

    /// @notice 테스트 편의를 위해 임의로 balance를 설정합니다.
    /// @dev 실제 운영 시에는 삭제하거나 onlyOwner로 보호하세요.
    function _setBalance(address account, uint256 amount) external {
        balances[account] = amount;
    }

    /// @notice owner → spender 에 대한 allowance를 설정합니다.
    /// @dev 실제 운영 시에는 삭제하거나 onlyOwner로 보호하세요.
    function _setAllowance(address owner, address spender, uint256 amount) external {
        allowed[owner][spender] = amount;
    }

    /* ======== 원본 transferFrom ======== */

    function transferFrom(
        address _from,
        address _to,
        uint256 _amount
    ) public returns (bool success) {
        require(
            balances[_from] >= _amount &&
            allowed[_from][msg.sender] >= _amount &&
            _amount > 0 &&
            balances[_to] + _amount > balances[_to],
            "transferFrom: pre-condition failed"
        );

        balances[_from] -= _amount;
        allowed[_from][msg.sender] -= _amount;
        balances[_to]   += _amount;
        return true;
    }
}
