"""
result[resultIndex] = tokenItemId 노드에서
visit_cnt별 in_vars/out_vars 추적 테스트
- for_join의 predecessor 및 initial entry 값 추적
"""
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Analyzer.DebugUnitAnalyzer import DebugBatchManager
from Utils.Helper import ParserHelpers

contract_analyzer = ContractAnalyzer()
snapman = contract_analyzer.snapman
batch_mgr = DebugBatchManager(contract_analyzer, snapman)

# Engine 패치: fixpoint에서 initial entry 추적
from Interpreter.Engine import Engine
original_fixpoint = Engine.fixpoint

def patched_fixpoint(self, head):
    from Utils.Helper import VariableEnv
    from collections import deque, defaultdict

    G = self.an.current_target_function_cfg.graph
    loop_nodes = self.traverse_loop_nodes(head)

    # for_join 노드와 그 predecessor들 찾기
    join_node = None
    for p in G.predecessors(head):
        if getattr(p, "fixpoint_evaluation_node", False):
            join_node = p
            break

    if join_node:
        print(f"\n{'='*60}")
        print(f"[FIXPOINT START] head={head.name}, join_node={join_node.name}")
        print(f"join_node predecessors:")
        for pp in G.predecessors(join_node):
            is_in_loop = pp in loop_nodes
            pp_vars = getattr(pp, "variables", {}) or {}
            result_val = None
            if 'result' in pp_vars:
                r = pp_vars['result']
                if hasattr(r, 'elements'):
                    result_val = [e.value if hasattr(e, 'value') else e for e in r.elements[:3]]
            print(f"  - {pp.name}: in_loop={is_in_loop}, result={result_val}")
        print(f"{'='*60}\n")

    # 원래 fixpoint 호출
    return original_fixpoint(self, head)

Engine.fixpoint = patched_fixpoint

def simulate_inputs(records):
    in_testcase = False

    for idx, rec in enumerate(records):
        code, s, e, ev = rec["code"], rec["startLine"], rec["endLine"], rec["event"]
        contract_analyzer.update_code(s, e, code, ev)
        print("target code : ", code[:60] if len(code) > 60 else code)

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

        analysis = contract_analyzer.get_line_analysis(s, e)
        if analysis:
            print(f"[{s}-{e}]  analysis =>")
        for ln, recs in analysis.items():
            for r in recs:
                print(f"  L{ln:3} | {r['kind']:>14} | {r['vars']}")

        print("--------------------------------------------------------")


# 기존 JSON 포맷과 동일하게 구성
test_inputs = [
    {"code": "contract AvatarArtMarketplace {\n}", "startLine": 1, "endLine": 2, "event": "add"},
    {"code": "    uint256[] internal _tokens;", "startLine": 2, "endLine": 2, "event": "add"},
    {"code": "\n", "startLine": 3, "endLine": 3, "event": "add"},
    {"code": "    function _removeFromTokens(uint tokenId) internal view returns(uint256[] memory){\n}", "startLine": 4, "endLine": 5, "event": "add"},
    {"code": "        uint256 tokenCount = _tokens.length;", "startLine": 5, "endLine": 5, "event": "add"},
    {"code": "        uint256[] memory result = new uint256[](tokenCount);", "startLine": 6, "endLine": 6, "event": "add"},
    {"code": "        uint256 resultIndex = 0;", "startLine": 7, "endLine": 7, "event": "add"},
    {"code": "        for(uint tokenIndex = 0; tokenIndex < tokenCount; tokenIndex++){\n}", "startLine": 8, "endLine": 9, "event": "add"},
    {"code": "            uint tokenItemId = _tokens[tokenIndex];", "startLine": 9, "endLine": 9, "event": "add"},
    {"code": "            if(tokenItemId != tokenId){\n}", "startLine": 10, "endLine": 11, "event": "add"},
    {"code": "                result[resultIndex] = tokenItemId;", "startLine": 11, "endLine": 11, "event": "add"},
    {"code": "                resultIndex++;", "startLine": 12, "endLine": 12, "event": "add"},
    {"code": "\n", "startLine": 15, "endLine": 15, "event": "add"},
    {"code": "        return result;", "startLine": 16, "endLine": 16, "event": "add"},
    # Debugging annotations
    {"code": "// @Debugging BEGIN", "startLine": 5, "endLine": 5, "event": "add"},
    {"code": "// @StateVar _tokens = array [1,2,3];", "startLine": 6, "endLine": 6, "event": "add"},
    {"code": "// @LocalVar tokenId = [4,4];", "startLine": 7, "endLine": 7, "event": "add"},
    {"code": "// @Debugging END", "startLine": 8, "endLine": 8, "event": "add"},
]

if __name__ == "__main__":
    simulate_inputs(test_inputs)
    Engine.fixpoint = original_fixpoint
