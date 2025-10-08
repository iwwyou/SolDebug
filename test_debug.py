from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers
import time
import sys

contract_analyzer = ContractAnalyzer()
snapman = contract_analyzer.snapman
batch_mgr = DebugBatchManager(contract_analyzer, snapman)

def simulate_inputs(records):
    in_testcase = False

    for idx, rec in enumerate(records):
        print(f"[{idx}] Processing line {rec['startLine']}: {rec['code'][:50]}...", flush=True)
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]

        try:
            contract_analyzer.update_code(s, e, code, ev)
        except Exception as ex:
            print(f"ERROR in update_code: {ex}", flush=True)
            raise

        stripped = code.lstrip()

        # ① BEGIN / END
        if stripped.startswith("// @Debugging BEGIN"):
            print(f"  → Found BEGIN", flush=True)
            batch_mgr.reset()
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            print(f"  → Found END, flushing...", flush=True)
            try:
                batch_mgr.flush()
            except Exception as ex:
                print(f"ERROR in flush: {ex}", flush=True)
                raise
            in_testcase = False
            continue

        # ② 디버그 주석
        if stripped.startswith("// @"):
            print(f"  → Debug annotation", flush=True)
            if ev == "add":
                batch_mgr.add_line(code, s, e)
            elif ev == "modify":
                batch_mgr.modify_line(code, s, e)
            elif ev == "delete":
                batch_mgr.delete_line(s)

            if not in_testcase:
                print(f"  → Flushing immediately...", flush=True)
                try:
                    batch_mgr.flush()
                except Exception as ex:
                    print(f"ERROR in immediate flush: {ex}", flush=True)
                    raise
            continue

        # ③ 일반 Solidity 코드
        if code.strip():
            ctx = contract_analyzer.get_current_context_type()
            print(f"  → Parsing context={ctx}", flush=True)
            try:
                tree = ParserHelpers.generate_parse_tree(code, ctx, True)
                EnhancedSolidityVisitor(contract_analyzer).visit(tree)
            except Exception as ex:
                print(f"ERROR in parsing/visiting: {ex}", flush=True)
                raise

        print(f"  [OK] Line {s} completed", flush=True)

# Minimal test case
test_inputs = [
    {"code": "contract Balancer {\n}", "startLine": 1, "endLine": 2, "event": "add"},
    {"code": "    address[] public actionBuilders;", "startLine": 2, "endLine": 2, "event": "add"},
    {"code": "// @StateVar actionBuilders = arrayAddress[1,2,3];", "startLine": 3, "endLine": 3, "event": "add"},
]

print("Starting test...", flush=True)
start = time.time()

try:
    simulate_inputs(test_inputs)
    end = time.time()
    print(f"\n[SUCCESS] Test completed in {end - start:.5f} sec")
except KeyboardInterrupt:
    print("\n[INTERRUPTED] Test interrupted by user")
    sys.exit(1)
except Exception as e:
    print(f"\n[FAILED] Test failed: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
