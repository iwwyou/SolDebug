from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:                                         # 타입 검사 전용
     from Analyzer.ContractAnalyzer import ContractAnalyzer

from Domain.Variable import Variables, ArrayVariable, StructVariable, MappingVariable, EnumVariable, EnumDefinition
from Domain.Type import SolType
from Domain.Interval import Interval, IntegerInterval, BoolInterval, UnsignedIntegerInterval
from Domain.AddressSet import AddressSet
from Domain.IR import Expression

from Utils.Helper import VariableEnv

from decimal import Decimal, InvalidOperation
import re

class Evaluation :

    def __init__(self, analyzer: "ContractAnalyzer"):
        # ContractAnalyzer 인스턴스만 보관해 두고,
        # 나머지 컴포넌트는 필요할 때 property 로 접근합니다.
        self.an = analyzer

    # ── lazy properties ──────────────────────────────────────────────
    @property
    def up(self):
        return self.an.updater          # Update 싱글톤

    @property
    def engine(self):
        return self.an.engine          # Engine 싱글톤

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
        elif expr.context == "FunctionCallOptionContext":
            return self.evaluate_function_call_option_context(expr, variables, callerObject, callerContext)
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
            # 동적 배열 크기 평가: new uint256[](size) 형태
            array_length = sol_t.arrayLength
            if expr.arguments and len(expr.arguments) > 0:
                # arguments[0]에 길이 표현식이 있으면 평가
                length_result = self.evaluate_expression(expr.arguments[0], variables, callerObject, callerContext)
                # 결과가 interval이면 상한값 사용
                if hasattr(length_result, 'upper'):
                    array_length = length_result.upper
                elif isinstance(length_result, int):
                    array_length = length_result
                else:
                    # 심볼릭이거나 다른 타입이면 None으로 (동적)
                    array_length = None

            arr = ArrayVariable(
                fresh_id,
                base_type=sol_t.arrayBaseType,
                array_length=array_length,
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
            ccf = self.an.contract_cfgs[self.an.current_target_contract]

            return MappingVariable(fresh_id,
                                   key_type=sol_t.mappingKeyType,
                                   value_type=sol_t.mappingValueType,
                                   scope="memory",
                                   struct_defs=ccf.structDefs,  # ⭐️ 전달
                                   enum_defs=ccf.enumDefs)  # ⭐️ 전달)

        # ── (C) 구조체 ─────────────────────────────────────────────
        if sol_t.typeCategory == "struct":
            return StructVariable(fresh_id, sol_t.structTypeName, scope="memory")

        # ── (D) 컨트랙트 new Foo()  → 심볼릭 address ───────────────
        if sol_t.typeCategory == "userDefined" :
            # "fresh address"를 set domain TOP 으로
            return AddressSet.top()

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

        def _to_scalar_int(txt: str) :
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
                if not callerObject.struct_defs or not callerObject.enum_defs:
                    ccf = self.an.contract_cfgs[self.an.current_target_contract]
                    callerObject.struct_defs = ccf.structDefs
                    callerObject.enum_defs = ccf.enumDefs

                key = lit
                if key not in callerObject.mapping:
                    # 새 엔트리 생성
                    new_var = callerObject.get_or_create(key)
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
            # ★ Set domain 사용: 구체적 address ID로 singleton set 생성
            return AddressSet(ids={val_int})

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
                if VariableEnv.is_interval(iv) and not iv.is_bottom() and iv.min_value == iv.max_value:
                    idx = iv.min_value
                    if idx < 0:
                        raise IndexError(f"Negative index {idx} for array '{callerObject.identifier}'")

                    if idx >= len(callerObject.elements):
                        # ❗ 요소가 아직 없음 → base-type 의 TOP 값 (알 수 없는 값)
                        base_t = callerObject.typeInfo.arrayBaseType
                        if base_t.elementaryTypeName.startswith("uint"):
                            bits = base_t.intTypeLength or 256
                            return UnsignedIntegerInterval.top(bits)
                        elif base_t.elementaryTypeName.startswith("int"):
                            bits = base_t.intTypeLength or 256
                            return IntegerInterval.top(bits)
                        elif base_t.elementaryTypeName == "bool":
                            return BoolInterval.top()
                        else:
                            # 주소/bytes/string 등은 symbol
                            return f"symbolic_{callerObject.identifier}[{idx}]"
                    return callerObject.elements[idx]

                # ── (B) 불확정(bottom 또는 [l,r] 범위) ─────────────────
                #      ⇒  배열 모든 요소의 join 을 반환
                if callerObject.elements:
                    joined = None
                    for elem in callerObject.elements:
                        val = getattr(elem, "value", elem)  # 스칼라 / 복합 둘 다 지원
                        joined = val if joined is None else joined.join(val)
                    return joined

                # 배열이 비어 있으면 base-type 에 맞는 TOP 반환 (알 수 없는 값)
                base_t = callerObject.typeInfo.arrayBaseType
                if base_t.elementaryTypeName.startswith("uint"):
                    bits = base_t.intTypeLength or 256
                    return UnsignedIntegerInterval.top(bits)
                if base_t.elementaryTypeName.startswith("int"):
                    bits = base_t.intTypeLength or 256
                    return IntegerInterval.top(bits)
                if base_t.elementaryTypeName == "bool":
                    return BoolInterval.top()
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
                if not callerObject.struct_defs or not callerObject.enum_defs:
                    ccf = self.an.contract_cfgs[self.an.current_target_contract]
                    callerObject.struct_defs = ccf.structDefs
                    callerObject.enum_defs = ccf.enumDefs

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
                    callerObject.mapping[key_val] = callerObject.get_or_create(key_val)
                mvar = callerObject.mapping[key_val]
                # ── ④ 반환 규칙 ────────────────────────────
                if isinstance(mvar, (StructVariable, ArrayVariable, MappingVariable)):
                    return mvar
                else:
                    return mvar.value
            elif isinstance(callerObject, EnumVariable):
                raise ValueError(f"This '{ident_str}' may not be included in enum def '{callerObject.enum_name}'")
            else:
                # ArrayVariable 등 다른 타입에서 identifier 사용 - 변수로 간주
                if ident_str in variables:
                    return variables[ident_str].value
                else:
                    raise ValueError(f"Identifier '{ident_str}' not found in variables")

        # callerObject가 없고 callerContext는 있는 경우
        if callerContext is not None:
            if callerContext == "MemberAccessContext":  # base에 대한 접근
                if ident_str in variables:
                    return variables[ident_str]  # MappingVariable, StructVariable 자체를 리턴
                elif ident_str in ["block", "tx", "msg", "address", "code"]:
                    return ident_str  # block, tx, msg를 리턴
                elif ident_str in self.an.contract_cfgs[self.an.current_target_contract].enumDefs:  # EnumDef 리턴
                    return self.an.contract_cfgs[self.an.current_target_contract].enumDefs[ident_str]
                else:
                    raise ValueError(f"This '{ident_str}' is may be array or struct but may not be declared")
            elif callerContext == "IndexAccessContext":  # base에 대한 접근
                if ident_str in variables:
                    return variables[ident_str]  # ArrayVariable, MappingVariable 자체를 리턴

        # callerContext, callerObject 둘다 없는 경우
        if ident_str in variables:  # variables에 있으면
            var_obj = variables[ident_str]
            # ArrayVariable, StructVariable, MappingVariable는 객체 자체를 반환
            if isinstance(var_obj, (ArrayVariable, StructVariable, MappingVariable)):
                return var_obj
            # 기본 변수는 value 반환
            return var_obj.value
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
                        callerObject.mapping[full_name] = callerObject.get_or_create(full_name)
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
                        # ★ address의 max는 모든 주소 가능 → TOP
                        return AddressSet.top()
                    if m == "min":
                        # ★ address의 min은 0 주소
                        return AddressSet(ids={0})

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
                    # 코드 사이즈 – 예시로 고정 상수 (uint256)
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
                # typeInfo.arrayLength 속성이 있으면 우선 사용 (디버깅 주석 등으로 설정된 경우)
                if baseVal.typeInfo.arrayLength is not None:
                    return UnsignedIntegerInterval(baseVal.typeInfo.arrayLength, baseVal.typeInfo.arrayLength, 256)
                elif baseVal.typeInfo.isDynamicArray and len(baseVal.elements) == 0:
                    # 아직 push 된 적이 없는 완전 "빈" 동적 배열
                    # ⇒ 0‥2²⁵⁶-1  (UInt256 TOP) 로 보수적으로 가정
                    return UnsignedIntegerInterval(0, 2 ** 256 - 1, 256)
                else:
                    ln = len(baseVal.elements)
                    return UnsignedIntegerInterval(ln, ln, 256)

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
            # ★ address 타입 변환
            if isinstance(sub_val, AddressSet):
                return sub_val  # 이미 AddressSet이면 그대로
            if isinstance(sub_val, (UnsignedIntegerInterval, IntegerInterval)):
                # uint → address: singleton이면 구체적 ID, 아니면 TOP
                if sub_val.is_bottom():
                    return AddressSet.bot()
                if sub_val.min_value == sub_val.max_value:
                    return AddressSet(ids={sub_val.min_value})
                return AddressSet.top()
            if isinstance(sub_val, str) and sub_val.startswith("0x"):
                addr_int = int(sub_val, 16)
                return AddressSet(ids={addr_int})
            return AddressSet.top()  # 기타 → symbolic TOP

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
        self.up.update_left_var(expr.left, r_val, '=', variables,
                             callerObject, callerContext, None, None, False)
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
        return

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
        elif operator in ('<<', '>>', '>>>'):
            if (isinstance(leftInterval, IntegerInterval) and
                    isinstance(rightInterval, IntegerInterval)):
                result = leftInterval.shift(rightInterval, operator)

            elif (isinstance(leftInterval, UnsignedIntegerInterval) and
                  isinstance(rightInterval, UnsignedIntegerInterval)):
                result = leftInterval.shift(rightInterval, operator)

            else:
                raise ValueError(
                    f"Shift operands must both be int/uint intervals, got "
                    f"{type(leftInterval).__name__} and {type(rightInterval).__name__}"
                )
        # 비교 연산자 처리
        elif operator in ['==', '!=', '<', '>', '<=', '>=']:
            # ★ AddressSet 비교
            if isinstance(leftInterval, AddressSet) and isinstance(rightInterval, AddressSet):
                if operator == '==':
                    result = leftInterval.equals(rightInterval)
                elif operator == '!=':
                    result = leftInterval.not_equals(rightInterval)
                else:
                    # <, >, <=, >= 는 address에 대해 정의되지 않음
                    result = BoolInterval.top()
            # 두 피연산자가 모두 Interval 계열인지 검사
            elif not (isinstance(leftInterval, (IntegerInterval,
                                              UnsignedIntegerInterval,
                                              BoolInterval))
                    and isinstance(rightInterval, (IntegerInterval,
                                                   UnsignedIntegerInterval,
                                                   BoolInterval))):
                # Interval 아니면 "결과 불확정" 으로 취급
                result = BoolInterval.top()  # [0,1]
            else:
                result = Evaluation.compare_intervals(
                    leftInterval, rightInterval, operator)
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
        elif expr.function.context == "MemberAccessContext":  # dynamic array에 대한 push, pop or address.call
            # Check if it's address.call/delegatecall/staticcall
            member = getattr(expr.function, 'member', None)
            if member in ['call', 'delegatecall', 'staticcall']:
                # address.call{value: ...}("") returns (bool success, bytes memory data)
                # Return Top for success (bool)
                return BoolInterval.top()
            return self.evaluate_expression(expr.function, variables, None, "functionCallContext")
        elif expr.function.context == "IdentifierExpContext":
            function_name = expr.function.identifier
        else:
            raise ValueError(f"There is no function name in function call context")

        # 2) 현재 컨트랙트 CFG 가져오기
        contract_cfg = self.an.contract_cfgs.get(self.an.current_target_contract)
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.an.current_target_contract}")

        # 2-A) 구조체 생성자인지 확인
        if function_name in contract_cfg.structDefs:
            # 구조체 생성자: StructName({ field1: val1, ... })
            struct_def = contract_cfg.structDefs[function_name]
            new_struct = StructVariable(
                identifier=f"temp_{function_name}_{id(expr)}",
                struct_type=function_name,
                scope="memory"
            )
            new_struct.initialize_struct(struct_def)

            # named_arguments로 필드 초기화
            named_args = expr.named_arguments if expr.named_arguments else {}
            for field_name, field_expr in named_args.items():
                if field_name in new_struct.members:
                    field_value = self.evaluate_expression(field_expr, variables, None, None)
                    field_var = new_struct.members[field_name]
                    if isinstance(field_var, Variables):
                        field_var.value = field_value

            return new_struct

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
        saved_function = self.an.current_target_function
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
        return_value = self.an.engine.interpret_function_cfg(function_cfg, variables)  # ← caller env 전달

        # 7) 함수 컨텍스트 복원
        self.an.current_target_function = saved_function

        return return_value

    def update_mapping_in_cfg(self, mapVarName: str, key_str: str, new_var_obj: Variables):
        """
        mapVarName: "myMapping"
        key_str: "someKey"
        new_var_obj: 새로 만든 Variables(...) for the mapping value
        여기에 state_variable_node, function_cfg 등을 업데이트
        """
        contract_cfg = self.an.contract_cfgs.get(self.an.current_target_contract)
        if not contract_cfg:
            raise ValueError(f"Unable to find contract CFG for {self.an.current_target_contract}")

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

    def convert_to_uint(self, sub_val, bits):
        """
        sub_val을 uintN 범위 [0 .. 2^bits−1] 로 변환/클램프
        """
        type_max = (1 << bits) - 1  # 2**bits - 1 과 동일

        # ────────────────────────────────────────────────────────
        # 1) Interval 계열 (Unsigned / Integer)
        # ────────────────────────────────────────────────────────
        if isinstance(sub_val, (UnsignedIntegerInterval, IntegerInterval)):
            if sub_val.is_bottom():  # ★ bottom 우선 검사
                return UnsignedIntegerInterval(None, None, bits)

            new_min = max(0, sub_val.min_value)
            new_max = min(type_max, sub_val.max_value)
            if new_min > new_max:  # 교집합이 공집합
                return UnsignedIntegerInterval(None, None, bits)

            return UnsignedIntegerInterval(new_min, new_max, bits)

        # ────────────────────────────────────────────────────────
        # 2) BoolInterval  (0 또는 1)
        # ────────────────────────────────────────────────────────
        if isinstance(sub_val, BoolInterval):
            return UnsignedIntegerInterval(
                sub_val.min_value, sub_val.max_value, bits
            )  # 이미 0‥1 범위

        # ────────────────────────────────────────────────────────
        # 3) 문자열(리터럴·symbolic) → symbolic 래퍼
        # ────────────────────────────────────────────────────────
        if isinstance(sub_val, str):
            return f"symbolicUint{bits}({sub_val})"

        # ────────────────────────────────────────────────────────
        # 4) 기타(정수 등) → 그대로 Interval 로 래핑
        # ────────────────────────────────────────────────────────
        try:
            v = int(sub_val)
            v = max(0, min(type_max, v))
            return UnsignedIntegerInterval(v, v, bits)
        except (ValueError, TypeError):
            return f"symbolicUint{bits}({sub_val})"

    def convert_to_int(self, sub_val, bits):
        """
        주어진 sub_val(Interval·리터럴·symbolic)을
        signed int<bits> 범위 [-2^(bits-1) .. 2^(bits-1)-1] 로 변환/클램프한다.
        """
        type_min = -(1 << (bits - 1))
        type_max = (1 << (bits - 1)) - 1

        # ────────────────────────────────────────────────────────
        # 1) Interval → Interval
        #    ⊥(bottom) 은 그대로 bottom 반환
        # ────────────────────────────────────────────────────────
        if isinstance(sub_val, (IntegerInterval, UnsignedIntegerInterval)):
            if sub_val.is_bottom():  # ★ bottom 체크
                return IntegerInterval(None, None, bits)

            new_min = max(type_min, sub_val.min_value)
            new_max = min(type_max, sub_val.max_value)
            if new_min > new_max:  # 교집합이 공집합
                return IntegerInterval(None, None, bits)
            return IntegerInterval(new_min, new_max, bits)

        # ────────────────────────────────────────────────────────
        # 2) BoolInterval → 0/1 로 압축 후 위와 동일
        # ────────────────────────────────────────────────────────
        if isinstance(sub_val, BoolInterval):
            # 0‥1 과 int<bits> 의 교집합은 그대로 0‥1
            return IntegerInterval(
                max(type_min, sub_val.min_value),
                min(type_max, sub_val.max_value),
                bits
            )

        # ────────────────────────────────────────────────────────
        # 3) 문자열(리터럴·심볼릭)  → 그대로 symbolic 래퍼
        # ────────────────────────────────────────────────────────
        if isinstance(sub_val, str):
            return f"symbolicInt{bits}({sub_val})"

        # ────────────────────────────────────────────────────────
        # 4) 기타(정수 등) → 그대로 Interval 로 래핑
        # ────────────────────────────────────────────────────────
        try:
            v = int(sub_val)
            v = max(type_min, min(type_max, v))  # 범위 클램프
            return IntegerInterval(v, v, bits)
        except (ValueError, TypeError):
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

    def evaluate_binary_operator_of_index(self, result, callerObject):
        def array_base_is_address(arr: ArrayVariable) -> bool:
            et = arr.typeInfo.arrayBaseType
            if isinstance(et, SolType):
                return et.elementaryTypeName == "address"
            return et == "address"

        if isinstance(callerObject, ArrayVariable):
            # 숫자/인터벌이 아니면 그대로 symbolic
            if not hasattr(result, "min_value"):
                return f"symbolicIndex({callerObject.identifier}[{result}])"

            # bottom → symbolic
            if result.is_bottom():
                return f"symbolicIndex({callerObject.identifier}[BOTTOM])"

            l, r = result.min_value, result.max_value

            # ─── (A) 단일 인덱스 ───────────────────────────────
            if l == r:
                try:
                    elem = callerObject.get_or_create_element(l)
                except IndexError:
                    return f"symbolicIndex({callerObject.identifier}[{l}])"
                return elem.value if hasattr(elem, "value") else elem

            # ─── (B) 범위 [l..r]  → join  ─────────────────────
            span = r - l
            # ① 범위가 너무 넓거나(≳1024) + 동적 배열이 비어 있으면 ⇒ TOP
            if span > 1024 or (callerObject.typeInfo.isDynamicArray and len(callerObject.elements) == 0):
                if array_base_is_address(callerObject):
                    # ★ address 배열의 경우 AddressSet TOP 반환
                    return AddressSet.top()
                return f"symbolicIndexRange({callerObject.identifier}[{result}])"

            joined = None
            for idx in range(l, r + 1):
                try:
                    elem = callerObject.get_or_create_element(idx)
                except IndexError:
                    return f"symbolicIndexRange({callerObject.identifier}[{result}])"

                val = elem.value if hasattr(elem, "value") else elem
                if hasattr(val, "join"):
                    joined = val if joined is None else joined.join(val)
                else:
                    return f"symbolicMixedType({callerObject.identifier}[{result}])"

            return joined

        # 3) callerObject가 MappingVariable인 경우 (비슷한 로직 확장 가능)
        if isinstance(callerObject, MappingVariable):
            # result => 단일 키 or 범위 => map lookup
            if not hasattr(result, 'min_value') or not hasattr(result, 'max_value'):
                # symbolic
                return f"symbolicMappingIndex({callerObject.identifier}[{result}])"

            if result.is_bottom():
                return f"symbolicMappingIndex({callerObject.identifier}[BOTTOM])"

            if not callerObject.struct_defs or not callerObject.enum_defs:
                ccf = self.an.contract_cfgs[self.an.current_target_contract]
                callerObject.struct_defs = ccf.structDefs
                callerObject.enum_defs = ccf.enumDefs

            min_idx = result.min_value
            max_idx = result.max_value
            if min_idx == max_idx:
                key_str = str(min_idx)
                if key_str in callerObject.mapping:
                    return callerObject.mapping[key_str].value
                else:
                    # 새로 추가 or symbolic
                    new_var_obj = callerObject.get_or_create(key_str)
                    self.update_mapping_in_cfg(callerObject.identifier, key_str, new_var_obj)
                    return new_var_obj.value
            else:
                # 범위 [min_idx .. max_idx]  ─ MappingVariable -----------------------------
                joined = None
                for k in range(min_idx, max_idx + 1):
                    k_str = str(k)
                    if k_str not in callerObject.mapping:
                        new_obj = callerObject.get_or_create(k_str)
                        self.update_mapping_in_cfg(callerObject.identifier, k_str, new_obj)
                        val = new_obj.value
                    else:
                        val = callerObject.mapping[k_str].value

                    if hasattr(val, "join"):
                        joined = val if joined is None else joined.join(val)
                    else:
                        return f"symbolicMixedType({callerObject.identifier}[{result}])"

                return joined
        return

    @staticmethod
    def calculate_default_interval(var_type):
        # 1. int 타입 처리 - 상태변수 기본값은 0
        if var_type.startswith("int"):
            length = int(var_type[3:]) if var_type != "int" else 256  # int 타입의 길이 (기본값은 256)
            return IntegerInterval(0, 0, length)  # int의 기본값 0

        # 2. uint 타입 처리 - 상태변수 기본값은 0
        elif var_type.startswith("uint"):
            length = int(var_type[4:]) if var_type != "uint" else 256  # uint 타입의 길이 (기본값은 256)
            return UnsignedIntegerInterval(0, 0, length)  # uint의 기본값 0

        # 3. bool 타입 처리 - 상태변수 기본값은 false (0)
        elif var_type == "bool":
            return BoolInterval(0, 0)  # bool의 기본값 false (0)

        # 4. address 타입 처리 - 기본값은 address(0)
        elif var_type == "address":
            return AddressSet(ids={0})  # address의 기본값 0 (singleton set)

        # 5. 기타 처리 (필요시 확장 가능)
        else:
            raise ValueError(f"Unsupported type for default interval: {var_type}")

    def evaluate_function_call_option_context(self, expr, variables, callerObject=None, callerContext=None):
        """
        FunctionCallOptions: expr.function { option1: val1, option2: val2, ... }

        두 가지 경우:
        1) 구조체 생성자: StructName({ field1: val1, field2: val2 })
        2) 함수 호출 옵션: contract.func{value: 1 ether, gas: 5000}(args)
        """
        # expr.function이 구조체 타입 이름인지 확인
        if expr.function and expr.function.context == "IdentifierExpContext":
            struct_name = expr.function.identifier

            # 구조체인지 확인
            if struct_name in self.an.structs:
                # 구조체 생성자: 새 StructVariable 생성
                struct_def = self.an.structs[struct_name]
                ccf = self.an.contract_cfgs[self.an.current_target_contract]

                new_struct = StructVariable(
                    identifier=f"temp_{struct_name}_{id(expr)}",
                    struct_type=struct_name,
                    scope="memory"
                )
                new_struct.typeInfo = SolType(typeCategory="struct", structTypeName=struct_name)

                # 구조체 초기화
                new_struct.initialize_struct(struct_def)

                # options에서 필드 값 설정
                if expr.options:
                    for field_name, field_expr in expr.options.items():
                        if field_name in new_struct.members:
                            field_value = self.evaluate_expression(field_expr, variables, None, None)
                            field_var = new_struct.members[field_name]
                            if isinstance(field_var, Variables):
                                field_var.value = field_value
                            # 중첩 구조체/배열의 경우 추가 처리 필요할 수 있음

                return new_struct

        # 함수 호출 옵션 (예: {value: 1 ether, gas: 5000})
        # 현재는 symbolic으로 처리
        return f"symbolicFunctionCallOptions({expr.function})"

    @staticmethod
    def compare_intervals(left_interval, right_interval, operator):

        # 값이 하나라도 없으면 판단 불가 → TOP
        if (left_interval.min_value is None or left_interval.max_value is None or
                right_interval.min_value is None or right_interval.max_value is None):
            return BoolInterval(0, 1)  # [0,1]

        definitely_true = False
        definitely_false = False

        # ───────── 비교 연산별 판정 ────────────────────────────────
        if operator == '==':
            if left_interval.max_value < right_interval.min_value or \
                    left_interval.min_value > right_interval.max_value:
                definitely_false = True
            elif (left_interval.min_value == left_interval.max_value ==
                  right_interval.min_value == right_interval.max_value):
                definitely_true = True

        elif operator == '!=':
            if left_interval.max_value < right_interval.min_value or \
                    left_interval.min_value > right_interval.max_value:
                definitely_true = True
            elif (left_interval.min_value == left_interval.max_value ==
                  right_interval.min_value == right_interval.max_value):
                definitely_false = True

        elif operator == '<':
            if left_interval.max_value < right_interval.min_value:
                definitely_true = True
            elif left_interval.min_value >= right_interval.max_value:
                definitely_false = True

        elif operator == '>':
            if left_interval.min_value > right_interval.max_value:
                definitely_true = True
            elif left_interval.max_value <= right_interval.min_value:
                definitely_false = True

        elif operator == '<=':
            if left_interval.max_value <= right_interval.min_value:
                definitely_true = True
            elif left_interval.min_value > right_interval.max_value:
                definitely_false = True

        elif operator == '>=':
            if left_interval.min_value >= right_interval.max_value:
                definitely_true = True
            elif left_interval.max_value < right_interval.min_value:
                definitely_false = True

        else:
            raise ValueError(f"Unsupported comparison operator: {operator}")

        # ───────── BoolInterval 생성 ─────────────────────────────
        if definitely_true and not definitely_false:
            return BoolInterval(1, 1)  # [1,1]  확실히 true
        if definitely_false and not definitely_true:
            return BoolInterval(0, 0)  # [0,0]  확실히 false
        return BoolInterval(0, 1)  # [0,1]  불확정(top)