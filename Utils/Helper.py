import copy
from typing import Dict, Any

from antlr4 import *
from Parser.SolidityLexer  import SolidityLexer
from Parser.SolidityParser import SolidityParser
from antlr4.error.ErrorListener import ErrorListener, ConsoleErrorListener

from Domain.Variable import (Variables, ArrayVariable,
                             StructVariable, MappingVariable, EnumVariable)
from Domain.Interval import *   # ← 딱 이 정도만 있으면 됨
from Domain.AddressSet import AddressSet
from Domain.Type import SolType
from Domain.IR import Expression

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
    _GLOBAL_BASES = {"block", "msg", "tx"}

    # public façade --------------------------------------------------------
    join_variables_simple     = staticmethod(lambda l, r:
        VariableEnv._merge_by_mode(l, r, "join"))
    join_variables_with_widening = staticmethod(lambda l, r:
        VariableEnv._merge_by_mode(l, r, "widen"))
    narrow_variables          = staticmethod(lambda old, new:
        VariableEnv._merge_by_mode(old, new, "narrow"))

    # ─────────────────────────────────────────── 복사 / 비교
    @staticmethod
    def copy_single_variable(v: "Variables") -> "Variables":
        """
        단일 변수를 deep-copy (Array / Struct / Mapping 서브-클래스 유지)
        """
        if isinstance(v, ArrayVariable):
            new_arr = ArrayVariable(
                identifier=v.identifier,
                base_type=copy.deepcopy(v.typeInfo.arrayBaseType),
                array_length=v.typeInfo.arrayLength,
                is_dynamic=v.typeInfo.isDynamicArray,
                scope=v.scope
            )
            new_arr.elements = [
                VariableEnv.copy_single_variable(e) for e in v.elements
            ]
            return new_arr

        if isinstance(v, StructVariable):
            new_st = StructVariable(
                identifier=v.identifier,
                struct_type=v.typeInfo.structTypeName,
                scope=v.scope
            )
            new_st.members = VariableEnv.copy_variables(v.members)
            return new_st

        if isinstance(v, MappingVariable):
            new_mp = MappingVariable(
                identifier=v.identifier,
                key_type=copy.deepcopy(v.typeInfo.mappingKeyType),
                value_type=copy.deepcopy(v.typeInfo.mappingValueType),
                scope=v.scope,
                struct_defs=v.struct_defs,
                enum_defs=v.enum_defs
            )
            new_mp.mapping = VariableEnv.copy_variables(v.mapping)
            return new_mp

        # Variables / EnumVariable
        return copy.deepcopy(v)

    @staticmethod
    def copy_variables(src: Dict[str, "Variables"]) -> Dict[str, "Variables"]:
        """
        deep-copy 하되 Array / Struct / Mapping 의 서브-클래스를 유지한다.
        (원래 Engine.copy_variables 와 동일 로직)
        """
        dst: Dict[str, "Variables"] = {}

        for name, v in src.items():
            dst[name] = VariableEnv.copy_single_variable(v)

        return dst

    @staticmethod
    def deep_clone_variable(var_obj, new_name: str):
        """
        var_obj   : 복제할 원본 변수 객체
        new_name  : 로컬 변수로 선언될 새 이름

        반환      : var_obj 와 동일한 타입의 “독립적인” 복사본
        """
        import copy
        new_var = copy.deepcopy(var_obj)  # 깊은 복사
        new_var.identifier = new_name  # 최상위 이름 교체

        # ── Struct 내부 멤버 식별자 업데이트 ──────────────────────
        if hasattr(new_var, "members"):  # StructVariable
            for m in new_var.members.values():
                tail = m.identifier.split('.', 1)[-1]  # 기존 “a.b.c”
                m.identifier = f"{new_name}.{tail}"

        # ── 배열 요소 식별자 업데이트 ─────────────────────────────
        if hasattr(new_var, "elements"):  # ArrayVariable
            for i, e in enumerate(new_var.elements):
                e.identifier = f"{new_name}[{i}]"

        # ── 매핑 value 식별자 업데이트 ───────────────────────────
        if hasattr(new_var, "mapping"):  # MappingVariable
            for k, v in new_var.mapping.items():
                v.identifier = f"{new_name}[{k}]"

        return new_var

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

            # ArrayVariable 특수 처리 - elements는 리스트
            if isinstance(v1, ArrayVariable):
                if not VariableEnv._compare_array_elements(v1.elements, v2.elements):
                    return False
                continue

            # leaf – 값 비교
            if hasattr(v1, "value"):
                if hasattr(v1.value, "equals"):
                    if type(v1.value) != type(v2.value):
                        return False
                    if not v1.value.equals(v2.value):
                        return False
                elif v1.value != v2.value:
                    return False
            else:
                # 복합 타입 – 재귀 (StructVariable, MappingVariable 등)
                attr1 = getattr(v1, "members", getattr(v1, "mapping", {}))
                attr2 = getattr(v2, "members", getattr(v2, "mapping", {}))
                if not VariableEnv.variables_equal(attr1, attr2):
                    return False
        return True

    @staticmethod
    def _compare_array_elements(els1: list, els2: list) -> bool:
        """ArrayVariable의 elements 리스트 비교"""
        if len(els1) != len(els2):
            return False
        for e1, e2 in zip(els1, els2):
            if type(e1) is not type(e2):
                return False
            # 재귀적으로 ArrayVariable 처리
            if isinstance(e1, ArrayVariable):
                if not VariableEnv._compare_array_elements(e1.elements, e2.elements):
                    return False
            # 값 비교
            elif hasattr(e1, "value"):
                if hasattr(e1.value, "equals"):
                    if type(e1.value) != type(e2.value):
                        return False
                    if not e1.value.equals(e2.value):
                        return False
                elif e1.value != e2.value:
                    return False
        return True

    @staticmethod
    def env_equal(a: dict[str, Variables] | None,
                   b: dict[str, Variables] | None) -> bool:
        return VariableEnv.variables_equal(a or {}, b or {})

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
            # ★ v1.value가 Variables인 경우 방어 처리 (잘못된 초기화 감지)
            if isinstance(v1.value, Variables):
                new.value = v1.value  # 그대로 유지
            else:
                new.value = VariableEnv._merge_values(v1.value, v2.value, mode)
            return new

        # ④ Array
        if isinstance(v1, ArrayVariable):
            if len(v1.elements) != len(v2.elements):
                # Array smashing: 길이가 다르면 더 긴 배열 반환 (over-approximation)
                # 디버깅 주석 없을 때는 이렇게 처리, 있을 때는 정확한 분석 가능
                longer = v1 if len(v1.elements) >= len(v2.elements) else v2
                new_arr = copy.copy(longer)
                new_arr.elements = longer.elements.copy()
                return new_arr
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

    @staticmethod
    def diff_changed(old_env: dict[str, Variables],
                     new_env: dict[str, Variables]) -> dict[str, Variables]:

        from Analyzer.RecordManager import RecordManager  # serialize 재사용
        rm = RecordManager()  # helper only

        def _flat(env: dict[str, Variables]) -> dict[str, str]:
            out = {}
            for k, v in env.items():
                # 방어 코드: v가 Variables 객체가 아니면 건너뛰기
                if not hasattr(v, 'identifier'):
                    continue
                rm._flatten_var(v, v.identifier, out)
            return out

        old_flat = _flat(old_env) if old_env else {}
        new_flat = _flat(new_env) if new_env else {}

        changed = {}
        for path, new_val in new_flat.items():
            old_val = old_flat.get(path)
            if old_val is None:
                # 이전에 없던 변수는 제외 (루프 내부 새 변수는 loopDelta에 포함 안 함)
                continue
            # old_val과 new_val은 이미 _flatten_var에서 직렬화된 문자열이므로 직접 비교
            if old_val != new_val:
                changed[path] = new_val  # path 는 "a[3].x" 같은 키
        return changed

    @staticmethod
    def is_interval(x) -> bool:
        """Integer / UnsignedInteger 계열인지 판단 (AddressSet은 제외)"""
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
            # ★ AddressSet bottom 반환
            return AddressSet.bot()
        return f"symbolic_{et}"

    @staticmethod
    def convert_int_to_bool_interval(int_interval):
        """
        간단히 [0,0] => BoolInterval(0,0),
             [1,1] => BoolInterval(1,1)
             그외 => BoolInterval(0,1)
        """
        if int_interval.is_bottom():
            return BoolInterval(None, None)
        if int_interval.min_value == 0 and int_interval.max_value == 0:
            return BoolInterval(0, 0)  # always false
        elif int_interval.min_value == 1 and int_interval.max_value == 1:
            return BoolInterval(1, 1)  # always true
        else:
            return BoolInterval(0, 1)  # unknown

    @staticmethod
    def is_global_expr(expr: Expression) -> bool:
        """
        Expression 이 block.xxx / msg.xxx / tx.xxx 형태인지 검사.
        """
        return (
                expr.member is not None  # x.y 형태
                and expr.base is not None
                and getattr(expr.base, "identifier", None) in VariableEnv._GLOBAL_BASES
        )