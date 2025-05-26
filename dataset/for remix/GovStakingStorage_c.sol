// SPDX-License-Identifier: MIT
pragma solidity ^0.8.20;

contract GovStakingStorage {
    /* ──────────── 원본 상태 변수 ──────────── */
    uint256 public totalLockedGogo;
    uint256 public totalRewardRates;
    uint256 public totalRewardMultiplier;

    struct UserInfo {
        uint256 amount;
        uint256 lockStart;
        uint256 lockPeriod;
        uint256 lastClaimed;
        uint256 unclaimedAmount;
        uint256 rewardRate;
        uint256 rewardMultiplier;
        uint256 userRewardPerTokenPaid;
        uint256 index; // 0 = 미등록
    }

    mapping(address => UserInfo) public userInfo;
    address[] public userList;
    mapping(address => bool) public allowed;

    /* ──────────── ✅ 테스트용 Setter / Helper ──────────── */

    /// @notice 테스트 계정을 allowed 플래그로 설정
    function _setAllowed(address who, bool flag) external {
        allowed[who] = flag;
    }

    /// @notice userInfo 구조체를 통째로 주입
    /// @dev  ↘︎ 파라미터가 많으니 IDE 자동 완성 사용 권장
    function _setUserInfo(
        address user,
        uint256 amount,
        uint256 lockStart,
        uint256 lockPeriod,
        uint256 lastClaimed,
        uint256 unclaimedAmount,
        uint256 rewardRate,
        uint256 rewardMultiplier,
        uint256 userRewardPerTokenPaid,
        uint256 index
    ) external {
        userInfo[user] = UserInfo({
            amount: amount,
            lockStart: lockStart,
            lockPeriod: lockPeriod,
            lastClaimed: lastClaimed,
            unclaimedAmount: unclaimedAmount,
            rewardRate: rewardRate,
            rewardMultiplier: rewardMultiplier,
            userRewardPerTokenPaid: userRewardPerTokenPaid,
            index: index
        });
    }

    /// @notice userList에 주소를 직접 push (index 관리는 직접 책임)
    function _pushUser(address user) external {
        userList.push(user);
    }

    /// @notice userList 마지막 요소를 pop
    function _popUser() external {
        userList.pop();
    }

    /// @notice 집계용 토큰·리워드 총계를 임의 수정 (필요 시)
    function _setTotals(
        uint256 lockedGogo,
        uint256 rewardRates,
        uint256 rewardMult
    ) external {
        totalLockedGogo     = lockedGogo;
        totalRewardRates    = rewardRates;
        totalRewardMultiplier = rewardMult;
    }

    /* ──────────── 권한 체크 ──────────── */
    modifier isAllowed() {
        require(allowed[msg.sender], "sender is not allowed to write");
        _;
    }

    /* ──────────── 원본 로직 ──────────── */
    function removeUser(address user) external isAllowed {
        require(userInfo[user].index != 0, "user does not exist");

        if (userList.length > 1) {
            address lastAddress = userList[userList.length - 1];
            uint256 oldIndex = userInfo[user].index;
            userList[oldIndex] = lastAddress;
            userInfo[lastAddress].index = oldIndex;
        }
        userList.pop();

        totalRewardMultiplier -= userInfo[user].rewardMultiplier;
        delete userInfo[user];
    }

    function updateRewardMultiplier(
        address user,
        uint256 oldRate,
        uint256 newRate,
        uint256 passedTime,
        uint256 oldLockPeriod,
        uint256 newLockPeriod,
        uint256 oldAmount,
        uint256 newAmount
    ) external isAllowed {
        UserInfo storage info = userInfo[user];

        uint256 toRemove = ((((oldLockPeriod - passedTime) / 1 weeks) * oldRate) * oldAmount) / 100000;
        uint256 toAdd    = ((( newLockPeriod               / 1 weeks) * newRate) * newAmount) / 100000;

        info.rewardMultiplier   = info.rewardMultiplier + toAdd - toRemove;
        totalRewardMultiplier   = totalRewardMultiplier + toAdd - toRemove;
    }
}
