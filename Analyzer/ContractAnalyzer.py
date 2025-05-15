# SolidityGuardian/Analyzers/ContractAnalyzer.py
from Utils.cfg import *
from Utils.util import *
from collections import deque
from solcx import (
    install_solc,
    set_solc_version,
    compile_source,
    get_installed_solc_versions
)
from solcx.exceptions import SolcError
import copy
from typing import Dict, cast, Tuple
from collections import defaultdict


class ContractAnalyzer:

    def __init__(self):
        self.sm = AddressSymbolicManager()

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

        self.analysis_per_line: dict[int, list[dict]] = defaultdict(list)

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

            # ───── B. analysis_per_line 이동 (추가) ─────
            for old_line_no in keys_to_shift:
                if old_line_no in self.analysis_per_line:
                    self.analysis_per_line[old_line_no + offset] = \
                        self.analysis_per_line.pop(old_line_no)

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

    def compile_check(self) -> None:
        wanted = '0.8.0'

        # ① 아직 안 깔려 있으면 다운로드
        if wanted not in get_installed_solc_versions():
            print(f"[info] installing solc {wanted} …")
            install_solc(wanted)  # 네트워크·권한 오류나면 여기서 예외 발생

        # ② 방금(또는 이전에) 받은 버전을 active 로 지정
        set_solc_version(wanted)

        # ③ 실제 컴파일
        try:
            compile_source(self.full_code)
            print("[ok] solidity compiled successfully")
        except SolcError as e:
            print("[err] Solidity compiler reported:\n", e)
        except Exception as e:
            print("[err] unexpected:", e)

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
                if context_type in ["function", "modifier"] :
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
            elif stripped_code.startswith("unchecked"):
                return "unchecked"
            elif stripped_code.startswith("return") :
                return "return"
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

    # ContractAnalyzer.py  (일부)

    def make_contract_cfg(self, contract_name: str):
        """
        contract-level CFG를 처음 만들 때 한 번 호출.
        address 계열 글로벌은 UnsignedIntegerInterval(160bit) 로,
        uint  계열은 [0,0] 256-bit Interval 로 초기화한다.
        """
        if contract_name in self.contract_cfgs:
            return

        cfg = ContractCFG(contract_name)

        # ────────── 1. local helpers ──────────
        def _u256(val: int = 0) -> UnsignedIntegerInterval:
            """[val,val] 256-bit uint Interval"""
            return UnsignedIntegerInterval(val, val, 256)

        def _addr_fixed(nid: int) -> UnsignedIntegerInterval:
            """symbolicAddress nid → Interval [nid,nid] (일관성 위해 매니저에 등록)"""
            self.sm.register_fixed_id(nid)
            return self.sm.get_interval(nid)

        def _sol_elem(name: str, bits: int | None = None) -> SolType:
            T = SolType()
            T.typeCategory = "elementary"
            T.elementaryTypeName = name
            if bits is not None:
                T.intTypeLength = bits
            return T

        # ────────── 2. 글로벌 변수 테이블 ──────────
        cfg.globals = {
            # --- block ---
            "block.basefee": GlobalVariable(
                identifier="block.basefee",
                value=_u256(),
                typeInfo=_sol_elem("uint")),
            "block.blobbasefee": GlobalVariable(
                identifier="block.blobbasefee",
                value=_u256(),
                typeInfo=_sol_elem("uint")),
            "block.chainid": GlobalVariable(
                identifier="block.chainid",
                value=_u256(),
                typeInfo=_sol_elem("uint")),
            "block.coinbase": GlobalVariable(
                identifier="block.coinbase",
                value=_addr_fixed(0),
                typeInfo=_sol_elem("address")),
            "block.difficulty": GlobalVariable(
                identifier="block.difficulty",
                value=_u256(),
                typeInfo=_sol_elem("uint")),
            "block.gaslimit": GlobalVariable(
                identifier="block.gaslimit",
                value=_u256(),
                typeInfo=_sol_elem("uint")),
            "block.number": GlobalVariable(
                identifier="block.number",
                value=_u256(),
                typeInfo=_sol_elem("uint")),
            "block.prevrandao": GlobalVariable(
                identifier="block.prevrandao",
                value=_u256(),
                typeInfo=_sol_elem("uint")),
            "block.timestamp": GlobalVariable(
                identifier="block.timestamp",
                value=_u256(),
                typeInfo=_sol_elem("uint")),

            # --- msg ---
            "msg.sender": GlobalVariable(
                identifier="msg.sender",
                value=_addr_fixed(101),
                typeInfo=_sol_elem("address")),
            "msg.value": GlobalVariable(
                identifier="msg.value",
                value=_u256(),
                typeInfo=_sol_elem("uint")),

            # --- tx ---
            "tx.gasprice": GlobalVariable(
                identifier="tx.gasprice",
                value=_u256(),
                typeInfo=_sol_elem("uint")),
            "tx.origin": GlobalVariable(
                identifier="tx.origin",
                value=_addr_fixed(100),
                typeInfo=_sol_elem("address")),
        }

        # ────────── 3. bookkeeping ──────────
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

        if not contract_cfg.state_variable_node:
            contract_cfg.initialize_state_variable_node()

        # 우변 표현식을 저장하기 위해 init_expr를 확인
        if init_expr is None: # 초기화가 없으면
            if isinstance(variable_obj, ArrayVariable) :
                if variable_obj.typeInfo.arrayBaseType.elementaryTypeName.startswith("int") :
                    variable_obj.initialize_elements(IntegerInterval.bottom())
                elif variable_obj.typeInfo.arrayBaseType.elementaryTypeName.startswith("uint") :
                    variable_obj.initialize_elements(UnsignedIntegerInterval.bottom())
                elif variable_obj.typeInfo.arrayBaseType.elementaryTypeName.startswith("bool") :
                    variable_obj.initialize_elements(BoolInterval.bottom())
                elif variable_obj.typeInfo.arrayBaseType.elementaryTypeName in ["address", "address payable", "string", "bytes", "Byte", "Fixed", "Ufixed"] :
                    variable_obj.initialize_not_abstracted_type(variable_obj.identifier)
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
            elif variable_obj.typeInfo.typeCategory == "elementary":
                et = variable_obj.typeInfo.elementaryTypeName

                # ── ① int / uint / bool 은 종전 로직 유지
                if et.startswith(("int", "uint", "bool")):
                    variable_obj.value = self.calculate_default_interval(et)

                # ── ② **address → fresh symbolic interval 로 변경**
                elif et == "address":
                    # 초기화식이 없으면 전체 주소 공간으로 보수적으로 설정
                    variable_obj.value = UnsignedIntegerInterval(0, 2 ** 160 - 1, 160)
                    # fresh-ID 는 **발급하지 않는다** → sm.bind_var 도 호출하지 않음

                # (string / bytes 등 - 추상화 안 할 타입은 심볼릭 문자열 그대로)
                else:
                    variable_obj.value = f"symbol_{variable_obj.identifier}"
        else : # 초기화 식이 있으면
            if isinstance(variable_obj, ArrayVariable) :
                inlineArrayValues = self.evaluate_expression(init_expr, contract_cfg.state_variable_node.variables, None, None)

                for value in inlineArrayValues :
                    variable_obj.elements.append(value)
            elif isinstance(variable_obj, StructVariable) : # 관련된 경우 없을듯
                pass
            elif isinstance(variable_obj, MappingVariable) : # 관련된 경우 없을 듯
                pass
            elif variable_obj.typeInfo.typeCategory == "elementary" :
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

    # ---------------------------------------------------------------------------
    # ② constant 변수 처리 (CFG·심볼 테이블 반영)
    # ---------------------------------------------------------------------------
    def process_constant_variable(self, variable_obj, init_expr):

        # 1. 컨트랙트 CFG 확보
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if contract_cfg is None:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. 반드시 초기화식이 있어야 함
        if init_expr is None:
            raise ValueError(f"Constant variable '{variable_obj.identifier}' must have an initializer.")

        if not contract_cfg.state_variable_node:
            contract_cfg.initialize_state_variable_node()

        #    평가 컨텍스트는 현재까지의 state-variable 노드 변수들
        state_vars = contract_cfg.state_variable_node.variables
        value = self.evaluate_expression(init_expr, state_vars, None, None)
        if value is None:
            raise ValueError(f"Unable to evaluate constant expression for '{variable_obj.identifier}'")

        variable_obj.value = value
        variable_obj.isConstant = True  # (안전용 중복 설정)

        # 3. ContractCFG 에 추가 (state 변수와 동일 API 사용)
        contract_cfg.add_state_variable(variable_obj, expr=init_expr)

        # 4. 이미 생성된 모든 FunctionCFG 에 read-only 변수로 연동
        for fn_cfg in contract_cfg.functions.values():
            fn_cfg.add_related_variable(variable_obj.identifier, variable_obj)

        # 5. 전역 map 업데이트
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 6. brace_count 갱신 → IDE/커서 매핑
        self.brace_count[self.current_start_line]["cfg_node"] = contract_cfg.state_variable_node

    def process_modifier_definition(self,
                                    modifier_name: str,
                                    parameters: dict[str, SolType] | None = None) -> None:
        """
        modifier 정의를 분석하여 FunctionCFG 로 등록
        parameters: { param_name : SolType, ... }  또는 None
        """
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if contract_cfg is None:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 1) 빈 CFG 생성
        modifier_cfg = FunctionCFG(function_type='modifier',
                                   function_name=modifier_name)

        # 2) 파라미터 처리 (없으면 {} 로 대체)
        parameters = parameters or {}
        for var_name, type_info in parameters.items():
            # 파라미터용 Variables 객체 한 개 생성
            var_obj = Variables(identifier=var_name, scope="local")
            var_obj.typeInfo = type_info

            # elementary 타입이면 보수적 default 값 부여
            if type_info.typeCategory == "elementary":
                et = type_info.elementaryTypeName
                if et.startswith(("int", "uint", "bool")):
                    var_obj.value = self.calculate_default_interval(et)
                elif et == "address":
                    # 파라미터 address → 전체 범위
                    var_obj.value = UnsignedIntegerInterval(0, 2 ** 160 - 1, 160)
                else:  # bytes / string 등
                    var_obj.value = f"symbol_{var_name}"

            modifier_cfg.add_related_variable(var_obj)

        if contract_cfg.state_variable_node:
            for var in contract_cfg.state_variable_node.variables.values():
                modifier_cfg.add_related_variable(var)

        # 3) CFG 저장
        contract_cfg.functions[modifier_name] = modifier_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg
        self.brace_count[self.current_start_line]['cfg_node'] = modifier_cfg.get_entry_node()

    # ContractAnalyzer.py  ----------------------------------------------

    def process_modifier_invocation(self,
                                    fn_cfg: FunctionCFG,
                                    modifier_name: str) -> None:
        """
        fn_cfg  ← 방금 만들고 있는 함수-CFG
        modifier_name  ← 'onlyOwner' 처럼 한 개

        ① 컨트랙트에 등록돼 있는 modifier-CFG 가져오기
        ② modifier-CFG 를 *얕은 복사* 하여 fn_cfg.graph 에 붙인다.
        ③ placeholder 노드(들)를 fn-entry/exit 로 스플라이스
        """

        contract_cfg = self.contract_cfgs[self.current_target_contract]

        # ── ① modifier 존재 확인 ──────────────────────────────────
        if modifier_name not in contract_cfg.modifiers:
            raise ValueError(f"Modifier '{modifier_name}' is not defined.")

        mod_cfg: FunctionCFG = contract_cfg.modifiers[modifier_name]

        # ── ② modifier-CFG 의 노드·엣지를 함수-CFG 로 복사 ───────
        g_fn = fn_cfg.graph
        g_mod = mod_cfg.graph

        # 노드 이름이 겹칠 위험이 있으니 prefix 붙여서 복사
        node_map: dict[CFGNode, CFGNode] = {}
        for n in g_mod.nodes:
            new_n = CFGNode(f"{modifier_name}::{n.name}")
            # 변수 환경은 빈 딕셔너리로 시작
            new_n.variables = self.copy_variables(getattr(n, "variables", {}))
            node_map[n] = new_n
            g_fn.add_node(new_n)

        for u, v in g_mod.edges:
            g_fn.add_edge(node_map[u], node_map[v])

        # ── ③ placeholder 스플라이스 ─────────────────────────────
        entry = fn_cfg.get_entry_node()
        exit_ = fn_cfg.get_exit_node()

        for mod_node_orig in g_mod.nodes:
            if mod_node_orig.name.startswith("MOD_PLACEHOLDER"):
                ph = node_map[mod_node_orig]  # 복사된 placeholder

                preds = list(g_fn.predecessors(ph))
                succs = list(g_fn.successors(ph))

                # placeholder 제거
                g_fn.remove_node(ph)

                # preds  →  entry
                for p in preds:
                    g_fn.add_edge(p, entry)

                # exit  →  succs
                for s in succs:
                    g_fn.add_edge(exit_, s)

        # (선택) ④ modifier 의 global/상태 변수 사용 정보를
        #        fn_cfg.related_variables 와 join 하고 싶다면 여기서 처리

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
                constructor_cfg.add_related_variable(var_info)

        self.brace_count[self.current_start_line]['cfg_node'] = constructor_cfg.get_entry_node()

    # ContractAnalyzer.py  ─ process_function_definition  (address-symb ✚ 최신 Array/Struct 초기화 반영)

    def process_function_definition(
            self,
            function_name: str,
            parameters: list[tuple[SolType, str]],
            modifiers: list[str],
            returns: list[Variables] | None,
    ):
        # ───────────────────────────────────────────────────────────────
        # 1. 컨트랙트 CFG
        # ----------------------------------------------------------------
        contract_cfg = self.contract_cfgs[self.current_target_contract]

        if contract_cfg is None:
            raise ValueError(f"Contract CFG for {self.current_target_contract} not found.")

        # ───────────────────────────────────────────────────────────────
        # 2. 함수 CFG 객체
        # ----------------------------------------------------------------
        fcfg = FunctionCFG(function_type="function", function_name=function_name)

        # ───────────────────────────────────────────────────────────────
        # 3. 파라미터 → related_variables
        # ----------------------------------------------------------------
        for p_type, p_name in parameters:
            if p_name:  # 이름이 있는 것만 변수화
                var = self._make_param_variable(p_type, p_name, scope="local")
                fcfg.add_related_variable(var)

        # ───────────────────────────────────────────────────────────────
        # 4. Modifier invocation → CFG 병합
        # ----------------------------------------------------------------
        for m_name in modifiers:
            self.process_modifier_invocation(fcfg, m_name)

        # ───────────────────────────────────────────────────────────────
        # 5. Return 변수 처리
        # ----------------------------------------------------------------
        for r_type, r_name in returns:
            if r_name:
                rv = self._make_param_variable(r_type, r_name, scope="local")
                fcfg.add_related_variable(rv)
                fcfg.return_vars.append(rv)
            else:
                fcfg.return_types.append(r_type)

        # ───────────────────────────────────────────────────────────────
        # 6. 상태 변수 → related_variables 에 복사
        # ----------------------------------------------------------------
        if contract_cfg.state_variable_node:
            for var in contract_cfg.state_variable_node.variables.values():
                fcfg.add_related_variable(var)

        # ───────────────────────────────────────────────────────────────
        # 7. 결과를 ContractCFG 에 반영
        # ----------------------------------------------------------------
        contract_cfg.functions[function_name] = fcfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # ───────────────────────────────────────────────────────────────
        # 8. brace_count 에 함수 entry 노드 기록
        # ----------------------------------------------------------------
        self.brace_count[self.current_start_line]["cfg_node"] = fcfg.get_entry_node()

    # ContractAnalyzer.py  ─ process_variable_declaration  (address-symbolic & 최신 Array/Struct 초기화 반영)

    def process_variable_declaration(
            self,
            type_obj: SolType,
            var_name: str,
            init_expr: Expression | None = None,
    ):
        # ───────────────────────────────────────────────────────────────
        # 1. CFG 컨텍스트
        # ----------------------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("variableDeclaration: active FunctionCFG not found")

        cur_blk = self.get_current_block()

        # ───────────────────────────────────────────────────────────────
        # 2. 변수 객체 생성
        # ----------------------------------------------------------------
        v: Variables | ArrayVariable | StructVariable | MappingVariable | EnumVariable

        # 2-A  배열
        if type_obj.typeCategory == "array":
            v = ArrayVariable(
                identifier=var_name,
                base_type=type_obj.arrayBaseType,
                array_length=type_obj.arrayLength,
                is_dynamic=type_obj.isDynamicArray,
                scope="local",
            )

        # 2-B  구조체
        elif type_obj.typeCategory == "struct":
            v = StructVariable(
                identifier=var_name,
                struct_type=type_obj.structTypeName,
                scope="local",
            )

        # 2-C  enum
        elif type_obj.typeCategory == "enum":
            v = EnumVariable(identifier=var_name, enum_type=type_obj.enumTypeName, scope="local")

        # 2-D  매핑
        elif type_obj.typeCategory == "mapping":
            v = MappingVariable(
                identifier=var_name,
                key_type=type_obj.mappingKeyType,
                value_type=type_obj.mappingValueType,
                scope="local",
            )

        # 2-E  elementary
        else:
            v = Variables(identifier=var_name, scope="local")
            v.typeInfo = type_obj

        # ───────────────────────────────────────────────────────────────
        # 3. 기본값 / 초기화식 해석
        # ----------------------------------------------------------------
        if init_expr is None:
            # ── 배열 기본
            if isinstance(v, ArrayVariable):
                bt = v.typeInfo.arrayBaseType
                if isinstance(bt, SolType):
                    et = bt.elementaryTypeName
                    if et and et.startswith("int"):
                        bits = bt.intTypeLength or 256
                        v.initialize_elements(IntegerInterval.bottom(bits))
                    elif et and et.startswith("uint"):
                        bits = bt.intTypeLength or 256
                        v.initialize_elements(UnsignedIntegerInterval.bottom(bits))
                    elif et == "bool":
                        v.initialize_elements(BoolInterval.bottom())
                    else:
                        v.initialize_not_abstracted_type(sm=self.sm)

            # ── 구조체 기본
            elif isinstance(v, StructVariable):
                if v.typeInfo.structTypeName not in ccf.structDefs:
                    raise ValueError(f"Undefined struct {v.typeInfo.structTypeName}")
                v.initialize_struct(ccf.structDefs[v.typeInfo.structTypeName], sm=self.sm)

            # ── enum 기본 (첫 멤버)
            elif isinstance(v, EnumVariable):
                enum_def = ccf.enumDefs.get(v.typeInfo.enumTypeName)
                if enum_def:
                    v.valueIndex = 0
                    v.value = enum_def.members[0]

            # ── elementary 기본
            elif isinstance(v, Variables):
                et = v.typeInfo.elementaryTypeName
                if et.startswith("int"):
                    v.value = IntegerInterval.bottom(v.typeInfo.intTypeLength or 256)
                elif et.startswith("uint"):
                    v.value = UnsignedIntegerInterval.bottom(v.typeInfo.intTypeLength or 256)
                elif et == "bool":
                    v.value = BoolInterval.bottom()
                elif et == "address":
                    iv = self.sm.alloc_fresh_interval()
                    v.value = iv
                    self.sm.bind_var(var_name, iv.min_value)
                else:  # bytes/string
                    v.value = f"symbol_{var_name}"

        # ───────────────────────────────────────────────────────────────
        # 3-b. 초기화식이 존재하는 경우
        # ----------------------------------------------------------------
        else:
            if isinstance(v, ArrayVariable):
                arr_vals = self.evaluate_expression(init_expr, cur_blk.variables, None, None)
                for e in arr_vals:
                    v.elements.append(e)

            elif isinstance(v, Variables):  # elementary / address / bool …
                v.value = self.evaluate_expression(init_expr, cur_blk.variables, None, None)

            # enum-init, mapping-init 등은 필요시 추가

        # ───────────────────────────────────────────────────────────────
        # 4. CFG 노드 업데이트
        # ----------------------------------------------------------------
        cur_blk.variables[v.identifier] = v
        cur_blk.add_variable_declaration_statement(type_obj, var_name, init_expr)
        self.current_target_function_cfg.add_related_variable(v)
        self.current_target_function_cfg.update_block(cur_blk)

        lhs_expr = Expression(identifier=var_name, context="IdentifierExpContext")
        self._record_analysis(
            line_no=self.current_start_line,
            stmt_type="vardecl",
            expr=lhs_expr,  # ← 좌변 Expression
            var_obj=v  # ← 방금 만든 Variables / ArrayVariable …
        )

        # ───────────────────────────────────────────────────────────────
        # 5. 저장 및 brace_count
        # ----------------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf
        self.brace_count[self.current_start_line]["cfg_node"] = cur_blk

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

        if self.current_target_function_cfg.function_type == "constructor" :
            self._overwrite_state_vars_from_block(contract_cfg, current_block.variables)

        # 2) 방금 변경된 변수 객체 다시 가져오기 (new_value=None ⇒ 탐색만)
        target_var = self._resolve_and_update_expr(
            expr.left,
            self.current_target_function_cfg,
            None
        )

        # 3) analysis 기록
        self._record_analysis(
            line_no=self.current_start_line,
            stmt_type="assign",
            expr=expr.left,
            var_obj=target_var
        )

        # 9. current_block을 function CFG에 반영
        self.current_target_function_cfg.update_block(current_block)  # 변경된 블록을 반영

        # 10. function_cfg 결과를 contract_cfg에 반영
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg

        # 11. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 12. brace_count에 CFG 노드 정보 업데이트 (함수의 시작 라인 정보 사용)
        self.brace_count[self.current_start_line]['cfg_node'] = current_block

    def _handle_unary_incdec(
            self,
            expr: Expression,  # ++x   또는   x--   의  피연산식
            op_sign: str,  # "+="  또는  "-="
            stmt_kind: str  # "unary_prefix" / "unary_suffix"
    ):
        ccf = self.contract_cfgs[self.current_target_contract]
        fcfg = ccf.get_function_cfg(self.current_target_function)
        if fcfg is None:
            raise ValueError("active FunctionCFG not found")

        cur_blk = self.get_current_block()

        # ── 1) LHS 갱신  (++/--  ==  ±= 1 )
        one_lit = Expression(literal="1", context="LiteralExpContext")
        self.update_left_var(expr, 1, op_sign, cur_blk.variables, None, None)
        cur_blk.add_assign_statement(expr, op_sign, one_lit)

        # ── 2) constructor 였으면 state-variables overwrite
        if fcfg.function_type == "constructor":
            self._overwrite_state_vars_from_block(ccf, cur_blk.variables)

        # ── 3) 갱신된 변수 객체 얻어서 analysis 기록
        target_var = self._resolve_and_update_expr(expr, fcfg, None)
        self._record_analysis(
            line_no=self.current_start_line,
            stmt_type=stmt_kind,
            expr=expr,
            var_obj=target_var
        )

        # ── 4) CFG 저장
        fcfg.update_block(cur_blk)
        ccf.functions[self.current_target_function] = fcfg
        self.contract_cfgs[self.current_target_contract] = ccf
        self.brace_count[self.current_start_line]["cfg_node"] = cur_blk

    # ───────────────────────────────────────────────────────────
    def process_unary_prefix_operation(self, expr: Expression):
        if expr.operator == "++":
            self._handle_unary_incdec(expr.expression, "+=", "unary_prefix")
        elif expr.operator == "--":
            self._handle_unary_incdec(expr.expression, "-=", "unary_prefix")
        else:
            raise ValueError(f"Unsupported prefix operator {expr.operator}")

    def process_unary_suffix_operation(self, expr: Expression):
        if expr.operator == "++":
            self._handle_unary_incdec(expr.expression, "+=", "unary_suffix")
        elif expr.operator == "--":
            self._handle_unary_incdec(expr.expression, "-=", "unary_suffix")
        else:
            raise ValueError(f"Unsupported suffix operator {expr.operator}")

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

        pre_env = self._clone_env(current_block.variables)

        # 4. brace_count 업데이트 - 존재하지 않으면 초기화
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = condition_block

        # 5. True 분기 블록 생성
        true_block = CFGNode(name=f"if_true_{self.current_start_line}")

        # 7. True 분기에서 변수 상태 복사 및 업데이트
        true_env  = self._clone_env(condition_block.variables)

        self.update_variables_with_condition(true_env, condition_expr, is_true_branch=True)

        false_block = CFGNode(name=f"if_false_{self.current_start_line}")
        false_env = self._clone_env(condition_block.variables)
        self.update_variables_with_condition(false_env, condition_expr, is_true_branch=False)

        # analysis 기록
        self._add_branch_analysis(
            cond_line=self.current_start_line,
            cond_expr=condition_expr,
            base_env=pre_env,
            true_env=true_env,
            false_env=false_env
        )

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

        base_env = self._clone_env(temp_variables)

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
        true_env   = self._clone_env(temp_variables)
        self.update_variables_with_condition(true_env, condition_expr, is_true_branch=True)

        # 5. False 분기 블록 생성
        false_block = CFGNode(name=f"else_if_false_{self.current_start_line}")

        false_env = self._clone_env(temp_variables)
        self.update_variables_with_condition(false_env, condition_expr,
                                             is_true_branch=False)

        self._add_branch_analysis(
            cond_line=self.current_start_line,
            cond_expr=condition_expr,
            base_env=base_env,
            true_env=true_env,
            false_env=false_env
        )

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
        # ───────────────────────── 1. CFG 컨텍스트 ─────────────────────────
        ccf = self.contract_cfgs[self.current_target_contract]
        if ccf is None:
            raise ValueError(f"Contract CFG for {self.current_target_contract} not found.")
        fcfg = ccf.get_function_cfg(self.current_target_function)
        if fcfg is None:
            raise ValueError("No active FunctionCFG when processing 'else'.")

        # ───────────────────────── 2. 직전 조건-노드 탐색 ───────────────────
        cond_node: CFGNode = self.find_corresponding_condition_node()
        if cond_node is None:
            raise ValueError("No preceding 'if/else-if' for this 'else'.")

        g = fcfg.graph

        # ── 2-A) 기존 **False** succ edge 제거
        for succ in list(g.successors(cond_node)):
            if g[cond_node][succ].get("condition") is False:
                g.remove_edge(cond_node, succ)

        # ── 2-B) “True succ” 들 저장 (join 지점 후보)
        true_succs = [
            s for s in g.successors(cond_node)
            if g[cond_node][s].get("condition") is True
        ]

        # ───────────────────────── 3. else 블록 생성 ──────────────────────
        else_blk = CFGNode(f"else_block_{self.current_start_line}")

        # (1) 변수환경 = cond_node 변수 deep-copy
        else_blk.variables = self.copy_variables(cond_node.variables)
        # (2) cond 부정 적용
        self.update_variables_with_condition(
            else_blk.variables,
            cond_node.condition_expr,
            is_true_branch=False
        )

        # ───────────────────────── 4. 그래프 연결 ─────────────────────────
        g.add_node(else_blk)
        g.add_edge(cond_node, else_blk, condition=False)  # False 브랜치

        for s in true_succs:  # join 유지
            g.add_edge(else_blk, s)

        # ───────────────────────── 5. brace_count 갱신 ────────────────────
        self.brace_count.setdefault(self.current_start_line, {})
        self.brace_count[self.current_start_line]["cfg_node"] = else_blk

        # ───────────────────────── 6. 분석 결과 기록 ──────────────────────
        #   “else { … }” 첫 줄에서   ▶  분기 전 전체 env 스냅-숏 저장
        self._record_analysis(
            line_no=self.current_start_line,
            stmt_type="else_enter",
            env=else_blk.variables  # flatten 은 _record_analysis 내부에서 수행
        )

        # ───────────────────────── 7. CFG 저장 ────────────────────────────
        ccf.functions[self.current_target_function] = fcfg
        self.contract_cfgs[self.current_target_contract] = ccf

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
        fixpoint_evaluation_node = self.find_fixpoint_evaluation_node(current_block)
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
        condition_node = self.find_loop_condition_node(current_block)
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

            # ────────── ✨ 분석 결과 기록 ✨ ──────────
            self._record_analysis(  # ← 추가 ①
                line_no=self.current_start_line,
                stmt_type="return",
                expr=return_expr,  # Expression 을 key 로 직렬화
                var_obj=Variables(  # ← dummy-wrap 해서 value 전달
                    identifier="__ret__", value=return_value, scope="tmp")
            )  # ← 추가 ②

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

        # ──────────────────────────────
        # ✨  A) ‘require’ 직전 환경 스냅샷 저장
        # ──────────────────────────────
        self._record_analysis(
            line_no=self.current_start_line,
            stmt_type="require-pre",
            env=current_block.variables  # 분기 전 전체 환경
        )

        # ── 3  successors 확보

        # ── 4  조건-노드 생성
        req_cond = CFGNode(
            name=f"require_condition_{self.current_start_line}",
            condition_node=True,
            condition_node_type="require"
        )
        req_cond.condition_expr = condition_expr

        # ── 5 True-블록
        true_blk = CFGNode(name=f"require_true_{self.current_start_line + 1}")
        true_blk.variables = self.copy_variables(current_block.variables)
        self.update_variables_with_condition(true_blk.variables,
                                             condition_expr,
                                             is_true_branch=True)

        # ──────────────────────────────
        # ✨  B) True-블록 시작 시 분기 후 환경 스냅샷
        # ──────────────────────────────
        self._record_analysis(
            line_no=self.current_start_line + 0.1,  # ‘가상’ 라인 – IDE 에선 동일 라인에 묶여보임
            stmt_type="require-true",
            env=true_blk.variables
        )

        # ── 6 CFG 재배선 (successor edge 이동)
        for succ in successors:
            self.current_target_function_cfg.graph.remove_edge(current_block, succ)
            self.current_target_function_cfg.graph.add_edge(req_cond, succ)

        # ── 7 current_block → require 노드
        g = self.current_target_function_cfg.graph
        g.add_node(req_cond)
        g.add_edge(current_block, req_cond)

        # ── 8 False-분기 : exit 노드로
        exit_node = self.current_target_function_cfg.get_exit_node()
        g.add_edge(req_cond, exit_node, condition=False)

        # ── 9 True-분기 연결
        g.add_node(true_blk)
        g.add_edge(req_cond, true_blk, condition=True)

        # ── 10 brace_count
        self.brace_count.setdefault(self.current_start_line, {})["cfg_node"] = req_cond

        # ── 11 CFG / contract 갱신
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

        # ➊ ====== 분석 결과: assert 직전 환경 저장 =============================
        self._record_analysis(
            line_no=self.current_start_line,
            stmt_type="assert-pre",
            env=current_block.variables  # 전체 환경 스냅샷
        )
        # ====================================================================

        # ── 3 successors, 4 조건노드 생성
        assert_cond = CFGNode(
            name=f"assert_condition_{self.current_start_line}",
            condition_node=True,
            condition_node_type="assert"
        )
        assert_cond.condition_expr = condition_expr

        # ── 5 True-블록
        true_blk = CFGNode(name=f"assert_true_{self.current_start_line + 1}")
        true_blk.variables = self.copy_variables(current_block.variables)
        self.update_variables_with_condition(true_blk.variables,
                                             condition_expr,
                                             is_true_branch=True)

        # ➋ ====== true 분기 스냅샷 저장 =====================================
        self._record_analysis(
            line_no=self.current_start_line + 0.1,  # 같은 코드 라인에 묶어서 표시
            stmt_type="assert-true",
            env=true_blk.variables
        )
        # ====================================================================

        # ── 6 successors edge 이동
        g = self.current_target_function_cfg.graph
        for succ in list(g.successors(current_block)):
            g.remove_edge(current_block, succ)
            g.add_edge(assert_cond, succ)

        # ── 7 current_block → 조건노드
        g.add_node(assert_cond)
        g.add_edge(current_block, assert_cond)

        # ── 8 실패( false ) → EXIT
        exit_node = self.current_target_function_cfg.get_exit_node()
        g.add_edge(assert_cond, exit_node, condition=False)

        # ── 9 true-분기 연결
        g.add_node(true_blk)
        g.add_edge(assert_cond, true_blk, condition=True)

        # ➌ ====== brace_count 등록 (IDE cursor tracking용) ====================
        self.brace_count.setdefault(self.current_start_line, {})["cfg_node"] = assert_cond
        # ====================================================================

        # ── 10 CFG / contract 갱신
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg
        self.current_target_function_cfg = None

    # ContractAnalyzer.py  (추가/수정)

    def process_identifier_expression(self, ident_expr: Expression):
        """
        · ident_expr.identifier 가 '_' 이고,
        · 현재 CFG 가 modifier 이면 → placeholder 처리
        · 아니면 평범한 identifier 로서 evaluate
        """
        ident_str = ident_expr.identifier
        cfg = self.contract_cfgs[self.current_target_contract]
        fcfg = cfg.get_function_cfg(self.current_target_function)

        # ───── modifier placeholder “_”인지 검사 ─────
        if ident_str == "_" and fcfg and fcfg.function_type == "modifier":
            self._create_modifier_placeholder_node(fcfg)
            return  # 값-업데이트 없음

    def process_unchecked_indicator(self):
        # 1. 현재 컨트랙트와 함수의 CFG 가져오기
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("No active function to process the require statement.")

        # 2. 현재 블록 가져오기
        current_block = self.get_current_block()
        current_block.add_unchecked_block()

        self.brace_count[self.current_start_line] = {"open": 1, "close": 0, "cfg_node": current_block}

        # ====================================================================

        # ── 10 CFG / contract 갱신
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg
        self.current_target_function_cfg = None



    # ContractAnalyzer.py ──────────────────────────────────────────────

    # ---------------------------------------------------------- #
    #  constructor 내부 상태-변수 → State_Variable 노드 동기화
    # ---------------------------------------------------------- #
    # ContractAnalyzer.py ────────────────────────────────────────────
    # ContractAnalyzer.py  내부 ― 클래스 메서드로 추가
    # --------------------------------------------------
    def _make_param_variable(
            self,
            sol_type: SolType,
            ident: str,
            *,
            scope: str = "local"
    ) -> Variables | ArrayVariable | StructVariable | EnumVariable:
        """
        <type, name> 쌍을 받아 Variables / ArrayVariable / StructVariable … 객체를
        하나 만들어 초기값(추상간격)까지 넣어 반환한다.

        ▸ scope      : "local"  (파라미터 · 리턴) / "state" 등
        ▸ self.sm    : AddressSymbolicManager  (주소 심볼릭 ID 발급용)
        """
        contract_cfg = self.contract_cfgs[self.current_target_contract]

        # ──────────────────────────── ① array ────────────────────────────
        if sol_type.typeCategory == "array":
            arr = ArrayVariable(
                identifier=ident,
                base_type=sol_type.arrayBaseType,
                array_length=sol_type.arrayLength,
                is_dynamic=sol_type.isDynamicArray,
                scope=scope,
            )

            base_t = sol_type.arrayBaseType
            if isinstance(base_t, SolType):  # 1-D 배열
                et = base_t.elementaryTypeName
                if et and et.startswith("int"):
                    arr.initialize_elements(IntegerInterval.bottom(base_t.intTypeLength or 256))
                elif et and et.startswith("uint"):
                    arr.initialize_elements(UnsignedIntegerInterval.bottom(base_t.intTypeLength or 256))
                elif et == "bool":
                    arr.initialize_elements(BoolInterval.bottom())
                else:  # address / bytes / string / struct 등
                    arr.initialize_not_abstracted_type(sm=self.sm)
            else:  # 다차원
                arr.initialize_not_abstracted_type(sm=self.sm)
            return arr

        # ──────────────────────────── ② struct ───────────────────────────
        if sol_type.typeCategory == "struct":
            sname = sol_type.structTypeName
            if sname not in contract_cfg.structDefs:
                raise ValueError(f"Undefined struct '{sname}' used as parameter/return.")
            sv = StructVariable(identifier=ident, struct_type=sname, scope=scope)
            sv.initialize_struct(contract_cfg.structDefs[sname], sm=self.sm)
            return sv

        # ──────────────────────────── ③ enum ────────────────────────────
        if sol_type.typeCategory == "enum":
            ev = EnumVariable(identifier=ident,
                              enum_type=sol_type.enumTypeName,
                              scope=scope)
            ev.valueIndex = 0  # 기본값 : 첫 멤버
            return ev

        # ──────────────────────────── ④ elementary ───────────────────────
        if sol_type.typeCategory == "elementary":
            v = Variables(identifier=ident, scope=scope)
            v.typeInfo = sol_type
            et = sol_type.elementaryTypeName

            if et.startswith("int"):
                v.value = IntegerInterval.bottom(sol_type.intTypeLength or 256)
            elif et.startswith("uint"):
                v.value = UnsignedIntegerInterval.bottom(sol_type.intTypeLength or 256)
            elif et == "bool":
                v.value = BoolInterval.bottom()
            elif et == "address":
                iv = self.sm.alloc_fresh_interval()
                v.value = iv
                self.sm.bind_var(ident, iv.min_value)
            else:  # bytes / string …
                v.value = f"symbol_{ident}"
            return v

        # ──────────────────────────── ⑤ mapping (rare) ───────────────────
        if sol_type.typeCategory == "mapping":
            return MappingVariable(identifier=ident,
                                   key_type=sol_type.mappingKeyType,
                                   value_type=sol_type.mappingValueType,
                                   scope=scope)

        raise ValueError(f"Unsupported typeCategory '{sol_type.typeCategory}'")

    def _clone_env(self, src: dict[str, Variables]) -> dict[str, Variables]:
        """deep-copy wrapper"""
        return self.copy_variables(src)

    def _add_branch_analysis(
            self,
            cond_line: int,
            cond_expr: Expression,
            base_env: dict[str, Variables],
            true_env: dict[str, Variables],
            false_env: dict[str, Variables]
    ):
        """
        cond_line   : if/else if/else 키워드가 시작된 라인
        cond_expr   : 조건 Expression (else 는 None)
        base_env    : 분기 직전 전체 env
        true_env    : 조건 만족 env   (else 의 경우 None)
        false_env   : 조건 불만족 env (else 의 경우 else-블록 env)
        """
        # ① 분기 전 스냅숏
        self._record_analysis(cond_line, "branch_pre", env=base_env)

        # ② true-env
        if true_env is not None:
            tl = cond_line + 0.1  # 소수점으로 “가상 줄 번호” 구분
            self._record_analysis(tl, "branch_true", env=true_env)

        # ③ false-env (else 또는 if-false)
        if false_env is not None:
            fl = cond_line + 0.2
            self._record_analysis(fl, "branch_false", env=false_env)

    # ContractAnalyzer.py ─────────────────────────────────────────
    def _overwrite_state_vars_from_block(
            self,
            contract_cfg: ContractCFG,
            block_vars: dict[str, Variables],
    ) -> None:
        """
        constructor 내부에서 수정된 state-변수를
        ContractCFG.state_variable_node 에 *그대로 덮어쓴다*.
        """
        state_vars = contract_cfg.state_variable_node.variables

        # ③ scope=='state' 인 항목을 그대로 복사해 덮어쓰기
        for name, var in block_vars.items():
            if getattr(var, "scope", None) != "state":
                continue
            state_vars[name] = self.copy_variables({name: var})[name]

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


    # --------------------------------------------------
    def _create_modifier_placeholder_node(self, fcfg: FunctionCFG):
        """
        modifier 안의 '_' 를 만났을 때 임시 노드를 만든다.
        ─ ① cur_blk ← 현재 CFGBlock
        ─ ② PLACEHOLDER 노드를 cur_blk 다음에 삽입
        ─ ③ cur_blk 의 기존 successor 들을 PLACEHOLDER 뒤로 밀기
        """
        cur_blk = self.get_current_block()

        idx = len(getattr(fcfg, "placeholders", []))
        ph = CFGNode(f"MOD_PLACEHOLDER_{idx}")
        fcfg.placeholders = getattr(fcfg, "placeholders", []) + [ph]

        g = fcfg.graph
        succs = list(g.successors(cur_blk))

        g.add_node(ph)
        g.add_edge(cur_blk, ph)
        for s in succs:
            g.add_edge(ph, s)
            g.remove_edge(cur_blk, s)

    # ContractAnalyzer 내부 메서드들
    # ─────────────────────────────────────────────────────────────
    def process_global_var_for_debug(self, gv_obj: GlobalVariable):
        """
        @GlobalVar …   처리
          • cfg.globals  갱신
          • FunctionCFG.related_variables  갱신
          •(주소형이면) AddressSymbolicManager 에 변수<->ID 바인딩
          • 영향을 받는 함수만 재해석
        """
        cfg = self.contract_cfgs[self.current_target_contract]

        # 1) 사전 엔트리 보장
        if gv_obj.identifier not in cfg.globals:
            gv_obj.default_value = gv_obj.value  # 최초 등록
            cfg.globals[gv_obj.identifier] = gv_obj
        g = cfg.globals[gv_obj.identifier]

        # 2) override 반영
        g.debug_override = gv_obj.value
        g.value = gv_obj.value  # 실시간 해석용

        # ↳ 주소형이면 AddressSymbolicManager 에 기록
        if g.typeInfo.elementaryTypeName == "address" and isinstance(g.value, UnsignedIntegerInterval):
            iv = g.value
            if iv.min_value == iv.max_value:  # [N,N] 형식 ⇒ 고정 ID
                nid = iv.min_value
                self.sm.register_fixed_id(nid, iv)
                self.sm.bind_var(g.identifier, nid)

        # 3) 모든 FunctionCFG 의 related_variables 동기화
        for fc in cfg.functions.values():
            if gv_obj.identifier in fc.related_variables:
                fc.related_variables[gv_obj.identifier].value = gv_obj.value

        # 4) 영향을 받는 함수만 재해석
        for func_name in g.usage_sites:
            if func_name in cfg.functions:
                self.interpret_function_cfg(cfg.functions[func_name])

    # ─────────────────────────────────────────────────────────────
    def process_state_var_for_debug(self, lhs_expr: Expression, value):
        """
        @StateVar …   주석 처리
        lhs_expr : Expression (identifier / .member / [index] …)
        value    : Interval | BoolInterval | UnsignedIntegerInterval(160-bit) | str
        """
        cfg = self.contract_cfgs[self.current_target_contract]
        fcfg = cfg.get_function_cfg(self.current_target_function)
        if fcfg is None:
            raise ValueError("@StateVar debug must appear inside a function body.")

        # 1) 변수 객체 위치 탐색 + 값 대입
        var_obj = self._resolve_and_update_expr(lhs_expr, fcfg, value)
        if var_obj is None:
            raise ValueError("LHS cannot be resolved to a state variable.")

        # 2) 주소형이면 심볼릭-ID 바인딩
        if (getattr(var_obj.typeInfo, "elementaryTypeName", None) == "address" and
                isinstance(var_obj.value, UnsignedIntegerInterval)):
            iv = var_obj.value
            if iv.min_value == iv.max_value:
                nid = iv.min_value
                self.sm.register_fixed_id(nid, iv)
                self.sm.bind_var(var_obj.identifier, nid)

        # 3) 해당 함수만 다시 해석
        self.interpret_function_cfg(fcfg)

    # ─────────────────────────────────────────────────────────────
    def process_local_var_for_debug(self, lhs_expr: Expression, value):
        """
        @LocalVar …   주석 처리 (함수 내부 로컬)
        """
        cfg = self.contract_cfgs[self.current_target_contract]
        fcfg = cfg.get_function_cfg(self.current_target_function)
        if fcfg is None:
            raise ValueError("@LocalVar debug must appear inside a function body.")

        var_obj = self._resolve_and_update_expr(lhs_expr, fcfg, value)
        if var_obj is None:
            raise ValueError("LHS cannot be resolved to a local variable.")

        # 주소형 → 심볼릭-ID 바인딩
        if (getattr(var_obj.typeInfo, "elementaryTypeName", None) == "address" and
                isinstance(var_obj.value, UnsignedIntegerInterval)):
            iv = var_obj.value
            if iv.min_value == iv.max_value:
                nid = iv.min_value
                self.sm.register_fixed_id(nid, iv)
                self.sm.bind_var(var_obj.identifier, nid)

        # 함수 재해석
        self.interpret_function_cfg(fcfg)

    # ---------------- util helpers ---------------- #
    # ---------------------------------------------------------------------------
    # Interval / value helpers  (ContractAnalyzer 내부 메서드들)
    # ---------------------------------------------------------------------------

    # ───────── static/utility ──────────────────────────────────────────────
    @staticmethod
    def _is_interval(x) -> bool:
        """Integer / UnsignedInteger 계열인지 판단"""
        return isinstance(x, (IntegerInterval, UnsignedIntegerInterval))

    @staticmethod
    def _extract_index_val(expr_idx: Expression):
        """
        index Expression → 정수 literal 이면 int, 그 외엔 Expression 그대로
        (symbolic index 처리를 위해)
        """
        if expr_idx.context == "LiteralExpContext":
            return int(expr_idx.literal, 0)
        return expr_idx  # symbolic 그대로

    # ContractAnalyzer 내부 (임의의 util 섹션)
    def _create_new_array_element(
            self,
            arr_var: ArrayVariable,
            index: int
    ) -> Variables | ArrayVariable:
        """
        동적/확장 배열에 새 element 를 생성해 돌려준다.
        - base type 이 elementary → Variables(Interval or symbol)
        - base type 이 array / struct → 각각 ArrayVariable / StructVariable 생성
        """

        eid = f"{arr_var.identifier}[{index}]"
        baseT: SolType | str = arr_var.typeInfo.arrayBaseType  # 편의상

        # ─ elementary ───────────────────────────────────────────
        if isinstance(baseT, SolType) and baseT.typeCategory == "elementary":
            et = baseT.elementaryTypeName

            if et.startswith("uint"):
                bits = baseT.intTypeLength or 256
                val = UnsignedIntegerInterval.bottom(bits)

            elif et.startswith("int"):
                bits = baseT.intTypeLength or 256
                val = IntegerInterval.bottom(bits)

            elif et == "bool":
                val = BoolInterval.bottom()

            elif et == "address":
                iv = self.sm.alloc_fresh_interval()
                self.sm.bind_var(eid, iv.min_value)
                val = iv

            else:  # string / bytes …
                val = f"symbol_{eid}"

            return Variables(identifier=eid, value=val, scope="array_element",
                             typeInfo=baseT)

        # ─ baseT 가 SolType(array) 인 경우 → 다차원 배열 ──────────────
        if isinstance(baseT, SolType) and baseT.typeCategory == "array":
            sub_arr = ArrayVariable(identifier=eid,
                                    base_type=baseT.arrayBaseType,
                                    array_length=baseT.arrayLength,
                                    is_dynamic=baseT.isDynamicArray,
                                    scope="array_element")
            # 하위 요소 미리 0-length 로 두고 필요 시 lazy-append
            return sub_arr

        # ─ struct / mapping 등 복합 타입은 심볼릭 처리 ───────────────
        return Variables(identifier=eid, value=f"symbol_{eid}",
                         scope="array_element", typeInfo=baseT)

    # ───────── mapping value 생성 ──────────────────────────────────────────
    def _create_new_mapping_value(
            self,
            map_var: MappingVariable,
            key: str | int,
    ) -> Variables:
        """
        새 key 접근 시, 기본 값을 가진 child Variables 생성.

        * address value 인 경우 AddressSymbolicManager 로 fresh interval 지급.
        * 그 밖의 elementary → bottom interval.
        * 배열/구조체/매핑 등의 value 타입은 보수적으로 symbol 로 둠.
        """
        eid = f"{map_var.identifier}[{key}]"
        val_type: SolType = map_var.typeInfo.mappingValueType

        # elementary --------------------------------------------------------
        if val_type.typeCategory == "elementary":
            et = val_type.elementaryTypeName

            if et.startswith("uint"):
                bits = val_type.intTypeLength or 256
                val = UnsignedIntegerInterval.bottom(bits)

            elif et.startswith("int"):
                bits = val_type.intTypeLength or 256
                val = IntegerInterval.bottom(bits)

            elif et == "bool":
                val = BoolInterval.bottom()

            elif et == "address":
                iv = self.sm.alloc_fresh_interval()
                self.sm.bind_var(eid, iv.min_value)
                val = iv

            else:  # bytes, string …
                val = f"symbol_{eid}"

        # non-elementary ----------------------------------------------------
        else:
            # (array / struct / mapping 등은 본 연구 범위 밖 → symbol 처리)
            val = f"symbol_{eid}"

        child = Variables(identifier=eid, value=val, scope="mapping_value", typeInfo=val_type)
        return child

    # ───────── 값 덮어쓰기 (debug 주석용) ────────────────────────────────────
    def _apply_new_value_to_variable(self, var_obj: Variables, new_value):
        """
        new_value 유형
          • IntegerInterval / UnsignedIntegerInterval / BoolInterval
          • 단일 int / bool
          • 'symbolicAddress N'  (str)
          • 기타 str   (symbolic tag)
        """
        # 0) 이미 Interval 객체면 그대로
        if self._is_interval(new_value) or isinstance(new_value, BoolInterval):
            var_obj.value = new_value
            return

        # 1) elementary 타입 확인
        if not (var_obj.typeInfo and var_obj.typeInfo.elementaryTypeName):
            print(f"[Info] _apply_new_value_to_variable: skip non-elementary '{var_obj.identifier}'")
            return

        etype = var_obj.typeInfo.elementaryTypeName
        bits = var_obj.typeInfo.intTypeLength or 256

        # ---- int / uint ---------------------------------------------------
        if etype.startswith("int"):
            iv = (
                new_value
                if isinstance(new_value, IntegerInterval)
                else IntegerInterval(int(new_value), int(new_value), bits)
            )
            var_obj.value = iv

        elif etype.startswith("uint"):
            uv = (
                new_value
                if isinstance(new_value, UnsignedIntegerInterval)
                else UnsignedIntegerInterval(int(new_value), int(new_value), bits)
            )
            var_obj.value = uv

        # ---- bool ---------------------------------------------------------
        elif etype == "bool":
            if isinstance(new_value, str) and new_value.lower() == "any":
                var_obj.value = BoolInterval.top()
            elif isinstance(new_value, (bool, int)):
                b = bool(new_value)
                var_obj.value = BoolInterval(int(b), int(b))
            else:
                var_obj.value = new_value  # already BoolInterval

        # ---- address ------------------------------------------------------
        elif etype == "address":
            if isinstance(new_value, UnsignedIntegerInterval):
                var_obj.value = new_value
                self.sm.bind_var(var_obj.identifier, new_value.min_value)

            elif isinstance(new_value, str) and new_value.startswith("symbolicAddress"):
                nid = int(new_value.split()[1])
                self.sm.register_fixed_id(nid)
                iv = self.sm.get_interval(nid)
                var_obj.value = iv
                self.sm.bind_var(var_obj.identifier, nid)

            else:  # 임의 문자열 → symbol 처리
                var_obj.value = f"symbol_{new_value}"

        # ---- fallback -----------------------------------------------------
        else:
            print(f"[Warning] _apply_new_value_to_variable: unhandled type '{etype}'")
            var_obj.value = new_value

    # ───────── debug LHS 해석 (member / index 접근) ────────────────────────
    def _resolve_and_update_expr(self, expr: Expression, fcfg: FunctionCFG, new_value):
        """
        testingExpression (AST) → 실제 변수 객체를 찾아 value 업데이트
        """
        # 1) 루트 식별자
        if expr.base is None:
            v = fcfg.get_related_variable(expr.identifier)
            if v and new_value is not None:
                self._apply_new_value_to_variable(v, new_value)
            return v

        # 2) base  먼저 해석
        base_obj = self._resolve_and_update_expr(expr.base, fcfg, None)
        if base_obj is None:
            return None

        # ─ member access (struct) ─────────────────────────────────────────
        if expr.member is not None:
            if not isinstance(base_obj, StructVariable):
                print(f"[Warn] member access on non-struct '{base_obj.identifier}'")
                return None
            m = base_obj.members.get(expr.member)
            if m is None:
                print(f"[Warn] struct '{base_obj.identifier}' has no member '{expr.member}'")
                return None
            if new_value is not None:
                self._apply_new_value_to_variable(m, new_value)
            return m

        # ─ index access (array / mapping) ─────────────────────────────────
        if expr.index is not None:
            idx_val = self._extract_index_val(expr.index)

            # ▸ 배열
            if isinstance(base_obj, ArrayVariable):
                if not isinstance(idx_val, int) or idx_val < 0:
                    print("[Warn] array index must be non-negative literal")
                    return None
                while idx_val >= len(base_obj.elements):
                    # address/bytes 등 실제 타입 고려
                    new_elem = self._create_new_array_element(base_obj,
                                                              len(base_obj.elements))
                elem = base_obj.elements[idx_val]
                if new_value is not None:
                    self._apply_new_value_to_variable(elem, new_value)
                return elem

            # ▸ 매핑
            if isinstance(base_obj, MappingVariable):
                key = str(idx_val)
                if key not in base_obj.mapping:
                    base_obj.mapping[key] = self._create_new_mapping_value(base_obj, key)
                tgt = base_obj.mapping[key]
                if new_value is not None:
                    self._apply_new_value_to_variable(tgt, new_value)
                return tgt

            print(f"[Warn] index access on non-array/mapping '{base_obj.identifier}'")
            return None

        return None

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

    def variables_equal(self, vars1: dict[str, Variables],
                        vars2: dict[str, Variables]) -> bool:
        """
        두 variable-env 가 완전히 동일한지 비교.
        구조 동일 + 값(equals) 동일해야 True
        """
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
        elif stmt.statement_type == 'unchecked' :
            return current_variables
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

                    if cfg_node.name.startswith("else") :
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
                    close_brace_queue.append(line)

            # ────────── CASE 2. close_brace_queue가 이미 존재 ──────────
            else:
                # 연속 '}' 누적
                if brace_info["open"] == 0 and brace_info["close"] == 1 and brace_info["cfg_node"] is None:
                    open_brace_info = self.find_corresponding_open_brace(line)
                    if not open_brace_info['cfg_node'].condition_node : # unchecked indicator or general curly brace
                        continue
                    else :
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

        # ───── 분석 스냅샷 ②: loop-fixpoint ──────────
        self._record_analysis(
            line_no=loop_condition_node.src_line + 0.9,  # 같은 라인 그룹에 살짝 뒤에
            stmt_type="loop-fixpoint",
            env=exit_node.variables
        )
        # ────────────────────────────────────────────

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
                if cfg_node == 'unchecked' :
                    return 'unchecked'

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
    def join_variables_with_widening(
            self,
            left_vars: dict[str, Variables] | None,
            right_vars: dict[str, Variables] | None
    ) -> dict[str, Variables]:
        """
        • left_vars ⨆ right_vars  +  widening
        • 값(Interval-계열)에 widen() 이 있으면 사용,
          그렇지 않으면 보통 join_variable_values() 로 합집합.
        """
        if left_vars is None:
            return self.copy_variables(right_vars or {})

        res = self.copy_variables(left_vars)

        for name, r_var in (right_vars or {}).items():

            # 이미 존재하는 변수라면 widen / join
            if name in res:
                l_var = res[name]

                # 두 변수 모두 elementary / enum / address 같은 '값'을 가진 경우
                if hasattr(l_var.value, "widen"):
                    l_var.value = l_var.value.widen(r_var.value)  # ★ 여기서 value.widen
                else:
                    l_var.value = self.join_variable_values(l_var.value,
                                                            r_var.value)
            else:
                # 새로 등장한 변수 → deep-copy 하여 추가
                res[name] = self.copy_variables({name: r_var})[name]

        return res

    # ――― simple join (⊔)  – narrowing 단계용 ――――――――――――――――――――――
    def join_variables_simple(
            self,
            left_vars: dict[str, Variables] | None,
            right_vars: dict[str, Variables] | None
    ) -> dict[str, Variables]:
        """
        값(Interval-계열)에 join() 이 있으면 그것을 쓰고,
        없으면  join_variable_values() 로 보수적 합집합을 만든다.
        """
        if left_vars is None:
            return self.copy_variables(right_vars or {})

        res = self.copy_variables(left_vars)

        for name, r_var in (right_vars or {}).items():

            if name in res:
                l_var = res[name]

                # ─ elementary / enum / address ───────────────────────────
                if hasattr(l_var.value, "join"):
                    l_var.value = l_var.value.join(r_var.value)
                else:
                    # Interval 이 아니거나 join() 없음 → 보수적 합집합
                    l_var.value = self.join_variable_values(l_var.value,
                                                            r_var.value)

            else:
                # 새 변수 → deep-copy
                res[name] = self.copy_variables({name: r_var})[name]

        return res

    # ――― narrow – old ⊓ new  ―――――――――――――――――――――――――――――――――――
    def narrow_variables(
            self,
            old_vars: dict[str, Variables],
            new_vars: dict[str, Variables]
    ) -> dict[str, Variables]:
        """
        각 변수의 value 가 지원하면  value.narrow(new_value)  를 적용한다.
        지원하지 않는 타입은  new_value 로 덮어쓴다.
        """
        res = self.copy_variables(old_vars)

        for name, n_var in new_vars.items():

            if name in res:
                o_var = res[name]

                # Interval / BoolInterval 같이 narrow() 를 제공하는 타입
                if hasattr(o_var.value, "narrow"):
                    o_var.value = o_var.value.narrow(n_var.value)
                else:
                    # 좁히기 연산 불가 → 보수적으로 새 값으로 교체
                    o_var.value = self.join_variable_values(o_var.value,
                                                            n_var.value)

            else:
                # old_env 에 없던 새 변수 → deep-copy 후 추가
                res[name] = self.copy_variables({name: n_var})[name]

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

    def _resolve_and_update_expr(
            self,
            expr: Expression,
            fcfg: FunctionCFG,
            new_value  # Interval | BoolInterval | str | None
    ) -> Variables | ArrayVariable | StructVariable | MappingVariable | EnumVariable | None:
        """
        Expression → Variables (or container) 객체 탐색
        · new_value 가 주어지면 update_left_var 처럼 **값도 갱신**
        · new_value 가 None 이면 **탐색만** 수행
        """

        # ───── 0. 글로벌 변수인가? ───────────────────────────────────
        if self._is_global_expr(expr):
            gv = self._get_global_var(expr)
            # 글로벌은 값 갱신을 허용하지 않는다
            return gv

        # ───── 1. 루트 식별자 (base 없음) ────────────────────────────
        if expr.base is None:
            root_name = expr.identifier
            var_obj = fcfg.get_related_variable(root_name)
            if var_obj and new_value is not None:
                self._apply_new_value_to_variable(var_obj, new_value)
            return var_obj

        # ───── 2. base 부터 재귀로 찾기 ─────────────────────────────
        base_obj = self._resolve_and_update_expr(expr.base, fcfg, None)
        if base_obj is None:
            return None

        # 2-A. 멤버(Struct) ---------------------------------------------------
        if expr.member is not None:
            if not isinstance(base_obj, StructVariable):
                return None
            mem = base_obj.members.get(expr.member)
            if mem and new_value is not None:
                self._apply_new_value_to_variable(mem, new_value)
            return mem

        # 2-B. 인덱스(Array / Mapping) ---------------------------------------
        if expr.index is not None:
            idx_val = self._extract_index_val(expr.index)

            # Array ───────────────────────────────────────────────
            if isinstance(base_obj, ArrayVariable):
                if not isinstance(idx_val, int) or idx_val < 0:
                    return None
                # 동적 배열 길이 확장 필요 시
                while idx_val >= len(base_obj.elements):
                    base_obj.elements.append(
                        self._create_new_mapping_value(base_obj, len(base_obj.elements))
                    )
                elem = base_obj.elements[idx_val]
                if new_value is not None:
                    self._apply_new_value_to_variable(elem, new_value)
                return elem

            # Mapping ────────────────────────────────────────────
            if isinstance(base_obj, MappingVariable):
                key = str(idx_val)
                if key not in base_obj.mapping:
                    base_obj.mapping[key] = self._create_new_mapping_value(base_obj, key)
                child = base_obj.mapping[key]
                if new_value is not None:
                    self._apply_new_value_to_variable(child, new_value)
                return child

        # ───── 그 밖의 경우 ─────────────────────────────────────────
        return None

    """
    Abstract Interpretation part
    """
    # ContractAnalyzer 내부

    _GLOBAL_BASES = {"block", "msg", "tx"}

    def _is_global_expr(self, expr: Expression) -> bool:
        """
        Expression 이 block.xxx / msg.xxx / tx.xxx 형태인지 검사.
        """
        return (
                expr.member is not None  # x.y 형태
                and expr.base is not None
                and getattr(expr.base, "identifier", None) in self._GLOBAL_BASES
        )

    def _get_global_var(self, expr: Expression) -> Variables | None:
        """
        expr 가 정확히 'block.timestamp' 처럼 두 단계라면
        ContractCFG.globals 에서 GlobalVariable 객체를 반환
        """
        if expr.base is None or expr.member is None:
            return None
        base = expr.base.identifier  # 'block' / 'msg' / 'tx'
        member = expr.member  # 'timestamp' …
        full = f"{base}.{member}"
        ccf = self.contract_cfgs[self.current_target_contract]
        return ccf.globals.get(full)

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
        # ── ① 글로벌이면 갱신 금지 ─────────────────────────
        if self._is_global_expr(expr):
            return None

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
        """
        +=, -=, <<= … 등 복합 대입 연산자의 interval 계산.
        한쪽이 ⊥(bottom) 이면 결과도 ⊥ 로 전파한다.
        """

        # 0) 단순 대입인 '='
        if operator == '=':
            return right_interval

        # 1) ⊥-전파용 로컬 헬퍼 ――――――――――――――――――――――――――――
        def _arith_safe(l, r, fn):
            """
            l·r 중 하나라도 bottom ⇒ bottom 그대로 반환
            아니면 fn(l, r) 실행
            """
            if l.is_bottom() or r.is_bottom():
                return l.bottom(getattr(l, "type_length", 256))
            return fn(l, r)

        # 2) 연산자 → 동작 매핑 ―――――――――――――――――――――――――――――――
        mapping = {
            '+=': lambda l, r: _arith_safe(l, r, lambda a, b: a.add(b)),
            '-=': lambda l, r: _arith_safe(l, r, lambda a, b: a.subtract(b)),
            '*=': lambda l, r: _arith_safe(l, r, lambda a, b: a.multiply(b)),
            '/=': lambda l, r: _arith_safe(l, r, lambda a, b: a.divide(b)),
            '%=': lambda l, r: _arith_safe(l, r, lambda a, b: a.modulo(b)),
            '|=': lambda l, r: _arith_safe(l, r, lambda a, b: a.bitwise('|', b)),
            '^=': lambda l, r: _arith_safe(l, r, lambda a, b: a.bitwise('^', b)),
            '&=': lambda l, r: _arith_safe(l, r, lambda a, b: a.bitwise('&', b)),
            '<<=': lambda l, r: _arith_safe(l, r, lambda a, b: a.shift(b, '<<')),
            '>>=': lambda l, r: _arith_safe(l, r, lambda a, b: a.shift(b, '>>')),
            '>>>=': lambda l, r: _arith_safe(l, r, lambda a, b: a.shift(b, '>>>')),
        }

        # 3) 실행
        try:
            return mapping[operator](left_interval, right_interval)
        except KeyError:
            raise ValueError(f"Unsupported compound-assignment operator: {operator}")

    def update_left_var_of_index_access_context(self, expr, rVal, operator, variables,
                                                callerObject=None, callerContext=None):
        # base expression에 대한 재귀
        base_obj = self.update_left_var(expr.base, rVal, operator, variables, None, "IndexAccessContext")

        # index expression에 대한 재귀
        self.update_left_var(expr.index, rVal, operator, variables, base_obj, "IndexAccessContext")

    def update_left_var_of_member_access_context(
            self, expr, rVal, operator, variables,
            callerObject=None, callerContext=None):

        # ① 먼저 base 부분을 재귀-업데이트
        base_obj = self.update_left_var(expr.base, rVal, operator,
                                        variables, None, "MemberAccessContext")
        member = expr.member

        # ② base 가 StructVariable 인지 확인
        if not isinstance(base_obj, StructVariable):
            raise ValueError(f"Member access on non-struct '{base_obj.identifier}'")

        # ③ 멤버 존재 확인
        if member not in base_obj.members:
            raise ValueError(f"Member '{member}' not in struct '{base_obj.identifier}'")

        nested = base_obj.members[member]

        # ── elementary / enum ──────────────────────────────
        if isinstance(nested, (Variables, EnumVariable)):
            nested.value = self.compound_assignment(nested.value, rVal, operator)
            return nested  # ← 작업 완료

        # ── 배열 / 중첩 구조체 ──────────────────────────────
        if isinstance(nested, (StructVariable, ArrayVariable, MappingVariable)):
            # 더 깊은 member access가 이어질 수 있으므로 그대로 반환
            return nested

        # ── 예외 처리 ──────────────────────────────────────
        raise ValueError(f"Unexpected member-type '{type(nested).__name__}'")

    def update_left_var_of_literal_context(
            self, expr, rVal, operator, variables,
            callerObject: Variables | ArrayVariable | MappingVariable | None = None):

        # ───────────────────────── 0. 준비 ─────────────────────────
        lit = expr.literal  # 예: "123", "0x1a", "true"
        lit_str = str(lit)
        lit_iv = None  # 필요 시 Interval 변환 결과
        if callerObject is None:
            raise ValueError(f"Literal '{lit_str}' cannot appear standalone on LHS")

        # bool·int·uint·address Literal → Interval 변환 helper  ───── 💡
        def _to_interval(ref_var: Variables, literal_text: str):
            if self._is_interval(rVal):  # 이미 Interval이라면 그대로
                return rVal

            # 숫자   -------------------------------------------------
            if literal_text.startswith(('-', '0x')) or literal_text.isdigit():
                v = int(literal_text, 0)  # auto base
                et = ref_var.typeInfo.elementaryTypeName
                if et.startswith("int"):
                    b = ref_var.typeInfo.intTypeLength or 256
                    return IntegerInterval(v, v, b)
                if et.startswith("uint"):
                    b = ref_var.typeInfo.intTypeLength or 256
                    return UnsignedIntegerInterval(v, v, b)

            # 불리언 -------------------------------------------------
            if literal_text in ("true", "false"):
                return BoolInterval(1, 1) if literal_text == "true" else BoolInterval(0, 0)

            # 주소 hex (0x…) ---------------------------------------- 💡
            if literal_text.startswith("0x") and len(literal_text) <= 42:
                v = int(literal_text, 16)
                return UnsignedIntegerInterval(v, v, 160)

            # 그 외 문자열/bytes 등 -> 그대로 symbol 처리
            return literal_text

        # ───────────────────────── 1. Array LHS ────────────────────
        if isinstance(callerObject, ArrayVariable):
            if not lit_str.isdigit():
                return None  # 비정수 인덱스 → 상위에서 오류/다른 케이스 처리

            idx = int(lit_str)
            if idx < 0:
                raise IndexError(f"Negative index {idx} for array '{callerObject.identifier}'")

            # 💡 동적 배열이라면 빈 element 채워넣기
            while idx >= len(callerObject.elements):
                # address/bytes 등은 symbolic 으로
                callerObject.elements.append(
                    Variables(f"{callerObject.identifier}[{len(callerObject.elements)}]",
                              f"symbol_{callerObject.identifier}_{len(callerObject.elements)}",
                              scope=callerObject.scope,
                              typeInfo=callerObject.typeInfo.arrayBaseType)
                )

            elem = callerObject.elements[idx]

            # leaf (elementary or enum)
            if isinstance(elem, (Variables, EnumVariable)):
                lit_iv = _to_interval(elem, rVal if isinstance(rVal, str) else lit_str)
                elem.value = self.compound_assignment(elem.value, lit_iv, operator)
                return None

            # 중첩 array/struct → 계속 내려감
            if isinstance(elem, (ArrayVariable, StructVariable, MappingVariable)):
                return elem
            return None

        # ───────────────────────── 2. Mapping LHS ──────────────────
        if isinstance(callerObject, MappingVariable):
            key = lit_str  # mapping key 는 문자열 그대로 보존
            if key not in callerObject.mapping:  # 없으면 새 child 생성
                callerObject.mapping[key] = self._create_new_mapping_value(callerObject, key)
            mvar = callerObject.mapping[key]

            if isinstance(mvar, (Variables, EnumVariable)):
                lit_iv = _to_interval(mvar, rVal if isinstance(rVal, str) else lit_str)
                mvar.value = self.compound_assignment(mvar.value, lit_iv, operator)
                return None

            if isinstance(mvar, (ArrayVariable, StructVariable, MappingVariable)):
                return mvar
            return None

        # ───────────────────────── 3. 기타(Struct 등) ───────────────
        raise ValueError(f"Literal context '{lit_str}' not handled for '{type(callerObject).__name__}'")

    def update_left_var_of_identifier_context(
            self,
            expr: Expression,
            rVal,  # Interval | int | str …
            operator: str,
            variables: dict[str, Variables],
            callerObject: Variables | ArrayVariable | StructVariable | MappingVariable | None = None,
            callerContext: str | None = None):

        ident = expr.identifier

        # ───────────────────────── helper ──────────────────────────
        def _apply_to_leaf(var_obj: Variables | EnumVariable):
            """compound-assignment 를 leaf 변수에 적용"""
            # rVal 이 원시(숫자·true 등)라면 Interval 로 래핑
            if not self._is_interval(rVal) and isinstance(var_obj, Variables):
                if isinstance(rVal, str):
                    # 숫자/bool literal → Interval
                    if rVal.lstrip('-').isdigit() or rVal.startswith('0x'):
                        et = var_obj.typeInfo.elementaryTypeName
                        if et.startswith("int"):
                            bit = var_obj.typeInfo.intTypeLength or 256
                            rv = IntegerInterval(int(rVal, 0), int(rVal, 0), bit)
                        elif et.startswith("uint"):
                            bit = var_obj.typeInfo.intTypeLength or 256
                            rv = UnsignedIntegerInterval(int(rVal, 0), int(rVal, 0), bit)
                        elif et == "bool":
                            rv = BoolInterval(1, 1) if rVal == "true" else BoolInterval(0, 0)
                        else:
                            rv = rVal  # address / bytes → 그대로
                    else:
                        rv = rVal
                else:
                    rv = rVal
            else:
                rv = rVal

            var_obj.value = self.compound_assignment(var_obj.value, rv, operator)

        # ─────────────────────── 1. 상위 객체 존재 ──────────────────
        if callerObject is not None:

            # 1-A) 단순 변수/enum → 그대로 leaf 갱신
            if isinstance(callerObject, (Variables, EnumVariable)):
                _apply_to_leaf(callerObject)
                return None

            # 1-B) ArrayVariable  (ident 는 index 변수명)
            if isinstance(callerObject, ArrayVariable):
                if ident not in variables:
                    raise ValueError(f"Index identifier '{ident}' not found.")
                idx_var = variables[ident]

                # 스칼라인지 보장
                if not self._is_interval(idx_var.value) or \
                        idx_var.value.min_value != idx_var.value.max_value:
                    raise ValueError(f"Array index '{ident}' must resolve to single constant.")

                idx = idx_var.value.min_value
                if idx < 0 or idx >= len(callerObject.elements):
                    raise IndexError(f"Index {idx} out of range for array '{callerObject.identifier}'")

                elem = callerObject.elements[idx]
                if isinstance(elem, (Variables, EnumVariable)):
                    _apply_to_leaf(elem)
                    return None
                return elem  # nested array / struct / mapping

            # 1-C) StructVariable  → 멤버 접근
            if isinstance(callerObject, StructVariable):
                if ident not in callerObject.members:
                    raise ValueError(f"Struct '{callerObject.identifier}' has no member '{ident}'")
                mem = callerObject.members[ident]
                if isinstance(mem, (Variables, EnumVariable)):
                    _apply_to_leaf(mem)
                    return None
                return mem

            # 1-D) MappingVariable → key 가 식별자인 케이스
            if isinstance(callerObject, MappingVariable):
                if ident not in callerObject.mapping:
                    callerObject.mapping[ident] = self._create_new_mapping_value(callerObject, ident)
                mvar = callerObject.mapping[ident]
                if isinstance(mvar, (Variables, EnumVariable)):
                    _apply_to_leaf(mvar)
                    return None
                return mvar

            # 예기치 못한 상위 타입
            raise ValueError(f"Unhandled callerObject type: {type(callerObject).__name__}")

        # ─────────────────────── 2. 상위 객체 없음 ──────────────────
        # (IndexAccess / MemberAccess 의 base 식별자를 해결하기 위한 분기)
        if callerContext in ("IndexAccessContext", "MemberAccessContext"):
            return variables.get(ident)  # 상위에서 None 체크

        # ─────────────────────── 3. 일반 대입식 ─────────────────────
        # 로컬-스코프 or state-scope 변수 직접 갱신
        if ident not in variables:
            raise ValueError(f"Variable '{ident}' not declared in current scope.")

        target_var = variables[ident]
        if not isinstance(target_var, (Variables, EnumVariable)):
            raise ValueError(f"Assignment to non-scalar variable '{ident}' must use member/index access.")

        _apply_to_leaf(target_var)
        return None

    def evaluate_expression(self, expr: Expression, variables, callerObject=None, callerContext=None):
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
        elif expr.context == "TupleExpressionContext":
            return self.evaluate_tuple_expression_context(expr, variables,
                                                          callerObject, callerContext)

        # 단항 연산자
        if expr.operator in ['-', '!', '~'] and expr.expression :
            return self.evaluate_unary_operator(expr, variables, callerObject, callerContext)

        # 이항 연산자
        if expr.left is not None and expr.right is not None :
            return self.evaluate_binary_operator(expr, variables, callerObject, callerContext)

    # ───────────────────── evaluate_literal_context ──────────────
    def evaluate_literal_context(
            self,
            expr: Expression,
            variables: dict[str, Variables],
            callerObject: Variables | ArrayVariable | MappingVariable | None = None,
            callerContext: str | None = None):

        lit = expr.literal  # 예: "123", "0x1A", "true", ...
        ety = expr.expr_type  # 'uint'·'int'·'bool'·'string'·'address' 등

        def _to_scalar_int(txt: str) -> int:
            """10진·16진(0x)·8진(0o) 등을 int 로 변환, 부호 허용"""
            return int(txt, 0)  # base=0  →  자동 판별

        def _literal_is_address(txt: str) -> bool:
            """
            0x 로 시작하고 20 바이트(40 hex) 또는 0x0 처럼 짧아도 ‘주소 literal’ 로 간주
            실제 Solidity lexer 는 0x 포함 42자 고정이지만, 여기선 분석 편의상 느슨하게 허용
            """
            return txt.lower().startswith("0x") and all(c in "0123456789abcdefABCDEF" for c in txt[2:])

        # ───────── 1. 상위 객체(Array / Mapping) 인덱싱 ──────────
        if callerObject is not None:
            # 1-A) 배열 인덱스
            if isinstance(callerObject, ArrayVariable):
                if not lit.lstrip("-").isdigit():
                    raise ValueError(f"Array index must be decimal literal, got '{lit}'")
                idx = int(lit)
                if idx < 0 or idx >= len(callerObject.elements):
                    raise IndexError(f"Index {idx} out of range for array '{callerObject.identifier}'")
                return callerObject.elements[idx]  # element (Variables | …)

            # 1-B) 매핑 키 – 문자열·hex·decimal 모두 허용
            if isinstance(callerObject, MappingVariable):
                key = lit
                if key not in callerObject.mapping:
                    # 새 엔트리 생성
                    new_var = self._create_new_mapping_value(callerObject, key)
                    # CFG 에 반영
                    self.update_mapping_in_cfg(callerObject.identifier, key, new_var)
                return callerObject.mapping[key]

        # ───────── 2. 상위 없음 & 인덱스/멤버 base 해결 ──────────
        if callerContext in ("IndexAccessContext", "MemberAccessContext"):
            return lit  # key 로 그대로 사용

        # ───────── 3. 실제 값으로 해석해 반환 ──────────
        if ety == "uint":
            val = _to_scalar_int(lit)
            if val < 0:
                raise ValueError("uint literal cannot be negative")
            bits = expr.type_length or 256
            return UnsignedIntegerInterval(val, val, bits)

        if ety == "int":
            bits = expr.type_length or 256
            val = _to_scalar_int(lit)
            return IntegerInterval(val, val, bits)

        if ety == "bool":
            if lit.lower() == "true":
                return BoolInterval(1, 1)
            if lit.lower() == "false":
                return BoolInterval(0, 0)
            raise ValueError(f"Invalid bool literal '{lit}'")

        # 새로 추가 ───────── address / bytes / string ─────────
        if ety == "address":
            if not _literal_is_address(lit):
                raise ValueError(f"Malformed address literal '{lit}'")
            val_int = int(lit, 16)
            return UnsignedIntegerInterval(val_int, val_int, 160)  # 160-bit 고정

        if ety in ("string", "bytes"):
            return lit  # 심볼릭 취급 ― 추가 분석시 필요하면 해시 등 사용

        # 기타 타입
        raise ValueError(f"Unsupported literal expr_type '{ety}'")

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

    def evaluate_member_access_context(
            self,
            expr: Expression,
            variables: dict[str, Variables],
            callerObject: Variables | None = None,
            callerContext: str | None = None):

        sm = self.sm  # AddressSymbolicManager ─ 주소 심볼릭 ID 관리
        baseVal = self.evaluate_expression(expr.base, variables, None,
                                           "MemberAccessContext")
        member = expr.member
        # ──────────────────────────────────────────────────────────────
        # 1. Global-var (block / msg / tx)
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, str):
            if baseVal in {"block", "msg", "tx"}:
                full_name = f"{baseVal}.{member}"
                contractCfg = self.contract_cfgs[self.current_target_contract]

                gv_obj = contractCfg.globals[full_name]
                funcName = self.current_target_function
                gv_obj.usage_sites.add(funcName)

                return gv_obj.current  # Interval or address-interval

            # address.code / address.code.length
            if baseVal == "code":
                if member == "length":
                    # 코드 사이즈 – 예시로 고정 상수
                    return UnsignedIntegerInterval(0, 24_000, 256)
                return member  # address.code → 다음 단계에서 .length 접근

            if member == "code":  # <addr>.code
                return "code"  # 상위 계층에서 재귀적으로 처리

            raise ValueError(f"member '{member}' is not a recognised global-member.")

        # ──────────────────────────────────────────────────────────────
        # 2. ArrayVariable  ( .myArray.length  /  .push() / .pop() )
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, ArrayVariable):
            # .push() / .pop()  – 동적배열만 허용
            if callerContext == "functionCallContext":
                if not baseVal.typeInfo.isDynamicArray:
                    raise ValueError("push / pop available only on dynamic arrays")
                elemType = baseVal.typeInfo.arrayBaseType

                if member == "push":
                    new_elem_id = f"{baseVal.identifier}[{len(baseVal.elements)}]"
                    # ▶ 기본-타입 요소 새로 만들어 배열에 append
                    if (isinstance(elemType, SolType) and
                            elemType.typeCategory == "elementary" and
                            elemType.elementaryTypeName == "address"):

                        iv = sm.alloc_fresh_interval()
                        sm.bind_var(new_elem_id, iv.min_value)
                        new_var = Variables(new_elem_id, iv, scope=baseVal.scope,
                                            typeInfo=elemType)
                    else:
                        # 숫자·bool 등
                        default_iv = self.calculate_default_interval(elemType
                                                                     if isinstance(elemType, str)
                                                                     else elemType.elementaryTypeName)
                        new_var = Variables(new_elem_id, default_iv, scope=baseVal.scope,
                                            typeInfo=elemType)
                    baseVal.elements.append(new_var)
                    baseVal.typeInfo.arrayLength += 1
                    return None

                if member == "pop":
                    if not baseVal.elements:
                        raise IndexError("pop from empty array")
                    baseVal.elements.pop()
                    baseVal.typeInfo.arrayLength -= 1
                    return None

            if member == "length":
                ln = len(baseVal.elements)
                return UnsignedIntegerInterval(ln, ln, 256)

        # ──────────────────────────────────────────────────────────────
        # 3. StructVariable  ( struct.field )
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, StructVariable):
            if member not in baseVal.members:
                raise ValueError(f"'{member}' not in struct '{baseVal.identifier}'")
            nested = baseVal.members[member]
            # elementary / enum → 값, 복합 → 객체 반환
            return nested.value if isinstance(nested, (Variables, EnumVariable)) else nested

        # ──────────────────────────────────────────────────────────────
        # 4. EnumDefinition  (EnumType.RED)
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, EnumDefinition):
            try:
                idx = baseVal.members.index(member)
                return UnsignedIntegerInterval(idx, idx, 256)
            except ValueError:
                raise ValueError(f"'{member}' not a member of enum '{baseVal.enum_name}'")

        # ──────────────────────────────────────────────────────────────
        # 5. Solidity type(uint).max / min  (baseVal == dict with "isType")
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, dict) and baseVal.get("isType"):
            T = baseVal["typeName"]
            if member not in {"max", "min"}:
                raise ValueError(f"Unsupported type property '{member}' for {T}")

            if T.startswith("uint"):
                bits = int(T[4:]) if len(T) > 4 else 256
                if member == "max":
                    mx = 2 ** bits - 1
                    return UnsignedIntegerInterval(mx, mx, bits)
                return UnsignedIntegerInterval(0, 0, bits)  # min

            if T.startswith("int"):
                bits = int(T[3:]) if len(T) > 3 else 256
                if member == "max":
                    mx = 2 ** (bits - 1) - 1
                    return IntegerInterval(mx, mx, bits)
                mn = -2 ** (bits - 1)
                return IntegerInterval(mn, mn, bits)

            raise ValueError(f"type() with unsupported base '{T}'")

        # ──────────────────────────────────────────────────────────────
        # 6. 기타 – 심볼릭 보수적 값
        # ──────────────────────────────────────────────────────────────
        return f"symbolic({baseVal}.{member})"

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

    def evaluate_tuple_expression_context(self, expr, variables,
                                          callerObject=None, callerContext=None):
        values = [self.evaluate_expression(e, variables, None, "TupleElem")
                  for e in expr.elements]
        return values  # list 그대로 돌려줌

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

        def _bottom(interval) -> "Interval":
            """
            interval 과 동일한 클래스·bit-width로 ⊥(bottom) 을 만들어 준다.
            (IntegerInterval.bottom(bits) 같은 헬퍼 통일)
            """
            if isinstance(interval, IntegerInterval):
                return IntegerInterval.bottom(interval.type_length)
            if isinstance(interval, UnsignedIntegerInterval):
                return UnsignedIntegerInterval.bottom(interval.type_length)
            if isinstance(interval, BoolInterval):
                return BoolInterval.bottom()
            return Interval(None, None)  # fallback – 거의 안 옴

        if (isinstance(leftInterval, Interval) and leftInterval.is_bottom()) or \
                (isinstance(rightInterval, Interval) and rightInterval.is_bottom()):
            # 산술/비트/시프트 → ⊥,  비교/논리 → BoolInterval ⊤(= [0,1])
            if operator in ['==', '!=', '<', '>', '<=', '>=', '&&', '||']:
                return BoolInterval.top()
            return _bottom(leftInterval if not leftInterval.is_bottom()else rightInterval)

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

            # (c) 범위: [min_idx .. max_idx]  ─ ArrayVariable --------------------------
            joined = None
            for idx in range(min_idx, max_idx + 1):
                if idx < 0 or idx >= len(callerObject.elements):
                    return f"symbolicIndexRange({callerObject.identifier}[{result}])"

                elem_var = callerObject.elements[idx]
                val = elem_var.value if hasattr(elem_var, "value") else elem_var

                # ▶ Interval 류만 join; 그 외는 symbolic 처리
                if hasattr(val, "join"):
                    joined = val if joined is None else joined.join(val)
                else:
                    return f"symbolicMixedType({callerObject.identifier}[{result}])"

            return joined  # 모든 요소가 Interval·BoolInterval 이었던 경우

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
                # 범위 [min_idx .. max_idx]  ─ MappingVariable -----------------------------
                joined = None
                for k in range(min_idx, max_idx + 1):
                    k_str = str(k)
                    if k_str not in callerObject.mapping:
                        new_obj = self.create_default_mapping_value(callerObject, k_str)
                        self.update_mapping_in_cfg(callerObject.identifier, k_str, new_obj)
                        val = new_obj.value
                    else:
                        val = callerObject.mapping[k_str].value

                    if hasattr(val, "join"):
                        joined = val if joined is None else joined.join(val)
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

    def _update_single_condition(self, vars_, cond_expr, is_true_branch):
        # bool literal인 경우는 영향 없음
        if cond_expr.context == "LiteralExpContext":
            return

        val = self.evaluate_expression(cond_expr, vars_, None, None)
        # ▸ bool interval로 강제 변환
        if not isinstance(val, BoolInterval):
            if self._is_interval(val):  # 숫자/주소
                val = self._convert_int_to_bool_interval(val)
            else:
                return  # symbol 등 – 포기

        tgt = BoolInterval(1, 1) if is_true_branch else BoolInterval(0, 0)
        refined = val.meet(tgt)

        name = (cond_expr.identifier
                if cond_expr.context == "IdentifierExpContext" else None)
        if name and name in vars_:
            vars_[name].value = refined

    def _update_logical_condition(
            self,
            variables: dict[str, Variables],
            cond_expr: Expression,
            is_true_branch: bool) -> None:

        op = cond_expr.operator  # '&&', '||', '!'
        # ───────── NOT ─────────
        if op == '!':
            # !X : true-branch → X=false, false-branch → X=true
            return self._update_single_condition(
                variables,
                cond_expr.expression,  # operand
                not is_true_branch)

        # AND / OR 는 좌·우 피연산자 필요
        condA = cond_expr.left
        condB = cond_expr.right

        # ───────── AND ─────────
        if op == '&&':
            if is_true_branch:  # 둘 다 참이어야 함
                self.update_variables_with_condition(variables, condA, True)
                self.update_variables_with_condition(variables, condB, True)
            else:  # A==false  또는  B==false
                # 두 피연산자 모두 “0 가능”하도록 meet
                self.update_variables_with_condition(variables, condA, False)
                self.update_variables_with_condition(variables, condB, False)
            return

        # ───────── OR ─────────
        if op == '||':
            if is_true_branch:  # A==true  또는  B==true
                # 둘 다 “1 가능”으로 넓힘 (정보 손실 최소화)
                self.update_variables_with_condition(variables, condA, True)
                self.update_variables_with_condition(variables, condB, True)
            else:  # 둘 다 false
                self.update_variables_with_condition(variables, condA, False)
                self.update_variables_with_condition(variables, condB, False)
            return

        raise ValueError(f"Unexpected logical operator '{op}'")

    def _update_comparison_condition(
            self,
            variables: dict[str, Variables],
            cond_expr: Expression,
            is_true_branch: bool) -> None:
        """
        cond_expr.operator ∈ {'<','>','<=','>=','==','!='}
        is_true_branch :
            · True  ⇒ op 그대로
            · False ⇒ negate_operator(op) 적용
        """

        op = cond_expr.operator
        actual_op = op if is_true_branch else self.negate_operator(op)

        left_expr = cond_expr.left
        right_expr = cond_expr.right

        # ───────── 1. 값 평가 ─────────
        left_val = self.evaluate_expression(left_expr, variables, None, None)
        right_val = self.evaluate_expression(right_expr, variables, None, None)

        # ---------------- CASE 1 : 둘 다 Interval ----------------
        if self._is_interval(left_val) and self._is_interval(right_val):
            new_l, new_r = self.refine_intervals_for_comparison(left_val, right_val, actual_op)
            self.update_left_var(left_expr, new_l, '=', variables)
            self.update_left_var(right_expr, new_r, '=', variables)
            return

        # ---------------- CASE 2-A : Interval  vs  스칼라/리터럴 ----------------
        if self._is_interval(left_val) and not self._is_interval(right_val):
            coerced_r = self._coerce_literal_to_interval(right_val, left_val.type_length)
            new_l, _ = self.refine_intervals_for_comparison(left_val, coerced_r, actual_op)
            self.update_left_var(left_expr, new_l, '=', variables)
            return

        # ---------------- CASE 2-B : 리터럴  vs  Interval ----------------
        if self._is_interval(right_val) and not self._is_interval(left_val):
            coerced_l = self._coerce_literal_to_interval(left_val, right_val.type_length)
            _, new_r = self.refine_intervals_for_comparison(coerced_l, right_val, actual_op)
            self.update_left_var(right_expr, new_r, '=', variables)
            return

        # ---------------- CASE 3 : BoolInterval 비교 ----------------
        if isinstance(left_val, BoolInterval) or isinstance(right_val, BoolInterval):
            self._update_bool_comparison(
                variables,
                left_expr, right_expr,
                left_val, right_val,
                actual_op)
            return

        # ---------------- CASE 4 : 주소 Interval(address) 비교 ▲ ----------------
        # (주소 literal ‘0x…’ → UnsignedIntegerInterval(…,160) 로 강제 변환)
        if (self._is_interval(left_val) and left_val.type_length == 160) or \
                (self._is_interval(right_val) and right_val.type_length == 160):

            # 좌·우 모두 Interval 로 맞추기
            if not self._is_interval(left_val):
                left_val = self._coerce_literal_to_interval(left_val, 160)
            if not self._is_interval(right_val):
                right_val = self._coerce_literal_to_interval(right_val, 160)

            new_l, new_r = self.refine_intervals_for_comparison(left_val, right_val, actual_op)
            self.update_left_var(left_expr, new_l, '=', variables)
            self.update_left_var(right_expr, new_r, '=', variables)
            return


    def refine_intervals_for_comparison(
            self,
            a_iv,  # IntegerInterval | UnsignedIntegerInterval
            b_iv,
            op: str):

        # ── bottom short-cut ─────────────────────────
        if a_iv.is_bottom() or b_iv.is_bottom():
            return (a_iv.bottom(a_iv.type_length),
                    b_iv.bottom(b_iv.type_length))

        A, B = a_iv.copy(), b_iv.copy()

        # 내부 헬퍼 -----------------------------------
        def clamp_max(iv, new_max):
            if iv.is_bottom():
                return iv
            if new_max < iv.min_value:
                return iv.bottom(iv.type_length)
            iv.max_value = min(iv.max_value, new_max)
            return iv

        def clamp_min(iv, new_min):
            if iv.is_bottom():
                return iv
            if new_min > iv.max_value:
                return iv.bottom(iv.type_length)
            iv.min_value = max(iv.min_value, new_min)
            return iv

        # --------------------------------------------

        # <  ------------------------------------------------
        if op == '<':
            if B.min_value != NEG_INFINITY:
                A = clamp_max(A, B.min_value - 1)
            if not A.is_bottom() and A.max_value != INFINITY:
                B = clamp_min(B, A.max_value + 1)
            return A, B

        # >  ------------------------------------------------
        if op == '>':
            if B.max_value != INFINITY:
                A = clamp_min(A, B.max_value + 1)
            if not A.is_bottom() and A.min_value != NEG_INFINITY:
                B = clamp_max(B, A.min_value - 1)
            return A, B

        # <=  -----------------------------------------------
        if op == '<=':
            lt_a, lt_b = self.refine_intervals_for_comparison(a_iv, b_iv, '<')
            eq_a, eq_b = self.refine_intervals_for_comparison(a_iv, b_iv, '==')
            return lt_a.join(eq_a), lt_b.join(eq_b)

        # >=  -----------------------------------------------
        if op == '>=':
            gt_a, gt_b = self.refine_intervals_for_comparison(a_iv, b_iv, '>')
            eq_a, eq_b = self.refine_intervals_for_comparison(a_iv, b_iv, '==')
            return gt_a.join(eq_a), gt_b.join(eq_b)

        # ==  -----------------------------------------------
        if op == '==':
            meet = A.meet(B)
            return meet, meet

        # !=  -----------------------------------------------
        if op == '!=':
            if (A.min_value == A.max_value ==
                    B.min_value == B.max_value):
                # 동일 싱글톤이면 모순
                return (A.bottom(A.type_length),
                        B.bottom(B.type_length))
            return A, B

        # 알 수 없는 op → 변경 없음
        return A, B

    def _coerce_literal_to_interval(self, lit, default_bits=256):
        def _hex_addr_to_interval(hex_txt: str) -> UnsignedIntegerInterval:
            """‘0x…’ 문자열을 160-bit UnsignedInterval 로 변환"""
            val = int(hex_txt, 16)
            return UnsignedIntegerInterval(val, val, 160)

        def _is_address_literal(txt: str) -> bool:
            return txt.lower().startswith("0x") and all(c in "0123456789abcdef" for c in txt[2:])

        if isinstance(lit, (int, float)):
            v = int(lit)
            return IntegerInterval(v, v, default_bits) if v < 0 \
                else UnsignedIntegerInterval(v, v, default_bits)
        if isinstance(lit, str):
            if _is_address_literal(lit):
                return _hex_addr_to_interval(lit)  # ◀︎ NEW
            try:
                v = int(lit, 0)
                return IntegerInterval(v, v, default_bits) if v < 0 \
                    else UnsignedIntegerInterval(v, v, default_bits)
            except ValueError:
                return IntegerInterval(None, None, default_bits)  # bottom
        return IntegerInterval(None, None, default_bits)

    def _update_bool_comparison(
            self,
            variables: dict[str, Variables],
            left_expr: Expression,
            right_expr: Expression,
            left_val,  # evaluate_expression 결과
            right_val,  # 〃
            op: str  # '==', '!=' ...
    ):
        """
        bool - bool 비교식을 통해 피연산자의 BoolInterval 을 좁힌다.
          * op == '==' : 두 피연산자가 동일 값이어야 함 → 교집합(meet)
          * op == '!=' : 두 피연산자가 상이해야 함
                         ─ 한쪽이 단정(True/False) ⇒ 다른 쪽은 반대값으로
                         ─ 양쪽 모두 Top([0,1]) ⇒ 정보 부족 → 건너뜀
        """

        # ───────────────── 0. BoolInterval 변환 ─────────────────
        def _as_bool_iv(val):
            # 이미 BoolInterval
            if isinstance(val, BoolInterval):
                return val
            # 정수 Interval [0,0]/[1,1] => BoolInterval
            if self._is_interval(val):
                return self._convert_int_to_bool_interval(val)
            return None  # 그밖엔 Bool 로 간주하지 않음

        l_iv = _as_bool_iv(left_val)
        r_iv = _as_bool_iv(right_val)
        if l_iv is None or r_iv is None:
            # 둘 다 Bool 로 환원 안 되면 관여하지 않는다
            return

        # ※ left_expr / right_expr 가 identifier 인지 → 이름 얻기
        l_name = self._extract_identifier_if_possible(left_expr)
        r_name = self._extract_identifier_if_possible(right_expr)

        # helper ― 변수 env 에 실제 적용
        def _replace(name, new_iv: BoolInterval):
            if name in variables and isinstance(variables[name].value, BoolInterval):
                variables[name].value = variables[name].value.meet(new_iv)

        # ───────────────── 1. op == '==' ───────────────────────
        if op == "==":
            meet = l_iv.meet(r_iv)  # 교집합
            _replace(l_name, meet)
            _replace(r_name, meet)
            return

        # ───────────────── 2. op == '!=' ───────────────────────
        if op == "!=":
            # 한쪽이 [1,1]/[0,0] 처럼 단정이라면 → 다른 쪽을 반대 값으로 강제
            def _is_const(iv: BoolInterval) -> bool:
                return iv.min_value == iv.max_value

            if _is_const(l_iv) and _is_const(r_iv):
                # 둘 다 단정인데 현재 env 가 모순이면 meet 하면 bottom,
                # 분석기에서는 “실행 불가” 분기로 처리하거나 그대로 둠
                if l_iv.equals(r_iv):
                    # a != a 는 거짓 ⇒ 해당 분기는 불가능 → 아무 것도 하지 않고 탈출
                    return
                # a(0) != b(1) 처럼 이미 참 ⇒ 정보 없음
                return

            if _is_const(l_iv):
                opposite = BoolInterval(0, 0) if l_iv.min_value == 1 else BoolInterval(1, 1)
                _replace(r_name, opposite)
                return

            if _is_const(r_iv):
                opposite = BoolInterval(0, 0) if r_iv.min_value == 1 else BoolInterval(1, 1)
                _replace(l_name, opposite)
                return

            # 양쪽 다 [0,1] → 정보 없음
            return

        # ───────────────── 3. <,>,<=,>= (불리언엔 의미 X) ──────
        #   원하는 정책에 따라 symbolic 처리하거나 경고만 남김
        #   여기선 그냥 통과
        return

    # ContractAnalyzer (또는 Expression helper 모듈) 내부에 추가
    def _extract_identifier_if_possible(self, expr: Expression) -> str | None:
        """
        Expression 이 단순 ‘경로(path)’ 형태인지 판별해
          -  foo                      → "foo"
          -  foo.bar                 → "foo.bar"
          -  foo[3]                  → "foo[3]"
          -  foo.bar[2].baz          → "foo.bar[2].baz"
        처럼 **오직 식별자 / 멤버 / 정수-리터럴 인덱스**만으로 이루어져 있을 때
        그 전체 경로 문자열을 돌려준다.

        산술, 함수 호출, 심볼릭 인덱스 등이 섞이면 None 반환.
        """

        # ───── 1. 멤버/인덱스가 전혀 없는 루트 ─────
        if expr.base is None:
            # 순수 식별자인지 확인
            if expr.context == "IdentifierExpContext":
                return expr.identifier
            return None  # literal, 연산 등 → 식별자 아님

        # ───── 2. 먼저 base-경로를 재귀적으로 확보 ──────
        base_path = self._extract_identifier_if_possible(expr.base)
        if base_path is None:
            return None  # base 가 이미 복합 → 포기

        # ───── 3.A  멤버 접근 foo.bar ──────────────
        if expr.member is not None:
            return f"{base_path}.{expr.member}"

        # ───── 3.B  인덱스 접근 foo[3] ─────────────
        if expr.index is not None:
            # 인덱스가 “정수 리터럴”인지(실행 시 결정되면 안 됨)
            if expr.index.context == "LiteralExpContext" and str(expr.index.literal).lstrip("-").isdigit():
                return f"{base_path}[{int(expr.index.literal, 0)}]"
            return None  # 심볼릭 인덱스면 변수 하나로 볼 수 없음

        # 그 밖의 케이스(예: 슬라이스, 함수 호출 등)
        return None

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
            return self.evaluate_expression(expr, variables, None, "functionCallContext")

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



    def _expr_to_str(self, e: Expression) -> str:
        """Expression AST → Solidity 소스 형태 문자열"""
        if e is None:
            return ""

        # ❶ 식별자
        if e.base is None:
            return e.identifier or str(e.literal)

        # ❷ 멤버 access
        if e.member is not None:
            return f"{self._expr_to_str(e.base)}.{e.member}"

        # ❸ 인덱스 access  (배열·매핑)
        if e.index is not None:
            return f"{self._expr_to_str(e.base)}[{self._expr_to_str(e.index)}]"

        # (필요시 함수호출 등 확장)
        return "<expr>"

    def _flatten_var(self, var_obj, prefix: str, out: dict):
        """Variables / ArrayVariable / StructVariable / MappingVariable 재귀 flatten"""
        """line_no 에서 stmt_type 수행 직후/직전에 var_env 를 직렬화하여 저장"""

        def _serialize_val(v):
            if hasattr(v, 'min_value'):  # Interval · BoolInterval
                return f"[{v.min_value},{v.max_value}]"
            return str(v)

        val = getattr(var_obj, "value", None)

        # elementary / enum / address
        if isinstance(var_obj, Variables) or isinstance(var_obj, EnumVariable):
            out[prefix] = _serialize_val(val)
            return

        # array
        if isinstance(var_obj, ArrayVariable):
            for idx, elem in enumerate(var_obj.elements):
                self._flatten_var(elem, f"{prefix}[{idx}]", out)
            return

        # struct
        if isinstance(var_obj, StructVariable):
            for m, mem_var in var_obj.members.items():
                self._flatten_var(mem_var, f"{prefix}.{m}", out)
            return

        # mapping
        if isinstance(var_obj, MappingVariable):
            for k, mv in var_obj.mapping.items():
                self._flatten_var(mv, f"{prefix}[{k}]", out)
            return

    def _record_analysis(
            self,
            line_no: int,
            stmt_type: str,
            env: dict[str, Variables] | None = None,
            expr: Expression | None = None,
            var_obj: Variables | None = None):
        """
        · env   → 여러 변수 snapshot(flat)
        · expr  → 지금 건드린 Expression 을 그대로 key 로
        · var_obj → expr 가 가리키는 Variables  (value 직렬화용)
        """
        def _serialize_val(v):
            if hasattr(v, 'min_value'):  # Interval · BoolInterval
                return f"[{v.min_value},{v.max_value}]"
            return str(v)

        # ───── ① 함수 본문 밖이면 아무것도 기록하지 않음 ─────
        if self.current_target_function is None:
            return

        line_info = {"kind": stmt_type}

        # A) 특정 식 하나만 기록
        if expr is not None and var_obj is not None:
            key = self._expr_to_str(expr)

            # ── (a) 단일 값(e.g., uint, bool, enum, address …)
            if isinstance(var_obj, (Variables, EnumVariable)):
                line_info["vars"] = {key: _serialize_val(getattr(var_obj, "value", None))}

            # ── (b) 배열 / 구조체 / 매핑 → 재귀로 평탄화
            else:  # ArrayVariable | StructVariable | MappingVariable
                flat = {}
                self._flatten_var(var_obj, key, flat)  # key 가 루트 prefix 가 됨
                line_info["vars"] = flat

        # B) 환경 전체(flatten)
        elif env is not None:
            flat = {}
            for v in env.values():
                self._flatten_var(v, v.identifier, flat)
            line_info["vars"] = flat

        self.analysis_per_line[line_no].append(line_info)

        # Analyzer/ContractAnalyzer.py  (끝부분쯤)

    # 신규 ▶  방금 추가된 라인(들)의 분석 결과를 돌려주는 작은 헬퍼
    def get_line_analysis(self, start_ln: int, end_ln: int) -> dict[int, list[dict]]:
        """
        [start_ln, end_ln] 구간에 대해
        { line_no: [ {kind: ..., vars:{...}}, ... ], ... }  형태 반환
        (구간 안에 기록이 없으면 key 자체가 없다)
        """
        return {
            ln: self.analysis_per_line[ln]
            for ln in range(start_ln, end_ln + 1)
            if ln in self.analysis_per_line
        }

