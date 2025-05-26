// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract FraxCrossChainLiquidityTracker {
    /* ──────────── 원본 상태 변수 ──────────── */
    uint256[] public chain_ids_array;
    mapping(uint256 => bool) public valid_chains;

    mapping(uint256 => uint256) public frax_minted;
    mapping(uint256 => uint256) public fxs_minted;
    mapping(uint256 => uint256) public collat_bridged;

    /* ──────────── ✅ 테스트용 Setter & 관리 함수 ──────────── */

    /// @notice 체인 ID를 배열에 추가하고 valid_chains 플래그를 동시에 설정
    function _addChain(uint256 chainId) external {
        require(!valid_chains[chainId], "chain already exists");
        chain_ids_array.push(chainId);
        valid_chains[chainId] = true;
    }

    /// @notice 체인 ID를 배열에서 제거하고 플래그도 해제
    function _removeChain(uint256 chainId) external {
        require(valid_chains[chainId], "chain not found");

        uint256 len = chain_ids_array.length;
        for (uint256 i = 0; i < len; i++) {
            if (chain_ids_array[i] == chainId) {
                // 마지막 요소와 스왑 후 pop
                chain_ids_array[i] = chain_ids_array[len - 1];
                chain_ids_array.pop();
                break;
            }
        }
        valid_chains[chainId] = false;
    }

    /// @notice 특정 체인에서 발행된 FRAX, FXS, Collat 값을 직접 설정
    function _setChainLiquidity(
        uint256 chainId,
        uint256 fraxAmt,
        uint256 fxsAmt,
        uint256 collatAmt
    ) external {
        require(valid_chains[chainId], "invalid chain");

        frax_minted[chainId]   = fraxAmt;
        fxs_minted[chainId]    = fxsAmt;
        collat_bridged[chainId] = collatAmt;
    }

    /* ──────────── 조회 함수 (원본) ──────────── */
    function totalsAcrossChains()
        public
        view
        returns (
            uint256 frax_tally,
            uint256 fxs_tally,
            uint256 collat_tally
        )
    {
        for (uint256 i = 0; i < chain_ids_array.length; i++) {
            uint256 chainId = chain_ids_array[i];
            frax_tally   += frax_minted[chainId];
            fxs_tally    += fxs_minted[chainId];
            collat_tally += collat_bridged[chainId];
        }
    }
}
