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
        "code": "contract AloeBlend {\n}",
        "startLine": 1,
        "endLine": 2,
        "event": "add"
    },
    {
        "code": "uint8 public constant MAINTENANCE_FEE = 10;",
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
        "code": "uint256 public maintenanceBudget0;",
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
        "code": "uint256 public maintenanceBudget1;",
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
        "code": "uint224[10] public rewardPerGas0Array;",
        "startLine": 8,
        "endLine": 8,
        "event": "add"
    },
    {
        "code": "\n",
        "startLine": 9,
        "endLine": 9,
        "event": "add"
    },
    {
        "code": "uint224 public rewardPerGas0Accumulator;",
        "startLine": 10,
        "endLine": 10,
        "event": "add"
    },
    {
        "code": "\n",
        "startLine": 11,
        "endLine": 11,
        "event": "add"
    },
    {
        "code": "uint64 public rebalanceCount;",
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
        "code": "function _earmarkSomeForMaintenance(uint256 earned0, uint256 earned1) private returns (uint256, uint256) {\n}",
        "startLine": 14,
        "endLine": 15,
        "event": "add"
    },
    {
        "code": "uint256 toMaintenance;",
        "startLine": 15,
        "endLine": 15,
        "event": "add"
    },
    {
        "code": "\n",
        "startLine": 16,
        "endLine": 16,
        "event": "add"
    },
    {
        "code": "unchecked {\n}",
        "startLine": 17,
        "endLine": 18,
        "event": "add"
    },
    {
        "code": "toMaintenance = earned0 / MAINTENANCE_FEE;",
        "startLine": 18,
        "endLine": 18,
        "event": "add"
    },
    {
        "code": "earned0 -= toMaintenance;",
        "startLine": 19,
        "endLine": 19,
        "event": "add"
    },
    {
        "code": "maintenanceBudget0 += toMaintenance;",
        "startLine": 20,
        "endLine": 20,
        "event": "add"
    },
    {
        "code": "toMaintenance = earned1 / MAINTENANCE_FEE;",
        "startLine": 21,
        "endLine": 21,
        "event": "add"
    },
    {
        "code": "earned1 -= toMaintenance;",
        "startLine": 22,
        "endLine": 22,
        "event": "add"
    },
    {
        "code": "maintenanceBudget1 += toMaintenance;",
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
        "code": "return (earned0, earned1);",
        "startLine": 26,
        "endLine": 26,
        "event": "add"
    },
    {
        "code": "\n",
        "startLine": 28,
        "endLine": 28,
        "event": "add"
    },
    {
        "code": "function pushRewardPerGas0(uint224 rewardPerGas0) private {\n}",
        "startLine": 29,
        "endLine": 30,
        "event": "add"
    },
    {
        "code": "unchecked {\n}",
        "startLine": 30,
        "endLine": 31,
        "event": "add"
    },
    {
        "code": "rewardPerGas0 /= 10;",
        "startLine": 31,
        "endLine": 31,
        "event": "add"
    },
    {
        "code": "rewardPerGas0Accumulator = rewardPerGas0Accumulator + rewardPerGas0 - rewardPerGas0Array[rebalanceCount % 10];",
        "startLine": 32,
        "endLine": 32,
        "event": "add"
    },
    {
        "code": "rewardPerGas0Array[rebalanceCount % 10] = rewardPerGas0;",
        "startLine": 33,
        "endLine": 33,
        "event": "add"
    },
    {
        "code": "// @TestCase BEGIN",
        "startLine": 30,
        "endLine": 30,
        "event": "add"
    },
    {
        "code": "// @LocalVar rewardPerGas0 = [100,100]",
        "startLine": 31,
        "endLine": 31,
        "event": "add"
    },
    {
        "code": "// @StateVar rebalanceCount = [1,1]",
        "startLine": 32,
        "endLine": 32,
        "event": "add"
    },
    {
        "code": "// @StateVar rewardPerGas0Accumulator = [10,20]",
        "startLine": 33,
        "endLine": 33,
        "event": "add"
    },
    {
        "code": "// @StateVar rewardPerGas0Array = array[1,2,3,4,5,6,7,8,9,10]",
        "startLine": 34,
        "endLine": 34,
        "event": "add"
    },
    {
        "code": "// @TestCase END",
        "startLine": 35,
        "endLine": 35,
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