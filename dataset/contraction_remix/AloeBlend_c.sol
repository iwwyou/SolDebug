// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract AloeBlend {
    uint8 public constant MAINTENANCE_FEE = 10;
    uint256 public maintenanceBudget0;
    uint256 public maintenanceBudget1;    

    function _earmarkSomeForMaintenance(uint256 earned0, uint256 earned1) public returns (uint256, uint256) {
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

    

    

    // Auto-generated setter for maintenanceBudget0
    function set_maintenanceBudget0(uint256 _value) public {
        maintenanceBudget0 = _value;
    }

    // Auto-generated setter for maintenanceBudget1
    function set_maintenanceBudget1(uint256 _value) public {
        maintenanceBudget1 = _value;
    }
}