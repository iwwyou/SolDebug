// Problem 1: GreenHouse (Complexity: Low)
// Pure arithmetic, no conditions
// Original: dataset/contraction/GreenHouse_c.sol

function calculateFees(
    uint256 amount,
    uint256 feeAllUsers,
    uint256 feeBonus,
    uint256 feePartner,
    uint256 feeReferral,
    uint256 feePlatform
) returns (uint256 net) {
    uint256 allUsers = (amount * feeAllUsers) / 10000;
    uint256 bonusPool = (amount * feeBonus) / 10000;
    uint256 partner = (amount * feePartner) / 10000;
    uint256 referral = (amount * feeReferral) / 10000;
    uint256 platform = (amount * feePlatform) / 10000;
    net = amount - allUsers - bonusPool - partner - referral - platform;
}

/*
[Input]
amount = 8500
feeAllUsers = 700
feeBonus = 100
feePartner = 50
feeReferral = 50
feePlatform = 100

[Question] What is the return value (net)?

[Solution]
allUsers = (8500 * 700) / 10000 = 5950000 / 10000 = 595
bonusPool = (8500 * 100) / 10000 = 850000 / 10000 = 85
partner = (8500 * 50) / 10000 = 425000 / 10000 = 42
referral = (8500 * 50) / 10000 = 425000 / 10000 = 42
platform = (8500 * 100) / 10000 = 850000 / 10000 = 85
net = 8500 - 595 - 85 - 42 - 42 - 85 = 7651

[Answer] 7651
*/
