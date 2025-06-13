from Domain.IR import Expression
from Domain.Variable import Variables, StructVariable, MappingVariable, ArrayVariable, EnumVariable
from Utils.CFG import FunctionCFG
from Domain.Interval import IntegerInterval, UnsignedIntegerInterval, BoolInterval
from Domain.Address import AddressSymbolicManager
from Utils.Helper import VariableEnv
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Interpreter.Semantics.Evaluation import Evaluation

class Resolve:
    def __init__(self, an:ContractAnalyzer):
        self.an = an
        self.eval = Evaluation(an)

    def _resolve_and_update_expr(self, expr: Expression,
                                 rVal,
                                 operator,
                                 variables: dict[str, Variables],  # ← 새로 넣었는지?
                                 fcfg: FunctionCFG,
                                 callerObject=None, callerContext=None):
        if callerObject is None and callerContext is None and VariableEnv.is_global_expr(expr):
            return None

        if expr.context == "IndexAccessContext":
            return self._resolve_and_update_expr_of_index_access_context(expr, rVal, operator, variables, fcfg,
                                                                         callerObject, callerContext)
        elif expr.context == "MemberAccessContext":
            return self._resolve_and_update_expr_of_member_access_context(expr, rVal, operator, variables, fcfg,
                                                                          callerObject, callerContext)

        elif expr.context == "IdentifierExpContext":
            return self._resolve_and_update_expr_of_identifier_context(expr, rVal, operator, variables, fcfg,
                                                                       callerObject, callerContext)
        elif expr.context == "LiteralExpContext":
            return self._resolve_and_update_expr_of_literal_context(expr, rVal, operator, variables, fcfg,
                                                                    callerObject, callerContext)

        elif expr.context == "TestingIndexAccess":
            return self._resolve_and_update_expr_of_testing_index_access_context(expr, rVal, operator, variables, fcfg,
                                                                                 callerObject, callerContext)
        elif expr.context == "TestingMemberAccess":
            return self._resolve_and_update_expr_of_testing_member_access_context(expr, rVal, operator, variables, fcfg,
                                                                                  callerObject, callerContext)

        elif expr.left is not None and expr.right is not None:
            return self._resolve_and_update_expr_of_binary_exp_context(expr, rVal, operator, variables, fcfg,
                                                                       callerObject, callerContext)

        return None

    def _resolve_and_update_expr_of_testing_index_access_context(self, expr: Expression,
                                                                 rVal,
                                                                 operator,
                                                                 variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                                 fcfg: FunctionCFG,
                                                                 callerObject=None, callerContext=None):
        # base
        base_obj = self._resolve_and_update_expr(
            expr.base, rVal, operator, variables,
            fcfg, None, "TestingIndexAccess"
        )
        # index
        return self._resolve_and_update_expr(
            expr.index, rVal, operator, variables, fcfg,
            base_obj, "TestingIndexAccess"
        )

    def _resolve_and_update_expr_of_testing_member_access_context(self, expr: Expression,
                                                                  rVal,
                                                                  operator,
                                                                  variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                                  fcfg: FunctionCFG,
                                                                  callerObject=None, callerContext=None):

        # ① 먼저 base 부분을 재귀-업데이트
        base_obj = self._resolve_and_update_expr(expr.base, rVal, operator,
                                                 variables, fcfg, None, "TestingMemberAccess")
        member = expr.member

        if member is not None:
            if VariableEnv.is_global_expr(expr) and isinstance(callerObject, MappingVariable):
                key = f"{expr.base.identifier}.{member}"  # "msg.sender"

                # 엔트리가 없으면 새로 만든다
                if key not in callerObject.mapping:
                    callerObject.mapping[key] = callerObject.get_or_create(key)

                entry = callerObject.mapping[key]

                # ① 더 깊은 IndexAccess 가 이어질 때는 객체 그대로 반환
                if callerContext == "TestingIndexAccess":
                    return entry  # allowed[msg.sender] 의 결과

                # ② leaf 읽기(Testing이므로 값 패치는 하지 않음)
                return entry  # Variables / EnumVariable / Array…

            if not isinstance(base_obj, StructVariable):
                raise ValueError(f"[Warn] member access on non-struct '{base_obj.identifier}'")
            m = base_obj.members.get(member)
            if m is None:
                raise ValueError(f"[Warn] struct '{base_obj.identifier}' has no member '{member}'")

            nested = base_obj.members[member]

            if isinstance(nested, (StructVariable, ArrayVariable, MappingVariable)):
                # 더 깊은 member access가 이어질 수 있으므로 그대로 반환
                return nested
            elif isinstance(nested, (Variables, EnumVariable)):
                if rVal is not None:
                    self._patch_var_with_new_value(m, rVal)
                return m

        raise ValueError(f"Unexpected member-type")

    def _resolve_and_update_expr_of_index_access_context(self, expr: Expression,
                                                         rVal,
                                                         operator,
                                                         variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                         fcfg: FunctionCFG,
                                                         callerObject=None, callerContext=None):
        # base
        base_obj = self._resolve_and_update_expr(
            expr.base, rVal, operator, variables,  # ← ❌  인수순서/개수 모두 틀림
            fcfg, None, "IndexAccessContext"
        )
        # index
        return self._resolve_and_update_expr(
            expr.index, rVal, operator, variables, fcfg,
            base_obj, "IndexAccessContext"
        )

    def _resolve_and_update_expr_of_member_access_context(self, expr: Expression,
                                                          rVal,
                                                          operator,
                                                          variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                          fcfg: FunctionCFG,
                                                          callerObject=None, callerContext=None):

        # ① 먼저 base 부분을 재귀-업데이트
        base_obj = self._resolve_and_update_expr(expr.base, rVal, operator,
                                                 variables, fcfg, None, "MemberAccessContext")
        member = expr.member

        if member is not None:
            if VariableEnv.is_global_expr(expr) and isinstance(callerObject, MappingVariable):
                key = f"{expr.base.identifier}.{member}"  # "msg.sender"

                # 1) 엔트리 확보 (없으면 생성)
                if key not in callerObject.mapping:
                    callerObject.mapping[key] = callerObject.get_or_create(key)

                entry = callerObject.mapping[key]

                # 2) 뒤에 또 인덱스가 붙을 때는 객체 그대로 반환
                if callerContext == "IndexAccessContext":
                    return entry

                # 3) leaf-write : rVal 반영
                if isinstance(entry, (Variables, EnumVariable)) and rVal is not None:
                    self._patch_var_with_new_value(entry, rVal)
                return entry  # ← leaf 객체 반환

            if not isinstance(base_obj, StructVariable):
                raise ValueError(f"[Warn] member access on non-struct '{base_obj.identifier}'")
            m = base_obj.members.get(member)
            if m is None:
                raise ValueError(f"[Warn] struct '{base_obj.identifier}' has no member '{member}'")

            nested = base_obj.members[member]

            if isinstance(nested, (StructVariable, ArrayVariable, MappingVariable)):
                # 더 깊은 member access가 이어질 수 있으므로 그대로 반환
                return nested
            elif isinstance(nested, (Variables, EnumVariable)):
                if rVal is not None:
                    self._patch_var_with_new_value(m, rVal)
                return m

        raise ValueError(f"Unexpected member-type")

    def _resolve_and_update_expr_of_identifier_context(self, expr: Expression,
                                                       rVal,
                                                       operator,
                                                       variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                       fcfg: FunctionCFG,
                                                       callerObject=None, callerContext=None):
        ident = expr.identifier

        if callerObject is not None:

            if isinstance(callerObject, ArrayVariable):
                if ident not in variables:
                    raise ValueError(f"Index identifier '{ident}' not found.")
                idx_var = variables[ident]

                # 스칼라인지 보장
                # ── ① 인덱스가 ⊥(bottom) 이면 “어느 요소인지 모름” → skip
                if (VariableEnv.is_interval(idx_var.value) and idx_var.value.is_bottom()) or \
                        getattr(idx_var.value, "min_value", None) is None:
                    # record 만 하고 실제 element 확정은 보류
                    return None  # ← **이 두 줄만 추가**

                # ── ② 스칼라(singleton) 여부 검사
                if not VariableEnv.is_interval(idx_var.value) or \
                        idx_var.value.min_value != idx_var.value.max_value:
                    raise ValueError(f"Array index '{ident}' must resolve to single constant.")

                idx = idx_var.value.min_value
                if idx < 0 or idx >= len(callerObject.elements):
                    raise IndexError(f"Index {idx} out of range for array '{callerObject.identifier}'")

                elem = callerObject.elements[idx]
                if isinstance(elem, (StructVariable, MappingVariable, ArrayVariable)):
                    return elem
                elif isinstance(elem, (Variables, EnumVariable)):
                    if rVal is None:
                        return elem
                    else:
                        self._patch_var_with_new_value(elem, rVal)
                        return elem

            if isinstance(callerObject, StructVariable):
                if ident not in callerObject.members:
                    raise ValueError(f"Struct '{callerObject.identifier}' has no member '{ident}'")
                mem = callerObject.members[ident]
                if isinstance(mem, (StructVariable, MappingVariable, ArrayVariable)):
                    return mem
                elif isinstance(mem, (Variables, EnumVariable)):
                    if rVal is None:
                        return mem
                    else:
                        self._patch_var_with_new_value(mem, rVal)
                        return mem

            if isinstance(callerObject, MappingVariable):
                if ident not in callerObject.mapping:
                    callerObject.mapping[ident] = callerObject.get_or_create(ident)
                mvar = callerObject.mapping[ident]
                # ① 복합 타입(Struct / Array / Mapping) ⇒ 더 내려가도록 반환
                if isinstance(mvar, (StructVariable, ArrayVariable, MappingVariable)):
                    return mvar
                elif isinstance(mvar, (Variables, EnumVariable)):
                    if rVal is None:
                        return mvar
                    else:
                        self._patch_var_with_new_value(mvar, rVal)
                        return mvar

            if isinstance(callerObject, (Variables, EnumVariable)):
                if rVal is None:
                    return callerObject
                else:
                    self._patch_var_with_new_value(callerObject, rVal)
                    return callerObject

        # (IndexAccess / MemberAccess 의 base 식별자를 해결하기 위한 분기)
        if callerContext in ("IndexAccessContext", "MemberAccessContext", "TestingIndexAccess",
                             "TestingMemberAccess"):
            if ident in variables:
                return variables[ident]  # MappingVariable, StructVariable 자체를 리턴
            elif ident in ["block", "tx", "msg", "address", "code"]:
                return ident  # block, tx, msg를 리턴
            elif ident in self.an.contract_cfgs[self.an.current_target_contract].enumDefs:  # EnumDef 리턴
                return self.an.contract_cfgs[self.an.current_target_contract].enumDefs[ident]
            else:
                raise ValueError(f"This '{ident}' is may be array or struct but may not be declared")

        if ident not in variables:
            raise ValueError(f"Variable '{ident}' not declared in current scope.")

        target_var = variables[ident]
        if rVal is None:
            return target_var
        if isinstance(target_var, (Variables, EnumVariable)):
            self._patch_var_with_new_value(target_var, rVal)
            return target_var

        raise ValueError(f"Unhandled callerObject type: {type(callerObject).__name__}")

    def _resolve_and_update_expr_of_literal_context(self, expr: Expression,
                                                    rVal,
                                                    operator,
                                                    variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                    fcfg: FunctionCFG,
                                                    callerObject=None, callerContext=None):
        lit = expr.literal  # 예: "123", "0x1a", "true"
        lit_str = str(lit)
        lit_iv = None  # 필요 시 Interval 변환 결과
        if callerObject is None:
            raise ValueError(f"Literal '{lit_str}' cannot appear standalone on LHS")

        if isinstance(callerObject, ArrayVariable):
            if not lit_str.isdigit():
                return None  # 비정수 인덱스 → 상위에서 오류/다른 케이스 처리

            idx = int(lit_str)
            if idx < 0:
                raise IndexError(f"Negative index {idx} for array '{callerObject.identifier}'")

            # 💡 동적 배열이라면 빈 element 채워넣기
            while idx >= len(callerObject.elements):
                # address/bytes 등은 symbolic 으로
                callerObject.elements.append(
                    Variables(f"{callerObject.identifier}[{len(callerObject.elements)}]",
                              f"symbol_{callerObject.identifier}_{len(callerObject.elements)}",
                              scope=callerObject.scope,
                              typeInfo=callerObject.typeInfo.arrayBaseType)
                )

            elem = callerObject.elements[idx]

            # 중첩 array/struct → 계속 내려감
            if isinstance(elem, (ArrayVariable, StructVariable, MappingVariable)):
                return elem
            # leaf (elementary or enum)
            elif isinstance(elem, (Variables, EnumVariable)):
                if rVal is None:
                    return elem
                else:
                    elem.value = rVal
                    return elem

        if isinstance(callerObject, MappingVariable):
            key = lit_str  # mapping key 는 문자열 그대로 보존
            if key not in callerObject.mapping:  # 없으면 새 child 생성
                callerObject.mapping[key] = callerObject.get_or_create(key)
            mvar = callerObject.mapping[key]

            if isinstance(mvar, (ArrayVariable, StructVariable, MappingVariable)):
                return mvar

            if isinstance(mvar, (Variables, EnumVariable)):
                if rVal is None:
                    return mvar
                else:
                    mvar.value = rVal
                    return mvar

        raise ValueError(f"Literal context '{lit_str}' not handled for '{type(callerObject).__name__}'")

    def _resolve_and_update_expr_of_binary_exp_context(self, expr: Expression,
                                                       rVal,
                                                       operator,
                                                       variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                       fcfg: FunctionCFG,
                                                       callerObject=None, callerContext=None):
        """
                rebalanceCount % 10 과 같이 BinaryExp(%) 가
                IndexAccess 의 인덱스로 쓰일 때 호출된다.
                """
        # (1) IndexAccess 의 인덱스로 불린 경우만 의미 있음
        if callerObject is None or callerContext in ["IndexAccessContext", "TestingIndexAccessContext"]:
            return None

        # (2) 인덱스 식 abstract-eval → int or Interval
        idx_val = self.eval.evaluate_expression(expr, variables, None, None)

        if isinstance(idx_val, (IntegerInterval, UnsignedIntegerInterval)):
            if idx_val.min_value == idx_val.max_value:
                idx_val = idx_val.min_value  # 확정 int
            else:
                # 범위 [l,r]  → 아래의 “구간 처리” 로 넘어감
                pass

            # ────────────────────────────────────────────────────────────────────
            # ② 확정 int 인 경우
            # ────────────────────────────────────────────────────────────────────
        if isinstance(idx_val, int):
            target = self._touch_index_entry(callerObject, idx_val)
            self._patch_var_with_new_value(target, rVal)
            return target  # logging 용으로 돌려줌

        if isinstance(idx_val, (IntegerInterval, UnsignedIntegerInterval)):
            l, r = idx_val.min_value, idx_val.max_value
            # 1) 배열 길이를 r 까지 확장 -----------------------------
            if isinstance(callerObject, ArrayVariable):
                # 필요하다면 0‥r 까지 자동 확장
                for i in range(len(callerObject.elements), r + 1):
                    callerObject.get_or_create_element(i)  # ← 바뀐 부분

                # l‥r 구간을 갱신
                for i in range(l, r + 1):
                    elem = callerObject.elements[i]  # 이미 존재함
                    self._patch_var_with_new_value(elem, rVal)

                return callerObject


            elif isinstance(callerObject, MappingVariable):
                for i in range(l, r + 1):
                    k = str(i)
                    if k in callerObject.mapping:  # 존재할 때만
                        entry = callerObject.mapping[k]
                        self._patch_var_with_new_value(entry, rVal)
                return callerObject
        raise ValueError(f"Unexpected variable of binary_exp_context")

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

    def _touch_index_entry(self, container, idx: int):
        if isinstance(container, ArrayVariable):
            return container.get_or_create_element(idx)  # ← 위임
        if isinstance(container, MappingVariable):
            return container.get_or_create(str(idx))

        return None
