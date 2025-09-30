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
            print(f"DEBUG: batch_targets before flush: {len(contract_analyzer._batch_targets)}")
            print(f"DEBUG: recorder ledger before flush: {len(contract_analyzer.recorder.ledger)}")
            batch_mgr.flush()  # TC 완성 → 1 회 해석
            print(f"DEBUG: _last_func_lines after flush: {getattr(contract_analyzer, '_last_func_lines', None)}")
            print(f"DEBUG: recorder ledger after flush: {len(contract_analyzer.recorder.ledger)}")
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
    "code": "contract Amoss {\n}",
    "startLine": 1,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "    uint256 private _totalSupply = 1*10**(9+18);    ",
    "startLine": 2,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "    mapping(address => uint256) private _balances;    ",
    "startLine": 3,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 4,
    "endLine": 4,
    "event": "add"
  },
  {
    "code": "    function _beforeTokenTransfer(address from, address to, uint256 amount) internal virtual {        \n}",
    "startLine": 5,
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
    "code": "    function _afterTokenTransfer(address from, address to, uint256 amount) internal virtual {        \n}",
    "startLine": 8,
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
    "code": "    function _burn(address account, uint256 amount) internal virtual {\n}",
    "startLine": 11,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "        require(account != address(0), \"ERC20: burn from the zero address\");",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "        _beforeTokenTransfer(account, address(0), amount);",
    "startLine": 13,
    "endLine": 13,
    "event": "add"
  },
  {
    "code": "        uint256 accountBalance = _balances[account];",
    "startLine": 14,
    "endLine": 14,
    "event": "add"
  },
  {
    "code": "        require(accountBalance >= amount, \"ERC20: burn amount exceeds balance\");",
    "startLine": 15,
    "endLine": 15,
    "event": "add"
  },
  {
    "code": "        unchecked {\n}",
    "startLine": 16,
    "endLine": 17,
    "event": "add"
  },
  {
    "code": "            _balances[account] = accountBalance - amount;",
    "startLine": 17,
    "endLine": 17,
    "event": "add"
  },
  {
    "code": "        _totalSupply -= amount;",
    "startLine": 19,
    "endLine": 19,
    "event": "add"
  },
  {
    "code": "        _afterTokenTransfer(account, address(0), amount);",
    "startLine": 20,
    "endLine": 20,
    "event": "add"
  },
  {
    "code": "// @Debugging BEGIN",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "// @StateVar _totalSupply = [500,500];",
    "startLine": 13,
    "endLine": 13,
    "event": "add"
  },
  {
    "code": "// @StateVar _balances[account] = [1000,1000];",
    "startLine": 14,
    "endLine": 14,
    "event": "add"
  },
  {
    "code": "// @LocalVar amount = [10,10];",
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