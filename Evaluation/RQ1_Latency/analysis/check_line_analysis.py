"""
Check line-by-line analysis results for contracts.
Prints variable values for each declaration, assignment, return etc.
"""

import sys
import json
from pathlib import Path

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers

JSON_DIR = Path(__file__).parent / "json_intervals" / "interval_0"


def check_contract(json_path):
    """Run contract and print line-by-line analysis."""
    print(f"\n{'='*70}")
    print(f"Contract: {json_path.stem}")
    print(f"{'='*70}")

    with open(json_path, 'r', encoding='utf-8') as f:
        records = json.load(f)

    contract_analyzer = ContractAnalyzer()
    snapman = contract_analyzer.snapman
    batch_mgr = DebugBatchManager(contract_analyzer, snapman)

    in_testcase = False

    for idx, rec in enumerate(records):
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)

        stripped = code.lstrip()

        # BEGIN / END
        if stripped.startswith("// @Debugging BEGIN"):
            batch_mgr.reset()
            in_testcase = True
            continue

        if stripped.startswith("// @Debugging END"):
            batch_mgr.flush()
            in_testcase = False
            continue

        # Debug annotations
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

        # Regular Solidity code
        if code.strip():
            ctx = contract_analyzer.get_current_context_type()
            tree = ParserHelpers.generate_parse_tree(code, ctx, True)
            EnhancedSolidityVisitor(contract_analyzer).visit(tree)

        # Print line analysis
        analysis = contract_analyzer.get_line_analysis(s, e)
        if analysis:
            code_preview = code.strip()[:60]
            print(f"\nLine {s}-{e}: {code_preview}")
            for ln, recs in analysis.items():
                for r in recs:
                    print(f"  L{ln:3} | {r['kind']:>18} | {r['vars']}")


if __name__ == "__main__":
    # Check specific contracts or all
    if len(sys.argv) > 1:
        contract_names = sys.argv[1:]
    else:
        # Default: check a few representative contracts
        contract_names = ["Dripper", "Core", "Dai", "MockChainlinkOracle"]

    for name in contract_names:
        json_path = JSON_DIR / f"{name}_c_annot.json"
        if json_path.exists():
            check_contract(json_path)
        else:
            print(f"WARNING: {json_path} not found")
