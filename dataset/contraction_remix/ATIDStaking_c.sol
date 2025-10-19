// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract ATIDStaking {
    struct LockedStake {
        bool active;        
        uint ID;
        uint prevID;  
        uint nextID;        
        uint amount;        
        uint lockedUntil;        
        uint stakeWeight;
    }
    
    mapping(address => mapping(uint => LockedStake)) public lockedStakeMap;
    mapping(address => uint) public headLockedStakeIDMap;
    mapping(address => uint) public nextLockedStakeIDMap;
    mapping(address => uint) public tailLockedStakeIDMap;
    mapping(address => uint) public weightedStakes;
    mapping(address => uint) public unweightedStakes;

    uint public totalWeightedATIDStaked;
    uint public totalUnWeightedATIDStaked;
    
    function _insertLockedStake(address _stakerAddress, uint _ATIDamount, uint _stakeWeight, uint _lockedUntil) public returns (uint newLockedStakeID) {
        if (nextLockedStakeIDMap[_stakerAddress] == 0) {
            nextLockedStakeIDMap[_stakerAddress] = 1;
        }
        uint nextLockedStateID = nextLockedStakeIDMap[_stakerAddress];
        nextLockedStakeIDMap[_stakerAddress]++;
        
        LockedStake memory newLockedStake = LockedStake({
            active: true,

            ID: nextLockedStateID,
            prevID: tailLockedStakeIDMap[_stakerAddress],  
            nextID: 0,  

            amount: _ATIDamount,
            lockedUntil: _lockedUntil,
            stakeWeight: _stakeWeight
        });
        lockedStakeMap[_stakerAddress][newLockedStake.ID] = newLockedStake;

        if (headLockedStakeIDMap[_stakerAddress] == 0) {           
            headLockedStakeIDMap[_stakerAddress] = newLockedStake.ID;
        } else {           
            lockedStakeMap[_stakerAddress][newLockedStake.prevID].nextID = newLockedStake.ID;
        }
        
        tailLockedStakeIDMap[_stakerAddress] = newLockedStake.ID;
        
        uint newWeightedStake = newLockedStake.amount * newLockedStake.stakeWeight;
        weightedStakes[_stakerAddress] += newWeightedStake;
        totalWeightedATIDStaked += newWeightedStake;        
        
        unweightedStakes[_stakerAddress] += _ATIDamount;
        totalUnWeightedATIDStaked += _ATIDamount;

        return newLockedStake.ID;
    }

    // Auto-generated setter for nextLockedStakeIDMap (mapping)
    function set_nextLockedStakeIDMap(address _key, uint _value) public {
        nextLockedStakeIDMap[_key] = _value;
    }

    // Auto-generated setter for tailLockedStakeIDMap (mapping)
    function set_tailLockedStakeIDMap(address _key, uint _value) public {
        tailLockedStakeIDMap[_key] = _value;
    }

    // Auto-generated setter for headLockedStakeIDMap (mapping)
    function set_headLockedStakeIDMap(address _key, uint _value) public {
        headLockedStakeIDMap[_key] = _value;
    }

    // Auto-generated setter for weightedStakes (mapping)
    function set_weightedStakes(address _key, uint _value) public {
        weightedStakes[_key] = _value;
    }

    // Auto-generated setter for totalWeightedATIDStaked
    function set_totalWeightedATIDStaked(uint _value) public {
        totalWeightedATIDStaked = _value;
    }

    // Auto-generated setter for unweightedStakes (mapping)
    function set_unweightedStakes(address _key, uint _value) public {
        unweightedStakes[_key] = _value;
    }
}