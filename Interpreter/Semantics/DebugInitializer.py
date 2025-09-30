from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from Analyzer.ContractAnalyzer import ContractAnalyzer

from Domain.Variable import Variables, ArrayVariable, StructVariable, MappingVariable, EnumVariable
from Domain.Type import SolType
from Domain.Interval import Interval, IntegerInterval, BoolInterval, UnsignedIntegerInterval
from Domain.IR import Expression

from Utils.Helper import VariableEnv

class DebugInitializer:
    """
    디버깅 전용 변수 초기화/업데이트 클래스.
    Update.py와 달리 mapping entry가 없으면 강제로 생성하는 등 디버깅에 특화된 동작.
    """

    def __init__(self, analyzer: "ContractAnalyzer"):
        self.an = analyzer

    def resolve_lhs_expr_for_debug(
            self,
            expr: Expression,
            variables: dict[str, Variables],
            caller_object=None,
            caller_context: str | None = None
    ):
        """
        디버깅 전용 LHS 표현식 해석.
        일반 프로그램과 달리 mapping entry가 없어도 강제로 생성함.
        """
        return self._update_left_var_for_debug(expr, None, None, variables, caller_object, caller_context)

    def _update_left_var_for_debug(self, expr, rVal, operator, variables, callerObject=None, callerContext=None):
        """
        디버깅 전용 변수 업데이트. Update.py의 update_left_var와 유사하지만 디버깅에 특화됨.
        """

        if expr.context == "IndexAccessContext":
            return self._update_left_var_of_index_access_context_for_debug(
                expr, rVal, operator, variables, callerObject, callerContext)
        elif expr.context == "MemberAccessContext":
            return self._update_left_var_of_member_access_context_for_debug(
                expr, rVal, operator, variables, callerObject, callerContext)
        elif expr.context == "IdentifierExpContext":
            return self._update_left_var_of_identifier_context_for_debug(
                expr, rVal, operator, variables, callerObject, callerContext)
        elif expr.context == "LiteralExpContext":
            return self._update_left_var_of_literal_context_for_debug(
                expr, rVal, operator, variables, callerObject, callerContext)
        elif expr.context == "TestingIndexAccess":
            return self._update_left_var_of_testing_index_access_context_for_debug(
                expr, rVal, operator, variables, callerObject, callerContext)

        return None

    def _update_left_var_of_testing_index_access_context_for_debug(
            self, expr: Expression, rVal, operator, variables, callerObject=None, callerContext=None):
        """
        TestingIndexAccess 컨텍스트 처리 (디버깅 전용)
        """
        # base 객체 찾기
        base_obj = self._update_left_var_for_debug(
            expr.base, rVal, operator, variables, None, "TestingIndexAccess")

        if base_obj is None:
            return None

        # index 처리
        return self._update_left_var_for_debug(
            expr.index, rVal, operator, variables, base_obj, "TestingIndexAccess")

    def _update_left_var_of_identifier_context_for_debug(
            self, expr: Expression, rVal, operator, variables, caller_object=None, caller_context=None):
        """
        Identifier 컨텍스트 처리 (디버깅 전용)
        """
        ident = expr.identifier

        # ======================================================================
        # 1) caller_object가 ArrayVariable인 경우 - arr[variable_index]
        # ======================================================================
        if isinstance(caller_object, ArrayVariable):
            if ident not in variables:
                # 디버깅에서는 변수가 없어도 리터럴로 처리 시도
                if ident.isdigit():
                    idx = int(ident)
                    try:
                        if caller_object.typeInfo.isDynamicArray:
                            return caller_object.get_or_create_element(idx)
                        else:
                            if idx < len(caller_object.elements):
                                return caller_object.elements[idx]
                        return None
                    except (IndexError, ValueError):
                        return None
                return None

            idx_var = variables[ident]
            iv = getattr(idx_var, "value", None)

            # 인덱스가 확정값인 경우
            if VariableEnv.is_interval(iv) and not iv.is_bottom() and iv.min_value == iv.max_value:
                idx = iv.min_value
                if idx < 0:
                    return None
                try:
                    if caller_object.typeInfo.isDynamicArray:
                        return caller_object.get_or_create_element(idx)
                    else:
                        if idx < len(caller_object.elements):
                            return caller_object.elements[idx]
                    return None
                except (IndexError, ValueError):
                    return None

            # 불확정 인덱스인 경우 - 디버깅에서는 일단 None 반환
            return None

        # ======================================================================
        # 2) caller_object가 MappingVariable인 경우
        # ======================================================================
        elif isinstance(caller_object, MappingVariable):
            # ── ① key 결정 ──────────────────────────────────
            if ident in variables:  # ident == 변수명
                key_var = variables[ident]
                val = getattr(key_var, "value", key_var)
                # 주소형 판별
                is_address = (
                        hasattr(key_var, "typeInfo") and
                        getattr(key_var.typeInfo, "elementaryTypeName", None) == "address"
                )

                if hasattr(val, "min_value"):
                    if is_address:
                        key_str = key_var.identifier  # "account" 그대로
                    elif val.min_value == val.max_value:  # 숫자·bool 싱글톤
                        key_str = str(val.min_value)
                    else:
                        key_str = key_var.identifier  # 여전히 TOP
                else:
                    key_str = key_var.identifier  # string·bool 등
            else:
                # ───── 디버깅 전용: 리터럴 키로 강제 사용 ────────────────────────────
                # 일반 프로그램에서는 오류이지만, 디버깅에서는 허용
                key_str = ident

            # ── ③ 매핑 엔트리 가져오거나 생성 ─────────────
            if not caller_object.struct_defs or not caller_object.enum_defs:
                ccf = self.an.contract_cfgs[self.an.current_target_contract]
                caller_object.struct_defs = ccf.structDefs
                caller_object.enum_defs = ccf.enumDefs

            entry = caller_object.get_or_create(key_str)
            if isinstance(entry, (StructVariable, ArrayVariable, MappingVariable)):
                return entry
            else:
                return entry  # Variables 객체 반환

        # ======================================================================
        # 3) caller_object가 StructVariable인 경우
        # ======================================================================
        elif isinstance(caller_object, StructVariable):
            if ident not in caller_object.members:
                # 디버깅에서는 struct 멤버가 없어도 시도는 해봄 (실제로는 정의에 따라)
                return None

            member = caller_object.members[ident]
            if isinstance(member, Variables):
                return member
            else:
                return member  # ArrayVariable, StructVariable, MappingVariable

        # ======================================================================
        # 4) 상위 객체 없음 (top-level ident) - 일반 변수 찾기
        # ======================================================================
        if caller_context in ("IndexAccessContext", "MemberAccessContext", "TestingIndexAccess"):
            # base에 대한 접근
            if ident in variables:
                return variables[ident]  # MappingVariable, ArrayVariable 등을 반환
            else:
                # 디버깅에서는 없어도 일단 None 반환 (에러 발생시키지 않음)
                return None

        # 일반적인 변수 접근
        if ident in variables:
            return variables[ident]
        else:
            return None

    def _update_left_var_of_index_access_context_for_debug(
            self, expr: Expression, rVal, operator, variables, callerObject=None, callerContext=None):
        """
        IndexAccess 컨텍스트 처리 (디버깅 전용) - arr[i], mapping[key] 등
        """
        # base 객체 찾기
        base_obj = self._update_left_var_for_debug(
            expr.base, rVal, operator, variables, None, "IndexAccessContext")

        if base_obj is None:
            return None

        # index 처리
        return self._update_left_var_for_debug(
            expr.index, rVal, operator, variables, base_obj, "IndexAccessContext")

    def _update_left_var_of_member_access_context_for_debug(
            self, expr: Expression, rVal, operator, variables, callerObject=None, callerContext=None):
        """
        MemberAccess 컨텍스트 처리 (디버깅 전용) - struct.field 등
        """
        # base 객체 찾기
        base_obj = self._update_left_var_for_debug(
            expr.base, rVal, operator, variables, None, "MemberAccessContext")

        if base_obj is None:
            return None

        member_name = expr.member

        # StructVariable인 경우
        if isinstance(base_obj, StructVariable):
            if member_name not in base_obj.members:
                # 디버깅에서는 멤버가 없어도 생성 시도 (실제로는 struct 정의에 따라)
                # 여기서는 일단 None 반환하고, 필요하면 struct 정의를 확인해서 생성
                return None
            return base_obj.members[member_name]

        # ArrayVariable의 length 접근 등
        elif isinstance(base_obj, ArrayVariable):
            if member_name == "length":
                # length는 변수가 아니므로 None 반환 (값만 필요한 경우)
                return None
            return None

        return None

    def _update_left_var_of_literal_context_for_debug(
            self, expr: Expression, rVal, operator, variables, callerObject=None, callerContext=None):
        """
        Literal 컨텍스트 처리 (디버깅 전용) - 숫자나 문자열 리터럴
        """
        lit = expr.literal

        # caller_object가 있는 경우 (배열 인덱스나 매핑 키로 사용)
        if callerObject is not None:
            # ArrayVariable인 경우
            if isinstance(callerObject, ArrayVariable):
                if not lit.lstrip("-").isdigit():
                    return None  # 디버깅에서도 배열 인덱스는 숫자여야 함
                idx = int(lit)
                if idx < 0:
                    return None
                # 동적 배열이면 확장 가능, 정적 배열이면 범위 체크
                try:
                    if callerObject.typeInfo.isDynamicArray:
                        # 동적 배열은 필요하면 확장
                        return callerObject.get_or_create_element(idx)
                    else:
                        # 정적 배열은 범위 내에서만
                        if idx < len(callerObject.elements):
                            return callerObject.elements[idx]
                        return None
                except (IndexError, ValueError):
                    return None

            # MappingVariable인 경우
            elif isinstance(callerObject, MappingVariable):
                if not callerObject.struct_defs or not callerObject.enum_defs:
                    ccf = self.an.contract_cfgs[self.an.current_target_contract]
                    callerObject.struct_defs = ccf.structDefs
                    callerObject.enum_defs = ccf.enumDefs

                key = lit
                # 디버깅에서는 키가 없어도 생성
                entry = callerObject.get_or_create(key)
                return entry

        # caller_context가 있는 경우 (base/index 해석용)
        if callerContext in ("IndexAccessContext", "MemberAccessContext"):
            return lit  # 리터럴 값 그대로 반환

        return None

    def apply_debug_directive_enhanced(
        self,
        *,
        scope: str,
        lhs_expr: Expression,
        value,
        variables: dict[str, Variables],
        edit_event: str,
    ):
        """
        개선된 디버깅 지시어 적용. mapping entry가 없어도 강제로 생성함.
        """
        target = self.resolve_lhs_expr_for_debug(lhs_expr, variables)
        if target is None:
            raise ValueError(f"LHS cannot be resolved to a {scope} variable even with debug mode.")

        # ① snapshot & restore
        self._snapshot_once_for_debug(target)
        if edit_event == "delete":
            self.an.snapman.restore(target, self.an.de)
            return
        elif edit_event not in ("add", "modify"):
            raise ValueError(f"unknown edit_event {edit_event!r}")

        # ② 값 패치
        self._patch_var_with_new_value_for_debug(target, value)

        # ③ 주소-ID 바인딩
        self._bind_if_address_for_debug(target)

        # ④ Recorder 기록 제거
        #   디버그 주석은 초기값 설정이므로 기록 불필요
        #   실제 assignment는 재해석 시 자동으로 기록됨

    def _snapshot_once_for_debug(self, target_var: Variables):
        """
        디버깅용 스냅샷 생성 - 처음 보는 객체면 스냅샷 매니저에 등록
        """
        if hasattr(self.an, 'snapman') and hasattr(self.an, 'ser'):
            if id(target_var) not in self.an.snapman.store:
                self.an.snapman.register(target_var, self.an.ser)

    def _patch_var_with_new_value_for_debug(self, target_var: Variables, new_value):
        """
        디버깅용 변수 값 패치
        """
        if isinstance(target_var, Variables):
            # 리스트 형태 값 처리 [1000,1000] -> UnsignedIntegerInterval(1000, 1000)
            if isinstance(new_value, list) and len(new_value) == 2:
                min_val, max_val = new_value
                if hasattr(target_var, 'typeInfo') and target_var.typeInfo:
                    et = getattr(target_var.typeInfo, 'elementaryTypeName', '')
                    bits = getattr(target_var.typeInfo, 'intTypeLength', 256) or 256

                    if et.startswith('uint'):
                        from Domain.Interval import UnsignedIntegerInterval
                        target_var.value = UnsignedIntegerInterval(min_val, max_val, bits)
                    elif et.startswith('int'):
                        from Domain.Interval import IntegerInterval
                        target_var.value = IntegerInterval(min_val, max_val, bits)
                    elif et == 'bool':
                        from Domain.Interval import BoolInterval
                        target_var.value = BoolInterval(min_val, max_val)
                    else:
                        target_var.value = new_value
                else:
                    target_var.value = new_value
            else:
                target_var.value = new_value

    def _bind_if_address_for_debug(self, target_var: Variables):
        """
        디버깅용 주소 바인딩 (필요한 경우)
        """
        if isinstance(target_var, Variables) and hasattr(target_var, 'typeInfo'):
            et = getattr(target_var.typeInfo, 'elementaryTypeName', '')
            if et == 'address':
                # 주소 타입이면 심볼릭 매니저에 바인딩 가능
                # 여기서는 간단히 패스
                pass

    def _record_usage_for_debug(self, lhs_expr: Expression, target_var: Variables, scope: str, edit_event: str):
        """
        디버깅용 사용 기록
        """
        if hasattr(self.an, 'recorder'):
            # RecordManager가 있으면 기록
            try:
                self.an.recorder.record_debug_variable_usage(
                    expr=lhs_expr,
                    variable=target_var,
                    scope=scope,
                    event=edit_event
                )
            except AttributeError:
                # record_debug_variable_usage 메서드가 없으면 무시
                pass