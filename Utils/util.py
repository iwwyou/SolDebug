from Utils.Interval import *

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
        elif statement_type == 'assignment':
            self.left = kwargs.get('left')        # 좌변 Expression
            self.operator = kwargs.get('operator')  # 할당 연산자 (예: '=', '+=', '-=' 등)
            self.right = kwargs.get('right')      # 우변 Expression
        elif statement_type == "functionCall" :
            self.function_expr = kwargs.get('function_expr')
        elif statement_type == 'return':
            self.return_expr = kwargs.get('return_expr')
        elif statement_type == 'revert' :
            self.identifier = kwargs.get('identifier')
            self.string_literal = kwargs.get('string_literal')
            self.arguments = kwargs.get('arguments')



class Expression:
    def __init__(self, left=None, operator=None, right=None, identifier=None, literal=None, var_type=None,
                 function=None, arguments=None, named_arguments=None, base=None, access=None,
                 index=None, start_index=None, end_index=None, member=None, options=None,
                 type_name=None, expression=None, condition=None, true_expr=None, false_expr=None,
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
        self.type_name = type_name      # 타입 변환의 대상 타입 이름 (문자열)
        self.expression = expression    # 변환될 표현식 또는 단일 표현식 (Expression)
        self.condition = condition      # 조건식 (삼항 연산자용) (Expression)
        self.true_expr = true_expr      # 조건식이 참일 때의 표현식 (Expression)
        self.false_expr = false_expr    # 조건식이 거짓일 때의 표현식 (Expression)
        self.is_postfix = is_postfix    # 후위 연산자 여부 (Boolean)
        self.elements = elements        # 튜플 또는 배열의 요소들 (리스트)
        self.expr_type = expr_type      # 표현식의 타입 (예: 'int', 'uint', 'bool')
        self.type_length = type_length  # 타입의 길이 (예: 256)
        self.context = context


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


class GlobalVariable(Variables):
    def __init__(self, identifier=None, isConstant=False, scope=None, base=None, member=None, value=None, typeInfo=None):
        super().__init__(identifier, value, isConstant, scope)
        self.base = base
        self.member = member
        self.value = value  #Interval이 될수도 있고 그냥 address 1 이렇게 될수도 있음
        self.typeInfo = SolType()


class ArrayVariable(Variables):
    def __init__(self, identifier=None, base_type=None, array_length=None, is_dynamic=False, value=None,
                 isConstant=False, scope=None):
        super().__init__(identifier, value, isConstant, scope)
        self.typeInfo = SolType()
        self.typeInfo.typeCategory = 'array'
        self.typeInfo.arrayBaseType = base_type  # SolType 객체 (배열의 기본 타입이 배열일 수도 있음)
        self.typeInfo.arrayLength = array_length
        self.typeInfo.isDynamicArray = is_dynamic
        self.elements = []  # 배열의 요소들: Variables 객체의 리스트

    def initialize_elements(self, initial_interval):
        """
        정적 배열의 요소들을 초기화하는 메소드.
        기본 타입이 배열인 경우 재귀적으로 요소들을 초기화합니다.
        """
        if self.typeInfo.isDynamicArray :
            return

        if self.typeInfo.arrayLength is not None:
            for i in range(self.typeInfo.arrayLength):
                elem_id = f"{self.identifier}[{i}]"
                # 하위 타입이 또 다른 배열이면 재귀적으로 ArrayVariable 생성
                if (isinstance(self.typeInfo.arrayBaseType, SolType) and
                        self.typeInfo.arrayBaseType.typeCategory == 'array'):

                    sub_array = ArrayVariable(
                        identifier=elem_id,
                        base_type=self.typeInfo.arrayBaseType.arrayBaseType,
                        array_length=self.typeInfo.arrayBaseType.arrayLength,
                        scope=self.scope
                    )
                    sub_array.initialize_elements(initial_interval)
                    self.elements.append(sub_array)
                else:
                    # 기본 타입인 경우 Variables 객체로 요소 생성
                    element_var = Variables(identifier=elem_id,
                                            value=initial_interval,
                                            isConstant=False,
                                            scope=self.scope,
                                            typeInfo=self.typeInfo.arrayBaseType)

                    self.elements.append(element_var)

    def initialize_elements_of_not_abstracted_type (self, var_name) :
        if self.typeInfo.arrayLength is not None:
            for i in range(self.typeInfo.arrayLength):
                elem_id = f"{self.identifier}[{i}]"
                # 하위 타입이 또 다른 배열이면 재귀적으로 ArrayVariable 생성
                if (isinstance(self.typeInfo.arrayBaseType, SolType) and
                        self.typeInfo.arrayBaseType.typeCategory == 'array'):

                    value_symbol = str("arraySymbol" + var_name + i)

                    sub_array = ArrayVariable(
                        identifier=elem_id,
                        base_type=self.typeInfo.arrayBaseType.arrayBaseType,
                        array_length=self.typeInfo.arrayBaseType.arrayLength,
                        scope=self.scope
                    )
                    sub_array.initialize_elements(value_symbol)
                    self.elements.append(sub_array)
                else:
                    # 기본 타입인 경우 Variables 객체로 요소 생성
                    element_var = Variables(identifier=elem_id,
                                            value=str("symbol" + var_name+ i),
                                            isConstant=False,
                                            scope=self.scope,
                                            typeInfo=self.typeInfo.arrayBaseType)
                    self.elements.append(element_var)


class MappingVariable(Variables):
    def __init__(self, identifier=None, key_type=None, value_type=None, value=None,
                 isConstant=False, scope=None):
        super().__init__(identifier, value, isConstant, scope)
        self.typeInfo = SolType()
        self.typeInfo.typeCategory = 'mapping'
        self.typeInfo.mappingKeyType = key_type    # SolType 객체
        self.typeInfo.mappingValueType = value_type # SolType 객체
        self.mapping = {}  # key(str) -> Variables 객체

    def add_mapping(self, key_str, value_var):
        """
        매핑에 새로운 키-값 쌍을 추가합니다.
        key_str: 문자열 형태의 키 (identifier)
        value_var: Variables 객체 (값)
        """

        if not isinstance(value_var, Variables):
            raise ValueError(f"Invalid value type for mapping: {value_var} is not a Variables object.")

        # 타입 검증 로직 (필요하다면 여기서 더 정교하게 할 수 있음)
        # 여기서는 기본 타입 checking만 간단히 예시로 유지
        expected_type = self.typeInfo.mappingValueType.elementaryTypeName
        actual_type = value_var.typeInfo.elementaryTypeName if value_var.typeInfo else None

        # 만약 elementary type인 경우 타입 이름이 맞는지 확인
        if self.typeInfo.mappingValueType.typeCategory == 'elementary':
            if actual_type != expected_type:
                raise TypeError(f"Value type mismatch: Expected {expected_type}, got {actual_type}")

        self.mapping[key_str] = value_var

    def get_mapping(self, key_str):
        """
        주어진 문자열 키에 해당하는 Variables 객체를 반환합니다.
        키가 없으면 기본값(Interval bottom 등)을 가진 Variables를 생성해서 반환할 수도 있음.
        """
        if key_str in self.mapping:
            return self.mapping[key_str]
        else:
            # 키가 없는 경우 새로운 Variables 생성 (기본 Interval)
            # 여기서 기본 interval을 만드는 헬퍼 함수가 있다고 가정 (예: get_default_interval)
            default_interval = self.get_default_interval_for_type(self.typeInfo.mappingValueType)
            new_var = Variables(identifier=f"{self.identifier}[{key_str}]",
                                value=default_interval,
                                scope=self.scope,
                                typeInfo=self.typeInfo.mappingValueType)
            self.mapping[key_str] = new_var
            return new_var

    def remove_mapping(self, key_str):
        if key_str in self.mapping:
            del self.mapping[key_str]
        else:
            raise KeyError(f"Key '{key_str}' not found in the mapping.")

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


class StructVariable(Variables):
    def __init__(self, identifier=None, struct_type=None, value=None, isConstant=False, scope=None):
        super().__init__(identifier, value, isConstant, scope)
        self.typeInfo = SolType()
        self.typeInfo.typeCategory = 'struct'
        self.typeInfo.structTypeName = struct_type  # 구조체 이름
        self.members = {}  # 멤버 변수들: 필드명 -> Variables 객체

    def initialize_struct(self, struct_def):
        for member in struct_def.members :
            m_name = member['member_name']
            m_type = member['member_type']
            variable_obj = None

            if m_type.typeCategory == 'array':
                variable_obj = ArrayVariable(identifier=m_name, base_type=m_type.arrayBaseType,
                                             array_length=m_type.arrayLength)

                baseType = m_type.arrayBaseType
                # 배열 요소 초기화
                if baseType.startswith('int'):
                    length = int(baseType[3:]) if baseType != "int" else 256
                    variable_obj.initialize_elements(IntegerInterval.bottom(length))  # 기본 interval 설정
                elif baseType.startswith('uint'):
                    length = int(baseType[4:]) if baseType != "int" else 256
                    variable_obj.initialize_elements(UnsignedIntegerInterval.bottom(length))  # 기본 interval 설정
                elif baseType == 'bool':
                    variable_obj.initialize_elements(BoolInterval.bottom())
                elif baseType in ["address", "address payable", "string", "bytes", "Byte", "Fixed", "Ufixed"]:
                    variable_obj.initialize_elements_of_not_abstracted_type(m_name)

            elif m_type.typeCategory == 'mapping': # 이거 좀 수정 필요
                variable_obj = MappingVariable(identifier=m_name,
                                               key_type=m_type.mappingKeyType,
                                               value_type=m_type.mappingValueType)
            elif m_type.typeCategory == 'elementary' :
                variable_obj = Variables(identifier=m_name)
                variable_obj.typeInfo = m_type

                if m_type.startswith("int") :
                    length = int(m_type[3:]) if m_type != "int" else 256  # int 타입의 길이 (기본값은 256)
                    variable_obj.value = IntegerInterval.bottom(length)  # int의 기본 범위 반환
                elif m_type.startswith("uint") :
                    length = int(m_type[4:]) if m_type != "int" else 256  # int 타입의 길이 (기본값은 256)
                    variable_obj.value = UnsignedIntegerInterval.bottom(length)  # int의 기본 범위 반환
                elif m_type.startswith("bool") :
                    variable_obj.value = BoolInterval.bottom()
                    variable_obj.value = str("structSymbol" +struct_def.struct_name + "memberSymbol" + m_name)

class StructDefinition:
    def __init__(self, struct_name):
        self.struct_name = struct_name
        self.members = []

    def add_member(self, var_name, type_obj):
        self.members.append({'member_name' : var_name, 'member_type' : type_obj})

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

        # 기타 필요한 속성 추가 가능
