function _calculateFees(uint256 amount)
    internal pure
    returns(
        uint256 allUsers,
        uint256 bonusPool,
        uint256 partner,
        uint256 referral,
        uint256 platform,
        uint256 net
    ) {
        allUsers = (amount * FEE_ALL_USERS_STAKED_PERMILLE) / 10000;
        bonusPool = (amount * FEE_BONUS_POOL_PERMILLE) / 10000;
        partner = (amount * FEE_PARTNER_WALLET_PERMILLE) / 10000;
        referral = (amount * FEE_REFERRAL_PERMILLE) / 10000;
        platform = (amount * FEE_PLATFORM_WALLET_PERMILLE) / 10000;
        net = amount - allUsers - bonusPool - partner - referral - platform;
    }