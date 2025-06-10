# SolidityGuardian/Utils/CFG.py
import networkx as nx
from Interpreter.IR import *
from Domain.Variable import *

class CFGNode:
    def __init__(self, name,
                 condition_node=False,
                 condition_node_type=None,
                 branch_node=False,
                 is_true_branch=False,
                 fixpoint_evaluation_node=False,
                 loop_exit_node=False,
                 is_for_increment=False,
                 unchecked_block=False,
                 src_line=None):
        self.name = name

        self.condition_node = condition_node
        self.condition_expr = None
        self.condition_node_type = condition_node_type

        self.branch_node = branch_node
        self.is_true_branch = is_true_branch

        self.join_point_node = False
        self.fixpoint_evaluation_node = fixpoint_evaluation_node
        self.is_for_increment = is_for_increment
        self.loop_exit_node = loop_exit_node
        self.is_loop_body = False
        self.fixpoint_evaluation_node_vars = {} # 고정점 분석을 위한 while문 진입 전에 var 상태, join 하면서 변하는 변수의 상태

        self.unchecked_block = unchecked_block

        self.statements = []  # 기본 블록 내의 명령어 리스트
        self.variables = {}  # var_name -> Variables 객체

        self.function_exit_node = False
        self.return_vals = {}
        self.src_line = src_line

        self.function_evaluated=None

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
        self.function_type = function_type # constructor, fallback, receive, function
        self.function_name = function_name
        self.modifiers = {}
        self.related_variables = {}
        self.parameters: list[str] = []  # ←★ 추가
        self.return_types: list[SolType] = []   # 이름 없는 리턴
        self.return_vars : list = [] # 이름이 있는 리턴

        self.exit_node.function_exit_node = True


    def update_block(self, block_node):
        """
        FunctionCFG 내에서 블록을 업데이트하는 메서드.
        기존 그래프에 블록을 찾아 업데이트하거나, 새로운 블록이 추가된 경우 이를 반영.
        """
        # 그래프에서 block_node의 ID에 해당하는 노드를 찾아서 업데이트
        if self.graph.has_node(block_node):
            # 이미 해당 노드가 그래프에 있으면, 노드 정보를 업데이트
            existing_node = self.graph.nodes[block_node]
            # 필요에 따라 기존 노드의 속성을 업데이트 (여기선 덮어쓰기)
            self.graph.nodes[block_node].update(block_node.__dict__)

        else:
            raise ValueError(f"There is no {block_node} in functionCFG")

    def add_related_variable(self, variable_obj):
        self.related_variables[variable_obj.identifier] = variable_obj

    def get_predecessor_node(self, cfg_node):
        if self.graph.has_node(cfg_node) :
            if self.graph.has_predecessor(cfg_node) :
                return self.graph.predecessors(cfg_node)
            else :
                raise ValueError("There is no predecessor")
        else :
            raise ValueError(f"There is no node in graph about {cfg_node}")

    def get_related_variable(self, var_name):
        # 변수를 반환
        return self.related_variables.get(var_name, None)

    def integrate_modifier(self, modifier_cfg):
        # 1. 기존 function entry node의 successor들을 저장
        successors = list(self.graph.successors(self.get_entry_node()))

        # 2. 기존 function entry node의 successor를 modifier entry node로 설정
        self.graph.add_edge(self.get_entry_node(), modifier_cfg.get_entry_node())

        # 3. Modifier의 exit node를 기존 function entry node의 successor로 연결
        for succ in successors:
            self.graph.add_edge(modifier_cfg.get_exit_node(), succ)
            self.graph.remove_edge(self.get_entry_node(), succ)

    def get_true_block(self, condition_node):
        """
        주어진 조건 노드의 true branch를 통해 true block을 반환
        """
        successors = list(self.graph.successors(condition_node))
        for successor in successors:
            if self.graph.edges[condition_node, successor].get('condition', False):  # True branch
                return successor
        return None  # True block을 찾지 못한 경우 None 반환

    def get_false_block(self, condition_node):
        """
        주어진 조건 노드의 false branch를 통해 false block을 반환
        """
        successors = list(self.graph.successors(condition_node))
        for successor in successors:
            if not self.graph.edges[condition_node, successor].get('condition', False):  # False branch
                return successor
        return None  # False block을 찾지 못한 경우 None 반환