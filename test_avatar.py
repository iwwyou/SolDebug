from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper                      import ParserHelpers
import time
import json

contract_analyzer = ContractAnalyzer()
snapman           = contract_analyzer.snapman
batch_mgr         = DebugBatchManager(contract_analyzer, snapman)

def simulate_inputs(records):
    in_testcase = False

    for idx, rec in enumerate(records):
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)
        print("target code : ", code)

        stripped = code.lstrip()

        # ① BEGIN / END
        if stripped.startswith("// @Debugging BEGIN"):
            batch_mgr.reset()
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            batch_mgr.flush()
            in_testcase = False
            continue

        # ② 디버그 주석
        if stripped.startswith("// @"):
            if ev == "add":
                batch_mgr.add_line(code, s, e)
            elif ev == "modify":
                batch_mgr.modify_line(code, s, e)
            elif ev == "delete":
                batch_mgr.delete_line(s)

            if not in_testcase:
                batch_mgr.flush()
            continue

        # ③ 일반 Solidity 코드
        if code.strip():
            ctx = contract_analyzer.get_current_context_type()
            print(f"[test_avatar.py] Line {s}-{e}: ctx={ctx}, current_target_contract={contract_analyzer.current_target_contract}")
            tree = ParserHelpers.generate_parse_tree(code, ctx, True)
            EnhancedSolidityVisitor(contract_analyzer).visit(tree)

        analysis = contract_analyzer.get_line_analysis(s, e)
        if analysis:
            print(f"[{s}-{e}]  analysis =>")
        for ln, recs in analysis.items():
            for r in recs:
                print(f"  L{ln:3} | {r['kind']:>14} | {r['vars']}")

        print("--------------------------------------------------------")


# Load annotation from JSON file
with open("C:\\Users\\isjeon\\PycharmProjects\\pythonProject\\SolDebug\\dataset\\json\\annotation\\AvatarArtMarketPlace_c_annot.json", "r") as f:
    test_inputs = json.load(f)

start = time.time()
simulate_inputs(test_inputs)
end = time.time()
print(f"Analyze time : {end - start:.5f} sec")
