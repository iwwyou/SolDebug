# SolidityGuardian/Analyzers/ContractAnalyzer.py
from collections import deque
from Utils.CFG import *
from solcx import (
    install_solc,
    set_solc_version,
    compile_source,
    get_installed_solc_versions
)
from solcx.exceptions import SolcError
from Domain.Address import *
from Utils.Helper import *
from Utils.Snapshot import *
from Analyzer.DynamicCFGBuilder import DynamicCFGBuilder
from Analyzer.RecordManager import RecordManager
from Analyzer.StaticCFGFactory import StaticCFGFactory
from Interpreter.Semantics.Evaluation import Evaluation
from Interpreter.Semantics.Update import Update
from Interpreter.Semantics.Refine import Refine
from Interpreter.Semantics.Runtime import Runtime
from Interpreter.Engine import Engine

class ContractAnalyzer:

    def __init__(self):
        self.sm = AddressSymbolicManager()
        self.snapman = SnapshotManager()
        self._batch_targets: set[FunctionCFG] = set()  # 🔹추가

        self.full_code = None
        self.full_code_lines = {} # 라인별 코드를 저장하는 딕셔너리
        self.line_info = {} # 각 라인에서 `{`와 `}`의 개수를 저장하는 딕셔너리

        self.current_start_line = None
        self.current_end_line = None

        self.current_context_type = None
        self.current_target_contract = None
        self.current_target_function = None
        self.current_target_function_cfg = None
        self.current_target_struct = None

        self.current_edit_event = None
        self._record_enabled = False
        self._seen_stmt_ids: set[int] = set()

        # for Multiple Contract
        self.contract_cfgs = {} # name -> CFG

        self.evaluator = Evaluation(self)
        self.updater = Update(self)
        self.refiner = Refine(self)
        self.runtime = Runtime(self)
        self.engine = Engine(self)
        self.builder = DynamicCFGBuilder(self)
        self.recorder = RecordManager()

        self.analysis_per_line = self.recorder.ledger

    """
    Prev analysis part
    """

    # ────────────────────────────────────────────────────────────────
    #  ContractAnalyzer   (class body 안)
    # ----------------------------------------------------------------
    def _shift_meta(self, old_ln: int, new_ln: int):
        """
        소스 라인 이동(old_ln → new_ln)에 맞춰
        brace_count / analysis_per_line / Statement.src_line  를 모두 동기화
        """
        # ① brace_count · analysis_per_line
        for d in (self.line_info, self.analysis_per_line):
            if old_ln in d:
                d[new_ln] = d.pop(old_ln)

        # ② 이미 생성된 CFG-Statement 들의 src_line 보정
        for ccf in self.contract_cfgs.values():
            for fcfg in ccf.functions.values():
                for blk in fcfg.graph.nodes:
                    for st in blk.statements:
                        if getattr(st, "src_line", None) == old_ln:
                            st.src_line = new_ln

    def _insert_lines(self, start: int, new_lines: list[str]):
        offset = len(new_lines)

        # ① 뒤 라인 밀기 (내림차순)
        for old_ln in sorted([ln for ln in self.full_code_lines if ln >= start],
                             reverse=True):
            self.full_code_lines[old_ln + offset] = self.full_code_lines.pop(old_ln)
            self._shift_meta(old_ln, old_ln + offset)  # ★

        # ② 새 코드 삽입
        for i, ln in enumerate(range(start, start + offset)):
            self.full_code_lines[ln] = new_lines[i]
            self.update_brace_count(ln, new_lines[i])

    def update_code(self,
                    start_line: int,
                    end_line: int,
                    new_code: str,
                    event: str):
        """
        event ∈  {"add", "modify", "delete"}

        • add     :  기존 로직 (뒤를 밀고 새 줄 삽입)
        • modify  :  같은 줄 범위를 *덮어쓰기*  (라인 수는 유지)
        • delete  :  먼저  analyse_context → 그 다음 완전히 없애고 뒤를 당김
        """

        # ──────────────────────────────────────────────────────────
        # ① 사전 준비
        # ----------------------------------------------------------
        self.current_start_line = start_line
        self.current_end_line = end_line
        self.current_edit_event = event
        lines = new_code.split("\n")  # add / modify 용

        if event not in {"add", "modify", "delete"}:
            raise ValueError(f"unknown event '{event}'")

        # ──────────────────────────────────────────────────────────
        # ② event별 분기
        # ----------------------------------------------------------
        if event == "add":
            self._insert_lines(start_line, lines)  # ← 종전 알고리즘

        elif event == "modify":
            # (1) 새 코드 줄 리스트
            new_lines = new_code.split("\n")
            # (2) ① 줄 수가 같지 않다면 → delete + add 로 fallback
            if (end_line - start_line + 1) != len(new_lines):
                self.update_code(start_line, end_line, "", event="delete")
                # add (line 수가 달라졌으므로 뒤쪽을 밀어냄)
                self.update_code(start_line, start_line + len(new_lines) - 1,
                                 new_code, event="add")
                return

            # (3) ② 줄 수가 동일 → **덮어쓰기** 만 수행
            ln = start_line
            for line in new_lines:
                # full-code 버퍼 교체
                self.full_code_lines[ln] = line
                # 바로 context 분석
                self.analyze_context(ln, line)
                ln += 1

        elif event == "delete":
            offset = end_line - start_line + 1
            # A.  삭제 전 rollback (종전 그대로)  …
            # B-1.  메타데이터 pop
            for ln in range(start_line, end_line + 1):
                self.full_code_lines.pop(ln, None)
                self.line_info.pop(ln, None)
                self.analysis_per_line.pop(ln, None)
            # B-2.  뒤쪽 라인을 앞으로 당김
            keys_to_shift = sorted(
                [ln for ln in self.full_code_lines if ln > end_line]
            )

            for old_ln in keys_to_shift:
                new_ln = old_ln - offset
                self.full_code_lines[new_ln] = self.full_code_lines.pop(old_ln)
                self._shift_meta(old_ln, new_ln)  # ★

        # ──────────────────────────────────────────────────────────
        # ③ full-code 재조합 & optional compile check
        # ----------------------------------------------------------
        self.full_code = "\n".join(
            self.full_code_lines[ln] for ln in sorted(self.full_code_lines)
        )

        # add / modify 는 새 코드를 바로 분석
        if event in {"add", "modify"} and new_code.strip():
            self.analyze_context(start_line, new_code)

        # 실험 코드라면 컴파일 생략 가능
        # self.compile_check()

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
        info = self.line_info.get(line_number, {})
        info['open'] = open_braces
        info['close'] = close_braces
        # 호환성 필드들 보장
        info.setdefault('cfg_nodes', [])
        info.setdefault('cfg_node', None)
        self.line_info[line_number] = info

    def analyze_context(self, start_line, new_code):
        stripped_code = new_code.strip()

        if stripped_code.startswith('// @'):
            self.current_context_type = "debugUnit"
            self.current_target_contract = self.find_contract_context(start_line)
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
            if parent_context in ["contract", "library", "interface",
                                  "abstract contract"]:  # 시작 규칙 : interactiveSourceUnit
                if 'constant' in stripped_code or 'immutable' in stripped_code:
                    self.current_context_type = "constantVariableDeclaration"
                else:
                    self.current_context_type = "stateVariableDeclaration"
                self.current_target_contract = self.find_contract_context(start_line)
            elif parent_context == "struct":  # 시작 규칙 : interactiveStructUnit
                self.current_context_type = "structMember"
                self.current_target_contract = self.find_contract_context(start_line)
                self.current_target_struct = self.find_struct_context(start_line)
            else:  # constructor, function, --- # 시작 규칙 : interactiveBlockUnit
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
            self.current_target_contract = self.find_contract_context(start_line)

            if self.current_context_type in ["contract", "library", "interface", "abstract contract"]:
                return

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
            brace_info = self.line_info.get(line, {'open': 0, 'close': 0, 'cfg_node': None})
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
            brace_info = self.line_info.get(line, {'open': 0, 'close': 0, 'cfg_node': None})
            if brace_info['open'] > 0 and brace_info['cfg_node']:
                context_type = self.determine_top_level_context(self.full_code_lines[line])
                if context_type == "contract":
                    return self.full_code_lines[line].split()[1]  # contract 이름 반환
        return None

    def find_function_context(self, line_number):
        # 위로 거슬러 올라가면서 해당 라인이 속한 함수를 찾습니다.
        for line in range(line_number, 0, -1):
            brace_info = self.line_info.get(line, {'open': 0, 'close': 0, 'cfg_node': None})
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
            brace_info = self.line_info.get(line, {'open': 0, 'close': 0, 'cfg_node': None})
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
        self.current_target_contract = contract_name
        cfg = StaticCFGFactory.make_contract_cfg(self, contract_name)

        self.line_info[self.current_start_line]['cfg_node'] = cfg

    # for interactiveEnumDefinition in Solidity.g4
    def process_enum_definition(self, enum_name):
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 새로운 EnumDefinition 객체 생성
        enum_def = EnumDefinition(enum_name)
        contract_cfg.define_enum(enum_name, enum_def)

        # brace_count 업데이트
        self.line_info[self.current_start_line]['cfg_node'] = enum_def

    def process_enum_item(self, items):
        # 현재 타겟 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)

        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # brace_count에서 가장 최근의 enum 정의를 찾습니다.
        enum_def = None
        for line in reversed(range(self.current_start_line + 1)):
            context = self.line_info.get(line)
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
        self.line_info[self.current_start_line]['cfg_node'] = contract_cfg.structDefs

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
                    variable_obj.initialize_not_abstracted_type()
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
                    variable_obj.value = self.evaluator.calculate_default_interval(et)
                elif et == "address":
                    # 초기화식이 없으면 전체 주소 공간으로 보수적으로 설정
                    variable_obj.value = UnsignedIntegerInterval(0, 2 ** 160 - 1, 160)

                # (string / bytes 등 - 추상화 안 할 타입은 심볼릭 문자열 그대로)
                else:
                    variable_obj.value = f"symbol_{variable_obj.identifier}"
        else : # 초기화 식이 있으면
            if isinstance(variable_obj, ArrayVariable) :
                inlineArrayValues = self.evaluator.evaluate_expression(
                    init_expr,
                    contract_cfg.state_variable_node.variables,
                    None,
                    None)

                for value in inlineArrayValues :
                    variable_obj.elements.append(value)
            elif isinstance(variable_obj, StructVariable) : # 관련된 경우 없을듯
                pass
            elif isinstance(variable_obj, MappingVariable) : # 관련된 경우 없을 듯
                pass
            elif variable_obj.typeInfo.typeCategory == "elementary" :
                variable_obj.value = self.evaluator.evaluate_expression(
                    init_expr,
                    contract_cfg.state_variable_node.variables,
                    None,
                    None)

        self.register_var(variable_obj)

        # 4. 상태 변수를 ContractCFG에 추가
        contract_cfg.add_state_variable(variable_obj, expr=init_expr, line_no=self.current_start_line)

        # 5. ContractCFG에 있는 모든 FunctionCFG에 상태 변수 추가
        for function_cfg in contract_cfg.functions.values():
            function_cfg.add_related_variable(variable_obj.identifier, variable_obj)

        # 6. contract_cfg를 contract_cfgs에 반영
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 7. brace_count 업데이트
        self.line_info[self.current_start_line]['cfg_node'] = contract_cfg.state_variable_node

    # ---------------------------------------------------------------------------
    # ② constant 변수 처리 (CFG·심볼 테이블 반영)
    # ---------------------------------------------------------------------------
    def process_constant_variable(self, variable_obj, init_expr):
        # 1. 컨트랙트 CFG 확보
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if contract_cfg is None:
            raise ValueError(f"Unable to find contract CFG for {self.current_target_contract}")

        # 2. 반드시 초기화식이 있어야 함 (constant 변수는 항상 초기화 필요)
        if init_expr is None:
            raise ValueError(f"Constant variable '{variable_obj.identifier}' must have an initializer.")

        # 3. constant로 선언 불가능한 타입 검증
        if isinstance(variable_obj, (ArrayVariable, StructVariable, MappingVariable)):
            type_name = type(variable_obj).__name__.replace('Variable', '').lower()
            raise ValueError(
                f"{type_name.capitalize()} variables cannot be declared as constant: '{variable_obj.identifier}'")

        if not contract_cfg.state_variable_node:
            contract_cfg.initialize_state_variable_node()

        # 4. 평가 컨텍스트는 현재까지의 state-variable 노드 변수들
        state_vars = contract_cfg.state_variable_node.variables

        # 5. constant 표현식 평가 (value types와 string만 지원)
        if isinstance(variable_obj, EnumVariable):
            # 열거형도 value type이므로 지원
            value = self.evaluator.evaluate_expression(init_expr, state_vars, None, None)
            if value is None:
                raise ValueError(f"Unable to evaluate constant enum expression for '{variable_obj.identifier}'")
            variable_obj.value = value
        elif variable_obj.typeInfo.typeCategory == "elementary":
            # value types (int, uint, bool, address 등)과 string 지원
            et = variable_obj.typeInfo.elementaryTypeName
            if et in ["string", "bytes"] or et.startswith(("int", "uint", "bool")) or et == "address":
                value = self.evaluator.evaluate_expression(init_expr, state_vars, None, None)
                if value is None:
                    raise ValueError(f"Unable to evaluate constant expression for '{variable_obj.identifier}'")
                variable_obj.value = value
            else:
                raise ValueError(f"Type '{et}' cannot be declared as constant: '{variable_obj.identifier}'")
        else:
            # 기타 지원되지 않는 타입
            raise ValueError(
                f"Type category '{variable_obj.typeInfo.typeCategory}' cannot be declared as constant: '{variable_obj.identifier}'")

        variable_obj.isConstant = True  # constant 플래그 설정

        self.register_var(variable_obj)

        # 3. ContractCFG 에 추가 (state 변수와 동일 API 사용)
        contract_cfg.add_state_variable(variable_obj, expr=init_expr, line_no=self.current_start_line)

        # 4. 이미 생성된 모든 FunctionCFG 에 read-only 변수로 연동
        for fn_cfg in contract_cfg.functions.values():
            fn_cfg.add_related_variable(variable_obj.identifier, variable_obj)

        # 5. 전역 map 업데이트
        self.contract_cfgs[self.current_target_contract] = contract_cfg

        # 6. brace_count 갱신 → IDE/커서 매핑
        self.line_info[self.current_start_line]["cfg_node"] = contract_cfg.state_variable_node

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

        mod_cfg = StaticCFGFactory.make_modifier_cfg(self, contract_cfg, modifier_name, parameters)

        # 3) CFG 저장
        self.line_info[self.current_start_line]['cfg_node'] = mod_cfg.get_entry_node()

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
        if modifier_name not in contract_cfg.functions:
            raise ValueError(f"Modifier '{modifier_name}' is not defined.")

        mod_cfg: FunctionCFG = contract_cfg.functions[modifier_name]

        self.builder.splice_modifier(fn_cfg, mod_cfg, modifier_name)

    def process_constructor_definition(self, name, params, modifiers):
        ccf = self.contract_cfgs[self.current_target_contract]

        ctor_cfg = StaticCFGFactory.make_constructor_cfg(
            self, name, params, modifiers
        )
        ccf.add_constructor_to_cfg(ctor_cfg)
        self.contract_cfgs[self.current_target_contract] = ccf

        # brace_count - 디폴트 entry 등록
        self.line_info[self.current_start_line]["cfg_node"] = ctor_cfg.get_entry_node()

    # ContractAnalyzer.py  ─ process_function_definition  (address-symb ✚ 최신 Array/Struct 초기화 반영)

    def process_function_definition(
            self,
            function_name: str,
            parameters: list[tuple[SolType, str]],
            modifiers: list[str],
            returns: list[Variables] | None,
    ):
        contract_cfg = self.contract_cfgs[self.current_target_contract]
        if contract_cfg is None:
            raise ValueError(f"Contract CFG for {self.current_target_contract} not found.")

        fcfg = StaticCFGFactory.make_function_cfg(self, function_name, parameters, modifiers, returns)

        contract_cfg.functions[function_name] = fcfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg
        self.line_info[self.current_start_line]["cfg_node"] = fcfg.get_entry_node()
        self.line_info[self.current_end_line]["cfg_node"] = fcfg.get_exit_node()

    def process_variable_declaration(
            self,
            type_obj: SolType,
            var_name: str,
            init_expr: Expression | None = None
    ):

        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("variableDeclaration: active FunctionCFG not found")

        cur_blk = self.builder.get_current_block()

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
                        v.initialize_not_abstracted_type()

            # ── 구조체 기본
            elif isinstance(v, StructVariable):
                if v.typeInfo.structTypeName not in ccf.structDefs:
                    raise ValueError(f"Undefined struct {v.typeInfo.structTypeName}")
                v.initialize_struct(ccf.structDefs[v.typeInfo.structTypeName])

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
                    v.value = AddressSymbolicManager.top_interval()
                else:  # bytes/string
                    v.value = f"symbol_{var_name}"

        # ───────────────────────────────────────────────────────────────
        # 3-b. 초기화식이 존재하는 경우
        # ----------------------------------------------------------------
        else:
            resolved = self.evaluator.evaluate_expression(init_expr,
                                                cur_blk.variables, None, None)

            # ───────────────────── 구조체 / 배열 / 매핑 ─────────────────────
            if isinstance(resolved, (StructVariable, ArrayVariable, MappingVariable)):
                v = VariableEnv.deep_clone_variable(resolved, var_name)  # ★ 새 객체 생성

            # ───────────────────── enum 초기화 ─────────────────────────────
            elif isinstance(v, EnumVariable):
                enum_def = ccf.enumDefs.get(v.typeInfo.enumTypeName)
                if enum_def is None:
                    raise ValueError(f"undefined enum {v.typeInfo.enumTypeName}")

                if isinstance(resolved, EnumVariable):
                    v.valueIndex = resolved.valueIndex
                    v.value = resolved.value
                elif isinstance(resolved, str) and not resolved.isdigit():
                    member = resolved.split('.')[-1]
                    v.valueIndex = enum_def.members.index(member)
                    v.value = member
                else:  # 숫자 또는 digit 문자열
                    idx = int(resolved, 0)
                    v.valueIndex = idx
                    v.value = enum_def.members[idx]

            # ───────────────────── 나머지(기존 로직) ─────────────────────
            else:
                if isinstance(v, ArrayVariable):
                    for e in resolved:
                        v.elements.append(e)
                elif isinstance(v, Variables):
                    v.value = resolved
                elif isinstance(v, StructVariable) and isinstance(resolved, StructVariable):
                    v.copy_from(resolved)

            # ────────────────── ③ CFG-빌더 / 레코더 위임 ─────────
            #    · 그래프/노드 업데이트는 cfg_builder에게
            #    · 분석 기록은 rec_mgr 에게
            self.builder.build_variable_declaration(
                cur_block=cur_blk,
                var_obj=v,
                type_obj=type_obj,
                init_expr=init_expr,
                line_no=self.current_start_line,
                fcfg=self.current_target_function_cfg,
                line_info=self.line_info,  # ← builder가 필요하다면 전달
            )

            self.recorder.record_variable_declaration(
                line_no=self.current_start_line,
                var_name=var_name,
                var_obj=v,
            )

            # ────────────────── ④ 저장 & 정리 ────────────────────
            ccf.functions[self.current_target_function] = self.current_target_function_cfg
            self.contract_cfgs[self.current_target_contract] = ccf
            self.current_target_function_cfg = None

    # Analyzer/ContractAnalyzer.py
    def process_assignment_expression(self, expr: Expression) -> None:
        # 1. CFG 컨텍스트 --------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active function CFG.")

        cur_blk = self.builder.get_current_block()

        # 2. 값 해석 + 변수 갱신  -----------------------------------------
        r_val = self.evaluator.evaluate_expression(
            expr.right, cur_blk.variables, None, None
        )

        self.updater.update_left_var(
            expr.left,
            r_val,
            expr.operator,
            cur_blk.variables,
            None, None, True
        )

        # 3. CFG 노드/엣지 정리  -----------------------------------------
        self.builder.build_assignment_statement(
            cur_block=cur_blk,
            expr=expr,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # 4. constructor 특수 처리 & 저장 -------------------------------
        if self.current_target_function_cfg.function_type == "constructor":
            state_vars = ccf.state_variable_node.variables

            # ③ scope=='state' 인 항목을 그대로 복사해 덮어쓰기
            for name, var in state_vars.items():
                if getattr(var, "scope", None) != "state":
                    continue
                state_vars[name] = VariableEnv.copy_variables({name: var})[name]

        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # --------------------------------------------------------------
    #  ++x / --x   (prefix·suffix 공통)
    # --------------------------------------------------------------
    def handle_unary_incdec(self, expr: Expression,
                             op_sign: str,  # "+=" | "-="
                             stmt_kind: str):  # "unary_prefix" | "unary_suffix"
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("active FunctionCFG not found")

        cur_blk = self.builder.get_current_block()

        # ① 현재 값 읽기 → 타입에 맞는 “1” Interval 준비 -------------
        cur_val = self.evaluator.evaluate_expression(
            expr, cur_blk.variables, None, None)

        if isinstance(cur_val, UnsignedIntegerInterval):
            one = UnsignedIntegerInterval(1, 1, cur_val.type_length)
        elif isinstance(cur_val, IntegerInterval):
            one = IntegerInterval(1, 1, cur_val.type_length)
        elif isinstance(cur_val, BoolInterval):
            one = BoolInterval(1, 1)  # 거의 안 쓰임 – 방어 코드
        else:
            raise ValueError(f"unsupported ++/-- type {type(cur_val).__name__}")

        # ② 실제 값 패치 (+ Recorder 자동 기록) -----------------------
        self.updater.update_left_var(
            expr, one, op_sign, cur_blk.variables, None, None, True
        )

        # ③ CFG Statement 삽입 -------------------------------------
        self.builder.build_unary_statement(
            cur_block=cur_blk,
            expr=expr,
            op_token=stmt_kind,  # 기록용 토큰 – 원하면 '++' 등으로
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # ④ constructor 특수 처리 + 저장 ---------------------------
        if self.current_target_function_cfg.function_type == "constructor":
            state_vars = ccf.state_variable_node.variables

            # ③ scope=='state' 인 항목을 그대로 복사해 덮어쓰기
            for name, var in state_vars.items():
                if getattr(var, "scope", None) != "state":
                    continue
                state_vars[name] = VariableEnv.copy_variables({name: var})[name]

        self.current_target_function_cfg.update_block(cur_blk)
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # --------------------------------------------------------------
    #  delete <expr>
    # --------------------------------------------------------------
    def handle_delete(self, target_expr: Expression):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("active FunctionCFG not found")

        cur_blk = self.builder.get_current_block()
        vars_env = cur_blk.variables

        # ① 대상 객체 resolve  (update-free 버전)
        var_obj = self.updater.resolve_lhs_expr(target_expr, vars_env)
        if var_obj is None:
            raise ValueError("LHS cannot be resolved.")

        # ② 값 wipe  ----------------------------------------------
        def _wipe(obj):
            if isinstance(obj, MappingVariable):
                obj.mapping.clear()
            elif isinstance(obj, ArrayVariable):
                obj.elements.clear()
            elif isinstance(obj, StructVariable):
                for m in obj.members.values(): _wipe(m)
            elif isinstance(obj, EnumVariable):
                obj.value = IntegerInterval(0, 0, 256)
            elif isinstance(obj, Variables):
                et = getattr(obj.typeInfo, "elementaryTypeName", "")
                bit = getattr(obj.typeInfo, "intTypeLength", 256) or 256
                if et.startswith("uint"):
                    obj.value = UnsignedIntegerInterval(0, 0, bit)
                elif et.startswith("int"):
                    obj.value = IntegerInterval(0, 0, bit)
                elif et == "bool":
                    obj.value = BoolInterval(0, 0)
                elif et == "address":
                    obj.value = UnsignedIntegerInterval(0, 0, 160)
                else:
                    obj.value = f"symbolic_zero_{obj.identifier}"

        _wipe(var_obj)

        # ④ CFG Statement 삽입 & 저장 ------------------------------
        self.builder.build_unary_statement(
            cur_block=cur_blk,
            expr=target_expr,
            op_token="delete",
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        self.current_target_function_cfg.update_block(cur_blk)
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # ───────────────────────────────────────────────────────────
    def process_unary_prefix_operation(self, expr: Expression):
        if expr.operator == "++":
            self.handle_unary_incdec(expr.expression, "+=", "unary_prefix")
        elif expr.operator == "--":
            self.handle_unary_incdec(expr.expression, "-=", "unary_prefix")
        elif expr.operator == "delete":
            self.handle_delete(expr.expression)
        else:
            raise ValueError(f"Unsupported prefix operator {expr.operator}")

    def process_unary_suffix_operation(self, expr: Expression):
        if expr.operator == "++":
            self.handle_unary_incdec(expr.expression, "+=", "unary_suffix")
        elif expr.operator == "--":
            self.handle_unary_incdec(expr.expression, "-=", "unary_suffix")
        else:
            raise ValueError(f"Unsupported suffix operator {expr.operator}")

    # ==================================================================
    #  함수 호출 처리
    # ==================================================================
    # ==================================================================
    #  함수 호출 처리
    # ==================================================================
    def process_function_call(self, expr: Expression) -> None:
        # ① CFG 컨텍스트 -------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active function CFG.")

        cur_blk = self.builder.get_current_block()

        # ② 실제 호출 해석  ---------------------------------------------
        _ = self.evaluator.evaluate_function_call_context(
            expr,
            cur_blk.variables,
            None,
            None,
        )
        # (Evaluate → Update 경유로 변수 변화는 자동 기록됨)

        # ③ CFG 노드/엣지 정리  ----------------------------------------
        self.builder.build_function_call_statement(
            cur_block=cur_blk,
            expr=expr,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # ④ constructor 특수 처리  -------------------------------------
        if self.current_target_function_cfg.function_type == "constructor":
            state_vars = ccf.state_variable_node.variables
            # ‣ scope=='state' 인 항목만 deep-copy 로 덮어쓰기
            for name, var in state_vars.items():
                if getattr(var, "scope", None) != "state":
                    continue
                state_vars[name] = VariableEnv.copy_variables({name: var})[name]

        # ⑤ CFG 저장  ---------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_payable_function_call(self, expr):
        # Handle payable function calls
        pass

    def process_function_call_options(self, expr):
        # Handle function calls with options
        pass

    def process_if_statement(self, condition_expr: Expression) -> None:
        # ── 1. CFG 컨텍스트 ─────────────────────────────────────────────
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active function CFG.")

        cur_blk = self.builder.get_current_block()

        base_env = VariableEnv.copy_variables(cur_blk.variables)
        true_env   = VariableEnv.copy_variables(base_env)
        false_env  = VariableEnv.copy_variables(base_env)

        self.refiner.update_variables_with_condition(true_env, condition_expr, True)
        self.refiner.update_variables_with_condition(false_env, condition_expr, False)

        true_delta = VariableEnv.diff_changed(base_env, true_env)

        if true_delta:  # 아무것도 안 바뀌면 기록 생략
            self.recorder.add_env_record(
                 line_no = self.current_start_line,
                 stmt_type = "branchTrue",
                 env = true_delta,
            )

        # ── 3. 그래프에 if-구조 삽입  ➜ DynamicCFGBuilder 위임 ──────────
        self.builder.build_if_statement(
            cur_block=cur_blk,
            condition_expr=condition_expr,
            true_env=true_env,
            false_env=false_env,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # ── 4. 저장 & 마무리 ───────────────────────────────────────────
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_else_if_statement(self, condition_expr: Expression) -> None:
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active function CFG.")
        prev_cond = self.builder.find_corresponding_condition_node()
        if prev_cond is None:
            raise ValueError("else-if used without a preceding if/else-if.")

        # --- 현재 false-분기로 내려온 변수 env --------------------
        false_base_env = VariableEnv.copy_variables(prev_cond.variables)
        self.refiner.update_variables_with_condition(
            false_base_env, prev_cond.condition_expr, is_true_branch=False
        )

        # --- 새 true/false env ------------------------------------
        base_env = VariableEnv.copy_variables(false_base_env)
        true_env = VariableEnv.copy_variables(base_env)
        false_env = VariableEnv.copy_variables(base_env)
        self.refiner.update_variables_with_condition(true_env, condition_expr, True)
        self.refiner.update_variables_with_condition(false_env, condition_expr, False)

        true_delta = VariableEnv.diff_changed(base_env, true_env)

        if true_delta:  # 아무것도 안 바뀌면 기록 생략
            self.recorder.add_env_record(
                line_no=self.current_start_line,
                stmt_type="branchTrue",
                env=true_delta,
            )

        # --- 그래프 삽입 ------------------------------------------
        cur_blk_dummy = CFGNode("ELSE_FALSE_TMP")  # false-dummy 역할
        cur_blk_dummy.variables = false_base_env
        # (그래프에 넣진 않고 env 복사 용도로만 사용)

        self.builder.build_else_if_statement(
            prev_cond=prev_cond,
            condition_expr=condition_expr,
            cur_block=cur_blk_dummy,
            true_env=true_env,
            false_env=false_env,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # 저장
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_else_statement(self) -> None:
        # ── 1. CFG 컨텍스트 --------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'else'.")

        # ── 2. 직전 if / else-if 노드 찾기 -----------------------------------
        cond_node = self.builder.find_corresponding_condition_node()
        if cond_node is None:
            raise ValueError("No preceding if/else-if for this 'else'.")

        # ── 3. else 분기용 변수-환경 생성 ------------------------------------
        base_env = VariableEnv.copy_variables(cond_node.variables)
        else_env = VariableEnv.copy_variables(base_env)
        self.refiner.update_variables_with_condition(
            else_env, cond_node.condition_expr, is_true_branch=False
        )

        true_delta = VariableEnv.diff_changed(base_env, else_env)

        if true_delta:  # 아무것도 안 바뀌면 기록 생략
            self.recorder.add_env_record(
                line_no=self.current_start_line,
                stmt_type="branchTrue",
                env=true_delta,
            )

        # ── 4. 그래프 작업은 Builder 에 위임 -------------------------------
        self.builder.build_else_statement(
            cond_node=cond_node,
            else_env=else_env,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # ── 5. 저장 ----------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_while_statement(self, condition_expr: Expression) -> None:
        # 1. CFG 컨텍스트 ---------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active function CFG.")

        cur_blk = self.builder.get_current_block()

        # 2. 분기별 변수 환경 ----------------------------------------------
        join_env = VariableEnv.copy_variables(cur_blk.variables)

        true_env = VariableEnv.copy_variables(join_env)
        false_env = VariableEnv.copy_variables(join_env)

        self.refiner.update_variables_with_condition(true_env, condition_expr, True)
        self.refiner.update_variables_with_condition(false_env, condition_expr, False)

        # 3. 그래프 구축은 Builder 에 위임 -------------------------------
        self.builder.build_while_statement(
            cur_block=cur_blk,
            condition_expr=condition_expr,
            join_env=join_env,
            true_env=true_env,
            false_env=false_env,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # 4. 저장 ----------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_for_statement(
            self,
            initial_statement: dict | None = None,
            condition_expr: Expression | None = None,
            increment_expr: Expression | None = None,
    ) -> None:
        # 1. CFG 컨텍스트 --------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active function CFG.")

        cur_blk = self.builder.get_current_block()

        # 2. ─────── init-노드 (있을 때만)  &  변수 환경 --------------------
        init_node: CFGNode | None = None

        if initial_statement:
            ctx = initial_statement["context"]

            init_node = CFGNode(f"for_init_{self.current_start_line}")
            init_node.variables = VariableEnv.copy_variables(cur_blk.variables)

            if ctx == "VariableDeclaration":
                v_type = initial_statement["initVarType"]
                v_name = initial_statement["initVarName"]
                init_expr = initial_statement["initValExpr"]

                # 값 해석 + 실제 변수 갱신
                if init_expr is not None:
                    r_val = self.evaluator.evaluate_expression(
                        init_expr, init_node.variables, None, None
                    )
                else:
                    r_val = None

                # 변수 객체 생성 & env 삽입
                v_obj = Variables(identifier=v_name, scope="local")
                v_obj.typeInfo = v_type
                if r_val is not None:
                    v_obj.value = r_val
                init_node.variables[v_name] = v_obj

                # CFG Statement
                init_node.add_variable_declaration_statement(
                    v_type, v_name, init_expr, self.current_start_line
                )

            elif ctx == "Expression":
                assn_expr = initial_statement["initExpr"]  # Assignment 식
                r_val = self.evaluator.evaluate_expression(
                    assn_expr.right, init_node.variables, None, None
                )
                # Update 내부에서 기록까지 수행
                self.updater.update_left_var(
                    assn_expr, r_val, assn_expr.operator, init_node.variables, None, None, False
                )
                # CFG Statement
                init_node.add_assign_statement(
                    assn_expr.left, assn_expr.operator, assn_expr.right,
                    self.current_start_line,
                )
            else:
                raise ValueError(f"[for] unknown init ctx '{ctx}'")

        # 3. ─────── 분기용 변수-환경 (join / true / false) ----------------
        join_env = VariableEnv.copy_variables(init_node.variables if init_node else cur_blk.variables)

        true_env = VariableEnv.copy_variables(join_env)
        false_env = VariableEnv.copy_variables(join_env)

        if condition_expr is not None:
            self.refiner.update_variables_with_condition(true_env, condition_expr, True)
            self.refiner.update_variables_with_condition(false_env, condition_expr, False)

        incr_node: CFGNode | None = None
        if increment_expr is not None:
            incr_node = CFGNode(f"for_incr_{self.current_start_line}",
                                is_for_increment=True)
            incr_node.variables = VariableEnv.copy_variables(true_env)

            # ---- ++ / -- --------------------------------------
            if increment_expr.operator in {"++", "--"}:
                # (1) 변수 환경에 즉시 반영
                one = UnsignedIntegerInterval(1, 1, 256)
                self.updater.update_left_var(
                    increment_expr.expression,  # i
                    one,
                    "+=" if increment_expr.operator == "++" else "-=",
                    incr_node.variables, None, None, False
                )
                # (2) **단항 스테이트먼트**로 기록
                incr_node.add_unary_statement(
                    operand=increment_expr.expression,  # 전체 i++ 식
                    operator=increment_expr.operator,  # '++' or '--'
                    line_no=self.current_start_line,
                )

            # ---- 복합 대입( += n / -= n … ) --------------------
            else:
                r_val = self.evaluator.evaluate_expression(
                    increment_expr.right, incr_node.variables)
                op = increment_expr.operator
                self.updater.update_left_var(
                    increment_expr.left, r_val, op, incr_node.variables, None, None, False)
                incr_node.add_assign_statement(
                    increment_expr.left, op, increment_expr.right,
                    self.current_start_line)

        # 5. ─────── 그래프 구성은 Builder 에 위임 ------------------------
        self.builder.build_for_statement(
            cur_block=cur_blk,
            init_node=init_node,
            join_env=join_env,
            cond_expr=condition_expr,
            true_env=true_env,
            false_env=false_env,
            incr_node=incr_node,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # 6. 저장 ---------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_continue_statement(self) -> None:
        # 1) CFG 컨텍스트
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'continue'.")

        # 2) 현재 블록
        cur_blk = self.builder.get_current_block()

        # 3) 그래프 처리 → Builder 에 위임
        self.builder.build_continue_statement(
            cur_block=cur_blk,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # 5) 저장
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_break_statement(self) -> None:
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'break'.")

        cur_blk = self.builder.get_current_block()

        self.builder.build_break_statement(
            cur_block=cur_blk,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py
    def process_return_statement(self, return_expr: Expression | None = None) -> None:
        # ── 1. CFG 컨텍스트 -------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'return'.")

        cur_blk = self.builder.get_current_block()

        # ── 2. 값 평가 ------------------------------------------------------
        r_val = None
        if return_expr is not None:
            r_val = self.evaluator.evaluate_expression(
                return_expr, cur_blk.variables, None, None
            )

        # ── 3. 그래프 & statement 구축  → builder 위임 ---------------------
        self.builder.build_return_statement(
            cur_block=cur_blk,
            return_expr=return_expr,
            return_val=r_val,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # ── 4. 기록 ---------------------------------------------------------
        self.recorder.record_return(
            line_no=self.current_start_line,
            return_expr=return_expr,
            return_val=r_val,
            fn_cfg=self.current_target_function_cfg,
        )

        # ── 5. CFG 저장 -----------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py
    def process_revert_statement(
            self,
            revert_identifier: str | None = None,
            string_literal: str | None = None,
            call_argument_list: list[Expression] | None = None,
    ) -> None:
        # ── 1. CFG context ---------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'revert'.")

        cur_blk = self.builder.get_current_block()

        # ── 2. graph / statement  → builder ---------------------------------
        self.builder.build_revert_statement(
            cur_block=cur_blk,
            revert_id=revert_identifier,
            string_literal=string_literal,
            call_args=call_argument_list,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # ── 3. analysis record ----------------------------------------------
        self.recorder.record_revert(
            line_no=self.current_start_line,
            revert_id=revert_identifier,
            string_literal=string_literal,
            call_args=call_argument_list,
        )

        # ── 4. save CFG ------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py
    def process_require_statement(
            self,
            condition_expr: Expression,
            string_literal: str | None,
    ) -> None:
        # 1) CFG context -----------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG.")

        cur_blk = self.builder.get_current_block()

        # 2) True-branch 환경 ------------------------------------------------
        base_env = VariableEnv.copy_variables(cur_blk.variables)
        true_env = VariableEnv.copy_variables(base_env)
        self.refiner.update_variables_with_condition(
            true_env, condition_expr, is_true_branch=True
        )

        true_delta = VariableEnv.diff_changed(base_env, true_env)

        if true_delta:  # 아무것도 안 바뀌면 기록 생략
            self.recorder.add_env_record(
                line_no=self.current_start_line,
                stmt_type="branchTrue",
                env=true_delta,
            )

        # 4) 그래프 구성 → builder ------------------------------------------
        self.builder.build_require_statement(
            cur_block=cur_blk,
            condition_expr=condition_expr,
            true_env=true_env,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # 5) 저장 ------------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # Analyzer/ContractAnalyzer.py
    def process_assert_statement(
            self,
            condition_expr: Expression,
            string_literal: str | None,
    ) -> None:
        # 1) CFG context -----------------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG.")

        cur_blk = self.builder.get_current_block()

        # 2) True-branch 환경(조건이 만족되는 경로) ---------------------------
        base_env = VariableEnv.copy_variables(cur_blk.variables)
        true_env = VariableEnv.copy_variables(base_env)
        self.refiner.update_variables_with_condition(
            true_env, condition_expr, is_true_branch=True
        )

        true_delta = VariableEnv.diff_changed(base_env, true_env)

        if true_delta:  # 아무것도 안 바뀌면 기록 생략
            self.recorder.add_env_record(
                line_no=self.current_start_line,
                stmt_type="branchTrue",
                env=true_delta,
            )

        # 4) CFG 구성 ---------------------------------------------------------
        self.builder.build_assert_statement(
            cur_block=cur_blk,
            condition_expr=condition_expr,
            true_env=true_env,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # 5) 저장 -------------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    # ContractAnalyzer.py  (추가/수정)

    # Analyzer/ContractAnalyzer.py
    def process_identifier_expression(self, ident_expr: Expression) -> None:
        """
        · ident == '_'  and  현재 CFG 가 modifier 이면  placeholder 처리
          그렇지 않으면 그냥 식별자 평가(별도 로직).
        """
        ident = ident_expr.identifier
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)

        # ── modifier placeholder (‘_’) --------------------------------------
        if (ident == "_" and self.current_target_function_cfg
                and self.current_target_function_cfg.function_type == "modifier"):
            cur_blk = self.builder.get_current_block()

            # ⬇️  새 helper 호출
            self.builder.build_modifier_placeholder(
                cur_block=cur_blk,
                fcfg=self.current_target_function_cfg,
                line_no=self.current_start_line,
                line_info=self.line_info,
            )
            return  # 값-해석 없음

        # … 이하 “일반 identifier” 처리는 기존 로직 유지 …

    # Analyzer/ContractAnalyzer.py
    def process_unchecked_indicator(self) -> None:
        # ── 1. CFG 컨텍스트 --------------------------------------------
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("No active FunctionCFG when processing 'unchecked'.")

        # ── 2. 현재 블록, 빌더 호출 -------------------------------------
        cur_blk = self.builder.get_current_block()

        self.builder.build_unchecked_block(
            cur_block=cur_blk,
            line_no=self.current_start_line,
            fcfg=self.current_target_function_cfg,
            line_info=self.line_info,
        )

        # ── 3. 저장 ------------------------------------------------------
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf

    def process_do_statement(self):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        fcfg = self.current_target_function_cfg
        if not fcfg:
            raise ValueError("No current target function to attach do-while.")
        cur_block = self.builder.get_current_block() # cur block is prev
        self.builder.build_do_statement(cur_block=cur_block,
                                        line_no=self.current_start_line,
                                        fcfg=fcfg,
                                        line_info=self.line_info)

    def process_do_while_statement(self, condition_expr):
        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        fcfg = self.current_target_function_cfg
        if not fcfg:
            raise ValueError("No current target function to attach do-while.")
        cur_block = self.builder.get_current_block() # cur block is do entry

        self.builder.build_do_while_statement(do_entry=cur_block,
                                        while_line=self.current_start_line,
                                        fcfg=fcfg,
                                        condition_expr=condition_expr,
                                        line_info=self.line_info)


    def process_global_var_for_debug(self, gv_obj: GlobalVariable):
        """
        @GlobalVar …   처리
          • cfg.globals  갱신
          • FunctionCFG.related_variables  갱신
          •(주소형이면) AddressSymbolicManager 에 변수<->ID 바인딩
          • 영향을 받는 함수만 재해석
        """
        ev = self.current_edit_event
        cfg = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = cfg.get_function_cfg(self.current_target_function)

        # ── 등록이 처음이면 snapshot ⬇︎
        if gv_obj.identifier not in cfg.globals:
            gv_obj.default_value = gv_obj.value
            cfg.globals[gv_obj.identifier] = gv_obj
            self.snapman.register(gv_obj, self.ser)  # ★ 스냅

        g = cfg.globals[gv_obj.identifier]

        # ── add/modify ───────────────────────────────────────────
        if ev in ("add", "modify"):
            g.debug_override = gv_obj.value
            g.value = gv_obj.value

        # ── delete  → snapshot 복원 + override 해제 ───────────────
        elif ev == "delete":
            self.snapman.restore(g, self.de)  # ★ 롤백
            g.debug_override = None

        else:
            raise ValueError(f"unknown event {ev!r}")

        # ↳ 주소형이면 AddressSymbolicManager 에 기록
        if g.typeInfo.elementaryTypeName == "address" and isinstance(g.value, UnsignedIntegerInterval):
            iv = g.value
            if iv.min_value == iv.max_value:  # [N,N] 형식 ⇒ 고정 ID
                nid = iv.min_value
                self.sm.register_fixed_id(nid, iv)
                self.sm.bind_var(g.identifier, nid)

        self._batch_targets.add(self.current_target_function_cfg)

        self.current_target_function_cfg = None

    # ─────────────────────────────────────────────────────────────
    def process_state_var_for_debug(self, lhs_expr: Expression, value):
        ccf  = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("@StateVar must be inside a function.")

        self.updater.apply_debug_directive(
            scope="state",
            lhs_expr=lhs_expr,
            value=value,
            variables=self.current_target_function_cfg.related_variables,
            edit_event=self.current_edit_event,
        )

        # 함수 다시 해석하도록 배치
        self._batch_targets.add(self.current_target_function_cfg)

    # ------------------------------------------------------------------
    #  @LocalVar   debug 주석
    # ------------------------------------------------------------------
    def process_local_var_for_debug(self, lhs_expr: Expression, value):
        ccf  = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("@LocalVar must be inside a function.")

        self.updater.apply_debug_directive(
            scope="local",
            lhs_expr=lhs_expr,
            value=value,
            variables=self.current_target_function_cfg.related_variables,
            edit_event=self.current_edit_event,
        )

        self._batch_targets.add(self.current_target_function_cfg)

    def reinterpret_from(self, fcfg: "FunctionCFG", seed_or_seeds) -> None:
        """
        Re-interpret downstream from the given seed node(s).
        BFS worklist + in_queue(중복 삽입 방지) + change-driven 재큐잉.
          - 조건 선행자: edge 라벨(True/False) 기준 prune
          - 그 외 선행자: pred.variables 그대로 사용 (재해석 금지)
          - 루프 헤더: 필요 시 fixpoint; false-exit이 곧 함수 종료면 스킵
          - 종료 조건: WL 비면 끝 (sink 분리 가정)
        """
        G = fcfg.graph
        eng = self.engine
        ref = self.refiner

        # ---------- helpers ----------
        def _is_loop_head(n):
            return getattr(n, "condition_node", False) and \
                getattr(n, "condition_node_type", None) in {"while", "for", "doWhile"}

        def _false_succs(n):
            return [s for s in G.successors(n) if G[n][s].get("condition") is False]

        def _is_sink(n):
            if getattr(n, "function_exit_node", False): return True
            if getattr(n, "error_exit_node", False):    return True
            if getattr(n, "return_exit_node", False):   return True
            nm = getattr(n, "name", "")
            return nm in {"EXIT", "ERROR", "RETURN"}

        def _branch_feasible(env, cond_expr, want_true):
            return self.runtime._branch_feasible(env, cond_expr, want_true)

        def _edge_env_from_pred(pred, succ):
            """
            pred→succ 경계에서 쓸 pred의 out 준비.
            - 조건 pred: edge 라벨로 prune (infeasible면 None)
            - 그 외: pred.variables 그대로 사용 (재해석 금지)
            """
            base = VariableEnv.copy_variables(getattr(pred, "variables", {}) or {})

            if getattr(pred, "condition_node", False):
                cond_expr = getattr(pred, "condition_expr", None)
                ed = G.get_edge_data(pred, succ, default=None)
                if cond_expr is not None and ed and "condition" in ed:
                    want_true = bool(ed["condition"])
                    ref.update_variables_with_condition(base, cond_expr, want_true)
                    if not _branch_feasible(base, cond_expr, want_true):
                        return None
                return base

            # 기본/더미/JOIN/기타: out 그대로 사용
            return base

        def _compute_in(n):
            acc = None
            for p in G.predecessors(n):
                env_p = _edge_env_from_pred(p, n)
                if env_p is None:  # infeasible edge
                    continue
                acc = VariableEnv.join_variables_simple(acc, env_p)
            return acc or {}

        # (선택) seed 보정: 루프 본문에 NEW가 있으면 헤더도 seed에 추가
        def _augment_seeds_with_loop_headers(seeds):
            out = list(seeds)
            for s in seeds:
                try:
                    hdr = self.find_enclosing_loop_header(s, fcfg)
                except Exception:
                    hdr = None
                if hdr is not None:
                    out.append(hdr)
            return list(dict.fromkeys(out))

        # (선택) seed 정규화: 지배 시드 제거 (상위에서 하위 도달 가능하면 하위 제거)
        def _dominant_seeds(seeds):
            seeds = list(dict.fromkeys(seeds))
            seed_set = set(seeds)
            dominated = set()
            for a in seeds:
                q = deque([a])
                seen = {a}
                while q:
                    u = q.popleft()
                    for v in G.successors(u):
                        if v in seen or _is_sink(v): continue
                        seen.add(v)
                        q.append(v)
                        if v in seed_set and v != a:
                            dominated.add(v)
            return [s for s in seeds if s not in dominated]

        # ---------- worklist init ----------
        if isinstance(seed_or_seeds, (list, tuple, set)):
            seeds = list(seed_or_seeds)
        else:
            seeds = [seed_or_seeds]

        # 너와 합의한 보정(옵션) 적용
        seeds = _augment_seeds_with_loop_headers(seeds)
        seeds = _dominant_seeds(seeds)

        WL = deque()
        in_queue = set()  # "큐에 이미 있음"만 추적 (visited 금지)
        out_snapshot = {}  # 변화 감지용 (처음은 항상 변한 것으로 처리됨)

        for s in seeds:
            if not _is_sink(s) and s not in in_queue:
                WL.append(s)
                in_queue.add(s)

        # ---------- main loop (BFS) ----------
        while WL:
            n = WL.popleft()
            in_queue.discard(n)  # <- 여기서 반드시 풀어줘야 재큐잉 가능

            # 1) in[n]
            in_env = _compute_in(n)

            # 2) loop head → 필요 시 fixpoint
            if _is_loop_head(n):
                false_s = _false_succs(n)
                only_exit = (len(false_s) == 1 and _is_sink(false_s[0]))
                if not only_exit:
                    exit_node = eng.fixpoint(n)  # widen→narrow 포함
                    for s in G.successors(exit_node):
                        if not _is_sink(s) and s not in in_queue:
                            WL.append(s)
                            in_queue.add(s)
                else:
                    # false-exit이 곧 종료면 fixpoint 생략
                    for s in false_s:
                        if not _is_sink(s) and s not in in_queue:
                            WL.append(s)
                            in_queue.add(s)
                continue

            # 3) 전이 적용 (여기서 n.variables가 out으로 동기화)
            new_out = eng.transfer_function(n, in_env)
            n.variables = VariableEnv.copy_variables(new_out)

            # 4) 변화 감지
            changed = not VariableEnv.variables_equal(out_snapshot.get(n), new_out)
            out_snapshot[n] = VariableEnv.copy_variables(new_out)

            # 5) 변화 있을 때만 후속 큐잉
            if changed:
                for s in G.successors(n):
                    if not _is_sink(s) and s not in in_queue:
                        WL.append(s)
                        in_queue.add(s)

        # 끝. (sink는 succ이 없으므로 자연 종료)

    def find_enclosing_loop_header(self, node: CFGNode, fcfg: "FunctionCFG") -> CFGNode | None:
        G = fcfg.graph
        # 가까운 것 우선: src_line 차이가 작을수록 우선 (없으면 BFS 깊이)
        from collections import deque
        q = deque([node]);
        seen = {node}
        while q:
            u = q.popleft()
            for p in G.predecessors(u):
                if p in seen:
                    continue
                seen.add(p)
                # 루프 헤더 판정: condition_node & type in {while, for, doWhile}
                if getattr(p, "condition_node", False) and \
                        getattr(p, "condition_node_type", None) in {"while", "for", "doWhile"}:
                    return p
                q.append(p)
        return None

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

    def send_report_to_front(
            self,
            patched_lines: list[tuple[str, int, int]] | None = None
    ) -> None:

        # 0) ‘어떤 라인을 보여줄지’ 결정 ---------------------------
        touched: set[int] = set()

        # (A) 호출 측에서 주석 라인을 넘겨준 경우
        if patched_lines:
            for _code, s, e in patched_lines:
                touched.update(range(s, e + 1))

        # (B) 주석 라인을 안 받았거나, 비어 있다면
        #     ⇢ 방금 재-해석한 함수 전체 라인 사용
        if not touched and getattr(self, "_last_func_lines", None):
            s, e = self._last_func_lines
            touched.update(range(s, e + 1))

        if not touched:
            print("※ send_report_to_front : 보여줄 라인이 없습니다.")
            return

        # 1) 라인별 분석 결과 수집 -------------------------------
        lmin, lmax = min(touched), max(touched)
        payload = self.get_line_analysis(lmin, lmax)

        if not payload:
            print("※ 분석 결과가 없습니다.")
            return

        print("\n=======  ANALYSIS  =======")
        for ln in sorted(payload):
            for rec in payload[ln]:
                kind = rec.get("kind", "?")
                vars_ = rec.get("vars", {})
                print(f"{ln:4} │ {kind:<12} │ {vars_}")
        print("==========================\n")

    # ContractAnalyzer.py  (클래스 내부)

    def flush_reinterpret_target(self) -> None:
        if not self._batch_targets:
            return
        fcfg = self._batch_targets.pop()
        self.runtime.interpret_function_cfg(fcfg, None)

        ln_set = {st.src_line
                  for blk in fcfg.graph.nodes
                  for st in blk.statements
                  if getattr(st, "src_line", None)}
        self._last_func_lines = (min(ln_set), max(ln_set)) if ln_set else None

    # ──────────────────────────────────────────────────────────────
    # Snapshot 전용 내부 헬퍼  ―  외부에서 쓸 일 없으므로 “프라이빗” 네이밍
    # ----------------------------------------------------------------
    @staticmethod
    def ser(v):  # obj → dict
        return v.__dict__

    @staticmethod
    def de(v, snap):  # dict → obj
        v.__dict__.clear()
        v.__dict__.update(snap)

    # 공통 ‘한 줄 helper’
    def register_var(self, var_obj):
        self.snapman.register(var_obj, self.ser)