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

def simulate_input(test_inputs):
    for input_data in test_inputs:
        code = input_data['code']
        start_line = input_data['startLine']
        end_line = input_data['endLine']

        contract_analyzer.update_code(start_line, end_line, code)

        if code == "\n" :
            continue

        # Parse the received code based on context_type
        tree = generate_parse_tree(code, contract_analyzer.get_current_context_type())

        visitor = EnhancedSolidityVisitor(contract_analyzer)
        visitor.visit(tree)

        # Get and print the analysis result
        result = contract_analyzer.get_analysis_result()
        print(json.dumps(result, indent=4))

test_inputs = [

    {
        'code': 'contract USDs { \n }',
        'startLine': 1,
        'endLine': 2
    },

    {
        'code': 'address owner;',
        'startLine': 2,
        'endLine': 2
    },

    {
        'code': '\n',
        'startLine': 3,
        'endLine': 3
    },

    {
        'code': 'modifier onlyOwner { \n }',
        'startLine': 4,
        'endLine': 5
    },

    {
        'code': 'require(msg.sender == owner);',
        'startLine': 5,
        'endLine': 5
    },

    {
        'code': '_;',
        'startLine': 6,
        'endLine': 6
    }
]

# Simulate input as if coming from VSCode with block structure assumptions
simulate_input(test_inputs)