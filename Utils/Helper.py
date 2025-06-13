import copy
from typing import Dict, Any

from antlr4 import *
from Parser.SolidityLexer  import SolidityLexer
from Parser.SolidityParser import SolidityParser
from antlr4.error.ErrorListener import ErrorListener, ConsoleErrorListener

from Domain.Variable import (Variables, ArrayVariable,
                             StructVariable, MappingVariable, EnumVariable)
from Domain.Interval import *   # ← 딱 이 정도만 있으면 됨
from Domain.Type import SolType

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

class VariableEnv:
    """
    변수 환경(dict[str, Variables])을 deep-copy / 비교 / merge 하는 공통 유틸.
    * Engine, Semantics 모두 같은 로직을 필요로 하므로 여기로 끌어올렸다.
    """

    # ─────────────────────────────────────────── 복사 / 비교
    @staticmethod
    def copy_variables(src: Dict[str, "Variables"]) -> Dict[str, "Variables"]:
        """
        deep-copy 하되 Array / Struct / Mapping 의 서브-클래스를 유지한다.
        (원래 Engine.copy_variables 와 동일 로직)
        """
        dst: Dict[str, "Variables"] = {}

        for name, v in src.items():
            if isinstance(v, ArrayVariable):
                new_arr = ArrayVariable(
                    identifier=v.identifier,
                    base_type=copy.deepcopy(v.typeInfo.arrayBaseType),
                    array_length=v.typeInfo.arrayLength,
                    is_dynamic=v.typeInfo.isDynamicArray,
                    scope=v.scope
                )
                new_arr.elements = [
                    VariableEnv.copy_variables({e.identifier: e})[e.identifier] for e in v.elements
                ]
                dst[name] = new_arr
                continue

            # StructVariable ------------------------------------
            if isinstance(v, StructVariable):
                new_st = StructVariable(
                    identifier=v.identifier,
                    struct_type=v.typeInfo.structTypeName,
                    scope=v.scope
                )
                new_st.members = VariableEnv.copy_variables(v.members)
                dst[name] = new_st
                continue

            # MappingVariable -----------------------------------
            if isinstance(v, MappingVariable):
                new_mp = MappingVariable(
                    identifier=v.identifier,
                    key_type=copy.deepcopy(v.typeInfo.mappingKeyType),
                    value_type=copy.deepcopy(v.typeInfo.mappingValueType),
                    scope=v.scope
                )
                new_mp.mapping = VariableEnv.copy_variables(v.mapping)
                dst[name] = new_mp
                continue

            # Variables / EnumVariable --------------------------
            dst[name] = copy.deepcopy(v)

        return dst

    @staticmethod
    def variables_equal(a: Dict[str, "Variables"] | None,
                        b: Dict[str, "Variables"] | None) -> bool:
        """
        Engine.variables_equal 와 동일.  (간단화 버전)
        """
        if a is None or b is None:
            return a is b
        if a.keys() != b.keys():
            return False

        for k in a:
            v1, v2 = a[k], b[k]
            if type(v1) is not type(v2):
                return False

            # leaf – 값 비교
            if hasattr(v1, "value"):
                if hasattr(v1.value, "equals"):
                    if not v1.value.equals(v2.value):
                        return False
                elif v1.value != v2.value:
                    return False
            else:
                # 복합 타입 – 재귀
                if not VariableEnv.variables_equal(
                        getattr(v1, "members", getattr(v1, "mapping", getattr(v1, "elements", {}))),
                        getattr(v2, "members", getattr(v2, "mapping", getattr(v2, "elements", {})))
                ):
                    return False
        return True

    # ─────────────────────────────────────────── join / widen / narrow
    @staticmethod
    def _merge_values(v1: Any, v2: Any, mode: str = "join") -> Any:

        def _should_widen(val):  # 작은 헬퍼
            return isinstance(val, (IntegerInterval, UnsignedIntegerInterval, BoolInterval))

        # ① primitive -----------------------------------------------------
        if not isinstance(v1, (Variables, ArrayVariable, StructVariable,
                               MappingVariable, EnumVariable)):
            if mode == "widen" and not _should_widen(v1):
                return VariableEnv._merge_values(v1, v2, "join")
            if hasattr(v1, mode):
                return getattr(v1, mode)(v2)
            return f"symbolic{mode.capitalize()}({v1},{v2})"

        # ② 래퍼 타입 but 서로 다른 클래스 → symbolic*
        if type(v1) is not type(v2):
            return f"symbolic{mode.capitalize()}({v1},{v2})"

        # ③ leaf Variables / EnumVariable
        if isinstance(v1, (Variables, EnumVariable)) and \
           not isinstance(v1, (ArrayVariable, StructVariable, MappingVariable)):
            new = copy.copy(v1)
            new.value = VariableEnv._merge_values(v1.value, v2.value, mode)
            return new

        # ④ Array
        if isinstance(v1, ArrayVariable):
            if len(v1.elements) != len(v2.elements):
                return f"symbolic{mode.capitalize()}({v1.identifier},{v2.identifier})"
            new_arr = copy.copy(v1)
            new_arr.elements = [
                VariableEnv._merge_values(a, b, mode) for a, b in zip(v1.elements, v2.elements)
            ]
            return new_arr

        # ⑤ Struct
        if isinstance(v1, StructVariable):
            new_st = copy.copy(v1)
            new_st.members = {}
            for m in v1.members.keys() | v2.members.keys():
                if m in v1.members and m in v2.members:
                    new_st.members[m] = VariableEnv._merge_values(v1.members[m], v2.members[m], mode)
                else:
                    new_st.members[m] = copy.copy(v1.members.get(m, v2.members.get(m)))
            return new_st

        # ⑥ Mapping
        if isinstance(v1, MappingVariable):
            new_map = copy.copy(v1)
            new_map.mapping = {}
            for k in v1.mapping.keys() | v2.mapping.keys():
                if k in v1.mapping and k in v2.mapping:
                    new_map.mapping[k] = VariableEnv._merge_values(v1.mapping[k], v2.mapping[k], mode)
                else:
                    new_map.mapping[k] = copy.copy(v1.mapping.get(k, v2.mapping.get(k)))
            return new_map

        return f"symbolic{mode.capitalize()}({v1},{v2})"

    @staticmethod
    def _merge_by_mode(left, right, mode: str):
        if left is None:
            return VariableEnv.copy_variables(right or {})
        if not right:
            return VariableEnv.copy_variables(left)

        res = VariableEnv.copy_variables(left)
        for name, r_var in (right or {}).items():
            if name in res:
                res[name] = VariableEnv._merge_values(res[name], r_var, mode)
            else:
                res[name] = VariableEnv.copy_variables({name: r_var})[name]
        return res

    # public façade --------------------------------------------------------
    join_variables_simple     = staticmethod(lambda l, r:
        VariableEnv._merge_by_mode(l, r, "join"))
    join_variables_with_widening = staticmethod(lambda l, r:
        VariableEnv._merge_by_mode(l, r, "widen"))
    narrow_variables          = staticmethod(lambda old, new:
        VariableEnv._merge_by_mode(old, new, "narrow"))

    @staticmethod
    def is_interval(x) -> bool:
        """Integer / UnsignedInteger 계열인지 판단"""
        return isinstance(x, (IntegerInterval, UnsignedIntegerInterval))

    @staticmethod
    def bottom_from_soltype(sol_t: SolType):
        if sol_t.typeCategory == "array":
            return ArrayVariable(
                base_type=sol_t.arrayBaseType,
                array_length=sol_t.arrayLength,
                is_dynamic=sol_t.isDynamicArray
            )
        if sol_t.typeCategory == "mapping":
            return MappingVariable(
                key_type=sol_t.mappingKeyType,
                value_type=sol_t.mappingValueType
            )
        if sol_t.typeCategory == "struct":
            return StructVariable(struct_type=sol_t.structTypeName)
        et = sol_t.elementaryTypeName
        if et.startswith("int"):
            return IntegerInterval.bottom(sol_t.intTypeLength or 256)
        if et.startswith("uint"):
            return UnsignedIntegerInterval.bottom(sol_t.intTypeLength or 256)
        if et == "bool":
            return BoolInterval.bottom()
        if et == "address":
            return UnsignedIntegerInterval(0, 2 ** 160 - 1, 160)
        return f"symbolic_{et}"

    @staticmethod
    def compare_intervals(left_interval, right_interval, operator):
        """
        두 Interval 비교 → BoolInterval(min, max) 반환
            [1,1] : definitely-true
            [0,0] : definitely-false
            [0,1] : 불확정(top)
        """

        # 값이 하나라도 없으면 판단 불가 → TOP
        if (left_interval.min_value is None or left_interval.max_value is None or
                right_interval.min_value is None or right_interval.max_value is None):
            return BoolInterval(0, 1)  # [0,1]

        definitely_true = False
        definitely_false = False

        # ───────── 비교 연산별 판정 ────────────────────────────────
        if operator == '==':
            if left_interval.max_value < right_interval.min_value or \
                    left_interval.min_value > right_interval.max_value:
                definitely_false = True
            elif (left_interval.min_value == left_interval.max_value ==
                  right_interval.min_value == right_interval.max_value):
                definitely_true = True

        elif operator == '!=':
            if left_interval.max_value < right_interval.min_value or \
                    left_interval.min_value > right_interval.max_value:
                definitely_true = True
            elif (left_interval.min_value == left_interval.max_value ==
                  right_interval.min_value == right_interval.max_value):
                definitely_false = True

        elif operator == '<':
            if left_interval.max_value < right_interval.min_value:
                definitely_true = True
            elif left_interval.min_value >= right_interval.max_value:
                definitely_false = True

        elif operator == '>':
            if left_interval.min_value > right_interval.max_value:
                definitely_true = True
            elif left_interval.max_value <= right_interval.min_value:
                definitely_false = True

        elif operator == '<=':
            if left_interval.max_value <= right_interval.min_value:
                definitely_true = True
            elif left_interval.min_value > right_interval.max_value:
                definitely_false = True

        elif operator == '>=':
            if left_interval.min_value >= right_interval.max_value:
                definitely_true = True
            elif left_interval.max_value < right_interval.min_value:
                definitely_false = True

        else:
            raise ValueError(f"Unsupported comparison operator: {operator}")

        # ───────── BoolInterval 생성 ─────────────────────────────
        if definitely_true and not definitely_false:
            return BoolInterval(1, 1)  # [1,1]  확실히 true
        if definitely_false and not definitely_true:
            return BoolInterval(0, 0)  # [0,0]  확실히 false
        return BoolInterval(0, 1)  # [0,1]  불확정(top)


