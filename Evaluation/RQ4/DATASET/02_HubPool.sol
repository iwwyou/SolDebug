// Problem 2: HubPool (Complexity: Medium)
// 2 conditions + variable dependency chain
// Original: dataset/contraction/HubPool_c.sol (modified)

function allocateFees(
    uint256 bundleFees,
    uint256 capturePct,
    uint256 undistributedFees,
    uint256 utilizedReserves,
    uint256 unclaimedFees
) returns (uint256) {
    uint256 protocolFees = (bundleFees * capturePct) / 100;
    uint256 lpFees = bundleFees - protocolFees;

    if (lpFees > 0) {
        undistributedFees += lpFees;
        utilizedReserves += lpFees;
    }

    if (protocolFees > 0) {
        unclaimedFees += protocolFees + undistributedFees - utilizedReserves;
    }

    return unclaimedFees;
}

/*
[Input]
bundleFees = 1847
capturePct = 30
undistributedFees = 500
utilizedReserves = 200
unclaimedFees = 100

[Question] What is the return value?

[Solution]
protocolFees = (1847 * 30) / 100 = 55410 / 100 = 554
lpFees = 1847 - 554 = 1293

lpFees > 0? Yes (1293 > 0)
  undistributedFees = 500 + 1293 = 1793
  utilizedReserves = 200 + 1293 = 1493

protocolFees > 0? Yes (554 > 0)
  unclaimedFees = 100 + 554 + 1793 - 1493 = 100 + 554 + 300 = 954

[Answer] 954
*/
