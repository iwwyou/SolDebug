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
    
    function _insertLockedStake(address _stakerAddress, uint _ATIDamount, uint _stakeWeight, uint _lockedUntil) internal returns (uint newLockedStakeID) {
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
        totalUnweightedATIDStaked += _ATIDamount;

        return newLockedStake.ID;
    }
}