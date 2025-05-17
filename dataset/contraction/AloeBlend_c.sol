contract AloeBlend {
    uint8 public constant MAINTENANCE_FEE = 10;

    uint256 public maintenanceBudget0;

    uint256 public maintenanceBudget1;

    uint224[10] public rewardPerGas0Array;    

    uint224 public rewardPerGas0Accumulator;    

    uint64 public rebalanceCount;

    function _earmarkSomeForMaintenance(uint256 earned0, uint256 earned1) private returns (uint256, uint256) {
        uint256 toMaintenance;

        unchecked {            
            toMaintenance = earned0 / MAINTENANCE_FEE;
            earned0 -= toMaintenance;
            maintenanceBudget0 += toMaintenance;            
            toMaintenance = earned1 / MAINTENANCE_FEE;
            earned1 -= toMaintenance;
            maintenanceBudget1 += toMaintenance;
        }

        return (earned0, earned1);
    }

    function pushRewardPerGas0(uint224 rewardPerGas0) private {
        unchecked {
            rewardPerGas0 /= 10;
            rewardPerGas0Accumulator = rewardPerGas0Accumulator + rewardPerGas0 - rewardPerGas0Array[rebalanceCount % 10];
            rewardPerGas0Array[rebalanceCount % 10] = rewardPerGas0;
        }
    }
}