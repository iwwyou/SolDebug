from __future__ import annotations

# Analyzer/CFGBuilder.py
from Utils.CFG import CFGNode, FunctionCFG
from Utils.Helper import VariableEnv
from Domain.IR import Expression
from Domain.Variable import Variables

from typing import TYPE_CHECKING

if TYPE_CHECKING:                                         # 타입 검사 전용
     from Analyzer.ContractAnalyzer import ContractAnalyzer

class DynamicCFGBuilder:
    def __init__(self, an: "ContractAnalyzer"):
        self.an = an                    # Engine 을 새로 만들지 않습니다.

    @property
    def eng(self):
        return self.an.engine

    @staticmethod
    def splice_modifier(
            fn_cfg: FunctionCFG,  # 호출 중인 함수-CFG
            modifier_cfg: FunctionCFG,  # StaticCFGFactory 가 만든 원본
            prefix: str  # ex) "onlyOwner"
    ) -> None:
        """
        * modifier_cfg 의 노드·엣지를 얕은 복사(pfx 붙여서) → fn_cfg.graph 에 삽입
        * placeholder 노드를 함수 ENTRY/EXIT 와 연결
        """
        g_fn, g_mod = fn_cfg.graph, modifier_cfg.graph
        node_map: dict[CFGNode, CFGNode] = {}

        # 1) 노드 복사 (+ prefix)
        for n in g_mod.nodes:
            clone = CFGNode(f"{prefix}::{n.name}")
            clone.variables = VariableEnv.copy_variables(getattr(n, "variables", {}))
            node_map[n] = clone
            g_fn.add_node(clone)

        # 2) 엣지 복사
        for u, v in g_mod.edges:
            g_fn.add_edge(node_map[u], node_map[v])

        # 3) placeholder 처리
        entry = fn_cfg.get_entry_node()
        exit_ = fn_cfg.get_exit_node()

        for orig in g_mod.nodes:
            if orig.name.startswith("MOD_PLACEHOLDER"):
                ph = node_map[orig]
                preds = list(g_fn.predecessors(ph))
                succs = list(g_fn.successors(ph))
                g_fn.remove_node(ph)

                for p in preds:
                    g_fn.add_edge(p, entry)
                for s in succs:
                    g_fn.add_edge(exit_, s)

    def build_variable_declaration(
            self,
            *,
            cur_block: CFGNode,
            var_obj,
            type_obj,
            init_expr,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict
    ) -> CFGNode:
        """
        Create a new statement block for variable declaration.
        New strategy: Always create a new block between cur_block and its successors.
        """
        # 1) Create new statement block
        new_block = self.insert_new_statement_block(
            pred_block=cur_block,
            fcfg=fcfg,
            line_no=line_no,
            line_info=line_info,
            tag="VarDecl"
        )

        # 2) Add variable and statement to the new block
        new_block.variables[var_obj.identifier] = var_obj
        new_block.add_variable_declaration_statement(
            type_obj, var_obj.identifier, init_expr, line_no
        )

        # 3) Add to function-scope variable table
        fcfg.add_related_variable(var_obj)
        
        return new_block

    def build_assignment_statement(
            self,
            *,
            cur_block: CFGNode,
            expr: Expression,  # a = b, a[i] += 1 …
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> CFGNode:
        """
        Create a new statement block for assignment.
        New strategy: Always create a new block between cur_block and its successors.
        """
        # 1) Create new statement block
        new_block = self.insert_new_statement_block(
            pred_block=cur_block,
            fcfg=fcfg,
            line_no=line_no,
            line_info=line_info,
            tag="Assign"
        )

        # 2) Add statement to the new block
        new_block.add_assign_statement(expr.left, expr.operator, expr.right, line_no)
        
        return new_block

    def build_unary_statement(
            self,
            *,
            cur_block: CFGNode,
            expr: Expression,  # ++x  /  delete y 등
            op_token: str,  # '++' / '--' / 'delete'
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> CFGNode:
        """
        Create a new statement block for unary operations.
        New strategy: Always create a new block between cur_block and its successors.
        """
        # 1) Create new statement block
        new_block = self.insert_new_statement_block(
            pred_block=cur_block,
            fcfg=fcfg,
            line_no=line_no,
            line_info=line_info,
            tag="Unary"
        )

        # 2) Add statement to the new block
        new_block.add_unary_statement(expr, op_token, line_no)
        
        return new_block

    def build_function_call_statement(
        self,
        *,
        cur_block: CFGNode,
        expr: Expression,          # foo(a,b)   전체 Expression
        line_no: int,
        fcfg: FunctionCFG,
        line_info: dict,
    ) -> CFGNode:
        """
        Create a new statement block for function call.
        New strategy: Always create a new block between cur_block and its successors.
        """
        # 1) Create new statement block
        new_block = self.insert_new_statement_block(
            pred_block=cur_block,
            fcfg=fcfg,
            line_no=line_no,
            line_info=line_info,
            tag="FuncCall"
        )

        # 2) Add function call statement to the new block
        new_block.add_function_call_statement(expr, line_no)

        # 3) Update FCG
        fcfg.update_block(new_block)

        return new_block

    def build_if_statement(
            self,
            *,
            cur_block: CFGNode,
            condition_expr: Expression,
            true_env: dict[str, Variables],
            false_env: dict[str, Variables],
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
            end_line: int | None = None,  # 있으면 거기도 매핑해도 됨 (선택)
    ) -> CFGNode:
        G = fcfg.graph
        old_succs = list(G.successors(cur_block))
        for s in old_succs:
            G.remove_edge(cur_block, s)

        cond = CFGNode(f"if_condition_{line_no}", condition_node=True,
                       condition_node_type="if", src_line=line_no, is_loop_body=cur_block.is_loop_body)
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(cur_block.variables)

        t_blk = CFGNode(f"if_true_{line_no}", branch_node=True, is_true_branch=True, src_line=line_no,
                        is_loop_body=cur_block.is_loop_body)
        t_blk.variables = VariableEnv.copy_variables(true_env)

        f_blk = CFGNode(f"if_false_{line_no}", branch_node=True, is_true_branch=False, src_line=line_no,
                        is_loop_body=cur_block.is_loop_body)
        f_blk.variables = VariableEnv.copy_variables(false_env)

        join_env = VariableEnv.join_variables_simple(true_env, false_env)
        join = CFGNode(f"if_join_{line_no}", join_point_node=True, src_line=line_no,
                       is_loop_body=cur_block.is_loop_body)
        join.variables = VariableEnv.copy_variables(join_env)

        for n in (cond, t_blk, f_blk, join):
            G.add_node(n)

        G.add_edge(cur_block, cond)
        G.add_edge(cond, t_blk, condition=True)
        G.add_edge(cond, f_blk, condition=False)
        G.add_edge(t_blk, join)
        G.add_edge(f_blk, join)
        for s in old_succs:
            G.add_edge(join, s)

        # line_info: start line에는 cond만, end line에는 join만
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cond)

        # end_line에 join 추가
        if end_line is not None:
            bc_end = line_info.setdefault(end_line, {"open": 0, "close": 0, "cfg_nodes": []})
            bc_end["cfg_nodes"].append(join)

        return join

    def build_else_if_statement(
            self,
            *,
            prev_cond: CFGNode,
            outer_join: CFGNode | None,  # ★ 추가: get_current_block에서 전달받음
            condition_expr: Expression,
            false_base_env: dict[str, Variables],  # prev False 분기 기본 env
            true_env: dict[str, Variables],
            false_env: dict[str, Variables],
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
            end_line: int | None = None,
    ) -> CFGNode:
        G = fcfg.graph

        # ① 이전 False edge 제거
        for s in list(G.successors(prev_cond)):
            if G.edges[prev_cond, s].get("condition") is False:
                G.remove_edge(prev_cond, s)
                if len(list(G.predecessors(s))) == 0:
                    for nxt in list(G.successors(s)):
                        G.remove_edge(s, nxt)
                    G.remove_node(s)
                break

        # ② 새 cond / t / f / local-join
        cond = CFGNode(f"else_if_condition_{line_no}", condition_node=True,
                       condition_node_type="else if", src_line=line_no,
                       is_loop_body=prev_cond.is_loop_body)
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(false_base_env)

        t_blk = CFGNode(f"else_if_true_{line_no}", branch_node=True, is_true_branch=True, src_line=line_no,
                        is_loop_body=prev_cond.is_loop_body)
        t_blk.variables = VariableEnv.copy_variables(true_env)

        f_blk = CFGNode(f"else_if_false_{line_no}", branch_node=True, is_true_branch=False, src_line=line_no,
                        is_loop_body=prev_cond.is_loop_body)
        f_blk.variables = VariableEnv.copy_variables(false_env)

        local_join_env = VariableEnv.join_variables_simple(true_env, false_env)
        local_join = CFGNode(f"else_if_join_{line_no}", join_point_node=True, src_line=line_no,
                             is_loop_body=prev_cond.is_loop_body)
        local_join.variables = VariableEnv.copy_variables(local_join_env)

        for n in (cond, t_blk, f_blk, local_join):
            G.add_node(n)

        G.add_edge(prev_cond, cond, condition=False)
        G.add_edge(cond, t_blk, condition=True)
        G.add_edge(cond, f_blk, condition=False)
        G.add_edge(t_blk, local_join)
        G.add_edge(f_blk, local_join)

        # ③ outer-join: 이미 get_current_block에서 찾아서 전달받음
        if outer_join is None:
            raise ValueError("else-if: outer join not found (passed from get_current_block)")

        G.add_edge(local_join, outer_join)

        # ④ outer join env 재계산(모든 preds join)
        new_outer_env = None
        for p in G.predecessors(outer_join):
            new_outer_env = VariableEnv.join_variables_simple(new_outer_env, getattr(p, "variables", {}) or {})
        outer_join.variables = VariableEnv.copy_variables(new_outer_env or {})

        # ⑤ line_info: start line에는 cond만, end line에는 local_join만
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cond)

        if end_line is not None:
            bc_end = line_info.setdefault(end_line, {"open": 0, "close": 0, "cfg_nodes": []})
            bc_end["cfg_nodes"].append(local_join)

        return local_join

    def build_else_statement(
            self,
            *,
            cond_node: CFGNode,
            outer_join: CFGNode | None,  # ★ 추가: get_current_block에서 전달받음
            else_env: dict[str, Variables],
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
            end_line: int | None = None,
    ) -> CFGNode:
        G = fcfg.graph

        # ① 기존 False successor 제거(+고아 정리)
        old_false = None
        for s in list(G.successors(cond_node)):
            if G.edges[cond_node, s].get("condition") is False:
                old_false = s
                G.remove_edge(cond_node, s)
                break
        if old_false is not None and len(list(G.predecessors(old_false))) == 0:
            for nxt in list(G.successors(old_false)):
                G.remove_edge(old_false, nxt)
            G.remove_node(old_false)

        # ② target-join: get_current_block에서 전달받은 것을 우선 사용
        target_join = outer_join
        if target_join is None:
            # fallback: 그래프 기반 검색
            target_join = self._outer_join_from_graph(cond_node, fcfg)
        if target_join is None:
            raise ValueError("else: target join not found (passed from get_current_block)")

        # ③ else 블록 생성 및 연결
        else_blk = CFGNode(f"else_block_{line_no}", branch_node=True, is_true_branch=False, src_line=line_no
                           ,is_loop_body=cond_node.is_loop_body)
        else_blk.variables = VariableEnv.copy_variables(else_env)

        G.add_node(else_blk)
        G.add_edge(cond_node, else_blk, condition=False)
        G.add_edge(else_blk, target_join)

        # ④ target join env 재계산
        new_env = None
        for p in G.predecessors(target_join):
            new_env = VariableEnv.join_variables_simple(new_env, getattr(p, "variables", {}) or {})
        target_join.variables = VariableEnv.copy_variables(new_env or {})

        # ⑤ line_info
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(else_blk)
        if end_line is not None:
            bc_end = line_info.setdefault(end_line, {"open": 0, "close": 0, "cfg_nodes": []})
            bc_end["cfg_nodes"].append(target_join)

        return target_join

    # DynamicCFGBuilder.py (시그니처/본문/리턴 변경)
    def build_while_statement(
            self,
            *,
            cur_block: CFGNode,
            condition_expr: Expression,
            join_env: dict[str, Variables],
            true_env: dict[str, Variables],
            false_env: dict[str, Variables],
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
            end_line: int | None = None,  # ★ 추가: 루프 끝 라인
    ) -> CFGNode:  # ★ 변경: exit 노드 반환
        """
        cur_block ─▶ join ─▶ cond ─▶ true(body) ───┐
                              │                    │
                              └──▶ false(exit) ────┘
        """

        G = fcfg.graph

        # ── ① join-노드 --------------------------------------------------
        join = CFGNode(f"while_join_{line_no}", fixpoint_evaluation_node=True)
        join.variables = VariableEnv.copy_variables(join_env)
        join.join_baseline_env = VariableEnv.copy_variables(join_env)
        join.fixpoint_evaluation_node_vars = VariableEnv.copy_variables(join_env)
        G.add_node(join)

        # cur_block → join
        old_succs = list(G.successors(cur_block))
        for s in old_succs:
            G.remove_edge(cur_block, s)
        G.add_edge(cur_block, join)

        # ── ② condition-노드 --------------------------------------------
        cond = CFGNode(
            f"while_cond_{line_no}",
            condition_node=True,
            condition_node_type="while",
            src_line=line_no
        )
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(join.variables)
        G.add_node(cond)
        G.add_edge(join, cond)

        # ── ③ body / exit 블록 ------------------------------------------
        body = CFGNode(f"while_body_{line_no}", branch_node=True, is_true_branch=True)
        body.is_loop_body = True
        body.variables = VariableEnv.copy_variables(true_env)

        exit_ = CFGNode(
            f"while_exit_{line_no}",
            branch_node=True,
            is_true_branch=False,
            loop_exit_node=True,
            src_line=(end_line if end_line is not None else line_no)  # ★ end_line 반영
        )
        exit_.variables = VariableEnv.copy_variables(false_env)

        G.add_nodes_from([body, exit_])
        G.add_edge(cond, body, condition=True)
        G.add_edge(cond, exit_, condition=False)

        # body → join (back-edge)
        G.add_edge(body, join)

        # exit_ → 이전 cur_block successors
        for s in old_succs:
            G.add_edge(exit_, s)

        # ── ④ line_info ------------------------------------------------
        # 시작 라인: 조건 노드만 매핑
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cond)

        # 끝 라인: loop-exit 노드만 매핑
        if end_line is not None:
            bc_end = line_info.setdefault(end_line, {"open": 0, "close": 0, "cfg_nodes": []})
            bc_end["cfg_nodes"].append(exit_)

        return exit_  # ★ seed 용으로 exit 반환

    # DynamicCFGBuilder.py (시그니처/본문/리턴 변경)
    def build_for_statement(
            self,
            *,
            cur_block: CFGNode,
            init_node: CFGNode | None,
            join_env: dict[str, Variables],
            cond_expr: Expression | None,
            true_env: dict[str, Variables],
            false_env: dict[str, Variables],
            incr_node: CFGNode | None,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
            end_line: int | None = None,  # ★ 추가: 루프 끝 라인
    ) -> CFGNode:  # ★ 변경: exit 노드 반환
        """
        pre ─▶ [init] ─▶ join ─▶ cond ─▶ body ─▶ incr
                               │         ▲        │
                               └─────────┘        │
                                         └────────┘
        """
        from typing import cast, Optional

        G = fcfg.graph
        pre = cur_block

        funcExit = None
        for succ in list(G.successors(pre)):
            if succ.name == "EXIT":
                funcExit = succ
                G.remove_edge(pre, succ)
                break

        # ── ① join ------------------------------------------------------
        join = CFGNode(f"for_join_{line_no}", fixpoint_evaluation_node=True)
        join.variables = VariableEnv.copy_variables(join_env)
        join.join_baseline_env = VariableEnv.copy_variables(join_env)
        join.fixpoint_evaluation_node_vars = VariableEnv.copy_variables(join_env)

        # ── ② condition -------------------------------------------------
        cond = CFGNode(
            f"for_cond_{line_no}",
            condition_node=True,
            condition_node_type="for",
            src_line=line_no
        )
        cond.condition_expr = cond_expr
        cond.variables = VariableEnv.copy_variables(join_env)

        # ── ③ body & exit ----------------------------------------------
        body = CFGNode(f"for_body_{line_no}", branch_node=True, is_true_branch=True)
        body.is_loop_body = True
        body.variables = VariableEnv.copy_variables(true_env)

        exit_ = CFGNode(
            f"for_exit_{line_no}",
            branch_node=True,
            is_true_branch=False,
            loop_exit_node=True,
            src_line=(end_line if end_line is not None else line_no)  # ★ end_line 반영
        )
        exit_.variables = VariableEnv.copy_variables(false_env)

        # ── ④ 그래프 ----------------------------------------------------
        for n in (join, cond, body, exit_):
            G.add_node(n)
        if init_node:
            G.add_node(init_node)
        if incr_node:
            G.add_node(incr_node)

        # pre → init? join?
        if init_node:
            G.add_edge(pre, init_node)
            G.add_edge(init_node, join)
        else:
            G.add_edge(pre, join)

        # join → cond
        G.add_edge(join, cond)

        # cond True/False
        G.add_edge(cond, body, condition=True)
        G.add_edge(cond, exit_, condition=False)

        # body → incr
        G.add_edge(body, incr_node)
        G.add_edge(incr_node, join)

        # exit_ → 함수 EXIT (있으면)
        if funcExit:
            G.add_edge(exit_, funcExit)

        # ── ⑤ line_info ------------------------------------------------
        # 시작 라인: 조건 노드만 매핑
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cond)

        # 끝 라인: loop-exit 노드만 매핑
        if end_line is not None:
            bc_end = line_info.setdefault(end_line, {"open": 0, "close": 0, "cfg_nodes": []})
            bc_end["cfg_nodes"].append(exit_)

        return exit_  # ★ seed 용으로 exit 반환

    def build_continue_statement(
            self,
            *,
            cur_block: CFGNode,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> CFGNode:  # 반환: 해당 루프의 loop-exit 노드 (seed 용)

        G = fcfg.graph

        # 1) pred(cur_block)과 그 후속 사이에 새 블록 삽입
        new_block = self.insert_new_statement_block(
            pred_block=cur_block,
            fcfg=fcfg,
            line_no=line_no,
            line_info=line_info,
            tag="Continue"
        )
        # 2) 새 블록에 statement 추가
        new_block.add_continue_statement(line_no)

        # 3) join(φ) 찾기 → new_block 의 모든 후속을 제거하고 φ로 재배선
        join = self.find_loop_join(new_block, fcfg)
        if join is None:
            raise ValueError("continue: loop join(fixpoint) node not found.")

        old_succs = list(G.successors(new_block))  # insert가 붙여 놓은 원래 후속들
        for s in old_succs:
            G.remove_edge(new_block, s)
        G.add_edge(new_block, join)

        # 4) loop-exit 찾기(헤더 False-분기, loop_exit_node=True)
        cond = self.find_loop_condition(new_block, fcfg)
        if cond is None:
            raise ValueError("continue: loop condition node not found.")

        exit_node = None
        for s in G.successors(cond):
            if G[cond][s].get("condition") is False and getattr(s, "loop_exit_node", False):
                exit_node = s
                break
        if exit_node is None:
            raise ValueError("continue: loop exit node not found.")

        # line_info 는 insert_new_statement_block 에서 이미 추가됨
        return exit_node  # seed

    def build_return_statement(
            self,
            *,
            cur_block: CFGNode,
            return_expr: Expression | None,
            return_val,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> list[CFGNode]:  # 반환: 재배선 전 ‘원래 후속’(seed 용)

        G = fcfg.graph

        # 1) 새 블록 삽입
        new_block = self.insert_new_statement_block(
            pred_block=cur_block,
            fcfg=fcfg,
            line_no=line_no,
            line_info=line_info,
            tag="Return"
        )
        # 2) statement 추가
        new_block.add_return_statement(return_expr, line_no)

        # 3) seed 용으로 현재(new_block) 후속 = “원래 cur_block 의 후속” 확보
        old_succs = list(G.successors(new_block))

        # 4) RETURN_EXIT 로 재배선
        return_exit_n = fcfg.get_return_exit_node()
        for s in old_succs:
            G.remove_edge(new_block, s)
        G.add_edge(new_block, return_exit_n)

        # 5) 반환 값 기록(RETURN_EXIT에)
        return_exit_n.return_vals[line_no] = return_val

        # line_info 는 insert 헬퍼가 이미 등록
        return old_succs  # seed

    def build_break_statement(
            self,
            *,
            cur_block: CFGNode,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> CFGNode:  # 반환: loop-exit (seed 용)

        G = fcfg.graph

        # 1) 새 블록 삽입
        new_block = self.insert_new_statement_block(
            pred_block=cur_block,
            fcfg=fcfg,
            line_no=line_no,
            line_info=line_info,
            tag="Break"
        )
        # 2) statement 추가
        new_block.add_break_statement(line_no)

        # 3) loop-exit 찾기
        cond = self.find_loop_condition(new_block, fcfg)
        if cond is None:
            raise ValueError("break: loop condition node not found.")

        exit_node = None
        for succ in G.successors(cond):
            if (G[cond][succ].get("condition") is False) and getattr(succ, "loop_exit_node", False):
                exit_node = succ
                break
        if exit_node is None:
            raise ValueError("break: loop exit node not found.")

        # 4) new_block 의 기본 후속 제거 → loop-exit 으로 재배선
        old_succs = list(G.successors(new_block))
        for s in old_succs:
            G.remove_edge(new_block, s)
        G.add_edge(new_block, exit_node)

        return exit_node  # seed

    def build_revert_statement(
            self,
            *,
            cur_block: CFGNode,
            revert_id: str | None,
            string_literal: str | None,
            call_args: list[Expression] | None,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> list[CFGNode]:  # ★ 변경: 이전 succ 들을 반환

        # ① statement
        cur_block.add_revert_statement(revert_id, string_literal, call_args, line_no)

        # ★ seed 용으로 ‘재배선 전’ succ 보관
        g = fcfg.graph
        old_succs = list(g.successors(cur_block))

        # ② edge --> ERROR_EXIT
        error_exit_n = fcfg.get_error_exit_node()
        for s in old_succs:
            g.remove_edge(cur_block, s)
        g.add_edge(cur_block, error_exit_n)

        # ③ 데이터-플로우
        fcfg.update_block(cur_block)

        # ④ line_info
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cur_block)

        return old_succs  # ★ seed

    def build_require_statement(
            self,
            *,
            cur_block: CFGNode,
            condition_expr: Expression,
            true_env: dict[str, Variables],
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> list[CFGNode]:  # ★ 변경: true-분기 succ 들 반환

        G = fcfg.graph

        # ── 조건 노드
        cond = CFGNode(
            name=f"require_condition_{line_no}",
            condition_node=True,
            condition_node_type="require",
            src_line=line_no,
            is_loop_body=cur_block.is_loop_body
        )
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(cur_block.variables)

        # ── True 블록
        t_blk = CFGNode(
            name=f"require_true_{line_no}",
            branch_node=True,
            is_true_branch=True,
            src_line=line_no,
            is_loop_body=cur_block.is_loop_body
        )
        t_blk.variables = true_env

        # ── 재배선 (old_succ 보관)
        old_succ = list(G.successors(cur_block))
        for s in old_succ:
            G.remove_edge(cur_block, s)

        G.add_node(cond)
        G.add_edge(cur_block, cond)

        # False → ERROR
        error_exit_n = fcfg.get_error_exit_node()
        G.add_edge(cond, error_exit_n, condition=False)

        # True → t_blk
        G.add_node(t_blk)
        G.add_edge(cond, t_blk, condition=True)

        # t_blk → 원래 succ (없으면 EXIT)
        true_succs = old_succ if old_succ else [fcfg.get_exit_node()]
        for s in true_succs:
            G.add_edge(t_blk, s)

        # 데이터-플로우
        fcfg.update_block(cur_block)

        # line_info
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cond)

        # ★ seed: True 분기가 향하는 후속 노드들
        #  (EXIT는 sink라 seed에 넣어도 자동 필터링됨)
        return true_succs

    def build_assert_statement(
            self,
            *,
            cur_block: CFGNode,
            condition_expr: Expression,
            true_env: dict[str, Variables],
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> list[CFGNode]:  # ★ 변경: true-분기 succ 들 반환

        G = fcfg.graph

        # ── 조건 노드
        cond = CFGNode(
            name=f"assert_condition_{line_no}",
            condition_node=True,
            condition_node_type="assert",
            src_line=line_no,
            is_loop_body=cur_block.is_loop_body
        )
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(cur_block.variables)

        # ── True 블록
        t_blk = CFGNode(
            name=f"assert_true_{line_no}",
            branch_node=True,
            is_true_branch=True,
            src_line=line_no,
            is_loop_body=cur_block.is_loop_body
        )
        t_blk.variables = true_env

        # ── 재배선 (old_succ 보관)
        old_succ = list(G.successors(cur_block))
        for s in old_succ:
            G.remove_edge(cur_block, s)

        G.add_node(cond)
        G.add_edge(cur_block, cond)

        # False → ERROR
        exit_n = fcfg.get_error_exit_node()
        G.add_edge(cond, exit_n, condition=False)

        # True → t_blk
        G.add_node(t_blk)
        G.add_edge(cond, t_blk, condition=True)

        # t_blk → 원래 succ (없으면 EXIT)
        true_succs = old_succ if old_succ else [fcfg.get_exit_node()]
        for s in true_succs:
            G.add_edge(t_blk, s)

        # 데이터-플로우, line_info
        fcfg.update_block(cur_block)
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cond)

        return true_succs  # ★ seed

    def build_modifier_placeholder(
            self,
            *,
            cur_block: CFGNode,
            fcfg: FunctionCFG,
            line_no: int,
            line_info: dict,
    ) -> None:
        """
        • 현재 modifier-CFG에서 식별자 ‘_’(place-holder)를 만나면
          =⇒ 새로운 CFGNode("MOD_PLACEHOLDER_n") 를 cur_block 뒤에 삽입.

        cur_block ─▶ placeholder ─▶ (원래 succ …)
        """
        # ① 새 노드
        idx = len(getattr(fcfg, "placeholders", []))
        ph = CFGNode(f"MOD_PLACEHOLDER_{idx}")

        # ② 그래프 재배선
        G = fcfg.graph
        succs = list(G.successors(cur_block))

        G.add_node(ph)
        G.add_edge(cur_block, ph)
        for s in succs:
            G.remove_edge(cur_block, s)
            G.add_edge(ph, s)

        # ③ bookkeeping
        fcfg.placeholders = getattr(fcfg, "placeholders", []) + [ph]
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(ph)

    def build_unchecked_block(
            self,
            *,
            cur_block: CFGNode,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ):
        """
        unchecked 키워드를 만나면

            cur_block ─▶ unchecked ─▶ (기존 succcl …)

        로 그래프를 재배선한다. 생성된 노드를 반환.
        """
        unchecked = CFGNode(f"unchecked_{line_no}", unchecked_block=True, is_loop_body=cur_block.is_loop_body)
        unchecked.variables = VariableEnv.copy_variables(cur_block.variables)

        G = fcfg.graph
        succs = list(G.successors(cur_block))

        # ① 그래프 재배선
        G.add_node(unchecked)
        G.add_edge(cur_block, unchecked)
        for s in succs:
            G.remove_edge(cur_block, s)
            G.add_edge(unchecked, s)

        # ② line_info
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(unchecked)

    # Analyzer/DynamicCFGBuilder.py  내부 메소드 교체/추가

    def build_do_statement(
            self, *, cur_block: CFGNode, line_no: int, fcfg: FunctionCFG, line_info: dict
    ) -> None:
        G = fcfg.graph
        do_entry = CFGNode(f"do_body_{line_no}", src_line=line_no, is_loop_body=True)
        do_entry.is_do_entry = True
        do_end = CFGNode(f"do_end_{line_no}", src_line=line_no, is_loop_body=False)
        do_end.is_do_end = True

        # env
        do_entry.variables = VariableEnv.copy_variables(cur_block.variables)
        do_end.variables = VariableEnv.copy_variables(cur_block.variables)

        G.add_node(do_entry)
        G.add_node(do_end)

        # prev → do_entry → do_end
        old_succs = list(G.successors(cur_block))
        for s in old_succs:
            G.remove_edge(cur_block, s)
        G.add_edge(cur_block, do_entry)
        G.add_edge(do_entry, do_end)

        # do_end → (원래 succ들)
        for s in old_succs:
            G.add_edge(do_end, s)

        # line_info: do 시작 라인에는 do_entry만 추가
        # do_end는 while 조건 라인에서 찾을 수 있도록 그래프 구조로만 연결
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(do_entry)

    def build_do_while_statement(
            self, *, do_entry: CFGNode, while_line: int, fcfg: FunctionCFG,
            condition_expr, line_info: dict
    ) -> CFGNode:
        G = fcfg.graph

        # do_end = successor of do_entry (직결)
        succs = list(G.successors(do_entry))
        if not succs:
            raise ValueError("do_while: do_entry has no successor.")
        do_end = succs[0]

        # do_end 의 후속 간선을 잠시 떼어낸다
        post_succs = list(G.successors(do_end))
        for s in post_succs:
            G.remove_edge(do_end, s)

        # φ / cond / exit
        phi = CFGNode(f"do_while_phi_{while_line}", fixpoint_evaluation_node=True, src_line=while_line)
        phi.variables = VariableEnv.copy_variables(do_end.variables)
        phi.join_baseline_env = VariableEnv.copy_variables(do_end.variables)
        phi.fixpoint_evaluation_node_vars = VariableEnv.copy_variables(do_end.variables)

        cond = CFGNode(f"do_while_cond_{while_line}", condition_node=True,
                       condition_node_type="do_while", src_line=while_line)
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(phi.variables)

        exit_ = CFGNode(f"do_while_exit_{while_line}", loop_exit_node=True, src_line=while_line)

        G.add_nodes_from([phi, cond, exit_])

        # 배선: do_end→φ→cond,  cond True→do_entry(Back-edge),  False→exit_,  exit_→post_succs
        G.add_edge(do_end, phi)
        G.add_edge(phi, cond)
        G.add_edge(cond, do_entry, condition=True)
        G.add_edge(cond, exit_, condition=False)
        for s in post_succs:
            G.add_edge(exit_, s)

        # line_info: while 라인에는 cond만 추가
        bc = line_info.setdefault(while_line, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cond)

        # exit은 별도 end_line이 있다면 거기에 추가되어야 하지만,
        # do-while은 보통 } while (cond); 형태로 한 줄이므로 여기서는 추가 안함

        return exit_

    def build_try_skeleton(
            self, *, cur_block: CFGNode, function_expr, line_no: int,
            fcfg: FunctionCFG, line_info: dict
    ):
        """
        cur_block → try_cond ──True──▶ try_true ─▶ join
                           └─False──▶ false_stub ─▶ join
        catch 가 오면 false_stub 를 끊고 catch_entry/end 를 붙인다.
        """
        G = fcfg.graph

        # 1) 선행 간선 분리
        old_succs = list(G.successors(cur_block))
        for s in old_succs:
            G.remove_edge(cur_block, s)

        # 2) 노드
        cond = CFGNode(f"try_cond_{line_no}",
                       condition_node=True, condition_node_type="try",
                       src_line=line_no)
        cond.condition_expr = function_expr  # 기록용

        t_blk = CFGNode(f"try_true_{line_no}", branch_node=True, is_true_branch=True, src_line=line_no)
        f_stub = CFGNode(f"try_false_stub_{line_no}", branch_node=True, is_true_branch=False, src_line=line_no)
        join = CFGNode(f"try_join_{line_no}", join_point_node=True, src_line=line_no)

        # env
        cond.variables = VariableEnv.copy_variables(cur_block.variables)
        t_blk.variables = VariableEnv.copy_variables(cond.variables)
        f_stub.variables = VariableEnv.copy_variables(cond.variables)
        join.variables = VariableEnv.copy_variables(cond.variables)

        # 3) 배선
        for n in (cond, t_blk, f_stub, join):
            G.add_node(n)
        G.add_edge(cur_block, cond)
        G.add_edge(cond, t_blk, condition=True)
        G.add_edge(cond, f_stub, condition=False)
        G.add_edge(t_blk, join)
        G.add_edge(f_stub, join)
        # join → 원래 succ 복원
        for s in old_succs:
            G.add_edge(join, s)

        # 4) 표시
        cond.__catch_attached = False

        # 5) line_info: start line에는 cond만 추가
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cond)

        return cond, t_blk, f_stub, join

    def find_open_try_for_catch(self, *, line_no: int, fcfg: FunctionCFG):
        G = fcfg.graph
        candidates = [
            n for n in G.nodes
            if getattr(n, "condition_node", False)
               and getattr(n, "condition_node_type", "") == "try"
               and not getattr(n, "__catch_attached", False)
               and (getattr(n, "src_line", -1) < line_no)
        ]
        if not candidates:
            return None

        # 가장 가까운(라인 큰) try 선택
        cond = max(candidates, key=lambda n: getattr(n, "src_line", -1))

        # false_stub, join 찾기
        f_stub = None
        for s in G.successors(cond):
            if G[cond][s].get("condition") is False:
                f_stub = s
                break
        if f_stub is None:
            return None

        succs = list(G.successors(f_stub))
        if len(succs) != 1 or not getattr(succs[0], "join_point_node", False):
            return None
        join = succs[0]
        return (cond, f_stub, join)

    def attach_catch_clause(
            self, *, cond: CFGNode, false_stub: CFGNode, join: CFGNode,
            line_no: int, fcfg: FunctionCFG, line_info: dict
    ):
        G = fcfg.graph

        # 1) false_stub 제거
        if G.has_edge(cond, false_stub):
            G.remove_edge(cond, false_stub)
        for s in list(G.successors(false_stub)):
            if G.has_edge(false_stub, s):
                G.remove_edge(false_stub, s)
        # 필요 시 그래프에서 f_stub 노드를 완전히 제거해도 됨
        # G.remove_node(false_stub)

        # 2) catch 블록 생성
        c_entry = CFGNode(f"catch_entry_{line_no}", src_line=line_no)
        c_end = CFGNode(f"catch_end_{line_no}", src_line=line_no)

        c_entry.variables = VariableEnv.copy_variables(cond.variables)
        c_end.variables = VariableEnv.copy_variables(cond.variables)

        G.add_node(c_entry)
        G.add_node(c_end)
        G.add_edge(cond, c_entry, condition=False)
        G.add_edge(c_entry, c_end)
        G.add_edge(c_end, join)

        cond.__catch_attached = True

        # line_info: catch 시작 라인에는 c_entry만 추가
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(c_entry)

        return c_entry, c_end

    # Analyzer/DynamicCFGBuilder.py  (클래스 내부에 교체/추가)

    def insert_new_statement_block(
            self,
            *,
            pred_block: CFGNode,
            fcfg: FunctionCFG,
            line_no: int,
            line_info: dict,
            tag: str = "Block"
    ) -> CFGNode:
        """
        Create a new statement block and insert it between pred_block and its successors.
        
        Args:
            pred_block: The predecessor block
            fcfg: The function CFG
            line_no: Source line number
            line_info: Line info mapping
            tag: Name prefix for the new block
            
        Returns:
            The newly created block
        """
        from Utils.Helper import VariableEnv
        
        G = fcfg.graph
        
        # 1. Get current successors of pred_block
        old_succs = list(G.successors(pred_block))
        
        # 2. Create new block with pred's environment
        new_block = CFGNode(f"{tag}_{line_no}", is_loop_body=pred_block.is_loop_body)
        new_block.variables = VariableEnv.copy_variables(pred_block.variables or {})
        new_block.src_line = line_no
        
        # 3. Add new block to graph
        G.add_node(new_block)
        
        # 4. Rewire edges: pred -> new_block -> old_succs
        for succ in old_succs:
            G.remove_edge(pred_block, succ)
            G.add_edge(new_block, succ)
        G.add_edge(pred_block, new_block)
        
        # 5. Update line_info mapping
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(new_block)
        
        # 6. Update FCG
        fcfg.update_block(new_block)
        
        return new_block

    def get_current_block(self, context: str = "statement") :
        """
        Return the predecessor anchor where a new statement-block will be inserted,
        or the condition node for special contexts (else/else-if/catch).

        Algorithm:
        - For regular statements: Look at L+1 node
          * If L+1 is loop-exit or join: check L-1
            - If L-1 is cond: return cond's TRUE branch
            - Else: return L-1 node
          * Else: return L+1's predecessor

        - For special statements (else-if/else/catch): Look at L node
          * Traverse CFG predecessors from L to find specific node:
            - else-if/else: first cond node (type=if/else-if)
            - catch: first cond node (type=try)

        Note: Do-while is NOT handled by this implementation yet.

        Args:
            context: "statement" (default), "else", "else_if", or "catch"
        """
        an = self.an
        fcfg = an.current_target_function_cfg
        if fcfg is None:
            raise ValueError("Active FunctionCFG not found.")

        G = fcfg.graph
        # ★ L-1을 볼 때는 start_line 기준, L+1을 볼 때는 end_line 기준
        L_start = an.current_start_line
        L_end = (an.current_end_line if getattr(an, "current_end_line", None) is not None
                 else an.current_start_line)
        if L_start is None:
            raise ValueError("current_start_line is not set.")

        # ---------- Helper functions ----------
        def _line_nodes(line: int) -> list[CFGNode]:
            """Get all CFG nodes at given line."""
            info = an.line_info.get(line, None)
            if not info:
                return []
            cfg_nodes = info.get("cfg_nodes", [])
            if isinstance(cfg_nodes, list):
                return [n for n in cfg_nodes if n in G.nodes]
            return []

        def _line_first(line: int) -> CFGNode | None:
            """Get first CFG node at given line."""
            ns = _line_nodes(line)
            return ns[0] if ns else None

        def _is_loop_exit(n: CFGNode) -> bool:
            return getattr(n, "loop_exit_node", False)

        def _is_join(n: CFGNode) -> bool:
            return getattr(n, "join_point_node", False)

        def _is_cond(n: CFGNode) -> bool:
            return getattr(n, "condition_node", False)

        def _get_cond_type(n: CFGNode) -> str | None:
            """Get condition node type (if/else-if/try/etc)."""
            return getattr(n, "condition_node_type", None) if _is_cond(n) else None

        def _get_true_branch(cond: CFGNode) -> CFGNode | None:
            """Get TRUE branch of condition node."""
            for s in G.successors(cond):
                if G[cond][s].get("condition") is True:
                    return s
            return None

        def _find_cond_in_nodes(nodes: list[CFGNode]) -> CFGNode | None:
            """Find condition node in list (search from end)."""
            for n in reversed(nodes):
                if _is_cond(n):
                    return n
            return None

        # ========== Special contexts (else-if/else/catch) ==========
        if context in ["else_if", "else", "catch"]:
            # Get L line nodes and traverse predecessors
            L_nodes = _line_nodes(L_start)
            if not L_nodes:
                raise ValueError(f"No CFG nodes found at line {L_start} for context '{context}'")

            # ★ L_nodes에서 outer join 찾기 (else_if/else의 경우)
            found_outer_join = None
            if context in ["else_if", "else"]:
                for n in L_nodes:
                    if _is_join(n):
                        found_outer_join = n
                        break

            # BFS through predecessors to find target node
            from collections import deque
            visited = set()
            queue = deque(L_nodes)
            found_cond = None

            while queue:
                node = queue.popleft()
                if node in visited:
                    continue
                visited.add(node)

                # Check if this is the target node
                if _is_cond(node):
                    node_type = _get_cond_type(node)

                    if context in ["else_if", "else"]:
                        # Looking for if/else-if condition
                        if node_type in ["if", "else if"]:
                            found_cond = node
                            # ★ outer join과 함께 반환
                            if found_outer_join is None:
                                # fallback: 그래프에서 찾기
                                found_outer_join = self._outer_join_from_graph(found_cond, fcfg)
                            return (found_cond, found_outer_join)
                    elif context == "catch":
                        # Looking for try condition
                        if node_type == "try":
                            # catch는 outer join 필요시 여기서도 찾아서 반환
                            catch_outer_join = None
                            for n in L_nodes:
                                if _is_join(n):
                                    catch_outer_join = n
                                    break
                            if catch_outer_join is not None:
                                return (node, catch_outer_join)
                            else:
                                return node

                # Continue searching predecessors
                for pred in G.predecessors(node):
                    if pred not in visited:
                        queue.append(pred)

            if found_cond is None:
                raise ValueError(f"No matching condition node found for context '{context}' at line {L_start}")

        # ========== Regular statement context ==========
        # Look at L+1 node (L_end + 1)
        L_plus_1_node = _line_first(L_end + 1)

        if L_plus_1_node is None:
            # L+1 is empty, use EXIT
            L_plus_1_node = fcfg.get_exit_node()

        # Check if L+1 is loop-exit or join
        is_exit = _is_loop_exit(L_plus_1_node)
        is_join = _is_join(L_plus_1_node)

        if _is_loop_exit(L_plus_1_node) or _is_join(L_plus_1_node):
            # Look at L-1 nodes (L_start - 1)
            L_minus_1_nodes = _line_nodes(L_start - 1)

            if not L_minus_1_nodes:
                # L-1 empty, return first predecessor of L+1
                preds = list(G.predecessors(L_plus_1_node))
                return preds[0] if preds else fcfg.get_entry_node()

            # Check if any L-1 node is a condition
            cond_node = _find_cond_in_nodes(L_minus_1_nodes)

            if cond_node:
                # L-1 is cond: return TRUE branch
                true_branch = _get_true_branch(cond_node)
                if true_branch:
                    return true_branch
                else:
                    # Fallback: return cond itself (shouldn't happen)
                    return cond_node
            else:
                # L-1 is not cond: return last L-1 node
                return L_minus_1_nodes[-1]
        else:
            # L+1 is not loop-exit/join: return L+1's predecessor
            preds = list(G.predecessors(L_plus_1_node))

            if len(preds) == 1:
                return preds[0]
            elif len(preds) > 1:
                # Multiple predecessors (shouldn't happen for regular statement)
                # Return the one closest to current line
                def distance(n: CFGNode):
                    ln = getattr(n, "src_line", None)
                    return abs((ln or 0) - L_start) if ln is not None else 999999
                return min(preds, key=distance)
            else:
                # No predecessors, return ENTRY
                return fcfg.get_entry_node()


    def find_loop_join(self, start: CFGNode, fcfg: FunctionCFG) -> CFGNode | None:
        """
        역-DFS 로 가장 가까운 `fixpoint_evaluation_node`(while/for join) 반환.
        """
        G = fcfg.graph
        stk, seen = [start], set()
        while stk:
            n = stk.pop()
            if n in seen:
                continue
            seen.add(n)
            if n.fixpoint_evaluation_node:
                return n
            stk.extend(G.predecessors(n))
        return None

    def find_loop_condition(self, start: CFGNode, fcfg: FunctionCFG) -> CFGNode | None:
        G = fcfg.graph
        stk, seen = [start], set()
        while stk:
            n = stk.pop()
            if n in seen:
                continue
            seen.add(n)
            if getattr(n, "condition_node", False) and getattr(n, "condition_node_type", "") in {"while", "for",
                                                                                                 "doWhile", "do_while"}:
                return n
            stk.extend(G.predecessors(n))
        return None

    def _line_nodes_at(self, line_no: int, fcfg: FunctionCFG) -> list[CFGNode]:
        info = self.an.line_info.get(line_no, None)
        if not info:
            return []
        G = fcfg.graph
        out = []
        if isinstance(info.get("cfg_nodes"), list) and info["cfg_nodes"]:
            out.extend([n for n in info["cfg_nodes"] if n in G.nodes])
        else:
            cfg_nodes = info.get("cfg_nodes", [])
            if cfg_nodes and cfg_nodes[0] in G.nodes:
                out.append(cfg_nodes[0])
        return out

    def _pick_first_join(self, nodes: list["CFGNode"]) -> "CFGNode | None":
        for n in nodes:
            if getattr(n, "join_point_node", False):
                return n
        return nodes[0] if nodes else None

    def find_outer_join_near(
            self,
            *,
            anchor_line: int,
            fcfg: FunctionCFG,
            direction: str = "backward",  # "backward" | "forward" | "both"
            include_anchor: bool = True
    ) -> "CFGNode | None":
        """
        '}' 같은 토큰에 의존하지 않고, line_info를 스캔하여
        anchor_line에서 가장 가까운 join-point 노드를 찾는다.
        - direction: 기본 backward (위로 올라가며 탐색)
        - include_anchor=False면 anchor_line 자체는 건너뛴다.
        """
        lines = list(self.an.line_info.keys())
        if not lines:
            return None
        lo, hi = 1, max(lines)

        def _scan(lo_line, hi_line, step, start_line, skip_first):
            started = False
            for ln in range(start_line, hi_line + step, step):
                if not started:
                    started = True
                    if skip_first:
                        continue
                nodes = self._line_nodes_at(ln, fcfg)
                j = self._pick_first_join(nodes)
                if j is not None:
                    return j
            return None

        if direction == "backward":
            start = anchor_line if include_anchor else anchor_line - 1
            end = lo
            return _scan(lo, anchor_line, -1, start, False)  # 위로
        elif direction == "forward":
            start = anchor_line if include_anchor else anchor_line + 1
            end = hi
            return _scan(anchor_line, hi, +1, start, False)  # 아래로
        else:  # both
            j = self.find_outer_join_near(anchor_line=anchor_line, fcfg=fcfg,
                                          direction="backward", include_anchor=include_anchor)
            if j is not None:
                return j
            return self.find_outer_join_near(anchor_line=anchor_line, fcfg=fcfg,
                                             direction="forward", include_anchor=include_anchor)

    def _outer_join_from_graph(self, prev_cond: "CFGNode", fcfg: FunctionCFG) -> "CFGNode | None":
        """
        폴백: 그래프만으로 outer-join 추정 (prev_cond True-브랜치 → succ 중 join).
        """
        G = fcfg.graph
        for s in G.successors(prev_cond):
            if G[prev_cond][s].get("condition") is True:
                for j in G.successors(s):
                    if getattr(j, "join_point_node", False):
                        return j
        return None
