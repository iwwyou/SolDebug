from Utils.Interval import *
from antlr4.error.ErrorListener import ErrorListener, ConsoleErrorListener

# util.py
import copy

from antlr4 import *
from Parser.SolidityLexer  import SolidityLexer
from Parser.SolidityParser import SolidityParser

class ParserHelpers:
    # --------------------------- 컨텍스트 → 파싱 규칙 매핑
    _CTX_MAP: dict[str, str] = {
        'contract':'interactiveSourceUnit', 'library':'interactiveSourceUnit',
        'interface':'interactiveSourceUnit', 'enum':'interactiveSourceUnit',
        'struct':'interactiveSourceUnit',   'functionDefinition':'interactiveSourceUnit',
        'constructor':'interactiveSourceUnit', 'fallback':'interactiveSourceUnit',
        'receive':'interactiveSourceUnit',  'event':'interactiveSourceUnit',
        'error':'interactiveSourceUnit',    'modifier':'interactiveSourceUnit',
        'stateVariableDeclaration':'interactiveSourceUnit',

        'enumMember':'interactiveEnumUnit',
        'structMember':'interactiveStructUnit',

        'simpleStatement':'interactiveBlockUnit', 'if':'interactiveBlockUnit',
        'for':'interactiveBlockUnit',     'while':'interactiveBlockUnit',
        'do':'interactiveBlockUnit',      'try':'interactiveBlockUnit',
        'return':'interactiveBlockUnit',  'break':'interactiveBlockUnit',
        'continue':'interactiveBlockUnit','emit':'interactiveBlockUnit',
        'unchecked':'interactiveBlockUnit',

        'doWhileWhile':'interactiveDoWhileUnit',
        'catch':'interactiveCatchClauseUnit',
        'else_if':'interactiveIfElseUnit', 'else':'interactiveIfElseUnit',

        'debugUnit':'debugUnit'
    }

    # --------------------------- map → 규칙 문자열
    @staticmethod
    def map_context_type(ctx_type: str) -> str|None:
        return ParserHelpers._CTX_MAP.get(ctx_type)

    # --------------------------- 파싱
    @staticmethod
    def generate_parse_tree(src: str, ctx_type: str, verbose=False):
        input_stream  = InputStream(src)
        lexer         = SolidityLexer(input_stream)
        token_stream  = CommonTokenStream(lexer)
        parser        = SolidityParser(token_stream)

        # ── ① 에러 리스너 부착 ───────────────────────────────
        if verbose:
            # 기본 ConsoleErrorListener 제거
            parser.removeErrorListeners()

            # ▶ 한 줄짜리 익명 ErrorListener
            parser.addErrorListener(
                type(
                    "InlineErr", (ErrorListener,), {
                        "syntaxError": lambda self, recognizer, offendingSymbol,
                                              line, column, msg, e:
                        print(f"[ANTLR] {line}:{column} {msg}")
                    }
                )()
            )
        else:
            # 최소한 기본 오류 출력은 유지하고 싶다면
            parser.removeErrorListeners()
            parser.addErrorListener(ConsoleErrorListener.INSTANCE)

        rule = ParserHelpers.map_context_type(ctx_type)

        match rule:
            case 'interactiveStructUnit':     return parser.interactiveStructUnit()
            case 'interactiveEnumUnit':       return parser.interactiveEnumUnit()
            case 'interactiveBlockUnit':      return parser.interactiveBlockUnit()
            case 'interactiveDoWhileUnit':    return parser.interactiveDoWhileUnit()
            case 'interactiveIfElseUnit':     return parser.interactiveIfElseUnit()
            case 'interactiveCatchClauseUnit':return parser.interactiveCatchClauseUnit()
            case 'debugUnit':                 return parser.debugUnit()
            case _:                           return parser.interactiveSourceUnit()

# Utils/snapshot_manager.py  (혹은 기존 SnapshotManager 정의 위치)
import copy
from collections.abc import Callable

class SnapshotManager:
    """
    * register(obj, serializer)              : 객체별 최초 스냅
    * restore(obj, deserializer)             : 단일 객체 롤백   (기존 인터페이스)
    * snapshot() -> dict                     : 전체 스냅          (새로 추가)
    * restore(snap_dict)                     : 전체 롤백          (새로 추가, 오버로드)
    """

    def __init__(self) -> None:
        # id(obj) -> { "__dict__": deep-copied dict, "serializer": fn }
        self._store: dict[int, dict] = {}
        # id(obj) -> 실객체 참조 (전역 롤백 시 필요)
        self._ref:   dict[int, object] = {}

    # ───────────────────────────────────────── register
    def register(self, obj: object, serializer: Callable[[object], dict]) -> None:
        """
        처음 보는 변수라면 serializer(obj) 결과를 깊은 복사로 저장
        (이미 등록돼 있으면 재등록하지 않음)
        """
        oid = id(obj)
        if oid not in self._store:
            self._store[oid] = {
                "snap": copy.deepcopy(serializer(obj)),
                "serializer": serializer,
            }
            self._ref[oid] = obj

    # ───────────────────────────────────────── 단일 객체 롤백 (기존용)
    def restore(self, target, deserializer: Callable[[object, dict], None] | None = None):
        """
        ‣ (a) 인자가 2개   → 단일 객체 롤백   : restore(obj, deser)
        ‣ (b) 인자가 1개   → 전역 롤백       : restore(snap_dict)
        """
        # -------- (a) 단일 객체
        if deserializer is not None:
            snap_info = self._store.get(id(target))
            if snap_info is not None:
                deserializer(target, copy.deepcopy(snap_info["snap"]))
            return

        # -------- (b) 전역 롤백 (target == snap_dict)
        snap_dict: dict[int, dict] = target       # type: ignore
        for oid, saved_state in snap_dict.items():
            obj = self._ref.get(oid)
            if obj is None:           # 아직 register 안 된 객체일 수 있음
                continue
            # 객체 내부 상태를 원본으로 되돌림
            obj.__dict__.clear()
            obj.__dict__.update(copy.deepcopy(saved_state))

    # ───────────────────────────────────────── 전체 스냅
    # 전체 스냅-샷을 반환
    def snapshot(self):
        return copy.deepcopy(self._store)

    # 외부에서 받은 snap(dict) 전체를 되돌린다
    def restore_from_snap(self, snap):
        self._store = snap


class Statement:
    def __init__(self, statement_type, **kwargs):
        self.statement_type = statement_type  # 'assignment', 'if', 'while', 'for', 'return', 'require', 'assert' 등

        # 공통 속성
        self.expressions = []  # 해당 문에서 사용하는 Expression 객체들
        self.statements = []   # 블록 내에 포함된 Statement 객체들

        # 각 statement_type별로 필요한 속성 설정
        if statement_type == 'variableDeclaration' :
            self.type_obj = kwargs.get('type_obj')  # SolType
            self.var_name = kwargs.get('var_name')
            self.init_expr = kwargs.get('init_expr')
            self.src_line = kwargs.get('src_line')
        elif statement_type == 'assignment':
            self.left = kwargs.get('left')        # 좌변 Expression
            self.operator = kwargs.get('operator')  # 할당 연산자 (예: '=', '+=', '-=' 등)
            self.right = kwargs.get('right')      # 우변 Expression
            self.src_line = kwargs.get('src_line')
        elif statement_type == "functionCall" :
            self.function_expr = kwargs.get('function_expr')
            self.src_line = kwargs.get('src_line')
        elif statement_type == 'return':
            self.return_expr = kwargs.get('return_expr')
            self.src_line = kwargs.get('src_line')
        elif statement_type == 'revert' :
            self.identifier = kwargs.get('identifier')
            self.string_literal = kwargs.get('string_literal')
            self.arguments = kwargs.get('arguments')
            self.src_line = kwargs.get('src_line')



class Expression:
    def __init__(self, left=None, operator=None, right=None, identifier=None, literal=None, var_type=None,
                 function=None, arguments=None, named_arguments=None, base=None, access=None,
                 index=None, start_index=None, end_index=None, member=None, options=None,
                 typeName=None, expression=None, condition=None, true_expr=None, false_expr=None,
                 is_postfix=None, elements=None, expr_type=None, type_length=256, context=None):
        self.left = left                # 좌측 피연산자 (Expression)
        self.operator = operator        # 연산자 (문자열)
        self.right = right              # 우측 피연산자 (Expression)
        self.identifier = identifier    # 식별자 (변수 이름, 함수 이름 등)
        self.literal = literal          # 리터럴 값 (숫자, 문자열 등)
        self.var_type = var_type        # 변수 타입 (문자열)
        self.function = function        # 함수 표현식 (Expression)
        self.arguments = arguments      # 위치 기반 인자 목록 (리스트)
        self.named_arguments = named_arguments  # 이름 지정 인자 (딕셔너리)
        self.base = base                # 인덱스 또는 멤버 접근의 대상 표현식 (Expression)
        self.access = access            # index_access 등
        self.index = index              # 단일 인덱스 표현식 (Expression)
        self.start_index = start_index  # 슬라이싱의 시작 인덱스 (Expression)
        self.end_index = end_index      # 슬라이싱의 끝 인덱스 (Expression)
        self.member = member            # 멤버 이름 (문자열)
        self.options = options          # 함수 호출 옵션 (딕셔너리)
        self.typeName = typeName        # 타입 변환의 대상 타입 이름 (문자열)
        self.expression = expression    # 변환될 표현식 또는 단일 표현식 (Expression)
        self.condition = condition      # 조건식 (삼항 연산자용) (Expression)
        self.true_expr = true_expr      # 조건식이 참일 때의 표현식 (Expression)
        self.false_expr = false_expr    # 조건식이 거짓일 때의 표현식 (Expression)
        self.is_postfix = is_postfix    # 후위 연산자 여부 (Boolean)
        self.elements = elements        # 튜플 또는 배열의 요소들 (리스트)
        self.expr_type = expr_type      # 표현식의 타입 (예: 'int', 'uint', 'bool')
        self.type_length = type_length  # 타입의 길이 (예: 256)
        self.context = context

class SolType:
    def __init__(self):
        self.typeCategory = None  # 'elementary', 'array', 'mapping', 'struct', 'function', 'enum'

        # elementary 타입 정보
        self.elementaryTypeName = None  # 예: 'uint256', 'address'
        self.intTypeLength = None  # 정수 타입의 비트 길이 (예: 256)

        # 배열 타입 정보
        self.arrayBaseType = None  # Type 객체
        self.arrayLength = None  # 배열 길이
        self.isDynamicArray = False  # 동적 배열 여부

        # mapping 타입 정보
        self.mappingKeyType = None  # Type 객체
        self.mappingValueType = None  # Type 객체

        # 구조체 타입 정보
        self.structTypeName = None  # 구조체 이름 (문자열)
        self.enumTypeName = None


class Variables:
    def __init__(self, identifier=None, value=None,
                 isConstant=False, scope=None, typeInfo=None):
        # 기본 속성
        self.identifier = identifier  # 변수명
        self.scope = scope  # 변수의 스코프 (local, state 등)
        self.isConstant = isConstant  # 상수 여부
        self.typeInfo = typeInfo # SolType

        # 값 정보
        self.value = value  # interval
        self.initial_value = copy.deepcopy(value)  # ← NEW


class GlobalVariable(Variables):
    def __init__(self, identifier=None, isConstant=False, scope=None, base=None, member=None, value=None, typeInfo=None):
        super().__init__(identifier, value, isConstant, scope)
        self.base = base
        self.member = member
        self.value = value
        self.typeInfo = SolType()

        self.default_value: Interval | str | None = None  # 런타임 기본값
        self.debug_override: Interval | str | None = None  # 마지막 @GlobalVar 값
        self.usage_sites: set[str] = set()   # func_name 만!

    # helper ― override 가 있으면 그것, 없으면 value
    @property
    def current(self):
        return self.debug_override if self.debug_override is not None else self.value

class AddressSymbolicManager:
    """
    160-bit 주소 공간의 심볼릭 ID ↔ Interval ↔ 변수 alias 를 한 곳에서 관리
    """
    ADDR_BITS = 160
    MAX_ADDR = (1 << ADDR_BITS) - 1
    TOP_INTERVAL = UnsignedIntegerInterval(0, MAX_ADDR, ADDR_BITS)
    _typeinfo = SolType()                 # 빈 객체 먼저 만들고
    _typeinfo.typeCategory = "elementary" # 필드 수동 설정
    _typeinfo.elementaryTypeName = "address"

    def __init__(self):
        self._next_id: int = 1                    # fresh ID counter
        self._id_to_iv: dict[int, UnsignedIntegerInterval] = {}
        self._id_to_vars: dict[int, set[str]] = {}  # 해당 ID를 쓰는 변수명 모음

    @staticmethod
    def top_interval() -> UnsignedIntegerInterval:
        return UnsignedIntegerInterval(0, 2 ** 160 - 1, type_length=160)

    # ───────────────────────────────── fresh / fixed  ID 발급
    def fresh_id(self) -> int:
        nid = self._next_id
        self._next_id += 1
        return nid

    def alloc_fresh_interval(self) -> UnsignedIntegerInterval:
        """새 ID 하나 -> Interval [id,id] 반환"""
        nid = self.fresh_id()
        iv  = UnsignedIntegerInterval(nid, nid, self.ADDR_BITS)
        self._id_to_iv[nid] = iv
        self._id_to_vars[nid] = set()
        return iv                                  # value 필드에 그대로 쓰면 됨

    def register_fixed_id(self, nid: int,
                          iv: UnsignedIntegerInterval | None = None):
        """
        주석처럼 `symbolicAddress 101` 이 들어왔을 때 호출.
        이미 등록돼 있으면 그대로 두고, 없으면 Interval을 결정해 추가.
        """
        if nid not in self._id_to_iv:
            if iv is None:
                iv = UnsignedIntegerInterval(nid, nid, self.ADDR_BITS)
            self._id_to_iv[nid] = iv
            self._id_to_vars[nid] = set()

    # ───────────────────────────────── 변수-ID 바인딩
    def bind_var(self, var_name: str, nid: int):
        self._id_to_vars.setdefault(nid, set()).add(var_name)

    # ───────────────────────────────── 조회
    def get_interval(self, nid: int) -> UnsignedIntegerInterval:
        return self._id_to_iv[nid]

    def get_alias_set(self, nid: int) -> set[str]:
        return self._id_to_vars.get(nid, set())

    # ───────────────────────────────── ranged 할당 예시
    def alloc_range(self, start: int, end: int) -> int:
        """
        [start,end] Interval 로 묶인 새 ID 발급 후 ID 반환
        """
        nid = self.fresh_id()
        self._id_to_iv[nid] = UnsignedIntegerInterval(start, end, self.ADDR_BITS)
        self._id_to_vars[nid] = set()
        return nid

class ArrayVariable(Variables):
    """
    ▸ 정적/동적 배열 래퍼
    ▸ int·uint·bool 은 interval 로,
      address·string·bytes 등은 심볼/AddressManager 를 이용해 초기화
    """

    def __init__(self, identifier=None, base_type=None,
                 array_length=None,
                 value=None, isConstant=False, scope=None,
                 is_dynamic=False):
        super().__init__(identifier, value, isConstant, scope)

        self.typeInfo = SolType()
        self.typeInfo.typeCategory = "array"
        self.typeInfo.arrayBaseType = base_type
        self.typeInfo.arrayLength = array_length  # None → 동적
        self.typeInfo.isDynamicArray = is_dynamic
        self.elements: list[Variables | "ArrayVariable"] = []

    # models.py ― ArrayVariable  내부
    def _create_default_value(self, eid: str):
        """
        base_type 에 맞춰 'TOP' 값을 만들어 준다.
        """
        bt = self.typeInfo.arrayBaseType  # SolType | str
        # ─ address ──────────────────────────────────
        if (isinstance(bt, SolType) and bt.elementaryTypeName == "address") \
                or bt == "address":
            return UnsignedIntegerInterval(0, 2 ** 160 - 1, 160)

        # ─ bool ─────────────────────────────────────
        if (isinstance(bt, SolType) and bt.elementaryTypeName == "bool") \
                or bt == "bool":
            return BoolInterval(0, 1)  # TOP of bool

        # ─ int / uint ──────────────────────────────
        if isinstance(bt, SolType) and bt.elementaryTypeName.startswith("int"):
            w = bt.intTypeLength or 256
            return IntegerInterval(-(2 ** (w - 1)), 2 ** (w - 1) - 1, w)
        if isinstance(bt, SolType) and bt.elementaryTypeName.startswith("uint"):
            w = bt.intTypeLength or 256
            return UnsignedIntegerInterval(0, 2 ** w - 1, w)

        # ─ 그 밖의 타입(bytes,string,구조체 등) ───
        return f"symbol_{eid}"  # 마지막 보루

    # -----------------------------------------------------------------
    def get_or_create_element(self, idx: int):
        """
        동적 배열이면 idx 위치까지 0‥idx 의 모든 요소를 채워 넣으며,
        정적 배열이면 범위 체크만 수행한다.
        """
        if idx < 0:
            raise IndexError("negative index")

        # 동적 배열 → 필요하면 확장
        if self.typeInfo.isDynamicArray:
            while idx >= len(self.elements):  # auto-push
                eid = f"{self.identifier}[{len(self.elements)}]"
                new_elem = Variables(eid,
                                     self._create_default_value(eid),
                                     scope=self.scope,
                                     typeInfo=self.typeInfo.arrayBaseType)
                self.elements.append(new_elem)

        # 정적 배열 → 범위 검사
        if idx >= len(self.elements):
            raise IndexError(f"index {idx} out of range ({len(self.elements)})")

        return self.elements[idx]

    def _create_new_array_element(self, idx: int):
        """
        배열 push·동적-초기화 시 1칸짜리 child 를 만든다.
        ▸ base_type 이
            · elementary / address / bool → Variables
            · struct                    → StructVariable
            · 배열                       → (중첩) ArrayVariable
            · mapping                   → MappingVariable
            · enum                      → EnumVariable
        """
        eid = f"{self.identifier}[{idx}]"
        btype = self.typeInfo.arrayBaseType  # SolType | str

        # ─ elementary / address / bool ───────────────────────────────
        if isinstance(btype, SolType) and btype.typeCategory == "elementary":
            # 주소형
            if btype.elementaryTypeName == "address":
                val = UnsignedIntegerInterval(0, 2 ** 160 - 1, 160)
                return Variables(eid, val, scope=self.scope, typeInfo=btype)
            # uint / int / bool → ⊤ interval
            if btype.elementaryTypeName.startswith("uint"):
                bits = int(btype.elementaryTypeName[4:] or 256)
                val = UnsignedIntegerInterval(0, 2 ** bits - 1, bits)
                return Variables(eid, val, scope=self.scope, typeInfo=btype)
            if btype.elementaryTypeName.startswith("int"):
                bits = int(btype.elementaryTypeName[3:] or 256)
                val = IntegerInterval(-(2 ** (bits - 1)), 2 ** (bits - 1) - 1, bits)
                return Variables(eid, val, scope=self.scope, typeInfo=btype)
            if btype.elementaryTypeName == "bool":
                return Variables(eid, BoolInterval(0, 1), scope=self.scope, typeInfo=btype)
            # bytes/string 등
            return Variables(eid, f"symbol_{eid}", scope=self.scope, typeInfo=btype)

        # ─ struct ───────────────────────────────────────────────────
        if isinstance(btype, SolType) and btype.typeCategory == "struct":
            return StructVariable(eid, btype.structTypeName, scope=self.scope)

        # ─ enum ─────────────────────────────────────────────────────
        if isinstance(btype, SolType) and btype.typeCategory == "enum":
            return EnumVariable(eid, btype.enumTypeName, scope=self.scope)

        # ─ mapping ──────────────────────────────────────────────────
        if isinstance(btype, SolType) and btype.typeCategory == "mapping":
            return MappingVariable(eid,
                                   btype.mappingKeyType,
                                   btype.mappingValueType,
                                   scope=self.scope)

        # ─ 중첩 배열 ────────────────────────────────────────────────
        if isinstance(btype, SolType) and btype.typeCategory == "array":
            return ArrayVariable(eid,
                                 btype.arrayBaseType,
                                 btype.arrayLength,
                                 scope=self.scope,
                                 is_dynamic=btype.isDynamicArray)

        # fallback
        raise ValueError(f"Unhandled array base-type for {eid!r}")


    # ────────────────────────── public API ──────────────────────────
    def initialize_elements(self, init_iv: Interval):
        """int / uint / bool 전용 (추상화 도메인 사용)"""
        if self.typeInfo.isDynamicArray:
            return
        self._init_recursive(
            baseT=self.typeInfo.arrayBaseType,
            length=self.typeInfo.arrayLength or 0,
            build_val=lambda eid, et:
            Variables(eid, init_iv.copy() if hasattr(init_iv, "copy") else init_iv,
                      scope=self.scope, typeInfo=et)
        )

    def initialize_not_abstracted_type(self,
                                       sm: AddressSymbolicManager | None = None):
        """address / bytes / string 등 — address 는 fresh interval, 나머진 심볼"""
        if self.typeInfo.isDynamicArray:
            return

        def builder(eid, et):
            # address
            if (isinstance(et, SolType) and et.elementaryTypeName == "address") or et == "address":
                top = UnsignedIntegerInterval(0, 2 ** 160 - 1, 160)
                return Variables(eid, top, scope=self.scope, typeInfo=et)
            # 그 외 string/bytes … → 심볼
            return Variables(eid, f"symbol_{eid}", scope=self.scope, typeInfo=et)

        self._init_recursive(
            baseT=self.typeInfo.arrayBaseType,
            length=self.typeInfo.arrayLength or 0,
            build_val=builder
        )

    # ──────────────────────── private helper ────────────────────────
    def _init_recursive(self, *, baseT, length: int, build_val):
        """
        baseT : SolType 또는 문자열
        length: 정적 배열 길이
        build_val(eid:str, et) ➜ Variables 객체를 생성해 주는 콜백
        """
        for i in range(length):
            eid = f"{self.identifier}[{i}]"

            # ─ nested array -----------------------------------------------------------------
            if isinstance(baseT, SolType) and baseT.typeCategory == "array":
                sub_arr = ArrayVariable(
                    identifier=eid,
                    base_type=baseT.arrayBaseType,
                    array_length=baseT.arrayLength,
                    scope=self.scope
                )
                # recursion – baseT.arrayBaseType 에 따라 분기
                if self._is_abstractable(baseT.arrayBaseType):
                    dummy = IntegerInterval.bottom() \
                        if str(baseT.arrayBaseType.elementaryTypeName).startswith("int") \
                        else UnsignedIntegerInterval.bottom()
                    sub_arr.initialize_elements(dummy)
                else:
                    sub_arr.initialize_not_abstracted_type(sm=None)
                self.elements.append(sub_arr)
                continue
            # ─ leaf element -----------------------------------------------------------------
            self.elements.append(build_val(eid, baseT))

    @staticmethod
    def _is_abstractable(bt):
        """int / uint / bool 이면 True"""
        if isinstance(bt, SolType):
            et = bt.elementaryTypeName
        else:
            et = str(bt)
        return et.startswith("int") or et.startswith("uint") or et == "bool"

class MappingVariable(Variables):
    def __init__(self, identifier=None, key_type=None, value_type=None, value=None,
                 isConstant=False, scope=None):
        super().__init__(identifier, value, isConstant, scope)
        self.typeInfo = SolType()
        self.typeInfo.typeCategory = 'mapping'
        self.typeInfo.mappingKeyType = key_type    # SolType 객체
        self.typeInfo.mappingValueType = value_type # SolType 객체
        self.mapping = {}


    # ────────────────────────────────────────────────
    # 값-생성 전용 private 헬퍼
    # ────────────────────────────────────────────────
    def _make_value(self, sub_id: str, sol_t: SolType) :
        """
        mappingValueType(SolType) 을 보고 알맞은 객체를 만들어 준다.
        숫자/불린 ⇒ ⊥ interval, 주소 ⇒ TOP interval, 복합 타입 ⇒ 재귀 생성
        """
        # 1) 배열 --------------------------------------------------------
        if sol_t.typeCategory == "array":
            arr = ArrayVariable(
                identifier   = sub_id,
                base_type    = sol_t.arrayBaseType,
                array_length = sol_t.arrayLength,
                is_dynamic   = sol_t.isDynamicArray,
                scope        = self.scope,
            )
            arr.initialize_not_abstracted_type()   # 내부까지 재귀 초기화
            return arr

        # 2) 매핑 --------------------------------------------------------
        if sol_t.typeCategory == "mapping":
            return MappingVariable(
                identifier  = sub_id,
                key_type    = sol_t.mappingKeyType,
                value_type  = sol_t.mappingValueType,
                scope       = self.scope,
            )

        # 3) 구조체 ------------------------------------------------------
        if sol_t.typeCategory == "struct":
            sv = StructVariable(identifier=sub_id,
                                struct_type=sol_t.structTypeName,
                                scope=self.scope)
            # 필요하다면 여기서 멤버 재귀 초기화
            return sv

        # 4) elementary -------------------------------------------------
        v = Variables(identifier=sub_id, scope=self.scope)
        v.typeInfo = sol_t
        et = sol_t.elementaryTypeName

        if et.startswith("int"):
            bits = sol_t.intTypeLength or 256
            v.value = IntegerInterval.bottom(bits)           # ⊥ interval
        elif et.startswith("uint"):
            bits = sol_t.intTypeLength or 256
            v.value = UnsignedIntegerInterval.bottom(bits)   # 0 ~ 2ᵇⁱᵗˢ-1
        elif et == "bool":
            v.value = BoolInterval.bottom()
        elif et == "address":
            v.value = UnsignedIntegerInterval(0, 2**160 - 1, 160)   # TOP 주소
        else:                               # string / bytes 등
            v.value = f"symbol_{sub_id}"
        return v

    # ────────────────────────────────────────────────
    # public API : get_or_create(key_val)  (기존 get_mapping 대체)
    # ────────────────────────────────────────────────
    def get_or_create(self, key_val) -> Variables:
        """
        키가 없으면 value_type 에 맞춰 **자동 생성** 후 반환
        """
        if key_val not in self.mapping:
            sub_id = f"{self.identifier}[{key_val}]"
            new_var = self._make_value(sub_id, self.typeInfo.mappingValueType)
            self.mapping[key_val] = new_var
        return self.mapping[key_val]

    def get_default_interval_for_type(self, sol_type):
        # 예시 구현: elementary int/uint/bool만 처리
        if sol_type.typeCategory == 'elementary':
            etype = sol_type.elementaryTypeName
            if etype.startswith("int"):
                return IntegerInterval(float('-inf'), float('inf'), sol_type.intTypeLength)
            elif etype.startswith("uint"):
                return UnsignedIntegerInterval(0, float('inf'), sol_type.intTypeLength)
            elif etype == "bool":
                return BoolInterval(False, True)
        # 기타 타입일 경우 None
        return None

class StructDefinition:
    def __init__(self, struct_name):
        self.struct_name = struct_name
        self.members = []

    def add_member(self, var_name, type_obj):
        self.members.append({'member_name' : var_name, 'member_type' : type_obj})

# utils.py  (발췌) ─ StructVariable  전체

class StructVariable(Variables):
    """
    구조체 변수를 나타내는 래퍼.
    ─ members : { fieldName(str) : Variables / ArrayVariable / MappingVariable … }
    """

    def __init__(
        self,
        identifier: str | None = None,
        struct_type: str | None = None,
        value=None,
        isConstant: bool = False,
        scope: str | None = None,
    ):
        super().__init__(identifier, value, isConstant, scope)

        self.typeInfo = SolType()
        self.typeInfo.typeCategory   = "struct"
        self.typeInfo.structTypeName = struct_type       # 구조체 이름
        self.members: dict[str, Variables] = {}          # field → variable ­obj

    # ────────────────────────────────────────────────────────────
    # 초기화
    # ------------------------------------------------------------------
    def initialize_struct(
        self,
        struct_def: StructDefinition,
        sm: "AddressSymbolicManager | None" = None,
    ):
        """
        struct_def.members :
            [{ "member_name": str, "member_type": SolType }, ... ]
        - sm : AddressSymbolicManager (주소 타입이면 fresh interval 발급용)
        """

        def _make_var(var_id: str, sol_t: SolType) -> Variables:
            """SolType → 적절한 Variables/ArrayVariable/MappingVariable 생성"""

            # 1) 배열  ---------------------------------------------------
            if sol_t.typeCategory == "array":
                arr = ArrayVariable(
                    identifier   = var_id,
                    base_type    = sol_t.arrayBaseType,
                    array_length = sol_t.arrayLength,
                    is_dynamic   = sol_t.isDynamicArray,
                    scope        = self.scope,
                )
                # base type이 elementary 인지 확인 후 초기화
                bt = sol_t.arrayBaseType
                if isinstance(bt, SolType):
                    # 주소 / string / bytes / bool / int 등 판단
                    if bt.elementaryTypeName in ("int",) or bt.elementaryTypeName.startswith("int"):
                        bits = bt.intTypeLength or 256
                        arr.initialize_elements(IntegerInterval.bottom(bits))
                    elif bt.elementaryTypeName in ("uint",) or bt.elementaryTypeName.startswith("uint"):
                        bits = bt.intTypeLength or 256
                        arr.initialize_elements(UnsignedIntegerInterval.bottom(bits))
                    elif bt.elementaryTypeName == "bool":
                        arr.initialize_elements(BoolInterval.bottom())
                    else:          # address / bytes / string 등
                        arr.initialize_not_abstracted_type(sm=sm)
                else:
                    # 다차원 배열(배열의 base 가 또 SolType(array)) → 재귀적으로 helper가 처리
                    arr.initialize_not_abstracted_type(sm=sm)
                return arr

            # 2) 매핑  ---------------------------------------------------
            if sol_t.typeCategory == "mapping":
                return MappingVariable(
                    identifier  = var_id,
                    key_type    = sol_t.mappingKeyType,
                    value_type  = sol_t.mappingValueType,
                    scope       = self.scope,
                )

            # 3) (중첩) 구조체  ------------------------------------------
            if sol_t.typeCategory == "struct":
                sv = StructVariable(identifier=var_id,
                                    struct_type=sol_t.structTypeName,
                                    scope=self.scope)
                # struct 정의가 이미 ContractCFG.structDefs 에 저장돼 있다고 가정
                # **여기서 struct_def를 다시 찾아 재귀 초기화 할 수도 있음**
                return sv  # 값은 호출 측에서 후처리

            # 4) elementary  --------------------------------------------
            v = Variables(identifier=var_id, scope=self.scope)
            v.typeInfo = sol_t

            et = sol_t.elementaryTypeName
            if et.startswith("int"):
                bits = sol_t.intTypeLength or 256
                v.value = IntegerInterval.bottom(bits)
            elif et.startswith("uint"):
                bits = sol_t.intTypeLength or 256
                v.value = UnsignedIntegerInterval.bottom(bits)
            elif et == "bool":
                v.value = BoolInterval.bottom()
            elif et == "address":
                v.value = UnsignedIntegerInterval(0, 2**160 - 1, 160)
            else:
                # string / bytes / 기타
                v.value = f"symbol_{var_id}"
            return v

        # ─ 실제 멤버 생성 ------------------------------------------------
        for mem in struct_def.members:
            m_name: str      = mem["member_name"]
            m_type: SolType  = mem["member_type"]

            self.members[m_name] = _make_var(f"{self.identifier}.{m_name}", m_type)

    # 디버깅용 표현
    def __repr__(self):
        mem_str = ", ".join(f"{k}:{v.value}" for k, v in self.members.items())
        return f"StructVariable({self.identifier}){{{mem_str}}}"

class EnumDefinition:
    def __init__(self, enum_name):
        self.enum_name = enum_name
        self.members = []  # 멤버들의 리스트

    def add_member(self, member_name):
        if member_name not in self.members:
            self.members.append(member_name)
        else:
            raise ValueError(f"Member '{member_name}' is already defined in enum '{self.enum_name}'.")

    def get_member(self, index):
        return self.members[index]


class EnumVariable(Variables):
    def __init__(self, identifier=None, enum_type=None, value=None, isConstant=False, scope=None):
        super().__init__(identifier, value, isConstant, scope)
        self.typeInfo = SolType()
        self.typeInfo.typeCategory = 'enum'
        self.typeInfo.enumTypeName = enum_type  # 열거형 이름
        self.members = {}  # 멤버 변수들: 멤버명 -> 정수 값 (열거형의 각 멤버는 정수 값에 매핑됨)
        self.value = None  # 현재 설정된 멤버의 이름
        self.valueIndex = None

    def set_member_value(self, member_name):
        """
        열거형 변수의 값을 특정 멤버로 설정합니다.
        :param member_name: 열거형 멤버 이름
        """
        if member_name in self.members:
            self.current_value = member_name
            self.value = self.members[member_name]  # 멤버의 정수 값을 변수의 값으로 설정
        else:
            raise ValueError(f"Member '{member_name}' not found in enum '{self.typeInfo.enumTypeName}'.")

    def get_member_value(self):
        """
        열거형 변수의 현재 값을 반환합니다.
        :return: 현재 설정된 멤버의 이름
        """
        return self.current_value