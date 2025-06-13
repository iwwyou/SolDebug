import copy
from collections.abc import Callable

from antlr4 import *
from Parser.SolidityLexer  import SolidityLexer
from Parser.SolidityParser import SolidityParser
from antlr4.error.ErrorListener import ErrorListener, ConsoleErrorListener

class ParserHelpers:
    # --------------------------- 컨텍스트 → 파싱 규칙 매핑
    _CTX_MAP: dict[str, str] = {
        'contract':'interactiveSourceUnit', 'library':'interactiveSourceUnit',
        'interface':'interactiveSourceUnit', 'enum':'interactiveSourceUnit',
        'struct':'interactiveSourceUnit',   'functionDefinition':'interactiveSourceUnit',
        'constructor':'interactiveSourceUnit', 'fallback':'interactiveSourceUnit',
        'receive':'interactiveSourceUnit',  'event':'interactiveSourceUnit',
        'error':'interactiveSourceUnit',    'modifier':'interactiveSourceUnit',
        'stateVariableDeclaration':'interactiveSourceUnit',

        'enumMember':'interactiveEnumUnit',
        'structMember':'interactiveStructUnit',

        'simpleStatement':'interactiveBlockUnit', 'if':'interactiveBlockUnit',
        'for':'interactiveBlockUnit',     'while':'interactiveBlockUnit',
        'do':'interactiveBlockUnit',      'try':'interactiveBlockUnit',
        'return':'interactiveBlockUnit',  'break':'interactiveBlockUnit',
        'continue':'interactiveBlockUnit','emit':'interactiveBlockUnit',
        'unchecked':'interactiveBlockUnit',

        'doWhileWhile':'interactiveDoWhileUnit',
        'catch':'interactiveCatchClauseUnit',
        'else_if':'interactiveIfElseUnit', 'else':'interactiveIfElseUnit',

        'debugUnit':'debugUnit'
    }

    # --------------------------- map → 규칙 문자열
    @staticmethod
    def map_context_type(ctx_type: str) -> str|None:
        return ParserHelpers._CTX_MAP.get(ctx_type)

    # --------------------------- 파싱
    @staticmethod
    def generate_parse_tree(src: str, ctx_type: str, verbose=False):
        input_stream  = InputStream(src)
        lexer         = SolidityLexer(input_stream)
        token_stream  = CommonTokenStream(lexer)
        parser        = SolidityParser(token_stream)

        # ── ① 에러 리스너 부착 ───────────────────────────────
        if verbose:
            # 기본 ConsoleErrorListener 제거
            parser.removeErrorListeners()

            # ▶ 한 줄짜리 익명 ErrorListener
            parser.addErrorListener(
                type(
                    "InlineErr", (ErrorListener,), {
                        "syntaxError": lambda self, recognizer, offendingSymbol,
                                              line, column, msg, e:
                        print(f"[ANTLR] {line}:{column} {msg}")
                    }
                )()
            )
        else:
            # 최소한 기본 오류 출력은 유지하고 싶다면
            parser.removeErrorListeners()
            parser.addErrorListener(ConsoleErrorListener.INSTANCE)

        rule = ParserHelpers.map_context_type(ctx_type)

        match rule:
            case 'interactiveStructUnit':     return parser.interactiveStructUnit()
            case 'interactiveEnumUnit':       return parser.interactiveEnumUnit()
            case 'interactiveBlockUnit':      return parser.interactiveBlockUnit()
            case 'interactiveDoWhileUnit':    return parser.interactiveDoWhileUnit()
            case 'interactiveIfElseUnit':     return parser.interactiveIfElseUnit()
            case 'interactiveCatchClauseUnit':return parser.interactiveCatchClauseUnit()
            case 'debugUnit':                 return parser.debugUnit()
            case _:                           return parser.interactiveSourceUnit()
