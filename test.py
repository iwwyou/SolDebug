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

    for idx, rec in enumerate(records):
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
            print(f"[test.py] Line {s}-{e}: ctx={ctx}, current_target_contract={contract_analyzer.current_target_contract}")
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
    "code": "contract OptimisitcRewards {    \n}",
    "startLine": 1,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "    bytes32 public pendingRoot;",
    "startLine": 2,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "    bytes32 public rewardsRoot;",
    "startLine": 3,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "    uint256 public proposalTime;",
    "startLine": 4,
    "endLine": 4,
    "event": "add"
  },
  {
    "code": "    address public proposer;",
    "startLine": 5,
    "endLine": 5,
    "event": "add"
  },
  {
    "code": "    uint256 public challengePeriod = 60 * 60 * 24 * 7;",
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
    "code": "    function proposeRewards(bytes32 newRoot) external {       \n}",
    "startLine": 8,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "        require(msg.sender == proposer, \"Not proposer\");     ",
    "startLine": 9,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "        if (           \n            pendingRoot != bytes32(0) &&\n            proposalTime != 0 &&        \n            block.timestamp > proposalTime + challengePeriod\n        ) {          \n}",
    "startLine": 10,
    "endLine": 15,
    "event": "add"
  },
  {
    "code": "            rewardsRoot = pendingRoot;",
    "startLine": 15,
    "endLine": 15,
    "event": "add"
  },
  {
    "code": "        pendingRoot = newRoot;",
    "startLine": 17,
    "endLine": 17,
    "event": "add"
  },
  {
    "code": "        proposalTime = block.timestamp;",
    "startLine": 18,
    "endLine": 18,
    "event": "add"
  },
  {
    "code": "// @Debugging BEGIN",
    "startLine": 9,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "// @GlobalVar block.timestamp = [100,200];",
    "startLine": 10,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "// @StateVar proposalTime = [0,10];",
    "startLine": 11,
    "endLine": 11,
    "event": "add"
  },
  {
    "code": "// @StateVar challengePeriod = [80,95];",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "// @Debugging END",
    "startLine": 13,
    "endLine": 13,
    "event": "add"
  }
]
start = time.time()

simulate_inputs(test_inputs)
end = time.time()
print(f"Analyze time : {end - start:.5f} sec")