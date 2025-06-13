# SolidityGuardian/Analyzers/ContractAnalyzer.py
from Utils.CFG import *
from solcx import (
    install_solc,
    set_solc_version,
    compile_source,
    get_installed_solc_versions
)
from solcx.exceptions import SolcError
from collections import defaultdict, deque
from Domain.Address import *
from Utils.Helper import *
from Utils.Snapshot import *

class ContractAnalyzer:

    def __init__(self):
        self.sm = AddressSymbolicManager()
        self.snapman = SnapshotManager()
        self._batch_targets: set[FunctionCFG] = set()  # 🔹추가

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

        self.current_edit_event = None
        self._record_enabled = False
        self._seen_stmt_ids: set[int] = set()

        # for Multiple Contract
        self.contract_cfgs = {} # name -> CFG

        self.analysis_per_line: dict[int, list[dict]] = defaultdict(list)

    # ──────────────────────────────────────────────────────────────
    # Snapshot 전용 내부 헬퍼  ―  외부에서 쓸 일 없으므로 “프라이빗” 네이밍
    # ----------------------------------------------------------------
    @staticmethod
    def _ser(v):  # obj → dict
        return v.__dict__

    @staticmethod
    def _de(v, snap):  # dict → obj
        v.__dict__.clear()
        v.__dict__.update(snap)

    # 공통 ‘한 줄 helper’
    def _register_var(self, var_obj):
        self.snapman.register(var_obj, self._ser)

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
        for d in (self.brace_count, self.analysis_per_line):
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
                self.brace_count.pop(ln, None)
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
            self.current_target_contract = self.find_contract_context(start_line)

            if self.current_context_type == "contract" :
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

        # ── 새로 추가: 모든 global 을 SnapshotManager に 등록
        for gv in cfg.globals.values():
            self._register_var(gv)

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
        self.brace_count[self.current_start_line]['cfg_node'] = contract_cfg.structDefs

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

        self._register_var(variable_obj)

        # 4. 상태 변수를 ContractCFG에 추가
        contract_cfg.add_state_variable(variable_obj, expr=init_expr, line_no=self.current_start_line)

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

        self._register_var(variable_obj)

        # 3. ContractCFG 에 추가 (state 변수와 동일 API 사용)
        contract_cfg.add_state_variable(variable_obj, expr=init_expr, line_no=self.current_start_line)

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

        for gv in contract_cfg.globals.values():  # ← 새 코드
            modifier_cfg.add_related_variable(gv)  # (얕은 복사 필요 없고
            #     원본 객체를 그대로 써도 OK)

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
        if modifier_name not in contract_cfg.functions:
            raise ValueError(f"Modifier '{modifier_name}' is not defined.")

        mod_cfg: FunctionCFG = contract_cfg.functions[modifier_name]

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
                fcfg.parameters.append(p_name)

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

        # 6-B. 글로벌 변수(block/msg/tx…) ----------------------------------------------
        for gv in contract_cfg.globals.values():  # ← 새 코드
            fcfg.add_related_variable(gv)  # (얕은 복사 필요 없고
            #     원본 객체를 그대로 써도 OK)

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
            init_expr: Expression | None = None
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
                    v.value = AddressSymbolicManager.top_interval()
                else:  # bytes/string
                    v.value = f"symbol_{var_name}"

        # ───────────────────────────────────────────────────────────────
        # 3-b. 초기화식이 존재하는 경우
        # ----------------------------------------------------------------
        else:
            resolved = self.evaluate_expression(init_expr,
                                                cur_blk.variables, None, None)

            # ───────────────────── 구조체 / 배열 / 매핑 ─────────────────────
            if isinstance(resolved, (StructVariable, ArrayVariable, MappingVariable)):
                v = self._deep_clone_variable(resolved, var_name)  # ★ 새 객체 생성
                # (별도로 cur_blk.variables 에도 등록해야 함 – 아래 4단계 참고)

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

        # ───────────────────────────────────────────────────────────────
        # 4. CFG 노드 업데이트
        # ----------------------------------------------------------------
        cur_blk.variables[v.identifier] = v
        cur_blk.add_variable_declaration_statement(type_obj, var_name, init_expr, self.current_start_line)
        self.current_target_function_cfg.add_related_variable(v)
        self.current_target_function_cfg.update_block(cur_blk)

        lhs_expr = Expression(identifier=var_name, context="IdentifierExpContext")
        self._record_analysis(
            line_no=self.current_start_line,
            stmt_type="varDeclaration",
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

        current_block.add_assign_statement(expr.left, expr.operator, expr.right, self.current_start_line)

        if self.current_target_function_cfg.function_type == "constructor" :
            self._overwrite_state_vars_from_block(contract_cfg, current_block.variables)

        base_obj = None
        # 2) 방금 변경된 변수 객체 가져오기
        target_var = self._resolve_and_update_expr(
            expr.left, None, '=', current_block.variables,
            self.current_target_function_cfg
        )

        if target_var is None:
            # a[i] / map[k] 같은 경우 처리
            base_obj = self._resolve_and_update_expr(
                expr.left.base, None, '=', current_block.variables,
                self.current_target_function_cfg
            )

            # ─ Array ─
            if isinstance(base_obj, ArrayVariable):
                concrete = self._try_concrete_key(expr.left.index, current_block.variables)
                if concrete is not None:  # a[5] = …
                    target_var = base_obj.elements[int(concrete)]
                else:  # a[i] = … (i 가 ⊥/TOP)
                    target_var = base_obj  # whole array 기록 + <unk>

            # ─ Mapping ─
            elif isinstance(base_obj, MappingVariable):
                concrete = self._try_concrete_key(expr.left.index, current_block.variables)
                if concrete is not None:
                    target_var = base_obj.mapping.setdefault(
                        concrete,
                        self._create_new_mapping_value(base_obj, concrete)
                    )
                else:
                    target_var = base_obj  # mapping 전체 + <unk>

        # 3) analysis 기록 (기존 호출 그대로)
        self._record_analysis(
            line_no=self.current_start_line,
            stmt_type="assignment",
            expr=expr.left if target_var is not base_obj else expr.left.base,
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
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("active FunctionCFG not found")

        cur_blk = self.get_current_block()

        # ──────────────────────────────────────────────
        # ❶ 피연산 변수의 현재 Interval 가져오기
        # ──────────────────────────────────────────────
        cur_val = self.evaluate_expression(expr,
                                           cur_blk.variables, None, None)

        # (※  evaluate_expression 은 ++x, x-- 양쪽 모두
        #     동일하게 expr.expression 을 넘겨도 됩니다)

        # ──────────────────────────────────────────────
        # ❷ “+1” / “-1” 에 사용할 타입-정합 Interval 생성
        # ──────────────────────────────────────────────
        if isinstance(cur_val, UnsignedIntegerInterval):
            one = UnsignedIntegerInterval(1, 1, cur_val.type_length)
        elif isinstance(cur_val, IntegerInterval):
            one = IntegerInterval(1, 1, cur_val.type_length)
        elif isinstance(cur_val, BoolInterval):
            # ++/-- 가 bool 에 쓰일 일은 없지만 방어적으로
            one = BoolInterval(1, 1)
        else:
            # 주소·string 등에는 ++/-- 가 허용되지 않으므로
            raise ValueError(f"unsupported ++/-- operand type: {type(cur_val).__name__}")

        # ──────────────────────────────────────────────
        # ❸ 실제 변수 갱신
        #     (++/--  ==  <var>  op_sign  1)
        # ──────────────────────────────────────────────
        self.update_left_var(expr, one, op_sign, cur_blk.variables, None, None)

        # ▸ CFG statement 기록 (분석-로그 용)
        cur_blk.add_assign_statement(expr, op_sign,
                                     Expression(literal="1", context="LiteralExpContext"),
                                     self.current_start_line)

        # ── 2) constructor 였으면 state-variables overwrite
        if self.current_target_function_cfg.function_type == "constructor":
            self._overwrite_state_vars_from_block(ccf, cur_blk.variables)

        # ─── 3) 갱신된 변수 객체 찾아서 record ─────────────────────
        base_obj = None  # ←★ 미리 초기화
        target_var = self._resolve_and_update_expr(
            expr,  # ++ / -- 의 피연산자 식
            None, '=',  # new_value 없음 ⇒ 탐색만
            cur_blk.variables,
            self.current_target_function_cfg
        )

        if target_var is None:  # 배열·매핑 인덱스가 불확정한 경우 등
            base_obj = self._resolve_and_update_expr(
                expr.base, None, '=', cur_blk.variables,
                self.current_target_function_cfg
            )
            if isinstance(base_obj, ArrayVariable):
                concrete = self._try_concrete_key(expr.index, cur_blk.variables)
                if concrete is not None:
                    target_var = base_obj.elements[int(concrete)]
                else:
                    target_var = base_obj  # whole-array + <unk>
            elif isinstance(base_obj, MappingVariable):
                concrete = self._try_concrete_key(expr.index, cur_blk.variables)
                if concrete is not None:
                    target_var = base_obj.mapping.setdefault(
                        concrete,
                        self._create_new_mapping_value(base_obj, concrete)
                    )
                else:
                    target_var = base_obj  # whole-mapping + <unk>

        self._record_analysis(
            line_no=self.current_start_line,
            stmt_type=stmt_kind,  # "unary_prefix" 또는 "unary_suffix"
            expr=expr if target_var is not base_obj else expr.base,
            var_obj=target_var
        )

        # ── 4) CFG 저장
        self.current_target_function_cfg.update_block(cur_blk)
        ccf.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = ccf
        self.brace_count[self.current_start_line]["cfg_node"] = cur_blk

    def _handle_delete(self, target_expr: Expression):
        """
        Solidity `delete x` :
            · 스칼라 → 기본값(0 / false / 0x0 …)
            · 배열   → 동적이면 length 0, 정적이면 요소 0
            · 매핑   → entry 제거
            · struct → 각 필드 delete 재귀
        분석 도메인에서는 “가장 보수적”으로 **bottom** 또는 0-singleton 으로 초기화
        """

        ccf = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = ccf.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("active FunctionCFG not found")

        cur_blk = self.get_current_block()
        vars_env = cur_blk.variables

        # 1) 대상 변수 객체 찾기 (update 없는 '=' 호출하여 객체만 받아옴)
        var_obj = self._resolve_and_update_expr(
            target_expr, rVal=None, operator="=", variables=vars_env,
            fcfg=self.current_target_function_cfg)

        # 2) 타입별 ‘기본값’ 적용 -----------------------------------------
        def _wipe(obj):
            if isinstance(obj, MappingVariable):
                obj.mapping.clear()
            elif isinstance(obj, ArrayVariable):
                obj.elements.clear()
            elif isinstance(obj, StructVariable):
                for m in obj.members.values():
                    _wipe(m)
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
                else:  # bytes / string …
                    obj.value = f"symbolic_zero_{obj.identifier}"

        _wipe(var_obj)

        # 3) 로그 & CFG 저장 (기존 ++/-- 로직과 동일 형태)
        cur_blk.add_assign_statement(
            target_expr, "delete", None, self.current_start_line)

        fcfg = self.current_target_function_cfg
        fcfg.update_block(cur_blk)
        self.contract_cfgs[self.current_target_contract] \
            .functions[self.current_target_function] = fcfg
        self.brace_count[self.current_start_line]["cfg_node"] = cur_blk

    # ───────────────────────────────────────────────────────────
    def process_unary_prefix_operation(self, expr: Expression):
        if expr.operator == "++":
            self._handle_unary_incdec(expr.expression, "+=", "unary_prefix")
        elif expr.operator == "--":
            self._handle_unary_incdec(expr.expression, "-=", "unary_prefix")
        elif expr.operator == "delete":
            self._handle_delete(expr.expression)
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

        saved_cfg = self.current_target_function_cfg  # ⭐ CFG 백업
        saved_fn = self.current_target_function  # ⭐ 함수 이름 백업

        current_block = self.get_current_block()
        # 3. 함수 표현식 가져오기
        function_expr = expr.function

        _ = self.evaluate_function_call_context(expr, current_block.variables, None, None)

        current_block.add_function_call_statement(expr, self.current_start_line)

        # 10. current_block을 function CFG에 반영
        self.current_target_function_cfg = saved_cfg
        self.current_target_function = saved_fn
        self.current_target_function_cfg.update_block(current_block)

        # 6) 상위 구조로 반영
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg
        self.brace_count[self.current_start_line]['cfg_node'] = current_block

        # 7) 컨텍스트 정리 (설계에 따라 유지/제거)
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
                                  condition_node_type="if",
                                  src_line=self.current_start_line)
        condition_block.condition_expr = condition_expr
        # 7. True 분기에서 변수 상태 복사 및 업데이트
        condition_block.variables = self.copy_variables(current_block.variables)

        # 4. brace_count 업데이트 - 존재하지 않으면 초기화
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = condition_block

        # 5. True 분기 블록 생성
        true_block = CFGNode(name=f"if_true_{self.current_start_line+1}",
                             branch_node=True,
                             is_true_branch=True,
                             src_line=self.current_start_line)
        true_block.variables = self.copy_variables(current_block.variables)
        # 7. True 분기에서 변수 상태 복사 및 업데이트
        self.update_variables_with_condition(true_block.variables, condition_expr, is_true_branch=True)

        # ❶――― 〈True-분기〉 변수 환경을 즉시 기록
        self._record_analysis(
            line_no=self.current_start_line,  # if 조건이 적힌 라인
            stmt_type="branchTrue",  # 또는 "ifConditionTrue" 등 통일된 tag
            env=true_block.variables  # 좁혀진 Interval 들
        )

        false_block = CFGNode(name=f"if_false_{self.current_start_line}",
                              branch_node=True,
                              is_true_branch=False,
                              src_line=self.current_start_line)
        false_block.variables = self.copy_variables(current_block.variables)
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
                                  branch_node=True,
                                  is_true_branch=False,
                                  condition_node=True,
                                  condition_node_type="else if",
                                  src_line=self.current_start_line)
        condition_block.condition_expr = condition_expr
        condition_block.variables = self.copy_variables(temp_variables)

        # 5. brace_count 업데이트 - 존재하지 않으면 초기화
        if self.current_start_line not in self.brace_count:
            self.brace_count[self.current_start_line] = {}
        self.brace_count[self.current_start_line]['cfg_node'] = condition_block

        # 6. True 분기 블록 생성
        true_block = CFGNode(name=f"else_if_true_{self.current_start_line}",
                             branch_node=True,
                             is_true_branch=True,
                             src_line=self.current_start_line)
        true_block.variables = self.copy_variables(condition_block.variables)

        self.update_variables_with_condition(true_block.variables, condition_expr, is_true_branch=True)

        # ❶――― 〈True-분기〉 변수 환경을 즉시 기록
        self._record_analysis(
            line_no=self.current_start_line,  # if 조건이 적힌 라인
            stmt_type="branchTrue",  # 또는 "ifConditionTrue" 등 통일된 tag
            env=true_block.variables  # 좁혀진 Interval 들
        )

        # 5. False 분기 블록 생성
        false_block = CFGNode(name=f"else_if_false_{self.current_start_line}",
                              branch_node=True,
                              is_true_branch=False,
                              src_line=self.current_start_line)

        false_block.variables = self.copy_variables(condition_block.variables)
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
        for ts in old_succs:  # 이전 True-succ
            for nxt in list(self.current_target_function_cfg.successors(ts)):  # 그 뒤 노드들
                self.current_target_function_cfg.add_edge(true_block, nxt)
                self.current_target_function_cfg.add_edge(false_block, nxt)

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

                # 👉 succ 가 가지고 있던 모든 outbound edge 제거
                for s in list(g.successors(succ)):
                    g.remove_edge(succ, s)

        # ── 2-B) “True succ” 들 저장 (join 지점 후보)
        true_succs = [
            s for s in g.successors(cond_node)
            if g[cond_node][s].get("condition") is True
        ]

        # ───────────────────────── 3. else 블록 생성 ──────────────────────
        else_blk = CFGNode(f"else_block_{self.current_start_line}",
                           branch_node=True,
                           is_true_branch=False,
                           src_line=self.current_start_line)

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

        for ts in true_succs:  # True 블록(들)
            for nxt in list(g.successors(ts)):  # 그 블록이 향하던 곳
                g.add_edge(else_blk, nxt)  # else ─▶ same succ

        # ───────────────────────── 5. brace_count 갱신 ────────────────────
        self.brace_count.setdefault(self.current_start_line, {})
        self.brace_count[self.current_start_line]["cfg_node"] = else_blk

        # ───────────────────────── 6. 분석 결과 기록 ──────────────────────
        #   “else { … }” 첫 줄에서   ▶  분기 전 전체 env 스냅-숏 저장
        self._record_analysis(
            line_no=self.current_start_line,
            stmt_type="branchTrue",
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
                                 condition_node_type="while",
                                 src_line=self.current_start_line)
        condition_node.condition_expr = condition_expr  # Store the condition expression for later use
        condition_node.variables = self.copy_variables(join_node.variables)


        # 5. Connect the current block to the join node (if not already connected)
        self.current_target_function_cfg.graph.add_node(join_node)
        self.current_target_function_cfg.graph.add_edge(current_block, join_node)

        # 6. Connect the join node to the condition node
        self.current_target_function_cfg.graph.add_node(condition_node)
        self.current_target_function_cfg.graph.add_edge(join_node, condition_node)

        # 7. Create the true node (loop body)
        true_node = CFGNode(name=f"while_body_{self.current_start_line}",
                            branch_node=True,
                            is_true_branch=True)
        true_node.is_loop_body = True
        true_node.variables = self.copy_variables(condition_node.variables)
        self.update_variables_with_condition(true_node.variables, condition_expr, is_true_branch=True)

        # 8. Create the false node (exit block)
        false_node = CFGNode(name=f"while_exit_{self.current_start_line}",
                             loop_exit_node=True,
                             branch_node=True,
                             is_true_branch=False)
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

        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("[for] active function CFG 없음")

        # ------------------------------------------------------------------#
        # 2) 루프 직전 블록
        # ------------------------------------------------------------------#
        current_block = self.get_current_block()  # for 키워드 이전 코드가 위치한 블록
        old_successors = list(self.current_target_function_cfg.graph.successors(current_block))

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

                init_node.add_variable_declaration_statement(
                    var_type,
                    var_name,
                    init_expr,
                    line_no=self.current_start_line
                )

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

                # ★  Assignment Statement 기록 ★
                init_node.add_assign_statement(
                    tmp_expr.left,
                    tmp_expr.operator,
                    tmp_expr.right,
                    line_no=self.current_start_line
                )

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
                            condition_node_type="for",
                            src_line=self.current_start_line)
        cond_node.condition_expr = condition_expr
        cond_node.variables = self.copy_variables(join_node.variables)

        # ------------------------------------------------------------------#
        # 6) body_node
        # ------------------------------------------------------------------#
        body_node = CFGNode(f"for_body_{self.current_start_line}",
                            branch_node=True,
                            is_true_branch=True)
        body_node.is_loop_body = True
        body_node.variables = self.copy_variables(cond_node.variables)

        if condition_expr is not None:
            self.update_variables_with_condition(body_node.variables,
                                                 condition_expr,
                                                 is_true_branch=True)

        # ------------------------------------------------------------------#
        # 7) increment_node
        # ------------------------------------------------------------------#
        incr_node = CFGNode(f"for_increment_{self.current_start_line}",
                            is_for_increment=True)
        incr_node.variables = self.copy_variables(body_node.variables)

        # ───────────────────────── for-increment helper ──────────────────────────
        def _make_one_interval(var_expr: Expression, cur_vars: dict[str, Variables]):
            """
            var_expr 로 가리키는 변수의 타입(uint / int)에 맞춰
            숫자 1을 UnsignedIntegerInterval 또는 IntegerInterval 로 래핑해 준다.
            """
            # var_expr 가 가리키는 실제 변수 객체 확보
            v_obj = self._resolve_and_update_expr(var_expr, 1, '=', cur_vars,
                                                   self.current_target_function_cfg)
            if v_obj is None or v_obj.typeInfo is None:
                # fallback – 그냥 리터럴 1 (실패해도 compound_assignment 쪽에서 처리는 됨)
                return 1

            et = v_obj.typeInfo.elementaryTypeName
            bits = v_obj.typeInfo.intTypeLength or 256

            if et.startswith("uint"):
                return UnsignedIntegerInterval(1, 1, bits)
            elif et.startswith("int"):
                return IntegerInterval(1, 1, bits)
            else:
                # bool 이나 기타가 for-counter 로 쓰이는 경우는 거의 없지만 안전장치
                return 1

        # ──────────────────────────────────────────────────────────────────────────
        if increment_expr is not None:
            op = increment_expr.operator

            # ① ++ / -- -----------------------------------------------------------
            if op in {"++", "--"}:
                one_iv = _make_one_interval(increment_expr.expression,
                                            incr_node.variables)
                incr_node.add_assign_statement(
                    increment_expr.expression,
                    "+=" if op == "++" else "-=",
                    # Statement 에도 Interval 을 넘겨둔다 (직렬화용)
                    one_iv,
                    self.current_start_line
                )

            # ② += / -= -----------------------------------------------------------
            elif op in {"+=", "-="}:
                # RHS 가 리터럴이면 타입에 맞춰 Interval 로 변환
                rhs_iv = (_make_one_interval(increment_expr.left,
                                             incr_node.variables)
                          if increment_expr.right.context == "LiteralExpContext"
                             and str(increment_expr.right.literal) == "1"
                          else increment_expr.right)

                incr_node.add_assign_statement(
                    increment_expr.left,
                    op,
                    rhs_iv,
                    self.current_start_line
                )

            else:
                raise ValueError(f"[for] unexpected increment operator '{op}'")

        # ------------------------------------------------------------------#
        # 8) exit_node  (loop-false 블록)
        # ------------------------------------------------------------------#
        exit_node = CFGNode(f"for_exit_{self.current_start_line}", loop_exit_node=True,
                            branch_node=True,
                            is_true_branch=False)
        exit_node.variables = self.copy_variables(join_node.variables)

        if condition_expr is not None:  # ★
            self.update_variables_with_condition(exit_node.variables,
                                                 condition_expr,
                                                 is_true_branch=False)

        # ------------------------------------------------------------------#
        # 9) 그래프 연결
        # ------------------------------------------------------------------#
        g = self.current_target_function_cfg.graph

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
        current_block.add_continue_statement(self.current_start_line)

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
        """
        `break` 가 등장했을 때 CFG 를 올바르게 재-배선한다.

        ①  break 가 위치한 블록(current_block) → loop-exit-node 로 edge 추가
        ②  condition-node → “루프 안쪽으로 들어가는 유일 진입점”
            ( - for : incr_node,  while : join_node ) 으로 향하는 edge 제거
        ③  이미 만들어져 있던 pred → incr|join edge 들도 끊어서
            true-branch 가 leaf 판정에 잡히지 않도록 만든다.
        """

        def debug_path_to_header(cur_blk, g):
            """cur_blk → … → loop header 로 가는 모든 선행-경로를 출력"""
            from collections import deque
            Q = deque([(cur_blk, [cur_blk.name])])
            seen = set()
            while Q:
                n, path = Q.popleft()
                if n in seen:  # 사이클 방지
                    continue
                seen.add(n)

                if n.condition_node and n.condition_node_type in ("for", "while", "doWhile"):
                    print("FOUND!", " → ".join(path))
                    return n
                for p in g.predecessors(n):
                    Q.append((p, path + [p.name]))
            print("❌ header 미발견")
            return None

        # ────────────────────────────────────────────────────────────
        # 1) 준비 – CFG 컨텍스트
        # ────────────────────────────────────────────────────────────
        contract_cfg = self.contract_cfgs.get(self.current_target_contract)
        if not contract_cfg:
            raise ValueError(f"[break] contract CFG '{self.current_target_contract}' not found")

        self.current_target_function_cfg = contract_cfg.get_function_cfg(self.current_target_function)
        if not self.current_target_function_cfg:
            raise ValueError("[break] active function CFG 없음")

        g = self.current_target_function_cfg.graph
        cur_blk = self.get_current_block()
        debug_path_to_header(cur_blk, g)

        # ────────────────────────────────────────────────────────────
        # 2) break 구문 statement 추가
        # ────────────────────────────────────────────────────────────
        cur_blk.add_break_statement(self.current_start_line)

        # ────────────────────────────────────────────────────────────
        # 3) “현재 루프”의 구성요소 찾기
        #    ▸ condition_node              ▸ loop_exit_node(false-branch)
        # ────────────────────────────────────────────────────────────
        cond_node = self.find_loop_condition_node(cur_blk)
        if cond_node is None:
            raise ValueError("[break] surrounding loop condition-node not found")

        exit_node = self.current_target_function_cfg.get_false_block(cond_node)  # while / for 공통
        if exit_node is None or not exit_node.loop_exit_node:
            raise ValueError("[break] loop-exit-node 찾기 실패")

        # ────────────────────────────────────────────────────────────
        # 4) 기존 cur_blk → successors edge 제거,
        #    cur_blk → exit_node 로 연결
        # ────────────────────────────────────────────────────────────
        for succ in list(g.successors(cur_blk)):
            g.remove_edge(cur_blk, succ)
        g.add_edge(cur_blk, exit_node)

        # ────────────────────────────────────────────────────────────
        # 6) bookkeeping – brace_count & CFG 저장
        # ────────────────────────────────────────────────────────────
        self.brace_count.setdefault(self.current_start_line, {})["cfg_node"] = cur_blk

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

            # ────────── ② 분석 기록 ──────────
            #  (a) TupleExpression – 요소별 flatten
            if return_expr and return_expr.context == "TupleExpressionContext":
                flat = {
                    self._expr_to_str(e): self._serialize_val(v)
                    for e, v in zip(return_expr.elements, return_value)
                }
                self._record_analysis(
                    line_no=self.current_start_line,
                    stmt_type="return",
                    env={**flat}  # ← env 인자로 직접 flatten 전달
                )

            #  (b) Named-return variables &  `return;`
            elif return_expr is None and self.current_target_function_cfg.return_vars:
                flat = {
                    rv.identifier: self._serialize_val(rv.value)
                    for rv in self.current_target_function_cfg.return_vars
                }
                self._record_analysis(
                    line_no=self.current_start_line,
                    stmt_type="return",
                    env=flat
                )

            #  (c) 단일 값
            else:
                self._record_analysis(
                    line_no=self.current_start_line,
                    stmt_type="return",
                    expr=return_expr,
                    var_obj=Variables("__ret__", return_value, scope="tmp")
                )

        # 4. Return 구문을 current_block에 추가
        current_block.add_return_statement(return_expr=return_expr, line_no=self.current_start_line)

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
        g = self.current_target_function_cfg.graph
        if not self.current_target_function_cfg:
            raise ValueError("No active function to process the require statement.")

        # 2. 현재 블록 가져오기
        current_block = self.get_current_block()

        # ── 4  조건-노드 생성
        req_cond = CFGNode(
            name=f"require_condition_{self.current_start_line}",
            condition_node=True,
            condition_node_type="require",
            src_line=self.current_start_line
        )
        req_cond.condition_expr = condition_expr
        req_cond.variables = self.copy_variables(current_block.variables)

        # ── 5 True-블록
        true_blk = CFGNode(name=f"require_true_{self.current_start_line}",
                           branch_node=True,
                           is_true_branch=True,
                           src_line=self.current_start_line)
        true_blk.variables = self.copy_variables(req_cond.variables)
        self.update_variables_with_condition(true_blk.variables,
                                             condition_expr,
                                             is_true_branch=True)


        # ─── True 블록 생성 후에만 기록
        self._record_analysis(
            line_no=self.current_start_line,
            stmt_type="requireTrue",  # camelCase 유지
            env=true_blk.variables  # 좁혀진 Interval 들
        )

        succs = list(g.successors(current_block))
        # ── 6 CFG 재배선 (successor edge 이동)
        for s in succs:
           g.remove_edge(current_block, s)
        g.add_node(req_cond)
        g.add_edge(current_block, req_cond)

        # ── 8 False-분기 : exit 노드로
        exit_node = self.current_target_function_cfg.get_exit_node()
        g.add_edge(req_cond, exit_node, condition=False)

        # ── 9 True-분기 연결
        g.add_node(true_blk)
        g.add_edge(req_cond, true_blk, condition=True)

        for s in succs or [exit_node]:  # succs 가 없으면 exit 직행
            g.add_edge(true_blk, s)

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

        g = self.current_target_function_cfg.graph
        succs = list(g.successors(current_block))
        for s in succs:
            g.remove_edge(current_block, s)  # 기존 edge 제거

        # ── 3 successors, 4 조건노드 생성
        assert_cond = CFGNode(
            name=f"assert_condition_{self.current_start_line}",
            condition_node=True,
            condition_node_type="assert",
            src_line=self.current_start_line
        )
        assert_cond.condition_expr = condition_expr

        # ── 5 True-블록
        true_blk = CFGNode(name=f"assert_true_{self.current_start_line}",
                           branch_node=True,
                           is_true_branch=True,
                           src_line=self.current_start_line)
        true_blk.variables = self.copy_variables(current_block.variables)
        self.update_variables_with_condition(true_blk.variables,
                                             condition_expr,
                                             is_true_branch=True)

        g.add_node(true_blk)
        g.add_edge(assert_cond, true_blk, condition=True)

        #     · True-블록 이후 기존 succ 으로 이어주기
        for s in (succs or [self.current_target_function_cfg.get_exit_node()]):
            g.add_edge(true_blk, s)

        # ── ③ False-분기 → exit
        exit_node = self.current_target_function_cfg.get_exit_node()
        g.add_edge(assert_cond, exit_node, condition=False)

        # ── ④ 분석 결과 : True-분기 스냅샷만 기록
        self._record_analysis(
            line_no=self.current_start_line,
            stmt_type="assertTrue",
            env=true_blk.variables
        )

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
        unchecked_block = CFGNode(name=f"unchecked_{self.current_start_line}",
                                  unchecked_block=True)
        unchecked_block.variables = self.copy_variables(current_block.variables)

        g = self.current_target_function_cfg.graph
        for succ in list(g.successors(current_block)):
            g.remove_edge(current_block, succ)
            g.add_edge(unchecked_block, succ)

        # ── 7 current_block → 조건노드
        g.add_node(unchecked_block)
        g.add_edge(current_block, unchecked_block)

        self.brace_count.setdefault(self.current_start_line, {})["cfg_node"] = unchecked_block

        # ====================================================================

        # ── 10 CFG / contract 갱신
        contract_cfg.functions[self.current_target_function] = self.current_target_function_cfg
        self.contract_cfgs[self.current_target_contract] = contract_cfg
        self.current_target_function_cfg = None

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
            self.snapman.register(gv_obj, self._ser)  # ★ 스냅

        g = cfg.globals[gv_obj.identifier]

        # ── add/modify ───────────────────────────────────────────
        if ev in ("add", "modify"):
            g.debug_override = gv_obj.value
            g.value = gv_obj.value

        # ── delete  → snapshot 복원 + override 해제 ───────────────
        elif ev == "delete":
            self.snapman.restore(g, self._de)  # ★ 롤백
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

        self.add_batch_target(self.current_target_function_cfg)

        self.current_target_function_cfg = None

    # ─────────────────────────────────────────────────────────────
    def process_state_var_for_debug(self, lhs_expr: Expression, value):
        """
        @StateVar …   주석 처리
        lhs_expr : Expression (identifier / .member / [index] …)
        value    : Interval | BoolInterval | UnsignedIntegerInterval(160-bit) | str
        """
        cfg = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = cfg.get_function_cfg(self.current_target_function)
        ev = self.current_edit_event
        if self.current_target_function_cfg is None:
            raise ValueError("@StateVar debug must appear inside a function body.")

        # 1) 변수 객체 위치 탐색 + 값 대입
        var_obj = self._resolve_and_update_expr(lhs_expr, value, '=',
                                                self.current_target_function_cfg.related_variables,
                                                self.current_target_function_cfg)
        if var_obj is None:
            raise ValueError("LHS cannot be resolved to a state variable.")

        # 최초 등록 시 snapshot
        if id(var_obj) not in self.snapman._store:
            self.snapman.register(var_obj, self._ser)

        if ev in ("add", "modify"):
            self._patch_var_with_new_value(var_obj, value)
        elif ev == "delete":
            self.snapman.restore(var_obj, self._de)
        else:
            raise ValueError(f"unknown event {ev!r}")

        # 2) 주소형이면 심볼릭-ID 바인딩
        if (getattr(var_obj.typeInfo, "elementaryTypeName", None) == "address" and
                isinstance(var_obj.value, UnsignedIntegerInterval)):
            iv = var_obj.value
            if iv.min_value == iv.max_value:
                nid = iv.min_value
                self.sm.register_fixed_id(nid, iv)
                self.sm.bind_var(var_obj.identifier, nid)

        self.add_batch_target(self.current_target_function_cfg)

        self.current_target_function_cfg = None

    # ─────────────────────────────────────────────────────────────
    def process_local_var_for_debug(self, lhs_expr: Expression, value):
        """
        @LocalVar …   주석 처리 (함수 내부 로컬)
        """
        ev = self.current_edit_event
        cfg = self.contract_cfgs[self.current_target_contract]
        self.current_target_function_cfg = cfg.get_function_cfg(self.current_target_function)
        if self.current_target_function_cfg is None:
            raise ValueError("@LocalVar debug must appear inside a function body.")

        var_obj = self._resolve_and_update_expr(lhs_expr, value, '=',
                                                self.current_target_function_cfg.related_variables,
                                                self.current_target_function_cfg)

        if var_obj is None:
            raise ValueError("LHS cannot be resolved to a local variable.")

        if id(var_obj) not in self.snapman._store:
            self.snapman.register(var_obj, self._ser)

        if ev in ("add", "modify"):
            var_obj.value = value
        elif ev == "delete":
            self.snapman.restore(var_obj, self._de)
        else:
            raise ValueError(f"unknown event {ev!r}")

        # 주소형 → 심볼릭-ID 바인딩
        if (getattr(var_obj.typeInfo, "elementaryTypeName", None) == "address" and
                isinstance(var_obj.value, UnsignedIntegerInterval)):
            iv = var_obj.value
            if iv.min_value == iv.max_value:
                nid = iv.min_value
                self.sm.register_fixed_id(nid, iv)
                self.sm.bind_var(var_obj.identifier, nid)

        # 함수 재해석
        self.add_batch_target(self.current_target_function_cfg)

        self.current_target_function_cfg = None