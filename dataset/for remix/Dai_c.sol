// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract Dai {
    /* ────── 원본 상태 변수 ────── */
    mapping (address => uint256) public wards;          // 1 = auth, 0 = none
    uint256 public totalSupply;
    mapping (address => uint256) public balanceOf;
    mapping (address => mapping (address => uint256)) public allowance;    

    /* ────── ✅ 테스트용 Setter ────── */

    /// @notice 특정 주소의 auth(ward) 플래그를 직접 설정
    function _setWard(address who, uint256 flag) public {
        wards[who] = flag;              // flag: 0 또는 1
    }

    /// @notice 임의 주소의 잔액을 직접 주입
    /// @dev totalSupply와 동기화가 필요하면 직접 `_setTotalSupply`를 호출하세요.
    function _setBalance(address who, uint256 amount) public {
        balanceOf[who] = amount;
    }

    /// @notice owner → spender 허용량 직접 설정
    function _setAllowance(address owner, address spender, uint256 amount) public {
        allowance[owner][spender] = amount;
    }

    /// @notice totalSupply 값을 강제로 맞추기 (테스트 전용)
    function _setTotalSupply(uint256 amount) external {
        totalSupply = amount;
    }

    /* ────── 내부 연산 라이브러리 ────── */
    function add(uint x, uint y) public returns (uint z) {
        require((z = x + y) >= x, "Dai/add-overflow");
    }
    function sub(uint x, uint y) public returns (uint z) {
        require((z = x - y) <= x, "Dai/sub-underflow");
    }

    /* ────── 핵심 로직 (원본) ────── */
    modifier auth {
        require(wards[msg.sender] == 1, "Dai/not-authorized");
        _;
    }

    function transferFrom(address src, address dst, uint wad) public returns (bool) {
        require(balanceOf[src] >= wad, "Dai/insufficient-balance");

        if (src != msg.sender && allowance[src][msg.sender] != type(uint).max) {
            require(allowance[src][msg.sender] >= wad, "Dai/insufficient-allowance");
            allowance[src][msg.sender] = sub(allowance[src][msg.sender], wad);
        }

        balanceOf[src] = sub(balanceOf[src], wad);
        balanceOf[dst] = add(balanceOf[dst], wad);
        return true;
    }

    function transfer(address dst, uint wad) external returns (bool) {
        return transferFrom(msg.sender, dst, wad);
    }

    function mint(address usr, uint wad) external auth {
        balanceOf[usr] = add(balanceOf[usr], wad);
        totalSupply    = add(totalSupply,    wad);
    }

    function burn(address usr, uint wad) external {
        require(balanceOf[usr] >= wad, "Dai/insufficient-balance");

        if (usr != msg.sender && allowance[usr][msg.sender] != type(uint).max) {
            require(allowance[usr][msg.sender] >= wad, "Dai/insufficient-allowance");
            allowance[usr][msg.sender] = sub(allowance[usr][msg.sender], wad);
        }

        balanceOf[usr] = sub(balanceOf[usr], wad);
        totalSupply    = sub(totalSupply,    wad);
    }
}
