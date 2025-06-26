from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:                                         # 타입 검사 전용
     from Analyzer.ContractAnalyzer import ContractAnalyzer

from Utils.CFG import CFGNode, FunctionCFG
from Utils.Helper import VariableEnv
from Domain.Variable import Variables, MappingVariable, ArrayVariable, StructVariable
from Domain.IR import Expression
from Domain.Interval import UnsignedIntegerInterval, IntegerInterval, BoolInterval

import copy
from collections import deque

class Runtime:
    def __init__(self, analyzer: "ContractAnalyzer"):
        # 별도 객체를 새로 만들지 않고 ContractAnalyzer 안의 싱글톤을
        # 지연-참조(lazy) 합니다.
        self.an = analyzer

    # ── lazy properties ──────────────────────────────────────────────
    @property
    def rec(self):
        return self.an.recorder

    @property
    def ref(self):
        return self.an.refiner

    @property
    def eval(self):
        return self.an.evaluator

    @property
    def up(self):
        return self.an.updater

    @property
    def eng(self):
        return self.an.engine

    def update_statement_with_variables(self, stmt, current_variables, ret_acc=None):
        if stmt.statement_type == 'variableDeclaration':
            return self.interpret_variable_declaration_statement(stmt, current_variables)
        elif stmt.statement_type == 'assignment':
            return self.interpret_assignment_statement(stmt, current_variables)
        elif stmt.statement_type == 'unary':  # 🔹 추가
            return self.interpret_unary_statement(stmt, current_variables)
        elif stmt.statement_type == 'functionCall':
            return self.interpret_function_call_statement(stmt, current_variables)
        elif stmt.statement_type == 'return':
            return self.interpret_return_statement(stmt, current_variables, ret_acc)
        elif stmt.statement_type == 'revert':
            return self.interpret_revert_statement(stmt, current_variables)
        elif stmt.statement_type == 'break':
            return self.interpret_break_statement(stmt, current_variables)
        elif stmt.statement_type == 'continue':
            return self.interpret_continue_statement(stmt, current_variables)
        else:
            raise ValueError(f"Statement '{stmt.statement_type}' is not implemented.")

    def interpret_function_cfg(self, fcfg: FunctionCFG, caller_env: dict[str, Variables] | None = None):
        # ─── ① 호출 이전 컨텍스트 백업 ─────────────────────────
        _old_func = self.an.current_target_function
        _old_fcfg = self.an.current_target_function_cfg

        # ─── ② 현재 해석 대상 함수로 설정 ─────────────────────
        self.an.current_target_function = fcfg.function_name
        self.an.current_target_function_cfg = fcfg

        self._record_enabled = True  # ★ 항상 켠다
        self.an._seen_stmt_ids.clear()  # ← 중복 방지용 세트 초기화
        for blk in fcfg.graph.nodes:  # ← 기존 로그 전부 clear
            for st in blk.statements:
                ln = getattr(st, "src_line", None)
                if ln is not None:
                    self.an.analysis_per_line[ln].clear()

        entry = fcfg.get_entry_node()
        start_block, = fcfg.graph.successors(entry)  # exactly one successor
        start_block.variables = copy.deepcopy(fcfg.related_variables)

        # ① caller_env 의 스냅샷을 그대로 덮어쓴다 (동명 키도 overwrite)

        if caller_env is not None:
            for k, v in caller_env.items():
                start_block.variables[k] = v

        # ────────────────── work-list 초기화 ───────────────────────────────
        work = deque([start_block])
        visited: set[CFGNode] = set()  # 첫 블록도 분석해야 하므로 비워 둠

        # return_values를 모아둘 자료구조 (나중에 exit node에서 join)
        return_values = []

        while work:
            node = work.popleft()
            if node in visited:
                continue
            visited.add(node)

            # 이전 block 분석 결과 반영
            # join_point_node인 경우 predecessor들의 결과를 join한뒤 analyzingNode에 반영
            # 아니면 predecessor 하나가 있을 것이므로 그 predecessor의 variables를 복사
            preds = list(fcfg.graph.predecessors(node))

            if preds:
                joined = None
                for p in preds:
                    if not p.variables:  # “실질-빈” → skip
                        continue
                    joined = VariableEnv.copy_variables(p.variables) if joined is None \
                        else VariableEnv.join_variables_simple(joined, p.variables)
                if joined is not None:
                    node.variables = joined

            cur_vars = node.variables
            node.evaluated = True
            # condition node 처리
            if node.condition_node:
                condition_expr = node.condition_expr
                ln = getattr(node, "src_line", None)  # 없으면 None

                if node.condition_node_type in ["if", "else if"]:
                    # true/false branch 각각 하나의 successor 가정
                    true_successors = [s for s in fcfg.graph.successors(node) if
                                       fcfg.graph.edges[node, s].get('condition') == True]
                    false_successors = [s for s in fcfg.graph.successors(node) if
                                        fcfg.graph.edges[node, s].get('condition') == False]

                    # 각각 한 개라 가정
                    if len(true_successors) != 1 or len(false_successors) != 1:
                        raise ValueError(
                            "if/else if node must have exactly one true successor and one false successor.")

                    true_variables = VariableEnv.copy_variables(cur_vars)
                    false_variables = VariableEnv.copy_variables(cur_vars)

                    self.ref.update_variables_with_condition(true_variables, condition_expr, is_true_branch=True)
                    self.ref.update_variables_with_condition(false_variables, condition_expr, is_true_branch=False)

                    can_true = self._branch_feasible(true_variables, condition_expr, True)
                    can_false = self._branch_feasible(false_variables, condition_expr, False)

                    if not can_true and not can_false:
                        # 이론상 불가능·모순 ⇒ 둘 다 버리고 다음 노드 탐색 중단
                        continue

                    # ── (B) True-브랜치 env 스냅샷 ─────────────────────────
                    if self._record_enabled and ln is not None:
                        self.rec.add_env_record(ln, "branchTrue", true_variables)

                    # true branch로 이어지는 successor enqueue
                    true_succ = true_successors[0]
                    false_succ = false_successors[0]

                    if can_true:
                        true_succ.variables = true_variables
                        work.append(true_succ)
                    else:
                        # 불가능 브랜치엔 “⊥” 찍어 두고 그래프 생략
                        self._set_bottom_env(true_succ.variables)

                    if can_false:
                        false_succ.variables = false_variables
                        work.append(false_succ)
                    else:
                        self._set_bottom_env(false_succ.variables)

                    continue

                elif node.condition_node_type in ["require", "assert"]:
                    # true branch만 존재한다고 가정
                    true_successors = [s for s in fcfg.graph.successors(node) if
                                       fcfg.graph.edges[node, s].get('condition') == True]

                    if len(true_successors) != 1:
                        raise ValueError("require/assert node must have exactly one true successor.")

                    true_variables = VariableEnv.copy_variables(cur_vars)
                    self.ref.update_variables_with_condition(true_variables, condition_expr, is_true_branch=True)

                    can_true = self._branch_feasible(true_variables, condition_expr, True)

                    self.rec.add_env_record(ln, "requireTrue", true_variables)

                    true_succ = true_successors[0]

                    if can_true:
                        true_succ.variables = true_variables
                        work.append(true_succ)
                    else:
                        # 불가능 브랜치엔 “⊥” 찍어 두고 그래프 생략
                        self._set_bottom_env(true_succ.variables)

                    continue

                elif node.condition_node_type in ["while", "for", "do_while"]:
                    # while 루프 처리
                    # fixpoint 계산 후 exit_node 반환
                    exit_node = self.eng.fixpoint(node)
                    # exit_node의 successor는 하나라고 가정
                    successors = list(fcfg.graph.successors(exit_node))
                    if len(successors) == 1:
                        next_node = successors[0]
                        next_node.variables = VariableEnv.copy_variables(exit_node.variables)
                        work.append(next_node)
                    elif len(successors) == 0:
                        # while 종료 후 아무 successor도 없으면 끝
                        pass
                    else:
                        raise ValueError("While exit node must have exactly one successor.")
                    continue

                elif node.fixpoint_evaluation_node:
                    # 그냥 continue
                    continue
                else:
                    raise ValueError(f"Unknown condition node type: {node.condition_node_type}")

            # interpret_function_cfg 안, while work: 루프 최상단 근처
            elif node.is_for_increment:
                # 1) 증감 expression 들을 모두 실행
                for stmt in node.statements:
                    cur_vars = self.update_statement_with_variables(stmt, cur_vars, return_values)

                # 2) successors 에 전달
                for succ in fcfg.graph.successors(node):
                    succ.variables = VariableEnv.copy_variables(node.variables)
                    work.append(succ)
                continue  # 이 노드에서 더 할 일 없음

            else:
                # condition node가 아닌 일반 블록
                # 블록 내 문장 해석
                for stmt in node.statements:
                    cur_vars = self.update_statement_with_variables(stmt, cur_vars, return_values)
                    if "__STOP__" in return_values:  # 플래그만 넣어도 되고
                        break

                # return이나 revert를 만나지 않았다면 successors 방문
                successors = list(fcfg.graph.successors(node))
                if len(successors) == 1:
                    next_node = successors[0]
                    # next_node에 현재 변수 상태를 반영
                    next_node.variables = VariableEnv.copy_variables(cur_vars)
                    work.append(next_node)
                elif len(successors) > 1:
                    raise ValueError("Non-condition, non-join node should not have multiple successors.")
                # successors가 없으면 리프노드이므로 그냥 끝.

        self._force_join_before_exit(fcfg)
        self._sync_named_return_vars(fcfg)  # ★ 여기서 값/객체 맞춰 주기

        self.an.current_target_function = _old_func
        self.an.current_target_function_cfg = _old_fcfg

        # ⑥  callee 의 최종 변수 집합을 caller_env 로 역-반영
        if caller_env is not None:
            exit_env = fcfg.get_exit_node().variables
            for k, v in exit_env.items():
                if k in caller_env:  # ① 기존 키만 덮어쓰기
                    if hasattr(caller_env[k], "value"):
                        caller_env[k].value = v.value
                    else:
                        caller_env[k] = v  # 복합-타입은 객체 공유
                elif isinstance(v, (MappingVariable, ArrayVariable)):
                    # ② “스토리지 엔트리 신규 생성”만 선택적으로 반영
                    caller_env[k] = v  # (필요 시 얕은 복사)

        def _log_implicit_return(var_objs: list[Variables]):
            if not self._record_enabled:
                return
            ln = self._last_executable_line(fcfg)
            if ln is None:
                return
            if len(var_objs) == 1:
                self.rec.record_return(
                    line_no=ln,
                    return_expr=None,
                    return_val=var_objs[0].value,
                    fn_cfg=fcfg
                )
            else:
                flat = {v.identifier: self.rec._serialize_val(v.value) for v in var_objs}
                self.rec.add_env_record(ln, "implicitReturn", flat)

        # exit node에 도달했다면 return_values join
        # 모든 return을 모아 exit node에서 join 처리할 수 있으나, 여기서는 단순히 top-level에서 return_values를 join
        # ── ⑦  최종 반환값 계산 ────────────────────────────────
        if len(return_values) == 0:
            # (A) 명시적 return 이 없을 때
            if fcfg.return_vars:  # named returns 존재
                _log_implicit_return(fcfg.return_vars)
                self._record_enabled = False
                if len(fcfg.return_vars) == 1:
                    ret_obj = fcfg.return_vars[0]  # Variables 객체
                    return ret_obj.value  # Interval / 값 반환
                else:
                    # 여러 개면 튜플 형태로 묶어 돌려줌
                    return [rv.value for rv in fcfg.return_vars]
            else:
                exit_retvals = list(fcfg.get_exit_node().return_vals.values())
                if exit_retvals:  # ★ 새 코드
                    joined = exit_retvals[0]
                    for v in exit_retvals[1:]:
                        joined = joined.join(v)  # Interval 등은 join
                    return joined
                return None

        elif len(return_values) == 1:
            self._record_enabled = False
            return return_values[0]

        else:
            self._record_enabled = False
            joined_ret = return_values[0]
            for rv in return_values[1:]:
                joined_ret = joined_ret.join(rv)
            return joined_ret

    def interpret_variable_declaration_statement(self, stmt, variables):
        var_type = stmt.type_obj
        var_name = stmt.var_name
        init_expr = stmt.init_expr  # None 가능

        # ① 변수 객체 찾기 (process 단계에서 이미 cur_blk.variables 에 들어있음)
        if var_name not in variables:
            vobj = Variables(identifier=var_name, scope="local")
            vobj.typeInfo = var_type

            # 타입에 맞춰 ⊥ 값으로 초기화
            et = var_type.elementaryTypeName
            if et.startswith("uint"):
                bits = var_type.intTypeLength or 256
                vobj.value = UnsignedIntegerInterval.bottom(bits)
            elif et.startswith("int"):
                bits = var_type.intTypeLength or 256
                vobj.value = IntegerInterval.bottom(bits)
            elif et == "bool":
                vobj.value = BoolInterval.bottom()
            else:  # address / bytes / string 등
                vobj.value = f"symbol_{var_name}"

            variables[var_name] = vobj  # ★ env 에 등록
        else:
            vobj = variables[var_name]

        # ② 초기화 식 평가 (있을 때만)
        if init_expr is not None:
            if isinstance(vobj, ArrayVariable):
                pass  # inline array 등은 필요 시
            else:  # Variables / EnumVariable
                vobj.value = self.eval.evaluate_expression(
                    init_expr, variables, None, None
                )

                # ③ RecordManager 로 기록  ← 기존 _record_analysis 블록 삭제
                self.rec.record_variable_declaration(
                    line_no=stmt.src_line,
                    var_name=var_name,
                    var_obj=vobj
                )

        return variables

    def interpret_assignment_statement(self, stmt, variables):
        # 0) RHS 계산 – 기존과 동일
        lexp, rexpr, op = stmt.left, stmt.right, stmt.operator
        if isinstance(rexpr, Expression):
            r_val = self.eval.evaluate_expression(rexpr, variables, None, None)
        else:  # 이미 Interval·리터럴 등 평가완료 값
            r_val = rexpr

        # 1) LHS 에 반영
        self.up.update_left_var(lexp, r_val, op, variables, None, None, True)

        return variables

    # ------------------------------------------------------------------
    # 단항(++ / -- / delete) 스테이트먼트 해석
    # ------------------------------------------------------------------
    def interpret_unary_statement(self, stmt, variables):
        """
        stmt.operator : '++' | '--' | 'delete' | 'unary_prefix' | 'unary_suffix' …
        stmt.operand  : Expression  (피연산자)

        ▸ ++ / -- 는 handle_unary_incdec() 단계에서 이미
          self.up.update_left_var() 로 값이 반영돼 있으므로
          여기서는 delete 만 실제 값을 지우고,
          나머지는 로그만 남겨 두면 된다.
        """
        op       = stmt.operator
        operand  = stmt.operand
        src_line = stmt.src_line

        # ── delete x  -----------------------------------------------
        if op == 'delete':
            # elementary 면 0 / ⊥ , 복합이면 재귀 ⊥ 적용
            self.up.update_left_var(operand, 0, '=', variables, None, None, True)

        return variables


    def interpret_function_call_statement(self, stmt, variables):
        function_expr = stmt.function_expr
        self.eval.evaluate_function_call_context(function_expr, variables, None, None)

        return variables

    def interpret_return_statement(self, stmt, variables, ret_acc=None):
        rexpr = stmt.return_expr
        r_val = self.eval.evaluate_expression(rexpr, variables, None, None)

        # NEW ─ 반드시 한 줄로 기록
        self.rec.record_return(
            line_no=stmt.src_line,
            return_expr=rexpr,
            return_val=r_val,
            fn_cfg=self.an.current_target_function_cfg
        )

        # exit-node 에 값 저장 (변경 없음)
        exit_node = self.an.current_target_function_cfg.get_exit_node()
        exit_node.return_vals[stmt.src_line] = r_val
        if ret_acc is not None:
            ret_acc.append(r_val)
            ret_acc.append("__STOP__")  # 실행 중단 플래그

        return variables

    def interpret_revert_statement(self, stmt, variables):
        return variables

    def interpret_break_statement(self, stmt, variables):
        return variables

    def interpret_continue_statement(self, stmt, variables):
        return variables

    def _branch_feasible(self, env: dict, cond: Expression, assume_true: bool) -> bool:
        r = self.eval.evaluate_expression(cond, env, None, None)

        # (a) BoolInterval — 확정 0/1 인지 확인
        if isinstance(r, BoolInterval):
            return (r.max_value == 1) if assume_true else (r.min_value == 0)

        # (b) 정수·주소 → bool 로 승격해 판단 (0 ↔ false)
        if VariableEnv.is_interval(r):
            as_bool = VariableEnv.convert_int_to_bool_interval(r)
            return (as_bool.max_value == 1) if assume_true else (as_bool.min_value == 0)

        # (c) 심벌릭 등 → “가능성 있어 보인다” 로 간주
        return True

    def _set_bottom_env(self, env: dict[str, Variables]) -> None:
        for v in env.values():
            self._make_bottom(v)

    # ContractAnalyzer 내부 - private
    def _make_bottom(self, v: Variables) -> None:
        """
        주어진 변수 객체(모든 서브-타입 포함)를
        ‘도달 불가능 환경’용 ⊥ 값으로 재귀 초기화한다.
        (in-place, return None)
        """

        # ─── A. **배열** ────────────────────────────────
        if isinstance(v, ArrayVariable):
            for elem in v.elements:
                self._make_bottom(elem)
            return  # Array 자체엔 별도 value 없음

        # ─── B. **구조체** ─────────────────────────────
        if isinstance(v, StructVariable):
            for m in v.members.values():
                self._make_bottom(m)
            return

        # ─── C. **매핑** ───────────────────────────────
        if isinstance(v, MappingVariable):
            for mv in v.mapping.values():
                self._make_bottom(mv)
            return

        # ─── D. **단일/Enum 값** ──────────────────────
        # ① 정수 interval
        if isinstance(v.value, UnsignedIntegerInterval):
            bits = v.value.type_length
            v.value = UnsignedIntegerInterval.bottom(bits)  # min=max=None
            return
        if isinstance(v.value, IntegerInterval):
            bits = v.value.type_length
            v.value = IntegerInterval.bottom(bits)
            return

        # ② Bool interval
        if isinstance(v.value, BoolInterval):
            v.value = BoolInterval.bottom()
            return

        # ③ 주소 interval (160-bit uint)
        if isinstance(v.value, UnsignedIntegerInterval) and v.value.type_length == 160:
            v.value = UnsignedIntegerInterval.bottom(160)
            return

        # ④ 나머지(string, bytes, 심볼 등) → None
        v.value = None

    def _force_join_before_exit(self, fcfg: FunctionCFG) -> None:
        """
        while/if 등을 모두 돈 뒤 아직 join 되지 않은 leaf-노드를
        EXIT 노드로 끌어모아 변수 구간을 확정한다.
        """

        def _is_leaf(g, n) -> bool:
            succs = list(g.successors(n))
            return (
                    not n.condition_node  # 조건 블록이 아니고
                    and len(succs) == 1  # successor 하나뿐이며
                    and succs[0].name == "EXIT"  # 그게 EXIT 노드
            )

        g = fcfg.graph
        exit_node = fcfg.get_exit_node()
        leaves = [n for n in g.nodes if _is_leaf(g, n)]

        # ─── (1) leaf 들의 변수환경을 통째로 join ──────────────────────
        joined_env: dict[str, Variables] = {}
        for leaf in leaves:
            joined_env = VariableEnv.join_variables_simple(joined_env, leaf.variables)

        # ─── (2) EXIT 노드에 반영 ─────────────────────────────────────
        exit_node.variables = joined_env

        # ─── (3) 그래프 재배선 (leaf → EXIT) ──────────────────────────
        for leaf in leaves:
            g.add_edge(leaf, exit_node)

    def _sync_named_return_vars(self, fcfg: FunctionCFG) -> None:
        exit_env = fcfg.get_exit_node().variables
        for rv in fcfg.return_vars:
            if rv.identifier in exit_env:
                src = exit_env[rv.identifier]
                # elementary → value 만, 복합 → 객체 자체 공유
                if hasattr(rv, "value"):
                    rv.value = getattr(src, "value", src)
                else:
                    # Array/Struct 등은 객체를 그대로 달아 줘도 무방
                    fcfg.return_vars[fcfg.return_vars.index(rv)] = src

    def _last_executable_line(self, fcfg: FunctionCFG) -> int | None:
        rng = self._function_body_range(fcfg)
        if rng is None:
            return None

        body_start, body_end = rng
        for ln in range(body_end, body_start - 1, -1):
            code = self.an.full_code_lines.get(ln, "").strip()
            if not code or code == "}" or code.startswith("//"):
                continue
            return ln
        return None

    def _function_start_line(self, fcfg: FunctionCFG) -> int | None:
        """
        fcfg.entry_node 가 어느 라인(brace_count key)에 매달려 있는지 찾는다.
        """
        entry = fcfg.get_entry_node()
        for ln, info in self.an.brace_count.items():
            if info.get("cfg_node") is entry:  # ← identity 비교
                return ln
        return None

    def _function_body_range(self, fcfg: FunctionCFG) -> tuple[int, int] | None:
        fn_start_ln = self._function_start_line(fcfg)
        if fn_start_ln is None:
            return None

        start_balance = 0
        for ln in range(1, fn_start_ln):
            bc = self.an.brace_count.get(ln, {})
            start_balance += bc.get("open", 0) - bc.get("close", 0)

        body_start = None
        balance = start_balance
        max_ln = max(self.an.full_code_lines) if self.an.full_code_lines else fn_start_ln
        for ln in range(fn_start_ln, max_ln + 1):
            bc = self.an.brace_count.get(ln, {})
            balance += bc.get("open", 0) - bc.get("close", 0)

            if balance == start_balance + 1 and body_start is None:
                body_start = ln + 1
            if balance == start_balance and body_start is not None:
                return (body_start, ln - 1)
        return None

    def _try_concrete_key(self, idx_expr, var_env) -> str | None:
        """
        idx_expr 를 evaluate 해 보아 단일 값인지 판단한다.
        반환:
          • "123"  ← 확정된 숫자/주소
          • None   ← 여러 값 가능 → 불확정
        """
        val = self.eval.evaluate_expression(idx_expr, var_env, None, None)

        # 1) Interval 이면서 두 끝점이 동일한 ‘실수’일 때만
        if (VariableEnv.is_interval(val)
                and val.min_value is not None
                and val.max_value is not None
                and val.min_value == val.max_value):
            return str(val.min_value)

        # 2) 이미 단일 리터럴(정수·주소 문자열)이면
        if isinstance(val, (int, str)):
            return str(val)

        # 3) 그 밖엔 불확정
        return None