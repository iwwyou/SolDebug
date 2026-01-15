from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper                      import ParserHelpers     # ★ here
import time
import json

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
    "code": "contract Dai {\n}",
    "startLine": 1,
    "endLine": 2,
    "event": "add"
  },
  {
    "code": "    mapping (address => uint) public wards;",
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
    "code": "    uint256 public totalSupply;",
    "startLine": 4,
    "endLine": 4,
    "event": "add"
  },
  {
    "code": "    mapping (address => uint) public balanceOf;",
    "startLine": 5,
    "endLine": 5,
    "event": "add"
  },
  {
    "code": "    mapping (address => mapping (address => uint)) public allowance;    ",
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
    "code": "    function add(uint x, uint y) internal pure returns (uint z) {\n}",
    "startLine": 8,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "        require((z = x + y) >= x);",
    "startLine": 9,
    "endLine": 9,
    "event": "add"
  },
  {
    "code": "    function sub(uint x, uint y) internal pure returns (uint z) {\n}",
    "startLine": 11,
    "endLine": 12,
    "event": "add"
  },
  {
    "code": "        require((z = x - y) <= x);",
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
    "code": "    function transferFrom(address src, address dst, uint wad) public returns (bool) {\n}",
    "startLine": 15,
    "endLine": 16,
    "event": "add"
  },
  {
    "code": "        require(balanceOf[src] >= wad, \"Dai/insufficient-balance\");",
    "startLine": 16,
    "endLine": 16,
    "event": "add"
  },
  {
    "code": "        if (src != msg.sender && allowance[src][msg.sender] != uint(-1)) {\n}",
    "startLine": 17,
    "endLine": 18,
    "event": "add"
  },
  {
    "code": "            require(allowance[src][msg.sender] >= wad, \"Dai/insufficient-allowance\");",
    "startLine": 18,
    "endLine": 18,
    "event": "add"
  },
  {
    "code": "            allowance[src][msg.sender] = sub(allowance[src][msg.sender], wad);",
    "startLine": 19,
    "endLine": 19,
    "event": "add"
  },
  {
    "code": "        balanceOf[src] = sub(balanceOf[src], wad);",
    "startLine": 21,
    "endLine": 21,
    "event": "add"
  },
  {
    "code": "        balanceOf[dst] = add(balanceOf[dst], wad);",
    "startLine": 22,
    "endLine": 22,
    "event": "add"
  },
  {
    "code": "\n",
    "startLine": 23,
    "endLine": 23,
    "event": "add"
  },
  {
    "code": "        return true;",
    "startLine": 24,
    "endLine": 24,
    "event": "add"
  },
  {
    "code": "// @Debugging BEGIN",
    "startLine": 16,
    "endLine": 16,
    "event": "add"
  },
  {
    "code": "// @GlobalVar msg.sender = symbolicAddress 0;",
    "startLine": 17,
    "endLine": 17,
    "event": "add"
  },
  {
    "code": "// @LocalVar src = symbolicAddress 1;",
    "startLine": 18,
    "endLine": 18,
    "event": "add"
  },
  {
    "code": "// @LocalVar dst = symbolicAddress 2;",
    "startLine": 19,
    "endLine": 19,
    "event": "add"
  },
  {
    "code": "// @StateVar balanceOf[src] = [1000,1000];",
    "startLine": 20,
    "endLine": 20,
    "event": "add"
  },
  {
    "code": "// @StateVar allowance[src][msg.sender] = [100,100];",
    "startLine": 21,
    "endLine": 21,
    "event": "add"
  },
  {
    "code": "// @StateVar balanceOf[dst] = [500,500];",
    "startLine": 22,
    "endLine": 22,
    "event": "add"
  },
  {
    "code": "// @LocalVar wad = [50,50];",
    "startLine": 23,
    "endLine": 23,
    "event": "add"
  },
  {
    "code": "// @Debugging END",
    "startLine": 24,
    "endLine": 24,
    "event": "add"
  }
]

# JSON 파일에서 테스트 입력 로드
json_path = r"Evaluation\RQ1_Latency\json_intervals\interval_0\MockChainlinkOracle_c_annot.json"
with open(json_path, 'r', encoding='utf-8') as f:
    test_inputs = json.load(f)

start = time.time()

simulate_inputs(test_inputs)
end = time.time()
print(f"Analyze time : {end - start:.5f} sec")
