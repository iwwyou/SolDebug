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
    ) -> None:
        """
        ContractAnalyzer.process_variable_declaration 에서
        노드·변수만 만든 뒤 호출된다.
        · cur_block.variables 업데이트
        · Statement 삽입
        · fcfg.related_variables 등록
        · fcfg.update_block 호출
        · line_info 갱신
        """
        # 1) 블록 내부 상태 반영
        cur_block.variables[var_obj.identifier] = var_obj
        cur_block.add_variable_declaration_statement(
            type_obj, var_obj.identifier, init_expr, line_no
        )

        # 2) 함수-스코프 변수 테이블에도 추가
        fcfg.add_related_variable(var_obj)
        fcfg.update_block(cur_block)

        # 3) line_info (라인 → 블록 매핑) 갱신
        if line_no not in line_info:
            line_info[line_no] = {"open": 0, "close": 0, "cfg_node": None}
        line_info[line_no]["cfg_node"] = cur_block

    @staticmethod
    def build_assignment_statement(
            *,
            cur_block: CFGNode,
            expr: Expression,  # a = b, a[i] += 1 …
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> None:

        # 1) 노드에 Statement 추가
        cur_block.add_assign_statement(expr.left,
                                       expr.operator,
                                       expr.right,
                                       line_no)

        # 2) FunctionCFG 에 변경 반영
        fcfg.update_block(cur_block)

        # 3) line_info 매핑
        bc = line_info.setdefault( line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cur_block

    @staticmethod
    def build_unary_statement(
            *,
            cur_block: CFGNode,
            expr: Expression,  # ++x  /  delete y 등
            op_token: str,  # '++' / '--' / 'delete'
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ):
        cur_block.add_unary_statement(expr, op_token, line_no)
        fcfg.update_block(cur_block)

        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cur_block

    @staticmethod
    def build_function_call_statement(
        *,
        cur_block: CFGNode,
        expr: Expression,          # foo(a,b)   전체 Expression
        line_no: int,
        fcfg: FunctionCFG,
        line_info: dict,
    ):
        """
        • cur_block 에 Statement 삽입 후
        • fcfg.update_block   (데이터-플로우 ⟲)
        • line_info[line_no]['cfg_node']  매핑
        """
        cur_block.add_function_call_statement(expr, line_no)
        fcfg.update_block(cur_block)

        bc = line_info.setdefault( line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cur_block

    @staticmethod
    def build_if_statement(
            *,
            cur_block: CFGNode,  # if 가 나오기 직전 블록
            condition_expr: Expression,  # 조건식
            true_env: dict[str, Variables],  # True-분기 변수 env
            false_env: dict[str, Variables],  # False-분기 변수 env
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> None:

        g = fcfg.graph
        succs = list(g.successors(cur_block))
        for s in succs:
            g.remove_edge(cur_block, s)

        # ① 노드 생성 ───────────────────────────────
        cond = CFGNode(
            name=f"if_condition_{line_no}",
            condition_node=True,
            condition_node_type="if",
            src_line=line_no,
        )
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(cur_block.variables)

        t_blk = CFGNode(
            name=f"if_true_{line_no}",
            branch_node=True,
            is_true_branch=True,
            src_line=line_no,
        )
        t_blk.variables = true_env

        f_blk = CFGNode(
            name=f"if_false_{line_no}",
            branch_node=True,
            is_true_branch=False,
            src_line=line_no,
        )
        f_blk.variables = false_env

        # ② 그래프 배선 ──────────────────────────────
        g.add_node(cond)
        g.add_node(t_blk)
        g.add_node(f_blk)

        g.add_edge(cur_block, cond)
        g.add_edge(cond, t_blk, condition=True)
        g.add_edge(cond, f_blk, condition=False)

        for s in succs:
            g.add_edge(t_blk, s)
            g.add_edge(f_blk, s)

        # ③ line_info ↔ line 매핑
        bc = line_info.setdefault( line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cond

    @staticmethod
    def build_else_if_statement(
            *,  # ← 모두 키워드-인수
            prev_cond: CFGNode,  # 직전 if / else-if 조건 노드
            condition_expr: Expression,  # 이번 else-if 조건
            cur_block: CFGNode,  # prev_cond 가 false 일 때 올 블록 (가상)
            true_env: dict[str, Variables],
            false_env: dict[str, Variables],
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> CFGNode:  # 새 condition-노드 반환
        G = fcfg.graph

        # ── ① old False edge 제거 ───────────────────────────────
        for succ in list(G.successors(prev_cond)):
            if G.edges[prev_cond, succ].get("condition") is False:
                G.remove_edge(prev_cond, succ)

        # ── ② 새 노드 3개 생성 ---------------------------------
        cond = CFGNode(
            f"else_if_condition_{line_no}",
            condition_node=True,
            condition_node_type="else if",
            src_line=line_no,
        )
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(cur_block.variables)

        t_blk = CFGNode(f"else_if_true_{line_no}",
                        branch_node=True, is_true_branch=True, src_line=line_no)
        t_blk.variables = true_env

        f_blk = CFGNode(f"else_if_false_{line_no}",
                        branch_node=True, is_true_branch=False, src_line=line_no)
        f_blk.variables = false_env

        # ── ③ 그래프 배선 --------------------------------------
        G.add_nodes_from((cond, t_blk, f_blk))
        G.add_edge(prev_cond, cond, condition=False)
        G.add_edge(cond, t_blk, condition=True)
        G.add_edge(cond, f_blk, condition=False)

        # cond / t_blk / f_blk 모두 이전 false successor 가 향하던 곳과
        # 연결하고 싶다면 여기에 g.add_edge(t_blk, succ) … 작성

        # ── ④ line_info 갱신 ---------------------------------
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cond
        return cond

    @staticmethod
    def build_else_statement(
            *,
            cond_node: CFGNode,  # 바로 앞 if / else-if 조건 노드
            else_env: dict[str, Variables],
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> CFGNode:
        """
        • cond_node 의 False 분기를 *교체* 해 “else 블록”을 삽입한다.
        • 그래프/line_info 갱신만 담당.  Interval 좁히기는 호출측(Refiner) 책임.
        """
        G = fcfg.graph

        # ── ① cond_node 에 달려 있던 ‘False’ edge / 블록 제거
        for succ in list(G.successors(cond_node)):
            if G.edges[cond_node, succ].get("condition") is False:
                G.remove_edge(cond_node, succ)
                for nxt in list(G.successors(succ)):
                    G.remove_edge(succ, nxt)

        # ── ② cond_node 의 True-succ 후속들을 기억 (join-point 후보)
        true_succs = [
            s for s in G.successors(cond_node)
            if G.edges[cond_node, s].get("condition") is True
        ]

        # ── ③ else 블록 생성
        else_blk = CFGNode(f"else_block_{line_no}",
                           branch_node=True,
                           is_true_branch=False,
                           src_line=line_no)
        else_blk.variables = else_env

        G.add_node(else_blk)
        G.add_edge(cond_node, else_blk, condition=False)

        # ── ④ True-succ 이 향하던 곳과 동일한 join 으로 연결
        for ts in true_succs:
            for nxt in list(G.successors(ts)):
                G.add_edge(else_blk, nxt)

        # ── ④ line_info 갱신 ---------------------------------
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = else_blk
        return else_blk

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
    ) -> None:
        """
        cur_block ─▶ join ─▶ cond ─▶ true(body) ───┐
                              │                    │
                              └──▶ false(exit) ────┘
        - 그래프, 변수 환경, line_info를 구성한다.
        - Interval 좁히기 결과(true_env / false_env)는 호출 측에서 계산해 넘긴다.
        """
        G = fcfg.graph

        # ── ① join-노드 --------------------------------------------------
        join = CFGNode(f"while_join_{line_no}", fixpoint_evaluation_node=True)
        join.variables = VariableEnv.copy_variables(join_env)
        join.join_baseline_env = VariableEnv.copy_variables(join_env)
        join.fixpoint_evaluation_node_vars = VariableEnv.copy_variables(join_env)

        G.add_node(join)

        # cur_block → join  (기존 cur_block successors 는 잠시 떼어낸다)
        old_succs = list(G.successors(cur_block))
        for s in old_succs:
            G.remove_edge(cur_block, s)
        G.add_edge(cur_block, join)

        # ── ② condition-노드 --------------------------------------------
        cond = CFGNode(f"while_cond_{line_no}",
                       condition_node=True,
                       condition_node_type="while",
                       src_line=line_no)
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(join.variables)

        G.add_node(cond)
        G.add_edge(join, cond)

        # ── ③ body / exit 블록 ------------------------------------------
        body = CFGNode(f"while_body_{line_no}", branch_node=True, is_true_branch=True)
        body.is_loop_body = True
        body.variables = VariableEnv.copy_variables(true_env)

        exit_ = CFGNode(f"while_exit_{line_no}", branch_node=True,
                        is_true_branch=False, loop_exit_node=True)
        exit_.variables = VariableEnv.copy_variables(false_env)

        G.add_nodes_from([body, exit_])
        G.add_edge(cond, body, condition=True)
        G.add_edge(cond, exit_, condition=False)

        # body → join  (back-edge)
        G.add_edge(body, join)

        # exit_ → 이전 cur_block successor 들로 복원
        for s in old_succs:
            G.add_edge(exit_, s)

        # ── ④ line_info ------------------------------------------------
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cond

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
    ) -> None:
        """
        pre ─▶ [init] ─▶ join ─▶ cond ─▶ body ─▶ incr
                               │         ▲        │
                               └─────────┘        │
                                         └────────┘
        * init_node / incr_node 는 ‘없을 수도’ 있으므로 Optional
        """
        G = fcfg.graph
        pre = cur_block  # for 키워드 직전 블록

        funcExit = None
        for succ in list(G.successors(pre)):
            if succ.name == "EXIT":  # 필요하면 추가 조건으로 더 안전하게
                funcExit = succ
                G.remove_edge(pre, succ)
                break  # 하나만 있으면 바로 탈출

        # ── ① join ------------------------------------------
        join = CFGNode(f"for_join_{line_no}", fixpoint_evaluation_node=True)
        join.variables = VariableEnv.copy_variables(join_env)
        join.join_baseline_env = VariableEnv.copy_variables(join_env)
        join.fixpoint_evaluation_node_vars = VariableEnv.copy_variables(join_env)

        # ── ② condition --------------------------------------
        cond = CFGNode(f"for_cond_{line_no}",
                       condition_node=True,
                       condition_node_type="for",
                       src_line=line_no)
        cond.condition_expr = cond_expr
        cond.variables = VariableEnv.copy_variables(join_env)

        # ── ③ body & exit ------------------------------------
        body = CFGNode(f"for_body_{line_no}", branch_node=True, is_true_branch=True)
        body.is_loop_body = True
        body.variables = VariableEnv.copy_variables(true_env)

        exit_ = CFGNode(f"for_exit_{line_no}", branch_node=True,
                        is_true_branch=False, loop_exit_node=True)
        exit_.variables = VariableEnv.copy_variables(false_env)

        # ── ④ 그래프 -----------------------------------------
        # 등록
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

        # exit_ → 함수 EXIT (있을 때만)
        if funcExit:
            G.add_edge(exit_, funcExit)

        # ── ⑤ line_info ------------------------------------
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cond

    @staticmethod
    def build_continue_statement(
            *,
            cur_block: CFGNode,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> None:

        cur_block.add_continue_statement(line_no)

        join = DynamicCFGBuilder.find_loop_join(cur_block, fcfg)
        if join is None:
            raise ValueError("continue: loop join(fixpoint) node not found.")

        G = fcfg.graph
        for succ in list(G.successors(cur_block)):
            G.remove_edge(cur_block, succ)
        G.add_edge(cur_block, join)

        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cur_block

    @staticmethod
    def build_return_statement(
            *,
            cur_block: CFGNode,
            return_expr: Expression | None,
            return_val,  # 계산된 값(Interval, list …)
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> None:
        """
        • cur_block 에 `return …` Statement 삽입
        • cur_block → EXIT 노드로 edge 연결
        • EXIT.return_vals[line_no] 에 결과 저장
        • line_info 갱신
        """
        # ① STATEMENT
        cur_block.add_return_statement(return_expr, line_no)

        # ② EXIT 노드 확보 & edge 재배선
        exit_n = fcfg.get_exit_node()
        G = fcfg.graph
        for succ in list(G.successors(cur_block)):
            G.remove_edge(cur_block, succ)
        G.add_edge(cur_block, exit_n)

        # ③ 반환-값 보관
        exit_n.return_vals[line_no] = return_val

        # ④ line_info
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cur_block

    @staticmethod
    def build_break_statement(
            *,
            cur_block: CFGNode,
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> None:

        cur_block.add_break_statement(line_no)

        cond = DynamicCFGBuilder.find_loop_condition(cur_block, fcfg)
        if cond is None:
            raise ValueError("break: loop condition node not found.")

        # loop-exit = cond 의 False-succ 중  loop_exit_node=True 인 것
        G = fcfg.graph
        exit_node = None
        for succ in G.successors(cond):
            if (
                    G[cond][succ].get("condition") is False
                    and succ.loop_exit_node
            ):
                exit_node = succ
                break
        if exit_node is None:
            raise ValueError("break: loop exit node not found.")

        for succ in list(G.successors(cur_block)):
            G.remove_edge(cur_block, succ)
        G.add_edge(cur_block, exit_node)

        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cur_block

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
    ) -> None:
        """
        Insert `revert (…)` into *cur_block* and connect the block
        straight to the EXIT node.
        """
        # ① statement
        cur_block.add_revert_statement(revert_id,
                                       string_literal,
                                       call_args,
                                       line_no)

        # ② edge --> EXIT
        exit_n = fcfg.get_exit_node()
        g = fcfg.graph

        # 모든 기존 successor 제거
        for succ in list(g.successors(cur_block)):
            g.remove_edge(cur_block, succ)

        g.add_edge(cur_block, exit_n)

        # ③ 데이터-플로우 갱신
        fcfg.update_block(cur_block)

        # ④ line_info
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cur_block

    @staticmethod
    def build_require_statement(
            *,
            cur_block: CFGNode,
            condition_expr: Expression,
            true_env: dict[str, Variables],
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> None:
        """
        Insert a Solidity `require(cond, …);`

        • current-block ─▶ require-cond (condition=True/False)
        • True  branch  ─▶   fall-through
        • False branch  ─▶   EXIT
        """
        G = fcfg.graph

        # ── ① 조건 노드 --------------------------------------------------
        cond = CFGNode(
            name=f"require_condition_{line_no}",
            condition_node=True,
            condition_node_type="require",
            src_line=line_no,
        )
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(cur_block.variables)

        # ── ② True 블록 --------------------------------------------------
        t_blk = CFGNode(
            name=f"require_true_{line_no}",
            branch_node=True,
            is_true_branch=True,
            src_line=line_no,
        )
        t_blk.variables = true_env

        # ── ③ 그래프 재배선 ---------------------------------------------
        #   current-block 의 succ 들을 임시 보관 후 제거
        old_succ = list(G.successors(cur_block))
        for s in old_succ:
            G.remove_edge(cur_block, s)

        G.add_node(cond)
        G.add_edge(cur_block, cond)

        #   False  → EXIT
        exit_n = fcfg.get_exit_node()
        G.add_edge(cond, exit_n, condition=False)

        #   True   → t_blk
        G.add_node(t_blk)
        G.add_edge(cond, t_blk, condition=True)

        #   t_blk  → 원래 succ (없으면 EXIT)
        if not old_succ:
            old_succ = [exit_n]
        for s in old_succ:
            G.add_edge(t_blk, s)

        # ── ④ 데이터-플로우 ---------------------------------------------
        fcfg.update_block(cur_block)

        # ── ⑤ line_info -----------------------------------------------
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc["cfg_node"] = cond

    @staticmethod
    def build_assert_statement(
            *,
            cur_block: CFGNode,
            condition_expr: Expression,
            true_env: dict[str, Variables],
            line_no: int,
            fcfg: FunctionCFG,
            line_info: dict,
    ) -> None:
        """
        Insert a Solidity `assert(cond, …);` block.

        • current-block ─▶ assert-cond
        • True  branch  ─▶ 기존 succ
        • False branch  ─▶ EXIT
        """
        G = fcfg.graph

        # ── ① 조건 노드 --------------------------------------------------
        cond = CFGNode(
            name=f"assert_condition_{line_no}",
            condition_node=True,
            condition_node_type="assert",
            src_line=line_no,
        )
        cond.condition_expr = condition_expr
        cond.variables = VariableEnv.copy_variables(cur_block.variables)

        # ── ② True 블록 --------------------------------------------------
        t_blk = CFGNode(
            name=f"assert_true_{line_no}",
            branch_node=True,
            is_true_branch=True,
            src_line=line_no,
        )
        t_blk.variables = true_env

        # ── ③ 그래프 재배선 ---------------------------------------------
        old_succ = list(G.successors(cur_block))
        for s in old_succ:
            G.remove_edge(cur_block, s)

        G.add_node(cond)
        G.add_edge(cur_block, cond)

        exit_n = fcfg.get_exit_node()
        G.add_edge(cond, exit_n, condition=False)

        G.add_node(t_blk)
        G.add_edge(cond, t_blk, condition=True)

        if not old_succ:  # fall-through 없으면 EXIT 로
            old_succ = [exit_n]
        for s in old_succ:
            G.add_edge(t_blk, s)

        # ── ④ 데이터-플로우, line_info ---------------------------------
        fcfg.update_block(cur_block)
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc['cfg_node'] = cond

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
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc['cfg_node'] = ph

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
        bc = line_info.setdefault(line_no, {"open": 0, "close": 0, "cfg_node": cast(Optional[CFGNode], None)})
        bc['cfg_node'] = unchecked

    # Analyzer/DynamicCFGBuilder.py  (클래스 내부에 교체/추가)

    def get_current_block(self) -> CFGNode:
        """
        Successor-first anchor selection (multi-nodes-per-line aware).

        - L := analyzer.current_end_line (fallback to start_line)
        - succ := FIRST node at line (L+1)  ← cfg_nodes[0] in program order
        - if succ is join-point:
            * prefer pred-join or pred-loop-exit
            * else guard-cond := LAST node at same line if it's a condition (cfg_nodes[-1]),
              fallback to graph backtracking (join <- branch <- cond)
            * choose branch(True/False) using line_info[succ_line]['block_end'].branch if present
        - if succ is loop-exit: insert NEW between (body → NEW → join)
        - if succ is basic: possibly create JOIN, then insert NEW between (pred → NEW → succ)
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
        def _line_nodes(fcfg: FunctionCFG, line: int) -> list[CFGNode]:
            """
            Return nodes mapped at `line` (in program order).
            Accepts both legacy single 'cfg_node' and list 'cfg_nodes'.
            """
            info = an.line_info.get(line, None)
            if not info:
                return []
            nodes: list[CFGNode] = []
            if "cfg_nodes" in info and isinstance(info["cfg_nodes"], list) and info["cfg_nodes"]:
                for n in info["cfg_nodes"]:
                    if n in fcfg.graph.nodes:
                        nodes.append(n)
            else:
                n = info.get("cfg_node", None)
                if n and n in fcfg.graph.nodes:
                    nodes.append(n)
            return nodes

        def _line_first(fcfg: FunctionCFG, line: int) -> CFGNode | None:
            ns = _line_nodes(fcfg, line)
            return ns[0] if ns else None

        def _line_last(fcfg: FunctionCFG, line: int) -> CFGNode | None:
            ns = _line_nodes(fcfg, line)
            return ns[-1] if ns else None

        def _map_line(line: int, node: CFGNode) -> None:
            # 단일 매핑 유지 (원하면 cfg_nodes append 로 확장 가능)
            bc = an.line_info.setdefault(line, {"open": 0, "close": 0, "cfg_node": None})
            bc["cfg_node"] = node

        def _create_between(u: CFGNode, v: CFGNode, env: dict[str, object], tag: str) -> CFGNode:
            new_blk = CFGNode(f"{tag}_{L}")
            new_blk.variables = VariableEnv.copy_variables(env or {})
            G.add_node(new_blk)
            if G.has_edge(u, v):
                G.remove_edge(u, v)
            G.add_edge(u, new_blk)
            G.add_edge(new_blk, v)
            _map_line(L, new_blk)
            fcfg.update_block(new_blk)
            return new_blk

        def _join_env(j: CFGNode) -> dict[str, object]:
            env = None
            for p in G.predecessors(j):
                env = VariableEnv.join_variables_simple(env, getattr(p, "variables", {}) or {})
            return VariableEnv.copy_variables(env or {})

        def _branch_block(cond: CFGNode, want_true: bool) -> CFGNode | None:
            for s in G.successors(cond):
                if G[cond][s].get("condition") is want_true:
                    return s
            return None

        def _cond_of_join_by_graph(j: CFGNode) -> CFGNode | None:
            # join <- branch_blk <- cond
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

        def _pruned_env(cond: CFGNode, branch_true: bool, base_env: dict[str, object]) -> dict[str, object]:
            env = VariableEnv.copy_variables(base_env or {})
            self.an.refiner.update_variables_with_condition(env, cond.condition_expr, branch_true)
            return env

        def _is_entry(n: CFGNode) -> bool:
            return getattr(n, "name", "") == "ENTRY"

        def _is_join(n: CFGNode) -> bool:
            return getattr(n, "join_point_node", False)

        def _is_loop_exit(n: CFGNode) -> bool:
            return getattr(n, "loop_exit_node", False)

        def _is_cond(n: CFGNode) -> bool:
            return getattr(n, "condition_node", False)

        def _is_basic(n: CFGNode) -> bool:
            return (not _is_cond(n)
                    and not getattr(n, "fixpoint_evaluation_node", False)
                    and not getattr(n, "function_exit_node", False)
                    and not _is_entry(n))

        def _nearest(nodes: list[CFGNode], succ_line: int) -> CFGNode:
            # 가장 가까운 pred (src_line 기준) 우선
            def key(n: CFGNode):
                ln = getattr(n, "src_line", None)
                return (0 if ln is not None else 1, abs((ln or 0) - succ_line))

            return sorted(nodes, key=key)[0]

        # ---------- 1) succ pick at L+1 ----------
        succ_line = L + 1
        succ = _line_first(fcfg, succ_line)  # ← 리스트의 [0]을 succ로 사용
        if succ is None:
            # 안전 폴백
            succ = fcfg.get_exit_node()

        # ---------- 2) by succ kind ----------
        if _is_join(succ):
            preds = list(G.predecessors(succ))
            join_preds = [p for p in preds if _is_join(p)]
            loopexit_preds = [p for p in preds if _is_loop_exit(p)]

            # (A-1) pred join이 있으면: 가장 가까운 join pred 뒤에 삽입
            if join_preds:
                pj = _nearest(join_preds, succ_line)
                env = getattr(pj, "variables", {}) or {}
                return _create_between(pj, succ, env, tag="Block")

            # (A-2) pred loop-exit이 있으면: loop-exit 뒤에 삽입
            if loopexit_preds:
                pl = _nearest(loopexit_preds, succ_line)
                env = getattr(pl, "variables", {}) or {}
                return _create_between(pl, succ, env, tag="Block")

            # (A-3) guard cond 선택: 같은 줄의 마지막 노드가 cond면 우선 사용
            guard = _line_last(fcfg, succ_line)
            cond = guard if (guard is not None and _is_cond(guard)) else _cond_of_join_by_graph(succ)

            if cond is None:
                # cond 추적 실패 → join 앞 env로 삽입
                env = _join_env(succ)
                any_pred = next(iter(G.predecessors(succ)))
                return _create_between(any_pred, succ, env, tag="Block")

            branch_flag = _branch_flag_from_meta(succ_line)
            if branch_flag is None:
                branch_flag = True  # 메타 없으면 True 가정

            b = _branch_block(cond, branch_flag)
            if b is None:
                # cond→(T/F) 간선이 아직 없다면 방어적 폴백
                b = next(iter(G.successors(cond)), None)
                if b is None:
                    env = _join_env(succ)
                    any_pred = next(iter(G.predecessors(succ)))
                    return _create_between(any_pred, succ, env, tag="Block")

            env = getattr(b, "variables", {}) or {}
            return _create_between(b, succ, env, tag="Block")

        if _is_loop_exit(succ):
            loop_cond = None
            for p in G.predecessors(succ):
                if _is_cond(p) and G[p][succ].get("condition") is False:
                    loop_cond = p
                    break

            if loop_cond is None:
                any_pred = next(iter(G.predecessors(succ)))
                env = getattr(any_pred, "variables", {}) or {}
                return _create_between(any_pred, succ, env, tag="Block")

            body = _branch_block(loop_cond, True)  # True-branch = body
            if body is None:
                body = next(iter(G.successors(loop_cond)), None)
                if body is None:
                    any_pred = next(iter(G.predecessors(succ)))
                    env = getattr(any_pred, "variables", {}) or {}
                    return _create_between(any_pred, succ, env, tag="Block")

            body_succs = list(G.successors(body))
            if not body_succs:
                env = getattr(body, "variables", {}) or {}
                new_blk = CFGNode(f"Block_{L}")
                new_blk.variables = VariableEnv.copy_variables(env)
                G.add_node(new_blk)
                G.add_edge(body, new_blk)
                _map_line(L, new_blk)
                fcfg.update_block(new_blk)
                return new_blk

            join_next = None
            for s2 in body_succs:
                if getattr(s2, "fixpoint_evaluation_node", False) or getattr(s2, "join_point_node", False):
                    join_next = s2
                    break
            if join_next is None:
                join_next = body_succs[0]

            env = getattr(body, "variables", {}) or {}
            return _create_between(body, join_next, env, tag="Block")

        # BASIC / 기타
        preds_all = list(G.predecessors(succ))
        preds = preds_all  # sink 분리가 되어 있다면 그대로 사용

        has_explicit_join = any(_is_join(p) for p in preds)
        if len(preds) >= 2 and not has_explicit_join:
            join_blk = CFGNode(f"JoinBlock_{L}")
            join_blk.join_point_node = True
            G.add_node(join_blk)
            env = None
            for p in preds:
                env = VariableEnv.join_variables_simple(env, getattr(p, "variables", {}) or {})
                if G.has_edge(p, succ):
                    G.remove_edge(p, succ)
                G.add_edge(p, join_blk)
            G.add_edge(join_blk, succ)
            fcfg.update_block(join_blk)
            preds = [join_blk]

        if len(preds) != 1:
            # 방어: 여전히 다수 → JOIN 뒤에 NEW
            p0 = preds[0]
            env = _join_env(p0) if _is_join(p0) else (getattr(p0, "variables", {}) or {})
            return _create_between(p0, succ, env, tag="Block")

        p = preds[0]
        if _is_join(p):
            env = _join_env(p)
            return _create_between(p, succ, env, tag="Block")

        if _is_cond(p):
            want_true = G[p][succ].get("condition", True)
            base = getattr(p, "variables", {}) or {}
            env = _pruned_env(p, want_true, base)
            return _create_between(p, succ, env, tag="Block")

        if _is_entry(p):
            env = VariableEnv.copy_variables(fcfg.related_variables)
            return _create_between(p, succ, env, tag="Block")

        env = getattr(p, "variables", {}) or {}
        return _create_between(p, succ, env, tag="Block")

    # ---------------------------------------------------------------------------
    # ② process_flow_join – '}' 를 만나 블록을 빠져나갈 때 합류/고정점 처리
    # ---------------------------------------------------------------------------
    def process_flow_join(self, close_brace_queue: list[int]) -> CFGNode | None:
        """
        close_brace_queue : 하향-탐색 중 만난 '}' 라인 번호 모음 (바깥쪽 brace 부터)
        반환              : 블록-아웃 뒤에 커서가 위치할 새 CFGNode (없으면 None)
        """

        outside_if_node: CFGNode | None = None
        has_if = False
        new_block: CFGNode | None = None

        stop_set = self.build_stop_set(close_brace_queue)

        # 가장 안쪽 '}' 부터 순차 처리
        for line in close_brace_queue:
            mb = self.match_open_brace(line)
            if mb is None:
                raise ValueError("Matching '{' not found for '}'")
            _, open_brace_info = mb

            cfg_node: CFGNode = open_brace_info["cfg_node"]

            # ── 루프 고정점 ─────────────────────────────────────────────
            if cfg_node.condition_node_type in ("while", "for", "doWhile"):
                new_block = self.eng.fixpoint(cfg_node)
                # fixpoint 후 new_block 을 line_info 에 등록 (다음 탐색용)
                self.an.line_info[self.an.current_start_line] = {"open": 0, "close": 0, "cfg_node": new_block}
                break  # 루프 하나만 처리하면 바깥은 다음 호출에서 다룸

            # ── if/else-if 합류 후보 ────────────────────────────────
            if not has_if and cfg_node.condition_node_type == "if":
                outside_if_node = cfg_node
                has_if = True

        # ─────────── if-join 처리 ───────────
        if has_if and outside_if_node is not None:
            return self.join_leaf_nodes(outside_if_node, stop_set)

        # 특별히 처리할 노드가 없으면 None – 상위 루틴에서 다시 판단
        return new_block

    # ContractAnalyzer.py (또는 해당 클래스가 정의된 모듈)

    def is_enclosed_by_loop(self, base_line: int) -> bool:
        """
        base_line 위쪽으로 올라가면서, 현재 블록이 while/for/doWhile
        내부에 있는지 판단한다.
        """
        # ① base_line 보다 위에 있는 모든 '{' 라인을 역순 탐색
        for ln in range(base_line - 1, 0, -1):
            info = self.an.line_info.get(ln)
            if not info:
                continue

            # ‘{’ 를 열면서 cfg_node 가 있는 경우만
            if info["open"] == 1 and info["cfg_node"]:
                node = info["cfg_node"]
                if node.condition_node_type in {"while", "for", "doWhile"}:
                    return True  # ← 루프 안에 있음
                #  (조건 노드가 루프가 아니면 계속 올라감)

            # 함수 시작 지점까지 왔으면 중단
            if info["cfg_node"] and info["cfg_node"].name == "ENTRY":
                break
        return False

    # Analyzer/CFGBuilder.py  내부
    def match_open_brace(self, close_ln: int) -> tuple[int, dict] | None:
        """
        close_ln 에 위치한 `}` 와 짝이 되는 `{` 의  (line_no, brace_info)  반환
        – 기존 두 함수(get_open_brace_info / find_corresponding_open_brace)를
          하나로 합친 버전.
        """
        depth = 1  # ① 첫 '}' 는 미리 count
        for ln in range(close_ln - 1, 0, -1):  # ② 위로 탐색
            info = self.an.line_info.get(ln, {"open": 0, "close": 0, "cfg_node": None})
            depth += info["close"] - info["open"]
            if info["open"] == 0:  # 여는 '{' 가 없는 라인
                continue

            if depth == 0:  # ③ 짝이 맞은 '{'
                cfg_node = info["cfg_node"]

                # unchecked 블록이면 그대로 OK
                if cfg_node and getattr(cfg_node, "unchecked_block", False):
                    return ln, info

                # else / else-if 라인은 스킵하고 더 위에서 찾는다
                if cfg_node and cfg_node.condition_node_type in ("else", "else if"):
                    continue

                # 그 외(if, while, for, 일반 블록 …) → 매칭 성공
                return ln, info
        return None  # 매칭 실패

    def build_stop_set(self, close_brace_queue: list[int]) -> set[CFGNode]:
        """
        queue의 ***바깥쪽*** '}' 에 대응하는 블록을 기준으로
        DFS 를 끊을 stop-node 집합을 만든다.
        """
        if not close_brace_queue:
            return set()

        outer_close = close_brace_queue[0]
        open_info = self.match_open_brace(outer_close)  # ← 새 헬퍼 사용
        if not open_info:
            return set()

        open_ln, brace_info = open_info
        base = brace_info["cfg_node"]  # if / loop 조건 노드
        G = self.an.current_target_function_cfg.graph
        stop = set()

        # base_line 은 (노드에 src_line 있으면) 그것, 없으면 open_ln
        base_line = open_ln
        enclosed_by_loop = self.is_enclosed_by_loop(base_line)

        # ❶ “루프 밖”에서 시작한다면 → left_loop = True
        #     기존 has_inner_loop 로 잡지 못했던 경우 보정

        # ────── ❶ 이 close-brace 뭉치 안에 “루프 블록”이 있었나? ──────
        has_inner_loop = False
        for cl in close_brace_queue:  # 안쪽→바깥쪽 모두 검사
            mb = self.match_open_brace(cl)
            if not mb:  # 방어
                continue
            _, inf = mb
            hd = inf["cfg_node"]
            if hd.condition_node_type in {"while", "for", "doWhile"}:
                has_inner_loop = True
                break

        # “루프 밖”에서 시작한다면 → left_loop = True
        left_loop = not has_inner_loop and not enclosed_by_loop

        # ────── ❷ 루트가 loop 인 경우 (기존 로직과 동일) ─────────────
        if base.condition_node_type in {"while", "for", "doWhile"}:
            for succ in G.successors(base):
                # loop-exit ==> 통과
                if succ.loop_exit_node:
                    continue
                # for-increment / fixpoint / join-point ==> stop
                if (
                        getattr(succ, "is_for_increment", False)
                        or succ.fixpoint_evaluation_node
                        or succ.join_point_node
                ):
                    stop.add(succ)
            return stop

        # ────── ❸ 루트가 if 인 경우 ------------------------------------
        if base.condition_node_type == "if":
            q = deque(G.successors(base))
            visited = set()

            while q:
                n = q.popleft()
                if n in visited:
                    continue
                visited.add(n)

                # (a) loop-exit 를 처음 만나면 “루프 밖”으로 전환
                if n.loop_exit_node:
                    if not left_loop:
                        left_loop = True
                        q.extend(G.successors(n))  # 루프 밖 흐름 확장
                    continue

                # (b) 루프 밖에서 처음 만난 join-point / EXIT  => stop
                if left_loop and (n.join_point_node or n.function_exit_node):
                    stop.add(n)
                    break  # 첫 번째 것만 필요하면 break

                if enclosed_by_loop and (n.join_point_node or n.is_for_increment or n.fixpoint_evaluation_node):
                    stop.add(n)
                    break

                # (c) 일반 블록 계속
                q.extend(G.successors(n))

        return stop

    def branch_block(self, condition_node: CFGNode, want_true: bool) -> CFGNode | None:
        cfg = self.an.contract_cfgs[self.an.current_target_contract]
        fcfg = cfg.get_function_cfg(self.an.current_target_function)
        if fcfg is None:
            raise ValueError("Active function CFG not found.")

        for succ in fcfg.graph.successors(condition_node):
            flag = fcfg.graph.edges[condition_node, succ].get("condition", False)
            if flag is want_true:
                return succ
        return None

    # 기존 API 유지용 thin-wrapper
    def get_true_block(self, n):
        return self.branch_block(n, True)

    def get_false_block(self, n):
        return self.branch_block(n, False)

    def join_leaf_nodes(self, condition_node, stop_node_list):
        G = self.an.current_target_function_cfg.graph

        leaf_nodes = self.collect_leaf_nodes(condition_node, stop_node_list)

        joined_env = None
        for n in leaf_nodes:
            if n.function_exit_node:
                continue
            joined_env = VariableEnv.join_variables_simple(joined_env, n.variables)

        new_blk = CFGNode(f"JoinBlock_{self.an.current_start_line}")
        new_blk.variables = joined_env
        new_blk.join_point_node = True
        G.add_node(new_blk)

        for leaf in leaf_nodes:
            succs = list(G.successors(leaf))
            if not succs:
                G.add_edge(leaf, new_blk)
                continue

            for s in succs:
                if (
                        getattr(s, "join_point_node", False) or
                        getattr(s, "is_for_increment", False) or
                        getattr(s, "fixpoint_evaluation_node", False) or  # ★ 추가
                        getattr(s, "function_exit_node", False) or
                        getattr(s, "name", "") == "EXIT"
                ):
                    G.remove_edge(leaf, s)
                    G.add_edge(leaf, new_blk)
                    G.add_edge(new_blk, s)
                else:
                    # 여기에 걸리면 보통 설계상 메타에 연결된 것이 아닌데,
                    # if 체인 내부가 아닌 다른 경로가 섞였다는 뜻 → 디버그 로그 추천
                    raise ValueError(f"This should never happen: succ={s.name}")
        return new_blk

    def collect_leaf_nodes(self, root_if: CFGNode,
                           stop_nodes: set[CFGNode]) -> list[CFGNode]:
        """
        leaf = stop-node 들의 predecessor 중에서
               (1) if-헤더에 의해 지배(dominated)되고,
               (2) 메타 노드가 아니고(조건/for-incr/join/loop-exit/fixpoint/EXIT),
               (3) 여전히 if-체인 내부에 있는 노드
        """
        fcfg = self.an.current_target_function_cfg
        G = fcfg.graph
        idom = self._compute_idom(fcfg)

        leaf: list[CFGNode] = []

        for s in stop_nodes:
            for p in G.predecessors(s):
                # ① if-헤더가 p를 지배하는가? (루프 preheader 같은 바깥 노드 제외)
                if not self._dominates(idom, root_if, p):
                    continue

                # ② 메타 노드 배제
                if getattr(p, "condition_node", False):
                    continue
                if getattr(p, "join_point_node", False):
                    continue
                if getattr(p, "fixpoint_evaluation_node", False):
                    continue
                if getattr(p, "is_for_increment", False):
                    continue
                if getattr(p, "function_exit_node", False) or getattr(p, "name", "") == "EXIT":
                    continue

                leaf.append(p)

        return leaf

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
                    if brace_info['cfg_node'] != None and \
                            brace_info['cfg_node'].condition_node_type in ['if', 'else if']:
                        return brace_info['cfg_node']
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
        """
        역-DFS 로 while / for / doWhile 의 condition-node(🔺) 를 찾는다.
        """
        G = fcfg.graph
        stk, seen = [start], set()
        while stk:
            n = stk.pop()
            if n in seen:
                continue
            seen.add(n)
            if n.condition_node and n.condition_node_type in {"while", "for", "doWhile"}:
                return n
            stk.extend(G.predecessors(n))
        return None

    # DynamicCFGBuilder 내부에 추가
    def _compute_idom(self, fcfg: FunctionCFG):
        import networkx as nx
        G = fcfg.graph
        entry = fcfg.get_entry_node()
        # immediate dominators: map[node] = its immediate dominator; entry maps to itself
        return nx.immediate_dominators(G, entry)

    def _dominates(self, idom_map: dict, a: CFGNode, b: CFGNode) -> bool:
        """
        a dominates b ?  (walk b -> entry along idom chain)
        """
        n = b
        while True:
            if n is a:
                return True
            # entry 의 idom 은 자기 자신
            parent = idom_map.get(n, None)
            if parent is None or parent is n:
                break
            n = parent
        return False