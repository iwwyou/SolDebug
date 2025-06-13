from Interpreter.Semantics import *
from collections import deque, defaultdict
from typing import Dict

class Engine:
    """
    – CFG work-list, widen / narrow, fix-point.
    – 실제 ‘한 줄 해석’은 Semantics 에게 위임.
    """

    def __init__(self, sem: Semantics, an:ContractAnalyzer):
        self.sems = sem
        self.an = an

    def transfer_function(self, node: CFGNode,
                          in_vars: dict[str, Variables]) -> dict[str, Variables]:

        out_vars = self.copy_variables(in_vars)
        changed = False

        # ─ 1) 조건 노드 ───────────────────────────────────────
        if node.condition_node:
            if node.branch_node and not node.is_true_branch:
                preds = list(self.an.current_target_function_cfg.graph.predecessors(node))

                cond_node = next(
                    (p for p in preds if getattr(p, "condition_node", False)),
                    None  # ← 조건-노드가 없을 때는 None
                )
                self.sems.update_variables_with_condition(out_vars,
                                                     cond_node.condition_expr,
                                                     node.is_true_branch)
            else:
                return out_vars

        # ─ 2) 일반/바디/증감 노드 ────────────────────────────
        elif not node.fixpoint_evaluation_node:
            if node.branch_node:
                preds = list(self.an.current_target_function_cfg.graph.predecessors(node))

                cond_node = next(
                    (p for p in preds if getattr(p, "condition_node", False)),
                    None  # ← 조건-노드가 없을 때는 None
                )
                self.sems.update_variables_with_condition(out_vars,
                                                     cond_node.condition_expr,
                                                     node.is_true_branch)

            for stmt in node.statements:
                before = self.copy_variables(out_vars)  # 🟢 깊은 사본
                self.sems.update_statement_with_variables(stmt, out_vars)
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
        for p in self.an.current_target_function_cfg.graph.predecessors(loop_condition_node):
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
            for succ in self.an.current_target_function_cfg.graph.successors(node):
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
            for p in self.an.current_target_function_cfg.graph.predecessors(node):
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
            for succ in self.an.current_target_function_cfg.graph.successors(node):
                if succ in loop_nodes:
                    WL.append(succ)

        # ── 4. exit-node 변수 반영 ─────────────────────────
        exit_env = None
        for p in self.an.current_target_function_cfg.graph.predecessors(exit_node):
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

    def copy_variables(self, src: Dict[str, Variables]) -> Dict[str, Variables]:
        """
        변수 env 를 **deep copy** 하되, 원본의 서브-클래스를 그대로 보존한다.
        """
        dst: Dict[str, Variables] = {}

        for name, v in src.items():

            # ───────── Array ─────────
            if isinstance(v, ArrayVariable):
                new_arr = ArrayVariable(
                    identifier=v.identifier,
                    base_type=copy.deepcopy(v.typeInfo.arrayBaseType),
                    array_length=v.typeInfo.arrayLength,
                    is_dynamic=v.typeInfo.isDynamicArray,
                    scope=v.scope
                )
                new_arr.elements = [
                    self.copy_variables({e.identifier: e})[e.identifier] for e in v.elements
                ]
                dst[name] = new_arr
                continue

            # ───────── Struct ─────────
            if isinstance(v, StructVariable):
                new_st = StructVariable(
                    identifier=v.identifier,
                    struct_type=v.typeInfo.structTypeName,
                    scope=v.scope
                )
                new_st.members = self.copy_variables(v.members)
                dst[name] = new_st
                continue

            # ───────── Mapping ────────
            if isinstance(v, MappingVariable):
                new_mp = MappingVariable(
                    identifier=v.identifier,
                    key_type=copy.deepcopy(v.typeInfo.mappingKeyType),
                    value_type=copy.deepcopy(v.typeInfo.mappingValueType),
                    scope=v.scope
                )
                # key-value 재귀 복사
                new_mp.mapping = self.copy_variables(v.mapping)
                dst[name] = new_mp
                continue

            # ───────── 기타(Variables / EnumVariable 등) ────────
            dst[name] = copy.deepcopy(v)  # 가장 안전

        return dst

    def _env_equal(self, a: dict[str, Variables] | None,
                   b: dict[str, Variables] | None) -> bool:
        return self.variables_equal(a or {}, b or {})

    def variables_equal(self, vars1: dict[str, Variables],
                        vars2: dict[str, Variables]) -> bool:
        """
        두 variable-env 가 완전히 동일한지 비교.
        구조 동일 + 값(equals) 동일해야 True
        """
        if vars1 is None or vars2 is None:
            # 둘 다 None 이면 True, 한쪽만 None 이면 False
            return vars1 is vars2

        if vars1.keys() != vars2.keys():
            return False

        for v in vars1:
            o1, o2 = vars1[v], vars2[v]
            if o1.typeInfo.typeCategory != o2.typeInfo.typeCategory:
                return False

            cat = o1.typeInfo.typeCategory

            # ─ array ───────────────────────────────────────────
            if cat == "array":
                a1 = cast(ArrayVariable, o1)  # type: ignore[assignment]
                a2 = cast(ArrayVariable, o2)  # type: ignore[assignment]

                if len(a1.elements) != len(a2.elements):
                    return False
                for e1, e2 in zip(a1.elements, a2.elements):
                    if not self.variables_equal({e1.identifier: e1},
                                                {e2.identifier: e2}):
                        return False

            # ─ struct ──────────────────────────────────────────
            elif cat == "struct":
                s1 = cast(StructVariable, o1)  # type: ignore[assignment]
                s2 = cast(StructVariable, o2)  # type: ignore[assignment]

                if not self.variables_equal(s1.members, s2.members):
                    return False

            # ─ mapping ─────────────────────────────────────────
            elif cat == "mapping":
                m1 = cast(MappingVariable, o1)  # type: ignore[assignment]
                m2 = cast(MappingVariable, o2)  # type: ignore[assignment]

                if m1.mapping.keys() != m2.mapping.keys():
                    return False
                for k in m1.mapping:
                    if not self.variables_equal({k: m1.mapping[k]},
                                                {k: m2.mapping[k]}):
                        return False

            # ─ elementary / enum / address ─
            else:
                v1, v2 = o1.value, o2.value
                if hasattr(v1, "equals") and hasattr(v2, "equals"):
                    if not v1.equals(v2):
                        return False
                else:
                    if v1 != v2:
                        return False
        return True

    def _val_or_self(self, var_obj):
        """elem이면 .value, 복합이면 객체 자체를 serialize"""
        return getattr(var_obj, "value", var_obj)

    def find_loop_exit_nodes(self, while_node):
        exit_nodes = set()  # ← 1) set 으로 중복 차단
        visited = set()
        stack = [while_node]

        while stack:
            cur = stack.pop()
            if cur in visited:
                continue
            visited.add(cur)

            for succ in self.an.current_target_function_cfg.graph.successors(cur):
                if succ == while_node:
                    continue
                if not self.is_node_in_loop(succ, while_node):
                    exit_nodes.add(succ)  # ← 2) add
                else:
                    stack.append(succ)

        return list(exit_nodes)  # ← 3) list 로 변환해 주면 기존 호출부 그대로

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

    def join_variable_values(self, v1, v2):
        """
        · Interval / BoolInterval              → 기존 join 유지
        · Variables (elementary wrapper)       → value 를 join
        · ArrayVariable                        → 길이·원소별 join
        · StructVariable                       → member 별 join
        · MappingVariable                      → 공통 key 만 join, 나머진 보존
        · EnumVariable                         → value 를 join (실제론 uint)
        · 타입 안 맞으면 symbolicJoin()
        """

        def _join_atomic(v1, v2):
            "두 primitive value(Interval / BoolInterval / literal)를 join"
            if hasattr(v1, "join") and type(v1) is type(v2):
                return v1.join(v2)  # Interval·BoolInterval
            if v1 == v2:
                return v1  # 동일 리터럴
            else:
                raise ValueError(f"Cannot join")  # 타입 다르거나 불가

        def _clone(obj):
            "Variables 류 객체를 얕은 copy – identifier / scope 등은 그대로"
            return copy.copy(obj)

        # ───── ① atomic (Interval / BoolInterval / 리터럴) ─────
        if not isinstance(v1, (Variables, ArrayVariable,
                               StructVariable, MappingVariable, EnumVariable)):
            return _join_atomic(v1, v2)

        # 두 객체의 타입이 다르면 → symbolic
        if type(v1) is not type(v2):
            raise ValueError(f"{v1}, {v2} is not same type")

        # ───── ② Variables (elementary) ─────
        if isinstance(v1, Variables) and not isinstance(v1, (ArrayVariable, StructVariable, MappingVariable)):
            new = _clone(v1)
            new.value = _join_atomic(v1.value, v2.value)
            return new

        # ───── ③ EnumVariable ─────
        if isinstance(v1, EnumVariable):
            new = _clone(v1)
            new.value = _join_atomic(v1.value, v2.value)
            return new

        # ───── ④ ArrayVariable ─────
        if isinstance(v1, ArrayVariable):
            # 길이 불일치 → 보수적으로 심볼릭
            if len(v1.elements) != len(v2.elements):
                raise ValueError(f"The length of element of Array Variable {v1}, {v2} is not same")
            new_arr = _clone(v1)
            new_arr.elements = [
                self.join_variable_values(a, b) for a, b in zip(v1.elements, v2.elements)
            ]
            return new_arr

        # ───── ⑤ StructVariable ─────
        if isinstance(v1, StructVariable):
            new_st = _clone(v1)
            new_st.members = {}
            for m in v1.members.keys() | v2.members.keys():  # 합집합
                if m in v1.members and m in v2.members:
                    new_st.members[m] = self.join_variable_values(v1.members[m], v2.members[m])
                else:
                    # 한쪽에만 있으면 그대로 유지
                    new_st.members[m] = _clone(v1.members.get(m, v2.members.get(m)))
            return new_st

        # ───── ⑥ MappingVariable ─────
        if isinstance(v1, MappingVariable):
            new_map = _clone(v1)
            new_map.mapping = {}
            all_keys = v1.mapping.keys() | v2.mapping.keys()
            for k in all_keys:
                if k in v1.mapping and k in v2.mapping:
                    new_map.mapping[k] = self.join_variable_values(v1.mapping[k], v2.mapping[k])
                else:
                    new_map.mapping[k] = _clone(v1.mapping.get(k, v2.mapping.get(k)))
            return new_map

        # ───── ⑦ fallback ─────
        raise ValueError(f"Cannot Join Fallback")

    # ContractAnalyzer (또는 utils 모듈 내부에)

    def _merge_values(self, v1, v2,
                      mode: str = "join"):  # "join" | "widen" | "narrow"
        """
        • Interval / BoolInterval      → 해당 메서드(join/widen/narrow) 사용
        • 래퍼(Variables / StructVariable / ArrayVariable / MappingVariable /
               EnumVariable)           → 내부 값 재귀적으로 merge
        • 타입 안 맞거나 merge 불가   → symbolicJoin / symbolicWiden / symbolicNarrow
        """

        def _should_widen(val):
            return isinstance(val, (IntegerInterval, UnsignedIntegerInterval, BoolInterval))

        # ---- ① primitive -----------------------------------------------
        if not isinstance(v1, (Variables, ArrayVariable,
                               StructVariable, MappingVariable, EnumVariable)):
            # Interval 인데 원하는 op 를 제공?
            if mode == "widen" and not _should_widen(v1):
                # widen 이지만 타입이 Interval 이 아님 → join 과 동일 처리
                return self._merge_values(v1, v2, "join")

            if hasattr(v1, mode):
                return getattr(v1, mode)(v2)
            return f"symbolic{mode.capitalize()}({v1},{v2})"

        # ---- ② 래퍼 객체 : 타입 불일치 → symbolic*
        # ---- ② 래퍼 객체 : 타입 불일치 → symbolic*
        if type(v1) is not type(v2):
            return f"symbolic{mode.capitalize()}({v1},{v2})"

        if type(v1) is not type(v2):
            if isinstance(v1, Variables) and isinstance(v2, Variables):
                new = copy.copy(v1)
                new.value = self._merge_values(v1.value, v2.value, mode)
                return new
            return f"symbolic{mode.capitalize()}({v1},{v2})"

        # ---- ③ Variables / EnumVariable -------------------------------
        if isinstance(v1, Variables) and not isinstance(v1, (ArrayVariable,
                                                             StructVariable,
                                                             MappingVariable)):
            new = copy.copy(v1)
            new.value = self._merge_values(v1.value, v2.value, mode)
            return new

        if isinstance(v1, EnumVariable):
            new = copy.copy(v1)
            new.value = self._merge_values(v1.value, v2.value, mode)
            return new

        # ---- ④ ArrayVariable ------------------------------------------
        if isinstance(v1, ArrayVariable):
            if len(v1.elements) != len(v2.elements):
                return f"symbolic{mode.capitalize()}({v1.identifier},{v2.identifier})"
            new_arr = copy.copy(v1)
            new_arr.elements = [
                self._merge_values(a, b, mode) for a, b in zip(v1.elements, v2.elements)
            ]
            return new_arr

        # ---- ⑤ StructVariable -----------------------------------------
        if isinstance(v1, StructVariable):
            new_st = copy.copy(v1)
            new_st.members = {}
            for m in v1.members.keys() | v2.members.keys():
                if m in v1.members and m in v2.members:
                    new_st.members[m] = self._merge_values(v1.members[m],
                                                           v2.members[m], mode)
                else:
                    new_st.members[m] = copy.copy(v1.members.get(m,
                                                                 v2.members.get(m)))
            return new_st

        # ---- ⑥ MappingVariable ----------------------------------------
        if isinstance(v1, MappingVariable):
            new_map = copy.copy(v1)
            new_map.mapping = {}

            for k in v1.mapping.keys() | v2.mapping.keys():
                if k in v1.mapping and k in v2.mapping:
                    new_map.mapping[k] = self._merge_values(v1.mapping[k],
                                                            v2.mapping[k], mode)
                else:
                    # ➤ 한쪽만 있을 때 bottom 이면 다른 쪽 값 채택
                    src = v1.mapping.get(k) or v2.mapping.get(k)
                    if (isinstance(src, Variables)
                            and isinstance(src.value, Interval)
                            and src.value.is_bottom()):
                        # 아무 정보가 없는 BOTTOM 이면 skip
                        continue
                    new_map.mapping[k] = self.copy_variables({k: src})[k]
            return new_map

        # ---- fallback --------------------------------------------------
        return f"symbolic{mode.capitalize()}({v1},{v2})"

    # ─────────────────────────────────────────────────────────────
    # 1) 공통 로직:  _merge_by_mode
    #    mode ∈ {"join", "widen", "narrow"}
    # ─────────────────────────────────────────────────────────────
    def _merge_by_mode(self, left_vars, right_vars, mode):
        if left_vars is None:
            return self.copy_variables(right_vars or {})
        if not right_vars:  # ← 추가
            return self.copy_variables(left_vars)

        res = self.copy_variables(left_vars)

        for name, r_var in (right_vars or {}).items():
            if name in res:
                # ① 기존 l_var 와 r_var 를 **전체** merge
                merged = self._merge_values(res[name], r_var, mode)
                # ② 결과를 그대로 덮어쓴다   ←  .value 만 건드리면 안 됨!
                res[name] = merged
            else:
                # 새로 등장한 변수는 deep-copy 해서 추가
                res[name] = self.copy_variables({name: r_var})[name]
        return res

    # widening-join (⊔ω)
    def join_variables_with_widening(self, left_vars, right_vars):
        return self._merge_by_mode(left_vars, right_vars, "widen")

    # 단순 join (⊔) – narrowing 1차 패스
    def join_variables_simple(self, left_vars, right_vars):
        return self._merge_by_mode(left_vars, right_vars, "join")

    # narrow (⊓) – narrowing 2차 패스
    def narrow_variables(self, old_vars, new_vars):
        return self._merge_by_mode(old_vars, new_vars, "narrow")

    def join_variables(self, vars1: dict[str, Variables],
                       vars2: dict[str, Variables]) -> dict[str, Variables]:
        """
        두 variable-env 를 ⨆(join) 한다.

        * elementary (int/uint/bool/address/enum)  → 값 Interval.join
          - address 값이 UnsignedIntegerInterval 이면 그대로 join.
          - 문자열(symbolic)  둘이 다르면  "symbolicJoin(...)" 로 보수화.
        * array     → 동일 인덱스 별도 join  (길이 불일치 ⇒ 오류)
        * struct    → 멤버별 join
        * mapping   → key 합집합, value 각각 join  (새 key 는 deep-copy)
        """
        res = self.copy_variables(vars1)  # 깊은 복사

        for v, obj2 in vars2.items():
            if v not in res:
                res[v] = self.copy_variables({v: obj2})[v]
                continue

            obj1 = res[v]
            cat = obj1.typeInfo.typeCategory

            # ——— 동일 typeCategory 보장 ———
            if cat != obj2.typeInfo.typeCategory:
                raise TypeError(f"join type mismatch: {cat} vs {obj2.typeInfo.typeCategory}")

            # ─ array ──────────────────────────────────────────────────────
            if cat == "array":
                # mypy / PyCharm 에게 ‘ArrayVariable 맞다’고 알려주기
                obj1_arr: ArrayVariable = obj1  # type: ignore[assignment]
                obj2_arr: ArrayVariable = obj2  # type: ignore[assignment]

                if len(obj1_arr.elements) != len(obj2_arr.elements):
                    raise ValueError("join-array length mismatch")

                for i, (e1, e2) in enumerate(zip(obj1_arr.elements, obj2_arr.elements)):
                    joined = self.join_variables({e1.identifier: e1},
                                                 {e2.identifier: e2})
                    obj1_arr.elements[i] = joined[e1.identifier]

            # ─ struct ──────────────────────────────────────────────
            elif cat == "struct":
                obj1_struct: StructVariable = cast(StructVariable, obj1)  # type: ignore[assignment]
                obj2_struct: StructVariable = cast(StructVariable, obj2)  # type: ignore[assignment]

                obj1_struct.members = self.join_variables(
                    obj1_struct.members,
                    obj2_struct.members
                )

            # ─ mapping ─────────────────────────────────────────────
            elif cat == "mapping":
                obj1_map: MappingVariable = cast(MappingVariable, obj1)  # type: ignore[assignment]
                obj2_map: MappingVariable = cast(MappingVariable, obj2)  # type: ignore[assignment]

                for k, mv2 in obj2_map.mapping.items():
                    if k in obj1_map.mapping:
                        merged = self.join_variables(
                            {k: obj1_map.mapping[k]},
                            {k: mv2}
                        )[k]
                        obj1_map.mapping[k] = merged
                    else:
                        obj1_map.mapping[k] = self.copy_variables({k: mv2})[k]

            # ─ elementary / enum / address ───────────────────────────────
            else:
                obj1.value = self.join_variable_values(obj1.value, obj2.value)

        return res

