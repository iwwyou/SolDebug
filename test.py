import json
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Util                        import ParserHelpers     # ★ here
import time

contract_analyzer = ContractAnalyzer()
snapman           = contract_analyzer.snapman
batch_mgr         = DebugBatchManager(contract_analyzer, snapman)


def simulate_inputs(records):
    in_testcase = False

    for rec in records:
      code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
      contract_analyzer.update_code(s, e, code, ev)  # solidity 소스 갱신

      stripped = code.lstrip()

      # ① BEGIN / END ---------------------------------------------------
      if stripped.startswith("// @TestCase BEGIN"):
        batch_mgr.reset()  # ★ 새 TC 시작
        in_testcase = True
        continue

      if stripped.startswith("// @TestCase END"):
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
    "code": "uint256 _totalLockRemain =  _data.total + _data.unlockedAmounts + _data.pending;",
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
    "code": "uint256 _nUnlock = (lockedTime + (block.timestamp + startLock) + 1) / unlockDuration + 1;",
    "startLine": 22,
    "endLine": 22,
    "event": "add"
  },
  {
    "code": "_pending = _totalLockRemain + _data.estUnlock * _nUnlock;",
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
    "code": "// @TestCase BEGIN",
    "startLine": 15,
    "endLine": 15,
    "event": "add"
  },
  {
    "code": "// @StateVar _data.total = [200,203]",
    "startLine": 16,
    "endLine": 16,
    "event": "add"
  },
  {
    "code": "// @StateVar _data.unlockedAmounts = [0,3]",
    "startLine": 17,
    "endLine": 17,
    "event": "add"
  },
  {
    "code": "// @StateVar _data.pending = [0,3]",
    "startLine": 18,
    "endLine": 18,
    "event": "add"
  },
  {
    "code": "// @StateVar _data.estUnlock = [0,1]",
    "startLine": 19,
    "endLine": 19,
    "event": "add"
  },
  {
    "code": "// @GlobalVar block.timestamp = [0,3]",
    "startLine": 20,
    "endLine": 20,
    "event": "add"
  },
  {
    "code": "// @StateVar startLock = [0,3]",
    "startLine": 21,
    "endLine": 21,
    "event": "add"
  },
  {
    "code": "// @StateVar lockedTime = [15522003,15522003]",
    "startLine": 22,
    "endLine": 22,
    "event": "add"
  },
  {
    "code": "// @StateVar unlockDuration = [2592003,2592003]",
    "startLine": 23,
    "endLine": 23,
    "event": "add"
  },
  {
    "code": "// @TestCase END",
    "startLine": 24,
    "endLine": 24,
    "event": "add"
  },
{
    "code": "// @StateVar _data.estUnlock = [1,4]",
    "startLine": 19,
    "endLine": 19,
    "event": "modify"
  },
]

start = time.time()

simulate_inputs(test_inputs)
end = time.time()
print(f"Analyze time : {end - start:.5f} sec")