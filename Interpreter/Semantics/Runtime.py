from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:                                         # 타입 검사 전용
     from Analyzer.ContractAnalyzer import ContractAnalyzer

from Domain.Variable import Variables, ArrayVariable
from Domain.IR import Expression
from Domain.Interval import UnsignedIntegerInterval, IntegerInterval, BoolInterval

class Runtime:
    def __init__(self, analyzer: "ContractAnalyzer"):
        # 별도 객체를 새로 만들지 않고 ContractAnalyzer 안의 싱글톤을
        # 지연-참조(lazy) 합니다.
        self.an = analyzer

    # ── lazy properties ──────────────────────────────────────────────
    @property
    def rec(self):
        return self.an.recorder

    @property
    def ref(self):
        return self.an.refiner

    @property
    def eval(self):
        return self.an.evaluator

    @property
    def up(self):
        return self.an.updater

    @property
    def eng(self):
        return self.an.engine

    def update_statement_with_variables(self, stmt, current_variables, ret_acc=None):
        if stmt.statement_type == 'variableDeclaration':
            return self.interpret_variable_declaration_statement(stmt, current_variables)
        elif stmt.statement_type == 'assignment':
            return self.interpret_assignment_statement(stmt, current_variables)
        elif stmt.statement_type == 'unary':  # 🔹 추가
            return self.interpret_unary_statement(stmt, current_variables)
        elif stmt.statement_type == 'functionCall':
            return self.interpret_function_call_statement(stmt, current_variables)
        elif stmt.statement_type == 'return':
            return self.interpret_return_statement(stmt, current_variables, ret_acc)
        elif stmt.statement_type == 'revert':
            return self.interpret_revert_statement(stmt, current_variables)
        elif stmt.statement_type == 'break':
            return self.interpret_break_statement(stmt, current_variables)
        elif stmt.statement_type == 'continue':
            return self.interpret_continue_statement(stmt, current_variables)
        else:
            raise ValueError(f"Statement '{stmt.statement_type}' is not implemented.")

    def interpret_variable_declaration_statement(self, stmt, variables):
        var_type = stmt.type_obj
        var_name = stmt.var_name
        init_expr = stmt.init_expr  # None 가능

        # ① 변수 객체 찾기 (process 단계에서 이미 cur_blk.variables 에 들어있음)
        if var_name not in variables:
            vobj = Variables(identifier=var_name, scope="local")
            vobj.typeInfo = var_type

            # 타입에 맞춰 ⊥ 값으로 초기화
            et = var_type.elementaryTypeName
            if et.startswith("uint"):
                bits = var_type.intTypeLength or 256
                vobj.value = UnsignedIntegerInterval.bottom(bits)
            elif et.startswith("int"):
                bits = var_type.intTypeLength or 256
                vobj.value = IntegerInterval.bottom(bits)
            elif et == "bool":
                vobj.value = BoolInterval.bottom()
            else:  # address / bytes / string 등
                vobj.value = f"symbol_{var_name}"

            variables[var_name] = vobj  # ★ env 에 등록
        else:
            vobj = variables[var_name]

        # ② 초기화 식 평가 (있을 때만)
        if init_expr is not None:
            if isinstance(vobj, ArrayVariable):
                pass  # inline array 등은 필요 시
            else:  # Variables / EnumVariable
                vobj.value = self.eval.evaluate_expression(
                    init_expr, variables, None, None
                )

                # ③ RecordManager 로 기록  ← 기존 _record_analysis 블록 삭제
                self.rec.record_variable_declaration(
                    line_no=stmt.src_line,
                    var_name=var_name,
                    var_obj=vobj
                )

        return variables

    def interpret_assignment_statement(self, stmt, variables):
        # 0) RHS 계산 – 기존과 동일
        lexp, rexpr, op = stmt.left, stmt.right, stmt.operator
        if isinstance(rexpr, Expression):
            r_val = self.eval.evaluate_expression(rexpr, variables, None, None)
        else:  # 이미 Interval·리터럴 등 평가완료 값
            r_val = rexpr

        # 1) LHS 에 반영
        self.up.update_left_var(lexp, r_val, op, variables, None, None, True)

        return variables

    # ------------------------------------------------------------------
    # 단항(++ / -- / delete) 스테이트먼트 해석
    # ------------------------------------------------------------------
    def interpret_unary_statement(self, stmt, variables):
        """
        stmt.operator : '++' | '--' | 'delete' …
        stmt.operand  : Expression
        """
        op = stmt.operator  # '++' / '--' / 'delete'
        operand = stmt.operand
        src_line = stmt.src_line

        # ── ++ / --  ---------------------------------------------------
        if op == '++':
            # rVal=1, operator='+='  →  i = i + 1
            self.up.update_left_var(
                operand,  # LHS
                1,  # rVal
                '+=',  # compound-operator
                variables,
                None, None,
                False  # log=True  → Recorder 기록
            )
            return variables

        if op == '--':
            # rVal=1, operator='-='  →  i = i - 1
            self.up.update_left_var(
                operand,
                1,
                '-=',
                variables,
                None, None,
                False
            )
            return variables

        # ── delete x  --------------------------------------------------
        if op == 'delete':
            # elementary → 0 / ⊥ , composite → 재귀 ⊥
            self.up.update_left_var(
                operand,
                0,  # 값 지우기
                '=',  # 단순 대입
                variables,
                None, None,
                True
            )
            return variables

        # 기타 unary 연산(prefix !, ~ 등)은 값쓰기 없음 → 그대로 통과
        return variables

    def interpret_function_call_statement(self, stmt, variables):
        function_expr = stmt.function_expr
        self.eval.evaluate_function_call_context(function_expr, variables, None, None)

        return variables

    def interpret_return_statement(self, stmt, variables, ret_acc=None):
        rexpr = stmt.return_expr
        r_val = self.eval.evaluate_expression(rexpr, variables, None, None)

        # NEW ─ 반드시 한 줄로 기록
        self.rec.record_return(
            line_no=stmt.src_line,
            return_expr=rexpr,
            return_val=r_val,
            fn_cfg=self.an.current_target_function_cfg
        )

        # exit-node 에 값 저장 (변경 없음)
        exit_node = self.an.current_target_function_cfg.get_exit_node()
        exit_node.return_vals[stmt.src_line] = r_val
        if ret_acc is not None:
            ret_acc.append(r_val)
            ret_acc.append("__STOP__")  # 실행 중단 플래그

        return variables

    def interpret_revert_statement(self, stmt, variables):
        return variables

    def interpret_break_statement(self, stmt, variables):
        return variables

    def interpret_continue_statement(self, stmt, variables):
        return variables

