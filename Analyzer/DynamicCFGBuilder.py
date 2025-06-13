# Analyzer/CFGBuilder.py
from Utils.CFG import CFGNode, FunctionCFG
from Utils.Helper import VariableEnv
from Analyzer.ContractAnalyzer import ContractAnalyzer
from Interpreter.Engine import Engine
from collections import deque

class DynamicCFGBuilder:
    def __init__(self, an: ContractAnalyzer):
        self.an = an
        self.eng = Engine(an)

    # ─────────────────────────────────────────────────────
    # 지역변수 선언 전용 헬퍼
    # ─────────────────────────────────────────────────────
    def add_variable_declaration(
            self,
            *,
            cur_block: CFGNode,
            var_obj,
            type_obj,
            init_expr,
            line_no: int,
            fcfg: FunctionCFG,
            brace_count: dict
    ) -> None:
        """
        ContractAnalyzer.process_variable_declaration 에서
        노드·변수만 만든 뒤 호출된다.
        · cur_block.variables 업데이트
        · Statement 삽입
        · fcfg.related_variables 등록
        · fcfg.update_block 호출
        · brace_count 갱신
        """
        # 1) 블록 내부 상태 반영
        cur_block.variables[var_obj.identifier] = var_obj
        cur_block.add_variable_declaration_statement(
            type_obj, var_obj.identifier, init_expr, line_no
        )

        # 2) 함수-스코프 변수 테이블에도 추가
        fcfg.add_related_variable(var_obj)
        fcfg.update_block(cur_block)

        # 3) brace_count (라인 → 블록 매핑) 갱신
        if line_no not in brace_count:
            brace_count[line_no] = {"open": 0, "close": 0, "cfg_node": None}
        brace_count[line_no]["cfg_node"] = cur_block

    def get_current_block(self) -> CFGNode:
        """
        커서가 위치한 소스-라인에 대응하는 CFG 블록을 반환한다.
        - 한 줄 코드 삽입 : 해당 블록 반환
        - '}' 로 블록-아웃  : process_flow_join 에게 위임
        """

        close_brace_queue: list[int] = []

        # ── 위에서 ↓ 아래로 탐색 (직전 라인부터)
        for line in range(self.an.current_start_line - 1, 0, -1):
            brace_info = self.an.brace_count.get(
                line,
                {"open": 0, "close": 0, "cfg_node": None},
            )

            txt = self.an.full_code_lines.get(line, "").strip()
            if txt == "" or txt.startswith("//"):  # ← 공백 + 주석 모두 건너뜀
                continue

            # 공백/주석 전용 라인 스킵
            if brace_info["open"] == brace_info["close"] == 0 and brace_info["cfg_node"] is None:
                # 원본 라인 텍스트 직접 확인 (whitespace - only?)
                if self.an.full_code_lines.get(line, "").strip() == "":
                    continue

            # ────────── CASE 1. 아직 close_brace_queue가 비어 있음 ──────────
            if not close_brace_queue:
                # 1-a) 일반 statement 라인 → 그 cfg_node 반환
                if brace_info["cfg_node"] and brace_info["open"] == brace_info["close"] == 0:
                    cfg_node: CFGNode = brace_info["cfg_node"]
                    if cfg_node.condition_node:
                        ctype = cfg_node.condition_node_type
                        if ctype in ("require", "assert"):
                            return self.get_true_block(cfg_node)
                    else:
                        return cfg_node

                # 1-b) 막 열린 '{' (open==1, close==0)
                if brace_info["cfg_node"] and brace_info["open"] == 1 and brace_info["close"] == 0:
                    cfg_node: CFGNode = brace_info["cfg_node"]

                    # ENTRY 블록 직후 새 블록 삽입
                    if cfg_node.name == "ENTRY":
                        if self.an.current_target_function_cfg is None:
                            raise ValueError("No active function CFG found.")
                        entry_node = cfg_node
                        new_block = CFGNode(f"Block_{self.an.current_start_line}")

                        # variables = 함수 related 변수 deep-copy
                        new_block.variables = VariableEnv.copy_variables(self.an.current_target_function_cfg.related_variables)

                        g = self.an.current_target_function_cfg.graph
                        # ENTRY 의 기존 successor 기억 후 재연결
                        old_succs = list(g.successors(entry_node))
                        g.add_node(new_block)
                        g.add_edge(entry_node, new_block)
                        for s in old_succs:
                            g.remove_edge(entry_node, s)
                            g.add_edge(new_block, s)
                        return new_block

                    if cfg_node.name.startswith("else"):
                        return cfg_node

                    # 조건-노드의 서브블록 결정
                    if cfg_node.condition_node:
                        ctype = cfg_node.condition_node_type
                        if ctype in ("if", "else if"):
                            return self.get_true_block(cfg_node)
                        if ctype in ("while", "for", "doWhile"):
                            return self.get_true_block(cfg_node)

                    # 그 외 – 바로 반환
                    return cfg_node

                # 1-c) '}' 발견 → close 큐에 push
                if brace_info["open"] == 0 and brace_info["close"] == 1 and brace_info["cfg_node"] is None:
                    open_brace = self.match_open_brace(line)
                    if open_brace is None:
                        continue
                    _, open_brace_info = open_brace
                    if open_brace_info['cfg_node'] is not None and open_brace_info[
                        'cfg_node'].unchecked_block == True:  # unchecked indicator or general curly brace
                        continue
                    else:
                        close_brace_queue.append(line)

            # ────────── CASE 2. close_brace_queue가 이미 존재 ──────────
            else:
                # 연속 '}' 누적
                if brace_info["open"] == 0 and brace_info["close"] == 1 and brace_info["cfg_node"] is None:
                    open_brace = self.match_open_brace(line)
                    if open_brace is None:
                        continue
                    _, open_brace_info = open_brace
                    if open_brace_info['cfg_node'].unchecked_block:  # unchecked indicator or general curly brace
                        continue
                    else:
                        close_brace_queue.append(line)
                        continue
                # 블록 아웃 탐색 종료 조건
                break

        # ── close_brace_queue 가 채워졌다면 블록-아웃 처리 ──
        if close_brace_queue:
            blk = self.process_flow_join(close_brace_queue)
            if blk:
                return blk
            raise ValueError("Flow-join 처리 후에도 유효 블록을 결정하지 못했습니다.")

        raise ValueError("No active function CFG found.")

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
                # fixpoint 후 new_block 을 brace_count 에 등록 (다음 탐색용)
                self.an.brace_count[self.an.current_start_line] = {"open": 0, "close": 0, "cfg_node": new_block}
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
            info = self.an.brace_count.get(ln)
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
            info = self.an.brace_count.get(ln, {"open": 0, "close": 0, "cfg_node": None})
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
        """
        주어진 조건 노드의 하위 그래프를 탐색하여 리프 노드들을 수집하고 변수 정보를 조인합니다.
        :param condition_node: 최상위 조건 노드 (if 노드)
        :return: 조인된 변수 정보를 가진 새로운 블록
        """
        # 리프 노드 수집
        G = self.an.current_target_function_cfg.graph

        # ① leaf 수집 ------------------------------------------------
        leaf_nodes = self.collect_leaf_nodes(condition_node, stop_node_list)

        # ② 값 join --------------------------------------------------
        joined = {}
        for n in leaf_nodes:
            if n.function_exit_node:
                continue
            for k, v in n.variables.items():
                joined[k] = VariableEnv.join_variables_simple(joined.get(k, v), v)

        # 새로운 블록 생성 및 변수 정보 저장
        new_blk = CFGNode(f"JoinBlock_{self.an.current_start_line}")
        new_blk.variables = joined
        new_blk.join_point_node = True  # ★ join-블록 표식
        G.add_node(new_blk)

        # ④ leaf-succ 재배선 ----------------------------------------
        for leaf in leaf_nodes:
            succs = list(G.successors(leaf))
            # leaf 자체는 조건 블록이 아님(collect 단계에서 필터링)
            if not succs:
                G.add_edge(leaf, new_blk)
                continue

            for s in succs:
                # succ 이 ‘메타’(join, for-incr, loop-exit, fixpoint) 면 edge 교체
                if s.join_point_node or s.is_for_increment or s.name == "EXIT":
                    G.remove_edge(leaf, s)
                    G.add_edge(leaf, new_blk)
                    G.add_edge(new_blk, s)
                else:
                    raise ValueError(f"This should never happen")

        return new_blk

    def collect_leaf_nodes(self, root_if: CFGNode,
                           stop_nodes: set[CFGNode]) -> list[CFGNode]:

        """
        leaf = stop-node 들의 모든 predecessor 중
               (a) if-조건 블록이 아니고
               (b) still-in-if-chain 인 노드
        """
        G = self.an.current_target_function_cfg.graph
        leaf = []

        for s in stop_nodes:
            for p in G.predecessors(s):
                # if-체인에 속하지 않는 블록이면 제외
                if not p.condition_node:
                    leaf.append(p)

        return leaf
