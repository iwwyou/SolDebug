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
    "code": "contract ATIDStaking {\n}",
    "startLine": 1,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "    struct LockedStake {\n}",
    "startLine": 2,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "        bool active;        ",
    "startLine": 3,
    "endLine": 3,
    "event": "add"
  },
  {
    "code": "        uint ID;",
    "startLine": 4,
    "endLine": 4,
    "event": "add"
  },
  {
    "code": "        uint prevID;  ",
    "startLine": 5,
    "endLine": 5,
    "event": "add"
  },
  {
    "code": "        uint nextID;        ",
    "startLine": 6,
    "endLine": 6,
    "event": "add"
  },
  {
    "code": "        uint amount;        ",
    "startLine": 7,
    "endLine": 7,
    "event": "add"
  },
  {
    "code": "        uint lockedUntil;        ",
    "startLine": 8,
    "endLine": 8,
    "event": "add"
  },
  {
    "code": "        uint stakeWeight;",
    "startLine": 9,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 11,
    "endLine": 11,
    "event": "add"
  },
  {
    "code": "    mapping(address => mapping(uint => LockedStake)) public lockedStakeMap;",
    "startLine": 12,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "    mapping(address => uint) public headLockedStakeIDMap;",
    "startLine": 13,
    "endLine": 13,
    "event": "add"
  },
  {
    "code": "    mapping(address => uint) public nextLockedStakeIDMap;",
    "startLine": 14,
    "endLine": 14,
    "event": "add"
  },
  {
    "code": "    mapping(address => uint) public tailLockedStakeIDMap;",
    "startLine": 15,
    "endLine": 15,
    "event": "add"
  },
  {
    "code": "    mapping(address => uint) public weightedStakes;",
    "startLine": 16,
    "endLine": 16,
    "event": "add"
  },
  {
    "code": "    mapping(address => uint) public unweightedStakes;",
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
    "code": "    uint public totalWeightedATIDStaked;",
    "startLine": 19,
    "endLine": 19,
    "event": "add"
  },
  {
    "code": "    uint public totalUnweightedATIDStaked;",
    "startLine": 20,
    "endLine": 20,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 21,
    "endLine": 21,
    "event": "add"
  },
  {
    "code": "    function _insertLockedStake(address _stakerAddress, uint _ATIDamount, uint _stakeWeight, uint _lockedUntil) internal returns (uint newLockedStakeID) {\n}",
    "startLine": 22,
    "endLine": 23,
    "event": "add"
  },
  {
    "code": "        if (nextLockedStakeIDMap[_stakerAddress] == 0) {\n}",
    "startLine": 23,
    "endLine": 24,
    "event": "add"
  },
  {
    "code": "            nextLockedStakeIDMap[_stakerAddress] = 1;",
    "startLine": 24,
    "endLine": 24,
    "event": "add"
  },
  {
    "code": "        uint nextLockedStateID = nextLockedStakeIDMap[_stakerAddress];",
    "startLine": 26,
    "endLine": 26,
    "event": "add"
  },
  {
    "code": "        nextLockedStakeIDMap[_stakerAddress]++;",
    "startLine": 27,
    "endLine": 27,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 28,
    "endLine": 28,
    "event": "add"
  },
  {
    "code": "        LockedStake memory newLockedStake = LockedStake({\n            active: true,\n\n            ID: nextLockedStateID,\n            prevID: tailLockedStakeIDMap[_stakerAddress],  \n            nextID: 0,  \n\n            amount: _ATIDamount,\n            lockedUntil: _lockedUntil,\n            stakeWeight: _stakeWeight\n        });",
    "startLine": 29,
    "endLine": 39,
    "event": "add"
  },
  {
    "code": "        lockedStakeMap[_stakerAddress][newLockedStake.ID] = newLockedStake;",
    "startLine": 40,
    "endLine": 40,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 41,
    "endLine": 41,
    "event": "add"
  },
  {
    "code": "        if (headLockedStakeIDMap[_stakerAddress] == 0) {           \n}",
    "startLine": 42,
    "endLine": 43,
    "event": "add"
  },
  {
    "code": "            headLockedStakeIDMap[_stakerAddress] = newLockedStake.ID;",
    "startLine": 43,
    "endLine": 43,
    "event": "add"
  },
  {
    "code": "else {           \n}",
    "startLine": 44,
    "endLine": 45,
    "event": "add"
  },
  {
    "code": "            lockedStakeMap[_stakerAddress][newLockedStake.prevID].nextID = newLockedStake.ID;",
    "startLine": 45,
    "endLine": 45,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 47,
    "endLine": 47,
    "event": "add"
  },
  {
    "code": "        tailLockedStakeIDMap[_stakerAddress] = newLockedStake.ID;",
    "startLine": 48,
    "endLine": 48,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 49,
    "endLine": 49,
    "event": "add"
  },
  {
    "code": "        uint newWeightedStake = newLockedStake.amount * newLockedStake.stakeWeight;",
    "startLine": 50,
    "endLine": 50,
    "event": "add"
  },
  {
    "code": "        weightedStakes[_stakerAddress] += newWeightedStake;",
    "startLine": 51,
    "endLine": 51,
    "event": "add"
  },
  {
    "code": "        totalWeightedATIDStaked += newWeightedStake;        ",
    "startLine": 52,
    "endLine": 52,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 53,
    "endLine": 53,
    "event": "add"
  },
  {
    "code": "        unweightedStakes[_stakerAddress] += _ATIDamount;",
    "startLine": 54,
    "endLine": 54,
    "event": "add"
  },
  {
    "code": "        totalUnweightedATIDStaked += _ATIDamount;",
    "startLine": 55,
    "endLine": 55,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 56,
    "endLine": 56,
    "event": "add"
  },
  {
    "code": "        return newLockedStake.ID;",
    "startLine": 57,
    "endLine": 57,
    "event": "add"
  },
  {
    "code": "// @Debugging BEGIN",
    "startLine": 23,
    "endLine": 23,
    "event": "add"
  },
  {
    "code": "// @StateVar nextLockedStakeIDMap[_stakerAddress] = [1,1];",
    "startLine": 24,
    "endLine": 24,
    "event": "add"
  },
  {
    "code": "// @StateVar tailLockedStakeIDMap[_stakerAddress] = [1,1];",
    "startLine": 25,
    "endLine": 25,
    "event": "add"
  },
  {
    "code": "// @StateVar headLockedStakeIDMap[_stakerAddress] = [1,1];",
    "startLine": 26,
    "endLine": 26,
    "event": "add"
  },
  {
    "code": "// @StateVar weightedStakes[_stakerAddress] = [1,1];",
    "startLine": 27,
    "endLine": 27,
    "event": "add"
  },
  {
    "code": "// @StateVar totalWeightedATIDStaked = [500,500];",
    "startLine": 28,
    "endLine": 28,
    "event": "add"
  },
  {
    "code": "// @StateVar unweightedStakes[_stakerAddress] = [1,1];",
    "startLine": 29,
    "endLine": 29,
    "event": "add"
  },
  {
    "code": "// @StateVar totalUnweightedATIDStaked = [500,500];",
    "startLine": 30,
    "endLine": 30,
    "event": "add"
  },
  {
    "code": "// @LocalVar _ATIDamount = [10,10];",
    "startLine": 31,
    "endLine": 31,
    "event": "add"
  },
  {
    "code": "// @LocalVar _stakeWeight = [1,1];",
    "startLine": 32,
    "endLine": 32,
    "event": "add"
  },
  {
    "code": "// @LocalVar _lockedUntil = [1,1];",
    "startLine": 33,
    "endLine": 33,
    "event": "add"
  },
  {
    "code": "// @Debugging END",
    "startLine": 34,
    "endLine": 34,
    "event": "add"
  }
]

start = time.time()

simulate_inputs(test_inputs)
end = time.time()
print(f"Analyze time : {end - start:.5f} sec")