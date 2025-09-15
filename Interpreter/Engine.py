from __future__ import annotations

from typing import TYPE_CHECKING, Optional

if TYPE_CHECKING:                                         # 타입 검사 전용
     from Analyzer.ContractAnalyzer import ContractAnalyzer

from Domain.Variable import Variables, MappingVariable, ArrayVariable, StructVariable
from Domain.IR import Expression
from Domain.Interval import UnsignedIntegerInterval, IntegerInterval, BoolInterval

from Utils.CFG import CFGNode, FunctionCFG
from Utils.Helper import VariableEnv

from collections import deque

class Engine:

    def __init__(self, an: "ContractAnalyzer"):
        self.an = an

    @property
    def ref(self):
        return self.an.refiner

    @property
    def runtime(self):
        return self.an.runtime
    
    @property
    def rec(self):
        return self.an.recorder

    @property
    def eval(self):
        return self.an.evaluator

    def transfer_function(
            self,
            node: CFGNode,
            in_vars: Optional[dict[str, Variables]],
    ) -> dict[str, Variables]:
        """
        * φ-노드(head join) : 그대로 통과 (고정점 평가용)
        * 조건 노드          : 변수 쓰기 없이 통과
        * 일반/본문/incr/stmt블록 : statement 해석
        * (중요) branch dummy에서는 더 이상 '직전 cond'를 찾아서 pruning하지 않는다.
                - 간선 단위 pruning은 reinterpret / fixpoint의 '전파 단계'에서 수행.
        """
        env_in = in_vars or {}

        # ① φ-노드 : widening 대상이므로 그대로 반환
        if getattr(node, "fixpoint_evaluation_node", False):
            node.variables = VariableEnv.copy_variables(env_in)
            return env_in

        # ② out 복사본 준비
        env_out = VariableEnv.copy_variables(env_in)

        # ③ statement 해석 (조건 노드는 statement 없음)
        if getattr(node, "statements", None):
            for st in node.statements:
                self.runtime.update_statement_with_variables(st, env_out)

        # ④ 노드 env 동기화 후 반환
        node.variables = VariableEnv.copy_variables(env_out)
        return env_out

    def fixpoint(self, head: CFGNode) -> CFGNode:
        """
        head : while/for/do-while 의 '조건 노드'
        반환 : 루프를 빠져나가는 exit-블록

        변경점:
          - φ 노드에서 '이전 스냅샷'과 '이번 1회 전파 결과'가 다르면
            첫 방문부터 widening.
          - 그렇지 않으면 기존처럼 2번째 방문부터 widening.
          - 간선 단위 pruning/feasibility는 기존 그대로.
        """
        from collections import deque, defaultdict

        G = self.an.current_target_function_cfg.graph
        ref = self.ref
        rt = self.runtime

        # ---------- helpers ----------
        def _edge_flow_from_node_out(node, succ, node_out_env):
            base = VariableEnv.copy_variables(node_out_env or {})
            if getattr(node, "condition_node", False):
                ed = G.get_edge_data(node, succ, default=None)
                cond_expr = getattr(node, "condition_expr", None)
                if ed and "condition" in ed and cond_expr is not None:
                    want_true = bool(ed["condition"])
                    ref.update_variables_with_condition(base, cond_expr, want_true)
                    if not rt._branch_feasible(base, cond_expr, want_true):
                        return None
            return base

        # 1) loop node 집합
        loop_nodes: set[CFGNode] = self.traverse_loop_nodes(head)

        # 2) in/out 테이블
        visit_cnt: defaultdict[CFGNode, int] = defaultdict(int)
        in_vars: dict[CFGNode, dict[str, Variables] | None] = {n: None for n in loop_nodes}
        out_vars: dict[CFGNode, dict[str, Variables] | None] = {n: None for n in loop_nodes}

        # φ-노드 초기 in = 노드 snapshot
        for n in loop_nodes:
            if getattr(n, "fixpoint_evaluation_node", False):
                in_vars[n] = VariableEnv.copy_variables(getattr(n, "variables", {}) or {})

        # 헤드 in = 외부 preds join
        start_env = None
        for p in G.predecessors(head):
            start_env = VariableEnv.join_variables_simple(start_env, getattr(p, "variables", {}) or {})
        in_vars[head] = start_env or {}

        # ───────── widening pass ─────────
        W_MAX = 300
        WL = deque([head])
        while WL and max(visit_cnt.values(), default=0) < W_MAX:
            node = WL.popleft()
            visit_cnt[node] += 1

            out_old = out_vars[node]
            out_raw = self.transfer_function(node, in_vars[node])

            # ★ φ 스냅샷과 비교 → 첫 방문에도 즉시 widen 허용
            if getattr(node, "fixpoint_evaluation_node", False):
                prev_snapshot = getattr(node, "fixpoint_evaluation_node_vars", None)
                changed_vs_prev = (
                        prev_snapshot is not None and
                        not VariableEnv.variables_equal(prev_snapshot, out_raw)
                )
            else:
                changed_vs_prev = False

            need_widen = (
                    getattr(node, "fixpoint_evaluation_node", False) and
                    (visit_cnt[node] >= 2 or changed_vs_prev)
            )

            out_joined = (
                VariableEnv.join_variables_with_widening(out_old, out_raw)
                if need_widen else
                VariableEnv.join_variables_simple(out_old, out_raw)
            )

            if getattr(node, "fixpoint_evaluation_node", False):
                node.fixpoint_evaluation_node_vars = VariableEnv.copy_variables(out_joined)

            if VariableEnv.variables_equal(out_old, out_joined):
                out_vars[node] = out_joined
                continue
            out_vars[node] = out_joined

            # succ in 갱신 (간선 단위 pruning)
            for succ in G.successors(node):
                if succ not in loop_nodes:
                    continue
                flow = _edge_flow_from_node_out(node, succ, out_joined)
                if flow is None:
                    continue

                if getattr(succ, "fixpoint_evaluation_node", False):
                    prev_snapshot_succ = getattr(succ, "fixpoint_evaluation_node_vars", None)
                    changed_succ = (
                            prev_snapshot_succ is not None and
                            not VariableEnv.variables_equal(prev_snapshot_succ, flow)
                    )
                    succ_need_widen = (visit_cnt[succ] >= 2 or changed_succ)
                else:
                    succ_need_widen = False

                in_new = (
                    VariableEnv.join_variables_with_widening(in_vars[succ], flow)
                    if succ_need_widen else
                    VariableEnv.join_variables_simple(in_vars[succ], flow)
                )
                if not VariableEnv.variables_equal(in_vars[succ], in_new):
                    in_vars[succ] = VariableEnv.copy_variables(in_new)
                    WL.append(succ)

        # ───────── narrowing pass ─────────
        WL = deque(loop_nodes)
        N_MAX = 30
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

            tmp_out = self.transfer_function(node, in_vars[node])
            if getattr(node, "fixpoint_evaluation_node", False):
                narrowed = VariableEnv.narrow_variables(out_vars[node], tmp_out)
            else:
                narrowed = tmp_out

            if VariableEnv.variables_equal(out_vars[node], narrowed):
                continue
            out_vars[node] = narrowed

            for succ in G.successors(node):
                if succ in loop_nodes:
                    WL.append(succ)

        # 0) exit 노드
        exit_node = self.find_loop_exit_node(head)
        if not exit_node:
            raise ValueError("loop without exit-node")

        # 3) exit-env (pred별 edge 조건 반영 후 join)
        exit_env = None
        for p in G.predecessors(exit_node):
            src = out_vars.get(p) or getattr(p, "variables", {}) or {}
            flow = _edge_flow_from_node_out(p, exit_node, src)
            if flow is None:
                continue
            exit_env = VariableEnv.join_variables_simple(exit_env, flow)

        exit_node.variables = VariableEnv.copy_variables(exit_env or {})

        # diff 기록(loopDelta) — join(φ) 찾기 (선행자→없으면 루프 내부 φ로 폴백)
        preds_of_head = list(G.predecessors(head))
        join_nodes = [p for p in preds_of_head if getattr(p, "fixpoint_evaluation_node", False)]
        join = join_nodes[0] if join_nodes else next(
            (n for n in loop_nodes if getattr(n, "fixpoint_evaluation_node", False)), None
        )
        if join is not None:
            base_env = getattr(join, "join_baseline_env", None)
            changed = VariableEnv.diff_changed(base_env, exit_node.variables) if base_env else {}
            if changed:
                self.an.recorder.add_env_record(
                    line_no=getattr(join, "src_line", None),
                    stmt_type="loopDelta",
                    env=changed
                )

        return exit_node

    def interpret_function_cfg(self, fcfg: FunctionCFG, caller_env: dict[str, Variables] | None = None):
        an = self.an
        rt = self.runtime
        rec = self.rec

        # ─── ① 호출 이전 컨텍스트 백업 ─────────────────────────
        _old_func = an.current_target_function
        _old_fcfg = an.current_target_function_cfg

        # ─── ② 현재 해석 대상 함수로 설정 ─────────────────────
        an.current_target_function = fcfg.function_name
        an.current_target_function_cfg = fcfg

        # Recorder/reset
        rt._record_enabled = True
        an._seen_stmt_ids.clear()
        for blk in fcfg.graph.nodes:
            for st in blk.statements:
                ln = getattr(st, "src_line", None)
                if ln is not None and ln in an.analysis_per_line:
                    an.analysis_per_line[ln].clear()

        entry = fcfg.get_entry_node()
        (start_block,) = fcfg.graph.successors(entry)
        start_block.variables = VariableEnv.copy_variables(fcfg.related_variables)

        # caller_env → callee entry merge (동명 키 overwrite 허용)
        if caller_env is not None:
            for k, v in caller_env.items():
                start_block.variables[k] = v

        # ---------- helpers (★ 추가) ----------
        G = fcfg.graph

        def _is_sink(n: CFGNode) -> bool:
            if getattr(n, "function_exit_node", False): return True
            if getattr(n, "error_exit_node", False):    return True
            if getattr(n, "return_exit_node", False):   return True
            nm = getattr(n, "name", "")
            return nm in {"EXIT", "ERROR", "RETURN"}

        def _edge_env_from_pred(pred: CFGNode, succ: CFGNode):
            """선행자→후속 간선 라벨(True/False)에 맞춰 edge 단위 pruning & feasibility."""
            base = VariableEnv.copy_variables(getattr(pred, "variables", {}) or {})
            if getattr(pred, "condition_node", False):
                cond_expr = getattr(pred, "condition_expr", None)
                ed = G.get_edge_data(pred, succ, default=None)
                if cond_expr is not None and ed and "condition" in ed:
                    want_true = bool(ed["condition"])
                    self.ref.update_variables_with_condition(base, cond_expr, want_true)
                    if not rt._branch_feasible(base, cond_expr, want_true):
                        return None
            return base

        from collections import deque
        work = deque([start_block])
        visited: set[CFGNode] = set()
        return_values = []

        while work:
            node = work.popleft()
            if node in visited:
                continue
            visited.add(node)

            # preds join → node.variables  (★ 간선 라벨 기반 pruning 적용)
            preds = list(G.predecessors(node))
            if preds:
                joined = None
                for p in preds:
                    flow = _edge_env_from_pred(p, node)
                    if flow is None:
                        continue
                    joined = (VariableEnv.copy_variables(flow)
                              if joined is None else
                              VariableEnv.join_variables_simple(joined, flow))
                if joined is not None:
                    node.variables = joined

            cur_vars = node.variables
            node.evaluated = True

            # ───────── 조건 노드 ─────────
            if node.condition_node:
                condition_expr = node.condition_expr
                ln = getattr(node, "src_line", None)

                if node.condition_node_type in ["if", "else if"]:
                    true_succs = [s for s in G.successors(node) if G.edges[node, s].get('condition') is True]
                    false_succs = [s for s in G.successors(node) if G.edges[node, s].get('condition') is False]
                    if len(true_succs) != 1 or len(false_succs) != 1:
                        raise ValueError("if/else-if node must have exactly one true and one false successor.")

                    true_variables = VariableEnv.copy_variables(cur_vars)
                    false_variables = VariableEnv.copy_variables(cur_vars)
                    self.ref.update_variables_with_condition(true_variables, condition_expr, True)
                    self.ref.update_variables_with_condition(false_variables, condition_expr, False)

                    can_true = self._branch_feasible(true_variables, condition_expr, True)
                    can_false = self._branch_feasible(false_variables, condition_expr, False)

                    if not can_true and not can_false:
                        continue

                    if rt._record_enabled and ln is not None:
                        rec.add_env_record(ln, "branchTrue", true_variables)

                    t = true_succs[0]
                    f = false_succs[0]
                    if can_true:
                        t.variables = true_variables
                        work.append(t)
                    else:
                        self._set_bottom_env(t.variables)
                    if can_false:
                        f.variables = false_variables
                        work.append(f)
                    else:
                        self._set_bottom_env(f.variables)
                    continue

                elif node.condition_node_type in ["require", "assert"]:
                    # require/assert 는 True 경로만 진행 (False→ERROR)
                    (t,) = [s for s in G.successors(node) if G.edges[node, s].get('condition') is True]
                    true_variables = VariableEnv.copy_variables(cur_vars)
                    self.ref.update_variables_with_condition(true_variables, condition_expr, True)
                    can_true = self._branch_feasible(true_variables, condition_expr, True)

                    if ln is not None:
                        # 기록 키는 필요 시 구분 (원하면 assertTrue로 바꿔도 됨)
                        tag = "requireTrue" if node.condition_node_type == "require" else "assertTrue"
                        rec.add_env_record(ln, tag, true_variables)

                    if can_true:
                        t.variables = true_variables
                        work.append(t)
                    else:
                        self._set_bottom_env(t.variables)
                    continue

                elif node.condition_node_type in ["while", "for", "do_while"]:
                    # 고정점 내부에서 간선 단위 pruning 수행
                    exit_node = self.fixpoint(node)
                    succs = list(G.successors(exit_node))
                    # ★ 여러 후속 가능 → 모두 전파(싱크 제외)
                    for nxt in succs:
                        if _is_sink(nxt):  # 굳이 넣어도 무해하지만 비용 절감
                            continue
                        nxt.variables = VariableEnv.copy_variables(exit_node.variables)
                        work.append(nxt)
                    continue

                elif node.condition_node_type == "try":  # ★ 추가
                    # try 성공(True) / 실패(False) 모두 가능성 열어 둠 (pruning 없음)
                    t_succs = [s for s in G.successors(node) if G.edges[node, s].get('condition') is True]
                    f_succs = [s for s in G.successors(node) if G.edges[node, s].get('condition') is False]
                    for s in (t_succs + f_succs):
                        if _is_sink(s):  # 일반적으로 sink는 아님
                            continue
                        s.variables = VariableEnv.copy_variables(cur_vars)
                        work.append(s)
                    continue

                else:
                    raise ValueError(f"Unknown condition node type: {node.condition_node_type}")

            # for-increment 노드 (증감 전용 블록)
            elif getattr(node, "is_for_increment", False):
                for stmt in node.statements:
                    cur_vars = rt.update_statement_with_variables(stmt, cur_vars, return_values)
                for succ in G.successors(node):  # ★ 이미 다중 succ 허용
                    if _is_sink(succ):
                        continue
                    succ.variables = VariableEnv.copy_variables(node.variables)
                    work.append(succ)
                continue

            # 일반/φ/join/exit(루프) 블록 등
            else:
                for stmt in node.statements:
                    cur_vars = rt.update_statement_with_variables(stmt, cur_vars, return_values)
                    if "__STOP__" in return_values:
                        break

                succs = list(G.successors(node))
                # ★ 다중 succ 허용 + sink는 큐잉 생략
                for nxt in succs:
                    if _is_sink(nxt):
                        continue
                    nxt.variables = VariableEnv.copy_variables(cur_vars)
                    work.append(nxt)

        # EXIT 전 합류 및 named returns 동기화
        self._force_join_before_exit(fcfg)
        self._sync_named_return_vars(fcfg)

        # 컨텍스트 복원
        an.current_target_function = _old_func
        an.current_target_function_cfg = _old_fcfg

        # caller_env 로 역반영 (스토리지 구조체/배열은 객체 공유)
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

        # 반환값 결정 (기존 로직 유지)
        def _log_implicit_return(var_objs: list[Variables]):
            if not rt._record_enabled:
                return
            ln = self._last_executable_line(fcfg)
            if ln is None:
                return
            if len(var_objs) == 1:
                rec.record_return(line_no=ln, return_expr=None, return_val=var_objs[0].value, fn_cfg=fcfg)
            else:
                flat = {v.identifier: rec._serialize_val(v.value) for v in var_objs}
                rec.add_env_record(ln, "implicitReturn", flat)

        if len(return_values) == 0:
            if fcfg.return_vars:
                _log_implicit_return(fcfg.return_vars)
                rt._record_enabled = False
                if len(fcfg.return_vars) == 1:
                    return fcfg.return_vars[0].value
                else:
                    return [rv.value for rv in fcfg.return_vars]
            else:
                # ★ RETURN_EXIT에서 수집
                exit_retvals = list(fcfg.get_return_exit_node().return_vals.values())
                if exit_retvals:
                    joined = exit_retvals[0]
                    for v in exit_retvals[1:]:
                        joined = joined.join(v)
                    return joined
                return None

        elif len(return_values) == 1:
            rt._record_enabled = False
            return return_values[0]
        else:
            rt._record_enabled = False
            joined_ret = return_values[0]
            for rv in return_values[1:]:
                joined_ret = joined_ret.join(rv)
            return joined_ret

    def reinterpret_from(self, fcfg: "FunctionCFG", seed_or_seeds) -> None:
        """
        Change-driven 재해석. (이전과 동작 동일)
        - 조건 선행자: edge 라벨(True/False) 기준 prune
        - 비조건: pred.variables 사용
        - 루프 헤더: 필요시 fixpoint
        """
        G = fcfg.graph
        ref = self.ref
        rt  = self.runtime

        # ---------- helpers ----------
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

        def _branch_feasible(env, cond_expr, want_true):
            return rt._branch_feasible(env, cond_expr, want_true)

        def _edge_env_from_pred(pred, succ):
            base = VariableEnv.copy_variables(getattr(pred, "variables", {}) or {})
            if getattr(pred, "condition_node", False):
                cond_expr = getattr(pred, "condition_expr", None)
                ed = G.get_edge_data(pred, succ, default=None)
                if cond_expr is not None and ed and "condition" in ed:
                    want_true = bool(ed["condition"])
                    ref.update_variables_with_condition(base, cond_expr, want_true)
                    if not _branch_feasible(base, cond_expr, want_true):
                        return None
                return base
            return base

        def _compute_in(n):
            acc = None
            for p in G.predecessors(n):
                env_p = _edge_env_from_pred(p, n)
                if env_p is None:
                    continue
                acc = VariableEnv.join_variables_simple(acc, env_p)
            return acc or {}

        # (선택) seed 보정: 루프 본문이라면 헤더도 seed에 포함
        def _augment_seeds_with_loop_headers(seeds):
            out = list(seeds)
            for s in seeds:
                hdr = self.find_enclosing_loop_header(s, fcfg)
                if hdr is not None:
                    out.append(hdr)
            return list(dict.fromkeys(out))

        # (선택) seed 정규화: 지배 시드 제거
        def _dominant_seeds(seeds):
            seeds = list(dict.fromkeys(seeds))
            seed_set = set(seeds)
            dominated = set()
            for a in seeds:
                q = deque([a])
                seen = {a}
                while q:
                    u = q.popleft()
                    for v in G.successors(u):
                        if v in seen or _is_sink(v): continue
                        seen.add(v)
                        q.append(v)
                        if v in seed_set and v != a:
                            dominated.add(v)
            return [s for s in seeds if s not in dominated]

        # ---------- worklist init ----------
        seeds = list(seed_or_seeds) if isinstance(seed_or_seeds, (list, tuple, set)) else [seed_or_seeds]
        seeds = _augment_seeds_with_loop_headers(seeds)
        seeds = _dominant_seeds(seeds)

        WL = deque()
        in_queue = set()
        out_snapshot = {}

        for s in seeds:
            if not _is_sink(s) and s not in in_queue:
                WL.append(s)
                in_queue.add(s)

        # ---------- main loop ----------
        while WL:
            n = WL.popleft()
            in_queue.discard(n)

            in_env = _compute_in(n)

            # 2) loop head → fixpoint (false-exit이 바로 종료면 생략)
            if _is_loop_head(n):
                false_s = _false_succs(n)
                only_exit = (len(false_s) == 1 and _is_sink(false_s[0]))
                if not only_exit:
                    exit_node = self.fixpoint(n)
                    for s in G.successors(exit_node):
                        if not _is_sink(s) and s not in in_queue:
                            WL.append(s); in_queue.add(s)
                else:
                    for s in false_s:
                        if not _is_sink(s) and s not in in_queue:
                            WL.append(s); in_queue.add(s)
                continue

            # 3) 전이
            new_out = self.transfer_function(n, in_env)
            n.variables = VariableEnv.copy_variables(new_out)

            # 4) 변화 검출
            changed = not VariableEnv.variables_equal(out_snapshot.get(n), new_out)
            out_snapshot[n] = VariableEnv.copy_variables(new_out)

            # 5) 변화 있을 때만 후속 큐잉
            if changed:
                for s in G.successors(n):
                    if not _is_sink(s) and s not in in_queue:
                        WL.append(s); in_queue.add(s)

    def find_enclosing_loop_header(self, node: CFGNode, fcfg: "FunctionCFG") -> CFGNode | None:
        """역-DFS로 가장 가까운 while/for/do-while 헤더를 찾는다."""
        G = fcfg.graph
        q = deque([node])
        seen = {node}
        while q:
            u = q.popleft()
            for p in G.predecessors(u):
                if p in seen:
                    continue
                seen.add(p)
                if (getattr(p, "condition_node", False) and
                    getattr(p, "condition_node_type", None) in {"while", "for", "doWhile", "do_while"}):
                    return p
                q.append(p)
        return None

    def find_loop_exit_node(self, loop_node):
        exit_nodes = set()  # ← 1) set 으로 중복 차단
        visited = set()
        stack = [loop_node]

        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)

            for succ in self.an.current_target_function_cfg.graph.successors(cur):
                if succ == loop_node:
                    continue
                if not self.is_node_in_loop(succ, loop_node):
                    exit_nodes.add(succ)  # ← 2) add
                else:
                    stack.append(succ)

        if len(exit_nodes) != 1:
            raise ValueError("loop exit node not found or two many")

        return next(iter(exit_nodes))

    def is_node_in_loop(self, node, while_node):
        """
        주어진 노드가 while 루프 내에 속해 있는지 확인합니다.
        :param node: 확인할 노드
        :param while_node: while 루프의 조건 노드
        :return: True 또는 False
        """
        # while_node에서 시작하여 루프 내의 모든 노드를 수집하고, 그 안에 node가 있는지 확인
        if node.loop_exit_node:  # ← 한 줄로 끝
            return False
        return node in self.traverse_loop_nodes(while_node)

    def traverse_loop_nodes(self, loop_node):
        visited = set()
        stack = [loop_node]

        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)

            for succ in self.an.current_target_function_cfg.graph.successors(cur):
                # **모든** loop-exit 노드는 무조건 제외
                if succ.loop_exit_node:
                    continue
                stack.append(succ)
        return visited

    # =================================================================
    #  Branch feasibility
    # =================================================================
    def _branch_feasible(self, env: dict, cond: Expression, assume_true: bool) -> bool:
        r = self.eval.evaluate_expression(cond, env, None, None)

        # (a) BoolInterval — 확정 0/1 인지 확인
        if isinstance(r, BoolInterval):
            return (r.max_value == 1) if assume_true else (r.min_value == 0)

        # (b) 정수·주소 → bool 로 승격해 판단 (0 ↔ false)
        if VariableEnv.is_interval(r):
            as_bool = VariableEnv.convert_int_to_bool_interval(r)
            return (as_bool.max_value == 1) if assume_true else (as_bool.min_value == 0)

        # (c) 심벌릭 등 → “가능성 있음”
        return True

    def _set_bottom_env(self, env: dict[str, Variables]) -> None:
        for v in env.values():
            self._make_bottom(v)

    def _make_bottom(self, v: Variables) -> None:
        """
        주어진 변수 객체(모든 서브-타입 포함)를
        ‘도달 불가능 환경’용 ⊥ 값으로 재귀 초기화.
        """
        if isinstance(v, ArrayVariable):
            for elem in v.elements:
                self._make_bottom(elem)
            return

        if isinstance(v, StructVariable):
            for m in v.members.values():
                self._make_bottom(m)
            return

        if isinstance(v, MappingVariable):
            for mv in v.mapping.values():
                self._make_bottom(mv)
            return

        # elementary / enum leaf
        val = getattr(v, "value", None)
        if isinstance(val, UnsignedIntegerInterval):
            v.value = UnsignedIntegerInterval.bottom(val.type_length)
            return
        if isinstance(val, IntegerInterval):
            v.value = IntegerInterval.bottom(val.type_length)
            return
        if isinstance(val, BoolInterval):
            v.value = BoolInterval.bottom()
            return
        # 기타(string/bytes/심볼 등)
        v.value = None

    # =================================================================
    #  EXIT/returns 동기화
    # =================================================================
    def _force_join_before_exit(self, fcfg: FunctionCFG) -> None:
        """
        함수 EXIT 의 환경을, 모든 predecessor 의 환경을 join 하여 갱신.
        (과거 'leaf만 join' 방식보다 안전)
        """
        g = fcfg.graph
        exit_node = fcfg.get_exit_node()
        preds = list(g.predecessors(exit_node))

        joined_env: dict[str, Variables] = {}
        for p in preds:
            joined_env = VariableEnv.join_variables_simple(joined_env, getattr(p, "variables", {}) or {})

        exit_node.variables = joined_env

    def _sync_named_return_vars(self, fcfg: FunctionCFG) -> None:
        exit_env = fcfg.get_exit_node().variables
        for i, rv in enumerate(fcfg.return_vars or []):
            if rv.identifier in exit_env:
                src = exit_env[rv.identifier]
                if hasattr(rv, "value"):
                    rv.value = getattr(src, "value", src)
                else:
                    # Array/Struct 등은 객체 자체 공유 허용
                    fcfg.return_vars[i] = src

    # =================================================================
    #  Function body range & last line (brace_count → line_info 로 교체)
    # =================================================================
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
        line_info[ln]["cfg_nodes"] 에 entry 가 수록된 라인을 찾는다.
        (이전 brace_count 기반 구현 대체)
        """
        entry = fcfg.get_entry_node()
        for ln, info in (self.an.line_info or {}).items():
            nodes = []
            if isinstance(info.get("cfg_nodes"), list):
                nodes.extend(info["cfg_nodes"])
            elif info.get("cfg_node") is not None:  # 하위호환
                nodes.append(info["cfg_node"])
            if entry in nodes:
                return ln
        return None

    def _function_body_range(self, fcfg: FunctionCFG) -> tuple[int, int] | None:
        """
        line_info 의 open/close 카운트를 누적해
        함수 바디의 [시작, 끝] 라인 범위를 추정한다.
        """
        li = self.an.line_info or {}
        fn_start_ln = self._function_start_line(fcfg)
        if fn_start_ln is None:
            return None

        def _oc(ln: int) -> tuple[int, int]:
            info = li.get(ln, {})
            return int(info.get("open", 0)), int(info.get("close", 0))

        # 함수 선언 전까지의 brace balance
        start_balance = 0
        for ln in range(1, fn_start_ln):
            o, c = _oc(ln)
            start_balance += (o - c)

        body_start = None
        balance = start_balance
        max_ln = max(li.keys()) if li else fn_start_ln

        for ln in range(fn_start_ln, max_ln + 1):
            o, c = _oc(ln)
            balance += (o - c)

            # 함수 헤더 다음으로 balance가 +1 되는 지점의 '다음 라인'이 바디 시작
            if balance == start_balance + 1 and body_start is None:
                body_start = ln + 1

            # balance가 원래로 돌아오면 바디 종료 직전 라인이 끝
            if balance == start_balance and body_start is not None:
                return (body_start, ln - 1)
        return None