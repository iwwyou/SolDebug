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

class SnapshotManager:
    """
    * register(obj, serializer)              : 객체별 최초 스냅
    * restore(obj, deserializer)             : 단일 객체 롤백   (기존 인터페이스)
    * snapshot() -> dict                     : 전체 스냅          (새로 추가)
    * restore(snap_dict)                     : 전체 롤백          (새로 추가, 오버로드)
    """

    def __init__(self) -> None:
        # id(obj) -> { "__dict__": deep-copied dict, "serializer": fn }
        self._store: dict[int, dict] = {}
        # id(obj) -> 실객체 참조 (전역 롤백 시 필요)
        self._ref:   dict[int, object] = {}

    # ───────────────────────────────────────── register
    def register(self, obj: object, serializer: Callable[[object], dict]) -> None:
        """
        처음 보는 변수라면 serializer(obj) 결과를 깊은 복사로 저장
        (이미 등록돼 있으면 재등록하지 않음)
        """
        oid = id(obj)
        if oid not in self._store:
            self._store[oid] = {
                "snap": copy.deepcopy(serializer(obj)),
                "serializer": serializer,
            }
            self._ref[oid] = obj

    # ───────────────────────────────────────── 단일 객체 롤백 (기존용)
    def restore(self, target, deserializer: Callable[[object, dict], None] | None = None):
        """
        ‣ (a) 인자가 2개   → 단일 객체 롤백   : restore(obj, deser)
        ‣ (b) 인자가 1개   → 전역 롤백       : restore(snap_dict)
        """
        # -------- (a) 단일 객체
        if deserializer is not None:
            snap_info = self._store.get(id(target))
            if snap_info is not None:
                deserializer(target, copy.deepcopy(snap_info["snap"]))
            return

        # -------- (b) 전역 롤백 (target == snap_dict)
        snap_dict: dict[int, dict] = target       # type: ignore
        for oid, saved_state in snap_dict.items():
            obj = self._ref.get(oid)
            if obj is None:           # 아직 register 안 된 객체일 수 있음
                continue
            # 객체 내부 상태를 원본으로 되돌림
            obj.__dict__.clear()
            obj.__dict__.update(copy.deepcopy(saved_state))

    # ───────────────────────────────────────── 전체 스냅
    # 전체 스냅-샷을 반환
    def snapshot(self):
        return copy.deepcopy(self._store)

    # 외부에서 받은 snap(dict) 전체를 되돌린다
    def restore_from_snap(self, snap):
        self._store = snap