# SolidityGuardian/Utils/CFG.py
import networkx as nx
from Domain.IR import *
from Domain.Variable import *

class CFGNode:
    def __init__(self, name,
                 # ───── condition / branch role flags ─────────────────────────
                 condition_node: bool = False,
                 condition_node_type: str | None = None,  # "if" | "else_if" | "require" | "while" | "for" | "do_while" …
                 branch_node: bool = False,               # pruned-dummy/basic after a cond
                 is_true_branch: bool = False,
                 # ───── loop / join / sink flags ──────────────────────────────
                 join_point_node: bool = False,           # 🔹 명시적 조인 노드
                 fixpoint_evaluation_node: bool = False,  # φ / back-edge 합류 노드
                 loop_exit_node: bool = False,            # while/for False-branch 종착
                 is_for_increment: bool = False,          # for(i;cond;i++) 의 incr 블록
                 is_loop_body: bool = False,              # 루프 본문 블록 여부(선택)
                 # ───── misc ─────────────────────────────────────────────────
                 unchecked_block: bool = False,
                 src_line: int | None = None):
        self.name = name

        # condition / branch
        self.condition_node = condition_node
        self.condition_expr = None
        self.condition_node_type = condition_node_type  # 표준화: "else_if", "do_while" 사용
        self.branch_node = branch_node
        self.is_true_branch = is_true_branch

        # join / loop / φ
        self.join_point_node = join_point_node
        self.fixpoint_evaluation_node = fixpoint_evaluation_node
        self.loop_exit_node = loop_exit_node
        self.is_for_increment = is_for_increment
        self.is_loop_body = is_loop_body

        # φ/조인 관련 보조 env
        self.fixpoint_evaluation_node_vars = {}  # while-header 진입 시점 env 스냅샷
        self.join_baseline_env = None

        # unchecked
        self.unchecked_block = unchecked_block

        # payload
        self.statements: list[Statement] = []   # 블록 내 명령어
        self.variables: dict[str, Variables] = {}  # var_name -> Variables

        # sink kinds
        self.function_exit_node = False         # 함수 정상 종료(기본 EXIT)
        self.return_exit_node = False           # 🔹 명시적 return 전용 sink
        self.error_exit_node = False            # 🔹 revert/require 실패 전용 sink

        # return values (for exit aggregation)
        self.return_vals: dict[int, object] = {}

        self.src_line = src_line
        self.function_evaluated = None

    def add_variable_declaration_statement(self, typeObj, varName, initExpr, line_no):

        # Statement 생성
        variableDeclarationStatment = Statement(
            statement_type='variableDeclaration',
            type_obj=typeObj,
            var_name=varName,
            init_expr=initExpr,
            src_line=line_no
        )

        self.statements.append(variableDeclarationStatment)

    def add_assign_statement(self, exprLeft, exprOperator, exprRight, line_no):

        # Statement 생성
        assignment_stmt = Statement(
            statement_type='assignment',
            left=exprLeft,
            operator=exprOperator,
            right=exprRight,
            src_line=line_no
        )
        self.statements.append(assignment_stmt)

    def add_unary_statement(self, operand, operator, line_no):
        """
        ++x, --y, delete z 같은 단항 연산 전용 스테이트먼트를 블록에 추가.
        ─ operand  : Expression (피연산자)
        ─ operator : '++' | '--' | 'delete' …
        ─ line_no  : 소스 코드 라인 번호
        """
        unary_stmt = Statement(
            statement_type='unary',
            operand=operand,
            operator=operator,
            src_line=line_no,
        )
        self.statements.append(unary_stmt)

        # 변수 정보 업데이트는 update_left_Var 관련 함수에서 수행

    def add_function_call_statement(self, function_expr: Expression, line_no):
        """
        함수 호출문을 CFG에 추가합니다.
        :param function_expr: 함수 호출 Expression 객체
        """
        function_call_stmt = Statement(
            statement_type='functionCall',
            function_expr=function_expr,
            src_line=line_no
        )
        self.statements.append(function_call_stmt)

    def add_return_statement(self, return_expr: Expression, line_no):
        """
        반환 구문을 CFG에 추가하고, 반환 값을 업데이트합니다.
        :param return_expr: 반환할 Expression 객체
        """
        return_stmt = Statement(
            statement_type='return',
            return_expr=return_expr,
            src_line=line_no
        )
        self.statements.append(return_stmt)

    def add_continue_statement(self, line_no):
        continue_stmt = Statement(statement_type='continue',
                                  src_line=line_no)
        self.statements.append(continue_stmt)

    def add_break_statement(self, line_no):
        break_stmt = Statement(statement_type='break',
                               src_line=line_no)
        self.statements.append(break_stmt)

    def add_revert_statement(self, revert_identifier=None, string_literal=None, call_argument_list=None,
                             line_no=None):
        # 4. Revert 문장을 Statement 객체로 만들어서 현재 블록에 추가
        revert_statement = Statement(
            statement_type="revert",
            identifier=revert_identifier,
            string_literal=string_literal,
            arguments=call_argument_list,
            src_line=line_no
        )
        self.statements.append(revert_statement)

    def get_variable(self, var_name: str) -> Variables:
        """
        변수 이름을 받아 관련 변수를 반환합니다.
        :param var_name: 변수 이름 (identifier)
        :return: Variables 객체
        """
        return self.variables.get(var_name)

class CFG:
    def __init__(self, cfg_type):
        self.graph = nx.DiGraph()
        self.cfg_type = cfg_type
        self.entry_node = CFGNode("ENTRY")
        self.exit_node = CFGNode("EXIT")
        self.exit_node.function_exit_node = True  # 🔹 명시
        self.graph.add_node(self.entry_node)
        self.graph.add_node(self.exit_node)
        self.graph.add_edge(self.entry_node, self.exit_node)

    def get_entry_node(self):
        return self.entry_node

    def get_exit_node(self):
        return self.exit_node


class ContractCFG(CFG):
    def __init__(self, contract_name):
        super().__init__('contract')
        self.contract_name = contract_name
        self.state_variable_node = None

        self.structDefs = {}  # name -> StructDefinition 객체
        self.structVars = {} # name -> StructVariable 객체

        self.enumDefs = {} # name -> EnumDefinition 객체
        self.enumVars = {} # name -> EnumVariable 객체

        self.constructor = None  # FunctionCFG (Constructor Type)
        self.fallback = None
        self.receive = None

        #self.modifiers = {}  # name -> FunctionCFG
        self.functions = {}  # name -> FunctionCFG

        self.globals: dict[str, GlobalVariable] = {}

    def initialize_state_variable_node(self):
        self.state_variable_node = CFGNode('State_Variable')
        self.graph.add_node(self.state_variable_node)

        # 기존 entry node의 successor를 새로운 state variable node의 successor로 설정
        successors = list(self.graph.successors(self.entry_node))
        for succ in successors:
            self.graph.add_edge(self.state_variable_node, succ)
            self.graph.remove_edge(self.entry_node, succ)

        # 새로운 state variable node를 entry node의 successor로 설정
        self.graph.add_edge(self.entry_node, self.state_variable_node)


    # Enum 정의 추가
    def define_enum(self, enum_name, enum_def):
        if enum_name not in self.enumDefs:
            self.enumDefs[enum_name] = enum_def
        else:
            raise ValueError(f"Enum {enum_name} is already defined.")

    # Struct 정의 추가
    def define_struct(self, struct_def_obj):
        self.structDefs[struct_def_obj.struct_name] = struct_def_obj

    def add_enum_member(self, enum_name, member_name):
        if enum_name in self.enumDefs:
            self.enumDefs[enum_name].add_member(member_name)
        else:
            raise ValueError(f"Enum {enum_name} is not defined.")

    def add_struct_member(self, struct_def_name, var_name, var_obj):
        if struct_def_name in self.structDefs :
            self.structDefs[struct_def_name].add_member(var_name, var_obj)
        else :
            raise ValueError(f"Struct {struct_def_name} is not defined/")

    def add_state_variable(self, variable, expr=None, line_no=None): # variable : Variables, expr : Interval
        self.state_variable_node.add_assign_statement(
            exprLeft=variable,  # 좌변
            exprRight=expr,  # 우변 (Expression | None)
            exprOperator='=',  # 연산자
            line_no=line_no
        )

        self.state_variable_node.variables[variable.identifier] = variable

    def add_constant_variable(self, variable, expr=None):
        if not self.state_variable_node:
            self.state_variable_node = CFGNode('State_Variable')
            self.graph.add_node(self.state_variable_node)

        # 상수 변수 정보를 노드에 추가
        self.state_variable_node.variables[variable.identifier] = {'variable' : variable, 'expression' : expr}

    def add_constructor_to_cfg(self, constructor_cfg):
        # 1. 상태변수 노드의 successor가 생성자가 되도록 설정
        if self.state_variable_node:
            # 상태변수 노드의 모든 successor를 가져옴
            successors = list(self.graph.successors(self.state_variable_node))
            for succ in successors:
                # 기존 상태변수 노드의 successor를 생성자의 exit_node와 연결
                self.graph.add_edge(constructor_cfg.exit_node, succ)
                # 상태변수 노드의 기존 successor 간선 삭제
                self.graph.remove_edge(self.state_variable_node, succ)

            # 상태변수 노드를 생성자의 entry_node와 연결
            self.graph.add_edge(self.state_variable_node, constructor_cfg.entry_node)
        else:
            # 상태변수 노드가 없을 경우 entry_node와 생성자 entry_node 연결
            self.graph.add_edge(self.entry_node, constructor_cfg.entry_node)

        # 2. ContractCFG에 생성자 CFG 추가
        self.constructor = constructor_cfg

    #def get_modifier_cfg(self, modifier_name):
    #    # modifier가 존재하면 해당 CFG를 반환하고, 없으면 None을 반환
    #    return self.modifiers.get(modifier_name)

    def add_function_cfg(self, function_name, function_cfg):
        self.functions[function_name] = function_cfg

    def get_function_cfg(self, function_name):
        return self.functions[function_name]


class FunctionCFG(CFG):
    def __init__(self, function_type, function_name=None):
        super().__init__('function')
        self.function_type = function_type  # constructor, fallback, receive, function, modifier
        self.function_name = function_name
        self.modifiers: dict[str, "FunctionCFG"] = {}
        self.related_variables: dict[str, Variables] = {}
        self.parameters: list[str] = []
        self.return_types: list[SolType] = []
        self.return_vars: list[Variables] = []

        # ── 분리된 sink 노드들 생성(빌더가 연결) ────────────────────────
        self.exit_node.function_exit_node = True
        self.return_exit = CFGNode("RETURN")
        self.return_exit.return_exit_node = True
        self.error_exit = CFGNode("ERROR")
        self.error_exit.error_exit_node = True
        self.graph.add_node(self.return_exit)
        self.graph.add_node(self.error_exit)

    # ── helpers ----------------------------------------------------------
    def get_return_exit_node(self) -> CFGNode:
        return self.return_exit

    def get_error_exit_node(self) -> CFGNode:
        return self.error_exit

    def update_block(self, block_node: CFGNode):
        if self.graph.has_node(block_node):
            self.graph.nodes[block_node].update(block_node.__dict__)
        else:
            raise ValueError(f"There is no {block_node} in FunctionCFG")

    # 🔹 두 형태 모두 허용: (var_obj) 또는 (name, var_obj)
    def add_related_variable(self, *args):
        if len(args) == 1:
            var_obj = args[0]
            self.related_variables[var_obj.identifier] = var_obj
        elif len(args) == 2:
            name, var_obj = args
            self.related_variables[name] = var_obj
        else:
            raise TypeError("add_related_variable expects (var_obj) or (name, var_obj)")

    def get_predecessor_node(self, cfg_node):
        if not self.graph.has_node(cfg_node):
            raise ValueError(f"There is no node in graph about {cfg_node}")
        preds = list(self.graph.predecessors(cfg_node))
        if not preds:
            raise ValueError("There is no predecessor")
        return preds

    def get_related_variable(self, var_name):
        return self.related_variables.get(var_name, None)

    def integrate_modifier(self, modifier_cfg):
        successors = list(self.graph.successors(self.get_entry_node()))
        self.graph.add_edge(self.get_entry_node(), modifier_cfg.get_entry_node())
        for succ in successors:
            self.graph.add_edge(modifier_cfg.get_exit_node(), succ)
            self.graph.remove_edge(self.get_entry_node(), succ)

    def get_true_block(self, condition_node):
        successors = list(self.graph.successors(condition_node))
        for successor in successors:
            if self.graph.edges[condition_node, successor].get('condition', False) is True:
                return successor
        return None

    def get_false_block(self, condition_node):
        successors = list(self.graph.successors(condition_node))
        for successor in successors:
            if self.graph.edges[condition_node, successor].get('condition', False) is False:
                return successor
        return None