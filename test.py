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
        print("code : ", code)
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
    "code": "contract Lock {\n}",
    "startLine": 1,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "struct LockedData {\n}",
    "startLine": 2,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "uint256 total;",
    "startLine": 3,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "uint256 pending;",
    "startLine": 4,
    "endLine": 4,
    "event": "add"
  },
  {
    "code": "uint256 estUnlock;",
    "startLine": 5,
    "endLine": 5,
    "event": "add"
  },
  {
    "code": "uint256 unlockedAmounts;",
    "startLine": 6,
    "endLine": 6,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 8,
    "endLine": 8,
    "event": "add"
  },
  {
    "code": "mapping(address => LockedData) public data;",
    "startLine": 9,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "uint256 public startLock;",
    "startLine": 10,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "uint256 public unlockDuration = 30 days;",
    "startLine": 11,
    "endLine": 11,
    "event": "add"
  },
  {
    "code": "uint256 public lockedTime = 6 * 30 days;",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 13,
    "endLine": 13,
    "event": "add"
  },
  {
    "code": "function pending(address _account) public view returns(uint256 _pending) {\n}",
    "startLine": 14,
    "endLine": 15,
    "event": "add"
  },
  {
    "code": "LockedData memory _data = data[_account];",
    "startLine": 15,
    "endLine": 15,
    "event": "add"
  },
  {
    "code": "uint256 _totalLockRemain =  _data.total - _data.unlockedAmounts - _data.pending;",
    "startLine": 16,
    "endLine": 16,
    "event": "add"
  },
  {
    "code": "if (_totalLockRemain > 0) {\n}",
    "startLine": 17,
    "endLine": 18,
    "event": "add"
  },
  {
    "code": "if (block.timestamp >= startLock + lockedTime) {\n}",
    "startLine": 18,
    "endLine": 19,
    "event": "add"
  },
  {
    "code": "_pending = _totalLockRemain;",
    "startLine": 19,
    "endLine": 19,
    "event": "add"
  },
  {
    "code": "else {\n}",
    "startLine": 21,
    "endLine": 22,
    "event": "add"
  },
  {
    "code": "uint256 _nUnlock = (lockedTime - (block.timestamp - startLock) - 1) / unlockDuration + 1;",
    "startLine": 22,
    "endLine": 22,
    "event": "add"
  },
  {
    "code": "_pending = _totalLockRemain - _data.estUnlock * _nUnlock;",
    "startLine": 23,
    "endLine": 23,
    "event": "add"
  },
  {
    "code": "if (_data.pending > 0) {\n}",
    "startLine": 26,
    "endLine": 27,
    "event": "add"
  },
  {
    "code": "_pending += _data.pending;",
    "startLine": 27,
    "endLine": 27,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 31,
    "endLine": 31,
    "event": "add"
  },
{
    "code": "//@TestCase BEGIN",
    "startLine": 15,
    "endLine": 15,
    "event": "add"
  },
  {
    "code": "// @StateVar _data.total = [300,300]",
    "startLine": 16,
    "endLine": 16,
    "event": "add"
  },
  {
    "code": "// @StateVar _data.unlockedAmounts = [0,0]",
    "startLine": 17,
    "endLine": 17,
    "event": "add"
  },
  {
    "code": "// @StateVar _data.pending = [1,1]",
    "startLine": 18,
    "endLine": 18,
    "event": "add"
  },
  {
    "code": "// @StateVar _data.estUnlock = [2,2]",
    "startLine": 19,
    "endLine": 19,
    "event": "add"
  },
  {
    "code": "// @GlobalVar block.timestamp = [3,3]",
    "startLine": 20,
    "endLine": 20,
    "event": "add"
  },
  {
    "code": "// @StateVar startLock = [4,4]",
    "startLine": 21,
    "endLine": 21,
    "event": "add"
  },
  {
    "code": "// @StateVar lockedTime = [20000000,20000000]",
    "startLine": 22,
    "endLine": 22,
    "event": "add"
  },
  {
    "code": "// @StateVar unlockDuration = [2592000,2592000]",
    "startLine": 23,
    "endLine": 23,
    "event": "add"
  },
  {
    "code": "//@TestCase END",
    "startLine": 24,
    "endLine": 24,
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