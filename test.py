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
        tree = ParserHelpers.generate_parse_tree(code, ctx)
        EnhancedSolidityVisitor(contract_analyzer).visit(tree)

        print("--------------------------------------------------------")


test_inputs = [
  {
    "code": "contract AOC_BEP {\n}",
    "startLine": 1,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "struct UserInfo {\n}",
    "startLine": 2,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "uint256 balance;",
    "startLine": 3,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "uint256 level;",
    "startLine": 4,
    "endLine": 4,
    "event": "add"
  },
  {
    "code": "uint256 year;",
    "startLine": 5,
    "endLine": 5,
    "event": "add"
  },
  {
    "code": "uint256 month;",
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
    "code": "struct Level {\n}",
    "startLine": 9,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "uint256 start;",
    "startLine": 10,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "uint256 end;",
    "startLine": 11,
    "endLine": 11,
    "event": "add"
  },
  {
    "code": "uint256 percentage;",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 14,
    "endLine": 14,
    "event": "add"
  },
  {
    "code": "mapping(address => UserInfo) public userInfo;",
    "startLine": 15,
    "endLine": 15,
    "event": "add"
  },
  {
    "code": "mapping(uint256 => Level) public levels;",
    "startLine": 16,
    "endLine": 16,
    "event": "add"
  },
  {
    "code": "mapping(address => uint256) private _balances;",
    "startLine": 17,
    "endLine": 17,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 18,
    "endLine": 18,
    "event": "add"
  },
  {
    "code": "function updateUserInfo(address account, uint256 year, uint256 month) internal {\n}",
    "startLine": 19,
    "endLine": 20,
    "event": "add"
  },
  {
    "code": "userInfo[account].balance = _balances[account];",
    "startLine": 20,
    "endLine": 20,
    "event": "add"
  },
  {
    "code": "userInfo[account].year = year;",
    "startLine": 21,
    "endLine": 21,
    "event": "add"
  },
  {
    "code": "userInfo[account].month = month;",
    "startLine": 22,
    "endLine": 22,
    "event": "add"
  },
  {
    "code": "for(uint256 i = 1; i <= 4; i++) {\n}",
    "startLine": 23,
    "endLine": 24,
    "event": "add"
  },
  {
    "code": "if(i == 4) {\n}",
    "startLine": 24,
    "endLine": 25,
    "event": "add"
  },
  {
    "code": "userInfo[account].level = i;",
    "startLine": 25,
    "endLine": 25,
    "event": "add"
  },
  {
    "code": "break;",
    "startLine": 26,
    "endLine": 26,
    "event": "add"
  },
  {
    "code": "if(block.timestamp >= levels[i].start && block.timestamp <= levels[i].end) {\n}",
    "startLine": 28,
    "endLine": 29,
    "event": "add"
  },
  {
    "code": "userInfo[account].level = i;",
    "startLine": 29,
    "endLine": 29,
    "event": "add"
  },
  {
    "code": "break;",
    "startLine": 30,
    "endLine": 30,
    "event": "add"
  },
  {
    "code": "// @TestCase BEGIN;",
    "startLine": 20,
    "endLine": 20,
    "event": "add"
  },
  {
    "code": "// @GlobalVar block.timestamp = [10,20];",
    "startLine": 21,
    "endLine": 21,
    "event": "add"
  },
  {
    "code": "// @StateVar _balances[account] = [100,200];",
    "startLine": 22,
    "endLine": 22,
    "event": "add"
  },
  {
    "code": "// @TestCase END;",
    "startLine": 23,
    "endLine": 23,
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