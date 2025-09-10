from __future__ import annotations

# Analyzer/CFGBuilder.py
from Utils.CFG import CFGNode, FunctionCFG
from Utils.Helper import VariableEnv
from Domain.IR import Expression
from Domain.Variable import Variables
from collections import deque
from typing import cast, Optional

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

    @staticmethod
    def build_variable_declaration(
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
        new_block = DynamicCFGBuilder.insert_new_statement_block(
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

    @staticmethod
    def build_assignment_statement(
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
        new_block = DynamicCFGBuilder.insert_new_statement_block(
            pred_block=cur_block,
            fcfg=fcfg,
            line_no=line_no,
            line_info=line_info,
            tag="Assign"
        )

        # 2) Add statement to the new block
        new_block.add_assign_statement(expr.left, expr.operator, expr.right, line_no)
        
        return new_block

    @staticmethod
    def build_unary_statement(
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
        new_block = DynamicCFGBuilder.insert_new_statement_block(
            pred_block=cur_block,
            fcfg=fcfg,
            line_no=line_no,
            line_info=line_info,
            tag="Unary"
        )

        # 2) Add statement to the new block
        new_block.add_unary_statement(expr, op_token, line_no)
        
        return new_block

    @staticmethod
    def build_function_call_statement(
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
        new_block = DynamicCFGBuilder.insert_new_statement_block(
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

    @staticmethod
    def build_if_statement(
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
                       condition_node_type="if", src_line=line_no)
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(cur_block.variables)

        t_blk = CFGNode(f"if_true_{line_no}", branch_node=True, is_true_branch=True, src_line=line_no)
        t_blk.variables = VariableEnv.copy_variables(true_env)

        f_blk = CFGNode(f"if_false_{line_no}", branch_node=True, is_true_branch=False, src_line=line_no)
        f_blk.variables = VariableEnv.copy_variables(false_env)

        join_env = VariableEnv.join_variables_simple(true_env, false_env)
        join = CFGNode(f"if_join_{line_no}", join_point_node=True, src_line=line_no)
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

        # line_info: 같은 라인에 cond와 join 둘 다 매핑 (멀티 노드)
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        # program-order 보존: cond 먼저, join 나중
        bc["cfg_nodes"].extend([cond, join])

        # 선택: end_line에도 join을 걸고 싶으면
        if end_line is not None:
            bc_end = line_info.setdefault(end_line, {"open": 0, "close": 0, "cfg_nodes": []})
            bc_end["cfg_nodes"].append(join)

        return join

    @staticmethod
    def build_else_if_statement(
            *,
            prev_cond: CFGNode,
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
                       condition_node_type="else if", src_line=line_no)
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(false_base_env)

        t_blk = CFGNode(f"else_if_true_{line_no}", branch_node=True, is_true_branch=True, src_line=line_no)
        t_blk.variables = VariableEnv.copy_variables(true_env)

        f_blk = CFGNode(f"else_if_false_{line_no}", branch_node=True, is_true_branch=False, src_line=line_no)
        f_blk.variables = VariableEnv.copy_variables(false_env)

        local_join_env = VariableEnv.join_variables_simple(true_env, false_env)
        local_join = CFGNode(f"else_if_join_{line_no}", join_point_node=True, src_line=line_no)
        local_join.variables = VariableEnv.copy_variables(local_join_env)

        for n in (cond, t_blk, f_blk, local_join):
            G.add_node(n)

        G.add_edge(prev_cond, cond, condition=False)
        G.add_edge(cond, t_blk, condition=True)
        G.add_edge(cond, f_blk, condition=False)
        G.add_edge(t_blk, local_join)
        G.add_edge(f_blk, local_join)

        # ③ outer-join: 헤딩 라인에서 '위로' 첫 join을 찾되, 현재 라인은 건너뜀
        outer_join = DynamicCFGBuilder.find_outer_join_near(anchor_line=line_no, fcfg=fcfg,
                                               direction="backward", include_anchor=False) \
                     or DynamicCFGBuilder._outer_join_from_graph(prev_cond, fcfg)
        if outer_join is None:
            raise ValueError("else-if: outer join not found via line-scan/graph")

        G.add_edge(local_join, outer_join)

        # ④ outer join env 재계산(모든 preds join)
        new_outer_env = None
        for p in G.predecessors(outer_join):
            new_outer_env = VariableEnv.join_variables_simple(new_outer_env, getattr(p, "variables", {}) or {})
        outer_join.variables = VariableEnv.copy_variables(new_outer_env or {})

        # ⑤ line_info: 헤딩 라인에 cond/로컬 join 둘 다 매핑 (멀티 노드)
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].extend([cond, local_join])

        if end_line is not None:
            bc_end = line_info.setdefault(end_line, {"open": 0, "close": 0, "cfg_nodes": []})
            bc_end["cfg_nodes"].append(local_join)

        return local_join

    @staticmethod
    def build_else_statement(
            *,
            cond_node: CFGNode,
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

        # ② target-join: 헤딩 라인 기준으로 위로 첫 join
        target_join = DynamicCFGBuilder.find_outer_join_near(anchor_line=line_no, fcfg=fcfg,
                                                direction="backward", include_anchor=True) \
                      or DynamicCFGBuilder._outer_join_from_graph(cond_node, fcfg)
        if target_join is None:
            raise ValueError("else: target join not found via line-scan/graph")

        # ③ else 블록 생성 및 연결
        else_blk = CFGNode(f"else_block_{line_no}", branch_node=True, is_true_branch=False, src_line=line_no)
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
    @staticmethod
    def build_while_statement(
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
        from typing import cast, Optional

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
        # 시작 라인: 조건 노드 매핑
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cond)

        # 끝 라인: loop-exit 노드 매핑
        if end_line is not None:
            bc_end = line_info.setdefault(end_line, {"open": 0, "close": 0, "cfg_nodes": []})
            bc_end["cfg_nodes"].append(exit_)

        return exit_  # ★ seed 용으로 exit 반환

    # DynamicCFGBuilder.py (시그니처/본문/리턴 변경)
    @staticmethod
    def build_for_statement(
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

        # body → incr? join?
        if incr_node:
            G.add_edge(body, incr_node)
            G.add_edge(incr_node, join)
        else:
            G.add_edge(body, join)

        # exit_ → 함수 EXIT (있으면)
        if funcExit:
            G.add_edge(exit_, funcExit)

        # ── ⑤ line_info ------------------------------------------------
        # 시작 라인: 조건 노드 매핑
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cond
        bc.setdefault("cfg_nodes", []).append(cond)

        # 끝 라인: loop-exit 노드 매핑
        if end_line is not None:
            bc_end = line_info.setdefault(end_line, {"open": 0, "close": 0, "cfg_nodes": []})
            bc_end["cfg_nodes"].append(exit_)

        return exit_  # ★ seed 용으로 exit 반환

    @staticmethod
    def build_continue_statement(
            *,
            cur_block: CFGNode,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> CFGNode:  # ★ 반환: 해당 루프의 loop-exit 노드

        cur_block.add_continue_statement(line_no)

        # ── join(고정점)으로 점프 (기존 동작 유지)
        join = DynamicCFGBuilder.find_loop_join(cur_block, fcfg)
        if join is None:
            raise ValueError("continue: loop join(fixpoint) node not found.")

        G = fcfg.graph
        for succ in list(G.successors(cur_block)):
            G.remove_edge(cur_block, succ)
        G.add_edge(cur_block, join)

        # ── loop-exit 찾기 (cond False-분기 중 loop_exit_node=True)
        cond = DynamicCFGBuilder.find_loop_condition(cur_block, fcfg)
        if cond is None:
            raise ValueError("continue: loop condition node not found.")

        exit_node = None
        for s in G.successors(cond):
            if G[cond][s].get("condition") is False and getattr(s, "loop_exit_node", False):
                exit_node = s
                break
        if exit_node is None:
            raise ValueError("continue: loop exit node not found.")

        # ── ★ 현재 env 를 loop-exit 에 ‘반영’(over-approx) — 요청사항 반영
        exit_node.variables = VariableEnv.join_variables_simple(exit_node.variables, cur_block.variables)

        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cur_block)

        return exit_node  # ★ seed 용

    @staticmethod
    def build_return_statement(
            *,
            cur_block: CFGNode,
            return_expr: Expression | None,
            return_val,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> list[CFGNode]:  # ★ 변경: 이전 succ 들을 반환

        # ① STATEMENT
        cur_block.add_return_statement(return_expr, line_no)

        # ★ seed 용으로 ‘재배선 전’ succ 보관
        G = fcfg.graph
        old_succs = list(G.successors(cur_block))

        # ② RETURN_EXIT 로 재배선
        return_exit_n = fcfg.get_return_exit_node()
        for s in old_succs:
            G.remove_edge(cur_block, s)
        G.add_edge(cur_block, return_exit_n)

        # ③ 반환 값 보관
        return_exit_n.return_vals[line_no] = return_val

        # ④ line_info
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cur_block)

        return old_succs  # ★ seed

    @staticmethod
    def build_break_statement(
            *,
            cur_block: CFGNode,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> CFGNode:  # ★ 반환: loop-exit

        cur_block.add_break_statement(line_no)

        cond = DynamicCFGBuilder.find_loop_condition(cur_block, fcfg)
        if cond is None:
            raise ValueError("break: loop condition node not found.")

        G = fcfg.graph
        exit_node = None
        for succ in G.successors(cond):
            if (G[cond][succ].get("condition") is False) and getattr(succ, "loop_exit_node", False):
                exit_node = succ
                break
        if exit_node is None:
            raise ValueError("break: loop exit node not found.")

        for succ in list(G.successors(cur_block)):
            G.remove_edge(cur_block, succ)
        G.add_edge(cur_block, exit_node)

        # ── ★ 현재 env 를 loop-exit 에 반영
        exit_node.variables = VariableEnv.join_variables_simple(exit_node.variables, cur_block.variables)

        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(cur_block)

        return exit_node  # ★ seed 용

    @staticmethod
    def build_revert_statement(
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

    @staticmethod
    def build_require_statement(
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
        )
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(cur_block.variables)

        # ── True 블록
        t_blk = CFGNode(
            name=f"require_true_{line_no}",
            branch_node=True,
            is_true_branch=True,
            src_line=line_no,
        )
        t_blk.variables = true_env

        # ── 재배선 (old_succ 보관)
        old_succ = list(G.successors(cur_block))
        for s in old_succ:
            G.remove_edge(cur_block, s)

        G.add_node(cond);
        G.add_edge(cur_block, cond)

        # False → ERROR
        error_exit_n = fcfg.get_error_exit_node()
        G.add_edge(cond, error_exit_n, condition=False)

        # True → t_blk
        G.add_node(t_blk);
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

    @staticmethod
    def build_assert_statement(
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
        )
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(cur_block.variables)

        # ── True 블록
        t_blk = CFGNode(
            name=f"assert_true_{line_no}",
            branch_node=True,
            is_true_branch=True,
            src_line=line_no,
        )
        t_blk.variables = true_env

        # ── 재배선 (old_succ 보관)
        old_succ = list(G.successors(cur_block))
        for s in old_succ:
            G.remove_edge(cur_block, s)

        G.add_node(cond);
        G.add_edge(cur_block, cond)

        # False → ERROR
        exit_n = fcfg.get_error_exit_node()
        G.add_edge(cond, exit_n, condition=False)

        # True → t_blk
        G.add_node(t_blk);
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

    @staticmethod
    def build_modifier_placeholder(
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

    @staticmethod
    def build_unchecked_block(
            *,
            cur_block: CFGNode,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ):
        """
        unchecked 키워드를 만나면

            cur_block ─▶ unchecked ─▶ (기존 succ …)

        로 그래프를 재배선한다. 생성된 노드를 반환.
        """
        unchecked = CFGNode(f"unchecked_{line_no}", unchecked_block=True)
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
        do_entry = CFGNode(f"do_body_{line_no}", src_line=line_no)
        do_entry.is_do_entry = True
        do_end = CFGNode(f"do_end_{line_no}", src_line=line_no)
        do_end.is_do_end = True

        # env
        do_entry.variables = VariableEnv.copy_variables(cur_block.variables)
        do_end.variables = VariableEnv.copy_variables(cur_block.variables)

        G.add_node(do_entry);
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

        # line_info (cfg_nodes 리스트 사용)
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].append(do_entry)
        bc["cfg_nodes"].append(do_end)

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

        # line_info
        bc = line_info.setdefault(while_line, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].extend([cond, exit_])

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

        # 5) line_info
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].extend([cond, t_blk, f_stub, join])

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
                f_stub = s;
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

        G.add_node(c_entry);
        G.add_node(c_end)
        G.add_edge(cond, c_entry, condition=False)
        G.add_edge(c_entry, c_end)
        G.add_edge(c_end, join)

        cond.__catch_attached = True

        # line_info
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_nodes": []})
        bc["cfg_nodes"].extend([c_entry, c_end])

        return c_entry, c_end

    # Analyzer/DynamicCFGBuilder.py  (클래스 내부에 교체/추가)

    @staticmethod
    def insert_new_statement_block(
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
        new_block = CFGNode(f"{tag}_{line_no}")
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

    def get_current_block(self) -> CFGNode:
        """
        Return the *predecessor anchor* where a new statement-block will be inserted.
        - NEVER mutates the CFG here (no new nodes, no edge rewiring, no fixpoint).
        - Selection rules:
            * succ := first node at (L+1), fallback to EXIT
            * if succ is loop-exit: return loop-body(True branch of the loop head)
            * if succ is join:
                - prefer predecessor with `is_do_end`
                - else prefer predecessor join
                - else try guard cond at same line and pick its branch via meta
                - else pick nearest predecessor
            * else (basic / others):
                - expect exactly one pred (skeleton already makes joins)
                - if not, fallback to “nearest” pred – but DO NOT create any join here
        """
        an = self.an
        fcfg = an.current_target_function_cfg
        if fcfg is None:
            raise ValueError("Active FunctionCFG not found.")

        G = fcfg.graph
        L = (an.current_end_line if getattr(an, "current_end_line", None) is not None
             else an.current_start_line)
        if L is None:
            raise ValueError("Neither current_end_line nor current_start_line is set.")

        # ---------- helpers ----------
        def _line_nodes(line: int) -> list[CFGNode]:
            info = an.line_info.get(line, None)
            if not info:
                return []
            out = []
            if isinstance(info.get("cfg_nodes"), list) and info["cfg_nodes"]:
                out.extend([n for n in info["cfg_nodes"] if n in G.nodes])
            else:
                # Check for old single cfg_node format for backward compatibility
                n = info.get("cfg_node")
                if n and n in G.nodes:
                    out.append(n)
            return out

        def _line_first(line: int) -> CFGNode | None:
            ns = _line_nodes(line)
            return ns[0] if ns else None

        def _line_last(line: int) -> CFGNode | None:
            ns = _line_nodes(line)
            return ns[-1] if ns else None

        def _branch_block(cond: CFGNode, want_true: bool) -> CFGNode | None:
            for s in G.successors(cond):
                if G[cond][s].get("condition") is want_true:
                    return s
            return None

        def _cond_of_join_by_graph(j: CFGNode) -> CFGNode | None:
            # join <- branch <- cond
            for b in G.predecessors(j):
                for q in G.predecessors(b):
                    if getattr(q, "condition_node", False):
                        return q
            return None

        def _branch_flag_from_meta(line: int) -> bool | None:
            info = an.line_info.get(line, None)
            if not info:
                return None
            meta = info.get("block_end", None)
            if not meta:
                return None
            br = meta.get("branch", None)
            return br if isinstance(br, bool) else None

        def _is_join(n: CFGNode) -> bool:
            return getattr(n, "join_point_node", False)

        def _is_loop_exit(n: CFGNode) -> bool:
            return getattr(n, "loop_exit_node", False)

        def _is_cond(n: CFGNode) -> bool:
            return getattr(n, "condition_node", False)

        def _nearest(nodes: list[CFGNode], succ_line: int) -> CFGNode:
            def key(n: CFGNode):
                ln = getattr(n, "src_line", None)
                return (0 if ln is not None else 1, abs((ln or 0) - succ_line))

            return sorted(nodes, key=key)[0]

        # ---------- 1) succ pick at L+1 ----------
        succ_line = L + 1
        succ = _line_first(succ_line)
        if succ is None:
            succ = fcfg.get_exit_node()

        # ---------- 2) succ is loop-exit → return loop body(True) as anchor ----------
        if _is_loop_exit(succ):
            loop_cond = None
            for p in G.predecessors(succ):
                if _is_cond(p) and G[p][succ].get("condition") is False:
                    loop_cond = p
                    break
            if loop_cond is not None:
                body = _branch_block(loop_cond, True)
                if body is not None:
                    return body
            preds = list(G.predecessors(succ))
            return _nearest(preds, succ_line) if preds else fcfg.get_entry_node()

        # ---------- 3) succ is join ----------
        if _is_join(succ):
            preds = list(G.predecessors(succ))

            # (A) do-while 마무리: do_end_* 를 최우선
            do_end_preds = [p for p in preds if getattr(p, "is_do_end", False)]
            if do_end_preds:
                return _nearest(do_end_preds, succ_line)

            # (B) pred-join 선호
            join_preds = [p for p in preds if _is_join(p)]
            if join_preds:
                return _nearest(join_preds, succ_line)

            # (C) 같은 줄 guard cond → 메타로 분기 선택
            guard = _line_last(succ_line)
            cond = guard if (guard is not None and _is_cond(guard)) else _cond_of_join_by_graph(succ)
            if cond is not None:
                want_true = _branch_flag_from_meta(succ_line)
                if want_true is None:
                    want_true = True
                b = _branch_block(cond, want_true)
                if b is not None:
                    return b

            # (D) 폴백: 가장 가까운 pred
            return _nearest(preds, succ_line) if preds else fcfg.get_entry_node()

        # ---------- 4) BASIC / 기타 ----------
        preds = list(G.predecessors(succ))
        # 기대상황: skeleton 덕에 항상 단일 pred
        if len(preds) == 1:
            return preds[0]

        # 방어적 폴백 (이상 상황): 가장 가까운 pred
        # (여기서 join 생성/그래프 수정은 절대 하지 않음)
        if len(preds) > 1:
            return _nearest(preds, succ_line)
        return fcfg.get_entry_node()

    def find_corresponding_condition_node(self):  # else if, else에 대한 처리
        # 현재 라인부터 위로 탐색하면서 대응되는 조건 노드를 찾음
        target_brace = 0
        for line in range(self.an.current_start_line - 1, 0, -1):
            brace_info = self.an.line_info[line]
            if brace_info:
                # '{'와 '}'의 개수 확인
                if brace_info['open'] == 1:
                    target_brace -= 1
                elif brace_info['close'] == 1:
                    target_brace += 1

                # target_brace가 0이 되면 대응되는 블록을 찾은 것
                if target_brace == 0:
                    cfg_nodes = brace_info.get('cfg_nodes', [])
                    cfg_node = cfg_nodes[0] if cfg_nodes else brace_info.get('cfg_node')
                    if cfg_node is not None and \
                            cfg_node.condition_node_type in ['if', 'else if']:
                        return cfg_node
        return None

    @staticmethod
    def find_loop_join(start: CFGNode, fcfg: FunctionCFG) -> CFGNode | None:
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

    @staticmethod
    def find_loop_condition(start: CFGNode, fcfg: FunctionCFG) -> CFGNode | None:
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
            # Check for old single cfg_node format for backward compatibility
            cfg_nodes = info.get("cfg_nodes", [])
            n = cfg_nodes[0] if cfg_nodes else info.get("cfg_node")
            if n and n in G.nodes:
                out.append(n)
        return out

    @staticmethod
    def _pick_first_join(nodes: list["CFGNode"]) -> "CFGNode | None":
        for n in nodes:
            if getattr(n, "join_point_node", False):
                return n
        return nodes[0] if nodes else None

    def find_outer_join_near(
            self, *,
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
