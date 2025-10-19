// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract HubPool {
    uint256 public protocolFeeCapturePct;

    struct PooledToken {       
        address lpToken;   
        bool isEnabled;    
        uint32 lastLpFeeUpdate;     
        int256 utilizedReserves;     
        uint256 liquidReserves;     
        uint256 undistributedLpFees;
    }

    mapping(address => PooledToken) public pooledTokens;
    mapping(address => uint256) public unclaimedAccumulatedProtocolFees;
    
    function _allocateLpAndProtocolFees(address l1Token, uint256 bundleLpFees) public {      
        uint256 protocolFeesCaptured = (bundleLpFees * protocolFeeCapturePct) / 1e18;
        uint256 lpFeesCaptured = bundleLpFees - protocolFeesCaptured;
      
        if (lpFeesCaptured > 0) {
            pooledTokens[l1Token].undistributedLpFees += lpFeesCaptured;
            pooledTokens[l1Token].utilizedReserves += int256(lpFeesCaptured);
        }
   
        if (protocolFeesCaptured > 0)  {
            unclaimedAccumulatedProtocolFees[l1Token] += protocolFeesCaptured;
        }
    }

    // Auto-generated setter for protocolFeeCapturePct
    function set_protocolFeeCapturePct(uint256 _value) public {
        protocolFeeCapturePct = _value;
    }

    // Auto-generated setter for pooledTokens (mapping)
    function set_pooledTokens(address _key, PooledToken _value) public {
        pooledTokens[_key] = _value;
    }

    // Auto-generated setter for unclaimedAccumulatedProtocolFees (mapping)
    function set_unclaimedAccumulatedProtocolFees(address _key, uint256 _value) public {
        unclaimedAccumulatedProtocolFees[_key] = _value;
    }
}