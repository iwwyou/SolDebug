contract ThorusLottery {
    uint256 public firstWinningNumber;
    uint256 public lastWinningNumber;
    
    struct Ticket {
        address owner;
        bool isClaimed;
    }

    Ticket[] public tickets;
    uint256[] public ticketNumbers;

    function isWinning(uint256 ticketIndex) public view returns (bool) {
        if(firstWinningNumber <= ticketNumbers[ticketIndex] && ticketNumbers[ticketIndex] < lastWinningNumber)
            return true;
        if(lastWinningNumber > tickets.length && ticketNumbers[ticketIndex] < (lastWinningNumber % tickets.length))
            return true;
        return false;
    }
}