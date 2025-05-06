# SolidityGuardian/Analyzers/ContractAnalyzer.py
from Utils.Interval import *
from Utils.cfg import *
from Utils.util import *
from solcx import compile_source, install_solc
from collections import deque
import solcx
import re
import copy


class ContractAnalyzer:
    def __init__(self):
        self.addressManager = AddressSymbolicManager()

        self.full_code = None
        self.full_code_lines = {} # 라인별 코드를 저장하는 딕셔너리
        self.brace_count = {} # 각 라인에서 `{`와 `}`의 개수를 저장하는 딕셔너리

        self.current_start_line = None
        self.current_end_line = None

        self.current_context_type = None
        self.current_target_contract = None
        self.current_target_function = None
        self.current_target_function_cfg = None
        self.current_target_struct = None

        # for Multiple Contract
        self.contract_cfgs = {} # name -> CFG

        self.analysis_results = None

    """
    Prev analysis part
    """

    def update_code(self, start_line, end_line, new_code):
        """
        1) 기존 로직 그대로 유지: 라인들을 self.full_code_lines에 삽입/갱신
        2) 만약 new_code가 "@during-execution" 주석이라면, 기존 라인을 수정 (append) 하여 코드가 '밀리지' 않도록 처리
        """

        self.current_start_line = start_line
        self.current_end_line = end_line

        lines = new_code.split('\n')

        # 새 라인들 삽입/밀기 등
        if not self.full_code_lines:  # initialize
            for i, line_no in enumerate(range(start_line, end_line + 1)):
                self.full_code_lines[line_no] = lines[i]
                self.update_brace_count(line_no, lines[i])
        else:
            offset = end_line - start_line + 1

            # 1. 기존 라인 뒤로 밀기
            keys_to_shift = sorted(
                [line_no for line_no in self.full_code_lines.keys() if line_no >= start_line],
                reverse=True
            )
            for old_line_no in keys_to_shift:
                self.full_code_lines[old_line_no + offset] = self.full_code_lines.pop(old_line_no)
                self.update_brace_count(old_line_no + offset, self.full_code_lines[old_line_no + offset])

            # 2. 새로운 코드 라인 삽입
            for i, line_no in enumerate(range(start_line, end_line + 1)):
                self.full_code_lines[line_no] = lines[i]
                self.update_brace_count(line_no, lines[i])

        # 3. full_code 재구성
        self.full_code = '\n'.join(
            [self.full_code_lines[line_no] for line_no in sorted(self.full_code_lines.keys())]
        )

        # 4. analyze_context
        if new_code != "\n":
            self.analyze_context(start_line, new_code)

        self.compile_check()

    def compile_check(self):
        try:
            install_solc('0.8.0')  # 필요한 Solidity 컴파일러 버전을 설치합니다.
            compile_source(self.full_code)
        except solcx.exceptions.SolcError as e:
            print("Solidity 컴파일 오류: ", e)
        except Exception as e:
            print("예상치 못한 오류: ", e)

    def update_brace_count(self, line_number, code):
        open_braces = code.count('{')
        close_braces = code.count('}')

        # brace_count 업데이트
        self.brace_count[line_number] = {
            'open': open_braces,
            'close': close_braces,
            'cfg_node': None
        }

    def analyze_context(self, start_line, new_code):
        stripped_code = new_code.strip()

        if stripped_code.startswith('// @'):
            self.current_context_type = "debugUnit"
            self.current_target_contract = self.find_contract_context(start_line)
            if 'GlobalVar' in stripped_code :
                return
            self.current_target_function = self.find_function_context(start_line)
            return  # 이 함수 종료

        # 매 분석마다 초기화
        self.current_context_type = None
        self.current_target_contract = None
        self.current_target_function = None
        self.current_target_struct = None

        # 새로 추가된 코드 블록의 컨텍스트를 분석
        if stripped_code.endswith(';'):
            if 'while' in stripped_code :
                self.current_context_type = "doWhileWhile"
                pass

            parent_context = self.find_parent_context(start_line)
            if parent_context == "contract" : # 시작 규칙 : interactiveSourceUnit
                self.current_context_type = "stateVariableDeclaration"
                self.current_target_contract = self.find_contract_context(start_line)
            elif parent_context == "struct" : # 시작 규칙 : interactiveStructUnit
                self.current_context_type = "structMember"
                self.current_target_contract = self.find_contract_context(start_line)
                self.current_target_struct = self.find_struct_context(start_line)
            else : # constructor, function, --- # 시작 규칙 : interactiveBlockUnit
                self.current_context_type = "simpleStatement"
                self.current_target_contract = self.find_contract_context(start_line)
                self.current_target_function = self.find_function_context(start_line)

        elif ',' in stripped_code:
            # 함수 정의인지 확인 (괄호 열고 닫힌 경우는 함수 파라미터로 가정)
            if '(' in stripped_code and ')' in stripped_code:
                self.current_context_type = "functionDefinition"
                self.current_target_contract = self.find_contract_context(start_line)
                self.current_target_function = self.find_function_context(start_line)

            # enum인지 확인
            else:
                parent_context = self.find_parent_context(start_line)
                if parent_context == "enum":
                    self.current_context_type = "enumMember"
                    self.current_target_contract = self.find_contract_context(start_line)

        elif '{' in stripped_code: # definition 및 block 관련
            self.current_context_type = self.determine_top_level_context(new_code)

            if self.current_context_type == "contract" :
                return

            # 수정 필요할수도 있음
            self.current_target_contract = self.find_contract_context(start_line)
            self.current_target_function = self.find_function_context(start_line)

        # 최종적으로 context가 제대로 파악되지 않은 경우 기본값 처리
        if not self.current_target_contract:
            raise ValueError(f"Contract context not found for line {start_line}")
        if self.current_context_type == "simpleStatement" and not self.current_target_function:
            raise ValueError(f"Function context not found for simple statement at line {start_line}")

    def find_parent_context(self, line_number):
        close_brace_count = 0

        # 위로 거슬러 올라가면서 `{`와 `}`의 짝을 찾기
        for line in range(line_number - 1, 0, -1):
            brace_info = self.brace_count.get(line, {'open': 0, 'close': 0, 'cfg_node': None})
            open_braces = brace_info['open']
            close_braces = brace_info['close']

            if close_brace_count > 0:
                close_brace_count -= open_braces
                if close_brace_count <= 0:
                    close_brace_count = 0
            else:
                if open_braces > 0:
                    return self.determine_top_level_context(self.full_code_lines[line])
                close_brace_count += close_braces

        return "unknown"

    def find_contract_context(self, line_number):
        # 위로 거슬러 올라가면서 해당 라인이 속한 컨트랙트를 찾습니다.
        for line in range(line_number, 0, -1):
            brace_info = self.brace_count.get(line, {'open': 0, 'close': 0, 'cfg_node': None})
            if brace_info['open'] > 0 and brace_info['cfg_node']:
                context_type = self.determine_top_level_context(self.full_code_lines[line])
                if context_type == "contract":
                    return self.full_code_lines[line].split()[1]  # contract 이름 반환
        return None

    def find_function_context(self, line_number):
        # 위로 거슬러 올라가면서 해당 라인이 속한 함수를 찾습니다.
        for line in range(line_number, 0, -1):
            brace_info = self.brace_count.get(line, {'open': 0, 'close': 0, 'cfg_node': None})
            if brace_info['open'] > 0 and brace_info['cfg_node']:
                context_type = self.determine_top_level_context(self.full_code_lines[line])
                if context_type == "function":
                    # 함수 이름 뒤에 붙은 '('를 기준으로 함수 이름만 추출
                    function_declaration = self.full_code_lines[line]
                    function_name = function_declaration.split()[1]  # 첫 번째는 함수 선언, 두 번째는 함수 이름 포함
                    function_name = function_name.split('(')[0]  # 함수 이름만 추출
                    return function_name
        return None

    def find_struct_context(self, line_number):
        # 위로 거슬러 올라가면서 해당 라인이 속한 함수를 찾습니다.
        for line in range(line_number, 0, -1):
            brace_info = self.brace_count.get(line, {'open': 0, 'close': 0, 'cfg_node': None})
            if brace_info['open'] > 0 and brace_info['cfg_node']:
                context_type = self.determine_top_level_context(self.full_code_lines[line])
                if context_type == "struct":
                    return self.full_code_lines[line].split()[1]

    def determine_top_level_context(self, code_line):
        try:
            # 코드 라인의 내용에 따라 최상위 컨텍스트를 결정
            stripped_code = code_line.strip()

            if stripped_code.startswith("contract"):
                return "contract"
            elif stripped_code.startswith("interface"):
                return "interface"
            elif stripped_code.startswith("library"):
                return "library"
            elif stripped_code.startswith("function"):
                return "function"
            elif stripped_code.startswith("constructor"):
                return "constructor"
            elif stripped_code.startswith("fallback"):
                return "fallback"
            elif stripped_code.startswith("receive"):
                return "receive"
            elif stripped_code.startswith("modifier"):
                return "modifier"
            elif stripped_code.startswith("struct"):
                return "struct"
            elif stripped_code.startswith("enum"):
                return "enum"
            elif stripped_code.startswith("event"):
                return "event"
            elif stripped_code.startswith("if"):
                return "if"
            elif stripped_code.startswith("else if"):
                return "else_if"
            elif stripped_code.startswith("else"):
                return "else"
            elif stripped_code.startswith("for"):
                return "for"
            elif stripped_code.startswith("while"):
                return "while"
            elif stripped_code.startswith("do"):
                return "do_while"
            elif stripped_code.startswith("try"):
                return "try"
            elif stripped_code.startswith("catch"):
                return "catch"
            elif stripped_code.startswith("assembly"):
                return "assembly"
            else:
                raise ValueError(f"Unknown context type for line: {code_line}")

        except ValueError as e:
            print(f"Error: {e}")
            return "unknown"

    def get_full_code(self):
        return self.full_code

    def get_current_context_type(self):
        return self.current_context_type

    """
    cfg part    
    """

    def make_contract_cfg(self, contract_name: str):
        if contract_name in self.contract_cfgs:
            return

        cfg = ContractCFG(contract_name)

        # ---------- 기본(Global) 값 ---------
        cfg.globals = {
            "block.basefee": GlobalVariable("block.basefee",
                                            UnsignedIntegerInterval(0, 0, 256),
                                            SolType(elementaryTypeName="uint")),
            "block.blobbasefee": GlobalVariable("block.blobbasefee",
                                                UnsignedIntegerInterval(0, 0, 256),
                                                SolType(elementaryTypeName="uint")),
            "block.chainid": GlobalVariable("block.chainid",
                                            UnsignedIntegerInterval(0, 0, 256),
                                            SolType(elementaryTypeName="uint")),
            "block.coinbase": GlobalVariable("block.coinbase",
                                             "symbolicAddress 0",
                                             SolType(elementaryTypeName="address")),
            "block.difficulty": GlobalVariable("block.difficulty",
                                               UnsignedIntegerInterval(0, 0, 256),
                                               SolType(elementaryTypeName="uint")),
            "block.gaslimit": GlobalVariable("block.gaslimit",
                                             UnsignedIntegerInterval(0, 0, 256),
                                             SolType(elementaryTypeName="uint")),
            "block.number": GlobalVariable("block.number",
                                           UnsignedIntegerInterval(0, 0, 256),
                                           SolType(elementaryTypeName="uint")),
            "block.prevrandao": GlobalVariable("block.prevrandao",
                                               UnsignedIntegerInterval(0, 0, 256),
                                               SolType(elementaryTypeName="uint")),
            "block.timestamp": GlobalVariable("block.timestamp",
                                              UnsignedIntegerInterval(0, 0, 256),
                                              SolType(elementaryTypeName="uint")),
            "msg.sender": GlobalVariable("msg.sender",
                                         "symbolicAddress 101",
                                         SolType(elementaryTypeName="address")),
            "msg.value": GlobalVariable("msg.value",
                                        UnsignedIntegerInterval(0, 0, 256),
                                        SolType(elementaryTypeName="uint")),
            "tx.gasprice": GlobalVariable("tx.gasprice",
                                          UnsignedIntegerInterval(0, 0, 256),
                                          SolType(elementaryTypeName="uint")),
            "tx.origin": GlobalVariable("tx.origin",
                                        "symbolicAddress 100",
                                        SolType(elementaryTypeName="address")),
        }

        # 나머지 초기화·등록 로직 동일 …
        self.contract_cfgs[contract_name] = cfg
        self.brace_count[self.current_start_line]['cfg_node'] = cfg

    def get_contract_cfg(self, contract_name):
        return self.contract_cfgs.get(contract_name)

    # for interactiveEnumDefinition in Solidity.g4
    def process_enum_definition(self, enum_name):
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 새로운 EnumDefinition 객체 생성
        enum_def = EnumDefinition(enum_name)
        contract_cfg.define_enum(enum_name, enum_def)

        # brace_count 업데이트
        self.brace_count[self.current_start_line]['cfg_node'] = enum_def

    def process_enum_item(self, items):
        # 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # brace_count에서 가장 최근의 enum 정의를 찾습니다.
        enum_def = None
        for line in reversed(range(self.current_start_line + 1)):
            context = self.brace_count.get(line)
            if context and 'cfg_node' in context and isinstance(context['cfg_node'], EnumDefinition):
                enum_def = context['cfg_node']
                break

        if enum_def is not None:
            # EnumDefinition에 아이템 추가
            for item in items:
                enum_def.add_member(item)
        else:
            raise ValueError(f"Unable to find EnumDefinition context for line {self.current_start_line}")

    # for interactiveStructDefinition in Solidity.g4
    def process_struct_definition(self, struct_name):
        contract_cfg = self.contract_cfgs[self.current_target_contract]

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        struct_def = StructDefinition(struct_name=struct_name)

        contract_cfg.define_struct(struct_def)

        # 10. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # brace_count 업데이트
        self.brace_count[self.current_start_line]['structs'] = contract_cfg.structs

    def process_struct_member(self, var_name, type_obj):
        # 1. 현재 타겟 컨트랙트의 CFG를 가져옴
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. 현재 타겟 구조체를 확인하고 멤버 추가
        if not self.current_target_struct:
            raise ValueError("No target struct to add members to.")

        contract_cfg.add_struct_member(self.current_target_struct, var_name, type_obj)

        # 10. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

    def process_state_variable(self, variable_obj, init_expr=None):
        # 1. 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 우변 표현식을 저장하기 위해 init_expr를 확인
        if init_expr is None: # 초기화가 없으면
            if isinstance(variable_obj, ArrayVariable) :
                if variable_obj.typeInfo.arrayBaseType.startswith("int") :
                    variable_obj.initialize_elements(IntegerInterval.bottom())
                elif variable_obj.typeInfo.arrayBaseType.startswith("uint") :
                    variable_obj.initialize_elements(UnsignedIntegerInterval.bottom())
                elif variable_obj.typeInfo.arrayBaseType.startswith("bool") :
                    variable_obj.initialize_elements(BoolInterval.bottom())
                elif variable_obj.typeInfo.arrayBaseType in ["address", "address payable", "string", "bytes", "Byte", "Fixed", "Ufixed"] :
                    variable_obj.initialize_elements_of_not_abstracted_type(variable_obj.identifier)
            elif isinstance(variable_obj, StructVariable) :
                if variable_obj.typeInfo.structTypeName in contract_cfg.structDefs.keys():
                    struct_def = contract_cfg.structDefs[variable_obj.typeInfo.structTypeName]
                    variable_obj.initialize_struct(struct_def)
                else :
                    ValueError(f"This struct def {variable_obj.typeInfo.structTypeName} is undefined")
            elif isinstance(variable_obj, MappingVariable) :
                pass
            elif isinstance(variable_obj,EnumVariable) :
                pass
            elif variable_obj.typeCategory == "elementary" :
                if variable_obj.elementaryTypeName.startswith("int", "uint", "bool") :
                    variable_obj.value = self.calculate_default_interval(variable_obj.elementaryTypeName)
                elif variable_obj.elementaryTypeName in ["address", "address payable", "string", "bytes", "Byte", "Fixed", "Ufixed"] :
                    variable_obj.value = str('symbol' + variable_obj.identifier)
        else : # 초기화 식이 있으면
            if isinstance(variable_obj, ArrayVariable) :
                inlineArrayValues = self.evaluate_expression(init_expr, contract_cfg.state_variable_node.variables, None, None)

                for value in inlineArrayValues :
                    variable_obj.elements.append(value)
            elif isinstance(variable_obj, StructVariable) : # 관련된 경우 없을듯
                pass
            elif isinstance(variable_obj, MappingVariable) : # 관련된 경우 없을 듯
                pass
            elif variable_obj.typeCategory == "elementary" :
                variable_obj.value = self.evaluate_expression(init_expr, contract_cfg.state_variable_node.variables, None, None)

        # 4. 상태 변수를 ContractCFG에 추가
        contract_cfg.add_state_variable(variable_obj, expr=init_expr)

        # 5. ContractCFG에 있는 모든 FunctionCFG에 상태 변수 추가
        for function_cfg in contract_cfg.functions.values():
            function_cfg.add_related_variable(variable_obj.identifier, variable_obj)

        # 6. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 7. brace_count 업데이트
        self.brace_count[self.current_start_line]['cfg_node'] = contract_cfg.state_variable_node

    def process_constant_variable(self, variable_obj, init_expr):
        # 1. 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. abstract interpretation 수행 (상수이므로 반드시 초기화 식이 있어야 함)
        if init_expr:
            interval_result = self.evaluate_expression(init_expr)
            if interval_result is not None:
                variable_obj.value = interval_result
            else:
                raise ValueError(f"Unable to evaluate constant expression for {variable_obj.identifier}")
        else:
            raise ValueError(f"Constant variable {variable_obj.identifier} must have an initializer.")

        # 4. 상수임을 표시
        variable_obj.isConstant = True

        # 3. 상태 변수를 ContractCFG에 추가
        contract_cfg.add_state_variable(variable_obj.identifier, variable_obj)

        # 5. brace_count 업데이트
        self.brace_count[self.current_start_line]['cfg_node'] = contract_cfg.state_variable_node

    def process_modifier_definition(self, modifier_name, parameters):
        # 현재 컨텍스트에서 타겟 컨트랙트를 가져옴
        contract_cfg = self.contract_cfgs[self.current_target_contract]

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # Modifier에 대한 FunctionCFG 생성
        modifier_cfg = FunctionCFG(function_type='modifier', function_name=modifier_name)

        # 파라미터가 있을 경우, 이를 FunctionCFG에 추가
        for var_name, var_type_info in parameters.items():
            modifier_cfg.add_related_variable(var_name, var_type_info)

        # 현재 state_variable_node에서 상태 변수를 가져와 related_variables에 추가
        if contract_cfg.state_variable_node:
            for var_name, var_info in contract_cfg.state_variable_node.variables.items():
                modifier_cfg.add_related_variable(var_name, var_info)

        # Modifier CFG를 ContractCFG에 추가
        contract_cfg.add_function_cfg(modifier_cfg)

        # 10. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # brace_count 업데이트 (필요시)
        self.brace_count[self.current_start_line]['cfg_node'] = modifier_cfg.get_entry_node()

    def process_modifier_invocation(self, function_cfg, modifier_name):
        # 현재 타겟 컨트랙트의 CFG를 가져옴
        contract_cfg = self.contract_cfgs[self.current_target_contract]

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # ContractCFG에서 modifier CFG를 가져옴
        modifier_cfg = contract_cfg.get_modifier_cfg(modifier_name)

        if not modifier_cfg:
            raise ValueError(f"Modifier {modifier_name} not found in contract {self.current_target_contract}")

        # Modifier를 function CFG에 통합 (entry와 exit 노드 연결)
        function_cfg.integrate_modifier(modifier_cfg)

        # function_cfg에 modifier 이름 추가
        function_cfg.modifiers[modifier_name] = modifier_cfg

        # 9. function_cfg 결과를 contract_cfg에 반영
        contract_cfg.functions[self.current_target_function] = function_cfg

        # 10. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

    def process_constructor_definition(self, constructor_name, parameters, modifiers):
        # 현재 컨텍스트에서 타겟 컨트랙트를 가져옴
        contract_cfg = self.contract_cfgs[self.current_target_contract]

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # Constructor에 대한 FunctionCFG 생성
        constructor_cfg = FunctionCFG(function_type='constructor', function_name=constructor_name)

        # 파라미터가 있을 경우, 이를 FunctionCFG에 추가
        for variable in parameters:
            constructor_cfg.add_related_variable(variable)

        # Modifier가 있을 경우 이를 FunctionCFG에 추가
        for modifier_name in modifiers:
            self.process_modifier_invocation(constructor_cfg, modifier_name)

        # Constructor CFG를 ContractCFG에 추가
        contract_cfg.add_constructor_to_cfg(constructor_cfg)

        # 10. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 현재 state_variable_node에서 상태 변수를 가져와 related_variables에 추가
        if contract_cfg.state_variable_node:
            for var_name, var_info in contract_cfg.state_variable_node.variables.items():
                constructor_cfg.add_related_variable(var_name, var_info)

        self.brace_count[self.current_start_line]['cfg_node'] = constructor_cfg.get_entry_node()

    def process_function_definition(self, function_name, parameters, modifiers, returns):
        # 1. 현재 타겟 컨트랙트의 CFG를 가져옴
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. 함수에 대한 FunctionCFG 생성
        function_cfg = FunctionCFG(function_type='function', function_name=function_name)

        # 3. 파라미터 처리
        for type_obj, var_name in parameters:
            variable_obj = None

            # 타입에 따라 적절한 변수 클래스를 생성
            if type_obj.typeCategory == 'array':
                # 배열 타입인 경우 ArrayVariable 생성
                variable_obj = ArrayVariable(
                    identifier=var_name,
                    base_type=type_obj.arrayBaseType,
                    array_length=type_obj.arrayLength,
                    scope="local"
                )

                baseType = type_obj.arrayBaseType

                # 배열 요소 초기화
                if baseType.startswith('int') :
                    length = int(baseType[3:]) if baseType != "int" else 256
                    variable_obj.initialize_elements(IntegerInterval.bottom(length))  # 기본 interval 설정
                elif baseType.startswith('uint') :
                    length = int(baseType[4:]) if baseType != "int" else 256
                    variable_obj.initialize_elements(UnsignedIntegerInterval.bottom(length))  # 기본 interval 설정
                elif baseType == 'bool' :
                    variable_obj.initialize_elements(BoolInterval.bottom())
                elif baseType in ["address", "address payable", "string", "bytes", "Byte", "Fixed", "Ufixed"] :
                    variable_obj.initialize_elements_of_not_abstracted_type(var_name)

            elif type_obj.typeCategory == 'struct':
                if type_obj.structTypeName in contract_cfg.structDefs :
                    struct_def = contract_cfg.structDefs[type_obj.structTypeName]

                    variable_obj = StructVariable(
                        identifier = var_name,
                        struct_type = type_obj.structTypeName,
                        socpe="local" # 이거 나중에 storage인지 memory인지 보고 고쳐야됨
                    )

                    variable_obj.initialize_struct(struct_def)

                else :
                    raise ValueError (f"This struct definition {type_obj.structTypeName} is not defined")
            elif type_obj.typeCategory == "elementary":
                # 기본 타입인 경우 Variables 객체 생성
                variable_obj = Variables(identifier=var_name, scope="local")
                variable_obj.typeInfo = type_obj  # SolType 객체를 typeInfo로 설정

                if type_obj.elementaryTypeName.startswith('int', 'uint', 'bool') :
                    variable_obj.value = self.calculate_default_interval(type_obj.elementaryTypeName)
                elif type_obj.elementaryTypeName in ["address", "address payable", "string", "bytes", "Byte", "Fixed", "Ufixed"] :
                    variable_obj.value = str("symbol" + var_name)

        # 4. Modifier 처리 및 CFG 통합
        for modifier_name in modifiers:
            self.process_modifier_invocation(function_cfg, modifier_name)

        # 5. 반환 타입 처리 (있다면)
        if returns:
            for variable in returns:
                function_cfg.add_related_variable(variable)

        # 현재 state_variable_node에서 상태 변수를 가져와 related_variables에 추가
        if contract_cfg.state_variable_node:
            for var_name, variable in contract_cfg.state_variable_node.variables.items():
                function_cfg.add_related_variable(variable)

        # 9. function_cfg 결과를 contract_cfg에 반영
        contract_cfg.functions[function_name] = function_cfg

        # 10. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 7. brace_count에 CFG 노드 정보 업데이트 (함수의 시작 라인 정보 사용)
        self.brace_count[self.current_start_line]['cfg_node'] = function_cfg.get_entry_node()

    def process_variable_declaration(self, type_obj, var_name, init_expr=None):
        # 1. 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. 현재 타겟 함수의 CFG 가져오기
        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to add variables to.")

        # 좌변 변수 객체 생성
        variable_obj = None
        if type_obj.typeCategory == 'array':
            # 배열 타입인 경우 ArrayVariable 생성
            base_type = type_obj.arrayBaseType
            array_length = type_obj.arrayLength
            variable_obj = ArrayVariable(identifier=var_name, base_type=base_type,
                                         array_length=array_length, scope='local')

        elif type_obj.typeCategory == 'struct':
            # 구조체 타입인 경우 StructVariable 생성
            struct_type = type_obj.structTypeName
            variable_obj = StructVariable(identifier=var_name, struct_type=struct_type, scope='local')

        elif type_obj.typeCategry == 'Enum' :
            struct_type = type_obj.enumTypeName
            variable_obj = EnumVariable(identifier=var_name, enum_type=struct_type, scope='local')

        else:
            # 기본 타입인 경우 Variables 객체 생성
            variable_obj = Variables(identifier=var_name, scope="local")
            variable_obj.typeInfo = type_obj  # SolType 객체를 typeInfo로 설정

        # 3. 현재 블록의 CFG 노드 가져오기
        current_block = self.get_current_block()

        # 우변 표현식을 저장하기 위해 init_expr를 확인
        if init_expr is None:  # 초기화가 없으면
            if isinstance(variable_obj, ArrayVariable):
                if variable_obj.typeInfo.arrayBaseType.startswith("int"):
                    variable_obj.initialize_elements(IntegerInterval.bottom())
                elif variable_obj.typeInfo.arrayBaseType.startswith("uint"):
                    variable_obj.initialize_elements(UnsignedIntegerInterval.bottom())
                elif variable_obj.typeInfo.arrayBaseType.startswith("bool"):
                    variable_obj.initialize_elements(BoolInterval.bottom())
                elif variable_obj.typeInfo.arrayBaseType in ["address", "address payable", "string", "bytes", "Byte",
                                                             "Fixed", "Ufixed"]:
                    variable_obj.initialize_elements_of_not_abstracted_type(variable_obj.identifier)
            elif isinstance(variable_obj, StructVariable):
                if variable_obj.typeInfo.structTypeName in contract_cfg.structDefs:
                    struct_def = contract_cfg.structDefs[variable_obj.typeInfo.structTypeName]
                    variable_obj.initialize_struct(struct_def)
                else:
                    ValueError(f"This struct def {variable_obj.struct_type} is undefined")
            elif isinstance(variable_obj, MappingVariable): # 동적으로 할당되서 선언이 딱히 없음
                pass
            elif isinstance(variable_obj, EnumVariable):
                if variable_obj.typeInfo.enumTypeName in contract_cfg.enumDefs :
                    enum_def = contract_cfg.enumDefs[variable_obj.typeInfo.enumTypeName]
                    variable_obj.value = enum_def.members[0]
                    variable_obj.valueIndex = 0

            elif variable_obj.typeCategory == "elementary":
                if variable_obj.elementaryTypeName.startswith("int", "uint", "bool"):
                    variable_obj.value = self.calculate_default_interval(variable_obj.elementaryTypeName)
                elif variable_obj.elementaryTypeName in ["address", "address payable", "string", "bytes", "Byte",
                                                         "Fixed", "Ufixed"]:
                    variable_obj.value = str('symbol' + variable_obj.identifier)

        else : # 초기화 식이 있으면
            if isinstance(variable_obj, ArrayVariable) :
                inlineArrayValues = self.evaluate_expression(init_expr, current_block.variables, None)
                for value in inlineArrayValues :
                    variable_obj.elements.append(value)
            elif isinstance(variable_obj, StructVariable) : # 관련된 경우 있을 것 같긴 함
                pass
            elif isinstance(variable_obj, MappingVariable) : # 관련된 경우 없을 듯
                pass
            elif isinstance(variable_obj, EnumVariable) : # 관련된 경우 있을 것 같긴 함
                enum_val = self.evaluate_expression(init_expr, current_block.variables, None)

                if isinstance(enum_val, IntegerInterval):
                    # int값으로 들어온 경우 -> 만약 min==max라면 유효 범위인지 검사
                    if enum_val.min_value == enum_val.max_value:
                        index_val = enum_val.min_value
                        # enum_def = contract_cfg.enumDefs[variable_obj.typeInfo.enumTypeName]
                        # 여기서 index_val이 enum_def.members 범위 내인지?
                        # (논문 스코프에선 간단히 pass 해도 됨)
                        variable_obj.valueIndex = index_val
                        variable_obj.value = f"EnumIndex({index_val})"
                    else:
                        # 범위가 넓으면 symbolic
                        variable_obj.value = f"SymbolicEnumInterval({enum_val})"

                elif isinstance(enum_val, str):
                    # 만약 "RED" 처럼 들어왔을 때
                    # enum_def = contract_cfg.enumDefs[variable_obj.typeInfo.enumTypeName]
                    # if enum_val in enum_def.members => variable_obj.valueIndex = ...
                    variable_obj.value = enum_val
                else:
                    # 나머지는 symbolic
                    variable_obj.value = f"symbolicEnum({enum_val})"

            elif variable_obj.typeCategory == "elementary" :
                variable_obj.value = self.evaluate_expression(init_expr, current_block.variables, None)

        # cfg node에 문장 추가
        current_block.variables[variable_obj.identifier] = variable_obj
        current_block.add_variable_declaration_statement(type_obj, var_name, init_expr)

        # function_cfg에 지역변수 추가
        self.current_target_function_cfg.add_related_variable(variable_obj)

        # 11. current_block을 function CFG에 반영
        self.current_target_function_cfg.update_block(current_block)  # 변경된 블록을 반영

        # 12. function_cfg 결과를 contract_cfg에 반영
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg

        # 13. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 14. brace_count에 CFG 노드 정보 업데이트 (함수의 시작 라인 정보 사용)
        self.brace_count[self.current_start_line]['cfg_node'] = current_block

        self.current_target_function_cfg = None


    def process_assignment_expression(self, expr):
        # 1. 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. 현재 타겟 함수의 CFG 가져오기
        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to add variables to.")

        # 3. 현재 블록의 CFG 노드 가져오기
        current_block = self.get_current_block()


        # assignment에 대한 abstract interpretation 수행
        rExpVal = self.evaluate_expression(expr.right, current_block.variables, None, None)
        self.update_left_var(expr.left, rExpVal, expr.operator, current_block.variables, None, None)

        current_block.add_assign_statement(expr.left, expr.operator, expr.right)

        # 9. current_block을 function CFG에 반영
        self.current_target_function_cfg.update_block(current_block)  # 변경된 블록을 반영

        # 10. function_cfg 결과를 contract_cfg에 반영
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg

        # 11. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 12. brace_count에 CFG 노드 정보 업데이트 (함수의 시작 라인 정보 사용)
        self.brace_count[self.current_start_line]['cfg_node'] = current_block

    def process_unary_prefix_operation(self, expr):
        # 1. 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. 현재 타겟 함수의 CFG 가져오기
        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to add variables to.")

        # 3. 현재 블록의 CFG 노드 가져오기
        current_block = self.get_current_block()

        literalExp = Expression(literal=1, context='LiteralExpContext')

        if expr.operator == "++" :
            self.update_left_var(expr.expression, 1, '+=', current_block.variables, None, None)
            current_block.add_assign_statement(expr.expression, '+=', literalExp)
        elif expr.operator == "--" :
            self.update_left_var(expr.expression, 1, '-=', current_block.variables, None, None)
            current_block.add_assign_statement(expr.expression, '-=', literalExp)

        # 10. current_block을 function CFG에 반영
        self.current_target_function_cfg.update_block(current_block)  # 변경된 블록을 반영

        # 11. function_cfg 결과를 contract_cfg에 반영
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg

        # 12. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 12. brace_count에 CFG 노드 정보 업데이트 (함수의 시작 라인 정보 사용)
        self.brace_count[self.current_start_line]['cfg_node'] = current_block

        self.current_target_function_cfg = None

    def process_unary_suffix_operation(self, expr):
        # 1. 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. 현재 타겟 함수의 CFG 가져오기
        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to add variables to.")

        # 3. 현재 블록의 CFG 노드 가져오기
        current_block = self.get_current_block()


        literalExp = Expression(literal=1, context='LiteralExpContext')

        if expr.operator == "++":
            self.update_left_var(expr.expression, 1, '+=', current_block.variables, None, None)
            current_block.add_assign_statement(expr.expression, '+=', literalExp)
        elif expr.operator == "--":
            self.update_left_var(expr.expression, 1, '-=', current_block.variables, None, None)
            current_block.add_assign_statement(expr.expression, '-=', literalExp)

        # 10. current_block을 function CFG에 반영
        self.current_target_function_cfg.update_block(current_block)  # 변경된 블록을 반영

        # 11. function_cfg 결과를 contract_cfg에 반영
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg

        # 12. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 12. brace_count에 CFG 노드 정보 업데이트 (함수의 시작 라인 정보 사용)
        self.brace_count[self.current_start_line]['cfg_node'] = current_block

        self.current_target_function_cfg = None

    def process_function_call(self, expr):
        """
        함수 호출을 처리하는 메소드입니다.
        :param expr: Expression 객체 (FunctionCall)
        :return: 함수 호출 결과 (Interval 또는 None)
        """

        # 1. 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. 현재 타겟 함수의 CFG 가져오기
        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to add variables to.")

        current_block = self.get_current_block()

        # 3. 함수 표현식 가져오기
        function_expr = expr.function

        _ = self.evaluate_function_call_context(function_expr, current_block.variables, None, None)

        current_block.add_function_call_statement(function_expr)

        # 10. current_block을 function CFG에 반영
        self.current_target_function_cfg.update_block(current_block)  # 변경된 블록을 반영

        # 11. function_cfg 결과를 contract_cfg에 반영
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg

        # 12. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 12. brace_count에 CFG 노드 정보 업데이트 (함수의 시작 라인 정보 사용)
        self.brace_count[self.current_start_line]['cfg_node'] = current_block

        self.current_target_function_cfg = None

    def process_payable_function_call(self, expr):
        # Handle payable function calls
        pass

    def process_function_call_options(self, expr):
        # Handle function calls with options
        pass

    def process_if_statement(self, condition_expr):
        # 1. 현재 컨트랙트와 함수의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to process the if statement.")

        # 2. 현재 블록 가져오기
        current_block = self.get_current_block()

        # 3. 조건식 블록 생성 및 평가
        condition_block = CFGNode(name=f"if_condition_{self.current_start_line}",
                                  condition_node=True,
                                  condition_node_type="if")
        condition_block.condition_expr = condition_expr
        # 7. True 분기에서 변수 상태 복사 및 업데이트
        condition_block.variables = self.copy_variables(current_block.variables)

        # 4. brace_count 업데이트 - 존재하지 않으면 초기화
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = condition_block

        # 5. True 분기 블록 생성
        true_block = CFGNode(name=f"if_true_{self.current_start_line}")

        # 7. True 분기에서 변수 상태 복사 및 업데이트
        true_block.variables = self.copy_variables(condition_block.variables)

        self.update_variables_with_condition(true_block.variables, condition_expr, is_true_branch=True)

        false_block = CFGNode(name=f"if_false_{self.current_start_line}")
        false_block.variables = self.copy_variables(condition_block.variables)
        self.update_variables_with_condition(false_block.variables, condition_expr, is_true_branch=False)

        # 8. 현재 블록의 후속 노드 처리 (기존 current_block의 successors를 가져옴)
        successors = list(self.current_target_function_cfg.graph.successors(current_block))

        # 기존 current_block과 successor들의 edge를 제거
        for successor in successors:
            self.current_target_function_cfg.graph.remove_edge(current_block, successor)

        # 9. CFG 노드 추가
        self.current_target_function_cfg.graph.add_node(condition_block)
        self.current_target_function_cfg.graph.add_node(true_block)
        self.current_target_function_cfg.graph.add_node(false_block)

        # 10. 조건 블록과 True/False 분기 연결
        self.current_target_function_cfg.graph.add_edge(current_block, condition_block)
        self.current_target_function_cfg.graph.add_edge(condition_block, true_block, condition=True)
        self.current_target_function_cfg.graph.add_edge(condition_block, false_block, condition=False)

        # 11. True 분기 후속 노드 연결
        for successor in successors:
            self.current_target_function_cfg.graph.add_edge(true_block, successor)
            self.current_target_function_cfg.graph.add_edge(false_block, successor)

        # 11. function_cfg 결과를 contract_cfg에 반영
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg

        # 12. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 12. brace_count에 CFG 노드 정보 업데이트 (함수의 시작 라인 정보 사용)
        self.brace_count[self.current_start_line]['cfg_node'] = condition_block

        self.current_target_function_cfg = None

    def process_else_if_statement(self, condition_expr):
        # 1. 현재 컨트랙트와 함수의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to process the else-if statement.")

        # 2. 이전 조건 노드를 가져와서 부정된 조건을 처리
        previous_condition_node = self.find_corresponding_condition_node()
        if not previous_condition_node:
            raise ValueError("No previous if or else if node found for else-if statement.")

        # --- 0) 기존 successor 기억
        old_succs = [
            s for s in self.current_target_function_cfg.graph.successors(previous_condition_node)
            if self.current_target_function_cfg.graph.get_edge_data(previous_condition_node, s).get('condition') is True
        ]

        # 3. 이전 조건 노드의 False 분기 제거
        false_successors = list(self.current_target_function_cfg.graph.successors(previous_condition_node))
        for successor in false_successors:
            edge_data = self.current_target_function_cfg.graph.get_edge_data(previous_condition_node, successor)
            if edge_data.get('condition') is False:
                self.current_target_function_cfg.graph.remove_edge(previous_condition_node, successor)

                # 2) false_block -> successor edge들도 제거
                succs_of_false = list(self.current_target_function_cfg.graph.successors(successor))
                for s in succs_of_false:
                    self.current_target_function_cfg.graph.remove_edge(successor, s)

        # 3. 이전 조건 노드에서 False 분기 처리 (가상의 블록)
        temp_variables = self.copy_variables(previous_condition_node.variables)
        self.update_variables_with_condition(temp_variables, previous_condition_node.condition_expr,
                                             is_true_branch=False)

        # 4. else if 조건식 블록 생성
        condition_block = CFGNode(name=f"else_if_condition_{self.current_start_line}",
                                  condition_node=True,
                                  condition_node_type="else if")
        condition_block.condition_expr = condition_expr

        # 5. brace_count 업데이트 - 존재하지 않으면 초기화
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = condition_block

        # 6. True 분기 블록 생성
        true_block = CFGNode(name=f"else_if_true_{self.current_start_line + 1}")

        # 7. True 분기에서 변수 상태 복사 및 업데이트
        true_block.variables = self.copy_variables(temp_variables)
        self.update_variables_with_condition(true_block.variables, condition_expr, is_true_branch=True)

        # 5. False 분기 블록 생성
        false_block = CFGNode(name=f"else_if_false_{self.current_start_line}")
        false_block.variables = self.copy_variables(temp_variables)
        self.update_variables_with_condition(false_block.variables, condition_expr,
                                             is_true_branch=False)

        # 8. 이전 조건 블록과 새로운 else_if_condition 블록 연결
        self.current_target_function_cfg.graph.add_edge(previous_condition_node, condition_block, condition=False)

        # 9. 새로운 조건 블록과 True 블록 연결
        self.current_target_function_cfg.graph.add_node(condition_block)
        self.current_target_function_cfg.graph.add_node(true_block)
        self.current_target_function_cfg.graph.add_node(false_block)

        self.current_target_function_cfg.graph.add_edge(condition_block, true_block, condition=True)
        self.current_target_function_cfg.graph.add_edge(condition_block, false_block, condition=False)

        # --- 2) edge 재연결
        for s in old_succs:
            self.current_target_function_cfg.graph.add_edge(true_block, s)
            self.current_target_function_cfg.graph.add_edge(false_block, s)

        # 11. function_cfg 결과를 contract_cfg에 반영
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg

        # 12. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 12. brace_count에 CFG 노드 정보 업데이트 (함수의 시작 라인 정보 사용)
        self.brace_count[self.current_start_line]['cfg_node'] = condition_block

        self.current_target_function_cfg = None

    def process_else_statement(self):
        # 1. 현재 컨트랙트와 함수의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to process the else statement.")

        # 2. 대응되는 if 또는 else if의 조건 노드 찾기
        condition_node = self.find_corresponding_condition_node()
        if not condition_node:
            raise ValueError("No corresponding if or else if condition node found for else statement.")

        old_succs = [
            s for s in self.current_target_function_cfg.graph.successors(condition_node)
            if self.current_target_function_cfg.graph.get_edge_data(condition_node, s).get('condition') is True
        ]

        # 3. 이전 조건 노드의 False 분기 제거
        false_successors = list(self.current_target_function_cfg.graph.successors(condition_node))
        for successor in false_successors:
            edge_data = self.current_target_function_cfg.graph.get_edge_data(condition_node, successor)
            if edge_data.get('condition') is False:
                self.current_target_function_cfg.graph.remove_edge(condition_node, successor)

        # 3. False 분기 블록 생성
        else_block = CFGNode(name=f"else_block_{self.current_start_line}")

        # 5. 변수 상태 관리
        # else 블록의 변수 상태 초기화 (이전 조건 노드의 변수 상태 복사)
        else_block.variables = self.copy_variables(condition_node.variables)

        # 6. 조건식 부정된 상태로 변수 값 업데이트
        self.update_variables_with_condition(else_block.variables, condition_node.condition_expr, is_true_branch=False)

        # 4. CFG 연결 - 조건 노드의 False 브랜치에 else 블록 연결
        self.current_target_function_cfg.graph.add_node(else_block)
        self.current_target_function_cfg.graph.add_edge(condition_node, else_block, condition=False)

        for s in old_succs:
            self.current_target_function_cfg.graph.add_edge(else_block, s)

        # 5. brace_count 업데이트 - 존재하지 않으면 초기화
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = else_block

        # 7. CFG 업데이트
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        self.current_target_function_cfg = None

    def process_while_statement(self, condition_expr):
        # 1. Get the current contract and function CFG
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to process the while statement.")

        # 2. Get the current block
        current_block = self.get_current_block()

        # 3. Create the join point node (entry point for the loop)
        join_node = CFGNode(name=f"while_join_{self.current_start_line}",
                            fixpoint_evaluation_node=True)

        # Copy variables from current_block to join_node
        join_node.variables = self.copy_variables(current_block.variables) # while문 이전에서 들어온 변수의 상태
        join_node.fixpoint_evaluation_node_vars = self.copy_variables(current_block.variables)

        successors = list(self.current_target_function_cfg.graph.successors(current_block))

        # 기존 current_block과 successor들의 edge를 제거
        for successor in successors:
            self.current_target_function_cfg.graph.remove_edge(current_block, successor)

        # 4. Create the condition node
        condition_node = CFGNode(name=f"while_condition_{self.current_start_line}",
                                 condition_node=True,
                                 condition_node_type="while")
        condition_node.condition_expr = condition_expr  # Store the condition expression for later use
        condition_node.variables = self.copy_variables(join_node.variables)


        # 5. Connect the current block to the join node (if not already connected)
        self.current_target_function_cfg.graph.add_node(join_node)
        self.current_target_function_cfg.graph.add_edge(current_block, join_node)

        # 6. Connect the join node to the condition node
        self.current_target_function_cfg.graph.add_node(condition_node)
        self.current_target_function_cfg.graph.add_edge(join_node, condition_node)

        # 7. Create the true node (loop body)
        true_node = CFGNode(name=f"while_body_{self.current_start_line}")
        true_node.is_loop_body = True
        true_node.variables = self.copy_variables(condition_node.variables)
        self.update_variables_with_condition(true_node.variables, condition_expr, is_true_branch=True)

        # 8. Create the false node (exit block)
        false_node = CFGNode(name=f"while_exit_{self.current_start_line}",
                             loop_exit_node=True)
        self.update_variables_with_condition(false_node.variables,
                                             condition_expr,
                                             is_true_branch=False)

        # 9. Connect the condition node's true branch to the true node
        self.current_target_function_cfg.graph.add_node(true_node)
        self.current_target_function_cfg.graph.add_edge(condition_node, true_node, condition=True)

        # 10. Connect the condition node's false branch to the false node
        self.current_target_function_cfg.graph.add_node(false_node)
        self.current_target_function_cfg.graph.add_edge(condition_node, false_node, condition=False)

        # 기존 current_block과 successor들을 false block의 successor로
        for successor in successors:
            self.current_target_function_cfg.graph.add_edge(false_node, successor)

        # 11. Connect the true node back to the join node (loop back)
        self.current_target_function_cfg.graph.add_edge(true_node, join_node)

        # 8. Return 노드에 대한 brace_count 업데이트
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = condition_node

        # 8. CFG 업데이트
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        self.current_target_function_cfg = None

    def process_for_statement(self, initial_statement=None, condition_expr=None, increment_expr=None):

        # 1) 현재 컨트랙트 / 함수 CFG 가져오기
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)
        if contract_cfg is None:
            raise ValueError(f"[for] contract CFG '{self.current_target_contract}' not found")

        function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if function_cfg is None:
            raise ValueError("[for] active function CFG 없음")

        # ------------------------------------------------------------------#
        # 2) 루프 직전 블록
        # ------------------------------------------------------------------#
        current_block = self.get_current_block()  # for 키워드 이전 코드가 위치한 블록
        old_successors = list(function_cfg.graph.successors(current_block))

        # ------------------------------------------------------------------#
        # 3) init_node 생성 및 initial_statement 해석
        # ------------------------------------------------------------------#
        init_node = CFGNode(f"for_init_{self.current_start_line}")
        init_node.variables = self.copy_variables(current_block.variables)

        if initial_statement is not None:
            ctx = initial_statement.get("context")

            if ctx == "VariableDeclaration":
                var_type = initial_statement["initVarType"]
                var_name = initial_statement["initVarName"]
                init_expr = initial_statement["initValExpr"]  # Expression | None

                var_obj = Variables(identifier=var_name, scope="local")  # ★
                var_obj.typeInfo = var_type  # ★
                init_node.variables[var_name] = var_obj

                if init_expr is not None:
                    val = self.evaluate_expression(init_expr,
                                                   init_node.variables,
                                                   None, None)
                    var_obj.value = val

            elif ctx == "Expression":
                tmp_expr = initial_statement["initExpr"]  # Assignment/Update Expression
                r_val = self.evaluate_expression(tmp_expr.right,
                                                 init_node.variables,
                                                 None, None)
                self.update_left_var(tmp_expr.left,
                                     r_val,
                                     tmp_expr.operator,
                                     init_node.variables,
                                     None, "ForInit")

            else:
                raise ValueError(f"[for] unknown initial_statement ctx '{ctx}'")

        # ------------------------------------------------------------------#
        # 4) join_node  (fix-point evaluation node)
        # ------------------------------------------------------------------#
        join_node = CFGNode(f"for_join_{self.current_start_line}",
                            fixpoint_evaluation_node=True)
        join_node.variables = self.copy_variables(init_node.variables)
        join_node.fixpoint_evaluation_node_vars = self.copy_variables(init_node.variables)

        # ------------------------------------------------------------------#
        # 5) condition_node
        # ------------------------------------------------------------------#
        cond_node = CFGNode(f"for_condition_{self.current_start_line}",
                            condition_node=True,
                            condition_node_type="for")
        cond_node.condition_expr = condition_expr
        cond_node.variables = self.copy_variables(join_node.variables)

        # ------------------------------------------------------------------#
        # 6) body_node
        # ------------------------------------------------------------------#
        body_node = CFGNode(f"for_body_{self.current_start_line}")
        body_node.is_loop_body = True
        body_node.variables = self.copy_variables(cond_node.variables)

        if condition_expr is not None:
            self.update_variables_with_condition(body_node.variables,
                                                 condition_expr,
                                                 is_true_branch=True)

        # ------------------------------------------------------------------#
        # 7) increment_node
        # ------------------------------------------------------------------#
        incr_node = CFGNode(f"for_increment_{self.current_start_line}")
        incr_node.variables = self.copy_variables(body_node.variables)

        if increment_expr is not None:
            lit_one = Expression(literal=1, context="LiteralExpContext")

            op = increment_expr.operator
            if op == "++":
                self.update_left_var(increment_expr.expression,
                                     1, "+=",
                                     incr_node.variables,
                                     None, None)
                incr_node.add_assign_statement(increment_expr.expression, "+=", lit_one)
            elif op == "--":
                self.update_left_var(increment_expr.expression,
                                     1, "-=",
                                     incr_node.variables,
                                     None, None)
                incr_node.add_assign_statement(increment_expr.expression, "-=", lit_one)
            elif op in {"+=", "-="}:
                self.update_left_var(increment_expr.left,
                                     increment_expr.right,
                                     op,
                                     incr_node.variables,
                                     None, None)
                incr_node.add_assign_statement(increment_expr.left, op, increment_expr.right)
            else:
                raise ValueError(f"[for] unexpected increment operator '{op}'")

        # ------------------------------------------------------------------#
        # 8) exit_node  (loop-false 블록)
        # ------------------------------------------------------------------#
        exit_node = CFGNode(f"for_exit_{self.current_start_line}", loop_exit_node=True)
        exit_node.variables = self.copy_variables(join_node.variables)

        if condition_expr is not None:  # ★
            self.update_variables_with_condition(exit_node.variables,
                                                 condition_expr,
                                                 is_true_branch=False)

        # ------------------------------------------------------------------#
        # 9) 그래프 연결
        # ------------------------------------------------------------------#
        g = function_cfg.graph

        # 9-1  노드 등록
        for n in (init_node, join_node, cond_node,
                  body_node, incr_node, exit_node):
            g.add_node(n)

        # 9-2  엣지 연결
        g.add_edge(current_block, init_node)  # pre → init
        g.add_edge(init_node, join_node)  # init → join
        g.add_edge(join_node, cond_node)  # join → cond
        g.add_edge(cond_node, body_node, condition=True)  # True
        g.add_edge(cond_node, exit_node, condition=False)  # False
        g.add_edge(body_node, incr_node)  # body → incr
        g.add_edge(incr_node, join_node)  # incr → join (back-edge)

        # 9-3  루프 탈출 후 원래 successor 로 이어주기         ★
        for succ in old_successors:
            g.remove_edge(current_block, succ)
            g.add_edge(exit_node, succ)

        # brace_count 업데이트 (선택)
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = cond_node

        self.current_target_function_cfg = None

    def process_continue_statement(self):
        # 1. 현재 컨트랙트와 함수의 CFG 가져오기
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to process the continue statement.")

        # 2. 현재 블록 가져오기 (continue가 발생한 블록)
        current_block = self.get_current_block()

        # 3. 현재 블록에 continue statement 추가 (Statement 객체로 추가)
        current_block.add_continue_statement()

        # 4. 재귀적으로 fixpoint_evaluation_node 찾기
        fixpoint_evaluation_node = self.find_fixpoint_evaluation_node(current_block, self.current_target_function_cfg)
        if not fixpoint_evaluation_node:
            raise ValueError("No corresponding loop join node found for continue statement.")

        # 5. 현재 블록의 모든 successor와의 edge 제거
        successors = list(self.current_target_function_cfg.graph.successors(current_block))
        for successor in successors:
            self.current_target_function_cfg.graph.remove_edge(current_block, successor)

        # 6. 현재 블록을 fixpoint_evaluation_node로 연결 (loop로 다시 돌아감)
        self.current_target_function_cfg.graph.add_edge(current_block, fixpoint_evaluation_node)

        # 8. Return 노드에 대한 brace_count 업데이트
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = current_block

        # 7. CFG 업데이트
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        self.current_target_function_cfg = None

    def process_break_statement(self):
        # 1. 현재 컨트랙트와 함수의 CFG 가져오기
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to process the break statement.")

        # 2. 현재 블록 가져오기 (break가 발생한 블록)
        current_block = self.get_current_block()

        # 3. 현재 블록에 break statement 추가 (Statement 객체로 추가)
        current_block.add_break_statement()

        # 4. 재귀적으로 위로 타고 올라가서 while문 조건 노드를 찾기
        condition_node = self.find_loop_condition_node(current_block, self.current_target_function_cfg)
        if not condition_node:
            raise ValueError("No corresponding while condition node found for break statement.")

        # 5. 해당 조건 노드의 false branch를 통해 loop_exit_node 찾기
        loop_exit_node = self.current_target_function_cfg.get_false_block(condition_node)  # 수정된 부분
        if not loop_exit_node or not loop_exit_node.loop_exit_node:
            raise ValueError("No valid loop exit node found for break statement.")

        # 6. 현재 블록의 모든 successor와의 edge 제거
        successors = list(self.current_target_function_cfg.graph.successors(current_block))
        for successor in successors:
            self.current_target_function_cfg.graph.remove_edge(current_block, successor)

        # 7. 현재 블록을 loop_exit_node로 연결 (루프에서 빠져나감)
        self.current_target_function_cfg.graph.add_edge(current_block, loop_exit_node)

        # 8. Return 노드에 대한 brace_count 업데이트
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = current_block

        # 8. CFG 업데이트
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        self.current_target_function_cfg = None

    def find_fixpoint_evaluation_node(self, current_node):
        """
        재귀적으로 predecessor를 탐색하여 fixpoint_evaluation_node를 찾는 함수
        """
        # 현재 노드가 fixpoint_evaluation_node라면 반환
        if current_node.fixpoint_evaluation_node:
            return current_node

        # 직접적인 predecessor를 탐색
        predecessors = list(self.current_target_function_cfg.graph.predecessors(current_node))
        for pred in predecessors:
            # 재귀적으로 predecessor를 탐색하여 fixpoint_evaluation_node를 찾음
            fixpoint_evaluation_node = self.find_fixpoint_evaluation_node(pred)
            if fixpoint_evaluation_node:
                return fixpoint_evaluation_node

        # fixpoint_evaluation_node를 찾지 못하면 None 반환
        return None

    def find_loop_condition_node(self, current_node):
        """
                재귀적으로 predecessor를 탐색하여 fixpoint_evaluation_node를 찾는 함수
                """
        # 현재 노드가 fixpoint_evaluation_node라면 반환
        if current_node.condition_node and current_node.condition_node_type in["while", "for"] :
            return current_node

        # 직접적인 predecessor를 탐색
        predecessors = list(self.current_target_function_cfg.graph.predecessors(current_node))
        for pred in predecessors:
            # 재귀적으로 predecessor를 탐색하여 fixpoint_evaluation_node를 찾음
            loop_condition_node = self.find_loop_condition_node(pred)
            if loop_condition_node:
                return loop_condition_node

        # fixpoint_evaluation_node를 찾지 못하면 None 반환
        return None

    def process_return_statement(self, return_expr=None):
        # 1. 현재 컨트랙트와 함수의 CFG 가져오기
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to process the return statement.")

        # 2. 현재 블록 가져오기
        current_block = self.get_current_block()


        # 3. 반환값이 있는 경우 expression 평가
        if return_expr:
            return_value = self.evaluate_expression(return_expr, current_block.variables, None, None)
        else:
            return_value = None

        # 4. Return 구문을 current_block에 추가
        current_block.add_return_statement(return_expr=return_expr)

        # 5. function_exit_node에 return 값을 저장
        exit_node = self.current_target_function_cfg.get_exit_node()
        exit_node.return_vals[self.current_start_line] = return_value  # 반환 값을 exit_node의 return_val에 기록

        # 7. current_block에서 exit_node로 직접 연결
        self.current_target_function_cfg.graph.add_edge(current_block, exit_node)

        # 8. CFG 업데이트
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 9. current_target_function_cfg를 None으로 설정하여 함수 종료
        self.current_target_function_cfg = None

    def process_revert_statement(self, revert_identifier=None, string_literal=None, call_argument_list=None):
        # 1. 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. 현재 타겟 함수의 CFG 가져오기
        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to process the revert statement.")

        # 3. 현재 블록 가져오기
        current_block = self.get_current_block()

        current_block.add_revert_statement(revert_identifier, string_literal, call_argument_list)

        # 5. 함수의 exit 노드와 현재 노드 간 연결이 이미 존재하는지 확인
        exit_node = self.current_target_function_cfg.get_exit_node()
        if not self.current_target_function_cfg.graph.has_edge(current_block, exit_node):
            # 기존 엣지가 없으면 연결
            self.current_target_function_cfg.graph.add_edge(current_block, exit_node)

        # 7. Revert 노드의 brace_count 업데이트
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = current_block

        # 6. CFG 업데이트
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        self.current_target_function_cfg = None

    def process_require_statement(self, condition_expr, string_literal):
        # 1. 현재 컨트랙트와 함수의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to process the require statement.")

        # 2. 현재 블록 가져오기
        current_block = self.get_current_block()

        # 3. 기존 current_block의 successor 가져오기
        successors = list(self.current_target_function_cfg.graph.successors(current_block))

        # 4. 조건식 블록 생성 및 평가
        require_condition_node = CFGNode(name=f"require_condition_{self.current_start_line}",
                                         condition_node=True,
                                         condition_node_type="require")
        require_condition_node.condition_expr = condition_expr

        # 5. True 분기 블록 생성
        true_block = CFGNode(name=f"require_true_{self.current_start_line + 1}")

        # 6. True 블록에서 변수 상태 복사 및 업데이트
        true_block.variables = self.copy_variables(current_block.variables)
        self.update_variables_with_condition(true_block.variables, condition_expr, is_true_branch=True)

        # 7. 기존 current_block의 successors를 require_condition_node로 설정
        for successor in successors:
            self.current_target_function_cfg.graph.add_edge(require_condition_node, successor)
            self.current_target_function_cfg.graph.remove_edge(current_block, successor)

        # 8. 기존 current_block과 require_condition_node 연결
        self.current_target_function_cfg.graph.add_node(require_condition_node)
        self.current_target_function_cfg.graph.add_edge(current_block, require_condition_node)

        # 9. False 분기 처리 (조건이 실패할 경우, exit 노드로 연결)
        exit_node = self.current_target_function_cfg.get_exit_node()
        self.current_target_function_cfg.graph.add_edge(require_condition_node, exit_node, condition=False)

        # 10. True 블록 연결
        self.current_target_function_cfg.graph.add_node(true_block)
        self.current_target_function_cfg.graph.add_edge(require_condition_node, true_block, condition=True)

        # 11. brace_count 업데이트
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = require_condition_node

        # 12. CFG 업데이트
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        self.current_target_function_cfg = None

    def process_assert_statement(self, condition_expr, string_literal):
        # 1. 현재 컨트랙트와 함수의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to process the require statement.")

        # 2. 현재 블록 가져오기
        current_block = self.get_current_block()

        # 3. 기존 current_block의 successor 가져오기
        successors = list(self.current_target_function_cfg.graph.successors(current_block))

        # 4. 조건식 블록 생성 및 평가
        assert_condition_node = CFGNode(name=f"assert_condition_{self.current_start_line}",
                                        condition_node=True,
                                        condition_node_type="assert")
        assert_condition_node.condition_expr = condition_expr


        # 5. True 분기 블록 생성
        true_block = CFGNode(name=f"require_true_{self.current_start_line + 1}")

        # 6. True 블록에서 변수 상태 복사 및 업데이트
        true_block.variables = self.copy_variables(current_block.variables)
        self.update_variables_with_condition(true_block.variables, condition_expr, is_true_branch=True)

        # 7. 기존 current_block의 successors를 require_condition_node로 설정
        for successor in successors:
            self.current_target_function_cfg.graph.add_edge(assert_condition_node, successor)
            self.current_target_function_cfg.graph.remove_edge(current_block, successor)

        # 8. 기존 current_block과 require_condition_node 연결
        self.current_target_function_cfg.graph.add_node(assert_condition_node)
        self.current_target_function_cfg.graph.add_edge(current_block, assert_condition_node)

        # 9. False 분기 처리 (조건이 실패할 경우, exit 노드로 연결)
        exit_node = self.current_target_function_cfg.get_exit_node()
        self.current_target_function_cfg.graph.add_edge(assert_condition_node, exit_node, condition=False)

        # 10. True 블록 연결
        self.current_target_function_cfg.graph.add_node(true_block)
        self.current_target_function_cfg.graph.add_edge(assert_condition_node, true_block, condition=True)

        # 11. brace_count 업데이트
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = assert_condition_node

        # 12. CFG 업데이트
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        self.current_target_function_cfg = None

    def process_global_var_for_debug(self, gv_obj: GlobalVariable):
        cfg = self.contract_cfgs[self.current_target_contract]

        # 1) 사전 엔트리 보장
        if gv_obj.identifier not in cfg.globals:
            gv_obj.default_value = gv_obj.value  # 최초 호출이면 default 기록
            cfg.globals[gv_obj.identifier] = gv_obj
        g = cfg.globals[gv_obj.identifier]

        # 2) override 반영
        g.debug_override = gv_obj.value
        g.value = gv_obj.value  # 실시간 해석에 쓰이도록

        # 3) 모든 FunctionCFG 의 related_variables 동기화
        for fc in cfg.functions.values():
            if gv_obj.identifier in fc.related_variables:
                fc.related_variables[gv_obj.identifier].value = gv_obj.value

        # ② 영향을 받는 함수만 재해석
        for func_name in gv_obj.usage_sites:
            if func_name in cfg.functions:
                self.interpret_function_cfg(cfg.functions[func_name])

    def process_state_var_for_debug(self, lhs_expr: Expression, value):
        """
        @StateVar ...  주석 처리

        lhs_expr : Expression  (identifier / .member / [index] …)
        value    : Interval | BoolInterval | str
        """
        # 1. CFG 찾기
        cfg = self.contract_cfgs[self.current_target_contract]
        fcfg = cfg.get_function_cfg(self.current_target_function)
        if fcfg is None:
            raise ValueError("StateVar debug must appear inside a function body.")

        # 2. 실제 변수 객체 해석·업데이트  (이미 있는 helper 재사용)
        var_obj = self._resolve_and_update_expr(lhs_expr, fcfg, value)
        if var_obj is None:
            raise ValueError("LHS cannot be resolved to a state variable.")

        # 3. 함수 한 번만 재해석
        self.interpret_function_cfg(fcfg)

    def process_local_var_for_debug(self, lhs_expr, value):
        cfg = self.contract_cfgs[self.current_target_contract]
        fcfg = cfg.get_function_cfg(self.current_target_function)
        if fcfg is None:
            raise ValueError("StateVar debug must appear inside a function body.")

        # 2. 실제 변수 객체 해석·업데이트  (이미 있는 helper 재사용)
        var_obj = self._resolve_and_update_expr(lhs_expr, fcfg, value)
        if var_obj is None:
            raise ValueError("LHS cannot be resolved to a state variable.")

        # 3. 함수 한 번만 재해석
        self.interpret_function_cfg(fcfg)

    # ---------------- util helpers ---------------- #
    def _is_interval(x):
        return isinstance(x, (IntegerInterval, UnsignedIntegerInterval))

    def _extract_index_val(expr_idx):
        """
        expr_idx: Expression
        → literal 이면 정수/주소 문자열 반환, 그 외엔 expression 자체(심볼릭) 반환
        """
        if expr_idx.context == "LiteralExpContext":
            return int(expr_idx.literal, 0)
        return expr_idx  # 심볼릭 인덱스 그대로

    def _create_new_mapping_value(map_var: MappingVariable, key):
        # value 타입은 mapping 의 valueType 에서 꺼낸다.
        val_type = map_var.valueType
        if val_type.startswith("uint"):
            bit = 256 if len(val_type) == 4 else int(val_type[4:])
            v = UnsignedIntegerInterval.bottom(bit)
        elif val_type.startswith("int"):
            bit = 256 if len(val_type) == 3 else int(val_type[3:])
            v = IntegerInterval.bottom(bit)
        elif val_type == "bool":
            v = BoolInterval.bottom()
        else:  # address, struct 등
            v = f"symbolic<{map_var.identifier}[{key}]>"
        child = Variables(identifier=f"{map_var.identifier}[{key}]",
                          value=v, scope="mapping_value")
        child.typeInfo = map_var.typeInfo.valueTypeInfo  # deep copy 필요 시 복제
        return child

    # ------------------------------------------------ #

    def _apply_new_value_to_variable(self, var_obj, new_value):
        """
        new_value 가능 유형
          - IntegerInterval / UnsignedIntegerInterval
          - int / bool (단정 값)
          - 'symbolicAddress N'  (str)
          - BoolInterval          (top, 단정)
        내부 로직:
          1) RHS 가 이미 Interval 계열이면 그대로 대입
          2) elementary type 에 맞춰 wrap
          3) 'any' → BoolInterval.top()
        """

        # 0. Interval 객체가 오면 그대로
        if self._is_interval(new_value):
            var_obj.value = new_value
            return

        # 1. elementary type 정보 추출
        if var_obj.typeInfo is None or var_obj.typeInfo.elementaryTypeName is None:
            # struct / array / mapping 등 (현재 스코프에선 직접 업데이트 X)
            print(f"[Info] _apply_new_value_to_variable: skip non-elementary '{var_obj.identifier}'")
            return

        etype = var_obj.typeInfo.elementaryTypeName

        # 2. wrap
        if etype.startswith("int"):
            bit = var_obj.typeInfo.intTypeLength or 256
            iv = new_value if isinstance(new_value, IntegerInterval) else \
                IntegerInterval(int(new_value), int(new_value), bit)
            var_obj.value = iv

        elif etype.startswith("uint"):
            bit = var_obj.typeInfo.intTypeLength or 256
            uv = new_value if isinstance(new_value, UnsignedIntegerInterval) else \
                UnsignedIntegerInterval(int(new_value), int(new_value), bit)
            var_obj.value = uv

        elif etype == "bool":
            if isinstance(new_value, BoolInterval):
                var_obj.value = new_value
            elif isinstance(new_value, str) and new_value.lower() == "any":
                var_obj.value = BoolInterval.top()
            else:
                var_obj.value = BoolInterval(bool(new_value), bool(new_value))

        elif etype == "address":
            # 주소는 문자열 그대로 두거나 심볼릭 처리
            var_obj.value = str(new_value)

        else:
            print(f"[Warning] _apply_new_value_to_variable: unhandled elementary type '{etype}'")
            var_obj.value = new_value  # fallback

    def _resolve_and_update_expr(self, expr: Expression, function_cfg, new_value):
        """
        디버그용 LHS(Expression) 탐색 & value 업데이트.
        반환: 실제로 갱신된 Variables 객체 (없으면 None)
        """
        # 1️⃣ root 식별자
        if expr.base is None:
            var_obj = function_cfg.get_related_variable(expr.identifier)
            if var_obj:
                if new_value is not None:  # 루트일 수도, 최종 leaf 일 수도
                    self._apply_new_value_to_variable(var_obj, new_value)
            else:
                print(f"[Warn] '{expr.identifier}' not in related_variables of '{function_cfg.function_name}'")
            return var_obj

        # 2️⃣ 하위 경로 탐색 (member / index)
        base_obj = self._resolve_and_update_expr(expr.base, function_cfg, None)
        if base_obj is None:
            return None

        # ---- member access (struct) ----
        if expr.member is not None:
            if not isinstance(base_obj, StructVariable):
                print(f"[Warn] member access on non-struct '{base_obj.identifier}'")
                return None
            member_name = expr.member
            mem_var = base_obj.members.get(member_name)
            if mem_var is None:
                print(f"[Warn] struct '{base_obj.identifier}' has no member '{member_name}'")
                return None
            if new_value is not None:
                self._apply_new_value_to_variable(mem_var, new_value)
            return mem_var

        # ---- index access (array / mapping) ----
        if expr.index is not None:
            if isinstance(base_obj, ArrayVariable):
                idx = self._extract_index_val(expr.index)
                if not isinstance(idx, int) or idx < 0:
                    print(f"[Warn] non-literal or negative array index '{idx}'")
                    return None
                # 동적 배열인 경우 길이 확장
                while idx >= len(base_obj.elements):
                    base_obj.elements.append(self._create_new_mapping_value(base_obj, len(base_obj.elements)))
                elem_var = base_obj.elements[idx]
                if new_value is not None:
                    self._apply_new_value_to_variable(elem_var, new_value)
                return elem_var

            elif isinstance(base_obj, MappingVariable):
                key = str(self._extract_index_val(expr.index))
                if key not in base_obj.mapping:
                    base_obj.mapping[key] = self._create_new_mapping_value(base_obj, key)
                mapped_var = base_obj.mapping[key]
                if new_value is not None:
                    self._apply_new_value_to_variable(mapped_var, new_value)
                return mapped_var

            else:
                print(f"[Warn] index access on non-array/mapping '{base_obj.identifier}'")
                return None

        return None  # 다른 케이스가 없으면

    import copy

    def copy_variables(self, variables):
        """
        주어진 변수 딕셔너리(variables)를 깊은 복사하여 반환합니다.
        variables: var_name -> Variables 객체
        """
        copied_variables = {}
        for var_name, var_obj in variables.items():
            if isinstance(var_obj, ArrayVariable):
                copied_array = ArrayVariable(
                    identifier=var_obj.identifier,
                    base_type=var_obj.typeInfo.arrayBaseType,
                    array_length=var_obj.typeInfo.arrayLength,
                    is_dynamic=var_obj.typeInfo.isDynamicArray,
                    value=copy.deepcopy(var_obj.value),
                    isConstant=var_obj.isConstant,
                    scope=var_obj.scope
                )
                # 배열의 각 요소를 깊은 복사
                copied_array.elements = [self.copy_variables({elem.identifier: elem})[elem.identifier] for elem in
                                         var_obj.elements]
                copied_variables[var_name] = copied_array

            elif isinstance(var_obj, StructVariable):
                copied_struct = StructVariable(
                    identifier=var_obj.identifier,
                    struct_type=var_obj.typeInfo.structTypeName,
                    value=copy.deepcopy(var_obj.value),
                    isConstant=var_obj.isConstant,
                    scope=var_obj.scope
                )
                # 구조체 멤버를 깊은 복사
                copied_struct.members = {member_name: self.copy_variables({member_name: member_obj})[member_name] for
                                         member_name, member_obj in var_obj.members.items()}
                copied_variables[var_name] = copied_struct

            elif isinstance(var_obj, MappingVariable):
                copied_mapping = MappingVariable(
                    identifier=var_obj.identifier,
                    key_type=var_obj.typeInfo.mappingKeyType,
                    value_type=var_obj.typeInfo.mappingValueType,
                    value=copy.deepcopy(var_obj.value),
                    isConstant=var_obj.isConstant,
                    scope=var_obj.scope
                )
                # 매핑의 키-값 쌍을 깊은 복사
                copied_mapping.mapping = {}
                for key, value in var_obj.mapping.items():
                    # 값이 Variables 객체인지 확인
                    if isinstance(value, Variables):
                        # Variables 객체인 경우 재귀적으로 복사
                        copied_value = self.copy_variables({key: value})[key]
                    else:
                        # Variables 객체가 아닌 경우 (Interval 등), 값을 그대로 복사
                        copied_value = copy.deepcopy(value)
                    copied_mapping.mapping[key] = copied_value
                copied_variables[var_name] = copied_mapping

            else:
                # 기본 Variables 타입 처리
                copied_variables[var_name] = Variables(
                    identifier=var_obj.identifier,
                    value=copy.deepcopy(var_obj.value),
                    isConstant=var_obj.isConstant,
                    scope=var_obj.scope,
                    typeInfo=var_obj.typeInfo  # SolType 객체 복사
                )

        return copied_variables

    def traverse_loop_nodes(self, loop_node):
        """
        루프 내의 모든 노드를 수집합니다.
        :param loop_node: 루프의 시작 노드 (fixpoint_evaluation_node)
        :return: 루프 내의 노드 집합 (set)
        """
        visited = set()
        stack = [loop_node]
        while stack:
            current_node = stack.pop()
            if current_node in visited:
                continue
            visited.add(current_node)
            successors = list(self.current_target_function_cfg.graph.successors(current_node))
            for succ in successors:
                # 루프 종료 노드로의 에지는 제외
                if current_node.condition_node and \
                        current_node.condition_node_type in ['while', 'for', 'do'] :
                    if succ.loop_exit_node:
                        continue
                stack.append(succ)
        return visited

    def join_variables(self, vars1, vars2):
        """
        두 변수 상태(vars1, vars2)를 조인하여(합집합) 반환.
        - array: 요소별 join
        - struct: 멤버별 join
        - mapping: 매핑 key별 join
        - 기본타입: Interval join
        """
        result = self.copy_variables(vars1)

        for var_name, var_obj2 in vars2.items():
            if var_name in result:
                var_obj1 = result[var_name]

                # 타입 동일성
                if var_obj1.typeInfo.typeCategory != var_obj2.typeInfo.typeCategory:
                    raise TypeError(f"Cannot join different typeCategories: {var_obj1.typeInfo.typeCategory} "
                                    f"vs {var_obj2.typeInfo.typeCategory}")

                cat = var_obj1.typeInfo.typeCategory
                if cat == 'array':
                    # 길이 같음 전제(동적 배열 등은 별도 정책)
                    if len(var_obj1.elements) != len(var_obj2.elements):
                        raise ValueError("Cannot join arrays of different lengths (static array).")
                    for i, (e1, e2) in enumerate(zip(var_obj1.elements, var_obj2.elements)):
                        joined_elem = self.join_variables({e1.identifier: e1}, {e2.identifier: e2})
                        var_obj1.elements[i] = joined_elem[e1.identifier]

                elif cat == 'struct':
                    # 멤버별 join
                    var_obj1.members = self.join_variables(var_obj1.members, var_obj2.members)

                elif cat == 'mapping':
                    # 매핑된 키-값 each join
                    for key, mvar2 in var_obj2.mapping.items():
                        if key not in var_obj1.mapping:
                            # 없는 키 => 새로 복사
                            var_obj1.mapping[key] = self.copy_variables({key: mvar2})[key]
                        else:
                            # 기존 키 => join
                            mvar1 = var_obj1.mapping[key]
                            joined_map = self.join_variables({key: mvar1}, {key: mvar2})
                            var_obj1.mapping[key] = joined_map[key]

                else:
                    # elementary => interval join
                    var_obj1.value = self.join_variable_values(var_obj1.value, var_obj2.value)
            else:
                # 새 변수
                result[var_name] = self.copy_variables({var_name: var_obj2})[var_name]
        return result

    def variables_equal(self, vars1, vars2):
        """
        두 변수 딕셔너리가 동일한지 비교
        - array: length/각 요소
        - struct: 멤버별
        - mapping: 동일 key, 동일 값
        - elementary: interval 동등성 체크
        """
        if vars1.keys() != vars2.keys():
            return False

        for var_name in vars1:
            if var_name not in vars2:
                return False

            obj1 = vars1[var_name]
            obj2 = vars2[var_name]

            cat = obj1.typeInfo.typeCategory
            if cat != obj2.typeInfo.typeCategory:
                return False

            if cat == 'array':
                if len(obj1.elements) != len(obj2.elements):
                    return False
                for e1, e2 in zip(obj1.elements, obj2.elements):
                    # 재귀
                    if not self.variables_equal({e1.identifier: e1}, {e2.identifier: e2}):
                        return False

            elif cat == 'struct':
                if not self.variables_equal(obj1.members, obj2.members):
                    return False

            elif cat == 'mapping':
                # 키 동일성
                if obj1.mapping.keys() != obj2.mapping.keys():
                    return False
                for key in obj1.mapping:
                    if not self.variables_equal({key: obj1.mapping[key]}, {key: obj2.mapping[key]}):
                        return False
            else:
                # elementary (int/uint/bool/enum 등) 비교
                if hasattr(obj1.value, "equals") and hasattr(obj2.value, "equals"):
                    if not obj1.value.equals(obj2.value):
                        return False
                else:
                    # Interval 이 아닌 단순 값(예: enum 리터럴 index, symbolic address 등)
                    if obj1.value != obj2.value:
                        return False

        return True

    def transfer_function(self, node, in_vars):
        """
        노드의 transfer function을 적용하여 out_vars를 계산합니다.
        :param node: 현재 노드
        :param in_vars: 노드의 입력 변수 상태 (var_name -> Variables 객체)
        :return: 노드의 출력 변수 상태 (var_name -> Variables 객체)
        """
        out_vars = self.copy_variables(in_vars)
        if node.condition_node:
            # 조건 노드 처리
            self.update_variables_with_condition(out_vars, node.condition_expr, is_true_branch=True)
        elif node.fixpoint_evaluation_node:
            return out_vars
        else:
            # 일반 노드 처리: 노드의 모든 statement 평가
            for statement in node.statements:
                self.update_statement_with_variables(statement, out_vars)
        return out_vars

    def update_statement_with_variables(self, stmt, current_variables):
        if stmt.statement_type == 'variableDeclaration':
            return self.interpret_variable_declaration_statement(stmt, current_variables)
        elif stmt.statement_type == 'assignment':
            return self.interpret_assignment_statement(stmt, current_variables)
        elif stmt.statement_type == 'function_call':
            return self.interpret_function_call_statement(stmt, current_variables)
        elif stmt.statement_type == 'return':
            return self.interpret_return_statement(stmt, current_variables)
        elif stmt.statement_type == 'revert':
            return self.interpret_revert_statement(stmt, current_variables)
        else:
            raise ValueError(f"Statement '{stmt.statement_type}' is not implemented.")

    # ---------------------------------------------------------------------------
    # ① get_current_block – 현재 커서가 들어갈 CFG 블록 탐색 + 블록-아웃 감지
    # ---------------------------------------------------------------------------
    def get_current_block(self) -> CFGNode:
        """
        커서가 위치한 소스-라인에 대응하는 CFG 블록을 반환한다.
        - 한 줄 코드 삽입 : 해당 블록 반환
        - '}' 로 블록-아웃  : process_flow_join 에게 위임
        """

        close_brace_queue: list[int] = []

        # ── 위에서 ↓ 아래로 탐색 (직전 라인부터)
        for line in range(self.current_start_line - 1, 0, -1):
            brace_info = self.brace_count.get(
                line,
                {"open": 0, "close": 0, "cfg_node": None},
            )

            # 공백/주석 전용 라인 스킵
            if brace_info["open"] == brace_info["close"] == 0 and brace_info["cfg_node"] is None:
                # 원본 라인 텍스트 직접 확인 (whitespace - only?)
                if self.full_code_lines.get(line, "").strip() == "":
                    continue

            # ────────── CASE 1. 아직 close_brace_queue가 비어 있음 ──────────
            if not close_brace_queue:

                # 1-a) 일반 statement 라인 → 그 cfg_node 반환
                if brace_info["cfg_node"] and brace_info["open"] == brace_info["close"] == 0:
                    return brace_info["cfg_node"]

                # 1-b) 막 열린 '{' (open==1, close==0)
                if brace_info["cfg_node"] and brace_info["open"] == 1 and brace_info["close"] == 0:
                    cfg_node: CFGNode = brace_info["cfg_node"]

                    # ENTRY 블록 직후 새 블록 삽입
                    if cfg_node.name == "ENTRY":
                        if self.current_target_function_cfg is None:
                            raise ValueError("No active function CFG found.")
                        entry_node = cfg_node
                        new_block = CFGNode(f"Block_{self.current_start_line}")

                        # variables = 함수 related 변수 deep-copy
                        new_block.variables = self.copy_variables(self.current_target_function_cfg.related_variables)

                        g = self.current_target_function_cfg.graph
                        # ENTRY 의 기존 successor 기억 후 재연결
                        old_succs = list(g.successors(entry_node))
                        g.add_node(new_block)
                        g.add_edge(entry_node, new_block)
                        for s in old_succs:
                            g.remove_edge(entry_node, s)
                            g.add_edge(new_block, s)
                        return new_block

                    # 조건-노드의 서브블록 결정
                    if cfg_node.condition_node:
                        ctype = cfg_node.condition_node_type
                        if ctype in ("if", "else if"):
                            return self.get_true_block(cfg_node)
                        if ctype == "else":
                            return self.get_false_block(cfg_node)
                        if ctype in ("while", "for", "doWhile"):
                            return self.get_true_block(cfg_node)

                    # 그 외 – 바로 반환
                    return cfg_node

                # 1-c) '}' 발견 → close 큐에 push
                if brace_info["open"] == 0 and brace_info["close"] == 1 and brace_info["cfg_node"] is None:
                    close_brace_queue.append(line)

            # ────────── CASE 2. close_brace_queue가 이미 존재 ──────────
            else:
                # 연속 '}' 누적
                if brace_info["open"] == 0 and brace_info["close"] == 1 and brace_info["cfg_node"] is None:
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

        # 가장 안쪽 '}' 부터 순차 처리
        for line in close_brace_queue:
            open_brace_info = self.find_corresponding_open_brace(line)
            if not open_brace_info:
                raise ValueError("Matching '{' not found for '}' ")

            cfg_node: CFGNode = open_brace_info["cfg_node"]

            # ── 루프 고정점 ─────────────────────────────────────────────
            if cfg_node.condition_node_type in ("while", "for", "doWhile"):
                new_block = self.fixpoint(cfg_node)
                # fixpoint 후 new_block 을 brace_count 에 등록 (다음 탐색용)
                self.brace_count[self.current_start_line] = {"open": 0, "close": 0, "cfg_node": new_block}
                break  # 루프 하나만 처리하면 바깥은 다음 호출에서 다룸

            # ── if/else-if 합류 후보 ────────────────────────────────
            if not has_if and cfg_node.condition_node_type == "if":
                outside_if_node = cfg_node
                has_if = True

        # ─────────── if-join 처리 ───────────
        if has_if and outside_if_node is not None:
            new_block = self.join_leaf_nodes(outside_if_node)

            g = self.current_target_function_cfg.graph
            succs = list(g.successors(outside_if_node))

            # succ ↦ new_block 으로 재연결 (중복/self-loop 방지)
            for s in succs:
                if s in (new_block, outside_if_node):
                    continue
                g.remove_edge(outside_if_node, s)
                if not g.has_edge(new_block, s):
                    g.add_edge(new_block, s)

            if not g.has_edge(outside_if_node, new_block):
                g.add_edge(outside_if_node, new_block)

            # brace_count 에도 등록
            self.brace_count[self.current_start_line] = {"open": 0, "close": 0, "cfg_node": new_block}
            return new_block

        # 특별히 처리할 노드가 없으면 None – 상위 루틴에서 다시 판단
        return new_block

    # ContractAnalyzer.py (또는 해당 클래스가 정의된 모듈)

    # ───────────────────────────────────────────────────────────
    # 고정점 계산 : work-list + widening & narrowing
    #   ① 1차 패스 – widening 으로 상향 수렴
    #   ② 2차 패스 – narrowing 으로 다시 조정
    #   • while / for / do-while 의 condition-node 를 인자로 받는다
    # ───────────────────────────────────────────────────────────
    def fixpoint(self, loop_condition_node: CFGNode) -> CFGNode:
        """
        loop_condition_node : while / for / doWhile 의 condition CFGNode
        return              : loop 의 exit-node  (CFGNode)
        """

        # ── 0. exit-node 찾기 ────────────────────────
        exit_nodes = self.find_loop_exit_nodes(loop_condition_node)
        if not exit_nodes:
            raise ValueError("Loop without exit-node")
        if len(exit_nodes) > 1:
            # for + break 같은 특수 케이스 대비. 우선 첫 번째만.
            print("[Warn] multiple exit-nodes – using the first one")
        exit_node = exit_nodes[0]

        # ── 1. 루프 내 노드 수집 ─────────────────────
        loop_nodes: set[CFGNode] = self.traverse_loop_nodes(loop_condition_node)
        #   condition-node 도 포함돼 있음

        # ── 2. 자료구조 초기화 ───────────────────────
        in_vars: dict[CFGNode, dict] = {n: {} for n in loop_nodes}
        out_vars: dict[CFGNode, dict] = {n: {} for n in loop_nodes}

        # 조건 노드 진입 시점 변수 = predecessor(join or 외부)의 값
        preds = list(self.current_target_function_cfg.graph.predecessors(loop_condition_node))
        start_env = None
        for p in preds:
            env = p.variables
            start_env = self.join_variables_with_widening(start_env, env) if start_env else self.copy_variables(env)
        in_vars[loop_condition_node] = self.copy_variables(start_env)

        # ── 3-A. 1차 패스 – widening ────────────────
        WL = deque([loop_condition_node])
        W_MAX = 30  # 안전 장치
        iter_cnt = 0
        while WL and iter_cnt < W_MAX:
            iter_cnt += 1
            node = WL.popleft()

            # 3-A-1. transfer
            out_old = out_vars[node]
            out_new = self.transfer_function(node, in_vars[node])

            # 3-A-2. widening (첫 방문이면 그냥 대입)
            widened = self.join_variables_with_widening(out_old, out_new)

            if not self.variables_equal(out_old, widened):
                out_vars[node] = widened

                # succ 의 in 변수 갱신 + WL push
                for succ in self.current_target_function_cfg.graph.successors(node):
                    if succ not in loop_nodes:  # 루프 밖 → exit-node 이거나 더 바깥
                        continue
                    in_old = in_vars[succ]
                    in_new = self.join_variables_with_widening(in_old, widened)
                    if not self.variables_equal(in_old, in_new):
                        in_vars[succ] = in_new
                        WL.append(succ)

        if iter_cnt == W_MAX:
            print("[Warn] widening phase hit max-iteration")

        # ── 3-B. 2차 패스 – narrowing ───────────────
        #     • 위에서 얻은 out_vars 를 starting point 로 재사용
        WL = deque(loop_nodes)
        N_MAX = 15
        n_iter = 0
        while WL and n_iter < N_MAX:
            n_iter += 1
            node = WL.popleft()

            # predecessors 의 out 을 meet → in'
            preds = list(self.current_target_function_cfg.graph.predecessors(node))
            new_in = None
            for p in preds:
                src = out_vars[p] if p in loop_nodes else p.variables
                new_in = self.join_variables_simple(new_in, src) if new_in else self.copy_variables(src)

            if new_in is None:
                continue
            if self.variables_equal(new_in, in_vars[node]):
                continue
            in_vars[node] = new_in

            # transfer
            old_out = out_vars[node]
            tmp_out = self.transfer_function(node, new_in)
            # narrowing : old_out.narrow(tmp_out)
            narrowed = self.narrow_variables(old_out, tmp_out)

            if not self.variables_equal(old_out, narrowed):
                out_vars[node] = narrowed
                WL.extend(self.current_target_function_cfg.graph.successors(node))

        if n_iter == N_MAX:
            print("[Warn] narrowing phase hit max-iteration")

        # ── 4. exit-node 변수 반영 ───────────────────
        exit_env = None
        for p in self.current_target_function_cfg.graph.predecessors(exit_node):
            src = out_vars[p] if p in out_vars else p.variables
            exit_env = self.join_variables_simple(exit_env, src) if exit_env else self.copy_variables(src)
        exit_node.variables = exit_env if exit_env else {}

        return exit_node

    def find_loop_exit_nodes(self, while_node):
        """
        주어진 while 노드의 루프 exit 노드를 찾습니다.
        :param while_node: while 루프의 조건 노드
        :return: 루프 exit 노드들의 리스트
        """
        exit_nodes = []
        visited = set()
        stack = [while_node]

        while stack:
            current_node = stack.pop()
            if current_node in visited:
                continue
            visited.add(current_node)

            successors = list(self.current_target_function_cfg.graph.successors(current_node))
            for succ in successors:
                if succ == while_node:
                    # 루프 백 엣지이므로 무시
                    continue
                if not self.is_node_in_loop(succ, while_node):
                    # 루프 밖의 노드이면 exit 노드로 추가
                    exit_nodes.append(succ)
                else:
                    stack.append(succ)

        return exit_nodes

    def is_node_in_loop(self, node, while_node):
        """
        주어진 노드가 while 루프 내에 속해 있는지 확인합니다.
        :param node: 확인할 노드
        :param while_node: while 루프의 조건 노드
        :return: True 또는 False
        """
        # while_node에서 시작하여 루프 내의 모든 노드를 수집하고, 그 안에 node가 있는지 확인
        loop_nodes = self.traverse_loop_nodes(while_node)
        return node in loop_nodes

    def find_corresponding_open_brace(self, close_line):
        """
        닫는 중괄호에 대응되는 여는 중괄호를 찾는 함수입니다.
        :param close_line: 닫는 중괄호 라인 번호
        :return: 여는 중괄호의 brace_info 딕셔너리
        """
        contextDiff = 0
        for line in range(close_line, 0, -1):
            brace_info = self.brace_count.get(line, {'open': 0, 'close': 0, 'cfg_node': None})
            contextDiff += brace_info['open'] - brace_info['close']

            if contextDiff == 0 and brace_info['open'] > 0:
                cfg_node = brace_info['cfg_node']
                if cfg_node and cfg_node.condition_node_type in ["while", "if"]:
                    return brace_info
                elif cfg_node and cfg_node.condition_node_type in ["else if", "else"] :
                    continue
        return None

    def join_leaf_nodes(self, condition_node):
        """
        주어진 조건 노드의 하위 그래프를 탐색하여 리프 노드들을 수집하고 변수 정보를 조인합니다.
        :param condition_node: 최상위 조건 노드 (if 노드)
        :return: 조인된 변수 정보를 가진 새로운 블록
        """
        # 리프 노드 수집
        leaf_nodes = self.collect_leaf_nodes(condition_node)

        # 리프 노드들의 변수 정보를 조인
        joined_variables = {}
        for node in leaf_nodes:
            if node.function_exit_node:
                continue
            for var_name, var_value in node.variables.items():
                if var_name in joined_variables:
                    # 기존 변수와 조인
                    joined_variables[var_name] = self.join_variable_values(joined_variables[var_name], var_value)
                else:
                    # 새로운 변수 추가
                    joined_variables[var_name] = var_value

        # 새로운 블록 생성 및 변수 정보 저장
        new_block = CFGNode(name=f"JoinBlock_{self.current_start_line}")
        new_block.variables = joined_variables

        # **CFG 그래프에 새로운 블록 추가**
        self.current_target_function_cfg.graph.add_node(new_block)

        # **리프 노드들과 새로운 블록을 에지로 연결**
        for node in leaf_nodes:
            # 기존의 successor가 없으므로, 리프 노드에서 new_block으로 에지를 연결
            self.current_target_function_cfg.graph.add_edge(node, new_block)

        # **조건 노드의 successor를 새로운 블록으로 연결**
        successors = list(self.current_target_function_cfg.graph.successors(condition_node))
        for succ in successors:
            # 조건 노드와 successor 간의 에지를 제거하고, 새로운 블록과 successor를 연결
            self.current_target_function_cfg.graph.remove_edge(condition_node, succ)
            self.current_target_function_cfg.graph.add_edge(new_block, succ)

        return new_block

    def collect_leaf_nodes(self, node):
        """
        주어진 노드의 하위 그래프를 탐색하여 리프 노드들을 수집합니다.
        :param node: 시작 노드
        :return: 리프 노드들의 리스트
        """
        leaf_nodes = []
        visited = set()
        stack = [node]

        while stack:
            current_node = stack.pop()
            if current_node in visited:
                continue
            visited.add(current_node)

            successors = list(self.current_target_function_cfg.graph.successors(current_node))
            if not successors:
                # 자식이 없는 노드 (리프 노드)
                leaf_nodes.append(current_node)
            else:
                # 자식 노드가 있는 경우 스택에 추가
                for successor in successors:
                    stack.append(successor)

        return leaf_nodes

    def join_variable_values(self, val1, val2):
        """
        elementary Interval 간의 join
        - 둘 다 Interval이면 val1.join(val2)
        - boolInterval이면 val1.join(val2)
        - 그 외 => symbolic or val1?
        """
        if hasattr(val1, 'join') and hasattr(val2, 'join') and type(val1) == type(val2):
            return val1.join(val2)
        else:
            # 타입 다르거나 join 불가 => symbolic
            return f"symbolicJoin({val1},{val2})"

    # ――― widening-join (⊔ω) ――――――――――――――――――――――――――――――――――
    def join_variables_with_widening(self, left_vars: dict | None,
                                     right_vars: dict | None) -> dict:
        """
        Interval 에서는   a.widen(b)   를 사용
        BoolInterval 등 widen 정의가 있으면 그대로, 없으면 그냥 join
        """
        if left_vars is None:
            return self.copy_variables(right_vars or {})

        res = self.copy_variables(left_vars)
        for k, rv in (right_vars or {}).items():
            if k in res and hasattr(res[k], "widen"):
                res[k] = res[k].widen(rv)
            else:
                res[k] = rv.copy() if hasattr(rv, "copy") else rv
        return res

    # ――― simple join (⊔)  – narrowing 단계용 ――――――――――――――――――――――
    def join_variables_simple(self, left_vars: dict | None,
                              right_vars: dict | None) -> dict:
        if left_vars is None:
            return self.copy_variables(right_vars or {})

        res = self.copy_variables(left_vars)
        for k, rv in (right_vars or {}).items():
            if k in res and hasattr(res[k], "join"):
                res[k] = res[k].join(rv)
            else:
                res[k] = rv.copy() if hasattr(rv, "copy") else rv
        return res

    # ――― narrow – old ⊓ new  ―――――――――――――――――――――――――――――――――――
    def narrow_variables(self, old_vars: dict, new_vars: dict) -> dict:
        res = self.copy_variables(old_vars)
        for k, nv in new_vars.items():
            if k in res and hasattr(res[k], "narrow"):
                res[k] = res[k].narrow(nv)
            else:
                res[k] = nv.copy() if hasattr(nv, "copy") else nv
        return res

    def get_true_block(self, condition_node):
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not function_cfg:
            raise ValueError("No active function to process the require statement.")

        # 해당 조건 노드에서 true일 때 실행될 블록을 찾아 리턴
        successors = list(function_cfg.graph.successors(condition_node))
        for successor in successors:
            if function_cfg.graph.edges[condition_node, successor].get('condition', False):
                return successor
        return None  # True 블록을 찾지 못하면 None 반환

    def get_false_block(self, condition_node):
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not function_cfg:
            raise ValueError("No active function to process the require statement.")

        # 해당 조건 노드에서 false일 때 실행될 블록을 찾아 리턴
        successors = list(function_cfg.graph.successors(condition_node))  # --- 수정 ---
        for successor in successors:
            if not function_cfg.graph.edges[condition_node, successor].get('condition', False):
                return successor
        return None  # False 블록을 찾지 못하면 None 반환

    def find_corresponding_condition_node(self): # else if, else에 대한 처리
        # 현재 라인부터 위로 탐색하면서 대응되는 조건 노드를 찾음
        target_brace = 0
        for line in range(self.current_start_line - 1, 0, -1):
            brace_info = self.brace_count[line]
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


    """
    Abstract Interpretation part
    """

    @staticmethod
    def calculate_default_interval(var_type):
        # 1. int 타입 처리
        if var_type.startswith("int"):
            length = int(var_type[3:]) if var_type != "int" else 256  # int 타입의 길이 (기본값은 256)
            return IntegerInterval.bottom(length)  # int의 기본 범위 반환

        # 2. uint 타입 처리
        elif var_type.startswith("uint"):
            length = int(var_type[4:]) if var_type != "uint" else 256  # uint 타입의 길이 (기본값은 256)
            return UnsignedIntegerInterval.bottom(length)  # uint의 기본 범위 반환

        # 3. bool 타입 처리
        elif var_type == "bool":
            return BoolInterval()  # bool은 항상 0 또는 1

        # 4. 기타 처리 (필요시 확장 가능)
        else:
            raise ValueError(f"Unsupported type for default interval: {var_type}")

    def update_left_var(self, expr, rVal, operator, variables, callerObject=None, callerContext=None):
        if expr.context == "IndexAccessContext" :
            return self.update_left_var_of_index_access_context(expr, rVal, operator, variables,
                                                                callerObject, callerContext)
        elif expr.context == "MemberAccessContext" :
            return self.update_left_var_of_member_access_context(expr, rVal, operator, variables,
                                                                callerObject, callerContext)

        elif expr.context == "IdentifierExpContext" :
            return self.update_left_var_of_identifier_context(expr, rVal, operator, variables,
                                                              callerObject, callerContext)
        elif expr.context == "LiteralExpContext" :
            return self.update_left_var_of_literal_context(expr, rVal, operator, variables,
                                                                callerObject)
        return None

    def compound_assignment(self, left_interval, right_interval, operator):
        if operator == '=' :
            return right_interval
        elif operator == '+=':
            return left_interval.add(right_interval)
        elif operator == '-=':
            return left_interval.subtract(right_interval)
        elif operator == '*=':
            return left_interval.multiply(right_interval)
        elif operator == '/=':
            return left_interval.divide(right_interval)
        elif operator == '%=':
            return left_interval.modulo(right_interval)
        elif operator == '|=':
            return left_interval.bitwise_or(right_interval)
        elif operator == '^=':
            return left_interval.bitwise_xor(right_interval)
        elif operator == '&=':
            return left_interval.bitwise_and(right_interval)
        elif operator in ['<<=', '>>=', '>>>=']:
            # '<<=', '>>=' 등에서 '=' 제거 후 처리
            return left_interval.shift(right_interval, operator[:-1])
        else:
            raise ValueError(f"Unsupported operator '{operator}' in compound assignment")

    def update_left_var_of_index_access_context(self, expr, rVal, operator, variables,
                                                callerObject=None, callerContext=None):
        # base expression에 대한 재귀
        base_obj = self.update_left_var(expr.base, rVal, operator, variables, None, "IndexAccessContext")

        # index expression에 대한 재귀
        self.update_left_var(expr.index, rVal, operator, variables, base_obj, "IndexAccessContext")

    def update_left_var_of_member_access_context(self, expr, rVal, operator, variables,
                                                 callerObject=None, callerContext=None) :
        base_obj = self.update_left_var(expr.base, rVal, operator, variables, None, "MemberAccessContext")
        member = expr.member

        if isinstance(base_obj, StructVariable) :
            if member in base_obj.members :
                nestedMember = base_obj.members[member]
                if isinstance(nestedMember, Variables) or isinstance(nestedMember, EnumVariable):
                    nestedMember.value = self.compound_assignment(nestedMember.value, rVal, operator)
                elif isinstance(nestedMember, StructVariable) or isinstance(nestedMember, ArrayVariable) :
                    return nestedMember  # 구조체 안에 member가 ArrayVariable, StructVariable 등인경우
                else :
                    raise ValueError(f"This object '{nestedMember}' is not expected in this context")
            else :
                raise ValueError(f"This member '{member}' is not included in struct '{base_obj.identifier}'")

    def update_left_var_of_literal_context(self, expr, rVal, operator, variables,
                                           callerObject=None):
        literal_str = expr.literal  # 예: "123", "0x1A", "true", "false", "Hello", ...
        expr_type = expr.expr_type  # 예: 'uint', 'int', 'bool', 'string'

        # assignment의 좌변 변수에 대해서는 literal은 callerObject 없이 있을 수 없는듯
        if callerObject is not None:
            # assignment의 좌변 변수에 대해서, literal이 오는 경우는 Array랑 Mapping 밖에 없는듯?
            if isinstance(callerObject, ArrayVariable):
                if literal_str.isdigit():
                    # 인덱스로 해석 (음수인지도 체크 가능)
                    idx = int(literal_str)
                    if idx < 0 or idx >= len(callerObject.elements):
                        raise IndexError(f"Index {idx} out of range in array '{callerObject.identifier}'")

                    element = callerObject.elements[idx]
                    if isinstance(element, Variables) or isinstance(element, EnumVariable) :
                        if not self._is_interval(rVal) :
                            if rVal.startswith('-') or rVal.isdigit() or rVal in ["true", "false"] :
                                rVal = self.convert_literal_to_interval(rVal, element)
                        element.value = self.compound_assignment(element.value, rVal, operator)
                        return None
                    elif isinstance(element, ArrayVariable) or isinstance(element, StructVariable) :
                        return element
                    return None
                return None
            elif isinstance(callerObject, MappingVariable):
                if literal_str in callerObject.mapping :
                    mapVar = callerObject.mapping[literal_str]
                    if isinstance(mapVar, Variables) or isinstance(mapVar, EnumVariable) :
                        if not self._is_interval(rVal) :
                            if rVal.startswith('-') or rVal.isdigit() or rVal in ["true", "false"]:
                                rVal = self.convert_literal_to_interval(rVal, mapVar)
                        mapVar.value = self.compound_assignment(mapVar.value, rVal, operator)
                        return None
                    elif isinstance(mapVar, ArrayVariable) or isinstance(mapVar, StructVariable)\
                            or isinstance(mapVar, MappingVariable):
                        return mapVar
                    return None
                return None
            return None
        else :
            raise ValueError(f"This literal context '{literal_str}' is wrong context")

    def update_left_var_of_identifier_context(self, expr, rVal, operator, variables:dict,
                                              callerObject=None, callerContext=None):
        ident_str = expr.identifier

        if callerObject is not None :
            if isinstance(callerObject, Variables) or isinstance(callerObject, EnumVariable) :
                callerObject.value = self.compound_assignment(callerObject.value, rVal, operator)
            elif isinstance(callerObject, ArrayVariable) : # index
                if ident_str not in variables:
                    raise ValueError(f"Index identifier '{ident_str}' not found in variables.")
                index_var_obj = variables[ident_str]
                if isinstance(index_var_obj, Variables):
                    if index_var_obj.value.min_value == index_var_obj.value.max_value:
                        idx = index_var_obj.value.min_value
                else:
                    raise ValueError(f"This excuse should be analyzed : '{ident_str}'")

                # 경계검사
                if idx < 0 or idx >= len(callerObject.elements):
                    raise IndexError(f"Index {idx} out of range in array '{callerObject.identifier}'")

                element = callerObject.elements[idx]
                if isinstance(element, Variables) or isinstance(element, EnumVariable) :
                    element.value = self.compound_assignment(element.value, rVal, operator)
                elif isinstance(element, ArrayVariable) or isinstance(element, StructVariable) :
                    return element
                elif isinstance(element, MappingVariable) :
                    raise ValueError(f"Is Mapping Variable is available of Array Variable's elements?")
            elif isinstance(callerObject, StructVariable) :
                if ident_str not in callerObject.members:
                    raise ValueError(f"member identifier '{ident_str}' not found in struct variables.")

                member = callerObject.members[ident_str]

                if isinstance(member, Variables) or isinstance(member, EnumVariable) :
                    member.value = self.compound_assignment(member.value, rVal, operator)
                elif isinstance(member, ArrayVariable) or isinstance(member, StructVariable) \
                        or isinstance(member, MappingVariable) :
                    return member
            elif isinstance(callerObject, MappingVariable) :
                if ident_str not in callerObject.mapping:
                    raise ValueError(f"mapping identifier '{ident_str}' not found in mapping variables.")

                mapVar = callerObject.mapping[ident_str]

                if isinstance(mapVar, Variables) or isinstance(mapVar, EnumVariable) :
                    mapVar.value = self.compound_assignment(mapVar.value, rVal, operator)
                elif isinstance(mapVar, ArrayVariable) or isinstance(mapVar, StructVariable) \
                        or isinstance(mapVar, MappingVariable) :
                    return mapVar

        if callerContext is not None :
            if callerContext == "IndexAccessContext" or "MemberAccessContext" :
                if ident_str in variables : # base에 대한 탐색
                    return variables[ident_str]

        if ident_str in variables :
            if isinstance(variables[ident_str], Variables) :
                variables[ident_str].value = self.compound_assignment(variables[ident_str].value, rVal, operator)

    def convert_literal_to_interval(self, literalValue:str, variableObj:Variables):
        if literalValue.startswith('-') or literalValue.isdigit() :
            varType = variableObj.typeInfo.elementaryTypeName
            varLen = variableObj.typeInfo.intTypeLength
            if varType.startswith("int") :
                return IntegerInterval(int(literalValue), int(literalValue), varLen)
            elif varType.startswith("uint") :
                return UnsignedIntegerInterval(int(literalValue), int(literalValue), varLen)
        elif literalValue in ["true", "false"] :
            lower_str = literalValue.lower()
            if lower_str == "true":
                return BoolInterval(1, 1)
            elif lower_str == "false":
                return BoolInterval(0, 0)
            else:
                raise ValueError(f"Invalid boolean literal '{literalValue}'")

    def evaluate_expression(self, expr: Expression, variables: Variables, callerObject=None, callerContext=None):
        if expr.context == "LiteralExpContext":
            return self.evaluate_literal_context(expr, variables, callerObject, callerContext)
        elif expr.context == "IdentifierExpContext" :
            return self.evaluate_identifier_context(expr, variables, callerObject, callerContext)
        elif expr.context == 'MemberAccessContext' :
            return self.evaluate_member_access_context(expr, variables, callerObject, callerContext)
        elif expr.context == "IndexAccessContext" :
            return self.evaluate_index_access_context(expr, variables, callerObject, callerContext)
        elif expr.context == "TypeConversionContext" :
            return self.evaluate_type_conversion_context(expr, variables, callerObject, callerContext)
        elif expr.context == "ConditionalExpContext" :
            return self.evaluate_conditional_expression_context(expr, variables, callerObject, callerContext)
        elif expr.context == "InlineArrayExpression" :
            return self.evaluate_inline_array_expression_context(expr, variables, callerObject, callerContext)
        elif expr.context == "FunctionCallContext" :
            return self.evaluate_function_call_context(expr, variables, callerObject, callerContext)

        # 단항 연산자
        if expr.operator in ['-', '!', '~'] and expr.expression :
            return self.evaluate_unary_operator(expr, variables, callerObject, callerContext)

        # 이항 연산자
        if expr.left is not None and expr.right is not None :
            return self.evaluate_binary_operator(expr, variables, callerObject, callerContext)

    def evaluate_literal_context(self, expr: Expression, variables, callerObject=None, callerContext=None):
        literal_str = expr.literal  # 예: "123", "0x1A", "true", "false", "Hello", ...
        expr_type = expr.expr_type  # 예: 'uint', 'int', 'bool', 'string'

        # 1) if we have a callerObject that is an ArrayVariable, and the literal is a digit
        if callerObject is not None :
            if isinstance(callerObject, ArrayVariable) :
                if literal_str.isdigit() :
                    # 인덱스로 해석 (음수인지도 체크 가능)
                    idx = int(literal_str)
                    if idx < 0 or idx >= len(callerObject.elements):
                        raise IndexError(f"Index {idx} out of range in array '{callerObject.identifier}'")
                    return callerObject.elements[idx]  # element: Variables, ArrayVariable, etc.
                else:
                    raise ValueError(
                        f"Array '{callerObject.identifier}' index must be integer literal, got '{literal_str}'")

            # 1-2) MappingVariable
            elif isinstance(callerObject, MappingVariable):
                # 맵핑 키로 사용. Solidity에선 key가 uint/address/bytes 등 가능하나,
                # 여기선 예시로 'string' key 로 처리
                if literal_str in callerObject.mapping:
                    return callerObject.mapping[literal_str]
                else:
                    # 새로 엔트리 생성
                    new_var_obj = self.create_default_mapping_value(callerObject, literal_str)

                    # callerObject.mapping[literal_str] = new_var_obj
                    # state_variable_node / function_cfg 둘 다 업데이트
                    self.update_mapping_in_cfg(callerObject.identifier, literal_str, new_var_obj)

                    return new_var_obj.value

        if callerContext is not None : # callerObject는 없고 callerContext가 있는 경우
            if callerContext == "IndexAccessContext" : # literal_str이 이면서 IndexAccess면 mapping key 호출 밖에 없을듯?
                return literal_str

        # callerObject, callerContext 둘다 없으면 그냥 값 리턴
        if expr_type == "uint":
            # int() with base=0로 파싱해 다양한 16진/10진 포맷 허용
            val = int(literal_str, 0)
            if val < 0:
                raise ValueError(f"Literal '{literal_str}' is negative, not valid for uint.")
            # 기본 비트 길이 설정
            length = expr.type_length if expr.type_length else 256
            return UnsignedIntegerInterval(val, val, length)

        elif expr_type == "int":
            val = int(literal_str, 0)
            length = expr.type_length if expr.type_length else 256
            return IntegerInterval(val, val, length)

        elif expr_type == "bool":
            lower_str = literal_str.lower()
            if lower_str == "true":
                return BoolInterval(1, 1)
            elif lower_str == "false":
                return BoolInterval(0, 0)
            else:
                raise ValueError(f"Invalid boolean literal '{literal_str}'")

        elif expr_type == "string":
            # 여기서 그대로 문자열 반환.
            # 필요하면 앞뒤 따옴표 제거 로직도 추가할 수 있음.
            return literal_str

        else:
            raise ValueError(f"Unsupported literal expr_type '{expr_type}'")

    def evaluate_identifier_context(self, expr:Expression, variables, callerObject=None, callerContext=None):
        ident_str = expr.identifier

        # callerObject가 있는 경우
        if callerObject is not None:
            if isinstance(callerObject, ArrayVariable) : # ident_Str이 index면 index별 join 필요 (index의 interval 크기, array의 길이 참조)
                if ident_str not in variables:
                    raise ValueError(f"Index identifier '{ident_str}' not found in variables.")
                index_var_obj = variables[ident_str]
                if isinstance(index_var_obj, Variables) :
                    if index_var_obj.value.min_value == index_var_obj.value.max_value:
                        idx = index_var_obj.value.min_value
                else :
                    raise ValueError(f"This excuse should be analyzed : '{ident_str}'")

                # 경계검사
                if idx < 0 or idx >= len(callerObject.elements):
                    raise IndexError(f"Index {idx} out of range in array '{callerObject.identifier}'")
                return callerObject.elements[idx]

            elif isinstance(callerObject, StructVariable) :
                if ident_str not in callerObject.members:
                    raise ValueError(f"member identifier '{ident_str}' not found in struct variables.")

                var = callerObject.members[ident_str]

                if isinstance(var, Variables) : # int, uint, bool이면 interval address, string이면 symbol을 리턴
                    return var.value
                else : # ArrayVariable, StructVariable
                    return var # var 자체를 리턴 (배열, 다른 구조체일 수 있음)

            elif isinstance(callerObject, EnumDefinition) :
                for enumMemberIndex in range(len(callerObject.members)) :
                    if ident_str == callerObject.members[enumMemberIndex] :
                        return enumMemberIndex

                raise ValueError(f"This '{ident_str}' may not be included in enum def '{callerObject.enum_name}'")

        # callerObject가 없고 callerContext는 있는 경우
        if callerContext is not None :
            if callerContext == "MemberAccessContext" : # base에 대한 접근
                if ident_str in variables :
                    return variables[ident_str] # MappingVariable, StructVariable 자체를 리턴
                elif ident_str in ["block", "tx", "msg", "address", "code"] :
                    return ident_str # block, tx, msg를 리턴
                elif ident_str in self.contract_cfgs[self.current_target_contract].enumDefs : # EnumDef 리턴
                    return self.contract_cfgs[self.current_target_contract].enumDefs[ident_str]
                else :
                    raise ValueError(f"This '{ident_str}' is may be array or struct but may not be declared")
            elif callerContext == "IndexAccessContext" : # base에 대한 접근
                if ident_str in variables :
                    return variables[ident_str] # ArrayVariable 자체를 리턴

        # callerContext, callerObject 둘다 없는 경우
        if ident_str in variables: # variables에 있으면
            return variables[ident_str].value # 해당 value 리턴
        else:
            raise ValueError(f"This '{ident_str}' is may be elementary variable but may not be declared")

    def evaluate_member_access_context(self, expr: Expression, variables, callerObject=None, callerContext=None):

        # 1. base expression 재귀적으로 평가
        base_val = self.evaluate_expression(expr.base, variables, None, "MemberAccessContext")
        member = expr.member

        # 2. 글로벌 변수 접근 (예: block, msg, tx)
        if isinstance(base_val, str) :
            if base_val in {"block", "msg", "tx"}:
                full_name = f"{base_val}.{member}"
                contract_cfg = self.contract_cfgs[self.current_target_contract]

                gv_obj = contract_cfg.globals[full_name]
                func_name = self.current_target_function
                gv_obj.usage_sites.add(func_name)  # ✔ 함수명만 저장

                return gv_obj.current

            elif member == "code" : # base_Val이 str 이면서 member가 code면 address.code 형태
                return member

            elif base_val == "code" :
                if member == "length" :
                    return UnsignedIntegerInterval(1000, 1000, 256)
            else :
                ValueError(f"member '{member}' is not global variable member'.")

        elif isinstance(base_val, ArrayVariable) :
            if callerContext == "functionCallContext" :
                if not base_val.typeInfo.isDynamicArray :
                    raise ValueError ("This variable's type is array and callerContext is functionCall "
                                      "but not dynamic array")
                base_type = base_val.typeInfo.arrayBaseType
                if member == "push" :
                    elementVar = Variables(identifier=base_val.identifier)
                    if base_type.startswith("int", "uint", "bool") :
                        elementVar.value = self.calculate_default_interval(base_type)

                    elif base_type in ["address", "address payable", "string", "bytes", "Byte",
                                                         "Fixed", "Ufixed"] :
                        elementVar.value = str('symbol' + base_val.identifier + "index" + len(base_val.elements))
                    base_val.elements.append(elementVar)
                    base_val.typeInfo.arrayLength += 1
                elif member == "pop" :
                    base_val.elements.pop()

            if member == "length" : # myArray.length
                length_val = len(base_val.elements)
                return UnsignedIntegerInterval(length_val, length_val, 256)

        elif isinstance(base_val, StructVariable) :
            if member in base_val.members :
                nestedMember = base_val.members[member]
                if isinstance(nestedMember, Variables) or isinstance(nestedMember, EnumVariable) :
                    return nestedMember.value # Variable 객체 이므로 Interval 값 등의 value를 리턴
                elif isinstance(nestedMember, StructVariable) or isinstance(nestedMember, ArrayVariable) :
                    return nestedMember # 구조체 안에 member가 ArrayVariable, StructVariable 등인경우
            else :
                raise ValueError(f"This member '{member}' is not included in struct '{base_val}'")

        elif isinstance(base_val, EnumDefinition) : # 이거 좀 수정해야됨
            for enumMemberIndex in range(len(base_val.members)) :
                if member == base_val.members[enumMemberIndex] :
                    return enumMemberIndex

        #elif isinstance(base_val, MappingVariable) : #base_Val이 Mapping이면서 value type이 enum, struct 인경우

        # 5. 타입 정보 접근 (예: type(uint256).max, type(uint256).min)
        if isinstance(base_val, dict) and base_val.get("isType", False):
            T = base_val["typeName"]
            if member == "max":
                if T.startswith("uint"):
                    length = int(T[4:]) if len(T) > 4 else 256
                    return UnsignedIntegerInterval(2 ** length - 1, 2 ** length - 1, length)
                elif T.startswith("int"):
                    length = int(T[3:]) if len(T) > 3 else 256
                    return IntegerInterval(2 ** (length - 1) - 1, 2 ** (length - 1) - 1, length)
                else:
                    raise ValueError(f"Unsupported type for max: {T}")
            elif member == "min":
                if T.startswith("uint"):
                    return UnsignedIntegerInterval(0, 0, 256)
                elif T.startswith("int"):
                    length = int(T[3:]) if len(T) > 3 else 256
                    return IntegerInterval(-2 ** (length - 1), -2 ** (length - 1), length)
                else:
                    raise ValueError(f"Unsupported type for min: {T}")
            else:
                raise ValueError(f"Unsupported type member '{member}' for type '{T}'")

        # 6. Enum 멤버 접근 (base가 enum type을 나타내는 dict)
        if isinstance(base_val, dict) and "enumType" in base_val:
            enum_type = base_val["enumType"]
            # 심볼릭하게 "EnumType.Member"를 리턴 (실제 구현은 contract_cfg에서 값 조회 필요)
            return f"{enum_type}.{member}"

        # 7. 컨트랙트 인스턴스 접근 (base가 contract instance를 나타내는 dict)
        if isinstance(base_val, dict) and "contractInstance" in base_val:
            if member == "address":
                return base_val["address"]
            return f"{base_val['contractInstance']}.{member}"

        # 8. 라이브러리 확장 메소드 (callerContext가 "library")
        if callerObject == "library":
            return f"library_function({base_val}).{member}"

        # 9. 만약 위 케이스에 해당하지 않으면 심볼릭하게 표현
        return f"symbolic({base_val}.{member})"

    def evaluate_index_access_context(self, expr, variables, callerObject=None, callerContext=None):
        """
        해석 로직:
          1) base_val = evaluate_expression(expr.base, variables, ..., callerContext="IndexAccessContext")
          2) index_val = evaluate_expression(expr.index, variables, callerObject=base_val, callerContext="IndexAccessContext")
          3) base_val이 ArrayVariable이면 -> arrayVar.elements[index]
             base_val이 MappingVariable이면 -> mappingVar.mapping[indexKey]
             그 외 -> symbolic/error
        """

        # 1) base 해석
        base_val = self.evaluate_expression(expr.base, variables, None, "IndexAccessContext")

        if expr.index is not None:
            return self.evaluate_expression(expr.index, variables, base_val, "IndexAccessContext")
        else:
            raise ValueError(f"There is no index expression")

    def evaluate_type_conversion_context(self, expr, variables, callerObject=None, callerContext=None):
        """
        expr: Expression(operator='type_conversion', type_name=..., expression=subExpr, context='TypeConversionContext')
        예:  'uint256(x)', 'int8(y)', 'bool(z)', 'address w' 등

        1) sub_val = evaluate_expression(expr.expression, variables, None, "TypeConversion")
        2) if type_name.startswith('uint'):  -> UnsignedIntegerInterval로 클램핑
           if type_name.startswith('int'):   -> IntegerInterval로 클램핑
           if type_name == 'bool':           -> 0이면 False, 나머지면 True (또는 Interval [0,1])
           if type_name == 'address':        -> int/Interval -> symbolic address, string '0x...' 등등
        3) 반환
        """

        type_name = expr.type_name  # 예: "uint256", "int8", "bool", "address"
        sub_val = self.evaluate_expression(expr.expression, variables, None, "TypeConversion")

        # 1) 우선 sub_val이 Interval(혹은 BoolInterval), str, etc. 중 어느 것인가 확인
        #    편의상, 아래에서 Interval이면 클램핑, BoolInterval이면 bool 변환 등 처리

        # a. bool, int, uint, address 등으로 나누어 처리
        if type_name.startswith("uint"):
            # 예: "uint256", "uint8" 등
            # 1) bits 추출
            bits_str = "".join(ch for ch in type_name[4:] if ch.isdigit())  # "256" or "8" 등
            bits = int(bits_str) if bits_str else 256

            # 2) sub_val이 IntegerInterval/UnsignedIntegerInterval 이라면:
            #    - 음수 부분은 0으로 clamp
            #    - 상한은 2^bits - 1로 clamp
            #    - 만약 sub_val이 BoolInterval, string, etc. => 대략 변환 로직 / symbolic
            return self.convert_to_uint(sub_val, bits)

        elif type_name.startswith("int"):
            # 예: "int8", "int256"
            bits_str = "".join(ch for ch in type_name[3:] if ch.isdigit())
            bits = int(bits_str) if bits_str else 256
            return self.convert_to_int(sub_val, bits)

        elif type_name == "bool":
            # sub_val이 Interval이면:
            #   == 0 => bool false
            #   != 0 => bool true
            # 범위 넓으면 [0,1]
            return self.convert_to_bool(sub_val)

        elif type_name == "address":
            # sub_val이 Interval이면 "address( interval )" → symbolic?
            # sub_val이 string "0x..." -> parse or symbolic
            return self.convert_to_address(sub_val)

        else:
            # 그 외( bytesNN, string, etc. ) => 필요 시 구현
            return f"symbolicTypeConversion({type_name}, {sub_val})"

    def evaluate_conditional_expression_context(self, expr, variables, callerObject=None, callerContext=None):
        """
        삼항 연산자 (condition ? true_expr : false_expr)
        expr: Expression(
          condition=...,  # condition expression
          true_expr=...,  # true-branch expression
          false_expr=..., # false-branch expression
          operator='?:',
          context='ConditionalExpContext'
        )
        """

        # 1) 조건식 해석
        cond_val = self.evaluate_expression(expr.condition, variables, None, "ConditionalCondition")
        # cond_val이 BoolInterval일 가능성이 높음
        # 다른 경우(Interval 등) => symbolic or 0≠0 ?

        if isinstance(cond_val, BoolInterval):
            # (a) cond_val이 [1,1] => 항상 true
            if cond_val.min_value == 1 and cond_val.max_value == 1:
                return self.evaluate_expression(expr.true_expr, variables, callerObject, "ConditionalExp")

            # (b) cond_val이 [0,0] => 항상 false
            if cond_val.min_value == 0 and cond_val.max_value == 0:
                return self.evaluate_expression(expr.false_expr, variables, callerObject, "ConditionalExp")

            # (c) cond_val이 [0,1] => 부분적 => 두 branch 모두 해석 후 join
            true_val = self.evaluate_expression(expr.true_expr, variables, callerObject, "ConditionalExp")
            false_val = self.evaluate_expression(expr.false_expr, variables, callerObject, "ConditionalExp")

            # 두 결과가 모두 Interval이면 => join
            # (IntegerInterval, UnsignedIntegerInterval, BoolInterval 등)
            if (hasattr(true_val, 'join') and hasattr(false_val, 'join')
                    and type(true_val) == type(false_val)):
                return true_val.join(false_val)
            else:
                # 타입이 다르거나, join 메서드 없는 경우 => symbolic
                return f"symbolicConditional({true_val}, {false_val})"

        # 2) cond_val이 BoolInterval가 아님 => symbolic
        # 예: cond_val이 IntegerInterval => 0이 아닌 값은 true?
        # 여기서는 간단히 [0,∞]? => partial => symbolic
        return f"symbolicConditionalCondition({cond_val})"

    def evaluate_inline_array_expression_context(self, expr, variables, callerObject=None, callerContext=None):
        """
        expr: Expression(
           elements = [ expr1, expr2, ... ],
           expr_type = 'array',
           context   = 'InlineArrayExpressionContext'
        )

        이 배열 표현식은 예: [1,2,3], [0x123, 0x456], [true, false], ...
        각 요소를 재귀적으로 evaluate_expression으로 해석하고, 그 결과들을 리스트로 만든다.
        """

        results = []
        for elem_expr in expr.elements:
            # 각 요소를 재귀 해석
            # callerObject, callerContext는 "inline array element"로 명시
            val = self.evaluate_expression(elem_expr, variables, None, "InlineArrayElement")
            results.append(val)

        # -- 2) 여기서 optional로, 모든 요소가 Interval인지, BoolInterval인지, etc.를 확인해
        #       "동일한 타입"인지 검사하거나, 적절히 symbolic 처리할 수도 있음.
        # 여기서는 단순히 그대로 반환

        return results

    def evaluate_unary_operator(self, expr, variables, callerObject=None, callerContext=None):
        operand_interval = self.evaluate_expression(expr.expression, variables, None, "Unary")
        if operand_interval is not None:
            if expr.operator == '-':
                return operand_interval.negate()
            elif expr.operator == '!':
                return operand_interval.logical_not()
            elif expr.operator == '~':
                return operand_interval.bitwise_not()
        else:
            raise ValueError(f"Unable to evaluate operand in unary expression: {expr}")

    def evaluate_binary_operator(self, expr, variables, callerObject=None, callerContext=None):
        leftInterval = self.evaluate_expression(expr.left, variables, None, "Binary")
        rightInterval = self.evaluate_expression(expr.right, variables, None, "Binary")
        operator = expr.operator

        result = None

        if operator == '+':
            result = leftInterval.add(rightInterval)
        elif operator == '-':
            result = leftInterval.subtract(rightInterval)
        elif operator == '*':
            result = leftInterval.multiply(rightInterval)
        elif operator == '/':
            result = leftInterval.divide(rightInterval)
        elif operator == '%':
            result = leftInterval.modulo(rightInterval)
        elif operator == '**':
            result = leftInterval.exponentiate(rightInterval)
        # 시프트 연산자 처리
        elif operator in ['<<', '>>', '>>>']:
            if 'int' in expr.expr_type:
                result = IntegerInterval.shift(leftInterval, rightInterval, operator)
            elif 'uint' in expr.expr_type:
                result = UnsignedIntegerInterval.shift(leftInterval, rightInterval, operator)
            else:
                raise ValueError(f"Unsupported type '{expr.expr_type}' for shift operation")
        # 비교 연산자 처리
        elif operator in ['==', '!=', '<', '>', '<=', '>=']:
            result = self.compare_intervals(leftInterval, rightInterval, operator)
        # 논리 연산자 처리
        elif operator in ['&&', '||']:
            result = leftInterval.logical_op(rightInterval, operator)
        else:
            raise ValueError(f"Unsupported operator '{operator}' in expression: {expr}")

        if isinstance(callerObject, ArrayVariable) or isinstance(callerObject, MappingVariable) :
            return self.evaluate_binary_operator_of_index(result, callerObject)
        else :
            return result

    def evaluate_array_expression(self, variable_obj=None, init_expr=None, variables=None):
        return

    def evaluate_enum_expression(self, expr, variables=None):
        return

    def evaluate_struct_expression(self, variable_obj, init_expr):
        return

    def convert_to_uint(self, sub_val, bits):
        """
        sub_val을 uintN 범위[0..(2^bits-1)]로 클램핑
        """
        type_max = 2 ** bits - 1

        # Interval(UnsignedIntegerInterval or IntegerInterval)인 경우
        if isinstance(sub_val, UnsignedIntegerInterval) or isinstance(sub_val, IntegerInterval):
            # min_value < 0 => clamp to 0
            new_min = max(0, sub_val.min_value)
            new_max = min(type_max, sub_val.max_value)
            if new_min > new_max:
                # 불가능 => bottom
                return UnsignedIntegerInterval(None, None, bits)

            return UnsignedIntegerInterval(new_min, new_max, bits)

        elif isinstance(sub_val, BoolInterval):
            # false => [0,0], true => [1,1], top => [0,1]
            # clamp to [0..1] (여전히 uintN 범위는 가능하니 문제 없음)
            if sub_val.min_value == 1 and sub_val.max_value == 1:
                return UnsignedIntegerInterval(1, 1, bits)
            elif sub_val.min_value == 0 and sub_val.max_value == 0:
                return UnsignedIntegerInterval(0, 0, bits)
            else:
                # [0,1]
                return UnsignedIntegerInterval(0, 1, bits)

        elif isinstance(sub_val, str):
            # string -> parse as decimal? hex?
            # 간단히 symbolic
            return f"symbolicUint{bits}({sub_val})"

        else:
            # fallback
            return f"symbolicUint{bits}({sub_val})"

    def convert_to_int(self, sub_val, bits):
        """
        sub_val을 intN 범위[-2^(bits-1) .. 2^(bits-1)-1]로 클램핑
        """
        type_min = -(2 ** (bits - 1))
        type_max = (2 ** (bits - 1)) - 1

        # Interval
        if isinstance(sub_val, IntegerInterval) or isinstance(sub_val, UnsignedIntegerInterval):
            new_min = max(type_min, sub_val.min_value)
            new_max = min(type_max, sub_val.max_value)
            if new_min > new_max:
                # bottom
                return IntegerInterval(None, None, bits)
            return IntegerInterval(new_min, new_max, bits)

        elif isinstance(sub_val, BoolInterval):
            # false => [0,0], true => [1,1], top => [0,1]
            # clamp to [-2^(bits-1), 2^(bits-1)-1]
            if sub_val.min_value == 1 and sub_val.max_value == 1:
                val = 1
                if val < type_min or val > type_max:
                    # bottom
                    return IntegerInterval(None, None, bits)
                return IntegerInterval(val, val, bits)
            elif sub_val.min_value == 0 and sub_val.max_value == 0:
                val = 0
                if val < type_min or val > type_max:
                    return IntegerInterval(None, None, bits)
                return IntegerInterval(val, val, bits)
            else:
                # [0,1]
                # => [0,1] intersect with [type_min..type_max]
                new_min = max(type_min, 0)
                new_max = min(type_max, 1)
                if new_min > new_max:
                    return IntegerInterval(None, None, bits)
                return IntegerInterval(new_min, new_max, bits)

        elif isinstance(sub_val, str):
            # parse or symbolic
            return f"symbolicInt{bits}({sub_val})"

        else:
            return f"symbolicInt{bits}({sub_val})"

    def convert_to_bool(self, sub_val):
        """
        int/uint interval -> 0 => false, !=0 => true => [0,1] 형태
        """
        if isinstance(sub_val, IntegerInterval) or isinstance(sub_val, UnsignedIntegerInterval):
            if sub_val.is_bottom():
                return BoolInterval(None, None)
            # if entire range is strictly 0..0 => false
            if sub_val.min_value == 0 and sub_val.max_value == 0:
                return BoolInterval(0, 0)
            # if entire range is non-zero => true => [1,1]
            if sub_val.min_value > 0:
                return BoolInterval(1, 1)
            # if partial includes 0 and nonzero => [0,1]
            return BoolInterval(0, 1)

        elif isinstance(sub_val, BoolInterval):
            # 이미 bool => 그대로 반환 가능
            return sub_val

        elif isinstance(sub_val, str):
            # string => symbolic bool
            return BoolInterval(0, 1)

        # fallback
        return BoolInterval(0, 1)

    def convert_to_address(self, sub_val):
        """
        address(...) 변환 예시:
        - int interval => symbolic address, 단일값 => 'address(0x..)'?
        - string => if startswith("0x") => parse? else symbolic
        """
        # 실무에선 address는 160bit => [0..2^160-1]
        # 여기선 간단히 symbolic
        if isinstance(sub_val, IntegerInterval) or isinstance(sub_val, UnsignedIntegerInterval):
            if sub_val.min_value == sub_val.max_value:
                # 단일 값 => e.g. 'address(12345)'
                return f"address({sub_val.min_value})"
            else:
                # symbolic
                return f"symbolicAddressInterval([{sub_val.min_value}, {sub_val.max_value}])"

        elif isinstance(sub_val, str):
            # 간단히 '0x'로 시작하면 주소로 간주?
            if sub_val.startswith("0x"):
                return sub_val  # already address string
            else:
                return f"symbolicAddress({sub_val})"

        elif isinstance(sub_val, BoolInterval):
            # bool -> address => symbolic
            return f"symbolicAddressFromBool({sub_val})"

        else:
            return f"symbolicAddress({sub_val})"

    def evaluate_binary_operator_of_index(self, result, callerObject):
        # 2) callerObject가 ArrayVariable이면 => 인덱스 접근 결과로 해석
        if isinstance(callerObject, ArrayVariable):
            # result가 Interval인지 검사
            if not hasattr(result, 'min_value') or not hasattr(result, 'max_value'):
                # result가 BoolInterval or symbolic 등 => array 인덱스로 사용 불가 → symbolic
                return f"symbolicIndex({callerObject.identifier}[{result}])"

            # (a) bottom이면 symbolic or direct bottom
            if result.is_bottom():
                return f"symbolicIndex({callerObject.identifier}[BOTTOM])"

            min_idx = result.min_value
            max_idx = result.max_value
            if min_idx is None or max_idx is None:
                # None이면 bottom => symbolic
                return f"symbolicIndex({callerObject.identifier}[{result}])"

            # (b) 단일값?
            if min_idx == max_idx:
                idx = min_idx
                # 범위체크
                if idx < 0 or idx >= len(callerObject.elements):
                    raise IndexError(f"Index {idx} out of range for array '{callerObject.identifier}'")
                element_var = callerObject.elements[idx]
                # element_var가 Variables면 element_var.value가 실제 Interval/주소/등일 수 있음
                if hasattr(element_var, 'value'):
                    return element_var.value
                else:
                    return element_var  # ArrayVariable/StructVariable 등

            # (c) 범위: [min_idx..max_idx]
            # 각 요소를 순회하며 join
            joined = None
            for idx in range(min_idx, max_idx + 1):
                if idx < 0 or idx >= len(callerObject.elements):
                    # 범위 벗어나면 symbolic 처리
                    return f"symbolicIndexRange({callerObject.identifier}[{result}])"

                elem_var = callerObject.elements[idx]
                # elem_var가 Variables => elem_var.value가 Interval일 수도 있고,
                # 다른 타입(주소, bool 등)일 수도 있음
                # 여기선 "전부 Interval이면 join, 아니면 symbolic" 예시
                val = elem_var.value if hasattr(elem_var, 'value') else elem_var

                # 주소 or string or struct => symbolic
                if (isinstance(val, IntegerInterval) or isinstance(val, UnsignedIntegerInterval)
                        or isinstance(val, BoolInterval)):
                    if joined is None:
                        joined = val
                    else:
                        joined = joined.join(val)
                else:
                    return f"symbolicMixedType({callerObject.identifier}[{result}])"

            # 모든 요소를 Interval.join했으면 joined에 최종 Interval
            return joined

        # 3) callerObject가 MappingVariable인 경우 (비슷한 로직 확장 가능)
        if isinstance(callerObject, MappingVariable):
            # result => 단일 키 or 범위 => map lookup
            if not hasattr(result, 'min_value') or not hasattr(result, 'max_value'):
                # symbolic
                return f"symbolicMappingIndex({callerObject.identifier}[{result}])"

            if result.is_bottom():
                return f"symbolicMappingIndex({callerObject.identifier}[BOTTOM])"

            min_idx = result.min_value
            max_idx = result.max_value
            if min_idx == max_idx:
                key_str = str(min_idx)
                if key_str in callerObject.mapping:
                    return callerObject.mapping[key_str].value
                else:
                    # 새로 추가 or symbolic
                    new_var_obj = self.create_default_mapping_value(callerObject, key_str)
                    self.update_mapping_in_cfg(callerObject.identifier, key_str, new_var_obj)
                    return new_var_obj.value
            else:
                # 범위 [min_idx..max_idx], 여러 entry join
                # (실제로 주소형이나 uint형 등 다양한 키 처리 시 로직 필요)
                joined = None
                for k in range(min_idx, max_idx + 1):
                    k_str = str(k)
                    if k_str not in callerObject.mapping:
                        # default
                        new_obj = self.create_default_mapping_value(callerObject, k_str)
                        self.update_mapping_in_cfg(callerObject.identifier, k_str, new_obj)
                        val = new_obj.value
                    else:
                        val = callerObject.mapping[k_str].value

                    # join
                    if isinstance(val, Interval):
                        if joined is None:
                            joined = val
                        else:
                            joined = joined.join(val)
                    else:
                        return f"symbolicMixedType({callerObject.identifier}[{result}])"

                return joined

    def create_default_mapping_value(self, mappingVar: MappingVariable, key_str: str):
        """
        mappingVar: MappingVariable
        key_str: 키 문자열
        이 매핑에 새로 들어갈 기본값(Variables 객체)을 생성해 반환
        예: int/uint -> 0, bool -> False, ...
        """
        value_type_info = mappingVar.typeInfo.mappingValueType
        # 일단 elementary 가정
        if value_type_info.elementaryTypeName.startswith("int"):
            length = value_type_info.intTypeLength or 256
            zero_interval = IntegerInterval(0, 0, length)
            new_obj = Variables(identifier=f"{mappingVar.identifier}[{key_str}]",
                                value=zero_interval,
                                typeInfo=value_type_info)
            mappingVar.mapping[key_str] = new_obj
            return new_obj
        elif value_type_info.elementaryTypeName.startswith("uint"):
            length = value_type_info.intTypeLength or 256
            zero_interval = UnsignedIntegerInterval(0, 0, length)
            new_obj = Variables(identifier=f"{mappingVar.identifier}[{key_str}]",
                                value=zero_interval,
                                typeInfo=value_type_info)
            mappingVar.mapping[key_str] = new_obj
            return new_obj
        elif value_type_info.elementaryTypeName == "bool":
            bool_obj = Variables(identifier=f"{mappingVar.identifier}[{key_str}]",
                                 value=BoolInterval(0, 0),
                                 typeInfo=value_type_info)
            mappingVar.mapping[key_str] = bool_obj
            return bool_obj
        else:
            # fallback for other types - struct, array, ...
            # possibly create a symbolic placeholder
            sym_obj = Variables(identifier=f"{mappingVar.identifier}[{key_str}]",
                                value=f"symbolicDefault({value_type_info.elementaryTypeName})",
                                typeInfo=value_type_info)
            mappingVar.mapping[key_str] = sym_obj
            return sym_obj

    def update_mapping_in_cfg(self, mapVarName: str, key_str: str, new_var_obj: Variables):
        """
        mapVarName: "myMapping"
        key_str: "someKey"
        new_var_obj: 새로 만든 Variables(...) for the mapping value
        여기에 state_variable_node, function_cfg 등을 업데이트
        """
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # state_variable_node 갱신
        if contract_cfg.state_variable_node and mapVarName in contract_cfg.state_variable_node.variables:
            mapVar = contract_cfg.state_variable_node.variables[mapVarName]
            if isinstance(mapVar, MappingVariable):
                mapVar.mapping[key_str] = new_var_obj

        # 함수 CFG 갱신
        function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if function_cfg:
            if mapVarName in function_cfg.related_variables:
                mapVar2 = function_cfg.related_variables[mapVarName]
                if isinstance(mapVar2, MappingVariable):
                    mapVar2.mapping[key_str] = new_var_obj

    def update_variables_with_condition(self, variables, condition_expr, is_true_branch):
        """
            condition_expr: Expression
              - 연산자(operator)가 비교연산(==,!=,<,>,<=,>=)일 수도 있고,
              - 논리연산(&&, ||, !)일 수도 있고,
              - 단일 변수(IdentifierExpContext)나 bool literal, etc. 일 수도 있음
            is_true_branch:
              - True => 조건이 만족되는 브랜치 (if, while 등의 true 분기)
              - False => 조건이 불만족인 브랜치 (else, while not, etc)
            variables: { var_name: Variables }  (CFGNode 상의 변수 상태)
            """

        # 1) condition_expr.operator 파악
        op = condition_expr.operator

        # 2) 만약 operator가 None인데, context가 IdentifierExpContext(단일 변수) 등 “단순 bool 변환”이라면
        if op is None:
            # 예: if (myBoolVar) => true branch라면 myBoolVar = [1,1], false branch라면 myBoolVar=[0,0]
            return self._update_single_condition(variables, condition_expr, is_true_branch)

        # 3) 논리 연산 처리
        elif op in ['&&', '||', '!']:
            return self._update_logical_condition(variables, condition_expr, is_true_branch)

        # 4) 비교 연산 처리 (==, !=, <, >, <=, >=)
        elif op in ['==', '!=', '<', '>', '<=', '>=']:
            return self._update_comparison_condition(variables, condition_expr, is_true_branch)

        else :
            raise ValueError(f"This operator '{op}' is not expected operator")

    def _update_single_condition(self, variables: dict, condition_expr: Expression, is_true_branch: bool):
        """
        예) if (myBoolVar) / while (myBoolVar) / ...
            - true branch => myBoolVar ∈ [1,1]
            - false branch => myBoolVar ∈ [0,0]
        """
        # condition_expr가 IdentifierExpContext or literalExpContext( true / false ) 등인 경우
        # 1) evaluate_expression으로 값을 가져옴
        cond_val = self.evaluate_expression(condition_expr, variables, None, None)
        if isinstance(cond_val, BoolInterval):
            # is_true_branch면 cond_val = [1,1], false면 [0,0]로 좁힘
            new_val = None
            if is_true_branch:
                # meet with [1,1]
                new_val = cond_val.meet(BoolInterval(1, 1))
            else:
                # meet with [0,0]
                new_val = cond_val.meet(BoolInterval(0, 0))
            # cond_val이 변수의 interval일 수도, 아니면 literal일 수도 있으므로
            # 만약 “단일 변수” 식이라면, 그 변수를 찾아서 interval 교체
            var_name = None
            if condition_expr.context == "IdentifierExpContext":
                var_name = condition_expr.identifier
            if var_name and var_name in variables:
                # 교집합 결과로 갱신
                if isinstance(variables[var_name].value, BoolInterval):
                    updated_val = variables[var_name].value.meet(new_val)
                    variables[var_name].value = updated_val
                # struct 일수도 있을듯 추후 수정
        else:
            # cond_val이 BoolInterval이 아닐 수도 있으므로, 간단히 symbolic 처리 or pass
            pass

    def _update_logical_condition(self, variables: dict, cond_expr: Expression, is_true_branch: bool):
        op = cond_expr.operator  # '&&', '||', '!'
        if op == '!':
            # ! X => true branch => X = false, false branch => X=true
            # => is_true_branch = true => X=[0,0], else => X=[1,1]
            # cond_expr.expression 이 실제 operand
            operand_expr = cond_expr.expression
            # 재귀적으로 single_condition 등 호출
            return self._update_single_condition(variables, operand_expr, not is_true_branch)

        elif op == '&&':
            # (condA && condB)
            # true branch => condA=true and condB=true
            # false branch => condA=false OR condB=false (정보손실: 둘 중 하나만 false면 되니까)
            condA = cond_expr.left
            condB = cond_expr.right

            if is_true_branch:
                # A=true, B=true
                self.update_variables_with_condition(variables, condA, True)
                self.update_variables_with_condition(variables, condB, True)
            else:
                # A=false or B=false
                # 단일 Interval domain에선 “둘 중 하나 false”를 따로 분기해서 저장하기 어렵다.
                # 보수적으로 A= [0,1], B=[0,1] 정도로 그냥 pass 하거나, symbolic
                pass

        elif op == '||':
            # (condA || condB)
            # true branch => condA=true or condB=true (Info-loss)
            # false branch => condA=false AND condB=false
            condA = cond_expr.left
            condB = cond_expr.right

            if is_true_branch:
                # A=true or B=true → Interval domain에서는 크게 좁히기 어렵다.
                pass
            else:
                # both false
                self.update_variables_with_condition(variables, condA, False)
                self.update_variables_with_condition(variables, condB, False)

    def _update_comparison_condition(self, variables: dict, cond_expr: Expression, is_true_branch: bool):
        """
        cond_expr.operator in ['<','>','<=','>=','==','!=']
        cond_expr.left, cond_expr.right => Expression
        is_true_branch => True면 cond_expr.operator 그대로 쓰고,
                          False면 negate_operator를 적용
        """
        op = cond_expr.operator
        # negate operator (if is_true_branch==False) => eq <-> !=, < -> >=, ...
        actual_op = op if is_true_branch else self.negate_operator(op)

        left_expr = cond_expr.left
        right_expr = cond_expr.right

        # 1) evaluate_expression으로 좌우 값을 먼저 가져옴
        left_val = self.evaluate_expression(left_expr, variables, None, None)
        right_val = self.evaluate_expression(right_expr, variables, None, None)

        # ========================= CASE 1: 양쪽이 Interval =========================
        if self._is_interval(left_val) and self._is_interval(right_val):
            # 예) a < b → clamp a, b
            updated_left, updated_right = self.refine_intervals_for_comparison(
                left_val, right_val, actual_op
            )

            self.update_left_var(left_expr, updated_left, '=', variables)
            self.update_left_var(right_expr, updated_right, '=', variables)

        # ========================= CASE 2: 한쪽 Interval, 한쪽 literal =========================
        # 예) a < 10, 혹은 0 < b
        elif self._is_interval(left_val) and isinstance(right_val, (int, float, str)):
            # ex) a < 10
            # 1) 우변 literal -> Interval로 변환 시도 (예: int => [10, 10])
            right_intv = self._coerce_literal_to_interval(right_val, left_val.type_length)
            updated_left, _ = self.refine_intervals_for_comparison(
                left_val, right_intv, actual_op
            )
            self.update_left_var(left_expr, updated_left, '=', variables)

        elif self._is_interval(right_val) and isinstance(left_val, (int, float, str)):
            # ex) 0 < b
            left_intv = self._coerce_literal_to_interval(left_val, right_val.type_length)
            # 실제 op가 (left op right)이므로, left=literal, right=interval
            # refine_intervals_for_comparison은 (a_interval, b_interval, op) 순
            updated_left, updated_right = self.refine_intervals_for_comparison(
                left_intv, right_val, actual_op
            )
            self.update_left_var(right_expr, updated_right, '=', variables)

        # ========================= CASE 3: BoolInterval 비교 =========================
        # 예) a == true, boolA != boolB, etc.
        elif isinstance(left_val, BoolInterval) or isinstance(right_val, BoolInterval):
            # 실제론 bool끼리의 <, >는 이상하긴 하지만,
            # == / != 는 가능
            self._update_bool_comparison(variables, left_expr, right_expr, left_val, right_val, actual_op)

        else:
            # 그 외 => symbolic or pass
            pass

    def refine_intervals_for_comparison(self, a_interval, b_interval, op):
        """
        a_interval, b_interval: Interval (IntegerInterval or UnsignedIntegerInterval)
        op: '<', '>', '<=', '>=', '==', '!='
        return: (new_a, new_b)
        """
        # 복사본 생성
        new_a = a_interval.copy()
        new_b = b_interval.copy()

        # ---------- 1) a < b ----------
        if op == '<':
            # a.max < b.min
            # clamp: a.max <= b.min - 1
            if new_b.min_value != float('-inf'):
                candidate_max = new_b.min_value - 1
                if candidate_max < new_a.min_value:
                    new_a = new_a.bottom(new_a.type_length)
                else:
                    new_a.max_value = min(new_a.max_value, candidate_max)

            # b.min >= a.max+1
            if not new_a.is_bottom() and new_a.max_value != float('inf'):
                candidate_min = new_a.max_value + 1
                if candidate_min > new_b.max_value:
                    new_b = new_b.bottom(new_b.type_length)
                else:
                    new_b.min_value = max(new_b.min_value, candidate_min)

            return (new_a, new_b)

        # ---------- 2) a <= b ----------
        if op == '<=':
            # a.max <= b.max
            # a <= b => a.max <= b.min?  (아닌가? Actually: a <= b => a.max <= b.max, b.min >= a.min..)
            # 보수적으로 a.max <= b.max, b.min >= a.min
            # 좀더 정확히: a <= b => a.max <= b.min if we treat strict domain
            # (실제로는 a <= b => a.max <= b.min ? => that’s effectively <)
            # => a <= b is basically (a < b) or (a==b)
            # 여기서는 a <= b => a.max <= b.max (너무 약함)
            # 혹은 (a < b) U (a==b) => clamp both
            # 간단 구현: treat as a < b, then a==b join
            # => pass
            # 아래선 a <= b를 "a < b or a==b"로 처리
            # => a< b clamp + a==b clamp => union => in Interval Domain, union 연산은 join
            lt_a, lt_b = self.refine_intervals_for_comparison(a_interval, b_interval, '<')
            eq_a, eq_b = self.refine_intervals_for_comparison(a_interval, b_interval, '==')
            # join
            join_a = lt_a.join(eq_a)
            join_b = lt_b.join(eq_b)
            return (join_a, join_b)

        # ---------- 3) a > b ----------
        if op == '>':
            # a.min > b.max
            # clamp a.min >= b.max+1
            if new_b.max_value != float('inf'):
                candidate_min = new_b.max_value + 1
                if candidate_min > new_a.max_value:
                    new_a = new_a.bottom(new_a.type_length)
                else:
                    new_a.min_value = max(new_a.min_value, candidate_min)
            # b.max <= a.min-1
            if not new_a.is_bottom() and new_a.min_value != float('-inf'):
                candidate_max = new_a.min_value - 1
                if candidate_max < new_b.min_value:
                    new_b = new_b.bottom(new_b.type_length)
                else:
                    new_b.max_value = min(new_b.max_value, candidate_max)
            return (new_a, new_b)

        # ---------- 4) a >= b ----------
        if op == '>=':
            # a >= b => same trick => union of (a> b) and (a==b)
            gt_a, gt_b = self.refine_intervals_for_comparison(a_interval, b_interval, '>')
            eq_a, eq_b = self.refine_intervals_for_comparison(a_interval, b_interval, '==')
            join_a = gt_a.join(eq_a)
            join_b = gt_b.join(eq_b)
            return (join_a, join_b)

        # ---------- 5) a == b ----------
        if op == '==':
            # a == b => meet(a,b)
            meet_ab = new_a.meet(new_b)
            return (meet_ab, meet_ab)

        # ---------- 6) a != b ----------
        if op == '!=':
            # a != b => (a,b) NOT in (a==b)
            # Interval Domain에서 정확히 "not equal"을 표현하기 어려움
            # 단일 정수라면 exclude => a,b 교집합 빼기
            # 간단히 "no refinement" or symbolic
            return (new_a, new_b)

        # fallback
        return (new_a, new_b)

    def _coerce_literal_to_interval(self, literal_value, default_bits=256):
        """
        literal_value가 int, float, str('123' 같은)이면
        IntegerInterval/UnsignedIntegerInterval 로 대충 변환
        - 여기선 부호 추정이 어려우므로 int인지 uint인지는
          대략 정하거나, int라고 가정
        - 실제론 parse해서 음수/양수 구분, base등 처리 가능
        """
        if isinstance(literal_value, (int, float)):
            # int 범위 - 여기선 int라고 가정
            # 실제론 unsigned 구분 필요
            int_val = int(literal_value)
            return IntegerInterval(int_val, int_val, default_bits)
        if isinstance(literal_value, str):
            # 만약 '123'이면 int 변환
            # 만약 'hello'이면 symbolic?
            try:
                int_val = int(literal_value, 0)
                return IntegerInterval(int_val, int_val, default_bits)
            except ValueError:
                # symbolic
                return IntegerInterval(None, None, default_bits).make_bottom()
        # fallback
        return IntegerInterval(None, None, default_bits).make_bottom()

    def _update_bool_comparison(self, variables: dict,
                                left_expr: Expression, right_expr: Expression,
                                left_val, right_val, op: str):
        """
        예) (boolA == boolB), (boolA != true), ...
        op in ['==','!=','<','>','<=','>='] 중 bool끼리 말이 되는건 ==, != 정도
        ( <, > 등은 사실상 말이 안 되지만 예시로 처리)
        """
        # 우선 bool이 아닌쪽을 boolInterval로 변환 시도?
        # 아니면 단순 symbolic
        if not isinstance(left_val, BoolInterval):
            if isinstance(right_val, BoolInterval):
                # swap
                left_expr, right_expr = right_expr, left_expr
                left_val, right_val = right_val, left_val
            else:
                # 둘다 bool이 아님
                return

        # 이제 left_val은 BoolInterval 확정
        # right_val이 BoolInterval이거나, bool literal => BoolInterval(0 or 1),
        # 또는 int(0 or 1)

        if not isinstance(right_val, BoolInterval):
            # 만약 int(0,0) or (1,1) => 변환
            if self._is_interval(right_val):
                # int interval => [0,0] => false, [1,1] => true, [0,1] => unknown
                bool_equiv = self._convert_int_to_bool_interval(right_val)
                right_val = bool_equiv
            else:
                # symbolic
                return

        # 이제 left_val, right_val 둘 다 BoolInterval
        # op == '==' => left==right => 교집합
        # op == '!=' => left!=right => 부분 부정
        # 그외 <, >, <=, >= => 논리적으로 별 의미 없음 => symbolic or skip
        if op == '==':
            meet_lr = left_val.meet(right_val)
            # left_expr/right_expr가 identifier면 갱신
            left_name = self._extract_identifier_if_possible(left_expr)
            right_name = self._extract_identifier_if_possible(right_expr)
            if left_name in variables:
                variables[left_name].value = meet_lr
            if right_name in variables:
                variables[right_name].value = meet_lr

        elif op == '!=':
            # left != right
            # 만약 left=[0,0], right=[0,0] => meet => bottom
            # if left=[0,1], right=[0,1], => no refinement
            # ...
            # 여기서는 간단히 partial symbolic
            pass

        else:
            # <, >, <=, >= => 보통 bool끼리 잘 안 씀 => symbolic
            pass

    def _convert_int_to_bool_interval(self, int_interval):
        """
        간단히 [0,0] => BoolInterval(0,0),
             [1,1] => BoolInterval(1,1)
             그외 => BoolInterval(0,1)
        """
        if int_interval.is_bottom():
            return BoolInterval(None, None)
        if int_interval.min_value == 0 and int_interval.max_value == 0:
            return BoolInterval(0, 0)  # always false
        elif int_interval.min_value == 1 and int_interval.max_value == 1:
            return BoolInterval(1, 1)  # always true
        else:
            return BoolInterval(0, 1)  # unknown

    def _is_interval(self, val):
        return isinstance(val, (IntegerInterval, UnsignedIntegerInterval, BoolInterval))

    def _extract_variable_of_expression(self, expr):
        """
        expr가 IdentifierExpContext인지 검사하여, 맞으면 expr.identifier 리턴
        아니면 None
        """
        if expr.context == "IdentifierExpContext":
            return expr.identifier
        return None

    def negate_operator(self, op: str) -> str:
        neg_map = {
            '==': '!=',
            '!=': '==',
            '<': '>=',
            '>': '<=',
            '<=': '>',
            '>=': '<'
        }
        return neg_map.get(op, op)

    def evaluate_function_call_context(self, expr, variables, callerObject=None, callerContext=None):
        if expr.context == "MemberAccessContext" : # dynamic array에 대한 push, pop
            return self.evaluate_expression((expr, variables, None, "functionCallContext"))

        if expr.function.identifier:
            function_name = expr.function.identifier
        else:
            raise ValueError (f"There is no function name in function call context")

        # 2) 현재 컨트랙트 CFG 가져오기
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 3) 함수 CFG 가져오기
        function_cfg = contract_cfg.get_function_cfg(function_name)
        if not function_cfg:
            return f"symbolicFunctionCall({function_name})"  # 또는 에러

        # 4) 함수 파라미터와 인자 매핑
        #    expr.arguments -> 위치 기반 인자
        #    expr.named_arguments -> 키워드 인자
        arguments = expr.arguments if expr.arguments else []
        named_arguments = expr.named_arguments if expr.named_arguments else {}

        # 파라미터 목록 (이 예시에서는 function_cfg.parameters를 [paramName1, paramName2, ...]로 가정)
        param_names = getattr(function_cfg, 'parameters', [])
        # 또는 function_cfg가 paramName->type인 dict라면 list(paramName->type) 식으로 바꿔야 함

        total_params = len(param_names)
        total_args = len(arguments) + len(named_arguments)
        if total_params != total_args:
            raise ValueError(f"Argument count mismatch in function call to '{function_name}': "
                             f"expected {total_params}, got {total_args}.")

        # 현재 함수 컨텍스트 저장
        saved_function = self.current_target_function
        self.current_target_function = function_name

        # 5) 인자 해석
        #    순서 기반 인자
        for i, arg_expr in enumerate(arguments):
            param_name = param_names[i]
            arg_val = self.evaluate_expression(arg_expr, variables, None, None)

            # function_cfg 내부의 related_variables에 param_name이 있어야
            if param_name in function_cfg.related_variables:
                function_cfg.related_variables[param_name].value = arg_val
            else:
                raise ValueError(f"Parameter '{param_name}' not found in function '{function_name}' variables.")

        #    named 인자
        #    (예: foo(a=1,b=2)) => paramName->index 매핑이 필요할 수 있음
        #    여기서는 paramName가 function_cfg.parameters[i]와 동일한지 가정
        param_offset = len(arguments)
        for i, (key, expr_val) in enumerate(named_arguments.items()):
            if key not in param_names:
                raise ValueError(f"Unknown named parameter '{key}' in function '{function_name}'.")
            arg_val = self.evaluate_expression(expr_val, variables, None, f"CallNamedArg({function_name})")

            if key in function_cfg.related_variables:
                function_cfg.related_variables[key].value = arg_val
            else:
                raise ValueError(f"Parameter '{key}' not found in function '{function_name}' variables.")

        # 6) 실제 함수 CFG 해석
        return_value = self.interpret_function_cfg(function_cfg)

        # 7) 함수 컨텍스트 복원
        self.current_target_function = saved_function

        return return_value

    def interpret_function_cfg(self, function_cfg):
        """
        수정된 interpret_function_cfg 로직 예시
        """
        entry_block = function_cfg.get_entry_node()
        successors = list(function_cfg.graph.successors(entry_block))
        if len(successors) != 1:
            raise ValueError("Entry block must have exactly one successor.")
        start_block = successors[0]

        # block_queue에는 now just nodes, no variables
        block_queue = deque()
        block_queue.append(start_block)

        # 함수 내 변수 환경은 CFG 노드에 저장됨.
        # entry_block의 successor 시작 시, entry_block.variables를 start_block에 전달
        # entry_block.variables는 아마 constructor나 state_variable_node 해석 후 초기값이 세팅되어 있을 것이라 가정
        # start_block은 predecessor가 entry_block 하나이므로 그냥 그 값 복사
        start_block.variables = self.copy_variables(entry_block.variables)

        # return_values를 모아둘 자료구조 (나중에 exit node에서 join)
        return_values = []

        visited = set()

        while block_queue:
            analyzingNode = block_queue.popleft()
            if analyzingNode in visited:
                continue
            visited.add(analyzingNode)

            # 이전 block 분석 결과 반영
            # join_point_node인 경우 predecessor들의 결과를 join한뒤 analyzingNode에 반영
            # 아니면 predecessor 하나가 있을 것이므로 그 predecessor의 variables를 복사
            predecessors = list(function_cfg.graph.predecessors(analyzingNode))

            # join node 처리
            # predecessor들의 variables를 join
            joined_vars = None
            for pred in predecessors:
                if joined_vars is None:
                    joined_vars = self.copy_variables(pred.variables)
                else:
                    joined_vars = self.join_variables(joined_vars, pred.variables)
            analyzingNode.variables = joined_vars

            current_block = analyzingNode
            current_variables = current_block.variables

            # condition node 처리
            if current_block.condition_node:
                condition_expr = current_block.condition_expr

                if current_block.condition_node_type in ["if", "else if"]:
                    # true/false branch 각각 하나의 successor 가정
                    true_successors = [s for s in function_cfg.graph.successors(current_block) if
                                       function_cfg.graph.edges[current_block, s].get('condition') == True]
                    false_successors = [s for s in function_cfg.graph.successors(current_block) if
                                        function_cfg.graph.edges[current_block, s].get('condition') == False]

                    # 각각 한 개라 가정
                    if len(true_successors) != 1 or len(false_successors) != 1:
                        raise ValueError(
                            "if/else if node must have exactly one true successor and one false successor.")

                    true_variables = self.copy_variables(current_variables)
                    false_variables = self.copy_variables(current_variables)

                    self.update_variables_with_condition(true_variables, condition_expr, is_true_branch=True)
                    self.update_variables_with_condition(false_variables, condition_expr, is_true_branch=False)

                    # true branch로 이어지는 successor enqueue
                    true_succ = true_successors[0]
                    true_succ.variables = true_variables
                    block_queue.append(true_succ)

                    # false branch로 이어지는 successor enqueue
                    false_succ = false_successors[0]
                    false_succ.variables = false_variables
                    block_queue.append(false_succ)
                    continue

                elif current_block.condition_node_type in ["require", "assert"]:
                    # true branch만 존재한다고 가정
                    true_successors = [s for s in function_cfg.graph.successors(current_block) if
                                       function_cfg.graph.edges[current_block, s].get('condition') == True]

                    if len(true_successors) != 1:
                        raise ValueError("require/assert node must have exactly one true successor.")

                    true_variables = self.copy_variables(current_variables)
                    self.update_variables_with_condition(true_variables, condition_expr, is_true_branch=True)

                    true_succ = true_successors[0]
                    true_succ.variables = true_variables
                    block_queue.append(true_succ)
                    continue

                elif current_block.condition_node_type in ["while", "for", "do_while"]:
                    # while 루프 처리
                    # fixpoint 계산 후 exit_node 반환
                    exit_node = self.fixpoint(current_block)
                    # exit_node의 successor는 하나라고 가정
                    successors = list(function_cfg.graph.successors(exit_node))
                    if len(successors) == 1:
                        next_node = successors[0]
                        next_node.variables = self.copy_variables(exit_node.variables)
                        block_queue.append(next_node)
                    elif len(successors) == 0:
                        # while 종료 후 아무 successor도 없으면 끝
                        pass
                    else:
                        raise ValueError("While exit node must have exactly one successor.")
                    continue

                elif current_block.fixpoint_evaluation_node:
                    # 그냥 continue
                    continue
                else:
                    raise ValueError(f"Unknown condition node type: {current_block.condition_node_type}")

            else:
                # condition node가 아닌 일반 블록
                # 블록 내 문장 해석
                for stmt in current_block.statements:
                    current_variables = self.update_statement_with_variables(stmt, current_variables)

                # return이나 revert를 만나지 않았다면 successors 방문
                successors = list(function_cfg.graph.successors(current_block))
                if len(successors) == 1:
                    next_node = successors[0]
                    # next_node에 현재 변수 상태를 반영
                    next_node.variables = self.copy_variables(current_variables)
                    block_queue.append(next_node)
                elif len(successors) > 1:
                    raise ValueError("Non-condition, non-join node should not have multiple successors.")
                # successors가 없으면 리프노드이므로 그냥 끝.

        # exit node에 도달했다면 return_values join
        # 모든 return을 모아 exit node에서 join 처리할 수 있으나, 여기서는 단순히 top-level에서 return_values를 join
        if len(return_values) == 0:
            return None
        elif len(return_values) == 1:
            return return_values[0]
        else:
            # 여러 return 값 join 로직 필요 (정수 interval join 등)
            joined_ret = return_values[0]
            for rv in return_values[1:]:
                joined_ret = joined_ret.join(rv)
            return joined_ret

    def interpret_variable_declaration_statement(self, stmt, variables):
        varType = stmt.type_obj
        varName = stmt.var_name
        initExpr = stmt.init_expr

        # 이미 process_variable_declaration에서 변수 객체 만들어져 있을 것이기 때문에
        # 초기화 식 없으면 그냥 리턴하면 됨
        if initExpr is None :
            return variables

        variableObj = None
        if varName in variables :
            variableObj = variables[varName]
        else :
            raise ValueError (f"There is no variable '{varName}' in variables dictionary")

        # 초기화 식이 있는데, array면 inline array expression 밖에 없을듯
        if isinstance(variableObj, ArrayVariable) :
            return variables
        elif isinstance(variableObj, StructVariable) : # 관련된거 있을 것 같긴 한데 일단 pass
            pass
        elif isinstance(variableObj, MappingVariable) : # mapping은 있을수가 없음
            raise ValueError (f"Mapping variable is not expected in variable declaration context")
        elif isinstance(variableObj, Variables) :
            if varType.typeCategory == "elementary" :
                variableObj.value = self.evaluate_expression(initExpr, variables, None, None)
                return variables
        else :
            raise ValueError (f"Unexpected type of variable object")

    def interpret_assignment_statement(self, stmt, variables):
        leftExpr = stmt.left
        operator = stmt.operator
        rightExpr = stmt.right

        rExpVal = self.evaluate_expression(rightExpr, variables, None, None)
        self.update_left_var(leftExpr, rExpVal, operator, variables, None, None)

        return variables

    def interpret_function_call_statement(self, stmt, variables):
        function_expr = stmt.function_call_expr
        return_value = self.evaluate_function_call_context(function_expr, variables, None, None)

        return variables

    def interpret_return_statement(self, stmt, variables):
        returnExpr = stmt.return_expr
        returnValue = self.evaluate_expression(returnExpr, variables, None, None)

        # 5. function_exit_node에 return 값을 저장
        exit_node = self.current_target_function_cfg.get_exit_node()
        exit_node.return_vals[self.current_start_line] = returnValue  # 반환 값을 exit_node의 return_val에 기록

        return variables

    def interpret_revert_statement(self, stmt, variables):
        return variables

    def compare_intervals(self, left_interval, right_interval, operator):
        """
        두 Interval 간의 비교를 수행하여 BooleanInterval을 반환합니다.
        """
        if left_interval.min_value is None or left_interval.max_value is None \
                or right_interval.min_value is None or right_interval.max_value is None:
            # Interval 중 하나라도 값이 없으면 결과를 확정할 수 없음
            return BoolInterval(False, True)

        # 비교 결과를 나타내는 변수
        is_true = False
        is_false = False

        if operator == '==':
            if left_interval.max_value < right_interval.min_value or left_interval.min_value > right_interval.max_value:
                is_false = True
            elif left_interval.min_value == left_interval.max_value == right_interval.min_value == right_interval.max_value:
                is_true = True
            else:
                is_true = is_false = True  # 불확실함
        elif operator == '!=':
            if left_interval.max_value < right_interval.min_value or left_interval.min_value > right_interval.max_value:
                is_true = True
            elif left_interval.min_value == left_interval.max_value == right_interval.min_value == right_interval.max_value:
                is_false = True
            else:
                is_true = is_false = True  # 불확실함
        elif operator == '<':
            if left_interval.max_value < right_interval.min_value:
                is_true = True
            elif left_interval.min_value >= right_interval.max_value:
                is_false = True
            else:
                is_true = is_false = True
        elif operator == '>':
            if left_interval.min_value > right_interval.max_value:
                is_true = True
            elif left_interval.max_value <= right_interval.min_value:
                is_false = True
            else:
                is_true = is_false = True
        elif operator == '<=':
            if left_interval.max_value <= right_interval.min_value:
                is_true = True
            elif left_interval.min_value > right_interval.max_value:
                is_false = True
            else:
                is_true = is_false = True
        elif operator == '>=':
            if left_interval.min_value >= right_interval.max_value:
                is_true = True
            elif left_interval.max_value < right_interval.min_value:
                is_false = True
            else:
                is_true = is_false = True
        else:
            raise ValueError(f"Unsupported comparison operator: {operator}")

        return BoolInterval(is_true, is_false)