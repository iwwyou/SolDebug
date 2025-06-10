from Domain.Variable import *
from Interpreter.IR import *
from Analyzer.ContractAnalyzer import *
from Utils.CFG import *
import re
from decimal import Decimal, InvalidOperation

class Semantics :

    def __init__(self, analyzer: ContractAnalyzer):
        """
        Semantics 인스턴스는 ContractAnalyzer 하나만 품고,
        나머지 속성·헬퍼는 전부 위임(propagation)한다.
        """
        self.an = analyzer  # composition
        self.sm = analyzer.sm  # 짧게 접근할 일 많으니 별칭
        # 필요한 순간마다 새로 복사/계산하는 유틸도 여기서 import

    def evaluate_expression(self, expr: Expression, variables, callerObject=None, callerContext=None):
        if expr.context == "LiteralExpContext":
            return self.evaluate_literal_context(expr, variables, callerObject, callerContext)
        elif expr.context == "IdentifierExpContext":
            return self.evaluate_identifier_context(expr, variables, callerObject, callerContext)
        elif expr.context == 'MemberAccessContext':
            return self.evaluate_member_access_context(expr, variables, callerObject, callerContext)
        elif expr.context == "IndexAccessContext":
            return self.evaluate_index_access_context(expr, variables, callerObject, callerContext)
        elif expr.context == "TypeConversion":
            return self.evaluate_type_conversion_context(expr, variables, callerObject, callerContext)
        elif expr.context == "ConditionalExpContext":
            return self.evaluate_conditional_expression_context(expr, variables, callerObject, callerContext)
        elif expr.context == "InlineArrayExpression":
            return self.evaluate_inline_array_expression_context(expr, variables, callerObject, callerContext)
        elif expr.context == "FunctionCallContext":
            return self.evaluate_function_call_context(expr, variables, callerObject, callerContext)
        elif expr.context == "TupleExpressionContext":
            return self.evaluate_tuple_expression_context(expr, variables,
                                                          callerObject, callerContext)
        elif expr.context == 'AssignmentOpContext':
            return self.evaluate_assignment_expression(expr, variables,
                                                       callerObject, callerContext)
        elif expr.context == "LiteralSubDenomination":
            return self.evaluate_literal_with_subdenomination_context(
                expr, variables, callerObject, callerContext)
        elif expr.context == "NewExpContext":
            return self.evaluate_new_expression_context(expr, variables,
                                                        callerObject, callerContext)

        # 단항 연산자
        if expr.operator in ['-', '!', '~'] and expr.expression:
            return self.evaluate_unary_operator(expr, variables, callerObject, callerContext)

        # 이항 연산자
        if expr.left is not None and expr.right is not None:
            return self.evaluate_binary_operator(expr, variables, callerObject, callerContext)

    def evaluate_new_expression_context(self, expr: Expression,
                                        variables, callerObject=None, callerContext=None):
        """
        ▸ expr.type_name  : visitNewExp() 에서 채워 둔 SolType 인스턴스
        ▸ 반환값          : 새로 만든 ArrayVariable / MappingVariable /
                           StructVariable / Variables (elementary) /
                           심볼릭 address 등
        """

        sol_t: SolType = expr.typeName  # 타입 정보
        fresh_id = f"new_{id(expr)}"  # 유니크한 식별자

        # ── (A) 배열 ───────────────────────────────────────────────
        if sol_t.typeCategory == "array":
            arr = ArrayVariable(
                fresh_id,
                base_type=sol_t.arrayBaseType,
                array_length=sol_t.arrayLength,
                is_dynamic=sol_t.isDynamicArray,
                scope="memory"
            )

            # ⬇ static-method 직접 호출
            if ArrayVariable._is_abstractable(sol_t.arrayBaseType):
                dummy = (IntegerInterval.bottom()
                         if str(sol_t.arrayBaseType.elementaryTypeName).startswith("int")
                         else UnsignedIntegerInterval.bottom())
                arr.initialize_elements(dummy)
            else:
                arr.initialize_not_abstracted_type()

            return arr

        # ── (B) 매핑 ───────────────────────────────────────────────
        if sol_t.typeCategory == "mapping":
            return MappingVariable(fresh_id,
                                   key_type=sol_t.mappingKeyType,
                                   value_type=sol_t.mappingValueType,
                                   scope="memory")

        # ── (C) 구조체 ─────────────────────────────────────────────
        if sol_t.typeCategory == "struct":
            return StructVariable(fresh_id, sol_t.structTypeName, scope="memory")

        # ── (D) 컨트랙트 new Foo()  → 심볼릭 address ───────────────
        if sol_t.typeCategory == "userDefined" :
            # “fresh address”를 160-bit Interval TOP 로 두고,
            # 필요하면 AddressSymbolicManager 로 별도 관리
            return UnsignedIntegerInterval(0, 2 ** 160 - 1, 160)

        # ── (E) 기본형 new uint[](...) 처럼 size 없는 array 등
        #        또는 new bytes(...) – 메모리 상 동적 할당
        if sol_t.typeCategory == "elementary":
            return f"symbolic_{fresh_id}"

        raise ValueError(f"unsupported 'new' type: {sol_t!r}")

    # ───────────────────── evaluate_literal_context ──────────────
    def evaluate_literal_context(
            self,
            expr: Expression,
            variables: dict[str, Variables],
            callerObject: Variables | ArrayVariable | MappingVariable | None = None,
            callerContext: str | None = None):

        lit = expr.literal  # 예: "123", "0x1A", "true", ...
        ety = expr.expr_type  # 'uint'·'int'·'bool'·'string'·'address' 등
        _NUM_SCI = re.compile(r"^[+-]?\d+([eE][+-]?\d+)$")  # 1e8, 2E+18 …

        def _to_scalar_int(txt: str) -> int:
            """
            10·16·8진수(+부호) + decimal scientific notation → int 로 변환.
            """
            try:
                return int(txt, 0)  # 0x… / 0o… / plain decimal
            except ValueError:
                pass

        def _parse_maybe_int(txt: str):
            """10·16·8진수 또는 지수표기를 int 로 반환. 실패하면 None."""
            # ➊ 0x / 0o / decimal
            try:
                return int(txt, 0)
            except ValueError:
                pass

            # ➋ scientific notation
            if _NUM_SCI.match(txt):
                try:
                    return int(Decimal(txt))
                except (InvalidOperation, ValueError):
                    pass
            return None

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
            maybe_int = _parse_maybe_int(lit)
            if maybe_int is not None:
                # ▶ 사실은 숫자!  → uint256 interval 로 취급
                return UnsignedIntegerInterval(maybe_int, maybe_int, 256)
            return lit  # 진짜 문자열이면 그대로 심볼릭

        # 기타 타입
        raise ValueError(f"Unsupported literal expr_type '{ety}'")

    def evaluate_identifier_context(self, expr: Expression, variables, callerObject=None, callerContext=None):
        ident_str = expr.identifier

        # callerObject가 있는 경우
        if callerObject is not None:
            if isinstance(callerObject, ArrayVariable):
                if ident_str not in variables:
                    raise ValueError(f"Index identifier '{ident_str}' not found.")

                idx_var_obj = variables[ident_str]
                iv = idx_var_obj.value  # Unsigned/IntegerInterval …

                # ── (A) 인덱스가 확정(singleton) ────────────────────────
                if self._is_interval(iv) and not iv.is_bottom() and iv.min_value == iv.max_value:
                    idx = iv.min_value
                    if idx < 0:
                        raise IndexError(f"Negative index {idx} for array '{callerObject.identifier}'")

                    if idx >= len(callerObject.elements):
                        # ❗ 요소가 아직 없음 → base-type 의 bottom 값만 돌려준다
                        base_t = callerObject.typeInfo.arrayBaseType
                        return self._bottom_from_soltype(base_t)
                    return callerObject.elements[idx]

                # ── (B) 불확정(bottom 또는 [l,r] 범위) ─────────────────
                #      ⇒  배열 모든 요소의 join 을 반환
                if callerObject.elements:
                    joined = None
                    for elem in callerObject.elements:
                        val = getattr(elem, "value", elem)  # 스칼라 / 복합 둘 다 지원
                        joined = val if joined is None else joined.join(val)
                    return joined

                # 배열이 비어 있으면 base-type 에 맞는 ⊥ 반환
                base_t = callerObject.typeInfo.arrayBaseType
                if base_t.elementaryTypeName.startswith("uint"):
                    bits = base_t.intTypeLength or 256
                    return UnsignedIntegerInterval.bottom(bits)
                if base_t.elementaryTypeName.startswith("int"):
                    bits = base_t.intTypeLength or 256
                    return IntegerInterval.bottom(bits)
                if base_t.elementaryTypeName == "bool":
                    return BoolInterval.bottom()
                # 주소/bytes/string 등은 symbol 로
                return f"symbolic_{callerObject.identifier}[<unk>]"

            elif isinstance(callerObject, StructVariable):
                if ident_str not in callerObject.members:
                    raise ValueError(f"member identifier '{ident_str}' not found in struct variables.")

                var = callerObject.members[ident_str]

                if isinstance(var, Variables):  # int, uint, bool이면 interval address, string이면 symbol을 리턴
                    return var.value
                else:  # ArrayVariable, StructVariable
                    return var  # var 자체를 리턴 (배열, 다른 구조체일 수 있음)

            elif isinstance(callerObject, EnumDefinition):
                for enumMemberIndex in range(len(callerObject.members)):
                    if ident_str == callerObject.members[enumMemberIndex]:
                        return enumMemberIndex

            # ContractAnalyzer.evaluate_identifier_context 내부

            elif isinstance(callerObject, MappingVariable):
                # ── ① key 결정 ──────────────────────────────────
                if ident_str in variables:  # ident_str == 변수명
                    key_var = variables[ident_str]
                    val = getattr(key_var, "value", key_var)
                    # ★ 주소형 판별을 elementaryTypeName 으로
                    is_address = (
                            hasattr(key_var, "typeInfo") and
                            getattr(key_var.typeInfo, "elementaryTypeName", None) == "address"
                    )

                    if hasattr(val, "min_value"):
                        if is_address:
                            key_val = key_var.identifier  # "msg.sender" 그대로
                        elif val.min_value == val.max_value:  # 숫자·bool 싱글톤
                            key_val = str(val.min_value)
                        else:
                            key_val = key_var.identifier  # 여전히 TOP
                    else:
                        key_val = key_var.identifier  # string·bool 등
                else:
                    # ───── 리터럴 키 ────────────────────────────
                    try:
                        key_val = str(int(ident_str, 0))
                    except ValueError:
                        key_val = ident_str

                # ── ③ 매핑 엔트리 가져오거나 생성 ─────────────
                if key_val not in callerObject.mapping:
                    callerObject.mapping[key_val] = self._create_new_mapping_value(
                        callerObject, key_val
                    )
                mvar = callerObject.mapping[key_val]
                # ── ④ 반환 규칙 ────────────────────────────
                if isinstance(mvar, (StructVariable, ArrayVariable, MappingVariable)):
                    return mvar
                else:
                    return mvar.value
            else:
                raise ValueError(f"This '{ident_str}' may not be included in enum def '{callerObject.enum_name}'")

        # callerObject가 없고 callerContext는 있는 경우
        if callerContext is not None:
            if callerContext == "MemberAccessContext":  # base에 대한 접근
                if ident_str in variables:
                    return variables[ident_str]  # MappingVariable, StructVariable 자체를 리턴
                elif ident_str in ["block", "tx", "msg", "address", "code"]:
                    return ident_str  # block, tx, msg를 리턴
                elif ident_str in self.contract_cfgs[self.current_target_contract].enumDefs:  # EnumDef 리턴
                    return self.contract_cfgs[self.current_target_contract].enumDefs[ident_str]
                else:
                    raise ValueError(f"This '{ident_str}' is may be array or struct but may not be declared")
            elif callerContext == "IndexAccessContext":  # base에 대한 접근
                if ident_str in variables:
                    return variables[ident_str]  # ArrayVariable, MappingVariable 자체를 리턴

        # callerContext, callerObject 둘다 없는 경우
        if ident_str in variables:  # variables에 있으면
            return variables[ident_str].value  # 해당 value 리턴
        else:
            raise ValueError(f"This '{ident_str}' is may be elementary variable but may not be declared")

    def evaluate_member_access_context(
            self,
            expr: Expression,
            variables: dict[str, Variables],
            callerObject: Variables | None = None,
            callerContext: str | None = None):

        baseVal = self.evaluate_expression(expr.base, variables, None,
                                           "MemberAccessContext")
        member = expr.member
        # ──────────────────────────────────────────────────────────────
        # 1. Global-var (block / msg / tx)
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, str):
            if baseVal in {"block", "msg", "tx"}:
                # 0) 함수-env 에 이미 변수로 들어와 있나?
                full_name = f"{baseVal}.{member}"
                if isinstance(callerObject, MappingVariable):
                    if full_name not in callerObject.mapping:
                        callerObject.mapping[full_name] = self._create_new_mapping_value(
                            callerObject, full_name)
                    entry = callerObject.mapping[full_name]
                    return entry.value if hasattr(entry, "value") else entry

                else:
                    if full_name in variables:  # ← added
                        return variables[full_name].value  # (Variables → 값))
                    else:
                        raise ValueError(f"There is no global variable in function")

            if baseVal.startswith("type(") and member == "max":
                inner = baseVal[5:-1].strip()  # "uint256", "int224", "address", "MyERC20", ...
                m = member  # 읽기 편하게 별도 변수로

                if inner.startswith("uint") or inner.startswith("int"):
                    signed = inner.startswith("int")
                    bits_txt = inner.lstrip("uintint")  # '' 면 기본 256
                    bits = int(bits_txt) if bits_txt else 256
                    if signed:
                        i_min = -2 ** (bits - 1)
                        i_max = 2 ** (bits - 1) - 1
                        if m == "max":
                            return IntegerInterval(i_max, i_max, bits)
                        elif m == "min":
                            return IntegerInterval(i_min, i_min, bits)
                    else:
                        u_min = 0
                        u_max = 2 ** bits - 1
                        if m == "max":
                            return UnsignedIntegerInterval(u_max, u_max, bits)
                        elif m == "min":
                            return UnsignedIntegerInterval(u_min, u_min, bits)

                    # ---- address ------------------------------------------------------
                if inner == "address":
                    if m == "max":
                        return UnsignedIntegerInterval(2 ** 160 - 1, 2 ** 160 - 1, 160)
                    if m == "min":
                        return UnsignedIntegerInterval(0, 0, 160)

                    # ---- bytes<M>  (고정 길이) ----------------------------------------
                if inner.startswith("bytes") and inner != "bytes":
                    # 컴파일 타임 바이트 시퀀스 최대/최소 → 심볼릭 문자열이면 충분
                    return f"{inner}.{m}"  # 예: "bytes32.max"

                    # ---- 컨트랙트 타입  (MyERC20) --------------------------------------
                    # creationCode / runtimeCode / interfaceId
                if m in {"creationCode", "runtimeCode", "interfaceId"}:
                    return f"symbolic_{inner}_{m}"  # 심볼릭 스트링

                    # ---- type(SomeType).name ------------------------------------------
                if m == "name":
                    return inner  # 그냥 타입 이름 문자열

                    # ---- 기타 미지원 멤버 ---------------------------------------------
                return f"symbolicMeta({inner}.{m})"

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
            if member == "length":
                if baseVal.typeInfo.isDynamicArray and len(baseVal.elements) == 0:
                    # 아직 push 된 적이 없는 완전 “빈” 동적 배열
                    # ⇒ 0‥2²⁵⁶-1  (UInt256 TOP) 로 보수적으로 가정
                    return UnsignedIntegerInterval(0, 2 ** 256 - 1, 256)
                else:
                    ln = len(baseVal.elements)
                    return UnsignedIntegerInterval(ln, ln, 256)
                return ln
            # .push() / .pop()  – 동적배열만 허용
            if callerContext == "functionCallContext":
                if not baseVal.typeInfo.isDynamicArray:
                    raise ValueError("push / pop available only on dynamic arrays")
                elemType = baseVal.typeInfo.arrayBaseType

                if expr.member == "push":
                    if not expr.arguments:  # push()  – 값 없이
                        elem = baseVal._create_new_array_element(len(baseVal.elements))
                        baseVal.elements.append(elem)
                    else:  # push(v)
                        val = self.evaluate_expression(expr.arguments[0], variables)
                        elem = baseVal._create_new_array_element(len(baseVal.elements))
                        elem.value = val
                        baseVal.elements.append(elem)
                    return None  # Solidity push 는 값 반환 X

                    # pop()
                if expr.member == "pop":
                    if not baseVal.elements:  # 빈 배열 pop  →  ⊥ 또는 revert
                        return None  # 보수적으로 ⊥ 처리하려면 Interval.bottom(...) 반환
                    popped = baseVal.elements.pop()
                    return getattr(popped, "value", popped)  # 값이 있으면 값, 없으면 객체

            if member == "length":
                # 동적 배열인데 아직 push 로 단 1-개도 추가되지 않음
                if baseVal.typeInfo.isDynamicArray and not baseVal.elements:
                    # “얼마든지 될 수 있다”  →  ⊥(bottom) 으로 전파
                    #   • 이후 비교( >, == 등) 는 항상 불확정 TOP 으로 유지
                    return UnsignedIntegerInterval(None, None, 256)

                # 그 밖의 경우 → 현재 element 수를 singleton-interval 로
                ln = len(baseVal.elements)
                return UnsignedIntegerInterval(ln, ln, 256)

        # ──────────────────────────────────────────────────────────────
        # 3. StructVariable  ( struct.field )
        # ──────────────────────────────────────────────────────────────
        if isinstance(baseVal, StructVariable):
            if member not in baseVal.members:
                raise ValueError(f"'{member}' not in struct '{baseVal.identifier}'")

            nested = baseVal.members[member]

            # ① enum (저장형 uint) -----------------------------------------
            if isinstance(nested, EnumVariable):
                return nested.value  # Enum 은 값만 필요

            # ② leaf-variable ---------------------------------------------
            if (isinstance(nested, Variables) and
                    not isinstance(nested, (ArrayVariable,
                                            StructVariable,
                                            MappingVariable))):
                return nested.value  # int / uint / bool / address …

            # ③ 배열·구조체·매핑 ------------------------------------------
            return nested  # 객체 그대로 넘김

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

    def evaluate_literal_with_subdenomination_context(
            self, expr: Expression, variables,
            callerObject=None, callerContext=None):
        """
        · expr.literal 은 이제 604800 처럼 *이미 환산된* 10진수 문자열이다.
        · 모든 sub-denom 값은 양수이므로 uint256 TOP 안에 들어간다.
        """

        lit_txt = expr.literal  # e.g. '604800'
        try:
            abs_val = int(lit_txt, 10)
        except ValueError:
            raise ValueError(f"Invalid pre-evaluated literal '{lit_txt}'")

        # uint256 상수 Interval 로 반환
        return UnsignedIntegerInterval(abs_val, abs_val, 256)

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

        type_name = expr.typeName  # 예: "uint256", "int8", "bool", "address"
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
            return sub_val

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

    def evaluate_assignment_expression(self, expr, variables,
                                       callerObject=None, callerContext=None):
        """
        대입식이 ‘값을 돌려주는 표현식’ 으로 사용될 때 처리.
          예)  (z = x + y)
        ①  RHS 값을 계산
        ②  LHS 변수에 반영(update_left_var)
        ③  RHS 값을 그대로 반환
        """
        r_val = self.evaluate_expression(expr.right, variables, None, None)
        # LHS 쪽 환경 업데이트
        self.update_left_var(expr.left, r_val, '=', variables,
                             callerObject, callerContext)
        return r_val  # ← ‘값을 돌려주기’ 핵심!

    def evaluate_tuple_expression_context(self, expr, variables,
                                          callerObject=None, callerContext=None):
        # 각 요소 평가
        elems = [self.evaluate_expression(e, variables, None, "TupleElem")
                 for e in expr.elements]

        # (a) 요소가 1개뿐 ⇒ 괄호식이거나 return (X) 같은 형태
        if len(elems) == 1:
            return elems[0]  # <- Interval · 값 그대로 반환

        # (b) 진짜 튜플 (a,b,...) ⇒ 리스트 유지
        return elems  # [v1, v2, ...]

    def evaluate_unary_operator(self, expr, variables,
                                callerObject=None, callerContext=None):

        operand_val = self.evaluate_expression(expr.expression, variables, None, "Unary")

        if operand_val is None:
            raise ValueError(f"Unable to evaluate operand in unary expression: {expr}")

        op = expr.operator
        if op == '-':
            return operand_val.negate()
        elif op == '!':
            return operand_val.logical_not()
        elif op == '~':
            return operand_val.bitwise_not()
        elif op == 'delete':
            # 분석 단계에서는 “완전 미정” 값으로 — 스칼라는 0-singleton,
            # Interval 이면 같은 bit-width bottom 으로.
            if hasattr(operand_val, "bottom"):
                return operand_val.bottom(getattr(operand_val, "type_length", 256))
            return 0

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
            return _bottom(leftInterval if not leftInterval.is_bottom() else rightInterval)

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

        if isinstance(callerObject, ArrayVariable) or isinstance(callerObject, MappingVariable):
            return self.evaluate_binary_operator_of_index(result, callerObject)
        else:
            return result

    def evaluate_function_call_context(self, expr, variables, callerObject=None, callerContext=None):
        if expr.context == "IdentifierExpContext":
            function_name = expr.identifier
        elif expr.function.context == "MemberAccessContext":  # dynamic array에 대한 push, pop
            return self.evaluate_expression(expr.function, variables, None, "functionCallContext")
        elif expr.function.context == "IdentifierExpContext":
            function_name = expr.function.identifier
        else:
            raise ValueError(f"There is no function name in function call context")

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

        # 5-A) ❶ caller 의 현재 env(variables)를 callee related_variables 로 병합
        #      ─ 이미 같은 key 가 있으면(상태변수·글로벌) 그대로 두고,
        #        caller 쪽에만 있던 로컬/임시 변수는 얕은 참조로 추가
        for k, v in variables.items():
            function_cfg.related_variables.setdefault(k, v)

        # 6) 실제 함수 CFG 해석
        return_value = self.interpret_function_cfg(function_cfg, variables)  # ← caller env 전달

        # 7) 함수 컨텍스트 복원
        self.current_target_function = saved_function

        return return_value

    def update_left_var(self, expr, rVal, operator, variables, callerObject=None, callerContext=None):
        # ── ① 글로벌이면 갱신 금지 ─────────────────────────
        if callerObject is None and callerContext is None and self._is_global_expr(expr):
            return None

        if expr.context == "IndexAccessContext":
            return self.update_left_var_of_index_access_context(expr, rVal, operator, variables,
                                                                callerObject, callerContext)
        elif expr.context == "MemberAccessContext":
            return self.update_left_var_of_member_access_context(expr, rVal, operator, variables,
                                                                 callerObject, callerContext)

        elif expr.context == "IdentifierExpContext":
            return self.update_left_var_of_identifier_context(expr, rVal, operator, variables,
                                                              callerObject, callerContext)
        elif expr.context == "LiteralExpContext":
            return self.update_left_var_of_literal_context(expr, rVal, operator, variables,
                                                           callerObject, callerContext)
        elif expr.left is not None and expr.right is not None:
            return self.update_left_var_of_binary_exp_context(expr, rVal, operator, variables,
                                                              callerObject, callerContext)

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

    def update_left_var_of_binary_exp_context(
            self, expr, rVal, operator, variables,
            callerObject=None, callerContext=None):
        """
        rebalanceCount % 10 과 같이 BinaryExp(%) 가
        IndexAccess 의 인덱스로 쓰일 때 호출된다.
        """

        # (1) IndexAccess 의 인덱스로 불린 경우만 의미 있음
        if callerObject is None or callerContext != "IndexAccessContext":
            return None

        # (2) 인덱스 식 abstract-eval → int or Interval
        idx_val = self.evaluate_expression(expr, variables, None, None)

        # ────────────────────────────────────────────────────────────────────
        # ① singleton [n,n]  → n 로 확정
        # ────────────────────────────────────────────────────────────────────
        if isinstance(idx_val, (IntegerInterval, UnsignedIntegerInterval)):
            if idx_val.min_value == idx_val.max_value:
                idx_val = idx_val.min_value  # 확정 int
            else:
                # 범위 [l,r]  → 아래의 “구간 처리” 로 넘어감
                pass

        # ────────────────────────────────────────────────────────────────────
        # ② 확정 int 인 경우
        # ────────────────────────────────────────────────────────────────────
        if isinstance(idx_val, int):
            target = self._touch_index_entry(callerObject, idx_val)
            new_val = self.compound_assignment(target.value, rVal, operator)
            self._patch_var_with_new_value(target, new_val)
            return target  # logging 용으로 돌려줌

        # ────────────────────────────────────────────────────────────────────
        # ③ 범위 interval  (l < r)  보수 처리
        #     ‣ 배열  : l‥r 전체 patch
        #     ‣ 매핑  : l‥r 중 ‘이미 존재하는 엔트리’만 patch
        #               (미정의 키는 <unk>로 남김)
        # ────────────────────────────────────────────────────────────────────
        # ──────────────────────────────────────────────────────────────
        # ③  범위 Interval  (l < r)  처리  ── 배열 / 매핑  둘 다 here
        # ----------------------------------------------------------------
        if isinstance(idx_val, (IntegerInterval, UnsignedIntegerInterval)):
            l, r = idx_val.min_value, idx_val.max_value

            # ===== 1) 배열(ArrayVariable) =================================
            if isinstance(callerObject, ArrayVariable):

                # 1-A) **동적 배열**  → 길이 확장 없이 전체 write 로 추상화
                if callerObject.typeInfo.isDynamicArray:
                    return callerObject  # <unk>  write

                # 1-B) **정적 배열**  → 선언 길이 한도 내에서만 패딩
                decl_len = callerObject.typeInfo.arrayLength or 0
                if r >= decl_len:
                    raise IndexError(f"Index [{l},{r}] out of range for "
                                     f"static array '{callerObject.identifier}' "
                                     f"(declared len={decl_len})")

                # 부족한 구간을 Variables 객체로 채움
                while len(callerObject.elements) <= r:
                    new_idx = len(callerObject.elements)
                    callerObject.elements.append(
                        self._create_new_array_element(callerObject, new_idx)
                    )

                # l‥r 모든 요소 patch
                for i in range(l, r + 1):
                    elem = callerObject.elements[i]
                    nv = self.compound_assignment(elem.value, rVal, operator)
                    self._patch_var_with_new_value(elem, nv)

            # ===== 2) 매핑(MappingVariable) ===============================
            elif isinstance(callerObject, MappingVariable):
                for i in range(l, r + 1):
                    k = str(i)
                    if k in callerObject.mapping:  # 이미 존재하는 키만
                        entry = callerObject.mapping[k]
                        nv = self.compound_assignment(entry.value, rVal, operator)
                        self._patch_var_with_new_value(entry, nv)
                # 존재하지 않는 키는 <unk> 로 유지

            return None  # logging 은 상위에서 처리

        # (idx_val 이 Interval 도 int 도 아니면 – 아직 완전 심볼릭) → 상위에서 <unk> 처리
        return None

    def update_left_var_of_index_access_context(self, expr, rVal, operator, variables,
                                                callerObject=None, callerContext=None):
        # base expression에 대한 재귀
        base_obj = self.update_left_var(expr.base, rVal, operator, variables, None, "IndexAccessContext")

        # index expression에 대한 재귀
        return self.update_left_var(expr.index, rVal, operator, variables, base_obj, "IndexAccessContext")

    def update_left_var_of_member_access_context(
            self, expr, rVal, operator, variables,
            callerObject=None, callerContext=None):

        # ① 먼저 base 부분을 재귀-업데이트
        base_obj = self.update_left_var(expr.base, rVal, operator,
                                        variables, None, "MemberAccessContext")
        member = expr.member

        # ────────────────────────────────────────────────
        # ② 〈글로벌 멤버〉가 매핑의 키로 쓰인 경우
        #      · balances[msg.sender]         (1-단계)
        #      · allowed[msg.sender][_from]   (2-단계)
        # ────────────────────────────────────────────────
        if self._is_global_expr(expr) and isinstance(callerObject, MappingVariable):
            key = f"{expr.base.identifier}.{member}"  # "msg.sender"

            # (1) 엔트리 없으면 생성
            if key not in callerObject.mapping:
                callerObject.mapping[key] = self._create_new_mapping_value(
                    callerObject, key)

            entry = callerObject.mapping[key]

            # (2-B) leaf 에 값 대입 중이면 여기서 patch
            if hasattr(entry, "value"):
                entry.value = self.compound_assignment(entry.value, rVal, operator)
            return entry  # logging 용

        if isinstance(base_obj, MappingVariable):
            # ① base expression 이 IndexAccess 면 → index 식에서 키 추출
            key = None
            base_exp = expr.base  # levels[i]   에서   expr.base == IndexAccess
            if getattr(base_exp, "context", "") == "IndexAccessExpContext":
                idx_exp = base_exp.index
                # 식별자 인덱스  (levels[i]  →  "i")
                if getattr(idx_exp, "context", "") == "IdentifierExpContext":
                    key = idx_exp.identifier
                # 숫자 / 주소 literal 인덱스
                elif getattr(idx_exp, "context", "") == "LiteralExpContext":
                    key = str(idx_exp.literal)

            # ② ①에서 못 뽑았고, 매핑에 엔트리 하나뿐이면 그걸 그대로 사용
            if key is None and len(base_obj.mapping) == 1:
                key, _ = next(iter(base_obj.mapping.items()))

            # ③ 그래도 못 정했다면 식별자 문자열로 통일
            if key is None:
                key = str(idx_exp) if "idx_exp" in locals() else "__any__"

            # ── 엔트리 가져오거나 생성
            if key not in base_obj.mapping:
                base_obj.mapping[key] = self._create_new_mapping_value(
                    base_obj, key
                )

            nested = base_obj.mapping[key]
            base_obj = nested  # 이후 Struct 처리로 fall-through

        if isinstance(base_obj, ArrayVariable):
            # (1) .length  ─ Read-only.  LHS 로 올 수 없으므로 rVal 는 None
            if member == "length":
                ln = len(base_obj.elements)
                return UnsignedIntegerInterval(ln, ln, 256)  # ← Interval 반환

            # (2) .push / .pop 은 LHS 로 오지 않으므로 여기서 무시
            return base_obj  # 깊은 체이닝 대비 그대로 전달

            # ② base 가 StructVariable 인지 확인
        if not isinstance(base_obj, StructVariable):
            raise ValueError(f"Member access on non-struct '{base_obj.identifier}'")

        # ③ 멤버 존재 확인
        if member not in base_obj.members:
            raise ValueError(f"Member '{member}' not in struct '{base_obj.identifier}'")

        nested = base_obj.members[member]

        if isinstance(nested, (StructVariable, ArrayVariable, MappingVariable)):
            # 더 깊은 member access가 이어질 수 있으므로 그대로 반환
            return nested

        # ── elementary / enum ──────────────────────────────
        if isinstance(nested, (Variables, EnumVariable)):
            nested.value = self.compound_assignment(nested.value, rVal, operator)
            return nested  # ← 작업 완료

        # ── 배열 / 중첩 구조체 ──────────────────────────────

        # ── 예외 처리 ──────────────────────────────────────
        raise ValueError(f"Unexpected member-type '{type(nested).__name__}'")

    def update_left_var_of_literal_context(
            self, expr, rVal, operator, variables,
            callerObject: Variables | ArrayVariable | MappingVariable | None = None, callerContext=None):

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

        if isinstance(callerObject, ArrayVariable):

            if ident not in variables:
                raise ValueError(f"Index identifier '{ident}' not found.")
            idx_var = variables[ident]
            iv = idx_var.value  # Interval 또는 ⊥

            # ① ⊥   또는  [l, r] 범위  ⇒  전체-쓰기(추상화)
            if self._is_interval(iv) and (
                    iv.is_bottom() or iv.min_value != iv.max_value
            ):
                return callerObject  # <unk> 쓰기

            # ② singleton [n,n] 이 아니면 오류
            if not self._is_interval(iv) or iv.min_value != iv.max_value:
                raise ValueError(f"Array index '{ident}' must resolve to single constant.")

            idx = iv.min_value
            if idx < 0:
                raise IndexError(f"Negative index {idx} for array '{callerObject.identifier}'")

            # ───── 동적·정적에 따른 분기 ─────────────────────────────────────────────
            if idx >= len(callerObject.elements):

                if callerObject.typeInfo.isDynamicArray:
                    # **동적 배열** → 길이 확장하지 않고 전체-쓰기 로 취급
                    return callerObject  # <unk> 쓰기 (logging 은 상위에서)

                # **정적 배열** → 선언 길이 한도 안에서 패딩
                decl_len = callerObject.typeInfo.arrayLength or 0
                if idx >= decl_len:  # 선언 길이 초과면 즉시 오류
                    raise IndexError(f"Index {idx} out of range for static array "
                                     f"'{callerObject.identifier}' (declared len={decl_len})")

                # 필요한 칸만 bottom 값으로 채운다
                base_t = callerObject.typeInfo.arrayBaseType
                while len(callerObject.elements) <= idx:
                    callerObject.elements.append(
                        self._bottom_from_soltype(base_t)
                    )

            # ───────── 실제 요소 갱신 / 재귀 내려가기 ─────────────────────────────
            elem = callerObject.elements[idx]

            if isinstance(elem, (StructVariable, ArrayVariable, MappingVariable)):
                return elem  # 더 깊이 체이닝
            elif isinstance(elem, (Variables, EnumVariable)):
                _apply_to_leaf(elem)  # leaf 값 갱신
                return None

        # 1-C) StructVariable  → 멤버 접근
        if isinstance(callerObject, StructVariable):
            if ident not in callerObject.members:
                raise ValueError(f"Struct '{callerObject.identifier}' has no member '{ident}'")
            mem = callerObject.members[ident]
            if isinstance(mem, (StructVariable, ArrayVariable, MappingVariable)):
                return mem
            elif isinstance(mem, (Variables, EnumVariable)):
                _apply_to_leaf(mem)
                return None

        # 1-D) MappingVariable → key 가 식별자인 케이스
        if isinstance(callerObject, MappingVariable):
            # ── ①  키가 “식별자”인 경우 ─────────────────────────────
            if ident in variables:
                key_var = variables[ident]

                # (a) 주소형 변수  ⇒  식별자 자체 사용 ("user")
                is_addr = (
                        hasattr(key_var, "typeInfo") and
                        getattr(key_var.typeInfo, "elementaryTypeName", None) == "address"
                )
                if is_addr:
                    key_str = ident

                # (b) 숫자/Bool Interval --------------------------------------
                elif self._is_interval(key_var.value):
                    iv = key_var.value  # Unsigned/Integer/BoolInterval

                    # ⊥  (bottom)  ────────────────
                    #   아직 어떤 값인지 전혀 모를 때 ⇒
                    #   식별자 그대로 엔트리 하나 만들고 그 엔트리를 바로 반환
                    if iv.is_bottom():
                        key_str = ident
                        if key_str not in callerObject.mapping:
                            callerObject.mapping[key_str] = self._create_new_mapping_value(
                                callerObject, key_str
                            )
                        return callerObject.mapping[key_str]  # ★ here

                    # [lo, hi]  (다중 singleton) ──────────────────
                    if iv.min_value != iv.max_value:
                        span = iv.max_value - iv.min_value + 1

                        if span <= 32:
                            # 작은 구간이면 lo..hi 전부 생성
                            for k in range(iv.min_value, iv.max_value + 1):
                                k_str = str(k)
                                if k_str not in callerObject.mapping:
                                    callerObject.mapping[k_str] = self._create_new_mapping_value(
                                        callerObject, k_str
                                    )
                            # 분석-중엔 “매핑 전체” 로 다룰 수 있도록 callerObject 그대로 반환
                            return callerObject  # ★ here
                        else:
                            # 범위가 크면 하나의 <unk> 키로 추상화
                            return callerObject  # ★ unchanged

                    # singleton  ────────────────────────────────
                    key_str = str(iv.min_value)  # ★ 확정 키

                # (c) 그밖의 심볼릭 값  ⇒  식별자 그대로
                else:
                    key_str = ident

            # ── ②  키가 리터럴(‘0x…’ 등) / 선언 안 된 식별자 ────────────
            else:
                key_str = ident

            # ── ③  엔트리 가져오거나 생성 ────────────────────────────────
            if key_str not in callerObject.mapping:
                callerObject.mapping[key_str] = self._create_new_mapping_value(
                    callerObject, key_str
                )
            mvar = callerObject.mapping[key_str]

            # ── ④  복합-타입이면 계속 내려가고, 스칼라면 leaf-갱신 ─────────
            if isinstance(mvar, (StructVariable, ArrayVariable, MappingVariable)):
                return mvar  # userInfo[user] …
            _apply_to_leaf(mvar)  # Variables / EnumVariable
            return None

        # 1-A) 단순 변수/enum → 그대로 leaf 갱신
        if isinstance(callerObject, (Variables, EnumVariable)):
            _apply_to_leaf(callerObject)
            return None

        # ─────────────────────── 2. 상위 객체 없음 ──────────────────
        # (IndexAccess / MemberAccess 의 base 식별자를 해결하기 위한 분기)
        if callerContext in ("IndexAccessContext", "MemberAccessContext"):
            if ident in variables:
                return variables[ident]  # MappingVariable, StructVariable 자체를 리턴
            elif ident in ["block", "tx", "msg", "address", "code"]:
                return ident  # block, tx, msg를 리턴
            elif ident in self.contract_cfgs[self.current_target_contract].enumDefs:  # EnumDef 리턴
                return self.contract_cfgs[self.current_target_contract].enumDefs[ident]
            else:
                raise ValueError(f"This '{ident}' is may be array or struct but may not be declared")

        # ─────────────────────── 3. 일반 대입식 ─────────────────────
        # 로컬-스코프 or state-scope 변수 직접 갱신
        if ident not in variables:
            raise ValueError(f"Variable '{ident}' not declared in current scope.")

        target_var = variables[ident]
        if not isinstance(target_var, (Variables, EnumVariable)):
            raise ValueError(f"Assignment to non-scalar variable '{ident}' must use member/index access.")

        _apply_to_leaf(target_var)
        return None

    def _resolve_and_update_expr(self, expr: Expression,
                                 rVal,
                                 operator,
                                 variables: dict[str, Variables],  # ← 새로 넣었는지?
                                 fcfg: FunctionCFG,
                                 callerObject=None, callerContext=None):
        if callerObject is None and callerContext is None and self._is_global_expr(expr):
            return None

        if expr.context == "IndexAccessContext":
            return self._resolve_and_update_expr_of_index_access_context(expr, rVal, operator, variables, fcfg,
                                                                         callerObject, callerContext)
        elif expr.context == "MemberAccessContext":
            return self._resolve_and_update_expr_of_member_access_context(expr, rVal, operator, variables, fcfg,
                                                                          callerObject, callerContext)

        elif expr.context == "IdentifierExpContext":
            return self._resolve_and_update_expr_of_identifier_context(expr, rVal, operator, variables, fcfg,
                                                                       callerObject, callerContext)
        elif expr.context == "LiteralExpContext":
            return self._resolve_and_update_expr_of_literal_context(expr, rVal, operator, variables, fcfg,
                                                                    callerObject, callerContext)

        elif expr.context == "TestingIndexAccess":
            return self._resolve_and_update_expr_of_testing_index_access_context(expr, rVal, operator, variables, fcfg,
                                                                                 callerObject, callerContext)
        elif expr.context == "TestingMemberAccess":
            return self._resolve_and_update_expr_of_testing_member_access_context(expr, rVal, operator, variables, fcfg,
                                                                                  callerObject, callerContext)

        elif expr.left is not None and expr.right is not None:
            return self._resolve_and_update_expr_of_binary_exp_context(expr, rVal, operator, variables, fcfg,
                                                                       callerObject, callerContext)

        return None

    def _resolve_and_update_expr_of_testing_index_access_context(self, expr: Expression,
                                                                 rVal,
                                                                 operator,
                                                                 variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                                 fcfg: FunctionCFG,
                                                                 callerObject=None, callerContext=None):
        # base
        base_obj = self._resolve_and_update_expr(
            expr.base, rVal, operator, variables,  # ← ❌  인수순서/개수 모두 틀림
            fcfg, None, "TestingIndexAccess"
        )
        # index
        return self._resolve_and_update_expr(
            expr.index, rVal, operator, variables, fcfg,
            base_obj, "TestingIndexAccess"
        )

    def _resolve_and_update_expr_of_testing_member_access_context(self, expr: Expression,
                                                                  rVal,
                                                                  operator,
                                                                  variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                                  fcfg: FunctionCFG,
                                                                  callerObject=None, callerContext=None):

        # ① 먼저 base 부분을 재귀-업데이트
        base_obj = self._resolve_and_update_expr(expr.base, rVal, operator,
                                                 variables, fcfg, None, "TestingMemberAccess")
        member = expr.member

        if member is not None:
            if self._is_global_expr(expr) and isinstance(callerObject, MappingVariable):
                key = f"{expr.base.identifier}.{member}"  # "msg.sender"

                # 엔트리가 없으면 새로 만든다
                if key not in callerObject.mapping:
                    callerObject.mapping[key] = self._create_new_mapping_value(
                        callerObject, key)

                entry = callerObject.mapping[key]

                # ① 더 깊은 IndexAccess 가 이어질 때는 객체 그대로 반환
                if callerContext == "TestingIndexAccess":
                    return entry  # allowed[msg.sender] 의 결과

                # ② leaf 읽기(Testing이므로 값 패치는 하지 않음)
                return entry  # Variables / EnumVariable / Array…

            if not isinstance(base_obj, StructVariable):
                raise ValueError(f"[Warn] member access on non-struct '{base_obj.identifier}'")
            m = base_obj.members.get(member)
            if m is None:
                raise ValueError(f"[Warn] struct '{base_obj.identifier}' has no member '{member}'")

            nested = base_obj.members[member]

            if isinstance(nested, (StructVariable, ArrayVariable, MappingVariable)):
                # 더 깊은 member access가 이어질 수 있으므로 그대로 반환
                return nested
            elif isinstance(nested, (Variables, EnumVariable)):
                if rVal is not None:
                    self._patch_var_with_new_value(m, rVal)
                return m

        raise ValueError(f"Unexpected member-type '{nested}'")

    def _resolve_and_update_expr_of_index_access_context(self, expr: Expression,
                                                         rVal,
                                                         operator,
                                                         variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                         fcfg: FunctionCFG,
                                                         callerObject=None, callerContext=None):
        # base
        base_obj = self._resolve_and_update_expr(
            expr.base, rVal, operator, variables,  # ← ❌  인수순서/개수 모두 틀림
            None, None, "IndexAccessContext"
        )
        # index
        return self._resolve_and_update_expr(
            expr.index, rVal, operator, variables, fcfg,
            base_obj, "IndexAccessContext"
        )

    def _resolve_and_update_expr_of_member_access_context(self, expr: Expression,
                                                          rVal,
                                                          operator,
                                                          variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                          fcfg: FunctionCFG,
                                                          callerObject=None, callerContext=None):

        # ① 먼저 base 부분을 재귀-업데이트
        base_obj = self._resolve_and_update_expr(expr.base, rVal, operator,
                                                 variables, fcfg, None, "MemberAccessContext")
        member = expr.member

        if member is not None:
            if self._is_global_expr(expr) and isinstance(callerObject, MappingVariable):
                key = f"{expr.base.identifier}.{member}"  # "msg.sender"

                # 1) 엔트리 확보 (없으면 생성)
                if key not in callerObject.mapping:
                    callerObject.mapping[key] = self._create_new_mapping_value(
                        callerObject, key)

                entry = callerObject.mapping[key]

                # 2) 뒤에 또 인덱스가 붙을 때는 객체 그대로 반환
                if callerContext == "IndexAccessContext":
                    return entry

                # 3) leaf-write : rVal 반영
                if isinstance(entry, (Variables, EnumVariable)) and rVal is not None:
                    self._patch_var_with_new_value(entry, rVal)
                return entry  # ← leaf 객체 반환

            if not isinstance(base_obj, StructVariable):
                raise ValueError(f"[Warn] member access on non-struct '{base_obj.identifier}'")
            m = base_obj.members.get(member)
            if m is None:
                raise ValueError(f"[Warn] struct '{base_obj.identifier}' has no member '{member}'")

            nested = base_obj.members[member]

            if isinstance(nested, (StructVariable, ArrayVariable, MappingVariable)):
                # 더 깊은 member access가 이어질 수 있으므로 그대로 반환
                return nested
            elif isinstance(nested, (Variables, EnumVariable)):
                if rVal is not None:
                    self._patch_var_with_new_value(m, rVal)
                return m

        raise ValueError(f"Unexpected member-type '{nested}'")

    def _resolve_and_update_expr_of_identifier_context(self, expr: Expression,
                                                       rVal,
                                                       operator,
                                                       variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                       fcfg: FunctionCFG,
                                                       callerObject=None, callerContext=None):
        ident = expr.identifier

        if callerObject is not None:

            if isinstance(callerObject, ArrayVariable):
                if ident not in variables:
                    raise ValueError(f"Index identifier '{ident}' not found.")
                idx_var = variables[ident]

                # 스칼라인지 보장
                # ── ① 인덱스가 ⊥(bottom) 이면 “어느 요소인지 모름” → skip
                if (self._is_interval(idx_var.value) and idx_var.value.is_bottom()) or \
                        getattr(idx_var.value, "min_value", None) is None:
                    # record 만 하고 실제 element 확정은 보류
                    return None  # ← **이 두 줄만 추가**

                # ── ② 스칼라(singleton) 여부 검사
                if not self._is_interval(idx_var.value) or \
                        idx_var.value.min_value != idx_var.value.max_value:
                    raise ValueError(f"Array index '{ident}' must resolve to single constant.")

                idx = idx_var.value.min_value
                if idx < 0 or idx >= len(callerObject.elements):
                    raise IndexError(f"Index {idx} out of range for array '{callerObject.identifier}'")

                elem = callerObject.elements[idx]
                if isinstance(elem, (StructVariable, MappingVariable, ArrayVariable)):
                    return elem
                elif isinstance(elem, (Variables, EnumVariable)):
                    if rVal is None:
                        return elem
                    else:
                        self._patch_var_with_new_value(elem, rVal)
                        return elem

            if isinstance(callerObject, StructVariable):
                if ident not in callerObject.members:
                    raise ValueError(f"Struct '{callerObject.identifier}' has no member '{ident}'")
                mem = callerObject.members[ident]
                if isinstance(mem, (StructVariable, MappingVariable, ArrayVariable)):
                    return mem
                elif isinstance(mem, (Variables, EnumVariable)):
                    if rVal is None:
                        return mem
                    else:
                        self._patch_var_with_new_value(mem, rVal)
                        return mem

            if isinstance(callerObject, MappingVariable):
                if ident not in callerObject.mapping:
                    callerObject.mapping[ident] = self._create_new_mapping_value(callerObject, ident)
                mvar = callerObject.mapping[ident]
                # ① 복합 타입(Struct / Array / Mapping) ⇒ 더 내려가도록 반환
                if isinstance(mvar, (StructVariable, ArrayVariable, MappingVariable)):
                    return mvar
                elif isinstance(mvar, (Variables, EnumVariable)):
                    if rVal is None:
                        return mvar
                    else:
                        self._patch_var_with_new_value(mvar, rVal)
                        return mvar

            if isinstance(callerObject, (Variables, EnumVariable)):
                if rVal is None:
                    return callerObject
                else:
                    self._patch_var_with_new_value(callerObject, rVal)
                    return callerObject

        # (IndexAccess / MemberAccess 의 base 식별자를 해결하기 위한 분기)
        if callerContext in ("IndexAccessContext", "MemberAccessContext", "TestingIndexAccess",
                             "TestingMemberAccess"):
            if ident in variables:
                return variables[ident]  # MappingVariable, StructVariable 자체를 리턴
            elif ident in ["block", "tx", "msg", "address", "code"]:
                return ident  # block, tx, msg를 리턴
            elif ident in self.contract_cfgs[self.current_target_contract].enumDefs:  # EnumDef 리턴
                return self.contract_cfgs[self.current_target_contract].enumDefs[ident]
            else:
                raise ValueError(f"This '{ident}' is may be array or struct but may not be declared")

        if ident not in variables:
            raise ValueError(f"Variable '{ident}' not declared in current scope.")

        target_var = variables[ident]
        if rVal is None:
            return target_var
        if isinstance(target_var, (Variables, EnumVariable)):
            self._patch_var_with_new_value(target_var, rVal)
            return target_var

        raise ValueError(f"Unhandled callerObject type: {type(callerObject).__name__}")

    def _resolve_and_update_expr_of_literal_context(self, expr: Expression,
                                                    rVal,
                                                    operator,
                                                    variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                    fcfg: FunctionCFG,
                                                    callerObject=None, callerContext=None):
        lit = expr.literal  # 예: "123", "0x1a", "true"
        lit_str = str(lit)
        lit_iv = None  # 필요 시 Interval 변환 결과
        if callerObject is None:
            raise ValueError(f"Literal '{lit_str}' cannot appear standalone on LHS")

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

            # 중첩 array/struct → 계속 내려감
            if isinstance(elem, (ArrayVariable, StructVariable, MappingVariable)):
                return elem
            # leaf (elementary or enum)
            elif isinstance(elem, (Variables, EnumVariable)):
                if rVal is None:
                    return elem
                else:
                    elem.value = rVal
                    return elem

        if isinstance(callerObject, MappingVariable):
            key = lit_str  # mapping key 는 문자열 그대로 보존
            if key not in callerObject.mapping:  # 없으면 새 child 생성
                callerObject.mapping[key] = self._create_new_mapping_value(callerObject, key)
            mvar = callerObject.mapping[key]

            if isinstance(mvar, (ArrayVariable, StructVariable, MappingVariable)):
                return mvar

            if isinstance(mvar, (Variables, EnumVariable)):
                if rVal is None:
                    return mvar
                else:
                    mvar.value = rVal
                    return mvar

        raise ValueError(f"Literal context '{lit_str}' not handled for '{type(callerObject).__name__}'")

    def _resolve_and_update_expr_of_binary_exp_context(self, expr: Expression,
                                                       rVal,
                                                       operator,
                                                       variables: dict[str, Variables],  # ← 새로 넣었는지?
                                                       fcfg: FunctionCFG,
                                                       callerObject=None, callerContext=None):
        """
                rebalanceCount % 10 과 같이 BinaryExp(%) 가
                IndexAccess 의 인덱스로 쓰일 때 호출된다.
                """
        # (1) IndexAccess 의 인덱스로 불린 경우만 의미 있음
        if callerObject is None or callerContext in ["IndexAccessContext", "TestingIndexAccessContext"]:
            return None

        # (2) 인덱스 식 abstract-eval → int or Interval
        idx_val = self.evaluate_expression(expr, variables, None, None)

        if isinstance(idx_val, (IntegerInterval, UnsignedIntegerInterval)):
            if idx_val.min_value == idx_val.max_value:
                idx_val = idx_val.min_value  # 확정 int
            else:
                # 범위 [l,r]  → 아래의 “구간 처리” 로 넘어감
                pass

            # ────────────────────────────────────────────────────────────────────
            # ② 확정 int 인 경우
            # ────────────────────────────────────────────────────────────────────
        if isinstance(idx_val, int):
            target = self._touch_index_entry(callerObject, idx_val)
            self._patch_var_with_new_value(target, rVal)
            return target  # logging 용으로 돌려줌

        if isinstance(idx_val, (IntegerInterval, UnsignedIntegerInterval)):
            l, r = idx_val.min_value, idx_val.max_value
            if isinstance(callerObject, ArrayVariable):
                # 배열 길이 확장
                while r >= len(callerObject.elements):
                    callerObject.elements.append(
                        self._create_new_array_element(callerObject,
                                                       len(callerObject.elements))
                    )
                # l‥r 모두 갱신
                for i in range(l, r + 1):
                    elem = callerObject.elements[i]
                    self._patch_var_with_new_value(elem, rVal)

                return callerObject

            elif isinstance(callerObject, MappingVariable):
                for i in range(l, r + 1):
                    k = str(i)
                    if k in callerObject.mapping:  # 존재할 때만
                        entry = callerObject.mapping[k]
                        self._patch_var_with_new_value(entry, rVal)
                return callerObject
        raise ValueError(f"Unexpected variable of binary_exp_context")