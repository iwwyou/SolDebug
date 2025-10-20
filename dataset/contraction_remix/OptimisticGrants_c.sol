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

    constructor() {
        _governance = msg.sender;
    }

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
    

    

    

    

    // Auto-generated setter for grants (mapping)
    function set_grants(address _key, Grant memory _value) public {
        grants[_key] = _value;
    }

    // Auto-generated setter for _governance
    function set__governance(address _value) public {
        _governance = _value;
    }

    // Auto-generated setter for solvency
    function set_solvency(uint256 _value) public {
        solvency = _value;
    }
}