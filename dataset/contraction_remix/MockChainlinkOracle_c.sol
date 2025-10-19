// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract MockChainlinkOracle {
    uint80 public roundId = 0;    

    struct Entry {
        uint80 roundId;
        int256 answer;
        uint256 startedAt;
        uint256 updatedAt;
        uint80 answeredInRound;
    }

    mapping(uint256 => Entry) public entries;

    bool public latestRoundDataShouldRevert;

    function getRoundData(uint80 _roundId)
        public
        returns (
            uint80,
            int256,
            uint256,
            uint256,
            uint80
        )
    {
        Entry memory entry = entries[_roundId];        
        require(entry.updatedAt > 0, "No data present");
        return (entry.roundId, entry.answer, entry.startedAt, entry.updatedAt, entry.answeredInRound);
    }
    
    function latestRoundData()
        external
        returns (
            uint80,
            int256,
            uint256,
            uint256,
            uint80
        )
    {
        if (latestRoundDataShouldRevert) {
            revert("latestRoundData reverted");
        }
        return getRoundData(uint80(roundId));
    }

    // Auto-generated setter for roundId
    function set_roundId(uint80 _value) public {
        roundId = _value;
    }

    // Auto-generated setter for latestRoundDataShouldRevert
    function set_latestRoundDataShouldRevert(bool _value) public {
        latestRoundDataShouldRevert = _value;
    }
}