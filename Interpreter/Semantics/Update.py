from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:                                         # 타입 검사 전용
     from Analyzer.ContractAnalyzer import ContractAnalyzer

from Interpreter.Semantics.Evaluation import Evaluation
from Domain.Interval import *
from Domain.Variable import Variables, ArrayVariable, MappingVariable, StructVariable, EnumVariable
from Domain.Address import AddressSymbolicManager
from Domain.IR import Expression
from Utils.Helper import VariableEnv


class Update :

    def __init__(self, an:"ContractAnalyzer"):
        self.an = an
        self.ev = Evaluation(an)

    def update_left_var(self, expr, rVal, operator, variables, callerObject=None, callerContext=None):
        # ── ① 글로벌이면 갱신 금지 ─────────────────────────
        if callerObject is None and callerContext is None and VariableEnv.is_global_expr(expr):
            return None

        if expr.context == "IndexAccessContext":
            return self.update_left_var_of_index_access_context(expr, rVal, operator, variables,
                                                                callerObject, callerContext)
        elif expr.context == "MemberAccessContext":
            return self.update_left_var_of_member_access_context(expr, rVal, operator, variables,
                                                                 callerObject, callerContext)

        elif expr.context == "IdentifierExpContext":
            return self.update_left_var_of_identifier_context(expr, rVal, operator, variables,
                                                              callerObject, callerContext)
        elif expr.context == "LiteralExpContext":
            return self.update_left_var_of_literal_context(expr, rVal, operator, variables,
                                                           callerObject, callerContext)
        elif expr.left is not None and expr.right is not None:
            return self.update_left_var_of_binary_exp_context(expr, rVal, operator, variables,
                                                              callerObject, callerContext)

        return None

    def update_left_var_of_binary_exp_context(
            self,
            expr: Expression,
            r_val,
            operator: str,
            variables: dict[str, Variables],
            caller_object=None,
            caller_context=None,
    ):
        """
        rebalanceCount % 10 처럼 BinaryExp(%) 가 IndexAccess 의 인덱스로
        쓰일 때 호출된다.
        """

        # IndexAccess 의 인덱스로 호출된 경우가 아니면 아무 것도 하지 않음
        if caller_object is None or caller_context != "IndexAccessContext":
            return None  # 🔸 더 내려갈 대상 없음

        # 1) 인덱스 식 abstract-eval → int 또는 Interval
        idx_val = self.ev.evaluate_expression(expr, variables, None, None)

        # ── ① singleton Interval ⇒ int 확정
        if isinstance(idx_val, (IntegerInterval, UnsignedIntegerInterval)) \
                and idx_val.min_value == idx_val.max_value:
            idx_val = idx_val.min_value

        # ── ② 확정 int ────────────────────────────────────────────────
        if isinstance(idx_val, int):
            target = self._touch_index_entry(caller_object, idx_val)
            new_val = self.compound_assignment(target.value, r_val, operator)
            self._patch_var_with_new_value(target, new_val)

            # 🔸 즉시 기록
            self.an.recorder.record_assignment(
                line_no=self.an.current_start_line,
                expr=expr,
                var_obj=target,
                base_obj=caller_object,
            )
            return None  # 더 내려갈 대상이 없으므로 None 반환

        # ── ③ Interval 범위 [l, r] ───────────────────────────────────
        if isinstance(idx_val, (IntegerInterval, UnsignedIntegerInterval)):
            l, r = idx_val.min_value, idx_val.max_value

            # ---- 배열(ArrayVariable) --------------------------------
            if isinstance(caller_object, ArrayVariable):
                # (a) 동적 배열 – 전체-쓰기(<unk>)로 추상화
                if caller_object.typeInfo.isDynamicArray:
                    self.an.recorder.record_assignment(
                        line_no=self.an.current_start_line,
                        expr=expr,
                        var_obj=caller_object,
                        base_obj=caller_object,
                    )
                    return None

                # (b) 정적 배열 – l..r 패치
                decl_len = caller_object.typeInfo.arrayLength or 0
                if r >= decl_len:
                    raise IndexError(
                        f"Index [{l},{r}] out of range for static array "
                        f"'{caller_object.identifier}' (decl len={decl_len})"
                    )
                for i in range(l, r + 1):
                    elem = caller_object.get_or_create_element(i)
                    nv = self.compound_assignment(elem.value, r_val, operator)
                    self._patch_var_with_new_value(elem, nv)

                self.an.recorder.record_assignment(
                    line_no=self.an.current_start_line,
                    expr=expr,
                    var_obj=caller_object,
                    base_obj=caller_object,
                )
                return None

            # ---- 매핑(MappingVariable) ------------------------------
            if isinstance(caller_object, MappingVariable):
                for i in range(l, r + 1):
                    k = str(i)
                    if k in caller_object.mapping:
                        entry = caller_object.mapping[k]
                        nv = self.compound_assignment(entry.value, r_val, operator)
                        self._patch_var_with_new_value(entry, nv)

                self.an.recorder.record_assignment(
                    line_no=self.an.current_start_line,
                    expr=expr,
                    var_obj=caller_object,
                    base_obj=caller_object,
                )
                return None

        # Interval 도 int 도 아니면 (아직 심볼릭) – 아무 것도 못 함
        return None

    def update_left_var_of_index_access_context(self, expr, rVal, operator, variables,
                                                callerObject=None, callerContext=None):
        # base expression에 대한 재귀
        base_obj = self.update_left_var(expr.base, rVal, operator, variables, None, "IndexAccessContext")

        # index expression에 대한 재귀
        return self.update_left_var(expr.index, rVal, operator, variables, base_obj, "IndexAccessContext")

    def update_left_var_of_member_access_context(
            self, expr, rVal, operator, variables,
            callerObject=None, callerContext=None):

        # ① 먼저 base 부분을 재귀-업데이트
        base_obj = self.update_left_var(expr.base, rVal, operator,
                                        variables, None, "MemberAccessContext")
        member = expr.member

        # ────────────────────────────────────────────────
        # ② 〈글로벌 멤버〉가 매핑의 키로 쓰인 경우
        #      · balances[msg.sender]         (1-단계)
        #      · allowed[msg.sender][_from]   (2-단계)
        # ────────────────────────────────────────────────
        if VariableEnv.is_global_expr(expr) and isinstance(callerObject, MappingVariable):
            key = f"{expr.base.identifier}.{member}"  # "msg.sender"

            # (1) 엔트리 없으면 생성
            if key not in callerObject.mapping:
                callerObject.mapping[key] = callerObject.get_or_create(key)

            entry = callerObject.mapping[key]

            # (2-B) leaf 에 값 대입 중이면 여기서 patch
            if hasattr(entry, "value"):
                entry.value = self.compound_assignment(entry.value, rVal, operator)

            # 📜 기록
            self.an.recorder.record_assignment(
                line_no=self.an.current_start_line,
                expr=expr,
                var_obj=entry,
                base_obj=callerObject,
            )
            return None

        if isinstance(base_obj, MappingVariable):
            # ① base expression 이 IndexAccess 면 → index 식에서 키 추출
            key = None
            base_exp = expr.base  # levels[i]   에서   expr.base == IndexAccess
            if getattr(base_exp, "context", "") == "IndexAccessExpContext":
                idx_exp = base_exp.index
                # 식별자 인덱스  (levels[i]  →  "i")
                if getattr(idx_exp, "context", "") == "IdentifierExpContext":
                    key = idx_exp.identifier
                # 숫자 / 주소 literal 인덱스
                elif getattr(idx_exp, "context", "") == "LiteralExpContext":
                    key = str(idx_exp.literal)

            # ② ①에서 못 뽑았고, 매핑에 엔트리 하나뿐이면 그걸 그대로 사용
            if key is None and len(base_obj.mapping) == 1:
                key, _ = next(iter(base_obj.mapping.items()))

            # ── 엔트리 가져오거나 생성
            if key not in base_obj.mapping:
                base_obj.mapping[key] = base_obj.get_or_create(key)

            nested = base_obj.mapping[key]
            base_obj = nested  # 이후 Struct 처리로 fall-through

        if isinstance(base_obj, ArrayVariable):
            # (1) .length  ─ Read-only.  LHS 로 올 수 없으므로 rVal 는 None
            if member == "length":
                ln = len(base_obj.elements)
                return UnsignedIntegerInterval(ln, ln, 256)  # ← Interval 반환

            # (2) .push / .pop 은 LHS 로 오지 않으므로 여기서 무시
            return base_obj  # 깊은 체이닝 대비 그대로 전달

            # ② base 가 StructVariable 인지 확인
        if not isinstance(base_obj, StructVariable):
            raise ValueError(f"Member access on non-struct '{base_obj.identifier}'")

        # ③ 멤버 존재 확인
        if member not in base_obj.members:
            raise ValueError(f"Member '{member}' not in struct '{base_obj.identifier}'")

        nested = base_obj.members[member]

        if isinstance(nested, (StructVariable, ArrayVariable, MappingVariable)):
            # 더 깊은 member access가 이어질 수 있으므로 그대로 반환
            return nested

        # ── elementary / enum ──────────────────────────────
        if isinstance(nested, (Variables, EnumVariable)):
            nested.value = self.compound_assignment(nested.value, rVal, operator)
            self.an.recorder.record_assignment(
                line_no=self.an.current_start_line,
                expr=expr,
                var_obj=nested,
                base_obj=base_obj,
            )
            return None

        raise ValueError(f"Unexpected member-type '{type(nested).__name__}'")

    # Interpreter/Semantics/Update.py
    # … (생략) …

    def update_left_var_of_literal_context(
            self,
            expr: Expression,
            r_val,
            operator: str,
            variables: dict[str, Variables],
            caller_object: Variables | ArrayVariable | MappingVariable | None = None,
            caller_context=None,
    ):
        # ───────────────────────────── 준비 ─────────────────────────────
        lit = expr.literal  # 예: 123, 0x1a, true …
        lit_str = str(lit)
        if caller_object is None:
            raise ValueError(f"Literal '{lit_str}' cannot appear standalone on LHS")

        # ── literal  ➜  Interval/원시값 변환 ────────────────────────────
        def _to_interval(ref_var: Variables, text: str):
            # RHS(r_val)이 이미 Interval 이면 그대로
            if VariableEnv.is_interval(r_val):
                return r_val

            # 숫자 ----------------------------------------------------------------
            if text.startswith(('-', '0x')) or text.isdigit():
                v = int(text, 0)
                et = ref_var.typeInfo.elementaryTypeName
                b = ref_var.typeInfo.intTypeLength or 256
                return (
                    IntegerInterval(v, v, b) if et.startswith("int")
                    else UnsignedIntegerInterval(v, v, b)
                )

            # 불리언 --------------------------------------------------------------
            if text in ("true", "false"):
                return BoolInterval(1, 1) if text == "true" else BoolInterval(0, 0)

            # 20-byte 주소 hex ----------------------------------------------------
            if text.startswith("0x") and len(text) <= 42:
                v = int(text, 16)
                return UnsignedIntegerInterval(v, v, 160)

            # bytes/string 등 – 심볼릭 그대로
            return text

        # ========================================================================
        # 1) ArrayVariable  ─ arr[ literal ]
        # ========================================================================
        if isinstance(caller_object, ArrayVariable):
            if not lit_str.isdigit():
                return None  # 비정수 인덱스면 상위에서 처리

            idx = int(lit_str)
            if idx < 0:
                raise IndexError(f"Negative index {idx} for array '{caller_object.identifier}'")

            # 동적 배열이면 부족한 요소는 심볼릭으로 padding
            while idx >= len(caller_object.elements):
                caller_object.elements.append(
                    Variables(
                        f"{caller_object.identifier}[{len(caller_object.elements)}]",
                        f"symbol_{caller_object.identifier}_{len(caller_object.elements)}",
                        scope=caller_object.scope,
                        typeInfo=caller_object.typeInfo.arrayBaseType,
                    )
                )

            elem = caller_object.elements[idx]

            # ── (a) leaf 스칼라(elementary / enum) ────────────────────────
            if isinstance(elem, (Variables, EnumVariable)):
                new_iv = _to_interval(elem, lit_str)
                elem.value = self.compound_assignment(elem.value, new_iv, operator)

                # 📜 record
                self.an.recorder.record_assignment(
                    line_no=self.an.current_start_line,
                    expr=expr,
                    var_obj=elem,
                    base_obj=caller_object,
                )
                return None  # 더 내려갈 대상 없음

            # ── (b) nested composite (struct/array/map) ──────────────────
            if isinstance(elem, (ArrayVariable, StructVariable, MappingVariable)):
                return elem  # 다음 단계로 체이닝
            return None

        # ========================================================================
        # 2) MappingVariable  ─ map[ literal ]
        # ========================================================================
        if isinstance(caller_object, MappingVariable):
            key = lit_str  # 매핑 키는 문자열 그대로
            entry = caller_object.mapping.setdefault(key, caller_object.get_or_create(key))

            # ── (a) leaf 스칼라 ───────────────────────────────────────────
            if isinstance(entry, (Variables, EnumVariable)):
                new_iv = _to_interval(entry, lit_str)
                entry.value = self.compound_assignment(entry.value, new_iv, operator)

                # 📜 record
                self.an.recorder.record_assignment(
                    line_no=self.an.current_start_line,
                    expr=expr,
                    var_obj=entry,
                    base_obj=caller_object,
                )
                return None

            # ── (b) nested composite ────────────────────────────────────
            if isinstance(entry, (ArrayVariable, StructVariable, MappingVariable)):
                return entry  # 이어서 내려감
            return None

        # ========================================================================
        # 3) 기타(Struct 등) – 현재 설계 범위 밖
        # ========================================================================
        raise ValueError(
            f"Literal context '{lit_str}' not handled for '{type(caller_object).__name__}'"
        )

    def update_left_var_of_identifier_context(
            self,
            expr: Expression,
            r_val,  # Interval | int | str | …
            operator: str,
            variables: dict[str, Variables],
            caller_object: Variables | ArrayVariable | StructVariable | MappingVariable | None = None,
            caller_context: str | None = None,
    ):
        ident = expr.identifier

        # ────────────────────────── 내부 헬퍼 ──────────────────────────
        def _apply_to_leaf(var_obj: Variables | EnumVariable, record_expr: Expression):
            """leaf 변수에 compound-assignment 적용 + Recorder 호출"""
            # (a) r_val → Interval 변환(필요 시)
            conv_val = r_val
            if not VariableEnv.is_interval(r_val) and isinstance(var_obj, Variables):
                if isinstance(r_val, str) and (r_val.lstrip("-").isdigit() or r_val.startswith("0x")):
                    et = var_obj.typeInfo.elementaryTypeName
                    bit = var_obj.typeInfo.intTypeLength or 256
                    conv_val = (
                        IntegerInterval(int(r_val, 0), int(r_val, 0), bit)
                        if et.startswith("int")
                        else UnsignedIntegerInterval(int(r_val, 0), int(r_val, 0), bit)
                        if et.startswith("uint")
                        else BoolInterval(1, 1) if r_val == "true"
                        else BoolInterval(0, 0) if r_val == "false"
                        else r_val
                    )
            # (b) 실제 값 패치
            var_obj.value = self.compound_assignment(var_obj.value, conv_val, operator)

            # (c) 기록 – **최상위 assignment**(caller_context is None) 일 때만
            if caller_context is None:
                self.an.recorder.record_assignment(
                    line_no=self.an.current_start_line,
                    expr=record_expr,
                    var_obj=var_obj,
                    base_obj=var_obj,
                )

        # ======================================================================
        # 1)  caller_object 가 **ArrayVariable** 인 경우  arr[i] = …
        # ======================================================================
        if isinstance(caller_object, ArrayVariable):
            if ident not in variables:
                raise ValueError(f"Index identifier '{ident}' not found.")

            idx_iv = variables[ident].value  # Interval | ⊥
            # 전체-쓰기(⊥ or 구간) → record는 Array 쪽에서 이미 수행
            if VariableEnv.is_interval(idx_iv) and (idx_iv.is_bottom() or idx_iv.min_value != idx_iv.max_value):
                return caller_object  # 계속 상위에서 처리

            if not (VariableEnv.is_interval(idx_iv) and idx_iv.min_value == idx_iv.max_value):
                raise ValueError(f"Array index '{ident}' must resolve to single constant.")

            idx = idx_iv.min_value
            if idx < 0:
                raise IndexError(f"Negative index {idx} for array '{caller_object.identifier}'")

            # 정적/동적 패딩 로직 (동일)
            if idx >= len(caller_object.elements):
                if caller_object.typeInfo.isDynamicArray:
                    return caller_object  # 전체-쓰기 추상화
                decl_len = caller_object.typeInfo.arrayLength or 0
                if idx >= decl_len:
                    raise IndexError(f"Index {idx} out of range (decl len={decl_len})")
                base_t = caller_object.typeInfo.arrayBaseType
                while len(caller_object.elements) <= idx:
                    caller_object.elements.append(VariableEnv.bottom_from_soltype(base_t))

            elem = caller_object.elements[idx]
            if isinstance(elem, (StructVariable, ArrayVariable, MappingVariable)):
                return elem  # composite – 더 내려감
            _apply_to_leaf(elem, expr)  # leaf 업데이트 + 기록
            return None

        # ======================================================================
        # 2)  caller_object 가 **StructVariable**  – s.x = …
        # ======================================================================
        if isinstance(caller_object, StructVariable):
            if ident not in caller_object.members:
                raise ValueError(f"Struct '{caller_object.identifier}' has no member '{ident}'")
            mem = caller_object.members[ident]
            if isinstance(mem, (StructVariable, ArrayVariable, MappingVariable)):
                return mem
            _apply_to_leaf(mem, expr)  # leaf
            return None

        # ======================================================================
        # 3)  caller_object 가 **MappingVariable**  – map[key] = …
        # ======================================================================
        if isinstance(caller_object, MappingVariable):
            # ── key 결정 ─────────────────────────────────────────────────
            if ident in variables:  # 식별자 → 변수값
                key_iv_or_sym = variables[ident].value
                if VariableEnv.is_interval(key_iv_or_sym):
                    iv = key_iv_or_sym
                    if iv.is_bottom() or iv.min_value != iv.max_value:
                        return caller_object  # 범위 / ⊥  → 전체-쓰기
                    key_str = str(iv.min_value)
                else:
                    key_str = ident  # 주소형 / 심볼릭
            else:
                key_str = ident  # 리터럴 식별자 그대로

            entry = caller_object.mapping.setdefault(key_str, caller_object.get_or_create(key_str))
            if isinstance(entry, (StructVariable, ArrayVariable, MappingVariable)):
                return entry  # composite
            _apply_to_leaf(entry, expr)  # leaf + 기록
            return None

        # ======================================================================
        # 4)  caller_object 가 스칼라(Variables / EnumVariable) – 단순 ident
        # ======================================================================
        if isinstance(caller_object, (Variables, EnumVariable)):
            _apply_to_leaf(caller_object, expr)
            return None

        # ======================================================================
        # 5)  상위 객체 없음  (top-level ident)  ─  a = …
        # ======================================================================
        if caller_context in ("IndexAccessContext", "MemberAccessContext"):
            # 상위 composite 의 base 식별자 해석 단계 – 객체 반환만
            if ident in variables:
                return variables[ident]
            if ident in ("block", "tx", "msg"):
                return ident
            enum_defs = self.an.contract_cfgs[self.an.current_target_contract].enumDefs
            if ident in enum_defs:
                return enum_defs[ident]
            raise ValueError(f"Identifier '{ident}' not declared.")

        # 일반 로컬/상태 변수 직접 갱신
        if ident not in variables:
            raise ValueError(f"Variable '{ident}' not declared.")
        tgt = variables[ident]
        if not isinstance(tgt, (Variables, EnumVariable)):
            raise ValueError(f"Assignment to non-scalar '{ident}' requires member/index access.")
        _apply_to_leaf(tgt, expr)
        return None

    # ---------------------------------------------------------------------------
    #  읽기-전용  LHS resolver
    #   • *어떤 값도* 수정하지 않는다.
    #   • 찾은 객체(Variables / ArrayVariable …)를 그대로 반환하거나
    #     더 내려갈 composite 객체를 반환한다.
    #   • 기존 _resolve_and_update_expr 의 “update 파트”를 모두 제거한 버전.
    # ---------------------------------------------------------------------------
    def resolve_lhs_expr(
            self,
            expr: Expression,
            variables: dict[str, Variables],
            caller_object=None,
            caller_context: str | None = None,
    ):
        """纯粹히 ‘변수 객체’를 찾아서 돌려준다. (값 패치는 전혀 하지 않음)"""

        # ── 글로벌 식별자는 LHS 에 올 수 없으므로 바로 None
        if caller_object is None and caller_context is None and VariableEnv.is_global_expr(expr):
            return None

        ctx = expr.context
        if ctx == "IndexAccessContext":
            base = self.resolve_lhs_expr(expr.base, variables, None, "IndexAccessContext")
            return self.resolve_lhs_expr(expr.index, variables, base, "IndexAccessContext")

        if ctx == "MemberAccessContext":
            base = self.resolve_lhs_expr(expr.base, variables, None, "MemberAccessContext")
            member = expr.member

            # (a) mapping + 글로벌-멤버   map[msg.sender] …
            if VariableEnv.is_global_expr(expr) and isinstance(caller_object, MappingVariable):
                key = f"{expr.base.identifier}.{member}"
                return caller_object.mapping.get(key)

            # (b) struct 멤버
            if isinstance(base, StructVariable) and member in base.members:
                return base.members[member]

            # (c) array.length / .push 등은 LHS 로 오지 않음
            if isinstance(base, ArrayVariable):
                return None

            return None  # fallback

        if ctx == "IdentifierExpContext":
            ident = expr.identifier

            # caller_object 가 있는 경우 – Array / Struct / Mapping 의 내부
            if caller_object is not None:
                if isinstance(caller_object, ArrayVariable):
                    # ident 가 인덱스를 담은 변수명인지 검사
                    if ident in variables:
                        idx_iv = variables[ident].value
                        if VariableEnv.is_interval(idx_iv) and \
                                idx_iv.min_value == idx_iv.max_value:
                            idx = idx_iv.min_value
                            if 0 <= idx < len(caller_object.elements):
                                return caller_object.elements[idx]
                    return None

                if isinstance(caller_object, StructVariable):
                    return caller_object.members.get(ident)

                if isinstance(caller_object, MappingVariable):
                    return caller_object.mapping.get(ident)

                return None

            # top-level identifier
            return variables.get(ident)

        if ctx == "LiteralExpContext":
            lit = str(expr.literal)
            if isinstance(caller_object, ArrayVariable) and lit.isdigit():
                idx = int(lit)
                return caller_object.elements[idx] if idx < len(caller_object.elements) else None
            if isinstance(caller_object, MappingVariable):
                return caller_object.mapping.get(lit)
            return None

        # (BinaryExp etc. – testing 전용 컨텍스트는 디버그 지시어에서 사용 안 함)
        return None

    def _touch_index_entry(self, container, idx: int):
        """배열/매핑에서 idx 번째 엔트리를 가져오거나 필요 시 생성"""
        if isinstance(container, ArrayVariable):
            return container.get_or_create_element(idx)

        if isinstance(container, MappingVariable):
            # MappingVariable 이 알아서 value 객체를 만들어 줌
            return container.get_or_create(str(idx))

        raise TypeError(
            f"_touch_index_entry: unsupported container type {type(container).__name__}"
        )

    def compound_assignment(self, left_interval, right_interval, operator):
        """
        +=, -=, <<= … 등 복합 대입 연산자의 interval 계산.
        한쪽이 ⊥(bottom) 이면 결과도 ⊥ 로 전파한다.
        """

        # 0) 단순 대입인 '='
        if operator == '=':
            return right_interval

        # 1) ⊥-전파용 로컬 헬퍼 ――――――――――――――――――――――――――――
        def _arith_safe(l, r, fn):
            """
            l·r 중 하나라도 bottom ⇒ bottom 그대로 반환
            아니면 fn(l, r) 실행
            """
            if l.is_bottom() or r.is_bottom():
                return l.bottom(getattr(l, "type_length", 256))
            return fn(l, r)

        # 2) 연산자 → 동작 매핑 ―――――――――――――――――――――――――――――――
        mapping = {
            '+=': lambda l, r: _arith_safe(l, r, lambda a, b: a.add(b)),
            '-=': lambda l, r: _arith_safe(l, r, lambda a, b: a.subtract(b)),
            '*=': lambda l, r: _arith_safe(l, r, lambda a, b: a.multiply(b)),
            '/=': lambda l, r: _arith_safe(l, r, lambda a, b: a.divide(b)),
            '%=': lambda l, r: _arith_safe(l, r, lambda a, b: a.modulo(b)),
            '|=': lambda l, r: _arith_safe(l, r, lambda a, b: a.bitwise('|', b)),
            '^=': lambda l, r: _arith_safe(l, r, lambda a, b: a.bitwise('^', b)),
            '&=': lambda l, r: _arith_safe(l, r, lambda a, b: a.bitwise('&', b)),
            '<<=': lambda l, r: _arith_safe(l, r, lambda a, b: a.shift(b, '<<')),
            '>>=': lambda l, r: _arith_safe(l, r, lambda a, b: a.shift(b, '>>')),
            '>>>=': lambda l, r: _arith_safe(l, r, lambda a, b: a.shift(b, '>>>')),
        }

        # 3) 실행
        try:
            return mapping[operator](left_interval, right_interval)
        except KeyError:
            raise ValueError(f"Unsupported compound-assignment operator: {operator}")

    def _fill_array(self, arr: ArrayVariable, py_val: list):
        """
        arr.elements 를 py_val(list) 내용으로 완전히 교체
        – 1-D · multi-D 모두 재귀로 채움
        – 숫자   → Integer / UnsignedInteger Interval( [n,n] )
        – Bool   → BoolInterval
        – str(‘symbolicAddress …’) → 160-bit interval
        – list   → nested ArrayVariable
        """
        arr.elements.clear()  # 새로 만들기
        baseT = arr.typeInfo.arrayBaseType

        def _make_elem(eid: str, raw):
            # list  →  하위 ArrayVariable 재귀
            if isinstance(raw, list):
                sub = ArrayVariable(
                    identifier=eid, base_type=baseT,
                    array_length=len(raw), is_dynamic=True,
                    scope=arr.scope
                )
                self._fill_array(sub, raw)
                return sub

            # symbolicAddress …
            if isinstance(raw, str) and raw.startswith("symbolicAddress"):
                nid = int(raw.split()[1])
                self.an.sm.register_fixed_id(nid)
                iv = self.an.sm.get_interval(nid)
                self.an.sm.bind_var(eid, nid)
                return Variables(eid, iv, scope=arr.scope, typeInfo=baseT)

            # 숫자  /  Bool  → Interval
            if isinstance(raw, (int, bool)):
                if baseT.elementaryTypeName.startswith("uint"):
                    bits = getattr(baseT, "intTypeLength", 256)
                    val = UnsignedIntegerInterval(raw, raw, bits)
                elif baseT.elementaryTypeName.startswith("int"):
                    bits = getattr(baseT, "intTypeLength", 256)
                    val = IntegerInterval(raw, raw, bits)
                else:  # bool
                    val = BoolInterval(int(raw), int(raw))
                return Variables(eid, val, scope=arr.scope, typeInfo=baseT)

            # bytes / string 심볼
            return Variables(eid, f"symbol_{eid}", scope=arr.scope, typeInfo=baseT)

        for i, raw in enumerate(py_val):
            elem_id = f"{arr.identifier}[{i}]"
            arr.elements.append(_make_elem(elem_id, raw))

        # ───────── 값 덮어쓰기 (debug 주석용) ────────────────────────────────────

    def _apply_new_value_to_variable(self, var_obj: Variables, new_value):
        """
        new_value 유형
          • IntegerInterval / UnsignedIntegerInterval / BoolInterval
          • 단일 int / bool
          • 'symbolicAddress N'  (str)
          • 기타 str   (symbolic tag)
        """
        # 0) 이미 Interval 객체면 그대로
        if VariableEnv.is_interval(new_value) or isinstance(new_value, BoolInterval):
            var_obj.value = new_value
            return

        # 1) elementary 타입 확인
        if not (var_obj.typeInfo and var_obj.typeInfo.elementaryTypeName):
            print(f"[Info] _apply_new_value_to_variable: skip non-elementary '{var_obj.identifier}'")
            return

        etype = var_obj.typeInfo.elementaryTypeName
        bits = var_obj.typeInfo.intTypeLength or 256

        # ---- int / uint ---------------------------------------------------
        if etype.startswith("int"):
            iv = (
                new_value
                if isinstance(new_value, IntegerInterval)
                else IntegerInterval(int(new_value), int(new_value), bits)
            )
            var_obj.value = iv

        elif etype.startswith("uint"):
            uv = (
                new_value
                if isinstance(new_value, UnsignedIntegerInterval)
                else UnsignedIntegerInterval(int(new_value), int(new_value), bits)
            )
            var_obj.value = uv

        # ---- bool ---------------------------------------------------------
        elif etype == "bool":
            if isinstance(new_value, str) and new_value.lower() == "any":
                var_obj.value = BoolInterval.top()
            elif isinstance(new_value, (bool, int)):
                b = bool(new_value)
                var_obj.value = BoolInterval(int(b), int(b))
            else:
                var_obj.value = new_value  # already BoolInterval

        # ---- address ------------------------------------------------------
        elif etype == "address":
            if isinstance(new_value, UnsignedIntegerInterval):
                var_obj.value = AddressSymbolicManager.top_interval()

            elif isinstance(new_value, str) and new_value.startswith("symbolicAddress"):
                nid = int(new_value.split()[1])
                self.an.sm.register_fixed_id(nid)
                iv = self.an.sm.get_interval(nid)
                var_obj.value = iv
                self.an.sm.bind_var(var_obj.identifier, nid)

            else:  # 임의 문자열 → symbol 처리
                var_obj.value = f"symbol_{new_value}"

        # ---- fallback -----------------------------------------------------
        else:
            print(f"[Warning] _apply_new_value_to_variable: unhandled type '{etype}'")
            var_obj.value = new_value

    def _patch_var_with_new_value(self, var_obj, new_val):
        """
        • ArrayVariable 인 경우 list 가 오면 _fill_array 로 교체
        • 그 외는 _apply_new_value_to_variable 로 기존 처리
        """
        if isinstance(var_obj, ArrayVariable) and isinstance(new_val, list):
            self._fill_array(var_obj, new_val)
        else:
            self._apply_new_value_to_variable(var_obj, new_val)

# ---------------------------------------------------------------------------
#  디버그 주석(@GlobalVar / @StateVar / @LocalVar) 전용 헬퍼
# ---------------------------------------------------------------------------
    def _snapshot_once(self, var_obj):
        """처음 보는 객체면 스냅샷 매니저에 등록."""
        if id(var_obj) not in self.an.snapman.store:
            self.an.snapman.register(var_obj, self.an.ser)

    def _bind_if_address(self, var_obj):
        """address 형이면 심볼릭-ID ↔ 변수 바인딩."""
        if getattr(var_obj.typeInfo, "elementaryTypeName", None) == "address" and \
           isinstance(var_obj.value, UnsignedIntegerInterval):
            iv = var_obj.value
            if iv.min_value == iv.max_value:
                nid = iv.min_value
                self.an.sm.register_fixed_id(nid, iv)
                self.an.sm.bind_var(var_obj.identifier, nid)

    # -------------- public API ---------------------------------------------
    def apply_debug_directive(
        self,
        *,
        scope: str,                    # "global" | "state" | "local"
        lhs_expr: Expression,
        value,
        variables: dict[str, Variables],   # state-var 테이블 or fcfg.related_variables
        edit_event: str,                  # "add" | "modify" | "delete"
    ):
        """
        • resolve_lhs_expr() 으로 객체를 찾고
        • 스냅샷 + 값 패치 + 주소 바인딩 + Recorder 기록까지 한-큐
        """
        target = self.resolve_lhs_expr(lhs_expr, variables)
        if target is None:
            raise ValueError(f"LHS cannot be resolved to a {scope} variable.")

        # ① snapshot & restore ---------------------------------------------
        self._snapshot_once(target)
        if edit_event == "delete":
            self.an.snapman.restore(target, self.an.de)
            return                          # 롤백만 하고 끝
        elif edit_event not in ("add", "modify"):
            raise ValueError(f"unknown edit_event {edit_event!r}")

        # ② 값 패치 ---------------------------------------------------------
        self._patch_var_with_new_value(target, value)

        # ③ 주소-ID 바인딩 ---------------------------------------------------
        self._bind_if_address(target)

        # ④ Recorder 기록 ---------------------------------------------------
        #   – ‘주석’ 이므로 kind 를 별도로 “debugAssign” 으로
        self.an.recorder.record_assignment(
            line_no=self.an.current_start_line,
            expr=lhs_expr,
            var_obj=target,
            base_obj=None,
        )
