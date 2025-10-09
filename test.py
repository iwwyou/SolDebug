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
    "code": "contract AOC_BEP {\n}",
    "startLine": 1,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "    struct UserInfo {\n}",
    "startLine": 2,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "        uint256 balance;",
    "startLine": 3,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "        uint256 level;",
    "startLine": 4,
    "endLine": 4,
    "event": "add"
  },
  {
    "code": "        uint256 year;",
    "startLine": 5,
    "endLine": 5,
    "event": "add"
  },
  {
    "code": "        uint256 month;",
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
    "code": "    struct Level {\n}",
    "startLine": 9,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "        uint256 start;",
    "startLine": 10,
    "endLine": 10,
    "event": "add"
  },
  {
    "code": "        uint256 end;",
    "startLine": 11,
    "endLine": 11,
    "event": "add"
  },
  {
    "code": "        uint256 percentage;",
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
    "code": "    mapping(address => UserInfo) public userInfo;",
    "startLine": 15,
    "endLine": 15,
    "event": "add"
  },
  {
    "code": "    mapping(uint256 => Level) public levels;",
    "startLine": 16,
    "endLine": 16,
    "event": "add"
  },
  {
    "code": "    mapping(address => uint256) private _balances;",
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
    "code": "    function updateUserInfo(address account, uint256 year, uint256 month) internal {\n}",
    "startLine": 19,
    "endLine": 20,
    "event": "add"
  },
  {
    "code": "        userInfo[account].balance = _balances[account];",
    "startLine": 20,
    "endLine": 20,
    "event": "add"
  },
  {
    "code": "        userInfo[account].year = year;",
    "startLine": 21,
    "endLine": 21,
    "event": "add"
  },
  {
    "code": "        userInfo[account].month = month;",
    "startLine": 22,
    "endLine": 22,
    "event": "add"
  },
  {
    "code": "        for(uint256 i = 1; i <= 4; i++) {\n}",
    "startLine": 23,
    "endLine": 24,
    "event": "add"
  },
  {
    "code": "            if(i == 4) {\n}",
    "startLine": 24,
    "endLine": 25,
    "event": "add"
  },
  {
    "code": "                userInfo[account].level = i;",
    "startLine": 25,
    "endLine": 25,
    "event": "add"
  },
  {
    "code": "                break;",
    "startLine": 26,
    "endLine": 26,
    "event": "add"
  },
  {
    "code": "            if(block.timestamp >= levels[i].start && block.timestamp <= levels[i].end) {\n}",
    "startLine": 28,
    "endLine": 29,
    "event": "add"
  },
  {
    "code": "                userInfo[account].level = i;",
    "startLine": 29,
    "endLine": 29,
    "event": "add"
  },
  {
    "code": "                break;",
    "startLine": 30,
    "endLine": 30,
    "event": "add"
  }
]

start = time.time()

simulate_inputs(test_inputs)
end = time.time()
print(f"Analyze time : {end - start:.5f} sec")