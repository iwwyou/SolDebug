from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper                      import ParserHelpers     # ★ here
import time

contract_analyzer = ContractAnalyzer()
snapman           = contract_analyzer.snapman
batch_mgr         = DebugBatchManager(contract_analyzer, snapman)

def simulate_inputs(records):
    in_testcase = False

    for rec in records:
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)  # solidity 소스 갱신
        print("target code : ", code)

        stripped = code.lstrip()

        # ① BEGIN / END ---------------------------------------------------
        if stripped.startswith("// @Debugging BEGIN"):
            batch_mgr.reset()  # ★ 새 TC 시작
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            batch_mgr.flush()  # TC 완성 → 1 회 해석
            in_testcase = False
            continue

        # ② 디버그 주석 (@StateVar, @GlobalVar …) --------------------------
        if stripped.startswith("// @"):
            if ev == "add":
                batch_mgr.add_line(code, s, e)
            elif ev == "modify":
                batch_mgr.modify_line(code, s, e)
            elif ev == "delete":
                batch_mgr.delete_line(s)

            # BEGIN-END 밖이면 즉시 재-해석
            if not in_testcase:
                batch_mgr.flush()
            continue

        # ③ 일반 Solidity 코드 --------------------------------------------
        if code.strip():
            ctx = contract_analyzer.get_current_context_type()
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
    "code": "    uint8 public constant MAINTENANCE_FEE = 10;",
    "startLine": 2,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "    uint256 public maintenanceBudget0;",
    "startLine": 3,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "    uint256 public maintenanceBudget1;    ",
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
    "code": "    function _earmarkSomeForMaintenance(uint256 earned0, uint256 earned1) private returns (uint256, uint256) {\n}",
    "startLine": 6,
    "endLine": 7,
    "event": "add"
  },
  {
    "code": "        uint256 toMaintenance;",
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
    "code": "        unchecked {            \n}",
    "startLine": 9,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "            toMaintenance = earned0 / MAINTENANCE_FEE;",
    "startLine": 10,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "            earned0 -= toMaintenance;",
    "startLine": 11,
    "endLine": 11,
    "event": "add"
  },
  {
    "code": "            maintenanceBudget0 += toMaintenance;            ",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "            toMaintenance = earned1 / MAINTENANCE_FEE;",
    "startLine": 13,
    "endLine": 13,
    "event": "add"
  },
  {
    "code": "            earned1 -= toMaintenance;",
    "startLine": 14,
    "endLine": 14,
    "event": "add"
  },
  {
    "code": "            maintenanceBudget1 += toMaintenance;",
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
    "code": "        return (earned0, earned1);",
    "startLine": 18,
    "endLine": 18,
    "event": "add"
  },
  {
    "code": "// @Debugging BEGIN",
    "startLine": 7,
    "endLine": 7,
    "event": "add"
  },
  {
    "code": "// @StateVar maintenanceBudget0 = [100,100];",
    "startLine": 8,
    "endLine": 8,
    "event": "add"
  },
  {
    "code": "// @StateVar maintenanceBudget1 = [100,100];",
    "startLine": 9,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "// @LocalVar earned0 = [50,50];",
    "startLine": 10,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "// @LocalVar earned1 = [50,50];",
    "startLine": 11,
    "endLine": 11,
    "event": "add"
  },
  {
    "code": "// @Debugging END",
    "startLine": 7,
    "endLine": 7,
    "event": "add"
  }
]

start = time.time()

simulate_inputs(test_inputs)
end = time.time()
print(f"Analyze time : {end - start:.5f} sec")