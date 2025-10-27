from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers
import time
import json

def test_contract(annotation_file, contract_name):
    print(f"\n{'='*60}")
    print(f"Testing: {contract_name}")
    print(f"{'='*60}\n")

    contract_analyzer = ContractAnalyzer()
    snapman = contract_analyzer.snapman
    batch_mgr = DebugBatchManager(contract_analyzer, snapman)

    def simulate_inputs(records):
        in_testcase = False

        for idx, rec in enumerate(records):
            code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
            contract_analyzer.update_code(s, e, code, ev)

            stripped = code.lstrip()

            if stripped.startswith("// @Debugging BEGIN"):
                batch_mgr.reset()
                in_testcase = True
                continue

            if stripped.startswith("// @Debugging END"):
                batch_mgr.flush()
                in_testcase = False
                continue

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

            if code.strip():
                ctx = contract_analyzer.get_current_context_type()
                tree = ParserHelpers.generate_parse_tree(code, ctx, True)
                EnhancedSolidityVisitor(contract_analyzer).visit(tree)

    with open(annotation_file, "r") as f:
        test_inputs = json.load(f)

    start = time.time()
    try:
        simulate_inputs(test_inputs)
        end = time.time()
        print(f"\n[OK] {contract_name} completed in {end - start:.3f}s")
        return True
    except Exception as e:
        end = time.time()
        print(f"\n[FAIL] {contract_name} failed: {e}")
        return False

# Test all 5 loop contracts
contracts = [
    ("TimeLockPool_c_annot.json", "TimeLockPool"),
    ("AvatarArtMarketPlace_c_annot.json", "AvatarArtMarketPlace"),
    ("Balancer_c_annot.json", "Balancer"),
    ("AOC_BEP_c_annot.json", "AOC_BEP"),
    ("Core_c_annot.json", "Core"),
]

base_path = "C:\\Users\\isjeon\\PycharmProjects\\pythonProject\\SolDebug\\dataset\\json\\annotation\\"

results = {}
for annot_file, name in contracts:
    result = test_contract(base_path + annot_file, name)
    results[name] = result

print(f"\n{'='*60}")
print("SUMMARY")
print(f"{'='*60}")
for name, success in results.items():
    status = "[OK]" if success else "[FAIL]"
    print(f"{name:30} {status}")
