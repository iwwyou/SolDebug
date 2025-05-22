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
    "code": "contract BEP20 {\n}",
    "startLine": 1,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "mapping (address=>uint256) balances;",
    "startLine": 2,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 3,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "uint256 public totalSupply;",
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
    "code": "mapping (address=>mapping (address=>uint256)) allowed;",
    "startLine": 6,
    "endLine": 6,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 7,
    "endLine": 7,
    "event": "add"
  },
  {
    "code": "function transferFrom(address _from,address _to,uint256 _amount) public returns (bool success) {\n}",
    "startLine": 8,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "require (balances[_from]>=_amount&&allowed[_from][msg.sender]>=_amount&&_amount>0&&balances[_to]+_amount>balances[_to]);",
    "startLine": 9,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "balances[_from]-=_amount;",
    "startLine": 10,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "allowed[_from][msg.sender]-=_amount;",
    "startLine": 11,
    "endLine": 11,
    "event": "add"
  },
  {
    "code": "balances[_to]+=_amount;",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "return true;",
    "startLine": 13,
    "endLine": 13,
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