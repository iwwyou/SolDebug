import json
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor
from Analyzer.ContractAnalyzer import ContractAnalyzer
from antlr4 import *
from Parser.SolidityLexer import SolidityLexer
from Parser.SolidityParser import SolidityParser

contract_analyzer = ContractAnalyzer()

def map_context_type(context_type):
    context_mapping = {
        'contract': 'interactiveSourceUnit',
        'library': 'interactiveSourceUnit',
        'interface': 'interactiveSourceUnit',
        'enum': 'interactiveSourceUnit',
        'struct': 'interactiveSourceUnit',
        'function': 'interactiveSourceUnit',
        'constructor': 'interactiveSourceUnit',
        'fallback': 'interactiveSourceUnit',
        'receive': 'interactiveSourceUnit',
        'event': 'interactiveSourceUnit',
        'error': 'interactiveSourceUnit',
        'modifier': 'interactiveSourceUnit',
        'stateVariableDeclaration': 'interactiveSourceUnit',
        'enumMember': 'interactiveEnumUnit',
        'structMember': 'interactiveStructUnit',
        'simpleStatement': 'interactiveBlockUnit',
        'if': 'interactiveBlockUnit',
        'for': 'interactiveBlockUnit',
        'while': 'interactiveBlockUnit',
        'do': 'interactiveBlockUnit',
        'try': 'interactiveBlockUnit',
        'return': 'interactiveBlockUnit',
        'break': 'interactiveBlockUnit',
        'continue': 'interactiveBlockUnit',
        'emit': 'interactiveBlockUnit',
        'unchecked': 'interactiveBlockUnit',
        'doWhileWhile': 'interactiveDoWhileUnit',
        'catch': 'interactiveCatchClauseUnit',
        'else_if': 'interactiveIfElseUnit',
        'else': 'interactiveIfElseUnit',
        'debugUnit' : 'debugUnit'
    }

    try:
        return context_mapping[context_type]
    except KeyError:
        print(f"Warning: No mapping found for context_type '{context_type}'. Returning None.")
        return None

def generate_parse_tree(input_stream, context_type):
    input_stream = InputStream(input_stream)
    lexer = SolidityLexer(input_stream)
    token_stream = CommonTokenStream(lexer)
    parser = SolidityParser(token_stream)

    context_rule = map_context_type(context_type)

    if context_rule == 'interactiveStructUnit':
        tree = parser.interactiveStructUnit()
    elif context_rule == 'interactiveEnumUnit':
        tree = parser.interactiveEnumUnit()
    elif context_rule == 'interactiveBlockUnit':
        tree = parser.interactiveBlockUnit()
    elif context_rule == 'interactiveDoWhileUnit':
        tree = parser.interactiveDoWhileUnit()
    elif context_rule == 'interactiveIfElseUnit':
        tree = parser.interactiveIfElseUnit()
    elif context_rule == 'interactiveCatchClauseUnit':
        tree = parser.interactiveCatchClauseUnit()
    elif context_rule == 'debugUnit' :
        tree = parser.debugUnit()
    else:
        tree = parser.interactiveSourceUnit()

    return tree

def simulate_inputs(test_inputs: list[dict], *, silent: bool = False) -> None:
    """
    `test_inputs`  ─ split_solidity_to_inputs 가 뱉은 dict 리스트
    """
    for rec in test_inputs:
        code       = rec["code"]
        start_line = rec["startLine"]
        end_line   = rec["endLine"]
        ev         = rec["event"]

        # 1) source‑buffer 업데이트
        contract_analyzer.update_code(start_line, end_line, code, ev)

        # 2) 완전한 공백 라인은 skip  (brace 카운트만 반영)
        if code.strip() == "":
            continue

        # 3) 현재 컨텍스트 규칙 추론 → 파싱
        ctx_type = contract_analyzer.get_current_context_type()
        tree     = generate_parse_tree(code, ctx_type)

        # 4) 방문 & 분석
        EnhancedSolidityVisitor(contract_analyzer).visit(tree)

        # 5) (옵션)  중간 결과 로그
        if not silent:
            for ln, infos in contract_analyzer.analysis_per_line.items():
                for info in infos:
                    print(f"[line {ln}] {json.dumps(info, ensure_ascii=False)}")

            print("--------------------------------------------------------")


test_inputs = [
    {
        "code": "contract AloeBlend {\n}",
        "startLine": 1,
        "endLine": 2,
        "event": "add"
    },
    {
        "code": "uint8 public constant MAINTENANCE_FEE = 10;",
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
        "code": "uint256 public maintenanceBudget0;",
        "startLine": 4,
        "endLine": 4,
        "event": "add"
    },
    {
        "code": "\n",
        "startLine": 5,
        "endLine": 5,
        "event": "add"
    },
    {
        "code": "uint256 public maintenanceBudget1;",
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
        "code": "uint224[10] public rewardPerGas0Array;",
        "startLine": 8,
        "endLine": 8,
        "event": "add"
    },
    {
        "code": "\n",
        "startLine": 9,
        "endLine": 9,
        "event": "add"
    },
    {
        "code": "uint224[10] public rewardPerGas1Array;",
        "startLine": 10,
        "endLine": 10,
        "event": "add"
    },
    {
        "code": "\n",
        "startLine": 11,
        "endLine": 11,
        "event": "add"
    },
    {
        "code": "uint224 public rewardPerGas0Accumulator;",
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
        "code": "uint224 public rewardPerGas1Accumulator;",
        "startLine": 14,
        "endLine": 14,
        "event": "add"
    },
    {
        "code": "\n",
        "startLine": 15,
        "endLine": 15,
        "event": "add"
    },
    {
        "code": "uint64 public rebalanceCount;",
        "startLine": 16,
        "endLine": 16,
        "event": "add"
    },
    {
        "code": "\n",
        "startLine": 17,
        "endLine": 17,
        "event": "add"
    },
    {
        "code": "function _earmarkSomeForMaintenance(uint256 earned0, uint256 earned1) private returns (uint256, uint256) {\n}",
        "startLine": 18,
        "endLine": 19,
        "event": "add"
    },
    {
        "code": "uint256 toMaintenance;",
        "startLine": 19,
        "endLine": 19,
        "event": "add"
    },
    {
        "code": "\n",
        "startLine": 20,
        "endLine": 20,
        "event": "add"
    },
    {
        "code": "unchecked {\n}",
        "startLine": 21,
        "endLine": 22,
        "event": "add"
    },
    {
        "code": "toMaintenance = earned0 / MAINTENANCE_FEE;",
        "startLine": 22,
        "endLine": 22,
        "event": "add"
    },
    {
        "code": "earned0 -= toMaintenance;",
        "startLine": 23,
        "endLine": 23,
        "event": "add"
    },
    {
        "code": "maintenanceBudget0 += toMaintenance;",
        "startLine": 24,
        "endLine": 24,
        "event": "add"
    },
    {
        "code": "toMaintenance = earned1 / MAINTENANCE_FEE;",
        "startLine": 25,
        "endLine": 25,
        "event": "add"
    },
    {
        "code": "earned1 -= toMaintenance;",
        "startLine": 26,
        "endLine": 26,
        "event": "add"
    },
    {
        "code": "maintenanceBudget1 += toMaintenance;",
        "startLine": 27,
        "endLine": 27,
        "event": "add"
    },
    {
        "code": "\n",
        "startLine": 29,
        "endLine": 29,
        "event": "add"
    },
    {
        "code": "return (earned0, earned1);",
        "startLine": 30,
        "endLine": 30,
        "event": "add"
    },
    {
        "code": "// @LocalVar earned0 = [10,100]",
        "startLine": 19,
        "endLine": 19,
        "event" : "add"
    },
    {
        "code": "// @LocalVar earned1 = [100,200]",
        "startLine": 20,
        "endLine": 20,
        "event" : "add"
    },
    {
        "code": "// @StateVar maintenanceBudget0 = [1000,2000]",
        "startLine": 21,
        "endLine": 21,
        "event" : "add"
    },
    {
        "code": "// @StateVar maintenanceBudget1 = [2000,2000]",
        "startLine": 22,
        "endLine": 22,
        "event" : "add"
    }
]



"""
# ──────────────────────────────────────────────────────────────
# ❸  CLI 엔트리포인트
# ----------------------------------------------------------------
def main(argv: list[str]) -> None:
    ap = argparse.ArgumentParser(
        description="Replay JSON input chunks into the incremental analyzer"
    )
    ap.add_argument("json_file", help="input file produced by split_solidity_to_inputs")
    ap.add_argument("-q", "--quiet", action="store_true",
                    help="suppress per‑line analysis dumps")
    args = ap.parse_args(argv)

    try:
        raw = pathlib.Path(args.json_file).read_text(encoding="utf-8")
        inputs = json.loads(raw)
    except FileNotFoundError:
        sys.exit(f"✖ file not found: {args.json_file}")
    except json.JSONDecodeError as e:
        sys.exit(f"✖ JSON parse error: {e}")

    simulate_inputs(inputs, silent=args.quiet)


if __name__ == "__main__":
    main(sys.argv[1:])
"""

simulate_inputs(test_inputs)