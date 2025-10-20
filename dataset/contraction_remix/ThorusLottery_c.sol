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

    // Auto-generated setter for tickets array
    function _addTicketsAt(Ticket memory _value, uint256 _index) public {
        if (_index >= tickets.length) {
            tickets.push(_value);
        } else {
            tickets[_index] = _value;
        }
    }

    // Auto-generated setter for ticketNumbers array
    function _addTicketNumbersAt(uint256 _value, uint256 _index) public {
        if (_index >= ticketNumbers.length) {
            ticketNumbers.push(_value);
        } else {
            ticketNumbers[_index] = _value;
        }
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