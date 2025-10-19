// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

contract ThorusLottery {
    uint256 public firstWinningNumber;
    uint256 public lastWinningNumber;
    
    struct Ticket {
        address owner;
        bool isClaimed;
    }

    Ticket[] public tickets;
    uint256[] public ticketNumbers;

    function isWinning(uint256 ticketIndex) public returns (bool) {
        if(firstWinningNumber <= ticketNumbers[ticketIndex] && ticketNumbers[ticketIndex] < lastWinningNumber) {
            return true;
        }
        if(lastWinningNumber > tickets.length && ticketNumbers[ticketIndex] < (lastWinningNumber % tickets.length)) {
            return true;
        }
        return false;
    }

    // Auto-generated setter for array tickets
    function _addTicketsAt(Ticket _value, uint256 _index) public {
        uint256 currentLength = tickets.length;

        if (currentLength == 0 || currentLength - 1 < _index) {
            uint256 additionalCount = _index - currentLength + 1;
            for (uint256 i = 0; i < additionalCount; i++) {
                tickets.push();
            }
        }
        tickets[_index] = _value;
    }


    // Auto-generated setter for array ticketNumbers
    function _addTicketNumbersAt(uint256 _value, uint256 _index) public {
        uint256 currentLength = ticketNumbers.length;

        if (currentLength == 0 || currentLength - 1 < _index) {
            uint256 additionalCount = _index - currentLength + 1;
            for (uint256 i = 0; i < additionalCount; i++) {
                ticketNumbers.push();
            }
        }
        ticketNumbers[_index] = _value;
    }

    // Setter for firstWinningNumber
    function set_firstWinningNumber(uint256 _value) public {
        firstWinningNumber = _value;
    }

    // Setter for lastWinningNumber
    function set_lastWinningNumber(uint256 _value) public {
        lastWinningNumber = _value;
    }

}