import json
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.util                        import ParserHelpers     # ★ here


contract_analyzer = ContractAnalyzer()
snapman           = contract_analyzer.snapman
batch_mgr         = DebugBatchManager(contract_analyzer, snapman)


def simulate_inputs(records):

    in_testcase = False          # ── 현재 @TestCase 블록 안인지

    for rec in records:
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)

        stripped = code.lstrip()

        # ─────────────────────────────────────────────
        # ①  BEGIN / END 마커
        # ─────────────────────────────────────────────
        if stripped.startswith("// @TestCase BEGIN"):
            # 이전 덩어리 남아 있으면 먼저 flush
            batch_mgr.flush()
            in_testcase = True
            continue

        if stripped.startswith("// @TestCase END"):
            batch_mgr.flush()     # ← 지금까지 모은 거 처리
            in_testcase = False
            continue

        # ─────────────────────────────────────────────
        # ②  디버그 주석 (@StateVar 등)
        # ─────────────────────────────────────────────
        if in_testcase and stripped.startswith("// @"):
            # 배치에 축적
            batch_mgr.add_line(code, s, e)
            continue

        # ─────────────────────────────────────────────
        # ③  일반 Solidity 코드
        # ─────────────────────────────────────────────
        if code.strip() == "":
            continue

        ctx  = contract_analyzer.get_current_context_type()
        tree = ParserHelpers.generate_parse_tree(code, ctx, True)

        EnhancedSolidityVisitor(contract_analyzer).visit(tree)

        print("--------------------------------------------------------")


test_inputs = [
  {
    "code": "contract GovStakingStorage {\n}",
    "startLine": 1,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "uint256 totalLockedGogo;",
    "startLine": 2,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "uint256 totalRewardRates;",
    "startLine": 3,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "uint256 totalRewardMultiplier;",
    "startLine": 4,
    "endLine": 4,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 5,
    "endLine": 5,
    "event": "add"
  },
  {
    "code": "struct UserInfo {\n}",
    "startLine": 6,
    "endLine": 7,
    "event": "add"
  },
  {
    "code": "uint256 amount;",
    "startLine": 7,
    "endLine": 7,
    "event": "add"
  },
  {
    "code": "uint256 lockStart;",
    "startLine": 8,
    "endLine": 8,
    "event": "add"
  },
  {
    "code": "uint256 lockPeriod;",
    "startLine": 9,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "uint256 lastClaimed;",
    "startLine": 10,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "uint256 unclaimedAmount;",
    "startLine": 11,
    "endLine": 11,
    "event": "add"
  },
  {
    "code": "uint256 rewardRate;",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "uint256 rewardMultiplier;",
    "startLine": 13,
    "endLine": 13,
    "event": "add"
  },
  {
    "code": "uint256 userRewardPerTokenPaid;",
    "startLine": 14,
    "endLine": 14,
    "event": "add"
  },
  {
    "code": "uint256 index;",
    "startLine": 15,
    "endLine": 15,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 17,
    "endLine": 17,
    "event": "add"
  },
  {
    "code": "mapping(address => UserInfo) public userInfo;",
    "startLine": 18,
    "endLine": 18,
    "event": "add"
  },
  {
    "code": "address[] public userList;",
    "startLine": 19,
    "endLine": 19,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 20,
    "endLine": 20,
    "event": "add"
  },
  {
    "code": "modifier isAllowed() {\n}",
    "startLine": 21,
    "endLine": 22,
    "event": "add"
  },
  {
    "code": "require(allowed[msg.sender], \"sender is not allowed to write\");",
    "startLine": 22,
    "endLine": 22,
    "event": "add"
  },
  {
    "code": "_;",
    "startLine": 23,
    "endLine": 23,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 25,
    "endLine": 25,
    "event": "add"
  },
  {
    "code": "function removeUser(address user) external isAllowed {\n}",
    "startLine": 26,
    "endLine": 27,
    "event": "add"
  },
  {
    "code": "require(userInfo[user].index != 0, \"user does not exist\");",
    "startLine": 27,
    "endLine": 27,
    "event": "add"
  },
  {
    "code": "if (userList.length > 1) {\n}",
    "startLine": 28,
    "endLine": 29,
    "event": "add"
  },
  {
    "code": "address lastAddress = userList[userList.length - 1];",
    "startLine": 29,
    "endLine": 29,
    "event": "add"
  },
  {
    "code": "uint256 oldIndex = userInfo[user].index;",
    "startLine": 30,
    "endLine": 30,
    "event": "add"
  },
  {
    "code": "userList[oldIndex] = lastAddress;",
    "startLine": 31,
    "endLine": 31,
    "event": "add"
  },
  {
    "code": "userInfo[lastAddress].index = oldIndex;",
    "startLine": 32,
    "endLine": 32,
    "event": "add"
  },
  {
    "code": "userList.pop();",
    "startLine": 34,
    "endLine": 34,
    "event": "add"
  },
  {
    "code": "totalRewardMultiplier -= userInfo[user].rewardMultiplier;",
    "startLine": 35,
    "endLine": 35,
    "event": "add"
  },
  {
    "code": "delete userInfo[user];",
    "startLine": 36,
    "endLine": 36,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 38,
    "endLine": 38,
    "event": "add"
  },
  {
    "code": "function updateRewardMultiplier(address user, uint256 oldRate, uint256 newRate, uint256 passedTime, uint256 oldLockPeriod, uint256 newLockPeriod, uint256 oldAmount, uint256 newAmount) external isAllowed {\n}",
    "startLine": 39,
    "endLine": 40,
    "event": "add"
  },
  {
    "code": "UserInfo storage info = userInfo[user];",
    "startLine": 40,
    "endLine": 40,
    "event": "add"
  },
  {
    "code": "uint256 toRemove = ((((oldLockPeriod - passedTime) / 1 weeks) * oldRate) * oldAmount) / 100000;",
    "startLine": 41,
    "endLine": 41,
    "event": "add"
  },
  {
    "code": "uint256 toAdd = (((newLockPeriod / 1 weeks) * newRate) * newAmount) / 100000;",
    "startLine": 42,
    "endLine": 42,
    "event": "add"
  },
  {
    "code": "info.rewardMultiplier = info.rewardMultiplier + toAdd - toRemove;",
    "startLine": 43,
    "endLine": 43,
    "event": "add"
  },
  {
    "code": "totalRewardMultiplier = totalRewardMultiplier + toAdd - toRemove;",
    "startLine": 44,
    "endLine": 44,
    "event": "add"
  }
]



"""
# ──────────────────────────────────────────────────────────────
# ❸  CLI 엔트리포인트
# ----------------------------------------------------------------
def main(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(
        description="Replay JSON input chunks into the incremental analyzer"
    )
    ap.add_argument("json_file", help="input file produced by split_solidity_to_inputs")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="suppress per‑line analysis dumps")
    args = ap.parse_args(argv)

    try:
        raw = pathlib.Path(args.json_file).read_text(encoding="utf-8")
        inputs = json.loads(raw)
    except FileNotFoundError:
        sys.exit(f"✖ file not found: {args.json_file}")
    except json.JSONDecodeError as e:
        sys.exit(f"✖ JSON parse error: {e}")

    simulate_inputs(inputs, silent=args.quiet)


if __name__ == "__main__":
    main(sys.argv[1:])
"""

simulate_inputs(test_inputs)