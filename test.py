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

        # 1) source‑buffer 업데이트
        contract_analyzer.update_code(start_line, end_line, code)

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
            for ln, infos in contract_analyzer.get_line_analysis(start_line, end_line).items():
                for info in infos:  # 같은 줄에 여러 기록이 있을 수 있음
                    print(f"[line {ln}] {json.dumps(info, ensure_ascii=False)}")
test_inputs = [
  {
    "code": "contract AloeBlend {\n}",
    "startLine": 1,
    "endLine": 2
  },
  {
    "code": "uint8 public constant MAINTENANCE_FEE = 10;",
    "startLine": 2,
    "endLine": 2
  },
  {
    "code": "\n",
    "startLine": 3,
    "endLine": 3
  },
  {
    "code": "uint256 public maintenanceBudget0;",
    "startLine": 4,
    "endLine": 4
  },
  {
    "code": "\n",
    "startLine": 5,
    "endLine": 5
  },
  {
    "code": "uint256 public maintenanceBudget1;",
    "startLine": 6,
    "endLine": 6
  },
  {
    "code": "\n",
    "startLine": 7,
    "endLine": 7
  },
  {
    "code": "uint224[10] public rewardPerGas0Array;",
    "startLine": 8,
    "endLine": 8
  },
  {
    "code": "\n",
    "startLine": 9,
    "endLine": 9
  },
  {
    "code": "uint224[10] public rewardPerGas1Array;",
    "startLine": 10,
    "endLine": 10
  },
  {
    "code": "\n",
    "startLine": 11,
    "endLine": 11
  },
  {
    "code": "uint224 public rewardPerGas0Accumulator;",
    "startLine": 12,
    "endLine": 12
  },
  {
    "code": "\n",
    "startLine": 13,
    "endLine": 13
  },
  {
    "code": "uint224 public rewardPerGas1Accumulator;",
    "startLine": 14,
    "endLine": 14
  },
  {
    "code": "\n",
    "startLine": 15,
    "endLine": 15
  },
  {
    "code": "uint64 public rebalanceCount;",
    "startLine": 16,
    "endLine": 16
  },
  {
    "code": "\n",
    "startLine": 17,
    "endLine": 17
  },
  {
    "code": "function _earmarkSomeForMaintenance(uint256 earned0, uint256 earned1) private returns (uint256, uint256) {\n}",
    "startLine": 18,
    "endLine": 19
  },
  {
    "code": "uint256 toMaintenance;",
    "startLine": 19,
    "endLine": 19
  },
  {
    "code": "\n",
    "startLine": 20,
    "endLine": 20
  },
  {
    "code": "unchecked {\n}",
    "startLine": 21,
    "endLine": 22
  },
  {
    "code": "toMaintenance = earned0 / MAINTENANCE_FEE;",
    "startLine": 22,
    "endLine": 22
  },
  {
    "code": "earned0 -= toMaintenance;",
    "startLine": 23,
    "endLine": 23
  },
  {
    "code": "maintenanceBudget0 += toMaintenance;",
    "startLine": 24,
    "endLine": 24
  },
  {
    "code": "toMaintenance = earned1 / MAINTENANCE_FEE;",
    "startLine": 25,
    "endLine": 25
  },
  {
    "code": "earned1 -= toMaintenance;",
    "startLine": 26,
    "endLine": 26
  },
  {
    "code": "maintenanceBudget1 += toMaintenance;",
    "startLine": 27,
    "endLine": 27
  },
  {
    "code": "\n",
    "startLine": 29,
    "endLine": 29
  },
  {
    "code": "return (earned0, earned1);",
    "startLine": 30,
    "endLine": 30
  },
  {
    "code": "\n",
    "startLine": 32,
    "endLine": 32
  },
  {
    "code": "function pushRewardPerGas0(uint224 rewardPerGas0) private {\n}",
    "startLine": 33,
    "endLine": 34
  },
  {
    "code": "unchecked {\n}",
    "startLine": 34,
    "endLine": 35
  },
  {
    "code": "rewardPerGas0 /= 10;",
    "startLine": 35,
    "endLine": 35
  },
  {
    "code": "rewardPerGas0Accumulator = rewardPerGas0Accumulator + rewardPerGas0 - rewardPerGas0Array[rebalanceCount % 10];",
    "startLine": 36,
    "endLine": 36
  },
  {
    "code": "rewardPerGas0Array[rebalanceCount % 10] = rewardPerGas0;",
    "startLine": 37,
    "endLine": 37
  },
  {
    "code": "\n",
    "startLine": 40,
    "endLine": 40
  },
  {
    "code": "function pushRewardPerGas1(uint224 rewardPerGas1) private {\n}",
    "startLine": 41,
    "endLine": 42
  },
  {
    "code": "unchecked {\n}",
    "startLine": 42,
    "endLine": 43
  },
  {
    "code": "rewardPerGas1 /= 10;",
    "startLine": 43,
    "endLine": 43
  },
  {
    "code": "rewardPerGas1Accumulator = rewardPerGas1Accumulator + rewardPerGas1 - rewardPerGas1Array[rebalanceCount % 10];",
    "startLine": 44,
    "endLine": 44
  },
  {
    "code": "rewardPerGas1Array[rebalanceCount % 10] = rewardPerGas1;",
    "startLine": 45,
    "endLine": 45
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