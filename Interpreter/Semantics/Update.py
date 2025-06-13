from Interpreter.Semantics.Evaluation import Evaluation
from Analyzer.ContractAnalyzer import *

class Update :

    def __init__(self, an:ContractAnalyzer):
        self.an = an
        self.ev = Evaluation(an)

    def update_left_var(self, expr, rVal, operator, variables, callerObject=None, callerContext=None):
        # ── ① 글로벌이면 갱신 금지 ─────────────────────────
        if callerObject is None and callerContext is None and self._is_global_expr(expr):
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
            self, expr, rVal, operator, variables,
            callerObject=None, callerContext=None):
        """
        rebalanceCount % 10 과 같이 BinaryExp(%) 가
        IndexAccess 의 인덱스로 쓰일 때 호출된다.
        """

        # (1) IndexAccess 의 인덱스로 불린 경우만 의미 있음
        if callerObject is None or callerContext != "IndexAccessContext":
            return None

        # (2) 인덱스 식 abstract-eval → int or Interval
        idx_val = self.ev.evaluate_expression(expr, variables, None, None)

        # ────────────────────────────────────────────────────────────────────
        # ① singleton [n,n]  → n 로 확정
        # ────────────────────────────────────────────────────────────────────
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
            new_val = self.compound_assignment(target.value, rVal, operator)
            self._patch_var_with_new_value(target, new_val)
            return target  # logging 용으로 돌려줌

        # ────────────────────────────────────────────────────────────────────
        # ③ 범위 interval  (l < r)  보수 처리
        #     ‣ 배열  : l‥r 전체 patch
        #     ‣ 매핑  : l‥r 중 ‘이미 존재하는 엔트리’만 patch
        #               (미정의 키는 <unk>로 남김)
        # ────────────────────────────────────────────────────────────────────
        # ──────────────────────────────────────────────────────────────
        # ③  범위 Interval  (l < r)  처리  ── 배열 / 매핑  둘 다 here
        # ----------------------------------------------------------------
        if isinstance(idx_val, (IntegerInterval, UnsignedIntegerInterval)):
            l, r = idx_val.min_value, idx_val.max_value

            # ===== 1) 배열(ArrayVariable) =================================
            if isinstance(callerObject, ArrayVariable):

                # 1-A) **동적 배열**  → 길이 확장 없이 전체 write 로 추상화
                if callerObject.typeInfo.isDynamicArray:
                    return callerObject  # <unk>  write

                # 1-B) **정적 배열**  → 선언 길이 한도 내에서만 패딩
                decl_len = callerObject.typeInfo.arrayLength or 0
                if r >= decl_len:
                    raise IndexError(f"Index [{l},{r}] out of range for "
                                     f"static array '{callerObject.identifier}' "
                                     f"(declared len={decl_len})")

                for i in range(l, r + 1):
                    try:
                        elem = callerObject.get_or_create_element(i)
                    except IndexError:
                        # 정적 배열인데 선언 길이보다 큰 인덱스이면 이미 앞서 range-check 로
                        # 예외가 발생하므로, 여기까지 오는 경우는 거의 없지만 안전 장치.
                        raise

                    new_val = self.compound_assignment(elem.value, rVal, operator)
                    self._patch_var_with_new_value(elem, new_val)

            # ===== 2) 매핑(MappingVariable) ===============================
            elif isinstance(callerObject, MappingVariable):
                for i in range(l, r + 1):
                    k = str(i)
                    if k in callerObject.mapping:  # 이미 존재하는 키만
                        entry = callerObject.mapping[k]
                        nv = self.compound_assignment(entry.value, rVal, operator)
                        self._patch_var_with_new_value(entry, nv)
                # 존재하지 않는 키는 <unk> 로 유지

            return None  # logging 은 상위에서 처리

        # (idx_val 이 Interval 도 int 도 아니면 – 아직 완전 심볼릭) → 상위에서 <unk> 처리
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
        if self._is_global_expr(expr) and isinstance(callerObject, MappingVariable):
            key = f"{expr.base.identifier}.{member}"  # "msg.sender"

            # (1) 엔트리 없으면 생성
            if key not in callerObject.mapping:
                callerObject.mapping[key] = callerObject.get_or_create(key)

            entry = callerObject.mapping[key]

            # (2-B) leaf 에 값 대입 중이면 여기서 patch
            if hasattr(entry, "value"):
                entry.value = self.compound_assignment(entry.value, rVal, operator)
            return entry  # logging 용

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
            return nested  # ← 작업 완료

        # ── 배열 / 중첩 구조체 ──────────────────────────────

        # ── 예외 처리 ──────────────────────────────────────
        raise ValueError(f"Unexpected member-type '{type(nested).__name__}'")

    def update_left_var_of_literal_context(
            self, expr, rVal, operator, variables,
            callerObject: Variables | ArrayVariable | MappingVariable | None = None, callerContext=None):

        # ───────────────────────── 0. 준비 ─────────────────────────
        lit = expr.literal  # 예: "123", "0x1a", "true"
        lit_str = str(lit)
        lit_iv = None  # 필요 시 Interval 변환 결과
        if callerObject is None:
            raise ValueError(f"Literal '{lit_str}' cannot appear standalone on LHS")

        # bool·int·uint·address Literal → Interval 변환 helper  ───── 💡
        def _to_interval(ref_var: Variables, literal_text: str):
            if VariableEnv.is_interval(rVal):  # 이미 Interval이라면 그대로
                return rVal

            # 숫자   -------------------------------------------------
            if literal_text.startswith(('-', '0x')) or literal_text.isdigit():
                v = int(literal_text, 0)  # auto base
                et = ref_var.typeInfo.elementaryTypeName
                if et.startswith("int"):
                    b = ref_var.typeInfo.intTypeLength or 256
                    return IntegerInterval(v, v, b)
                if et.startswith("uint"):
                    b = ref_var.typeInfo.intTypeLength or 256
                    return UnsignedIntegerInterval(v, v, b)

            # 불리언 -------------------------------------------------
            if literal_text in ("true", "false"):
                return BoolInterval(1, 1) if literal_text == "true" else BoolInterval(0, 0)

            # 주소 hex (0x…) ---------------------------------------- 💡
            if literal_text.startswith("0x") and len(literal_text) <= 42:
                v = int(literal_text, 16)
                return UnsignedIntegerInterval(v, v, 160)

            # 그 외 문자열/bytes 등 -> 그대로 symbol 처리
            return literal_text

        # ───────────────────────── 1. Array LHS ────────────────────
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

            # leaf (elementary or enum)
            if isinstance(elem, (Variables, EnumVariable)):
                lit_iv = _to_interval(elem, rVal if isinstance(rVal, str) else lit_str)
                elem.value = self.compound_assignment(elem.value, lit_iv, operator)
                return None

            # 중첩 array/struct → 계속 내려감
            if isinstance(elem, (ArrayVariable, StructVariable, MappingVariable)):
                return elem
            return None

        # ───────────────────────── 2. Mapping LHS ──────────────────
        if isinstance(callerObject, MappingVariable):
            key = lit_str  # mapping key 는 문자열 그대로 보존
            if key not in callerObject.mapping:  # 없으면 새 child 생성
                callerObject.mapping[key] = callerObject.get_or_create(key)

            mvar = callerObject.mapping[key]

            if isinstance(mvar, (Variables, EnumVariable)):
                lit_iv = _to_interval(mvar, rVal if isinstance(rVal, str) else lit_str)
                mvar.value = self.compound_assignment(mvar.value, lit_iv, operator)
                return None

            if isinstance(mvar, (ArrayVariable, StructVariable, MappingVariable)):
                return mvar
            return None

        # ───────────────────────── 3. 기타(Struct 등) ───────────────
        raise ValueError(f"Literal context '{lit_str}' not handled for '{type(callerObject).__name__}'")

    def update_left_var_of_identifier_context(
            self,
            expr: Expression,
            rVal,  # Interval | int | str …
            operator: str,
            variables: dict[str, Variables],
            callerObject: Variables | ArrayVariable | StructVariable | MappingVariable | None = None,
            callerContext: str | None = None):

        ident = expr.identifier

        # ───────────────────────── helper ──────────────────────────
        def _apply_to_leaf(var_obj: Variables | EnumVariable):
            """compound-assignment 를 leaf 변수에 적용"""
            # rVal 이 원시(숫자·true 등)라면 Interval 로 래핑
            if not VariableEnv.is_interval(rVal) and isinstance(var_obj, Variables):
                if isinstance(rVal, str):
                    # 숫자/bool literal → Interval
                    if rVal.lstrip('-').isdigit() or rVal.startswith('0x'):
                        et = var_obj.typeInfo.elementaryTypeName
                        if et.startswith("int"):
                            bit = var_obj.typeInfo.intTypeLength or 256
                            rv = IntegerInterval(int(rVal, 0), int(rVal, 0), bit)
                        elif et.startswith("uint"):
                            bit = var_obj.typeInfo.intTypeLength or 256
                            rv = UnsignedIntegerInterval(int(rVal, 0), int(rVal, 0), bit)
                        elif et == "bool":
                            rv = BoolInterval(1, 1) if rVal == "true" else BoolInterval(0, 0)
                        else:
                            rv = rVal  # address / bytes → 그대로
                    else:
                        rv = rVal
                else:
                    rv = rVal
            else:
                rv = rVal

            var_obj.value = self.compound_assignment(var_obj.value, rv, operator)

        if isinstance(callerObject, ArrayVariable):

            if ident not in variables:
                raise ValueError(f"Index identifier '{ident}' not found.")
            idx_var = variables[ident]
            iv = idx_var.value  # Interval 또는 ⊥

            # ① ⊥   또는  [l, r] 범위  ⇒  전체-쓰기(추상화)
            if VariableEnv.is_interval(iv) and (
                    iv.is_bottom() or iv.min_value != iv.max_value
            ):
                return callerObject  # <unk> 쓰기

            # ② singleton [n,n] 이 아니면 오류
            if not VariableEnv.is_interval(iv) or iv.min_value != iv.max_value:
                raise ValueError(f"Array index '{ident}' must resolve to single constant.")

            idx = iv.min_value
            if idx < 0:
                raise IndexError(f"Negative index {idx} for array '{callerObject.identifier}'")

            # ───── 동적·정적에 따른 분기 ─────────────────────────────────────────────
            if idx >= len(callerObject.elements):

                if callerObject.typeInfo.isDynamicArray:
                    # **동적 배열** → 길이 확장하지 않고 전체-쓰기 로 취급
                    return callerObject  # <unk> 쓰기 (logging 은 상위에서)

                # **정적 배열** → 선언 길이 한도 안에서 패딩
                decl_len = callerObject.typeInfo.arrayLength or 0
                if idx >= decl_len:  # 선언 길이 초과면 즉시 오류
                    raise IndexError(f"Index {idx} out of range for static array "
                                     f"'{callerObject.identifier}' (declared len={decl_len})")

                # 필요한 칸만 bottom 값으로 채운다
                base_t = callerObject.typeInfo.arrayBaseType
                while len(callerObject.elements) <= idx:
                    callerObject.elements.append(
                        VariableEnv.bottom_from_soltype(base_t)
                    )

            # ───────── 실제 요소 갱신 / 재귀 내려가기 ─────────────────────────────
            elem = callerObject.elements[idx]

            if isinstance(elem, (StructVariable, ArrayVariable, MappingVariable)):
                return elem  # 더 깊이 체이닝
            elif isinstance(elem, (Variables, EnumVariable)):
                _apply_to_leaf(elem)  # leaf 값 갱신
                return None

        # 1-C) StructVariable  → 멤버 접근
        if isinstance(callerObject, StructVariable):
            if ident not in callerObject.members:
                raise ValueError(f"Struct '{callerObject.identifier}' has no member '{ident}'")
            mem = callerObject.members[ident]
            if isinstance(mem, (StructVariable, ArrayVariable, MappingVariable)):
                return mem
            elif isinstance(mem, (Variables, EnumVariable)):
                _apply_to_leaf(mem)
                return None

        # 1-D) MappingVariable → key 가 식별자인 케이스
        if isinstance(callerObject, MappingVariable):
            # ── ①  키가 “식별자”인 경우 ─────────────────────────────
            if ident in variables:
                key_var = variables[ident]

                # (a) 주소형 변수  ⇒  식별자 자체 사용 ("user")
                is_addr = (
                        hasattr(key_var, "typeInfo") and
                        getattr(key_var.typeInfo, "elementaryTypeName", None) == "address"
                )
                if is_addr:
                    key_str = ident

                # (b) 숫자/Bool Interval --------------------------------------
                elif VariableEnv.is_interval(key_var.value):
                    iv = key_var.value  # Unsigned/Integer/BoolInterval

                    # ⊥  (bottom)  ────────────────
                    #   아직 어떤 값인지 전혀 모를 때 ⇒
                    #   식별자 그대로 엔트리 하나 만들고 그 엔트리를 바로 반환
                    if iv.is_bottom():
                        key_str = ident
                        if key_str not in callerObject.mapping:
                            callerObject.mapping[key_str] = callerObject.get_or_create(key_str)
                        return callerObject.mapping[key_str]  # ★ here

                    # [lo, hi]  (다중 singleton) ──────────────────
                    if iv.min_value != iv.max_value:
                        span = iv.max_value - iv.min_value + 1

                        if span <= 32:
                            # 작은 구간이면 lo..hi 전부 생성
                            for k in range(iv.min_value, iv.max_value + 1):
                                k_str = str(k)
                                if k_str not in callerObject.mapping:
                                    callerObject.mapping[k_str] = callerObject.get_or_create(k_str)
                            # 분석-중엔 “매핑 전체” 로 다룰 수 있도록 callerObject 그대로 반환
                            return callerObject  # ★ here
                        else:
                            # 범위가 크면 하나의 <unk> 키로 추상화
                            return callerObject  # ★ unchanged

                    # singleton  ────────────────────────────────
                    key_str = str(iv.min_value)  # ★ 확정 키

                # (c) 그밖의 심볼릭 값  ⇒  식별자 그대로
                else:
                    key_str = ident

            # ── ②  키가 리터럴(‘0x…’ 등) / 선언 안 된 식별자 ────────────
            else:
                key_str = ident

            # ── ③  엔트리 가져오거나 생성 ────────────────────────────────
            if key_str not in callerObject.mapping:
                callerObject.mapping[key_str] = callerObject.get_or_create(key_str)
            mvar = callerObject.mapping[key_str]

            # ── ④  복합-타입이면 계속 내려가고, 스칼라면 leaf-갱신 ─────────
            if isinstance(mvar, (StructVariable, ArrayVariable, MappingVariable)):
                return mvar  # userInfo[user] …
            _apply_to_leaf(mvar)  # Variables / EnumVariable
            return None

        # 1-A) 단순 변수/enum → 그대로 leaf 갱신
        if isinstance(callerObject, (Variables, EnumVariable)):
            _apply_to_leaf(callerObject)
            return None

        # ─────────────────────── 2. 상위 객체 없음 ──────────────────
        # (IndexAccess / MemberAccess 의 base 식별자를 해결하기 위한 분기)
        if callerContext in ("IndexAccessContext", "MemberAccessContext"):
            if ident in variables:
                return variables[ident]  # MappingVariable, StructVariable 자체를 리턴
            elif ident in ["block", "tx", "msg", "address", "code"]:
                return ident  # block, tx, msg를 리턴
            elif ident in self.an.contract_cfgs[self.an.current_target_contract].enumDefs:  # EnumDef 리턴
                return self.an.contract_cfgs[self.an.current_target_contract].enumDefs[ident]
            else:
                raise ValueError(f"This '{ident}' is may be array or struct but may not be declared")

        # ─────────────────────── 3. 일반 대입식 ─────────────────────
        # 로컬-스코프 or state-scope 변수 직접 갱신
        if ident not in variables:
            raise ValueError(f"Variable '{ident}' not declared in current scope.")

        target_var = variables[ident]
        if not isinstance(target_var, (Variables, EnumVariable)):
            raise ValueError(f"Assignment to non-scalar variable '{ident}' must use member/index access.")

        _apply_to_leaf(target_var)
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