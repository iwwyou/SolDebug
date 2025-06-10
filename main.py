import json
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Util                        import ParserHelpers     # ★ here
import time

contract_analyzer = ContractAnalyzer()
snapman           = contract_analyzer.snapman
batch_mgr         = DebugBatchManager(contract_analyzer, snapman)


def simulate_inputs(records, silent=False):
    in_testcase = False

    for rec in records:
        code, s, e, ev = \
            rec["code"], rec["startLine"], rec["endLine"], rec["event"]

        # ───── Solidity 소스 반영 (add/modify/delete) ─────
        contract_analyzer.update_code(s, e, code, ev)

        stripped = code.lstrip()

        # ---------- BEGIN / END ---------------------------------
        if stripped.startswith("// @TestCase BEGIN"):
            batch_mgr.reset()
            in_testcase = True
            continue

        if stripped.startswith("// @TestCase END"):
            batch_mgr.flush()           # 전체 해석
            in_testcase = False
            continue

        # ---------- 주석(디버그 어노테이션) ----------------------
        if stripped.startswith("// @"):
            if ev == "add":
                batch_mgr.add_line(code, s, e)
            elif ev == "modify":
                batch_mgr.modify_line(code, s, e)
            elif ev == "delete":
                batch_mgr.delete_line(s)

            # BEGIN~END 밖이거나 modify/delete 면 즉시 해석
            if (not in_testcase) or ev in {"modify", "delete"}:
                batch_mgr.flush()
            continue

        # ---------- 일반 Solidity 한 줄 ------------------------
        if code.strip():           # 공백 라인은 생략
            ctx = contract_analyzer.get_current_context_type()
            tree = ParserHelpers.generate_parse_tree(code, ctx, True)
            EnhancedSolidityVisitor(contract_analyzer).visit(tree)

            if not silent:
                analysis = contract_analyzer.get_line_analysis(s, e)
                for ln, recs in analysis.items():
                    for r in recs:
                        print(f"L{ln:3} | {r['kind']:>12} | {r['vars']}")

