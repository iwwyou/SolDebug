import json
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.util                        import ParserHelpers     # ★ here
import time

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
            start = time.time()
            batch_mgr.flush()     # ← 지금까지 모은 거 처리
            end = time.time()
            print(f"Analyze time : {end - start:.5f} sec")
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

        # ✨ ★ 여기서 바로 찍어 보기 ★ ✨
        analysis = contract_analyzer.get_line_analysis(s, e)
        if analysis:  # 비어 있지 않을 때만
          print(f"[{s}-{e}]  analysis ⇒")
          for ln, recs in analysis.items():
            for r in recs:
              print(f"  L{ln:3} | {r['kind']:>14} | {r['vars']}")

        print("--------------------------------------------------------")


test_inputs = [
  {
    "code": "contract DapiServer {\n}",
    "startLine": 1,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "uint256 public constant override HUNDRED_PERCENT = 1e8;",
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
    "code": "function calculateUpdateInPercentage(int224 initialValue, int224 updatedValue) private pure returns (uint256 updateInPercentage) {\n}",
    "startLine": 4,
    "endLine": 5,
    "event": "add"
  },
  {
    "code": "int256 delta = int256(updatedValue) - int256(initialValue);",
    "startLine": 5,
    "endLine": 5,
    "event": "add"
  },
  {
    "code": "uint256 absoluteDelta = delta > 0 ? uint256(delta) : uint256(-delta);",
    "startLine": 6,
    "endLine": 6,
    "event": "add"
  },
  {
    "code": "uint256 absoluteInitialValue = initialValue > 0 ? uint256(int256(initialValue)) : uint256(-int256(initialValue));",
    "startLine": 7,
    "endLine": 7,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 8,
    "endLine": 8,
    "event": "add"
  },
  {
    "code": "if (absoluteInitialValue == 0) {\n}",
    "startLine": 9,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "absoluteInitialValue = 1;",
    "startLine": 10,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "updateInPercentage = (absoluteDelta * HUNDRED_PERCENT) / absoluteInitialValue;",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
{
    "code": "// @TestCase BEGIN",
    "startLine": 5,
    "endLine": 5,
    "event": "add"
  },
{
    "code": "// @LocalVar initialValue = [50,100]",
    "startLine": 6,
    "endLine": 6,
    "event": "add"
  },
{
    "code": "// @LocalVar updatedValue = [200,300]",
    "startLine": 7,
    "endLine": 7,
    "event": "add"
  },
{
    "code": "// @TestCase END",
    "startLine": 8,
    "endLine": 8,
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
#start = time.time()

simulate_inputs(test_inputs)
#end = time.time()
#print(f"Analyze time : {end - start:.5f} sec")