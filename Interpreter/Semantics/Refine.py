from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:                                         # 타입 검사 전용
     from Analyzer.ContractAnalyzer import ContractAnalyzer

from Analyzer.EnhancedSolidityVisitor import READONLY_MEMBERS, READONLY_GLOBAL_BASES
from Domain.Interval import *
from Domain.Variable import Variables
from Domain.IR import Expression
from Utils.Helper import VariableEnv


class Refine:

    def __init__(self, an: "ContractAnalyzer"):
        self.an = an

    @property
    def ev(self):
        return self.an.evaluator        # Evaluation 싱글톤

    @property
    def up(self):
        return self.an.updater          # Update 싱글톤

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

        val = self.an.evaluator.evaluate_expression(cond_expr, vars_, None, None)
        # ▸ bool interval로 강제 변환
        if not isinstance(val, BoolInterval):
            if VariableEnv.is_interval(val):  # 숫자/주소
                val = VariableEnv.convert_int_to_bool_interval(val)
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
        if op == '!':
            # !X : true-branch → X=false, false-branch → X=true
            return self._update_single_condition(
                variables,
                cond_expr.expression,
                not is_true_branch)

        condA = cond_expr.left
        condB = cond_expr.right

        # 먼저 현재 env에서 A, B를 불리언으로 평가(정제 전에 힌트 확보)
        A_b = self._as_bool_interval(condA, variables)
        B_b = self._as_bool_interval(condB, variables)

        # ───────── AND ─────────
        if op == '&&':
            if is_true_branch:
                # A && B 가 참 → 둘 다 참이어야 함 (교집합)
                self.update_variables_with_condition(variables, condA, True)
                self.update_variables_with_condition(variables, condB, True)
                return
            else:
                # ¬(A && B) ≡ (¬A) ∨ (¬B)
                # 단락 최적화: 한쪽이 확실히 false면 그쪽만 적용
                if self._is_false(A_b):
                    self.update_variables_with_condition(variables, condA, False)
                    return
                if self._is_false(B_b):
                    self.update_variables_with_condition(variables, condB, False)
                    return
                # 둘 다 불명 → 분기 2개를 만들어 정제 후 join
                env1 = self._clone_env(variables)
                self.update_variables_with_condition(env1, condA, False)
                env2 = self._clone_env(variables)
                self.update_variables_with_condition(env2, condB, False)
                merged = self._join_two_envs(env1, env2)
                self._apply_env_inplace(variables, merged)
                return

        # ───────── OR ─────────
        if op == '||':
            if is_true_branch:
                # A || B 가 참
                # 단락 최적화: 한쪽이 확실히 true면 그쪽만 적용
                if self._is_true(A_b):
                    self.update_variables_with_condition(variables, condA, True)
                    return
                if self._is_true(B_b):
                    self.update_variables_with_condition(variables, condB, True)
                    return
                # 둘 다 불명 → 분기 2개를 만들어 정제 후 join
                env1 = self._clone_env(variables)
                self.update_variables_with_condition(env1, condA, True)
                env2 = self._clone_env(variables)
                self.update_variables_with_condition(env2, condB, True)
                merged = self._join_two_envs(env1, env2)
                self._apply_env_inplace(variables, merged)
                return
            else:
                # ¬(A || B) ≡ ¬A ∧ ¬B → 둘 다 false로 정제
                self.update_variables_with_condition(variables, condA, False)
                self.update_variables_with_condition(variables, condB, False)
                return

        raise ValueError(f"Unexpected logical operator '{op}'")

    def _update_comparison_condition(
            self,
            variables: dict[str, Variables],
            cond_expr: Expression,
            is_true_branch: bool) -> None:

        def _maybe_update(expr, variables, new_iv):
            if self._is_read_only_expr(expr, variables):
                return  # read-only → 변수 상태 수정 X

            # ★ Update.py의 전략 적용: 매핑/배열 접근에서 심볼릭 인덱스 처리
            # IndexAccessContext일 때 인덱스가 interval인지 확인
            if getattr(expr, "context", "") == "IndexAccessExpContext":
                idx_expr = expr.index
                if getattr(idx_expr, "context", "") == "IdentifierExpContext":
                    idx_name = idx_expr.identifier
                    if idx_name in variables:
                        idx_val = variables[idx_name].value
                        # interval이 Top이거나 범위가 너무 크면 업데이트 skip
                        if VariableEnv.is_interval(idx_val):
                            # Top interval 체크 (0부터 최댓값까지)
                            if idx_val.min_value == 0 and idx_val.max_value >= 2**255:
                                return  # Top interval은 업데이트 불가
                            # 범위가 너무 큰 경우도 skip
                            MAX_REFINE_RANGE = 20
                            if idx_val.max_value - idx_val.min_value + 1 > MAX_REFINE_RANGE:
                                return

            # MemberAccessContext에서 base가 IndexAccess이고 심볼릭 인덱스인 경우
            if getattr(expr, "context", "") == "MemberAccessContext":
                base_expr = expr.base
                if getattr(base_expr, "context", "") == "IndexAccessExpContext":
                    idx_expr = base_expr.index
                    if getattr(idx_expr, "context", "") == "IdentifierExpContext":
                        idx_name = idx_expr.identifier
                        if idx_name in variables:
                            idx_val = variables[idx_name].value
                            if VariableEnv.is_interval(idx_val):
                                # Top interval이거나 범위가 큰 경우 업데이트 skip
                                if idx_val.min_value == 0 and idx_val.max_value >= 2**255:
                                    return
                                MAX_REFINE_RANGE = 20
                                if idx_val.max_value - idx_val.min_value + 1 > MAX_REFINE_RANGE:
                                    return

            try:
                self.up.update_left_var(expr, new_iv, '=', variables, None, None, False)
            except ValueError as e:
                # 매핑 키를 resolve할 수 없는 경우 등은 조용히 무시
                if "Cannot resolve mapping key" in str(e):
                    return
                raise

        # ───── 준비 ─────────────────────────────────────────────
        op = cond_expr.operator
        actual_op = op if is_true_branch else self.negate_operator(op)
        left_expr = cond_expr.left
        right_expr = cond_expr.right

        left_val = self.ev.evaluate_expression(left_expr, variables, None, None)
        right_val = self.ev.evaluate_expression(right_expr, variables, None, None)

        # ───────── CASE 1 : 둘 다 Interval ─────────────────────
        if VariableEnv.is_interval(left_val) and VariableEnv.is_interval(right_val):
            new_l, new_r = self.refine_intervals_for_comparison(left_val, right_val, actual_op)
            _maybe_update(left_expr, variables, new_l)
            _maybe_update(right_expr, variables, new_r)
            return

        # ───────── CASE 2-A : Interval vs literal ──────────────
        if VariableEnv.is_interval(left_val) and not VariableEnv.is_interval(right_val):
            coerced_r = self._coerce_literal_to_interval(right_val, left_val.type_length)
            new_l, _dummy = self.refine_intervals_for_comparison(left_val, coerced_r, actual_op)
            _maybe_update(left_expr, variables, new_l)  # ★ 변경
            return

        # ───────── CASE 2-B : literal vs Interval ──────────────
        if VariableEnv.is_interval(right_val) and not VariableEnv.is_interval(left_val):
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
        if (VariableEnv.is_interval(left_val) and left_val.type_length == 160) or \
                (VariableEnv.is_interval(right_val) and right_val.type_length == 160):

            if not VariableEnv.is_interval(left_val):
                left_val = self._coerce_literal_to_interval(left_val, 160)
            if not VariableEnv.is_interval(right_val):
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
        def _hex_addr_to_addressset(hex_txt: str):
            """'0x…' 문자열을 AddressSet({val}) 로 변환"""
            from Domain.AddressSet import AddressSet
            val = int(hex_txt, 16)
            return AddressSet(ids={val})

        def _is_address_literal(txt: str) -> bool:
            return txt.lower().startswith("0x") and all(c in "0123456789abcdef" for c in txt[2:])

        if isinstance(lit, (int, float)):
            v = int(lit)
            return IntegerInterval(v, v, default_bits) if v < 0 \
                else UnsignedIntegerInterval(v, v, default_bits)
        if isinstance(lit, str):
            if _is_address_literal(lit):
                return _hex_addr_to_addressset(lit)  # ◀︎ AddressSet
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

        def extract_identifier_if_possible(expr: Expression) -> str | None:
            """
            Expression 이 단순 ‘경로(path)’ 형태인지 판별해
              -  foo                      → "foo"
              -  foo.bar                 → "foo.bar"
              -  foo[3]                  → "foo[3]"
              -  foo.bar[2].baz          → "foo.bar[2].baz"
            처럼 **오직 식별자 / 멤버 / 정수-리터럴 인덱스**만으로 이루어져 있을 때
            그 전체 경로 문자열을 돌려준다.

            산술, 함수 호출, 심볼릭 인덱스 등이 섞이면 None 반환.
            """

            # ───── 1. 멤버/인덱스가 전혀 없는 루트 ─────
            if expr.base is None:
                # 순수 식별자인지 확인
                if expr.context == "IdentifierExpContext":
                    return expr.identifier
                return None  # literal, 연산 등 → 식별자 아님

            # ───── 2. 먼저 base-경로를 재귀적으로 확보 ──────
            base_path = extract_identifier_if_possible(expr.base)
            if base_path is None:
                return None  # base 가 이미 복합 → 포기

            # ───── 3.A  멤버 접근 foo.bar ──────────────
            if expr.member is not None:
                return f"{base_path}.{expr.member}"

            # ───── 3.B  인덱스 접근 foo[3] ─────────────
            if expr.index is not None:
                # 인덱스가 “정수 리터럴”인지(실행 시 결정되면 안 됨)
                if expr.index.context == "LiteralExpContext" and str(expr.index.literal).lstrip("-").isdigit():
                    return f"{base_path}[{int(expr.index.literal, 0)}]"
                return None  # 심볼릭 인덱스면 변수 하나로 볼 수 없음

            # 그 밖의 케이스(예: 슬라이스, 함수 호출 등)
            return None


        # ───────────────── 0. BoolInterval 변환 ─────────────────
        def _as_bool_iv(val):
            # 이미 BoolInterval
            if isinstance(val, BoolInterval):
                return val
            # 정수 Interval [0,0]/[1,1] => BoolInterval
            if VariableEnv.is_interval(val):
                return VariableEnv.convert_int_to_bool_interval(val)
            return None  # 그밖엔 Bool 로 간주하지 않음

        l_iv = _as_bool_iv(left_val)
        r_iv = _as_bool_iv(right_val)
        if l_iv is None or r_iv is None:
            # 둘 다 Bool 로 환원 안 되면 관여하지 않는다
            return

        # ※ left_expr / right_expr 가 identifier 인지 → 이름 얻기
        l_name = extract_identifier_if_possible(left_expr)
        r_name = extract_identifier_if_possible(right_expr)

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

    def negate_operator(self, op: str) -> str:
        neg_map = {
            '==': '!=',
            '!=': '==',
            '<': '>=',
            '>': '<=',
            '<=': '>',
            '>=': '<'
        }
        return neg_map.get(op, op)

    def _clone_env(self, env: dict[str, Variables]) -> dict[str, Variables]:
        return VariableEnv.copy_variables(env)

    def _join_two_envs(self, e1: dict[str, Variables], e2: dict[str, Variables]) -> dict[str, Variables]:
        out = self._clone_env(e1)
        for k, v2 in e2.items():
            if k in out:
                # Variables.value 에 lattice join 필요
                # None 값 체크 추가
                if out[k].value is None or v2.value is None:
                    # 한쪽이 None이면 다른 쪽 값 사용, 둘 다 None이면 None 유지
                    if out[k].value is None and v2.value is not None:
                        out[k].value = v2.value
                    # out[k].value가 None이 아니고 v2.value가 None이면 현재 값 유지
                else:
                    out[k].value = out[k].value.join(v2.value)
            else:
                out[k] = VariableEnv.copy_single_variable(v2)
        return out

    def _apply_env_inplace(self, dst: dict[str, Variables], src: dict[str, Variables]) -> None:
        # dst를 src로 대체(메타데이터를 유지하려면 필요시 필드 단위 복사)
        # 여기서는 value만 바꾸는 것으로 충분할 때가 많지만, 안전하게 통째로 교체
        dst.clear()
        for k, v in src.items():
            dst[k] = VariableEnv.copy_single_variable(v)

    def _as_bool_interval(self, expr: Expression, variables: dict[str, Variables]) -> BoolInterval | None:
        val = self.ev.evaluate_expression(expr, variables, None, None)
        if isinstance(val, BoolInterval):
            return val
        if VariableEnv.is_interval(val):
            return VariableEnv.convert_int_to_bool_interval(val)
        return None  # bool로 해석 불가

    def _is_true(self, bi: BoolInterval | None) -> bool:
        return isinstance(bi, BoolInterval) and bi.min_value == bi.max_value == 1

    def _is_false(self, bi: BoolInterval | None) -> bool:
        return isinstance(bi, BoolInterval) and bi.min_value == bi.max_value == 0