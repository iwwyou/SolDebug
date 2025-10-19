// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract OptimisitcGrants {
    address _governance;
    uint256 public solvency;

    struct Grant {    
        uint128 amount;    
        uint128 expiration;
    }

    mapping(address => Grant) public grants;
    
    modifier onlyGovernance() {
        require(msg.sender == _governance, "!governance");
        _;
    }

    function configureGrant(
        address _owner,
        uint128 _amount,
        uint128 _expiration
    ) external onlyGovernance {
        uint128 oldAmount = grants[_owner].amount;
      
        if (oldAmount < _amount) {
            solvency -= (_amount - oldAmount);
        }       
        else {
            solvency += (oldAmount - _amount);
        }

        grants[_owner].amount = _amount;
        grants[_owner].expiration = _expiration;
    }
}