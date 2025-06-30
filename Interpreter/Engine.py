from __future__ import annotations

from typing import TYPE_CHECKING, Dict, Optional

if TYPE_CHECKING:                                         # 타입 검사 전용
     from Analyzer.ContractAnalyzer import ContractAnalyzer

from Domain.Variable import Variables

from Utils.CFG import CFGNode
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