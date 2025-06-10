from Interpreter.Semantics import *
from collections import deque, defaultdict

class Engine:
    """
    – CFG work-list, widen / narrow, fix-point.
    – 실제 ‘한 줄 해석’은 Semantics 에게 위임.
    """

    def __init__(self, sem: Semantics):
        self.sems = sem

    def transfer_function(self, node: CFGNode,
                          in_vars: dict[str, Variables]) -> dict[str, Variables]:

        out_vars = self.copy_variables(in_vars)
        changed = False

        # ─ 1) 조건 노드 ───────────────────────────────────────
        if node.condition_node:
            if node.branch_node and not node.is_true_branch:
                preds = list(self.current_target_function_cfg.graph.predecessors(node))

                cond_node = next(
                    (p for p in preds if getattr(p, "condition_node", False)),
                    None  # ← 조건-노드가 없을 때는 None
                )
                self.update_variables_with_condition(out_vars,
                                                     cond_node.condition_expr,
                                                     node.is_true_branch)
            else:
                return out_vars

        # ─ 2) 일반/바디/증감 노드 ────────────────────────────
        elif not node.fixpoint_evaluation_node:
            if node.branch_node:
                preds = list(self.current_target_function_cfg.graph.predecessors(node))

                cond_node = next(
                    (p for p in preds if getattr(p, "condition_node", False)),
                    None  # ← 조건-노드가 없을 때는 None
                )
                self.update_variables_with_condition(out_vars,
                                                     cond_node.condition_expr,
                                                     node.is_true_branch)

            for stmt in node.statements:
                before = self.copy_variables(out_vars)  # 🟢 깊은 사본
                self.update_statement_with_variables(stmt, out_vars)
                if not self._env_equal(before, out_vars):  # 🟢 깊이 비교
                    changed = True
        # ─ 4) 결과 반환 ──────────────────────────────────────
        return out_vars if changed else in_vars

    def fixpoint(self, loop_condition_node: CFGNode) -> CFGNode:
        """
        loop_condition_node : while / for / do-while 의 condition CFGNode
        return              : 루프의 exit-node
        """

        # ──────────────────────────────────────────────────────────────
        def _need_widen(n: CFGNode, vc: dict[CFGNode, int]) -> bool:
            """φ-node 이고 두 번째 방문부터 widen."""
            return n.fixpoint_evaluation_node and vc[n] >= 2

        def _need_narrow(n: CFGNode) -> bool:
            """φ-node 인가? (헤드만 narrow)"""
            return n.fixpoint_evaluation_node

        # ──────────────────────────────────────────────────────────────

        # 0) exit-node
        exit_nodes = self.find_loop_exit_nodes(loop_condition_node)
        if not exit_nodes:
            raise ValueError("Loop without exit-node")
        if len(exit_nodes) > 1:
            print("[Warn] multiple exit-nodes – using the first one")
        exit_node = exit_nodes[0]

        # 1) 루프 내부 노드 집합
        loop_nodes: set[CFGNode] = self.traverse_loop_nodes(loop_condition_node)

        # 2) 자료구조
        visit_cnt: defaultdict[CFGNode, int] = defaultdict(int)
        in_vars: dict[CFGNode, dict | None] = {n: None for n in loop_nodes}
        out_vars: dict[CFGNode, dict | None] = {n: None for n in loop_nodes}

        for n in loop_nodes:
            if n.fixpoint_evaluation_node and in_vars[n] is None:
                in_vars[n] = self.copy_variables(n.variables)

        # ───── 초기 in (헤드의 in = 외부 predecessor join) ─────
        start_env = None
        for p in self.current_target_function_cfg.graph.predecessors(loop_condition_node):
            start_env = (self.join_variables_simple(start_env, p.variables)
                         if start_env else self.copy_variables(p.variables))
        in_vars[loop_condition_node] = start_env

        # ───────────────── 3-A. widening 패스 ─────────────────
        WL, W_MAX = deque([loop_condition_node]), 30
        while WL and (w_iter := visit_cnt[loop_condition_node]) < W_MAX:
            node = WL.popleft()
            visit_cnt[node] += 1

            out_old = out_vars[node]
            out_new = self.transfer_function(node, in_vars[node])

            # φ-node + 2회차 이상이면 widen, 그 외엔 join
            if _need_widen(node, visit_cnt):
                new_out = self.join_variables_with_widening(out_old, out_new)
            else:
                new_out = self.join_variables_simple(out_old, out_new)

            if node.fixpoint_evaluation_node:
                node.fixpoint_evaluation_node_vars = copy.deepcopy(new_out)

            if self.variables_equal(out_old, new_out):
                continue
            out_vars[node] = new_out

            # 후속 노드 갱신
            for succ in self.current_target_function_cfg.graph.successors(node):
                if succ not in loop_nodes:
                    continue

                if _need_widen(succ, visit_cnt):
                    in_new = self.join_variables_with_widening(in_vars[succ], new_out)
                else:
                    in_new = self.join_variables_simple(in_vars[succ], new_out)

                if not self.variables_equal(in_vars[succ], in_new):
                    in_vars[succ] = in_new
                    WL.append(succ)

        # ── 3-B. narrowing 패스 ────────────────────────────
        # ── 3-B. narrowing 패스 ───────────────────────────
        WL = deque([loop_condition_node])  # (1) seed 전부
        N_MAX = 30
        while WL and N_MAX:
            N_MAX -= 1
            node = WL.popleft()

            # 1) 새 in
            new_in = None
            for p in self.current_target_function_cfg.graph.predecessors(node):
                src = out_vars[p] if p in loop_nodes else p.variables
                new_in = self.join_variables_simple(new_in, src) if new_in else self.copy_variables(src)

            if not self.variables_equal(new_in, in_vars[node]):
                in_vars[node] = new_in

            # 2) transfer  ─ 항상 실행
            tmp_out = self.transfer_function(node, in_vars[node])

            if _need_narrow(node):
                narrowed = self.narrow_variables(out_vars[node], tmp_out)
                if self.variables_equal(out_vars[node], narrowed):
                    continue  # 변동 없으면 끝
            else:
                narrowed = tmp_out

            out_vars[node] = narrowed  # 갱신

            # 4) 후속 노드 enqueue
            for succ in self.current_target_function_cfg.graph.successors(node):
                if succ in loop_nodes:
                    WL.append(succ)

        # ── 4. exit-node 변수 반영 ─────────────────────────
        exit_env = None
        for p in self.current_target_function_cfg.graph.predecessors(exit_node):
            # 루프 안쪽 pred 는 out_vars 테이블에, 루프 밖 pred 는 CFG 노드에
            src = out_vars[p] if p in out_vars else p.variables
            exit_env = (self.join_variables_simple(exit_env, src)
                        if exit_env else self.copy_variables(src))

        # ① 조건·문장을 반영하기 위해 transfer_function 한 번 호출
        #    (loop-exit 노드는 branch_node=True, is_true_branch=False 로 지정되어 있으므로
        #     transfer_function 내부에서 ‘루프 조건의 부정’이 적용됩니다)
        exit_final = self.transfer_function(exit_node, exit_env or {})

        # ② 노드에 저장
        exit_node.variables = exit_final

        return exit_node