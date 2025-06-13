from Interpreter.Semantics.Update import *
from Analyzer.EnhancedSolidityVisitor import READONLY_MEMBERS, READONLY_GLOBAL_BASES

class Refine:
    def update_variables_with_condition(self, variables, condition_expr, is_true_branch):
        """
            condition_expr: Expression
              - 연산자(operator)가 비교연산(==,!=,<,>,<=,>=)일 수도 있고,
              - 논리연산(&&, ||, !)일 수도 있고,
              - 단일 변수(IdentifierExpContext)나 bool literal, etc. 일 수도 있음
            is_true_branch:
              - True => 조건이 만족되는 브랜치 (if, while 등의 true 분기)
              - False => 조건이 불만족인 브랜치 (else, while not, etc)
            variables: { var_name: Variables }  (CFGNode 상의 변수 상태)
            """

        if self._is_read_only_expr(condition_expr, variables): return

        # 1) condition_expr.operator 파악
        op = condition_expr.operator

        # 2) 만약 operator가 None인데, context가 IdentifierExpContext(단일 변수) 등 “단순 bool 변환”이라면
        if op is None:
            # 예: if (myBoolVar) => true branch라면 myBoolVar = [1,1], false branch라면 myBoolVar=[0,0]
            return self._update_single_condition(variables, condition_expr, is_true_branch)

        # 3) 논리 연산 처리
        elif op in ['&&', '||', '!']:
            return self._update_logical_condition(variables, condition_expr, is_true_branch)

        # 4) 비교 연산 처리 (==, !=, <, >, <=, >=)
        elif op in ['==', '!=', '<', '>', '<=', '>=']:
            return self._update_comparison_condition(variables, condition_expr, is_true_branch)

        else:
            raise ValueError(f"This operator '{op}' is not expected operator")

    def _update_single_condition(self, vars_, cond_expr, is_true_branch):
        # bool literal인 경우는 영향 없음
        if cond_expr.context == "LiteralExpContext":
            return

        val = Evaluation.evaluate_expression(cond_expr, vars_, None, None)
        # ▸ bool interval로 강제 변환
        if not isinstance(val, BoolInterval):
            if VariableEnv.is_interval(val):  # 숫자/주소
                val = self._convert_int_to_bool_interval(val)
            else:
                return  # symbol 등 – 포기

        tgt = BoolInterval(1, 1) if is_true_branch else BoolInterval(0, 0)
        refined = val.meet(tgt)

        name = (cond_expr.identifier
                if cond_expr.context == "IdentifierExpContext" else None)
        if name and name in vars_:
            vars_[name].value = refined

    def _update_logical_condition(
            self,
            variables: dict[str, Variables],
            cond_expr: Expression,
            is_true_branch: bool) -> None:

        op = cond_expr.operator  # '&&', '||', '!'
        # ───────── NOT ─────────
        if op == '!':
            # !X : true-branch → X=false, false-branch → X=true
            return self._update_single_condition(
                variables,
                cond_expr.expression,  # operand
                not is_true_branch)

        # AND / OR 는 좌·우 피연산자 필요
        condA = cond_expr.left
        condB = cond_expr.right

        # ───────── AND ─────────
        if op == '&&':
            if is_true_branch:  # 둘 다 참이어야 함
                self.update_variables_with_condition(variables, condA, True)
                self.update_variables_with_condition(variables, condB, True)
            else:  # A==false  또는  B==false
                # 두 피연산자 모두 “0 가능”하도록 meet
                self.update_variables_with_condition(variables, condA, False)
                self.update_variables_with_condition(variables, condB, False)
            return

        # ───────── OR ─────────
        if op == '||':
            if is_true_branch:  # A==true  또는  B==true
                # 둘 다 “1 가능”으로 넓힘 (정보 손실 최소화)
                self.update_variables_with_condition(variables, condA, True)
                self.update_variables_with_condition(variables, condB, True)
            else:  # 둘 다 false
                self.update_variables_with_condition(variables, condA, False)
                self.update_variables_with_condition(variables, condB, False)
            return

        raise ValueError(f"Unexpected logical operator '{op}'")

    def _update_comparison_condition(
            self,
            variables: dict[str, Variables],
            cond_expr: Expression,
            is_true_branch: bool) -> None:

        # ───── 헬퍼 ──────────────────────────────────────────────
        def _is_literal_expr(e: Expression) -> bool:
            return getattr(e, "context", "") == "LiteralExpContext"

        def _maybe_update(expr, variables, new_iv):
            if self._is_read_only_expr(expr, variables):
                return  # read-only → 변수 상태 수정 X
            Update.update_left_var(expr, new_iv, '=', variables)

        # ───── 준비 ─────────────────────────────────────────────
        op = cond_expr.operator
        actual_op = op if is_true_branch else self.negate_operator(op)
        left_expr = cond_expr.left
        right_expr = cond_expr.right

        left_val = Evaluation.evaluate_expression(left_expr, variables, None, None)
        right_val = Evaluation.evaluate_expression(right_expr, variables, None, None)

        # ───────── CASE 1 : 둘 다 Interval ─────────────────────
        if self._is_interval(left_val) and self._is_interval(right_val):
            new_l, new_r = self.refine_intervals_for_comparison(left_val, right_val, actual_op)
            _maybe_update(left_expr, variables, new_l)
            _maybe_update(right_expr, variables, new_r)
            return

        # ───────── CASE 2-A : Interval vs literal ──────────────
        if self._is_interval(left_val) and not self._is_interval(right_val):
            coerced_r = self._coerce_literal_to_interval(right_val, left_val.type_length)
            new_l, _dummy = self.refine_intervals_for_comparison(left_val, coerced_r, actual_op)
            _maybe_update(left_expr, variables, new_l)  # ★ 변경
            return

        # ───────── CASE 2-B : literal vs Interval ──────────────
        if self._is_interval(right_val) and not self._is_interval(left_val):
            coerced_l = self._coerce_literal_to_interval(left_val, right_val.type_length)
            _dummy, new_r = self.refine_intervals_for_comparison(coerced_l, right_val, actual_op)
            _maybe_update(right_expr, variables, new_r)  # ★ 변경
            return

        # ───────── CASE 3 : BoolInterval 비교 ──────────────────
        if isinstance(left_val, BoolInterval) or isinstance(right_val, BoolInterval):
            self._update_bool_comparison(
                variables,
                left_expr, right_expr,
                left_val, right_val,
                actual_op)
            return

        # ───────── CASE 4 : address Interval 비교 ───────────────
        if (self._is_interval(left_val) and left_val.type_length == 160) or \
                (self._is_interval(right_val) and right_val.type_length == 160):

            if not self._is_interval(left_val):
                left_val = self._coerce_literal_to_interval(left_val, 160)
            if not self._is_interval(right_val):
                right_val = self._coerce_literal_to_interval(right_val, 160)

            new_l, new_r = self.refine_intervals_for_comparison(left_val, right_val, actual_op)
            _maybe_update(left_expr, variables, new_l)  # ★ 변경
            _maybe_update(right_expr, variables, new_r)  # ★ 변경
            return

    def refine_intervals_for_comparison(
            self,
            a_iv,  # IntegerInterval | UnsignedIntegerInterval
            b_iv,
            op: str):

        # ── bottom short-cut ─────────────────────────
        if a_iv.is_bottom() or b_iv.is_bottom():
            return (a_iv.bottom(a_iv.type_length),
                    b_iv.bottom(b_iv.type_length))

        A, B = a_iv.copy(), b_iv.copy()

        # 내부 헬퍼 -----------------------------------
        def clamp_max(iv, new_max):
            if iv.is_bottom():
                return iv
            if new_max < iv.min_value:
                return iv.bottom(iv.type_length)
            iv.max_value = min(iv.max_value, new_max)
            return iv

        def clamp_min(iv, new_min):
            if iv.is_bottom():
                return iv
            if new_min > iv.max_value:
                return iv.bottom(iv.type_length)
            iv.min_value = max(iv.min_value, new_min)
            return iv

        # --------------------------------------------

        # <  ------------------------------------------------
        if op == '<':
            if B.min_value != NEG_INFINITY:
                A = clamp_max(A, B.min_value - 1)
            if not A.is_bottom() and A.max_value != INFINITY:
                B = clamp_min(B, A.max_value + 1)
            return A, B

        # >  ------------------------------------------------
        if op == '>':
            if B.max_value != INFINITY:
                A = clamp_min(A, B.max_value + 1)
            if not A.is_bottom() and A.min_value != NEG_INFINITY:
                B = clamp_max(B, A.min_value - 1)
            return A, B

        # <=  -----------------------------------------------
        if op == '<=':
            lt_a, lt_b = self.refine_intervals_for_comparison(a_iv, b_iv, '<')
            eq_a, eq_b = self.refine_intervals_for_comparison(a_iv, b_iv, '==')
            return lt_a.join(eq_a), lt_b.join(eq_b)

        # >=  -----------------------------------------------
        if op == '>=':
            gt_a, gt_b = self.refine_intervals_for_comparison(a_iv, b_iv, '>')
            eq_a, eq_b = self.refine_intervals_for_comparison(a_iv, b_iv, '==')
            return gt_a.join(eq_a), gt_b.join(eq_b)

        # ==  -----------------------------------------------
        if op == '==':
            meet = A.meet(B)
            return meet, meet

        # !=  -----------------------------------------------
        if op == '!=':
            if (A.min_value == A.max_value ==
                    B.min_value == B.max_value):
                # 동일 싱글톤이면 모순
                return (A.bottom(A.type_length),
                        B.bottom(B.type_length))
            return A, B

        # 알 수 없는 op → 변경 없음
        return A, B

    def _coerce_literal_to_interval(self, lit, default_bits=256):
        def _hex_addr_to_interval(hex_txt: str) -> UnsignedIntegerInterval:
            """‘0x…’ 문자열을 160-bit UnsignedInterval 로 변환"""
            val = int(hex_txt, 16)
            return UnsignedIntegerInterval(val, val, 160)

        def _is_address_literal(txt: str) -> bool:
            return txt.lower().startswith("0x") and all(c in "0123456789abcdef" for c in txt[2:])

        if isinstance(lit, (int, float)):
            v = int(lit)
            return IntegerInterval(v, v, default_bits) if v < 0 \
                else UnsignedIntegerInterval(v, v, default_bits)
        if isinstance(lit, str):
            if _is_address_literal(lit):
                return _hex_addr_to_interval(lit)  # ◀︎ NEW
            try:
                v = int(lit, 0)
                return IntegerInterval(v, v, default_bits) if v < 0 \
                    else UnsignedIntegerInterval(v, v, default_bits)
            except ValueError:
                return IntegerInterval(None, None, default_bits)  # bottom
        return IntegerInterval(None, None, default_bits)

    def _update_bool_comparison(
            self,
            variables: dict[str, Variables],
            left_expr: Expression,
            right_expr: Expression,
            left_val,  # evaluate_expression 결과
            right_val,  # 〃
            op: str  # '==', '!=' ...
    ):
        """
        bool - bool 비교식을 통해 피연산자의 BoolInterval 을 좁힌다.
          * op == '==' : 두 피연산자가 동일 값이어야 함 → 교집합(meet)
          * op == '!=' : 두 피연산자가 상이해야 함
                         ─ 한쪽이 단정(True/False) ⇒ 다른 쪽은 반대값으로
                         ─ 양쪽 모두 Top([0,1]) ⇒ 정보 부족 → 건너뜀
        """

        # ───────────────── 0. BoolInterval 변환 ─────────────────
        def _as_bool_iv(val):
            # 이미 BoolInterval
            if isinstance(val, BoolInterval):
                return val
            # 정수 Interval [0,0]/[1,1] => BoolInterval
            if self._is_interval(val):
                return self._convert_int_to_bool_interval(val)
            return None  # 그밖엔 Bool 로 간주하지 않음

        l_iv = _as_bool_iv(left_val)
        r_iv = _as_bool_iv(right_val)
        if l_iv is None or r_iv is None:
            # 둘 다 Bool 로 환원 안 되면 관여하지 않는다
            return

        # ※ left_expr / right_expr 가 identifier 인지 → 이름 얻기
        l_name = self._extract_identifier_if_possible(left_expr)
        r_name = self._extract_identifier_if_possible(right_expr)

        # helper ― 변수 env 에 실제 적용
        def _replace(name, new_iv: BoolInterval):
            if name in variables and isinstance(variables[name].value, BoolInterval):
                variables[name].value = variables[name].value.meet(new_iv)

        # ───────────────── 1. op == '==' ───────────────────────
        if op == "==":
            meet = l_iv.meet(r_iv)  # 교집합
            _replace(l_name, meet)
            _replace(r_name, meet)
            return

        # ───────────────── 2. op == '!=' ───────────────────────
        if op == "!=":
            # 한쪽이 [1,1]/[0,0] 처럼 단정이라면 → 다른 쪽을 반대 값으로 강제
            def _is_const(iv: BoolInterval) -> bool:
                return iv.min_value == iv.max_value

            if _is_const(l_iv) and _is_const(r_iv):
                # 둘 다 단정인데 현재 env 가 모순이면 meet 하면 bottom,
                # 분석기에서는 “실행 불가” 분기로 처리하거나 그대로 둠
                if l_iv.equals(r_iv):
                    # a != a 는 거짓 ⇒ 해당 분기는 불가능 → 아무 것도 하지 않고 탈출
                    return
                # a(0) != b(1) 처럼 이미 참 ⇒ 정보 없음
                return

            if _is_const(l_iv):
                opposite = BoolInterval(0, 0) if l_iv.min_value == 1 else BoolInterval(1, 1)
                _replace(r_name, opposite)
                return

            if _is_const(r_iv):
                opposite = BoolInterval(0, 0) if r_iv.min_value == 1 else BoolInterval(1, 1)
                _replace(l_name, opposite)
                return

            # 양쪽 다 [0,1] → 정보 없음
            return

        # ───────────────── 3. <,>,<=,>= (불리언엔 의미 X) ──────
        #   원하는 정책에 따라 symbolic 처리하거나 경고만 남김
        #   여기선 그냥 통과
        return

    def _is_read_only_expr(self, e: Expression, variables: dict) -> bool:
        ctx = getattr(e, "context", "")

        # ── (a) 숫자‧문자‧bool 리터럴
        if ctx == "LiteralExpContext":
            return True

        # ── (b) 배열·주소·함수의 read-only 멤버
        if ctx == "MemberAccessContext":
            if e.member in READONLY_MEMBERS:
                return True
            # type(uint256).max 등
            if getattr(e.base, "context", "") == "MetaTypeContext":
                return True

        # ── (c) 전역(block/msg/tx) 멤버 → 쓰기 불가
        if ctx == "MemberAccessContext" and isinstance(e.base, Expression):
            if getattr(e.base, "identifier", "") in READONLY_GLOBAL_BASES:
                return True

        # ── (d) constant / immutable 변수
        if (ctx == "IdentifierExpContext"
                and e.identifier in variables
                and getattr(variables[e.identifier], "isConstant", False)):
            return True

        return False

    def _convert_int_to_bool_interval(self, int_interval):
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
