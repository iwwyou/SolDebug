"""
RQ4: Test SolQDebug with point intervals [n,n] to verify concrete value computation
"""

import sys
import os
from pathlib import Path

# Add project root to path for imports
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers


def create_fresh_analyzer():
    """Create a fresh ContractAnalyzer instance for each test."""
    contract_analyzer = ContractAnalyzer()
    snapman = contract_analyzer.snapman
    batch_mgr = DebugBatchManager(contract_analyzer, snapman)
    return contract_analyzer, batch_mgr


def simulate_inputs(records, contract_analyzer, batch_mgr):
    """Run analysis and collect results."""
    in_testcase = False
    results = {}

    for idx, rec in enumerate(records):
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)

        stripped = code.lstrip()

        if stripped.startswith("// @Debugging BEGIN"):
            batch_mgr.reset()
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            batch_mgr.flush()
            in_testcase = False

            analysis = contract_analyzer.get_line_analysis(s, e)
            if analysis:
                for ln, recs in analysis.items():
                    if ln not in results:
                        results[ln] = []
                    results[ln].extend(recs)
            continue

        if stripped.startswith("// @"):
            if ev == "add":
                batch_mgr.add_line(code, s, e)
            elif ev == "modify":
                batch_mgr.modify_line(code, s, e)
            elif ev == "delete":
                batch_mgr.delete_line(s)

            if not in_testcase:
                batch_mgr.flush()
            continue

        if code.strip():
            ctx = contract_analyzer.get_current_context_type()
            try:
                tree = ParserHelpers.generate_parse_tree(code, ctx, True)
                EnhancedSolidityVisitor(contract_analyzer).visit(tree)
            except Exception:
                pass

        analysis = contract_analyzer.get_line_analysis(s, e)
        if analysis:
            for ln, recs in analysis.items():
                if ln not in results:
                    results[ln] = []
                results[ln].extend(recs)

    return results


# ============================================================
# Problem 1: GreenHouse
# Expected: 7651
# ============================================================
def test_greenhouse():
    print("\n" + "="*60)
    print("Problem 1: GreenHouse")
    print("Expected answer: 7651")
    print("="*60)

    contract_analyzer, batch_mgr = create_fresh_analyzer()

    records = [
        # Contract definition
        {"code": "contract GreenHouse {\n}", "startLine": 1, "endLine": 2, "event": "add"},
        # Function definition
        {"code": """    function calculateFees(
        uint256 amount,
        uint256 feeAllUsers,
        uint256 feeBonus,
        uint256 feePartner,
        uint256 feeReferral,
        uint256 feePlatform
    ) returns (uint256 net) {
}""", "startLine": 2, "endLine": 10, "event": "add"},
        # Function body
        {"code": "        uint256 allUsers = (amount * feeAllUsers) / 10000;", "startLine": 10, "endLine": 10, "event": "add"},
        {"code": "        uint256 bonusPool = (amount * feeBonus) / 10000;", "startLine": 11, "endLine": 11, "event": "add"},
        {"code": "        uint256 partner = (amount * feePartner) / 10000;", "startLine": 12, "endLine": 12, "event": "add"},
        {"code": "        uint256 referral = (amount * feeReferral) / 10000;", "startLine": 13, "endLine": 13, "event": "add"},
        {"code": "        uint256 platform = (amount * feePlatform) / 10000;", "startLine": 14, "endLine": 14, "event": "add"},
        {"code": "        net = amount - allUsers - bonusPool - partner - referral - platform;", "startLine": 15, "endLine": 15, "event": "add"},
        # Annotations with point intervals
        {"code": "// @Debugging BEGIN", "startLine": 16, "endLine": 16, "event": "add"},
        {"code": "// @LocalVar amount = [8500,8500];", "startLine": 17, "endLine": 17, "event": "add"},
        {"code": "// @LocalVar feeAllUsers = [700,700];", "startLine": 18, "endLine": 18, "event": "add"},
        {"code": "// @LocalVar feeBonus = [100,100];", "startLine": 19, "endLine": 19, "event": "add"},
        {"code": "// @LocalVar feePartner = [50,50];", "startLine": 20, "endLine": 20, "event": "add"},
        {"code": "// @LocalVar feeReferral = [50,50];", "startLine": 21, "endLine": 21, "event": "add"},
        {"code": "// @LocalVar feePlatform = [100,100];", "startLine": 22, "endLine": 22, "event": "add"},
        {"code": "// @Debugging END", "startLine": 23, "endLine": 23, "event": "add"},
    ]

    results = simulate_inputs(records, contract_analyzer, batch_mgr)    


# ============================================================
# Problem 2: HubPool
# Expected: 954
# ============================================================
def test_hubpool():
    print("\n" + "="*60)
    print("Problem 2: HubPool")
    print("Expected answer: 954")
    print("="*60)

    contract_analyzer, batch_mgr = create_fresh_analyzer()

    records = [
        {"code": "contract HubPool {\n}", "startLine": 1, "endLine": 2, "event": "add"},
        {"code": """    function allocateFees(
        uint256 bundleFees,
        uint256 capturePct,
        uint256 undistributedFees,
        uint256 utilizedReserves,
        uint256 unclaimedFees
    ) returns (uint256) {
}""", "startLine": 2, "endLine": 9, "event": "add"},
        {"code": "        uint256 protocolFees = (bundleFees * capturePct) / 100;", "startLine": 9, "endLine": 9, "event": "add"},
        {"code": "        uint256 lpFees = bundleFees - protocolFees;", "startLine": 10, "endLine": 10, "event": "add"},
        {"code": "        if (lpFees > 0) {\n}", "startLine": 11, "endLine": 12, "event": "add"},
        {"code": "            undistributedFees += lpFees;", "startLine": 12, "endLine": 12, "event": "add"},
        {"code": "            utilizedReserves += lpFees;", "startLine": 13, "endLine": 13, "event": "add"},
        {"code": "        if (protocolFees > 0) {\n}", "startLine": 15, "endLine": 16, "event": "add"},
        {"code": "            unclaimedFees += protocolFees + undistributedFees - utilizedReserves;", "startLine": 16, "endLine": 16, "event": "add"},
        {"code": "        return unclaimedFees;", "startLine": 18, "endLine": 18, "event": "add"},
        # Annotations
        {"code": "// @Debugging BEGIN", "startLine": 19, "endLine": 19, "event": "add"},
        {"code": "// @LocalVar bundleFees = [1847,1847];", "startLine": 20, "endLine": 20, "event": "add"},
        {"code": "// @LocalVar capturePct = [30,30];", "startLine": 21, "endLine": 21, "event": "add"},
        {"code": "// @LocalVar undistributedFees = [500,500];", "startLine": 22, "endLine": 22, "event": "add"},
        {"code": "// @LocalVar utilizedReserves = [200,200];", "startLine": 23, "endLine": 23, "event": "add"},
        {"code": "// @LocalVar unclaimedFees = [100,100];", "startLine": 24, "endLine": 24, "event": "add"},
        {"code": "// @Debugging END", "startLine": 25, "endLine": 25, "event": "add"},
    ]

    results = simulate_inputs(records, contract_analyzer, batch_mgr)   


# ============================================================
# Problem 3: PercentageFeeModel
# Expected: 85
# ============================================================
def test_percentagefeemodel():
    print("\n" + "="*60)
    print("Problem 3: PercentageFeeModel")
    print("Expected answer: 85")
    print("="*60)

    contract_analyzer, batch_mgr = create_fresh_analyzer()

    # Note: isDepositOverridden=false, isPoolOverridden=true
    # So feeRate = poolFee = 35
    # feeAmount = (2450 * 35) / 1000 = 85

    records = [
        {"code": "contract PercentageFeeModel {\n}", "startLine": 1, "endLine": 2, "event": "add"},
        {"code": """    function getEarlyWithdrawFeeAmount(
        uint256 withdrawnAmount,
        bool isDepositOverridden,
        uint256 depositFee,
        bool isPoolOverridden,
        uint256 poolFee,
        uint256 defaultFee
    ) returns (uint256 feeAmount) {
}""", "startLine": 2, "endLine": 10, "event": "add"},
        {"code": "        uint256 feeRate;", "startLine": 10, "endLine": 10, "event": "add"},
        {"code": "        if (isDepositOverridden) {\n}", "startLine": 11, "endLine": 12, "event": "add"},
        {"code": "            feeRate = depositFee;", "startLine": 12, "endLine": 12, "event": "add"},
        {"code": "        else {\n}", "startLine": 13, "endLine": 14, "event": "add"},
        {"code": "            if (isPoolOverridden) {\n}", "startLine": 14, "endLine": 15, "event": "add"},
        {"code": "                feeRate = poolFee;", "startLine": 15, "endLine": 15, "event": "add"},
        {"code": "            else {\n}", "startLine": 16, "endLine": 17, "event": "add"},
        {"code": "                feeRate = defaultFee;", "startLine": 17, "endLine": 17, "event": "add"},
        {"code": "        feeAmount = (withdrawnAmount * feeRate) / 1000;", "startLine": 20, "endLine": 20, "event": "add"},
        # Annotations
        {"code": "// @Debugging BEGIN", "startLine": 21, "endLine": 21, "event": "add"},
        {"code": "// @LocalVar withdrawnAmount = [2450,2450];", "startLine": 22, "endLine": 22, "event": "add"},
        {"code": "// @LocalVar isDepositOverridden = [0,0];", "startLine": 23, "endLine": 23, "event": "add"},
        {"code": "// @LocalVar depositFee = [50,50];", "startLine": 24, "endLine": 24, "event": "add"},
        {"code": "// @LocalVar isPoolOverridden = [1,1];", "startLine": 25, "endLine": 25, "event": "add"},
        {"code": "// @LocalVar poolFee = [35,35];", "startLine": 26, "endLine": 26, "event": "add"},
        {"code": "// @LocalVar defaultFee = [25,25];", "startLine": 27, "endLine": 27, "event": "add"},
        {"code": "// @Debugging END", "startLine": 28, "endLine": 28, "event": "add"},
    ]

    results = simulate_inputs(records, contract_analyzer, batch_mgr)  


# ============================================================
# Problem 4: LockupContract
# Expected: 6000
# ============================================================
def test_lockupcontract():
    print("\n" + "="*60)
    print("Problem 4: LockupContract")
    print("Expected answer: 6000")
    print("="*60)

    contract_analyzer, batch_mgr = create_fresh_analyzer()

    records = [
        {"code": "contract LockupContract {\n}", "startLine": 1, "endLine": 2, "event": "add"},
        {"code": """    function getReleasedAmount(
        uint256 currentTime,
        uint256 deploymentStartTime,
        uint256 monthsToWait,
        uint256 secondsInMonth,
        uint256 initialAmount,
        uint256 releaseSchedule
    ) returns (uint256) {
}""", "startLine": 2, "endLine": 10, "event": "add"},
        {"code": "        uint256 unlockTimestamp = deploymentStartTime + (monthsToWait * secondsInMonth);", "startLine": 10, "endLine": 10, "event": "add"},
        {"code": "        if (currentTime < unlockTimestamp) {\n}", "startLine": 11, "endLine": 12, "event": "add"},
        {"code": "            return 0;", "startLine": 12, "endLine": 12, "event": "add"},
        {"code": "        uint256 monthsSinceUnlock = ((currentTime - unlockTimestamp) / secondsInMonth) + 1;", "startLine": 14, "endLine": 14, "event": "add"},
        {"code": "        uint256 monthlyReleaseAmount = initialAmount / releaseSchedule;", "startLine": 15, "endLine": 15, "event": "add"},
        {"code": "        uint256 releasedAmount = monthlyReleaseAmount * monthsSinceUnlock;", "startLine": 16, "endLine": 16, "event": "add"},
        {"code": "        if (releasedAmount > initialAmount) {\n}", "startLine": 17, "endLine": 18, "event": "add"},
        {"code": "            return initialAmount;", "startLine": 18, "endLine": 18, "event": "add"},
        {"code": "        return releasedAmount;", "startLine": 20, "endLine": 20, "event": "add"},
        # Annotations
        {"code": "// @Debugging BEGIN", "startLine": 21, "endLine": 21, "event": "add"},
        {"code": "// @LocalVar currentTime = [15000000,15000000];", "startLine": 22, "endLine": 22, "event": "add"},
        {"code": "// @LocalVar deploymentStartTime = [10000000,10000000];", "startLine": 23, "endLine": 23, "event": "add"},
        {"code": "// @LocalVar monthsToWait = [3,3];", "startLine": 24, "endLine": 24, "event": "add"},
        {"code": "// @LocalVar secondsInMonth = [1000000,1000000];", "startLine": 25, "endLine": 25, "event": "add"},
        {"code": "// @LocalVar initialAmount = [24000,24000];", "startLine": 26, "endLine": 26, "event": "add"},
        {"code": "// @LocalVar releaseSchedule = [12,12];", "startLine": 27, "endLine": 27, "event": "add"},
        {"code": "// @Debugging END", "startLine": 28, "endLine": 28, "event": "add"},
    ]

    results = simulate_inputs(records, contract_analyzer, batch_mgr)    


# ============================================================
# Problem 5: Lock
# Expected: 6800
# ============================================================
def test_lock():
    print("\n" + "="*60)
    print("Problem 5: Lock")
    print("Expected answer: 6800")
    print("="*60)

    contract_analyzer, batch_mgr = create_fresh_analyzer()

    records = [
        {"code": "contract Lock {\n}", "startLine": 1, "endLine": 2, "event": "add"},
        {"code": """    function pending(
        uint256 total,
        uint256 unlockedAmounts,
        uint256 pendingAmount,
        uint256 estUnlock,
        uint256 currentTime,
        uint256 startLock,
        uint256 lockedTime,
        uint256 unlockDuration
    ) returns (uint256 result) {
}""", "startLine": 2, "endLine": 12, "event": "add"},
        {"code": "        uint256 totalLockRemain = total - unlockedAmounts - pendingAmount;", "startLine": 12, "endLine": 12, "event": "add"},
        {"code": "        if (totalLockRemain > 0) {\n}", "startLine": 13, "endLine": 14, "event": "add"},
        {"code": "            if (currentTime >= startLock + lockedTime) {\n}", "startLine": 14, "endLine": 15, "event": "add"},
        {"code": "                result = totalLockRemain;", "startLine": 15, "endLine": 15, "event": "add"},
        {"code": "            else {\n}", "startLine": 16, "endLine": 17, "event": "add"},
        {"code": "                uint256 nUnlock = (lockedTime - (currentTime - startLock) - 1) / unlockDuration + 1;", "startLine": 17, "endLine": 17, "event": "add"},
        {"code": "                result = totalLockRemain - estUnlock * nUnlock;", "startLine": 18, "endLine": 18, "event": "add"},
        {"code": "        if (pendingAmount > 0) {\n}", "startLine": 21, "endLine": 22, "event": "add"},
        {"code": "            result += pendingAmount;", "startLine": 22, "endLine": 22, "event": "add"},
        # Annotations
        {"code": "// @Debugging BEGIN", "startLine": 24, "endLine": 24, "event": "add"},
        {"code": "// @LocalVar total = [10000,10000];", "startLine": 25, "endLine": 25, "event": "add"},
        {"code": "// @LocalVar unlockedAmounts = [2000,2000];", "startLine": 26, "endLine": 26, "event": "add"},
        {"code": "// @LocalVar pendingAmount = [500,500];", "startLine": 27, "endLine": 27, "event": "add"},
        {"code": "// @LocalVar estUnlock = [400,400];", "startLine": 28, "endLine": 28, "event": "add"},
        {"code": "// @LocalVar currentTime = [2500,2500];", "startLine": 29, "endLine": 29, "event": "add"},
        {"code": "// @LocalVar startLock = [1000,1000];", "startLine": 30, "endLine": 30, "event": "add"},
        {"code": "// @LocalVar lockedTime = [3000,3000];", "startLine": 31, "endLine": 31, "event": "add"},
        {"code": "// @LocalVar unlockDuration = [500,500];", "startLine": 32, "endLine": 32, "event": "add"},
        {"code": "// @Debugging END", "startLine": 33, "endLine": 33, "event": "add"},
    ]

    results = simulate_inputs(records, contract_analyzer, batch_mgr)    


def run_with_timing(test_func, name, expected):
    """Run a test function and measure execution time."""
    import time

    start = time.perf_counter()
    test_func()
    end = time.perf_counter()

    elapsed_ms = (end - start) * 1000
    return {
        'name': name,
        'expected': expected,
        'time_ms': elapsed_ms
    }


if __name__ == "__main__":
    import time

    print("="*60)
    print("RQ4: Testing SolQDebug with Point Intervals")
    print("="*60)

    results = []

    results.append(run_with_timing(test_greenhouse, "GreenHouse", 7651))
    results.append(run_with_timing(test_hubpool, "HubPool", 954))
    results.append(run_with_timing(test_percentagefeemodel, "PercentageFeeModel", 85))
    results.append(run_with_timing(test_lockupcontract, "LockupContract", 6000))
    results.append(run_with_timing(test_lock, "Lock", 6800))

    print("\n" + "="*60)
    print("EXECUTION TIME SUMMARY")
    print("="*60)
    print(f"{'Problem':<25} {'Expected':<10} {'Time (ms)':<15}")
    print("-"*50)

    total_time = 0
    for r in results:
        print(f"{r['name']:<25} {r['expected']:<10} {r['time_ms']:<15.2f}")
        total_time += r['time_ms']

    print("-"*50)
    print(f"{'TOTAL':<25} {'':<10} {total_time:<15.2f}")
    print(f"{'AVERAGE':<25} {'':<10} {total_time/len(results):<15.2f}")

    print("\n" + "="*60)
    print("TEST COMPLETE")
    print("="*60)
