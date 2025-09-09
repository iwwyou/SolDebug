from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:                                         # 타입 검사 전용
     from Analyzer.ContractAnalyzer import ContractAnalyzer

from Domain.Variable import Variables, MappingVariable, ArrayVariable, StructVariable
from Domain.IR import Expression
from Domain.Interval import UnsignedIntegerInterval, IntegerInterval, BoolInterval

from Utils.CFG import CFGNode, FunctionCFG
from Utils.Helper import VariableEnv

from collections import defaultdict, deque

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

    def transfer_function(
            self,
            node: CFGNode,
            in_vars: Optional[dict[str, Variables]],
    ) -> dict[str, Variables]:
        """
        * 루프 헤더(φ-노드) -->  그대로 통과
        * 조건 노드            -->  변수 쓰기 없이 통과
        * branch dummy 노드    -->  조건식 pruning 후 통과
        * 일반 / incr / body   -->  statement 해석
        """
        env_in = in_vars or {}
        # ① φ-노드 : widening 대상이므로 그대로 반환
        if node.fixpoint_evaluation_node:
            node.variables = VariableEnv.copy_variables(env_in)
            return env_in  # 변화 없음

        # ② out 복사본 준비
        env_out = VariableEnv.copy_variables(env_in)

        # ③ branch dummy 인 경우 → 직전 condition 찾아 pruning
        if node.branch_node and not node.condition_node:
            preds = [
                p for p in self.an.current_target_function_cfg.graph.predecessors(node)
                if getattr(p, "condition_node", False)
            ]
            if preds:
                cond_node = preds[0]  # predecessor 는 하나뿐
                self.ref.update_variables_with_condition(
                    env_out,
                    cond_node.condition_expr,
                    node.is_true_branch,
                )

        # ④ statement 해석 (조건 노드는 statement 없음)
        if node.statements:
            for st in node.statements:
                self.runtime.update_statement_with_variables(st, env_out)

        # ⑤ 노드 env 동기화 후 반환
        node.variables = VariableEnv.copy_variables(env_out)
        return env_out

    def fixpoint(self, head: CFGNode) -> CFGNode:
        """
        head : while/for/do-while 의 조건-블록
        반환 : 루프를 빠져나가는 exit-블록
        """
        import pathlib, datetime
        import networkx as nx

        def dump_cfg(fcfg, tag=""):
            """
            FunctionCFG → 그래프 구조/조건/변수 요약을 DEBUG/outputs/ 아래로 저장
            * tag : "before_else", "after_else" 등 파일명에 꽂아 두면 비교가 쉬움
            """
            ts = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            base = pathlib.Path("DEBUG/outputs")
            base.mkdir(parents=True, exist_ok=True)

            G = fcfg.graph

            # ──────────────────────────────────────────────────────────
            # ③  pydot + PNG (가장 보기 편함)
            try:
                import pydot
                dot_path = base / f"{fcfg.function_name}_{tag}_{ts}.dot"
                png_path = base / f"{fcfg.function_name}_{tag}_{ts}.png"

                nx.nx_pydot.write_dot(G, dot_path)
                (graph,) = pydot.graph_from_dot_file(str(dot_path))
                graph.write_png(str(png_path))
                print(f"[CFG-DUMP] PNG saved → {png_path}")
                return
            except Exception as e:
                print(f"[CFG-DUMP] pydot unavailable ({e}); falling back to DOT/TXT")

            # ──────────────────────────────────────────────────────────
            # ②  DOT 파일만 (Graphviz 로 열어보기)
            try:
                dot_path = base / f"{fcfg.function_name}_{tag}_{ts}.dot"
                nx.nx_pydot.write_dot(G, dot_path)
                print(f"[CFG-DUMP] DOT saved  → {dot_path}")
                return
            except Exception:
                pass

            # ──────────────────────────────────────────────────────────
            # ①  콘솔 텍스트
            print("\n≡≡ CFG TEXT DUMP", tag, "≡≡")
            for n in G.nodes:
                succs = [
                    f"{s.name}({G[n][s].get('condition')})"
                    if G.has_edge(n, s) else s.name for s in G.successors(n)
                ]
                print(
                    f"· {n.name:<20} | succs={succs} | "
                    f"cond={n.condition_node_type or '-'} | src={getattr(n, 'src_line', None)}"
                )
            print("≡" * 50, "\n")

        #dump_cfg(self.an.current_target_function_cfg)

        # 1) loop node 집합 ---------------------------------------------
        loop_nodes: set[CFGNode] = self.traverse_loop_nodes(head)

        # 2) in/out 테이블 준비 ------------------------------------------
        visit_cnt: defaultdict[CFGNode, int] = defaultdict(int)
        in_vars: Dict[CFGNode, Optional[dict[str, Variables]]] = {
            n: None for n in loop_nodes
        }
        out_vars: Dict[CFGNode, Optional[dict[str, Variables]]] = {
            n: None for n in loop_nodes
        }

        # φ-노드의 초기 in = 노드 자체 snapshot
        for n in loop_nodes:
            if n.fixpoint_evaluation_node:
                in_vars[n] = VariableEnv.copy_variables(n.variables)

        # 헤드 in = 외부 preds join
        start_env = None
        for p in self.an.current_target_function_cfg.graph.predecessors(head):
            start_env = VariableEnv.join_variables_simple(start_env, p.variables)
        in_vars[head] = start_env or {}

        # ─────────────────── widening 패스 ────────────────────
        W_MAX = 300
        WL    = deque([head])            # ★ 수정: 모든 노드 seed
        while WL and max(visit_cnt.values(), default=0) < W_MAX:
            node = WL.popleft()
            visit_cnt[node] += 1

            out_old = out_vars[node]
            out_new = self.transfer_function(node, in_vars[node])

            need_widen = node.fixpoint_evaluation_node and visit_cnt[node] >= 2
            out_joined = (
                VariableEnv.join_variables_with_widening(out_old, out_new)
                if need_widen
                else VariableEnv.join_variables_simple(out_old, out_new)
            )

            if node.fixpoint_evaluation_node:
                node.fixpoint_evaluation_node_vars = VariableEnv.copy_variables(out_joined)

            if VariableEnv.variables_equal(out_old, out_joined):
                continue
            out_vars[node] = out_joined

            # succ 의 in 갱신
            for succ in self.an.current_target_function_cfg.graph.successors(node):
                if succ not in loop_nodes:
                    continue
                need_widen_succ = succ.fixpoint_evaluation_node and visit_cnt[succ] >= 2
                in_new = (
                    VariableEnv.join_variables_with_widening(in_vars[succ], out_joined)
                    if need_widen_succ
                    else VariableEnv.join_variables_simple(in_vars[succ], out_joined)
                )
                if not VariableEnv.variables_equal(in_vars[succ], in_new):
                    in_vars[succ] = VariableEnv.copy_variables(in_new)
                    WL.append(succ)

        # ─────────────────── narrowing 패스 ───────────────────
        WL    = deque(loop_nodes)      # 모든 φ-노드 seed
        N_MAX = 30
        while WL and N_MAX:
            N_MAX -= 1
            node = WL.popleft()

            # in 재계산 = preds out join
            new_in = None
            for p in self.an.current_target_function_cfg.graph.predecessors(node):
                src = out_vars.get(p) or p.variables
                new_in = VariableEnv.join_variables_simple(new_in, src)
            if not VariableEnv.variables_equal(in_vars[node], new_in):
                in_vars[node] = new_in

            tmp_out = self.transfer_function(node, new_in)
            if node.fixpoint_evaluation_node:
                narrowed = VariableEnv.narrow_variables(out_vars[node], tmp_out)
            else:
                narrowed = tmp_out

            if VariableEnv.variables_equal(out_vars[node], narrowed):
                continue
            out_vars[node] = narrowed

            for succ in self.an.current_target_function_cfg.graph.successors(node):
                if succ in loop_nodes:
                    WL.append(succ)

        # 0) exit 노드
        exit_node = self.find_loop_exit_node(head)
        if not exit_node:
            raise ValueError("loop without exit-node")

        # 3) exit-env 계산 (모든 exit 노드 join) -------------------------
        exit_env = None

        for p in self.an.current_target_function_cfg.graph.predecessors(exit_node):
            src = out_vars.get(p) or p.variables
            exit_env = VariableEnv.join_variables_simple(exit_env, src)

        # 🔹 exit_node 자체의 transfer 를 한 번 더 실행
        #     (for-cond False 브랜치 pruning 포함)
        exit_env = self.transfer_function(exit_node, exit_env or {})
        exit_node.variables = VariableEnv.copy_variables(exit_env)

        # (A) join 노드 잡기
        join = next(n for n in loop_nodes if n.fixpoint_evaluation_node)
        # (B) exit-env 구하기 (이미 계산됨)
        base_env = getattr(join, "join_baseline_env", None)

        # (C) diff
        changed = VariableEnv.diff_changed(base_env, exit_env) if base_env else {}

        # (D) 기록
        if changed :
            self.an.recorder.add_env_record(
                line_no=getattr(join, "src_line", None),
                stmt_type="loopDelta",
                env=changed
            )

        # 여러 exit 중 첫 번째 exit 블록을 반환 (노드를 따로 쓰려면 caller가 결정)
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

        from collections import deque
        work = deque([start_block])
        visited: set[CFGNode] = set()
        return_values = []

        while work:
            node = work.popleft()
            if node in visited:
                continue
            visited.add(node)

            # preds join → node.variables
            preds = list(fcfg.graph.predecessors(node))
            if preds:
                joined = None
                for p in preds:
                    if not p.variables:
                        continue
                    joined = (VariableEnv.copy_variables(p.variables)
                              if joined is None else
                              VariableEnv.join_variables_simple(joined, p.variables))
                if joined is not None:
                    node.variables = joined

            cur_vars = node.variables
            node.evaluated = True

            # ───────── 조건 노드 ─────────
            if node.condition_node:
                condition_expr = node.condition_expr
                ln = getattr(node, "src_line", None)

                if node.condition_node_type in ["if", "else if"]:
                    true_succs  = [s for s in fcfg.graph.successors(node) if fcfg.graph.edges[node, s].get('condition') is True]
                    false_succs = [s for s in fcfg.graph.successors(node) if fcfg.graph.edges[node, s].get('condition') is False]
                    if len(true_succs) != 1 or len(false_succs) != 1:
                        raise ValueError("if/else-if node must have exactly one true and one false successor.")

                    true_variables  = VariableEnv.copy_variables(cur_vars)
                    false_variables = VariableEnv.copy_variables(cur_vars)
                    self.ref.update_variables_with_condition(true_variables,  condition_expr, True)
                    self.ref.update_variables_with_condition(false_variables, condition_expr, False)

                    can_true  = rt._branch_feasible(true_variables,  condition_expr, True)
                    can_false = rt._branch_feasible(false_variables, condition_expr, False)

                    if not can_true and not can_false:
                        continue

                    if rt._record_enabled and ln is not None:
                        rec.add_env_record(ln, "branchTrue", true_variables)

                    t = true_succs[0]; f = false_succs[0]
                    if can_true:
                        t.variables = true_variables;  work.append(t)
                    else:
                        rt._set_bottom_env(t.variables)
                    if can_false:
                        f.variables = false_variables; work.append(f)
                    else:
                        rt._set_bottom_env(f.variables)
                    continue

                elif node.condition_node_type in ["require", "assert"]:
                    (t,) = [s for s in fcfg.graph.successors(node) if fcfg.graph.edges[node, s].get('condition') is True]
                    true_variables = VariableEnv.copy_variables(cur_vars)
                    self.ref.update_variables_with_condition(true_variables, condition_expr, True)
                    can_true = rt._branch_feasible(true_variables, condition_expr, True)
                    if ln is not None:
                        rec.add_env_record(ln, "requireTrue", true_variables)
                    if can_true:
                        t.variables = true_variables; work.append(t)
                    else:
                        rt._set_bottom_env(t.variables)
                    continue

                elif node.condition_node_type in ["while", "for", "do_while"]:
                    exit_node = self.fixpoint(node)
                    succs = list(fcfg.graph.successors(exit_node))
                    if len(succs) == 1:
                        nxt = succs[0]
                        nxt.variables = VariableEnv.copy_variables(exit_node.variables)
                        work.append(nxt)
                    elif len(succs) == 0:
                        pass
                    else:
                        raise ValueError("while exit node must have exactly one successor.")
                    continue

                elif node.fixpoint_evaluation_node:
                    continue

                else:
                    raise ValueError(f"Unknown condition node type: {node.condition_node_type}")

            # for-increment 노드
            elif node.is_for_increment:
                for stmt in node.statements:
                    cur_vars = rt.update_statement_with_variables(stmt, cur_vars, return_values)
                for succ in fcfg.graph.successors(node):
                    succ.variables = VariableEnv.copy_variables(node.variables)
                    work.append(succ)
                continue

            # 일반 블록
            else:
                for stmt in node.statements:
                    cur_vars = rt.update_statement_with_variables(stmt, cur_vars, return_values)
                    if "__STOP__" in return_values:
                        break

                succs = list(fcfg.graph.successors(node))
                if len(succs) == 1:
                    nxt = succs[0]
                    nxt.variables = VariableEnv.copy_variables(cur_vars)
                    work.append(nxt)
                elif len(succs) > 1:
                    raise ValueError("Non-condition, non-join node should not have multiple successors.")

        # EXIT 전 합류 및 named returns 동기화
        rt._force_join_before_exit(fcfg)
        rt._sync_named_return_vars(fcfg)

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

        # 반환값 결정
        def _log_implicit_return(var_objs: list[Variables]):
            if not rt._record_enabled:
                return
            ln = rt._last_executable_line(fcfg)
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
                exit_retvals = list(fcfg.get_exit_node().return_vals.values())
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