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
        elif expr.context == "TestingMemberAccess":
            return self._update_left_var_of_testing_member_access_context_for_debug(
                expr, rVal, operator, variables, callerObject, callerContext)

        return None

    def _update_left_var_of_testing_index_access_context_for_debug(
            self, expr: Expression, rVal, operator, variables, callerObject=None, callerContext=None):
        """
        TestingIndexAccess 컨텍스트 처리 (디버깅 전용)
        allowed[_from][msg.sender] 같은 중첩 매핑 접근 처리
        """
        # base 객체 찾기
        base_obj = self._update_left_var_for_debug(
            expr.base, rVal, operator, variables, None, "TestingIndexAccess")

        if base_obj is None:
            return None

        # index 처리 - callerObject를 base_obj로, callerContext를 TestingIndexAccess로 전달
        result = self._update_left_var_for_debug(
            expr.index, rVal, operator, variables, base_obj, "TestingIndexAccess")
        return result

    def _update_left_var_of_identifier_context_for_debug(
            self, expr: Expression, rVal, operator, variables, caller_object=None, caller_context=None):
        """
        Identifier 컨텍스트 처리 (디버깅 전용)
        """
        ident = expr.identifier

        # ======================================================================
        # 0) caller_context가 TestingIndexAccess이고 ident가 글로벌 변수인 경우
        #    (예: block, tx, msg)
        # ======================================================================
        if caller_context == "TestingIndexAccess" and ident in ("block", "tx", "msg"):
            # 글로벌 객체는 그대로 반환 (다음 MemberAccess에서 처리)
            return ident

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
        if caller_context in (
                "IndexAccessContext", "MemberAccessContext", "TestingIndexAccess"):
            # base에 대한 접근
            if ident in variables:
                return variables[ident]  # MappingVariable, ArrayVariable 등을 반환
            elif ident in ("block", "tx", "msg"):
                # 글로벌 객체는 문자열로 반환 (MemberAccess에서 처리)
                return ident
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
        result = self._update_left_var_for_debug(
            expr.index, rVal, operator, variables, base_obj, "IndexAccessContext")
        return result

    def _update_left_var_of_member_access_context_for_debug(
            self, expr: Expression, rVal, operator, variables, callerObject=None, callerContext=None):
        """
        MemberAccess 컨텍스트 처리 (디버깅 전용) - struct.field, msg.sender 등
        """
        from Utils.Helper import VariableEnv

        # base 객체 찾기
        base_obj = self._update_left_var_for_debug(
            expr.base, rVal, operator, variables, None, "MemberAccessContext")

        if base_obj is None:
            return None

        member_name = expr.member

        # ======================================================================
        # 1) 글로벌 멤버 (msg.sender, tx.origin 등)가 매핑 키로 사용되는 경우
        #    예: allowed[_from][msg.sender], balances[msg.sender]
        # ======================================================================
        if VariableEnv.is_global_expr(expr) and isinstance(callerObject, MappingVariable):
            key = f"{expr.base.identifier}.{member_name}"  # "msg.sender"

            if not callerObject.struct_defs or not callerObject.enum_defs:
                ccf = self.an.contract_cfgs[self.an.current_target_contract]
                callerObject.struct_defs = ccf.structDefs
                callerObject.enum_defs = ccf.enumDefs

            # 엔트리 없으면 생성
            if key not in callerObject.mapping:
                callerObject.mapping[key] = callerObject.get_or_create(key)

            entry = callerObject.mapping[key]

            # TestingIndexAccess나 IndexAccessContext에서 호출된 경우
            # 더 깊은 접근이 이어질 수 있으므로 객체 반환
            if callerContext in ("TestingIndexAccess", "IndexAccessContext"):
                return entry

            # leaf 변수에 값 대입하는 경우
            if rVal is not None and hasattr(entry, "value"):
                entry.value = rVal

            return entry

        # ======================================================================
        # 2) base가 글로벌 문자열인 경우 (ident 단계에서 "msg" 반환된 경우)
        # ======================================================================
        if isinstance(base_obj, str) and base_obj in ("block", "tx", "msg"):
            # 글로벌 멤버 접근 - callerObject가 MappingVariable이면 키로 사용
            if isinstance(callerObject, MappingVariable):
                key = f"{base_obj}.{member_name}"

                if not callerObject.struct_defs or not callerObject.enum_defs:
                    ccf = self.an.contract_cfgs[self.an.current_target_contract]
                    callerObject.struct_defs = ccf.structDefs
                    callerObject.enum_defs = ccf.enumDefs

                if key not in callerObject.mapping:
                    callerObject.mapping[key] = callerObject.get_or_create(key)

                return callerObject.mapping[key]

            # 그 외에는 None 반환 (글로벌 값 자체는 변수가 아님)
            return None

        # ======================================================================
        # 3) StructVariable인 경우
        # ======================================================================
        if isinstance(base_obj, StructVariable):
            if member_name not in base_obj.members:
                # 디버깅에서는 멤버가 없어도 생성 시도 (실제로는 struct 정의에 따라)
                # 여기서는 일단 None 반환하고, 필요하면 struct 정의를 확인해서 생성
                return None
            return base_obj.members[member_name]

        # ======================================================================
        # 4) ArrayVariable의 length 접근 등
        # ======================================================================
        if isinstance(base_obj, ArrayVariable):
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
                        try:
                            print(f"[DEBUG INIT] Getting/creating element {idx} in array {callerObject.identifier}, current length={len(callerObject.elements)}")
                        except:
                            pass
                        elem = callerObject.get_or_create_element(idx)
                        try:
                            print(f"[DEBUG INIT] After get_or_create: array length={len(callerObject.elements)}, elem type={type(elem).__name__}")
                        except:
                            pass
                        return elem
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

    def _update_left_var_of_testing_member_access_context_for_debug(
            self, expr: Expression, rVal, operator, variables, callerObject=None, callerContext=None):
        """
        TestingMemberAccess 컨텍스트 처리 (디버깅 전용)
        디버그 주석에서 사용되는 멤버 접근: allowed[_from][msg.sender] 형태

        callerObject: 외부 매핑 객체 (예: allowed[_from])
        callerContext: 호출 컨텍스트 (예: "TestingIndexAccess")
        """
        member = expr.member

        # ======================================================================
        # 1) 글로벌 멤버가 매핑 키로 사용되는 경우: allowed[_from][msg.sender]
        # ======================================================================
        if VariableEnv.is_global_expr(expr) and isinstance(callerObject, MappingVariable):
            key = f"{expr.base.identifier}.{member}"  # "msg.sender"

            if not callerObject.struct_defs or not callerObject.enum_defs:
                ccf = self.an.contract_cfgs[self.an.current_target_contract]
                callerObject.struct_defs = ccf.structDefs
                callerObject.enum_defs = ccf.enumDefs

            # 엔트리가 없으면 새로 만든다
            if key not in callerObject.mapping:
                callerObject.mapping[key] = callerObject.get_or_create(key)

            entry = callerObject.mapping[key]

            # ① 더 깊은 IndexAccess 가 이어질 때는 객체 그대로 반환
            if callerContext == "TestingIndexAccess":
                return entry  # allowed[msg.sender] 의 결과

            # ② leaf 읽기(Testing이므로 값 패치는 하지 않음)
            return entry  # Variables / EnumVariable / Array…

        # ======================================================================
        # 2) 일반적인 경우: base 객체를 먼저 찾고 멤버 접근
        # ======================================================================
        # ① 먼저 base 부분을 재귀-업데이트
        base_obj = self._update_left_var_for_debug(
            expr.base, rVal, operator, variables, None, "TestingMemberAccess")

        if base_obj is None:
            return None

        if member is not None:
            # ======================================================================
            # 3) StructVariable인 경우
            # ======================================================================
            if isinstance(base_obj, StructVariable):
                m = base_obj.members.get(member)
                if m is None:
                    # 디버깅에서는 멤버가 없어도 시도 (실제로는 정의에 따라)
                    return None

                nested = base_obj.members[member]

                if isinstance(nested, (StructVariable, ArrayVariable, MappingVariable)):
                    # 더 깊은 member access가 이어질 수 있으므로 그대로 반환
                    return nested
                elif isinstance(nested, (Variables, EnumVariable)):
                    if rVal is not None:
                        nested.value = rVal
                    return nested

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

        특별 처리:
        - `array.length = [N, N]` → 동적 배열의 크기를 N개로 초기화
        """

        # ★ 특별 케이스: 동적 배열의 .length 설정
        if (lhs_expr.context in ("MemberAccessContext", "TestingMemberAccess") and
            lhs_expr.member == "length"):

            # base 객체 찾기
            base_obj = self.resolve_lhs_expr_for_debug(lhs_expr.base, variables)

            if isinstance(base_obj, ArrayVariable) and base_obj.typeInfo.isDynamicArray:
                # ① 스냅샷 먼저 생성 (복원을 위해)
                self._snapshot_once_for_debug(base_obj)

                if edit_event == "delete":
                    # 삭제: 원래 상태로 복원
                    self.an.snapman.restore(base_obj, self.an.de)
                    return
                elif edit_event not in ("add", "modify"):
                    raise ValueError(f"unknown edit_event {edit_event!r}")

                # value에서 크기 추출
                target_length = self._extract_array_length_from_value(value)
                if target_length is not None:
                    # ② 동적 배열을 target_length 크기로 초기화
                    self._initialize_dynamic_array_to_length(base_obj, target_length)
                    return
                else:
                    raise ValueError(f"Invalid length value for dynamic array: {value}")

        # 일반적인 변수 처리
        target = self.resolve_lhs_expr_for_debug(lhs_expr, variables)
        if target is None:
            # More detailed error message for debugging
            try:
                expr_repr = f"{lhs_expr.context}"
                if hasattr(lhs_expr, 'identifier') and lhs_expr.identifier is not None:
                    expr_repr += f" (identifier: {lhs_expr.identifier})"
                if hasattr(lhs_expr, 'member') and lhs_expr.member is not None:
                    expr_repr += f" (member: {lhs_expr.member})"
            except:
                expr_repr = "unknown"

            # Don't raise error, just log warning and skip this annotation
            print(f"[WARNING] Cannot resolve LHS expression: {expr_repr} (scope: {scope})")
            print(f"[WARNING] Available variables: {list(variables.keys())[:10]}...")
            return  # Skip this annotation instead of raising error

        # DEBUG: Show what we're patching (safe repr) - commented out for clean output
        # try:
        #     target_id = getattr(target, 'identifier', '?')
        #     target_val = repr(getattr(target, 'value', '?'))
        #     print(f"[APPLY DEBUG] Patching {target_id} with value {value}")
        # except:
        #     pass

        # ① snapshot & restore
        self._snapshot_once_for_debug(target)
        if edit_event == "delete":
            self.an.snapman.restore(target, self.an.de)
            return
        elif edit_event not in ("add", "modify"):
            raise ValueError(f"unknown edit_event {edit_event!r}")

        # ② 값 패치
        self._patch_var_with_new_value_for_debug(target, value)
        # try:
        #     print(f"[APPLY DEBUG] After patching: {target_id} value updated")
        # except:
        #     pass

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

    def _patch_var_with_new_value_for_debug(self, target_var, new_value):
        """
        디버깅용 변수 값 패치
        """
        from Domain.Variable import Variables as VarClass
        from Domain.Interval import UnsignedIntegerInterval, IntegerInterval

        # ArrayVariable 처리: value가 리스트이고 배열 요소 값들인 경우
        if isinstance(target_var, ArrayVariable) and isinstance(new_value, list):
            # 배열 요소 초기화
            base_type = target_var.typeInfo.arrayBaseType
            target_var.typeInfo.arrayLength = len(new_value)
            target_var.elements.clear()

            for idx, val in enumerate(new_value):
                # Variables 객체 생성
                elem_id = f"{target_var.identifier}[{idx}]"
                elem = VarClass(identifier=elem_id, scope=target_var.scope)
                elem.typeInfo = base_type

                # 값 설정
                if isinstance(val, list) and len(val) == 2:
                    min_val, max_val = val
                    if base_type.elementaryTypeName.startswith('uint'):
                        bits = base_type.intTypeLength or 256
                        elem.value = UnsignedIntegerInterval(min_val, max_val, bits)
                    elif base_type.elementaryTypeName.startswith('int'):
                        bits = base_type.intTypeLength or 256
                        elem.value = IntegerInterval(min_val, max_val, bits)
                    else:
                        elem.value = val
                elif isinstance(val, int):
                    if base_type.elementaryTypeName.startswith('uint'):
                        bits = base_type.intTypeLength or 256
                        elem.value = UnsignedIntegerInterval(val, val, bits)
                    elif base_type.elementaryTypeName.startswith('int'):
                        bits = base_type.intTypeLength or 256
                        elem.value = IntegerInterval(val, val, bits)
                    else:
                        elem.value = val
                else:
                    elem.value = val

                target_var.elements.append(elem)
            return

        if isinstance(target_var, VarClass):
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

    def _extract_array_length_from_value(self, value) -> int | None:
        """
        value에서 배열 길이를 추출
        - [N, N] → N
        - N (int) → N
        - UnsignedIntegerInterval([N, N]) → N (min == max일 때)
        """
        # Interval 객체인 경우
        if hasattr(value, 'min_value') and hasattr(value, 'max_value'):
            if value.min_value == value.max_value and isinstance(value.min_value, int):
                return value.min_value
        # 리스트 형태
        elif isinstance(value, list) and len(value) == 2:
            # [N, N] 형태
            if value[0] == value[1] and isinstance(value[0], int):
                return value[0]
        # 정수 형태
        elif isinstance(value, int):
            return value
        return None

    def _initialize_dynamic_array_to_length(self, arr: ArrayVariable, target_length: int):
        """
        동적 배열을 target_length 크기로 초기화
        - 현재 크기보다 크면 bottom 값으로 채움
        - 현재 크기보다 작으면 뒤쪽 요소 제거
        """
        current_length = len(arr.elements)

        if target_length > current_length:
            # 부족한 만큼 bottom 값으로 채우기
            base_type = arr.typeInfo.arrayBaseType
            for i in range(current_length, target_length):
                elem = self._create_array_element_with_bottom(arr, i, base_type)
                arr.elements.append(elem)
        elif target_length < current_length:
            # 뒤쪽 요소 제거
            arr.elements = arr.elements[:target_length]
        # target_length == current_length이면 아무것도 안 함

    def _create_array_element_with_bottom(self, arr: ArrayVariable, index: int, base_type: SolType) -> Variables:
        """
        배열 요소를 bottom 값으로 생성
        """
        elem_id = f"{arr.identifier}[{index}]"

        # elementary type인 경우
        if base_type.typeCategory == "elementary":
            et = base_type.elementaryTypeName
            bits = base_type.intTypeLength or 256

            if et.startswith("uint"):
                from Domain.Interval import UnsignedIntegerInterval
                bottom_val = UnsignedIntegerInterval.bottom(bits)
            elif et.startswith("int"):
                from Domain.Interval import IntegerInterval
                bottom_val = IntegerInterval.bottom(bits)
            elif et == "bool":
                from Domain.Interval import BoolInterval
                bottom_val = BoolInterval.bottom()
            elif et == "address":
                from Domain.AddressSet import AddressSet
                bottom_val = AddressSet.bot()
            else:
                # bytes, string 등
                bottom_val = f"symbolic_{elem_id}"

            return Variables(
                identifier=elem_id,
                value=bottom_val,
                scope=arr.scope,
                typeInfo=base_type
            )

        # struct type인 경우
        elif base_type.typeCategory == "struct":
            return StructVariable(
                identifier=elem_id,
                struct_type=base_type.structTypeName,
                scope=arr.scope
            )

        # nested array인 경우
        elif base_type.typeCategory == "array":
            return ArrayVariable(
                identifier=elem_id,
                base_type=base_type.arrayBaseType,
                array_length=base_type.arrayLength,
                is_dynamic=base_type.isDynamicArray,
                scope=arr.scope
            )

        # mapping인 경우 (배열의 요소로는 불가능하지만 방어적 처리)
        else:
            return Variables(
                identifier=elem_id,
                value=f"symbolic_{elem_id}",
                scope=arr.scope,
                typeInfo=base_type
            )