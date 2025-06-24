class Statement:
    def __init__(self, statement_type, **kwargs):
        self.statement_type = statement_type
        self.src_line       = kwargs.get("src_line")

        # ───────────── statement-type별 전용 필드 ─────────────
        if statement_type == "variableDeclaration":
            self.type_obj  = kwargs.get("type_obj")
            self.var_name  = kwargs.get("var_name")
            self.init_expr = kwargs.get("init_expr")

        elif statement_type == "assignment":
            self.left     = kwargs.get("left")
            self.operator = kwargs.get("operator")   # '=', '+=', …
            self.right    = kwargs.get("right")

        elif statement_type == "functionCall":
            self.function_expr = kwargs.get("function_expr")

        elif statement_type == "return":
            self.return_expr = kwargs.get("return_expr")

        elif statement_type == "revert":
            self.identifier     = kwargs.get("identifier")
            self.string_literal = kwargs.get("string_literal")
            self.arguments      = kwargs.get("arguments")

        # ------ 단항(++x, --y, delete z)
        elif statement_type == "unary":
            self.operator = kwargs.get("operator")   # '++' | '--' | 'delete'
            self.operand  = kwargs.get("operand")    # Expression

        # ------ 흐름 제어(break / continue) ------
        elif statement_type in {"break", "continue"}:
            # 별도 데이터 필요 없음 – src_line 만 기록
            pass

        else:
            raise ValueError(f"Unsupported statement_type '{statement_type}'")





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