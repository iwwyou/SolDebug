// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Core {
    /* ──────────── 상태 변수 ──────────── */
    mapping(address => bool) public governorMap;
    address[] internal _stablecoinList;

    /* ────────────  ✅ 테스트용 Setter ──────────── */

    /// @notice governor 권한 부여 (테스트 전용)
    function _addGovernor(address governor) external {
        governorMap[governor] = true;
    }

    /// @notice governor 권한 회수 (테스트 전용)
    function _removeGovernor(address governor) external {
        governorMap[governor] = false;
    }

    /// @notice stable master 주소를 목록에 추가 (테스트 전용)
    function _pushStableMaster(address stableMaster) external {
        _stablecoinList.push(stableMaster);
    }

    /* ────────────  권한 제어 ──────────── */
    modifier onlyGovernor() {
        require(governorMap[msg.sender], "1"); // "1" = not governor
        _;
    }

    /* ────────────  원본 로직 ──────────── */
    function revokeStableMaster(address stableMaster)
        external
        onlyGovernor
    {
        uint256 stablecoinListLength = _stablecoinList.length;
        require(stablecoinListLength >= 1, "45"); // "45" = empty list

        uint256 indexMet;
        for (uint256 i = 0; i < stablecoinListLength - 1; i++) {
            if (_stablecoinList[i] == stableMaster) {
                indexMet = 1;
                _stablecoinList[i] = _stablecoinList[stablecoinListLength - 1];
                break;
            }
        }
        require(
            indexMet == 1 || _stablecoinList[stablecoinListLength - 1] == stableMaster,
            "45"
        );
        _stablecoinList.pop();
    }

    /* ────────────  편의 함수 (선택) ──────────── */
    function stablecoinList() external view returns (address[] memory) {
        return _stablecoinList;
    }
}
