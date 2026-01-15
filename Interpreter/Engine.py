# engine.py (발췌/교체본)

from __future__ import annotations
from typing import TYPE_CHECKING, Optional
if TYPE_CHECKING:
    from Analyzer.ContractAnalyzer import ContractAnalyzer

from Domain.Variable import Variables, MappingVariable, ArrayVariable, StructVariable
from Domain.IR import Expression
from Domain.Interval import UnsignedIntegerInterval, IntegerInterval, BoolInterval
from Utils.CFG import CFGNode, FunctionCFG
from Utils.Helper import VariableEnv
from collections import deque
from typing import cast  # 파일 상단 import 구역에 추가

class Engine:
    def __init__(self, an: "ContractAnalyzer"):
        self.an = an
        # ── 기록 제어 플래그(기존 Runtime 것이 여기로 이동) ───────────────
        self._record_enabled: bool = True
        self._suppress_stmt_records: bool = False  # 고정점 중 문장 기록 억제
        self._in_widening_mode: bool = False  # widening 중에는 side-effect 억제

    # ── lazy properties (그대로 유지) ──────────────────────────────────
    @property
    def ref(self):
        return self.an.refiner
    @property
    def rec(self):
        return self.an.recorder
    @property
    def eval(self):
        return self.an.evaluator
    @property
    def up(self):
        return self.an.updater


    # =================================================================
    #  (통합) 문장 해석기 – 기존 Runtime.* 가 여기로 이동
    # =================================================================
    def update_statement_with_variables(self, stmt, current_variables, ret_acc=None):
        typ = stmt.statement_type
        if   typ == 'variableDeclaration':
            return self._interpret_var_decl(stmt, current_variables)
        elif typ == 'assignment':
            return self._interpret_assignment(stmt, current_variables)
        elif typ == 'unary':
            return self._interpret_unary(stmt, current_variables)
        elif typ == 'functionCall':
            return self._interpret_func_call(stmt, current_variables)
        elif typ == 'return':
            return self._interpret_return(stmt, current_variables, ret_acc)
        elif typ == 'revert':
            return self._interpret_revert(stmt, current_variables)
        elif typ == 'break':
            return self._interpret_break(stmt, current_variables)
        elif typ == 'continue':
            return self._interpret_continue(stmt, current_variables)
        else:
            raise ValueError(f"Statement '{typ}' is not implemented.")

    def _interpret_var_decl(self, stmt, variables):
        var_type = stmt.type_obj
        var_name = stmt.var_name
        init_expr = stmt.init_expr

        # ──────────────────────────────────────────────────────────────
        # 1. 변수가 없으면 새로 생성
        # ──────────────────────────────────────────────────────────────
        if var_name not in variables:
            if var_type.typeCategory in ("struct", "array", "mapping"):
                # 초기화식 없으면 타입에 맞는 빈 객체 생성
                if var_type.typeCategory == "array":
                    vobj = ArrayVariable(
                        identifier=var_name,
                        base_type=var_type.arrayBaseType,
                        array_length=var_type.arrayLength,
                        is_dynamic=var_type.isDynamicArray,
                        scope="local"
                    )
                elif var_type.typeCategory == "struct":
                    vobj = StructVariable(
                        identifier=var_name,
                        struct_type=var_type.structTypeName,
                        scope="local"
                    )
                elif var_type.typeCategory == "mapping":
                    vobj = MappingVariable(
                        identifier=var_name,
                        key_type=var_type.mappingKeyType,
                        value_type=var_type.mappingValueType,
                        scope="local"
                    )
                variables[var_name] = vobj
            else:
                # Elementary 타입 처리
                vobj = Variables(identifier=var_name, scope="local")
                vobj.typeInfo = var_type
                et = var_type.elementaryTypeName
                if et and et.startswith("uint"):
                    bits = var_type.intTypeLength or 256
                    vobj.value = UnsignedIntegerInterval.bottom(bits)
                elif et and et.startswith("int"):
                    bits = var_type.intTypeLength or 256
                    vobj.value = IntegerInterval.bottom(bits)
                elif et == "bool":
                    vobj.value = BoolInterval.bottom()
                else:
                    vobj.value = f"symbol_{var_name}"
                variables[var_name] = vobj

        # ──────────────────────────────────────────────────────────────
        # 2. 초기화식이 있으면 항상 평가 (변수가 이미 있어도)
        # ──────────────────────────────────────────────────────────────
        if init_expr is not None:
            if var_type.typeCategory in ("struct", "array", "mapping"):
                # 구조체/배열/매핑: 초기화식 평가 결과로 변수 대체
                eval_result = self.eval.evaluate_expression(init_expr, variables, None, None)
                if isinstance(eval_result, (StructVariable, ArrayVariable, MappingVariable)):
                    eval_result.identifier = var_name
                    variables[var_name] = eval_result
                    vobj = eval_result
                else:
                    vobj = variables[var_name]
            else:
                # Elementary 타입: 값 평가 후 업데이트
                vobj = variables[var_name]
                eval_result = self.eval.evaluate_expression(init_expr, variables, None, None)

                # 평가 결과가 Variables 객체면 그 value를 추출
                if isinstance(eval_result, Variables) and not isinstance(eval_result, (ArrayVariable, StructVariable, MappingVariable)):
                    vobj.value = getattr(eval_result, 'value', eval_result)
                else:
                    vobj.value = eval_result

                if self._record_enabled and not self._suppress_stmt_records:
                    self.rec.record_variable_declaration(
                        line_no=stmt.src_line,
                        var_name=var_name,
                        var_obj=vobj
                    )

        return variables

    def _interpret_assignment(self, stmt, variables):
        lexp, rexpr, op = stmt.left, stmt.right, stmt.operator
        r_val = (self.eval.evaluate_expression(rexpr, variables, None, None)
                 if isinstance(rexpr, Expression) else rexpr)

        should_record = self._record_enabled and not self._suppress_stmt_records
        line_num = getattr(stmt, 'src_line', None)

        # stmt.src_line을 line_no로 전달
        self.up.update_left_var(lexp, r_val, op, variables, None, None, should_record, line_num)
        return variables

    def _interpret_unary(self, stmt, variables):
        op = stmt.operator
        operand = stmt.operand

        if op == '++' or op == 'unary_suffix' or op == 'unary_prefix':
            self.up.update_left_var(operand, 1, '+=', variables, None, None, False)
            return variables
        if op == '--':
            self.up.update_left_var(operand, 1, '-=', variables, None, None, False)
            return variables
        if op == 'delete':
            self.up.update_left_var(operand, 0, '=', variables, None, None,
                                    (self._record_enabled and not self._suppress_stmt_records))
            return variables
        return variables

    def _interpret_func_call(self, stmt, variables):
        self.eval.evaluate_function_call_context(stmt.function_expr, variables, None, None)
        return variables

    def _interpret_return(self, stmt, variables, ret_acc=None):
        rexpr = stmt.return_expr
        r_val = self.eval.evaluate_expression(rexpr, variables, None, None)
        if self._record_enabled and not self._suppress_stmt_records:
            self.rec.record_return(
                line_no=stmt.src_line,
                return_expr=rexpr,
                return_val=r_val,
                fn_cfg=self.an.current_target_function_cfg
            )
        exit_node = self.an.current_target_function_cfg.get_exit_node()
        exit_node.return_vals[stmt.src_line] = r_val
        if ret_acc is not None:
            ret_acc.append(r_val); ret_acc.append("__STOP__")
        return variables

    def _interpret_revert(self, stmt, variables):
        return variables
    def _interpret_break(self, stmt, variables):
        return variables
    def _interpret_continue(self, stmt, variables):
        return variables

    # =================================================================
    #  Transfer (엔진 내부에서 바로 호출하도록 수정)
    # =================================================================
    def transfer_function(self, node: CFGNode, in_vars: Optional[dict[str, Variables]]) -> dict[str, Variables]:
        env_in = in_vars or {}
        if getattr(node, "fixpoint_evaluation_node", False):
            node.variables = VariableEnv.copy_variables(env_in)
            return env_in
        env_out = VariableEnv.copy_variables(env_in)
        if getattr(node, "statements", None):
            for st in node.statements:
                env_out = self.update_statement_with_variables(st, env_out)
        node.variables = VariableEnv.copy_variables(env_out)
        return env_out

    # =================================================================
    #  Loop Condition Convergence Check & Iteration Estimation
    # =================================================================
    def _check_loop_condition_converged(self, cond_expr: Expression,
                                       prev_env: dict[str, Variables],
                                       curr_env: dict[str, Variables]) -> bool:
        """
        루프 조건식을 평가하여 조건이 수렴했는지 체크

        조건식의 좌변과 우변을 각각 평가하여 둘 다 singleton으로 수렴했는지 확인

        Args:
            cond_expr: 루프 조건식
            prev_env: 이전 iteration의 변수 환경
            curr_env: 현재 iteration의 변수 환경

        Returns:
            True if 조건식의 좌변/우변이 모두 singleton으로 수렴
        """
        if cond_expr is None or not prev_env or not curr_env:
            return False

        # Binary expression이 아니면 판단 불가
        if not (hasattr(cond_expr, 'left') and hasattr(cond_expr, 'right')):
            return False

        try:
            # 좌변 평가
            prev_left = self.eval.evaluate_expression(cond_expr.left, prev_env, None, None)
            curr_left = self.eval.evaluate_expression(cond_expr.left, curr_env, None, None)

            # 우변 평가
            prev_right = self.eval.evaluate_expression(cond_expr.right, prev_env, None, None)
            curr_right = self.eval.evaluate_expression(cond_expr.right, curr_env, None, None)

            # 좌변 수렴 체크
            left_converged = False
            if VariableEnv.is_interval(prev_left) and VariableEnv.is_interval(curr_left):
                prev_left_singleton = (not prev_left.is_bottom() and
                                      prev_left.min_value == prev_left.max_value)
                curr_left_singleton = (not curr_left.is_bottom() and
                                      curr_left.min_value == curr_left.max_value)
                if prev_left_singleton and curr_left_singleton:
                    left_converged = (prev_left.min_value == curr_left.min_value)

            # 우변 수렴 체크
            right_converged = False
            if VariableEnv.is_interval(prev_right) and VariableEnv.is_interval(curr_right):
                prev_right_singleton = (not prev_right.is_bottom() and
                                       prev_right.min_value == prev_right.max_value)
                curr_right_singleton = (not curr_right.is_bottom() and
                                       curr_right.min_value == curr_right.max_value)
                if prev_right_singleton and curr_right_singleton:
                    right_converged = (prev_right.min_value == curr_right.min_value)

            # 좌변과 우변이 모두 수렴하면 true
            return left_converged and right_converged

        except Exception:
            return False

    def _estimate_loop_iterations(self, head: CFGNode, start_env: dict) -> int:
        """
        Loop 조건식을 평가해서 예상 반복 횟수 추정

        Args:
            head: Loop head node
            start_env: Loop 진입 시점의 변수 환경

        Returns:
            추정 반복 횟수 (기본값: 1, 최대값: 20)
        """
        # Loop head가 condition node가 아니면 기본값
        if not getattr(head, 'condition_node', False):
            return 1

        cond_expr = getattr(head, 'condition_expr', None)
        if cond_expr is None:
            return 1

        # 조건식 평가
        try:
            # Binary expression인지 확인
            if not hasattr(cond_expr, 'operator') or cond_expr.operator not in ['<', '<=', '>', '>=', '!=']:
                return 1

            # 좌변/우변 평가 (Evaluation.py 활용)
            left_val = self.eval.evaluate_expression(cond_expr.left, start_env, None, None)
            right_val = self.eval.evaluate_expression(cond_expr.right, start_env, None, None)

            # Interval인지 확인
            if not (VariableEnv.is_interval(left_val) and VariableEnv.is_interval(right_val)):
                return 1

            # bottom 체크
            if left_val.is_bottom() or right_val.is_bottom():
                return 1

            # 반복 횟수 계산
            if cond_expr.operator in ['<', '<=']:
                # left < right: right의 상한 - left의 하한
                iterations = right_val.max_value - left_val.min_value
                if cond_expr.operator == '<=':
                    iterations += 1
            elif cond_expr.operator in ['>', '>=']:
                # left > right: left의 상한 - right의 하한
                iterations = left_val.max_value - right_val.min_value
                if cond_expr.operator == '>=':
                    iterations += 1
            elif cond_expr.operator == '!=':
                # != 조건은 예측 어려움, 보수적으로 처리
                return 10
            else:
                return 1

            # 합리적인 범위로 제한: [1, 20]
            if iterations <= 0:
                return 1
            elif iterations > 20:
                return 20
            else:
                return int(iterations)

        except Exception as e:
            # 평가 실패 시 기본값
            return 1

    # =================================================================
    #  Fixpoint (루프 중 문장기록 억제)
    # =================================================================
    def fixpoint(self, head: CFGNode) -> CFGNode:
        G = self.an.current_target_function_cfg.graph
        ref = self.ref; rec = self.rec

        def _edge_flow_from_node_out(node, succ, node_out_env):
            base = VariableEnv.copy_variables(node_out_env or {})
            if getattr(node, "condition_node", False):
                ed = G.get_edge_data(node, succ, default=None)
                cond_expr = getattr(node, "condition_expr", None)
                if ed and "condition" in ed and cond_expr is not None:
                    want_true = bool(ed["condition"])
                    ref.update_variables_with_condition(base, cond_expr, want_true)
                    if not self._branch_feasible(base, cond_expr, want_true):
                        return None
            return base

        loop_nodes: set[CFGNode] = self.traverse_loop_nodes(head)
        from collections import defaultdict
        visit_cnt: defaultdict[CFGNode, int] = defaultdict(int)
        in_vars: dict[CFGNode, dict[str, Variables] | None] = {n: None for n in loop_nodes}
        out_vars: dict[CFGNode, dict[str, Variables] | None] = {n: None for n in loop_nodes}

        # ★ fixpoint 시작 전에 join 노드의 cached fixpoint vars 초기화
        for n in loop_nodes:
            if getattr(n, "fixpoint_evaluation_node", False):
                if hasattr(n, "fixpoint_evaluation_node_vars"):
                    delattr(n, "fixpoint_evaluation_node_vars")

        # ★ start_env 계산: join 노드의 경우 back edge를 제외하고 초기 진입 edge만 사용
        start_env = None
        join_node_ref = None
        for p in G.predecessors(head):
            # join 노드인 경우: 그 predecessor 중 loop 내부가 아닌 것만 사용
            if getattr(p, "fixpoint_evaluation_node", False):
                join_node_ref = p
                for pp in G.predecessors(p):
                    # back edge (증감식)는 제외: loop_nodes에 속하는 predecessor는 skip
                    if pp in loop_nodes:
                        continue
                    pp_vars = getattr(pp, "variables", {}) or {}
                    start_env = VariableEnv.join_variables_simple(start_env, pp_vars)
            else:
                # 일반 predecessor
                p_vars = getattr(p, "variables", {}) or {}
                start_env = VariableEnv.join_variables_simple(start_env, p_vars)
        in_vars[head] = start_env or {}

        # ★ join 노드를 loop_nodes에 추가하고 초기값 설정
        # 이렇게 하면 첫 iteration에서 i=1부터 시작됨
        if join_node_ref is not None:
            loop_nodes.add(join_node_ref)
            in_vars[join_node_ref] = VariableEnv.copy_variables(start_env or {})
            out_vars[join_node_ref] = None
            join_node_ref.join_baseline_env = VariableEnv.copy_variables(start_env or {})

        # ── 루프 내부 문장 기록 억제 on
        old_sup = self._suppress_stmt_records
        self._suppress_stmt_records = True

        # Loop 반복 횟수 추정 (조건식 기반)
        widening_threshold = (self._estimate_loop_iterations(head, in_vars[head]))

        # ★ widening - 초기 WL은 head만 (join 노드는 predecessor가 준비되면 자동으로 추가됨)
        W_MAX = 300
        WL = deque([head])
        iteration = 0

        while WL and max(visit_cnt.values(), default=0) < W_MAX:
            node = WL.popleft()
            visit_cnt[node] += 1
            iteration += 1

            # ★ in_vars[node]가 None인 경우 처리
            if in_vars[node] is None:
                # None이면 predecessor들의 out을 join해서 계산
                in_new = None
                for p in G.predecessors(node):
                    if p in loop_nodes and out_vars[p] is not None:
                        flow = _edge_flow_from_node_out(p, node, out_vars[p])
                        if flow is not None:
                            in_new = VariableEnv.join_variables_simple(in_new, flow)
                if in_new is not None:
                    in_vars[node] = in_new

            out_old = out_vars[node]

            # ★ widening 필요 여부를 미리 계산하고 플래그 설정
            need_widen = (getattr(node, "fixpoint_evaluation_node", False) and
                          visit_cnt[node] > widening_threshold)

            # ★ widening 모드 설정 (후속 노드들도 widening threshold 넘으면 추상화)
            old_widening = self._in_widening_mode
            if visit_cnt[node] > widening_threshold:
                self._in_widening_mode = True

            out_raw = self.transfer_function(node, in_vars[node])

            # ★ widening 모드 복원
            self._in_widening_mode = old_widening

            out_joined = (
                VariableEnv.join_variables_with_widening(out_old, out_raw)
                if need_widen else
                VariableEnv.join_variables_simple(out_old, out_raw)
            )

            if getattr(node, "fixpoint_evaluation_node", False):
                node.fixpoint_evaluation_node_vars = VariableEnv.copy_variables(out_joined)

            equal = VariableEnv.variables_equal(out_old, out_joined)

            if equal:
                out_vars[node] = out_joined; continue
            out_vars[node] = out_joined

            for succ in G.successors(node):
                if succ not in loop_nodes:  # 루프 밖은 고정점 후 reinterpret에서 처리
                    continue
                flow = _edge_flow_from_node_out(node, succ, out_joined)
                if flow is None:
                    continue
                if getattr(succ, "fixpoint_evaluation_node", False):
                    succ_widen = (visit_cnt[succ] > widening_threshold)
                else:
                    succ_widen = False

                in_new = (VariableEnv.join_variables_with_widening(in_vars[succ], flow)
                          if succ_widen
                          else VariableEnv.join_variables_simple(in_vars[succ], flow))

                changed_succ = not VariableEnv.variables_equal(in_vars[succ], in_new)

                if changed_succ:
                    in_vars[succ] = VariableEnv.copy_variables(in_new)
                    WL.append(succ)

        # narrowing
        WL = deque(loop_nodes); N_MAX = 30
        while WL and N_MAX:
            N_MAX -= 1
            node = WL.popleft()

            new_in = None
            for p in G.predecessors(node):
                src = out_vars.get(p) or getattr(p, "variables", {}) or {}
                flow = _edge_flow_from_node_out(p, node, src)
                if flow is None:
                    continue
                new_in = VariableEnv.join_variables_simple(new_in, flow)

            if not VariableEnv.variables_equal(in_vars[node], new_in):
                in_vars[node] = VariableEnv.copy_variables(new_in or {})

            # ★ unreachable 노드 처리: in_vars가 빈 딕셔너리면 skip
            if not in_vars[node]:
                # 이 노드는 unreachable (모든 predecessor의 flow가 None)
                continue

            tmp_out = self.transfer_function(node, in_vars[node])
            narrowed = (VariableEnv.narrow_variables(out_vars[node], tmp_out)
                        if getattr(node, "fixpoint_evaluation_node", False)
                        else tmp_out)

            if VariableEnv.variables_equal(out_vars[node], narrowed):
                continue
            out_vars[node] = narrowed

            for succ in G.successors(node):
                if succ in loop_nodes:
                    WL.append(succ)


        # 루프 내부 문장 기록 억제 off
        self._suppress_stmt_records = old_sup

        # exit env
        exit_node = self.find_loop_exit_node(head)
        if not exit_node:
            raise ValueError("loop without exit-node")

        exit_env = None
        for p in G.predecessors(exit_node):
            src = out_vars.get(p) or getattr(p, "variables", {}) or {}
            flow = _edge_flow_from_node_out(p, exit_node, src)
            if flow is None:
                continue
            exit_env = VariableEnv.join_variables_simple(exit_env, flow)
        exit_node.variables = VariableEnv.copy_variables(exit_env or {})

        # loopDelta: 헤더(조건) 라인에 기록
        # ★ fixpoint evaluation node(join)의 고정점 상태를 사용 (false edge 정제 전)
        join_node = None
        for p in G.predecessors(head):
            if getattr(p, "fixpoint_evaluation_node", False):
                join_node = p
                break

        if join_node is not None:
            base_env = getattr(join_node, "join_baseline_env", None)
            # ★ fixpoint_evaluation_node_vars: 고정점 도달 후 join 노드의 최종 상태
            fixpoint_env = getattr(join_node, "fixpoint_evaluation_node_vars", None)

            if base_env is not None and fixpoint_env is not None:
                changed_flat = VariableEnv.diff_changed(base_env, fixpoint_env)

                if changed_flat:
                    ln_head = getattr(head, "src_line", None)
                    if ln_head is not None:
                        # loopDelta 기록: diff_changed는 이미 직렬화된 딕셔너리를 반환하므로
                        # _append_or_replace를 직접 호출
                        rec._append_or_replace(
                            ln_head,
                            {"kind": "loopDelta", "vars": changed_flat},
                            replace_rule=lambda old, new: old.get("kind") == new["kind"],
                        )

        return exit_node

    # =================================================================
    #  interpret_function_cfg (내부 함수 호출용 - 기록 비활성화)
    # =================================================================
    def interpret_function_cfg(self, fcfg: FunctionCFG, caller_env: dict[str, Variables] | None = None):
        return self._interpret_function_cfg_impl(fcfg, caller_env, record_enabled=False)

    # =================================================================
    #  interpret_function_cfg_for_debug (디버깅 테스트용 - 기록 활성화)
    # =================================================================
    def interpret_function_cfg_for_debug(self, fcfg: FunctionCFG, caller_env: dict[str, Variables] | None = None):
        return self._interpret_function_cfg_impl(fcfg, caller_env, record_enabled=True)

    # =================================================================
    #  _interpret_function_cfg_impl (공통 구현)
    # =================================================================
    def _interpret_function_cfg_impl(self, fcfg: FunctionCFG, caller_env: dict[str, Variables] | None = None, record_enabled: bool = False):
        an = self.an; rec = self.rec
        _old_func = an.current_target_function
        _old_fcfg = an.current_target_function_cfg

        # ★ 재귀 호출 전 _record_enabled 상태 저장 (내부 함수 호출 후 복원용)
        _old_record_enabled = self._record_enabled

        an.current_target_function = fcfg.function_name
        an.current_target_function_cfg = fcfg

        # 기록 활성화 여부 설정
        self._record_enabled = record_enabled
        an._seen_stmt_ids.clear()
        for blk in fcfg.graph.nodes:
            # ★ 노드의 variables 초기화 (이전 실행의 값 제거)
            blk.variables = {}
            for st in blk.statements:
                ln = getattr(st, "src_line", None)
                if ln is not None and ln in an.analysis_per_line:
                    an.analysis_per_line[ln].clear()

        entry = fcfg.get_entry_node()
        (start_block,) = fcfg.graph.successors(entry)

        start_block.variables = VariableEnv.copy_variables(fcfg.related_variables)

        if caller_env is not None:
            for k, v in caller_env.items():
                start_block.variables[k] = v

        G = fcfg.graph
        def _is_sink(n: CFGNode) -> bool:
            if getattr(n, "function_exit_node", False): return True
            if getattr(n, "error_exit_node", False):    return True
            if getattr(n, "return_exit_node", False):   return True
            nm = getattr(n, "name", "")
            return nm in {"EXIT", "ERROR", "RETURN"}

        def _edge_env_from_pred(pred: CFGNode, succ: CFGNode):
            base = VariableEnv.copy_variables(getattr(pred, "variables", {}) or {})
            if getattr(pred, "condition_node", False):
                cond_expr = getattr(pred, "condition_expr", None)
                ed = G.get_edge_data(pred, succ, default=None)
                if cond_expr is not None and ed and "condition" in ed:
                    want_true = bool(ed["condition"])
                    self.ref.update_variables_with_condition(base, cond_expr, want_true)
                    if not self._branch_feasible(base, cond_expr, want_true):
                        return None
            return base

        work = deque([start_block])
        visited: set[CFGNode] = set()
        return_values = []

        while work:
            node = work.popleft()
            if node in visited: continue
            visited.add(node)

            preds = list(G.predecessors(node))
            if preds:
                joined = None
                for p in preds:
                    # ★ 이번 해석에서 이미 방문한 predecessor만 join (재해석 시 이전 값 무시)
                    if p not in visited:
                        continue
                    flow = _edge_env_from_pred(p, node)
                    if flow is None: continue
                    joined = (VariableEnv.copy_variables(flow) if joined is None
                              else VariableEnv.join_variables_simple(joined, flow))
                if joined is not None:
                    node.variables = joined

            cur_vars = node.variables
            node.evaluated = True

            if node.condition_node:
                condition_expr = node.condition_expr
                ln = getattr(node, "src_line", None)

                if node.condition_node_type in ["if", "else if"]:
                    true_succs  = [s for s in G.successors(node) if G.edges[node, s].get('condition') is True]
                    false_succs = [s for s in G.successors(node) if G.edges[node, s].get('condition') is False]
                    if len(true_succs) != 1 or len(false_succs) != 1:
                        raise ValueError("if/else-if node must have exactly one true and one false successor.")

                    true_variables  = VariableEnv.copy_variables(cur_vars)
                    false_variables = VariableEnv.copy_variables(cur_vars)
                    self.ref.update_variables_with_condition(true_variables,  condition_expr, True)
                    self.ref.update_variables_with_condition(false_variables, condition_expr, False)

                    can_true  = self._branch_feasible(true_variables,  condition_expr, True)
                    can_false = self._branch_feasible(false_variables, condition_expr, False)

                    if not can_true and not can_false:
                        continue

                    # ✂ branch 기록 제거

                    t = true_succs[0]; f = false_succs[0]
                    if can_true:
                        t.variables = true_variables;  work.append(t)
                    else:
                        self._set_bottom_env(t.variables)
                    if can_false:
                        f.variables = false_variables; work.append(f)
                    else:
                        self._set_bottom_env(f.variables)
                    continue

                elif node.condition_node_type in ["require", "assert"]:
                    (t,) = [s for s in G.successors(node) if G.edges[node, s].get('condition') is True]
                    true_variables = VariableEnv.copy_variables(cur_vars)
                    self.ref.update_variables_with_condition(true_variables, condition_expr, True)
                    can_true = self._branch_feasible(true_variables, condition_expr, True)

                    # ✂ require/assert 기록 제거

                    if can_true:
                        t.variables = true_variables; work.append(t)
                    else:
                        self._set_bottom_env(t.variables)
                    continue

                elif node.condition_node_type in ["while", "for", "do_while"]:
                    exit_node = self.fixpoint(node)
                    for nxt in list(G.successors(exit_node)):
                        if _is_sink(nxt): continue
                        nxt.variables = VariableEnv.copy_variables(exit_node.variables)
                        work.append(nxt)
                    continue

                elif node.condition_node_type == "try":
                    t_succs = [s for s in G.successors(node) if G.edges[node, s].get('condition') is True]
                    f_succs = [s for s in G.successors(node) if G.edges[node, s].get('condition') is False]
                    for s in (t_succs + f_succs):
                        if _is_sink(s): continue
                        s.variables = VariableEnv.copy_variables(cur_vars)
                        work.append(s)
                    continue

                else:
                    raise ValueError(f"Unknown condition node type: {node.condition_node_type}")

            elif getattr(node, "is_for_increment", False):
                for stmt in node.statements:
                    cur_vars = self.update_statement_with_variables(stmt, cur_vars, return_values)
                for succ in G.successors(node):
                    if _is_sink(succ): continue
                    succ.variables = VariableEnv.copy_variables(node.variables)
                    work.append(succ)
                continue

            else:
                for stmt in node.statements:
                    cur_vars = self.update_statement_with_variables(stmt, cur_vars, return_values)
                    if "__STOP__" in return_values:
                        break
                for nxt in list(G.successors(node)):
                    if _is_sink(nxt): continue
                    nxt.variables = VariableEnv.copy_variables(cur_vars)
                    work.append(nxt)

        self._force_join_before_exit(fcfg)
        self._sync_named_return_vars(fcfg)

        # 컨텍스트 복원
        an.current_target_function = _old_func
        an.current_target_function_cfg = _old_fcfg

        # caller_env 반영
        if caller_env is not None:
            exit_env = fcfg.get_exit_node().variables
            for k, v in exit_env.items():
                if k in caller_env:
                    if hasattr(caller_env[k], "value"):
                        caller_env[k].value = v.value
                    else:
                        caller_env[k] = v
                elif isinstance(v, (MappingVariable, ArrayVariable)):
                    caller_env[k] = v

        # 반환값
        def _log_implicit_return(var_objs: list[Variables]):
            if not self._record_enabled: return
            ln = self._last_executable_line(fcfg)
            if ln is None: return
            if len(var_objs) == 1:
                rec.record_return(line_no=ln, return_expr=None, return_val=var_objs[0].value, fn_cfg=fcfg)
            else:
                # ★ add_env_record는 Variables 객체의 딕셔너리를 기대함
                # 직렬화된 딕셔너리가 아닌 Variables 객체 딕셔너리를 전달
                env_dict = {v.identifier: v for v in var_objs}
                self.rec.add_env_record(ln, "implicitReturn", env_dict)

        # ★ 반환 전 _record_enabled 복원을 위한 헬퍼
        def _restore_and_return(val):
            self._record_enabled = _old_record_enabled
            return val

        if len(return_values) == 0:
            if fcfg.return_vars:
                _log_implicit_return(fcfg.return_vars)
                result = fcfg.return_vars[0].value if len(fcfg.return_vars) == 1 \
                       else [rv.value for rv in fcfg.return_vars]
                return _restore_and_return(result)
            else:
                exit_retvals = list(fcfg.get_return_exit_node().return_vals.values())
                if exit_retvals:
                    joined = exit_retvals[0]
                    for v in exit_retvals[1:]:
                        if hasattr(joined, 'join') and hasattr(v, 'join'):
                            joined = joined.join(v)
                        else:
                            # Handle tuples or other types that don't have join method
                            return _restore_and_return(joined)
                    return _restore_and_return(joined)
                return _restore_and_return(None)
        elif len(return_values) == 1:
            return _restore_and_return(return_values[0])
        else:
            # Filter out "__STOP__" strings from return_values
            filtered_values = [rv for rv in return_values if rv != "__STOP__"]
            if not filtered_values:
                return _restore_and_return(None)

            joined_ret = filtered_values[0]
            for rv in filtered_values[1:]:
                if hasattr(joined_ret, 'join') and hasattr(rv, 'join'):
                    joined_ret = joined_ret.join(rv)
                else:
                    # Handle tuples or other types that don't have join method
                    # For now, just return the first valid return value
                    return _restore_and_return(joined_ret)
            return _restore_and_return(joined_ret)

    # =================================================================
    #  reinterpret_from (변경 없음; self.* 호출로 정리)
    # =================================================================
    def reinterpret_from(self, fcfg: "FunctionCFG", seed_or_seeds) -> None:
        G = fcfg.graph; ref = self.ref
        rec = self.rec  # ★ Recorder
        # --- helpers 동일 (_is_loop_head / _false_succs / _is_sink / _edge_env_from_pred / _compute_in) ---

        # ★ 재해석 시 기록 활성화
        self._record_enabled = True
        self._suppress_stmt_records = False

        seeds = list(seed_or_seeds) if isinstance(seed_or_seeds, (list, tuple, set)) else [seed_or_seeds]
        WL, in_queue = deque(), set()
        out_snapshot: dict[CFGNode, dict[str, Variables] | None] = {}

        # ★ 이번 run에서 이미 비웠던 라인 집합
        cleared_lines: set[int] = set()
        # ★ 이번 run에서 “출력 대상으로 건드린 라인” 집합 (send_report에서 사용)
        touched_lines: set[int] = set()
        def _is_loop_head(n):
            return (getattr(n, "condition_node", False) and
                    getattr(n, "condition_node_type", None) in {"while", "for", "doWhile", "do_while"})
        def _false_succs(n):
            return [s for s in G.successors(n) if G[n][s].get("condition") is False]
        def _is_sink(n):
            if getattr(n, "function_exit_node", False): return True
            if getattr(n, "error_exit_node", False):    return True
            if getattr(n, "return_exit_node", False):   return True
            nm = getattr(n, "name", "")
            return nm in {"EXIT", "ERROR", "RETURN"}
        def _edge_env_from_pred(pred, succ):
            base = VariableEnv.copy_variables(getattr(pred, "variables", {}) or {})
            if getattr(pred, "condition_node", False):
                cond_expr = getattr(pred, "condition_expr", None)
                ed = G.get_edge_data(pred, succ, default=None)
                if cond_expr is not None and ed and "condition" in ed:
                    want_true = bool(ed["condition"])
                    ref.update_variables_with_condition(base, cond_expr, want_true)
                    if not self._branch_feasible(base, cond_expr, want_true):
                        return None
                return base
            return base
        def _compute_in(n):
            acc = None
            for p in G.predecessors(n):
                env_p = _edge_env_from_pred(p, n)
                if env_p is None: continue
                acc = VariableEnv.join_variables_simple(acc, env_p)
            return acc or {}

        def _clear_line_once(ln: int | None) -> None:
            if ln is None or ln in cleared_lines:
                return
            rec.clear_line(ln)
            cleared_lines.add(ln)


        for s in seeds:
            if not _is_sink(s) and s not in in_queue:
                WL.append(s); in_queue.add(s)

        while WL:
            n = WL.popleft(); in_queue.discard(n)

            in_env = _compute_in(n)

            # ── loop head는 fixpoint에서 loopDelta를 기록하므로 특별 처리
            if _is_loop_head(n):
                ln_head = getattr(n, "src_line", None)
                if ln_head is not None: touched_lines.add(ln_head)

                # ★ fixpoint 재실행 전에 join 노드의 스냅샷 초기화
                # 디버그 주석 적용 후 조건이 바뀌었을 수 있으므로 clean slate에서 시작
                for p in G.predecessors(n):
                    if getattr(p, "fixpoint_evaluation_node", False):
                        if hasattr(p, "fixpoint_evaluation_node_vars"):
                            delattr(p, "fixpoint_evaluation_node_vars")

                exit_node = self.fixpoint(n)
                for s in G.successors(exit_node):
                    if not _is_sink(s) and s not in in_queue:
                        WL.append(s); in_queue.add(s)

                continue

            # ── (A) 라인 초기화: 이 노드가 기록을 남길 수 있는 라인들을 선제적으로 clear
            #     - 조건 노드: 자신의 src_line (branchTrue/requireTrue 등)
            #     - 일반/베이식: 각 statement 의 src_line
            ln = getattr(n, "src_line", None)
            if getattr(n, "condition_node", False):
                _clear_line_once(ln)
                if ln is not None: touched_lines.add(ln)
            else:
                for st in getattr(n, "statements", []):
                    ln_st = getattr(st, "src_line", None)
                    _clear_line_once(ln_st)
                    if ln_st is not None: touched_lines.add(ln_st)

            new_out = self.transfer_function(n, in_env)
            n.variables = VariableEnv.copy_variables(new_out)

            changed = not VariableEnv.variables_equal(out_snapshot.get(n), new_out)
            out_snapshot[n] = VariableEnv.copy_variables(new_out)

            if changed:
                for s in G.successors(n):
                    if not _is_sink(s) and s not in in_queue:
                        WL.append(s); in_queue.add(s)

            # ★ 이번 reinterpret 에서 ‘어디를 보여줄지’를 ContractAnalyzer에 남김
            if touched_lines:
                self.an._last_touched_lines = set(touched_lines)

    # =================================================================
    #  Helpers (branch feasible, bottom, EXIT sync, line utils)
    # =================================================================
    def _branch_feasible(self, env: dict, cond: Expression, assume_true: bool) -> bool:
        r = self.eval.evaluate_expression(cond, env, None, None)
        if isinstance(r, BoolInterval):
            return (r.max_value == 1) if assume_true else (r.min_value == 0)
        if VariableEnv.is_interval(r):
            as_bool = VariableEnv.convert_int_to_bool_interval(r)
            return (as_bool.max_value == 1) if assume_true else (as_bool.min_value == 0)
        return True

    def _set_bottom_env(self, env: dict[str, Variables]) -> None:
        for v in env.values():
            self._make_bottom(v)

    def _make_bottom(self, v: Variables) -> None:
        if isinstance(v, ArrayVariable):
            for elem in v.elements: self._make_bottom(elem); return
        if isinstance(v, StructVariable):
            for m in v.members.values(): self._make_bottom(m); return
        if isinstance(v, MappingVariable):
            for mv in v.mapping.values(): self._make_bottom(mv); return
        val = getattr(v, "value", None)
        if isinstance(val, UnsignedIntegerInterval):
            v.value = UnsignedIntegerInterval.bottom(val.type_length); return
        if isinstance(val, IntegerInterval):
            v.value = IntegerInterval.bottom(val.type_length); return
        if isinstance(val, BoolInterval):
            v.value = BoolInterval.bottom(); return
        v.value = None

    def _force_join_before_exit(self, fcfg: FunctionCFG) -> None:
        g = fcfg.graph; exit_node = fcfg.get_exit_node()
        joined_env: dict[str, Variables] = {}
        for p in list(g.predecessors(exit_node)):
            joined_env = VariableEnv.join_variables_simple(joined_env, getattr(p, "variables", {}) or {})
        exit_node.variables = joined_env

    def _sync_named_return_vars(self, fcfg: FunctionCFG) -> None:
        exit_env = fcfg.get_exit_node().variables
        for i, rv in enumerate(fcfg.return_vars or []):
            if rv.identifier in exit_env:
                src = exit_env[rv.identifier]
                if hasattr(rv, "value"): rv.value = getattr(src, "value", src)
                else: fcfg.return_vars[i] = src

    def _last_executable_line(self, fcfg: FunctionCFG) -> int | None:
        rng = self._function_body_range(fcfg)
        if rng is None: return None
        body_start, body_end = rng
        for ln in range(body_end, body_start - 1, -1):
            code = self.an.full_code_lines.get(ln, "").strip()
            if not code or code == "}" or code.startswith("//"): continue
            return ln
        return None

    def _function_start_line(self, fcfg: FunctionCFG) -> int | None:
        entry = fcfg.get_entry_node()
        for ln, info in (self.an.line_info or {}).items():
            nodes = []
            if isinstance(info.get("cfg_nodes"), list): nodes.extend(info["cfg_nodes"])
            if entry in nodes: return ln
        return None

    def _function_body_range(self, fcfg: FunctionCFG) -> tuple[int, int] | None:
        li = self.an.line_info or {}
        fn_start_ln = self._function_start_line(fcfg)
        if fn_start_ln is None: return None
        def _oc(ln: int) -> tuple[int, int]:
            info = li.get(ln, {}); return int(info.get("open", 0)), int(info.get("close", 0))
        start_balance = 0
        for ln in range(1, fn_start_ln):
            o, c = _oc(ln); start_balance += (o - c)
        body_start = None; balance = start_balance
        max_ln = max(li.keys()) if li else fn_start_ln
        for ln in range(fn_start_ln, max_ln + 1):
            o, c = _oc(ln); balance += (o - c)
            if balance == start_balance + 1 and body_start is None:
                body_start = ln + 1
            if balance == start_balance and body_start is not None:
                return (body_start, ln - 1)
        return None

    # Engine 클래스 내부에 추가
    def traverse_loop_nodes(self, loop_head: CFGNode) -> set[CFGNode]:
        """
        loop_head(while/for/do-while 의 조건 노드)에서 시작해,
        loop-exit 노드(= False 분기에서 loop_exit_node=True)를 '절단점'으로 보고
        그 안쪽 노드들만 수집한다.
        """
        G = self.an.current_target_function_cfg.graph
        visited: set[CFGNode] = set()
        stack = [loop_head]
        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)
            for succ in G.successors(cur):
                # 루프 바깥으로 나가는 exit 노드는 확장하지 않음
                if getattr(succ, "loop_exit_node", False):
                    continue
                stack.append(cast(CFGNode, succ))
        return visited

    def is_node_in_loop(self, node: CFGNode, loop_head: CFGNode) -> bool:
        """
        node 가 loop_head 로 정의된 루프 본문에 속하는지 확인.
        loop_exit_node=True 는 바깥으로 간주.
        """
        if getattr(node, "loop_exit_node", False):
            return False
        return node in self.traverse_loop_nodes(loop_head)

    def find_loop_exit_node(self, loop_head: CFGNode) -> CFGNode:
        """
        (가능하면) 헤더의 False-edge 로 표시된 loop-exit 를 먼저 사용하고,
        없다면 traverse 기반으로 '루프 내부 노드들의 후속 중 루프 밖에 있는 유일한 노드'를 찾는다.
        여러 후보면 loop_exit_node=True 를 우선, 그래도 애매하면 오류.
        """
        G = self.an.current_target_function_cfg.graph

        # 1) 가장 신뢰도 높은 경로: 헤더의 False-edge + loop_exit_node=True
        for succ in G.successors(loop_head):
            if G[loop_head][succ].get("condition") is False and getattr(succ, "loop_exit_node", False):
                return cast(CFGNode, succ)

        # 2) traverse 로 루프 내부 집합을 만든 뒤 바깥으로 나가는 successor 를 후보로 수집
        loop_nodes = self.traverse_loop_nodes(loop_head)
        exit_candidates: set[CFGNode] = set()
        for n in loop_nodes:
            for succ in G.successors(n):
                succ = cast(CFGNode, succ)
                if succ not in loop_nodes:
                    exit_candidates.add(succ)

        if not exit_candidates:
            raise ValueError("loop exit node not found")

        # 3) loop_exit_node=True 가 달린 후보가 하나면 그걸 사용
        flagged = [c for c in exit_candidates if getattr(c, "loop_exit_node", False)]
        if len(flagged) == 1:
            return flagged[0]
        if len(flagged) > 1:
            # 헤더의 False-edge 쪽과 맞닿은 것을 우선적으로 선택 (있으면)
            for c in flagged:
                if loop_head in G.predecessors(c) and G[loop_head][c].get("condition") is False:
                    return c
            raise ValueError(f"ambiguous loop exits: {len(flagged)} candidates with loop_exit_node=True")

        # 4) 플래그가 하나도 없으면,
        #    (a) 헤더 False-edge에서 바로 이어지는 후보가 있으면 그걸 사용
        for c in exit_candidates:
            if loop_head in G.predecessors(c) and G[loop_head][c].get("condition") is False:
                return c
        #    (b) 바깥으로 나간 뒤 다시 루프 안으로 돌아오지 않는 후보를 선호
        for c in exit_candidates:
            if all(succ2 not in loop_nodes for succ2 in G.successors(c)):
                return c
        #    (c) 최후수단: 첫 후보 반환
        return next(iter(exit_candidates))