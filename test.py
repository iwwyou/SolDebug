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

    print(f"DEBUG: Total records to process: {len(records)}")

    for idx, rec in enumerate(records):
        print(f"DEBUG: Processing record {idx}/{len(records)-1}")
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)  # solidity 소스 갱신
        print("target code : ", code)

        stripped = code.lstrip()

        # ① BEGIN / END ---------------------------------------------------
        if stripped.startswith("// @Debugging BEGIN"):
            print(f"DEBUG: Found @Debugging BEGIN at line {s}")
            batch_mgr.reset()  # ★ 새 TC 시작
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            print(f"DEBUG: Found @Debugging END at line {s}, batch_mgr._lines has {len(batch_mgr._lines)} items")
            print(f"DEBUG: batch_targets before flush: {len(contract_analyzer._batch_targets)}")
            print(f"DEBUG: recorder ledger before flush: {len(contract_analyzer.recorder.ledger)}")
            batch_mgr.flush()  # TC 완성 → 1 회 해석
            print(f"DEBUG: _last_func_lines after flush: {getattr(contract_analyzer, '_last_func_lines', None)}")
            print(f"DEBUG: recorder ledger after flush: {len(contract_analyzer.recorder.ledger)}")
            in_testcase = False
            continue

        # ② 디버그 주석 (@StateVar, @GlobalVar …) --------------------------
        if stripped.startswith("// @"):
            print(f"DEBUG: Found debug annotation at line {s}: {stripped[:50]}...")
            if ev == "add":
                print(f"DEBUG: Adding to batch_mgr: {code[:50]}...")
                batch_mgr.add_line(code, s, e)
            elif ev == "modify":
                batch_mgr.modify_line(code, s, e)
            elif ev == "delete":
                batch_mgr.delete_line(s)

            # BEGIN-END 밖이면 즉시 재-해석
            if not in_testcase:
                print(f"DEBUG: Not in testcase, flushing immediately")
                batch_mgr.flush()
            else:
                print(f"DEBUG: In testcase, deferring flush. batch_mgr._lines now has {len(batch_mgr._lines)} items")
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
    "code": "contract TimeLockPool {\n}",
    "startLine": 1,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 2,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "    struct Deposit {\n}",
    "startLine": 3,
    "endLine": 4,
    "event": "add"
  },
  {
    "code": "        uint256 amount;",
    "startLine": 4,
    "endLine": 4,
    "event": "add"
  },
  {
    "code": "        uint64 start;",
    "startLine": 5,
    "endLine": 5,
    "event": "add"
  },
  {
    "code": "        uint64 end;",
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
    "code": "    mapping(address => Deposit[]) public depositsOf;",
    "startLine": 9,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 10,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "    function getTotalDeposit(address _account) public view returns(uint256) {\n}",
    "startLine": 11,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "        uint256 total;",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "        for(uint256 i = 0; i < depositsOf[_account].length; i++) {\n}",
    "startLine": 13,
    "endLine": 14,
    "event": "add"
  },
  {
    "code": "            total += depositsOf[_account][i].amount;",
    "startLine": 14,
    "endLine": 14,
    "event": "add"
  },
  {
    "code": "        return total;",
    "startLine": 16,
    "endLine": 16,
    "event": "add"
  },
  {
    "code": "// @Debugging BEGIN",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "// @StateVar depositsOf[_account][0].amount = [100,200];",
    "startLine": 13,
    "endLine": 13,
    "event": "add"
  },
  {
    "code": "// @StateVar depositsOf[_account][1].amount = [200,300];",
    "startLine": 14,
    "endLine": 14,
    "event": "add"
  },
  {
    "code": "// @StateVar depositsOf[_account][2].amount = [400,500];",
    "startLine": 14,
    "endLine": 14,
    "event": "add"
  },
  {
    "code": "// @LocalVar _account = symbolicAddress 1;",
    "startLine": 15,
    "endLine": 15,
    "event": "add"
  },
  {
    "code": "// @Debugging END",
    "startLine": 16,
    "endLine": 16,
    "event": "add"
  }
]

start = time.time()

simulate_inputs(test_inputs)
end = time.time()
print(f"Analyze time : {end - start:.5f} sec")