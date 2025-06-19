from Parser.SolidityParser import SolidityParser
from Parser.SolidityVisitor import SolidityVisitor
# 맨 위 import 부분
from antlr4.tree.Tree import TerminalNodeImpl

from Domain.Variable import Variables, GlobalVariable, ArrayVariable, StructVariable, EnumVariable, MappingVariable
from Domain.Type import SolType
from Domain.Interval import IntegerInterval, UnsignedIntegerInterval, BoolInterval
from Domain.IR import Expression

KEYWORD_IDENTIFIERS = {
    "from", "to", "payable", "returns",      # 필요 시 계속 추가
}

TIME_VALUE = {
    "seconds": 1,
    "minutes": 60,
    "hours":   60 * 60,
    "days":    24 * 60 * 60,
    "weeks":   7  * 24 * 60 * 60,
    "years":   365 * 24 * 60 * 60,
    "wei":     1,
    "gwei":    10 ** 9,
    "ether":   10 ** 18,
}

# ContractAnalyzer (or util module) ──────────────────────────
READONLY_MEMBERS = {
    # Array / bytes
    "length", "slot", "offset",
    # Address
    "balance", "code", "codehash",
    # Function
    "selector",
    # type(T) meta
    "max", "min", "size", "name"
}

READONLY_GLOBAL_BASES = {"block", "msg", "tx"}


class EnhancedSolidityVisitor(SolidityVisitor):

    def __init__(self, contract_analyzer):
        self.contract_analyzer = contract_analyzer

    # Visit a parse tree produced by SolidityParser#sourceUnit.
    def visitSourceUnit(self, ctx:SolidityParser.SourceUnitContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#pragmaDirective.
    def visitPragmaDirective(self, ctx:SolidityParser.PragmaDirectiveContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#pragmaName.
    def visitPragmaName(self, ctx:SolidityParser.PragmaNameContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#pragmaValue.
    def visitPragmaValue(self, ctx:SolidityParser.PragmaValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#version.
    def visitVersion(self, ctx:SolidityParser.VersionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#versionOperator.
    def visitVersionOperator(self, ctx:SolidityParser.VersionOperatorContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#versionConstraint.
    def visitVersionConstraint(self, ctx:SolidityParser.VersionConstraintContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#importDeclaration.
    def visitImportDeclaration(self, ctx:SolidityParser.ImportDeclarationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#importDirective.
    def visitImportDirective(self, ctx:SolidityParser.ImportDirectiveContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#importPath.
    def visitImportPath(self, ctx:SolidityParser.ImportPathContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#symbolAliases.
    def visitSymbolAliases(self, ctx:SolidityParser.SymbolAliasesContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#contractDefinition.
    def visitContractDefinition(self, ctx:SolidityParser.ContractDefinitionContext):
        contract_name = ctx.identifier().getText()

        # ContractAnalyzer에서 해당 컨트랙트의 CFG 생성
        self.contract_analyzer.make_contract_cfg(contract_name)
        return

    # Visit a parse tree produced by SolidityParser#interfaceDefinition.
    def visitInterfaceDefinition(self, ctx:SolidityParser.InterfaceDefinitionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#libraryDefinition.
    def visitLibraryDefinition(self, ctx:SolidityParser.LibraryDefinitionContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SolidityParser#inheritanceSpecifier.
    def visitInheritanceSpecifier(self, ctx:SolidityParser.InheritanceSpecifierContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SolidityParser#callArgumentList.
    def visitCallArgumentList(self, ctx:SolidityParser.CallArgumentListContext):
        argument_list = []

        # 1. 명명되지 않은 인자 리스트 (표현식 목록) 처리
        if ctx.expression():
            for expr in ctx.expression():
                # expression 각각을 방문하여 처리한 결과를 리스트에 추가
                argument_list.append(self.visitExpression(expr))

        # 2. 명명된 인자 처리 (identifier: expression 쌍)
        elif ctx.identifier() and ctx.expression():
            named_arguments = {}
            for identifier, expression in zip(ctx.identifier(), ctx.expression()):
                # identifier와 해당 expression을 각각 방문한 결과로 dictionary에 추가
                named_arguments[identifier.getText()] = self.visitExpression(expression)

            argument_list.append(named_arguments)

        return argument_list


    # Visit a parse tree produced by SolidityParser#identifierPath.
    def visitIdentifierPath(self, ctx:SolidityParser.IdentifierPathContext):
        return self.visitChildren(ctx)


    # Visit a parse tree produced by SolidityParser#constantVariableDeclaration.
    # ---------------------------------------------------------------------------
    # ① constant 변수 선언 방문      (예:  uint256 constant DECIMALS = 18;)
    # ---------------------------------------------------------------------------
    def visitConstantVariableDeclaration(self,
                                         ctx: SolidityParser.ConstantVariableDeclarationContext):

        var_name = ctx.identifier().getText()

        # 1) 타입 분석 → SolType 객체
        type_ctx = ctx.typeName()
        type_obj = SolType()
        type_obj = self.visitTypeName(type_ctx, type_obj)

        # 2) 변수 객체 생성 (state 변수와 동일한 분기)
        if type_obj.typeCategory == "array":
            variable_obj = ArrayVariable(identifier=var_name,
                                         base_type=type_obj.arrayBaseType,
                                         array_length=type_obj.arrayLength,
                                         scope="state")
        elif type_obj.typeCategory == "struct":
            variable_obj = StructVariable(identifier=var_name,
                                          struct_type=type_obj.structTypeName,
                                          scope="state")
        elif type_obj.typeCategory == "mapping":
            variable_obj = MappingVariable(identifier=var_name,
                                           key_type=type_obj.mappingKeyType,
                                           value_type=type_obj.mappingValueType,
                                           scope="state")
        elif type_obj.typeCategory == "enum":
            variable_obj = EnumVariable(identifier=var_name,
                                        enum_type=type_obj.enumTypeName,
                                        scope="state")
        else:  # elementary
            variable_obj = Variables(identifier=var_name, scope="state")
            variable_obj.typeInfo = type_obj

        variable_obj.isConstant = True  # ← 상수 표시

        # 3) 초기화식 (Expression) 파싱
        init_expr = self.visitExpression(ctx.expression()) if ctx.expression() else None

        # 4) ContractAnalyzer 로 위임
        self.contract_analyzer.process_constant_variable(variable_obj, init_expr)

    # Visit a parse tree produced by SolidityParser#contractBodyElement.
    def visitContractBodyElement(self, ctx:SolidityParser.ContractBodyElementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#constructorDefinition.
    def visitConstructorDefinition(self, ctx: SolidityParser.ConstructorDefinitionContext):
        constructor_name = "constructor"

        # 파라미터 리스트 처리
        parameters = {}
        if ctx.parameterList():
            parameters = self.visitParameterList(ctx.parameterList())

        # Modifier 처리
        modifiers = []
        if ctx.modifierInvocation():
            for modifier_ctx in ctx.modifierInvocation():
                modifier_name = modifier_ctx.identifierPath().getText()
                modifiers.append(modifier_name)

        # ContractAnalyzer로 전달하여 처리
        self.contract_analyzer.process_constructor_definition(
            constructor_name=constructor_name,
            parameters=parameters,
            modifiers=modifiers
        )

    # Visit a parse tree produced by SolidityParser#fallbackFunctionDefinition.
    def visitFallbackFunctionDefinition(self, ctx:SolidityParser.FallbackFunctionDefinitionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#receiveFunctionDefinition.
    def visitReceiveFunctionDefinition(self, ctx:SolidityParser.ReceiveFunctionDefinitionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#stateVariableDeclaration.
    # EnhancedSolidityVisitor.py
    def visitStateVariableDeclaration(self,
                                      ctx: SolidityParser.StateVariableDeclarationContext):

        var_name = ctx.identifier().getText()

        # ── ① 타입 해석 ─────────────────────────────────────────────
        type_ctx = ctx.typeName()
        type_info = self.visitTypeName(type_ctx, SolType())  # ← SolType 객체

        # ── ② 변수 object  생성 (array / struct / mapping / enum / elementary) ──
        if type_info.typeCategory == "array":
            var_obj = ArrayVariable(var_name, type_info.arrayBaseType,
                                    type_info.arrayLength, scope="state",
                                    is_dynamic=type_info.isDynamicArray)
        elif type_info.typeCategory == "struct":
            var_obj = StructVariable(var_name, type_info.structTypeName, scope="state",
                                     )
        elif type_info.typeCategory == "mapping":
            var_obj = MappingVariable(var_name,
                                      type_info.mappingKeyType,
                                      type_info.mappingValueType,
                                      scope="state")
        elif type_info.typeCategory == "enum":
            var_obj = EnumVariable(var_name, type_info.enumTypeName, scope="state")
        else:  # elementary / address / bool …
            var_obj = Variables(var_name, scope="state")
            var_obj.typeInfo = type_info

        # ── ③ 초기화식 (있을 수도, 없을 수도) ────────────────────────
        init_expr = self.visitExpression(ctx.expression()) if ctx.expression() else None

        # ── ④ ‘constant’ 토큰 존재 여부 판별 ────────────────────────
        #     antlr4 는 토큰 이름으로 <rule>.<TokenName>() 메서드를 준다.
        has_constant = len(ctx.ConstantKeyword()) > 0

        if has_constant:
            # `constant`이면 별도 로직으로
            self.contract_analyzer.process_constant_variable(var_obj, init_expr)
        else:
            # 일반 state-var
            self.contract_analyzer.process_state_variable(var_obj, init_expr)

    # Visit a parse tree produced by SolidityParser#errorDefinition.
    def visitErrorDefinition(self, ctx:SolidityParser.ErrorDefinitionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#errorParameter.
    def visitErrorParameter(self, ctx:SolidityParser.ErrorParameterContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#usingDirective.
    def visitUsingDirective(self, ctx:SolidityParser.UsingDirectiveContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#userDefinableOperators.
    def visitUserDefinableOperators(self, ctx:SolidityParser.UserDefinableOperatorsContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#structDefinition.
    def visitStructDefinition(self, ctx:SolidityParser.StructDefinitionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#structMember.
    def visitStructMember(self, ctx: SolidityParser.StructMemberContext):
        var_name = ctx.identifier().getText()

        # 1. 기본 Variables 객체 생성 (초기에는 타입을 모름)
        variable_obj = None

        # 2. 타입 분석
        type_ctx = ctx.typeName()
        type_obj = SolType()
        type_obj = self.visitTypeName(type_ctx, type_obj)  # SolType 객체 반환

        # 2. ContractAnalyzer로 전달하여 처리
        self.contract_analyzer.process_struct_member(var_name, type_obj)

    # Visit a parse tree produced by SolidityParser#modifierDefinition.
    def visitModifierDefinition(self, ctx: SolidityParser.ModifierDefinitionContext):
        # 1. Modifier 이름을 가져옴
        modifier_name = ctx.identifier().getText()

        # 2. 파라미터가 존재하는지 확인
        parameters = None
        if ctx.parameterList():
            parameters = self.visitParameterList(ctx.parameterList())

        self.contract_analyzer.process_modifier_definition(modifier_name, parameters)

    # Visit a parse tree produced by SolidityParser#visibility.
    def visitVisibility(self, ctx:SolidityParser.VisibilityContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#modifierInvocation.
    def visitModifierInvocation(self, ctx:SolidityParser.ModifierInvocationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#functionDefinition.
    def visitFunctionDefinition(self, ctx: SolidityParser.FunctionDefinitionContext):
        fname = ctx.identifier().getText() if ctx.identifier() else None
        if not fname:
            raise ValueError("function name missing")

        params = self.visitParameterList(ctx.parameterList(0)) \
            if ctx.parameterList(0) else []
        rets = self.visitParameterList(ctx.parameterList(1)) \
            if ctx.parameterList(1) else []

        # ── ② modifierInvocation 만 수집하되 override/virtual 은 필터링 -----
        mods: list[str] = []
        for m in ctx.getChildren():
            if isinstance(m, SolidityParser.ModifierInvocationContext):
                name = m.identifierPath().getText()
                # ※ override / virtual 은 modifier 가 아님
                if name not in {"override", "virtual"}:
                    mods.append(name)

        self.contract_analyzer.process_function_definition(
            function_name=fname,
            parameters=params,
            modifiers=mods,
            returns=rets
        )

    # Visit a parse tree produced by SolidityParser#eventDefinition.
    def visitEventDefinition(self, ctx:SolidityParser.EventDefinitionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#enumDefinition.
    def visitEnumDefinition(self, ctx:SolidityParser.EnumDefinitionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#parameterList.
    def visitParameterList(self,
                           ctx: SolidityParser.ParameterListContext
                           ) -> list[tuple[SolType, str | None]]:
        params: list[tuple[SolType, str | None]] = []

        cur: list = []
        for ch in ctx.children:
            if ch.getText() == ',':
                if cur:
                    params.append(self._param_from_group(cur))
                    cur = []
            else:
                cur.append(ch)
        if cur:
            params.append(self._param_from_group(cur))
        return params

    def _param_from_group(self, group):
        sol_type = SolType()
        name = None

        for el in group:
            if isinstance(el, SolidityParser.TypeNameContext):
                sol_type = self.visitTypeName(el, sol_type)

            elif isinstance(el, SolidityParser.IdentifierContext):
                name = el.getText()

            elif isinstance(el, TerminalNodeImpl):
                txt = el.getText()
                if txt in KEYWORD_IDENTIFIERS:  # ← 소문자 문자열 비교
                    name = txt

        return sol_type, name

    # Visit a parse tree produced by SolidityParser#eventParameter.
    def visitEventParameter(self, ctx:SolidityParser.EventParameterContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#variableDeclaration.
    def visitVariableDeclaration(self, ctx:SolidityParser.VariableDeclarationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#variableDeclarationTuple.
    def visitVariableDeclarationTuple(self, ctx:SolidityParser.VariableDeclarationTupleContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#typeName.
    def visitTypeName(self, ctx: SolidityParser.TypeNameContext, type_obj):

        if isinstance(ctx, SolidityParser.BasicTypeContext):  # elementaryTypeName (BasicType)
            return self.visitBasicType(ctx, type_obj)
        elif isinstance(ctx, SolidityParser.FunctionTypeContext):  # functionTypeName (FunctionType)
            return self.visitFunctionType(ctx, type_obj)
        elif isinstance(ctx, SolidityParser.MapTypeContext):  # mapping (MapType)
            return self.visitMapType(ctx, type_obj)
        elif isinstance(ctx, SolidityParser.UserDefinedTypeContext):  # identifierPath (StructType)
            return self.visitUserDefinedType(ctx, type_obj)
        elif isinstance(ctx, SolidityParser.ArrayTypeContext):  # typeName '[' expression? ']' (ArrayType)
            return self.visitArrayType(ctx, type_obj)

    # Visit a parse tree produced by SolidityParser#ArrayType.
    def visitArrayType(
            self,
            ctx: SolidityParser.ArrayTypeContext,  # ← 변경
            type_obj: SolType
    ) -> SolType:
        # 배열의 기본 타입 처리
        base_type_ctx = ctx.typeName()
        base_type_obj = SolType()
        base_type_obj = self.visitTypeName(base_type_ctx, base_type_obj)

        # 배열 크기 확인
        if ctx.expression():
            array_size_expr = ctx.expression()
            array_size = self.evaluate_literal_expression(array_size_expr)  # 배열 크기를 평가 (정수 값이어야 함)
            is_dynamic = False
        else:
            array_size = 0
            is_dynamic = True

        type_obj.typeCategory = "array"
        type_obj.arrayBaseType = base_type_obj  # 재귀적으로 타입 표현
        type_obj.arrayLength = array_size
        type_obj.isDynamicArray = is_dynamic

        return type_obj

    # Visit a parse tree produced by SolidityParser#BasicType.
    def visitBasicType(self, ctx: SolidityParser.ElementaryTypeNameContext, type_obj):
        var_type = ctx.getText()
        type_obj.typeCategory = "elementary"
        type_obj.elementaryTypeName = var_type

        if var_type.startswith('int'):
            if var_type == 'int':
                type_obj.intTypeLength = 256  # 기본 길이는 256
            else:
                # 'int' 뒤에 붙은 숫자를 추출하여 비트 길이 설정
                try:
                    type_obj.intTypeLength = int(var_type[3:])  # 'int' 뒤의 숫자를 추출
                except ValueError:
                    raise ValueError(f"Invalid integer type length in '{var_type}'")

        elif var_type.startswith('uint'):
            if var_type == 'uint':
                type_obj.intTypeLength = 256  # 기본 길이는 256
            else:
                # 'uint' 뒤에 붙은 숫자를 추출하여 비트 길이 설정
                try:
                    type_obj.intTypeLength = int(var_type[4:])  # 'uint' 뒤의 숫자를 추출
                except ValueError:
                    raise ValueError(f"Invalid unsigned integer type length in '{var_type}'")

        return type_obj

    # Visit a parse tree produced by SolidityParser#FunctionType.
    def visitFunctionType(self, ctx: SolidityParser.FunctionTypeNameContext, type_obj):
        # 함수 타입 처리 (필요한 경우)
        type_obj.typeCategory = "function"
        # 추가적인 정보 처리 필요 시 여기서 처리
        return type_obj

    # Visit a parse tree produced by SolidityParser#StructType.
    def visitUserDefinedType(self, ctx: SolidityParser.UserDefinedTypeContext, type_obj):
        """
            사용자 정의 타입(Struct, Enum 등)을 처리합니다.
            :param ctx: IdentifierPathContext
            :param type_obj: SolType 객체
            :return: 수정된 type_obj
            """
        # 타입 이름 추출
        type_name = ctx.getText()

        # 현재 타겟 컨트랙트 이름 가져오기
        contract_name = self.contract_analyzer.current_target_contract

        # 현재 컨트랙트의 CFG 가져오기
        contract_cfg = self.contract_analyzer.contract_cfgs.get(contract_name)
        if not contract_cfg:
            raise ValueError(f"Contract '{contract_name}' not found in contract configurations.")

        # 타입이 enum인지 struct인지 확인
        if type_name in contract_cfg.enumDefs:
            # Enum 타입인 경우
            type_obj.typeCategory = "enum"
            type_obj.enumTypeName = type_name
        elif type_name in contract_cfg.structDefs:
            # Struct 타입인 경우
            type_obj.typeCategory = "struct"
            type_obj.structTypeName = type_name
        else:
            # 정의되지 않은 타입인 경우 예외 처리 또는 기본값 설정
            raise ValueError(f"Type '{type_name}' is not defined as struct or enum in contract '{contract_name}'.")

        return type_obj

    # Visit a parse tree produced by SolidityParser#MapType.
    def visitMapType(
            self,
            ctx: SolidityParser.MapTypeContext,  # ✔ MapTypeContext!
            type_obj: SolType
    ) -> SolType:
        # ctx.mapping() 는 이제 정적으로도 인식된다
        return self.visitMapping(ctx.mapping(), type_obj)

    # Visit a parse tree produced by SolidityParser#mapping.
    def visitMapping(self, ctx: SolidityParser.MappingContext, type_obj):
        # 키 타입 처리
        key_type_ctx = ctx.mappingKeyType()
        key_type_obj = self.visitMappingKeyType(key_type_ctx)

        # 값 타입 처리
        value_type_ctx = ctx.typeName()
        value_type_obj = SolType()
        value_type_obj = self.visitTypeName(value_type_ctx, value_type_obj)

        type_obj.typeCategory = "mapping"
        type_obj.mappingKeyType = key_type_obj
        type_obj.mappingValueType = value_type_obj

        return type_obj

    # Visit a parse tree produced by SolidityParser#mappingKeyType.
    def visitMappingKeyType(self, ctx:SolidityParser.MappingKeyTypeContext):
        # 키 타입은 elementaryTypeName만 가능
        if ctx.elementaryTypeName() is not None:
            key_type_obj = SolType()
            self.visitBasicType(ctx.elementaryTypeName(), key_type_obj)
            return key_type_obj
        else:
            # Solidity에서 키 타입은 elementary 타입만 허용하므로, 기타 타입은 오류 처리
            raise ValueError("Invalid key type in mapping: {}".format(ctx.getText()))

    # Visit a parse tree produced by SolidityParser#functionTypeName.
    def visitFunctionTypeName(self, ctx:SolidityParser.FunctionTypeNameContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveSourceUnit.
    def visitInteractiveSourceUnit(self, ctx:SolidityParser.InteractiveSourceUnitContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveEnumUnit.
    def visitInteractiveEnumUnit(self, ctx:SolidityParser.InteractiveEnumUnitContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveStructUnit.
    def visitInteractiveStructUnit(self, ctx:SolidityParser.InteractiveStructUnitContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveBlockUnit.
    def visitInteractiveBlockUnit(self, ctx:SolidityParser.InteractiveBlockUnitContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveDoWhileUnit.
    def visitInteractiveDoWhileUnit(self, ctx:SolidityParser.InteractiveDoWhileUnitContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveIfElseUnit.
    def visitInteractiveIfElseUnit(self, ctx:SolidityParser.InteractiveIfElseUnitContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveCatchClauseUnit.
    def visitInteractiveCatchClauseUnit(self, ctx:SolidityParser.InteractiveCatchClauseUnitContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#debugUnit.
    def visitDebugUnit(self, ctx:SolidityParser.DebugUnitContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#debugGlobalVar.
    def visitDebugGlobalVar(self, ctx: SolidityParser.DebugGlobalVarContext):
        # ─────────────────── 1) 식별자 추출 ───────────────────
        left_id = ctx.identifier(0).getText()  # "block" | "msg" | "tx"
        right_id = ctx.identifier(1).getText() if ctx.identifier(1) else None
        global_name = f"{left_id}.{right_id}" if right_id else left_id

        # ─────────────────── 2) 유효성 검사 ───────────────────
        valid = {
            "block.basefee", "block.blobbasefee", "block.chainid", "block.coinbase",
            "block.difficulty", "block.gaslimit", "block.number", "block.prevrandao",
            "block.timestamp", "msg.sender", "msg.value", "tx.gasprice", "tx.origin"
        }
        if global_name not in valid:
            raise ValueError(f"[DebugGlobalVar] invalid global '{global_name}'")

        # ─────────────────── 3) 값 파싱 ───────────────────────
        gv_ctx = ctx.globalValue()
        firsttok = gv_ctx.getChild(0).getText()

        # helper - bit width 결정
        is_addr = global_name in {"block.coinbase", "msg.sender", "tx.origin"}
        bit_len = 160 if is_addr else 256

        # 3-A. [min , max] 형
        if firsttok == '[':
            min_v = int(gv_ctx.numberLiteral(0).getText(), 0)
            max_v = int(gv_ctx.numberLiteral(1).getText(), 0)
            if min_v > max_v:
                raise ValueError(f"[DebugGlobalVar] range invalid [{min_v},{max_v}]")
            value = UnsignedIntegerInterval(min_v, max_v, bit_len)

        # 3-B. symbolicAddress N  형
        elif firsttok == 'symbolicAddress':
            nid = int(gv_ctx.numberLiteral().getText(), 0)
            sm = self.contract_analyzer.sm  # AddressSymbolicManager
            sm.register_fixed_id(nid)  # (중복 호출 안전)
            value = sm.get_interval(nid)  # Interval [nid,nid]
            sm.bind_var(global_name, nid)  # alias 정보 기록

        else:
            raise ValueError("[DebugGlobalVar] unsupported value format")

        # ─────────────────── 4) GlobalVariable 객체 구성 ─────
        st = SolType()  # 빈 객체 하나 만들고
        st.typeCategory = "elementary"
        st.elementaryTypeName = "address" if is_addr else "uint"
        st.intTypeLength = bit_len  # 선택: 160 또는 256

        gv_obj = GlobalVariable(
            identifier=global_name,
            value=value,
            typeInfo=st  # ← 완성된 SolType 주입
        )

        # ─────────────────── 5) ContractAnalyzer 에 전달 ─────
        self.contract_analyzer.process_global_var_for_debug(gv_obj)
        return None

    # Visit a parse tree produced by SolidityParser#GlobalIntValue.
    def visitGlobalIntValue(self, ctx: SolidityParser.GlobalIntValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#GlobalAddressValue.
    def visitGlobalAddressValue(self, ctx: SolidityParser.GlobalAddressValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#debugStateVar.
    # Analyzer/EnhancedSolidityVisitor.py
    # ──────────────────────────────────────────────────────────────
    # helper : stateLocalValue  →   구체 객체(Interval · Bytes …)
    # ──────────────────────────────────────────────────────────────
    def _parse_state_local_value(self, sv_ctx):
        """
        stateLocalValue →
          • Integer / UnsignedInteger Interval
          • BoolInterval
          • UnsignedIntegerInterval(160-bit) for address
          • bytes / string literal 그대로
          • Enum 멤버 이름 (str)
          • Inline 배열 -> (nested) list
        """
        first = sv_ctx.getChild(0).getText()

        # ── ①  [min,max]  --------------------------------------------------
        if first == '[':
            lo = int(sv_ctx.numberLiteral(0).getText(), 0)
            hi = int(sv_ctx.numberLiteral(1).getText(), 0)
            cls = IntegerInterval if lo < 0 else UnsignedIntegerInterval
            return cls(lo, hi, 256)

        # ── ②  symbolicAddress N  → 160-bit interval [N,N] -----------------
        if first == 'symbolicAddress':
            nid = int(sv_ctx.numberLiteral().getText(), 0)
            sm = self.contract_analyzer.sm
            sm.register_fixed_id(nid)
            return sm.get_interval(nid)

        # ── ③  symbolicBytes / symbolicString  -----------------------------
        if first in ('symbolicBytes', 'symbolicString'):
            # hexStringLiteral 은 따옴표 포함 → getText() 로 그대로
            return f"{first} {sv_ctx.hexStringLiteral().getText()}"

        # ── ④  boolean  ----------------------------------------------------
        if first in ('true', 'false', 'any'):
            return {
                'true': BoolInterval(1, 1),
                'false': BoolInterval(0, 0),
                'any': BoolInterval(0, 1)
            }[first]

        # ── ⑤  enum  (identifier [. identifier])  -------------------------
        if isinstance(sv_ctx, SolidityParser.StateLocalEnumValueContext):
            if sv_ctx.identifier(1):  # enumName.member
                enum_name, member = sv_ctx.identifier(0).getText(), sv_ctx.identifier(1).getText()
                return f"{enum_name}.{member}"
            else:  # member  (단일)
                return sv_ctx.identifier(0).getText()

        # ── ⑥  inlineArrayAnnotation  -------------------------------------
        if isinstance(sv_ctx, SolidityParser.StateLocalInlineValueContext):
            return self._parse_inline_array(sv_ctx.inlineArrayAnnotation())

        # ── 디폴트 ---------------------------------------------------------
        raise ValueError("Unsupported stateLocalValue format")

    # ──────────────────────────────────────────────────────────────
    #  State-level 주석  (@StateVar …)
    # ──────────────────────────────────────────────────────────────
    def visitDebugStateVar(self, ctx: SolidityParser.DebugStateVarContext):
        # 1) LHS (testingExpression → Expression AST)
        lhs_expr = self.visitTestingExpression(ctx.testingExpression())

        # 2) RHS
        rhs_val = self._parse_state_local_value(ctx.stateLocalValue())

        # 3) ContractAnalyzer 전달
        self.contract_analyzer.process_state_var_for_debug(lhs_expr, rhs_val)
        return None

    # ──────────────────────────────────────────────────────────────
    #  Local-level 주석  (@LocalVar …)
    # ──────────────────────────────────────────────────────────────
    def visitDebugLocalVar(self, ctx: SolidityParser.DebugLocalVarContext):
        lhs_expr = self.visitTestingExpression(ctx.testingExpression())
        rhs_val = self._parse_state_local_value(ctx.stateLocalValue())

        self.contract_analyzer.process_local_var_for_debug(lhs_expr, rhs_val)
        return None

    # Visit a parse tree produced by SolidityParser#testingExpression.
    def visitTestingExpression(self, ctx: SolidityParser.TestingExpressionContext):
        """
                testingExpression : identifier subAccess* ;
                subAccess : '.' identifier | '[' expression ']' ;
                Build an Expression object representing the testing expression.
                """
        # 시작 식별자
        root = Expression(
            identifier=ctx.identifier().getText(),
            context="IdentifierExpContext"
        )
        # subAccess 처리 (있다면)
        if ctx.subAccess():
            for sub in ctx.subAccess():
                # 각 subAccess의 label는 우리 문법에서 두 종류로 구분됨
                # (1) TestingMemberAccess: '.' identifier
                # (2) TestingIndexAccess: '[' expression ']'
                if sub.getChild(0).getText() == '.':
                    member = sub.identifier().getText()
                    root = Expression(
                        base=root,
                        member=member,
                        operator='.',
                        context="TestingMemberAccess"
                    )
                elif sub.getChild(0).getText() == '[':
                    # index 접근: 내부 표현식을 방문해서 Expression 생성
                    index_expr = self.visitExpression(sub.expression())
                    root = Expression(
                        base=root,
                        index=index_expr,
                        access="index_access",
                        context="TestingIndexAccess"
                    )
                else:
                    raise ValueError("Unknown subAccess type.")
        return root

    def parse_number_bool_literal(self, literal_str: str):
        """
        Parses a literal string into an integer or boolean.
          "100"     -> 100 (int)
          "-20"     -> -20 (int)
          "true"    -> True (bool)
          "false"   -> False (bool)
        """
        if literal_str.lower() == "true":
            return True
        elif literal_str.lower() == "false":
            return False
        else:
            # 숫자 파싱 (예: 0x.., decimal, negative 등)
            return int(literal_str, 0)

    # Visit a parse tree produced by SolidityParser#TestingMemberAccess.
    def visitTestingMemberAccess(self, ctx: SolidityParser.TestingMemberAccessContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#TestingIndexAccess.
    def visitTestingIndexAccess(self, ctx: SolidityParser.TestingIndexAccessContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#StateLocalIntValue.
    def visitStateLocalIntValue(self, ctx: SolidityParser.StateLocalIntValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#StateLocalAddressValue.
    def visitStateLocalAddressValue(self, ctx: SolidityParser.StateLocalAddressValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#StateLocalByteValue.
    def visitStateLocalByteValue(self, ctx: SolidityParser.StateLocalByteValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#StateLocalStringValue.
    def visitStateLocalStringValue(self, ctx: SolidityParser.StateLocalStringValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#StateLocalBooleanValue.
    def visitStateLocalBoolValue(self, ctx: SolidityParser.StateLocalBoolValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#StateLocalEnumValue.
    def visitStateLocalEnumValue(self, ctx: SolidityParser.StateLocalEnumValueContext):
        return self.visitChildren(ctx)

    def _parse_inline_array(self, ia_ctx):
        """
        inlineArrayAnnotation → python list (재귀)
        - 숫자   →  int  / IntegerInterval([lo,lo])
        - array  →  nested list
        - arrayAddress → list[UnsignedIntegerInterval([id,id])]
        """

        def _ctx_label(ctx):
            "ANTLR alt-label 헬퍼"
            return type(ctx).__name__.removesuffix('Context')

        elems = []
        for el in ia_ctx.inlineElement():
            lbl = _ctx_label(el)
            if lbl == 'InlineIntElement':
                elems.append(int(el.getText(), 0))
            elif lbl == 'NestedArrayElement':
                elems.append(self._parse_inline_array(el.inlineArrayAnnotation()))
            elif lbl == 'AddrArrayElement':
                ids = [int(n.getText(), 0) for n in el.numberLiteral()]
                sm = self.contract_analyzer.sm
                elems.append(
                    [sm.get_interval(i) for i in ids]
                )
        return elems


    # Visit a parse tree produced by SolidityParser#StateLocalInlineValue.
    def visitStateLocalInlineValue(self, ctx: SolidityParser.StateLocalInlineValueContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#inlineArrayAnnotation.
    def visitInlineArrayAnnotation(self, ctx: SolidityParser.InlineArrayAnnotationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#InlineIntElement.
    def visitInlineIntElement(self, ctx: SolidityParser.InlineIntElementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#NestedArrayElement.
    def visitNestedArrayElement(self, ctx: SolidityParser.NestedArrayElementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#AddrArrayElement.
    def visitAddrArrayElement(self, ctx: SolidityParser.AddrArrayElementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveSimpleStatement.
    def visitInteractiveSimpleStatement(self, ctx:SolidityParser.InteractiveSimpleStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveVariableDeclarationStatement.
    def visitInteractiveVariableDeclarationStatement(self, ctx:SolidityParser.InteractiveVariableDeclarationStatementContext):
        # 1. 변수 선언 정보 가져오기
        type_ctx = ctx.variableDeclaration().typeName()
        var_name = ctx.variableDeclaration().identifier().getText()

        # dataLocation?  (memory / storage / calldata)
        data_loc = None
        #if ctx.dataLocation():
        #    data_loc = ctx.dataLocation().getText()  # 'storage' 등

        # 2. 초기화 값이 있는 경우 처리
        init_expr = None
        if ctx.expression():
            init_expr = self.visitExpression(ctx.expression())

        # 3. 변수 타입 정보 분석 및 적절한 Variables 객체 생성
        type_obj = SolType()
        type_obj = self.visitTypeName(type_ctx, type_obj)  # 타입 정보 분석

        # 5. ContractAnalyzer로 Variables 객체 및 lineComment 전달
        self.contract_analyzer.process_variable_declaration(
            type_obj=type_obj,
            var_name=var_name,
            init_expr=init_expr
        )

    # Visit a parse tree produced by SolidityParser#interactiveExpressionStatement.
    def visitInteractiveExpressionStatement(self, ctx:SolidityParser.InteractiveExpressionStatementContext):
        # 1. 표현식 방문
        expr_ctx = ctx.expression()
        expr = self.visitExpression(expr_ctx)

        # Handle assignment expressions
        if isinstance(expr_ctx, SolidityParser.AssignmentContext):
            self.contract_analyzer.process_assignment_expression(expr)
        elif isinstance(expr_ctx, SolidityParser.UnaryPrefixOpContext):
            self.contract_analyzer.process_unary_prefix_operation(expr)
        elif isinstance(expr_ctx, SolidityParser.UnarySuffixOpContext):
            self.contract_analyzer.process_unary_suffix_operation(expr)
        elif isinstance(expr_ctx, SolidityParser.FunctionCallContext):
            self.contract_analyzer.process_function_call(expr)
        elif isinstance(expr_ctx, SolidityParser.PayableFunctionCallContext):
            self.contract_analyzer.process_payable_function_call(expr)
        elif isinstance(expr_ctx, SolidityParser.FunctionCallOptionsContext):
            self.contract_analyzer.process_function_call_options(expr)
        elif isinstance(expr_ctx, SolidityParser.IdentifierExpContext) :
            self.contract_analyzer.process_identifier_expression(expr)
        else:
            raise ValueError(f"Unsupported expression context in interactiveExpressionStatement: {ctx}")

    # Visit a parse tree produced by SolidityParser#interactiveStateVariableElement.
    def visitInteractiveStateVariableElement(self, ctx:SolidityParser.InteractiveStateVariableElementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveEnumDefinition.
    def visitInteractiveEnumDefinition(self, ctx:SolidityParser.InteractiveEnumDefinitionContext):
        enum_name = ctx.identifier().getText()
        self.contract_analyzer.process_enum_definition(enum_name)
        return

    # Visit a parse tree produced by SolidityParser#interactiveStructDefinition.
    def visitInteractiveStructDefinition(self, ctx:SolidityParser.InteractiveStructDefinitionContext):
        struct_name = ctx.identifier().getText()
        self.contract_analyzer.process_struct_definition(struct_name)

    # Visit a parse tree produced by SolidityParser#interactiveEnumItems.
    def visitInteractiveEnumItems(self, ctx:SolidityParser.InteractiveEnumItemsContext):
        enum_items = [identifier.getText() for identifier in ctx.identifier()]

        self.contract_analyzer.process_enum_item(enum_items)

    # Visit a parse tree produced by SolidityParser#interactiveFunctionElement.
    def visitInteractiveFunctionElement(self, ctx:SolidityParser.InteractiveFunctionElementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveBlockItem.
    def visitInteractiveBlockItem(self, ctx:SolidityParser.InteractiveBlockItemContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#dataLocation.
    def visitDataLocation(self, ctx:SolidityParser.DataLocationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#stateMutability.
    def visitStateMutability(self, ctx:SolidityParser.StateMutabilityContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#block.
    def visitBlock(self, ctx:SolidityParser.BlockContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#uncheckedBlock.
    def visitUncheckedBlock(self, ctx:SolidityParser.UncheckedBlockContext):
        return self.contract_analyzer.process_unchecked_indicator()

    # Visit a parse tree produced by SolidityParser#statement.
    def visitStatement(self, ctx:SolidityParser.StatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#expressionStatement.
    def visitExpressionStatement(self, ctx:SolidityParser.ExpressionStatementContext):
        # 1. 표현식 방문
        expr_ctx = ctx.expression()
        return self.visitExpression(expr_ctx)

    # Visit a parse tree produced by SolidityParser#ifStatement.
    def visitIfStatement(self, ctx:SolidityParser.IfStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#tryStatement.
    def visitTryStatement(self, ctx:SolidityParser.TryStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#catchClause.
    def visitCatchClause(self, ctx:SolidityParser.CatchClauseContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#whileStatement.
    def visitWhileStatement(self, ctx:SolidityParser.WhileStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#VDContext.
    def visitVDContext(self, ctx:SolidityParser.VDContextContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#EContext.
    def visitEContext(self, ctx:SolidityParser.EContextContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#forStatement.
    def visitForStatement(self, ctx:SolidityParser.ForStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#inlineArrayExpression.
    def visitInlineArrayExpression(self, ctx:SolidityParser.InlineArrayExpressionContext):
        elements = []

        # 배열의 각 요소들을 순회하며 Expression으로 방문
        for expr_ctx in ctx.expression():
            element_expr = self.visitExpression(expr_ctx)  # 각 요소에 대해 Expression 객체 생성
            elements.append(element_expr)  # 리스트에 추가

        # Expression 객체로 배열을 표현
        array_expr = Expression(
            elements=elements,  # 배열의 요소들 저장
            expr_type='array',  # 표현식 타입을 배열로 지정
            context='InlineArrayExpressionContext'
        )

        return array_expr

    # Visit a parse tree produced by SolidityParser#assemblyStatement.
    def visitAssemblyStatement(self, ctx:SolidityParser.AssemblyStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#assemblyFlags.
    def visitAssemblyFlags(self, ctx:SolidityParser.AssemblyFlagsContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#assemblyFlagString.
    def visitAssemblyFlagString(self, ctx:SolidityParser.AssemblyFlagStringContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulStatement.
    def visitYulStatement(self, ctx:SolidityParser.YulStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulBlock.
    def visitYulBlock(self, ctx:SolidityParser.YulBlockContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulVariableDeclaration.
    def visitYulVariableDeclaration(self, ctx:SolidityParser.YulVariableDeclarationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulAssignment.
    def visitYulAssignment(self, ctx:SolidityParser.YulAssignmentContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulIfStatement.
    def visitYulIfStatement(self, ctx:SolidityParser.YulIfStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulForStatement.
    def visitYulForStatement(self, ctx:SolidityParser.YulForStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulSwitchStatement.
    def visitYulSwitchStatement(self, ctx:SolidityParser.YulSwitchStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulFunctionDefinition.
    def visitYulFunctionDefinition(self, ctx:SolidityParser.YulFunctionDefinitionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulPath.
    def visitYulPath(self, ctx:SolidityParser.YulPathContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulFunctionCall.
    def visitYulFunctionCall(self, ctx:SolidityParser.YulFunctionCallContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulBoolean.
    def visitYulBoolean(self, ctx:SolidityParser.YulBooleanContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulLiteral.
    def visitYulLiteral(self, ctx:SolidityParser.YulLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#yulExpression.
    def visitYulExpression(self, ctx:SolidityParser.YulExpressionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#doWhileStatement.
    def visitDoWhileStatement(self, ctx:SolidityParser.DoWhileStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#continueStatement.
    def visitContinueStatement(self, ctx:SolidityParser.ContinueStatementContext):
        return self.contract_analyzer.process_continue_statement()

    # Visit a parse tree produced by SolidityParser#breakStatement.
    def visitBreakStatement(self, ctx:SolidityParser.BreakStatementContext):
        return self.contract_analyzer.process_break_statement()

    # Visit a parse tree produced by SolidityParser#returnStatement.
    def visitReturnStatement(self, ctx:SolidityParser.ReturnStatementContext):
        # 1. 반환되는 expression 처리
        if ctx.expression():
            return_expr = self.visitExpression(ctx.expression())
        else:
            return_expr = None

        # 2. ContractAnalyzer에 반환 표현식 전달
        self.contract_analyzer.process_return_statement(return_expr)

    # Visit a parse tree produced by SolidityParser#emitStatement.
    def visitEmitStatement(self, ctx:SolidityParser.EmitStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#revertStatement.
    def visitRevertStatement(self, ctx:SolidityParser.RevertStatementContext):
        # 1. identifier와 stringLiteral 둘 중 하나를 처리
        revert_identifier = None
        string_literal = None

        if ctx.identifier():
            revert_identifier = self.visitIdentifier(ctx.identifier())
        elif ctx.stringLiteral():
            string_literal = self.visitStringLiteral(ctx.stringLiteral())

        # 2. callArgumentList가 존재하는지 여부 확인 및 처리
        call_argument_list = []
        if ctx.callArgumentList():
            call_argument_list = self.visitCallArgumentList(ctx.callArgumentList())

        # 3. ContractAnalyzer의 process_revert_statement 메소드 호출
        self.contract_analyzer.process_revert_statement(revert_identifier, string_literal, call_argument_list)

    # Visit a parse tree produced by SolidityParser#requireStatement.
    def visitRequireStatement(self, ctx:SolidityParser.RequireStatementContext):
        # 1. 'require'의 조건식(expression)을 방문하여 추출
        condition_expr = self.visit(ctx.expression())

        # 2. 에러 메시지(stringLiteral) 처리 - 선택적
        if ctx.stringLiteral():
            error_message = ctx.stringLiteral().getText()
        else:
            error_message = None

        # 3. ContractAnalyzer에서 process_require_statement 호출
        self.contract_analyzer.process_require_statement(condition_expr, error_message)

    # Visit a parse tree produced by SolidityParser#assertStatement.
    def visitAssertStatement(self, ctx:SolidityParser.AssertStatementContext):
        # 1. expression을 방문해서 조건식을 가져옴
        condition_expr = self.visitExpression(ctx.expression())

        # 2. ContractAnalyzer에서 process_assert_statement 호출
        self.contract_analyzer.process_assert_statement(condition_expr)

    # Visit a parse tree produced by SolidityParser#variableDeclarationStatement.
    def visitVariableDeclarationStatement(self, ctx:SolidityParser.VariableDeclarationStatementContext):
        # 1. 변수 선언 정보 가져오기
        type_ctx = ctx.variableDeclaration().typeName()
        var_name = ctx.variableDeclaration().identifier().getText()

        # 2. 초기화 값이 있는 경우 처리
        init_expr = None
        if ctx.expression():
            init_expr = self.visitExpression(ctx.expression())

        # 3. 변수 타입 정보 분석 및 적절한 Variables 객체 생성
        type_obj = SolType()
        type_obj = self.visitTypeName(type_ctx, type_obj)  # 타입 정보 분석

        return type_obj, var_name, init_expr

    # Visit a parse tree produced by SolidityParser#interactiveStatement.
    def visitInteractiveStatement(self, ctx:SolidityParser.InteractiveStatementContext):
        if ctx.interactiveSimpleStatement():
            return self.visitInteractiveSimpleStatement(ctx.interactiveSimpleStatement())
        elif ctx.interactiveIfStatement():
            return self.visitInteractiveIfStatement(ctx.interactiveIfStatement())
        elif ctx.interactiveForStatement():
            return self.visitInteractiveForStatement(ctx.interactiveForStatement())
        elif ctx.interactiveWhileStatement():
            return self.visitInteractiveWhileStatement(ctx.interactiveWhileStatement())
        elif ctx.interactiveDoWhileDoStatement():
            return self.visitInteractiveDoWhileDoStatement(ctx.interactiveDoWhileDoStatement())
        elif ctx.continueStatement():
            return self.visitContinueStatement(ctx.continueStatement())
        elif ctx.breakStatement():
            return self.visitBreakStatement(ctx.breakStatement())
        elif ctx.interactiveTryStatement():
            return self.visitInteractiveTryStatement(ctx.interactiveTryStatement())
        elif ctx.returnStatement():
            return self.visitReturnStatement(ctx.returnStatement())
        elif ctx.emitStatement():
            return self.visitEmitStatement(ctx.emitStatement())
        elif ctx.revertStatement():
            return self.visitRevertStatement(ctx.revertStatement())
        elif ctx.assemblyStatement():
            # assembly에 대한 처리 (나중에 구현 예정)
            pass
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveIfStatement.
    def visitInteractiveIfStatement(self, ctx:SolidityParser.InteractiveIfStatementContext):
        # 1. 조건식 표현식 방문
        condition_expr = self.visitExpression(ctx.expression())

        # 부모 컨텍스트가 else문에서 온 경우인지 확인
        if ctx.parentCtx and isinstance(ctx.parentCtx, SolidityParser.InteractiveElseStatementContext):
            # else if 문 처리
            self.contract_analyzer.process_else_if_statement(condition_expr)
        else:
            # if 문 처리
            self.contract_analyzer.process_if_statement(condition_expr)

    # Visit a parse tree produced by SolidityParser#interactiveElseStatement.
    def visitInteractiveElseStatement(self, ctx:SolidityParser.InteractiveElseStatementContext):
        # 'else if' 블록인지 아니면 'else' 블록인지를 판단
        if ctx.interactiveIfStatement():
            # 'else if' 문이 존재하는 경우
            return self.visitInteractiveIfStatement(ctx.interactiveIfStatement())
        else:
            # 'else' 블록을 처리
            self.contract_analyzer.process_else_statement()

    # Visit a parse tree produced by SolidityParser#interactiveForStatement.
    def visitInteractiveForStatement(
            self, ctx: SolidityParser.InteractiveForStatementContext):

        # init ----------------------------------------------------------------
        init_stmt = {}
        init_ctx = ctx.simpleStatement()
        if init_ctx:  # simpleStatement 존재
            if isinstance(init_ctx, SolidityParser.VDContextContext):
                t, n, v = self.visitVDContext(init_ctx)
                init_stmt = {'context': 'VariableDeclaration',
                             'initVarType': t, 'initVarName': n, 'initValExpr': v}
            else:  # expressionStatement
                init_stmt = {'context': 'Expression',
                             'initExpr': self.visitExpression(init_ctx.expression())}

        # condition -----------------------------------------------------------
        cond_expr = None
        exprs = ctx.expression()  # 최대 두 개
        if len(exprs) >= 1:
            cond_expr = self.visitExpression(exprs[0])

        # increment -----------------------------------------------------------
        inc_expr = None
        if len(exprs) == 2:
            inc_expr = self.visitExpression(exprs[1])

        # ContractAnalyzer 로 전달 -------------------------------------------
        self.contract_analyzer.process_for_statement(
            initial_statement=init_stmt,
            condition_expr=cond_expr,
            increment_expr=inc_expr
        )

    # Visit a parse tree produced by SolidityParser#interactiveWhileStatement.
    def visitInteractiveWhileStatement(self, ctx:SolidityParser.InteractiveWhileStatementContext):
        # 1. 조건식 표현식 방문
        condition_expr = self.visitExpression(ctx.expression())

        # 2. ContractAnalyzer의 process_while_statement 호출
        self.contract_analyzer.process_while_statement(condition_expr)

    # Visit a parse tree produced by SolidityParser#interactiveDoWhileDoStatement.
    def visitInteractiveDoWhileDoStatement(self, ctx:SolidityParser.InteractiveDoWhileDoStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveDoWhileWhileStatement.
    def visitInteractiveDoWhileWhileStatement(self, ctx:SolidityParser.InteractiveDoWhileWhileStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveTryStatement.
    def visitInteractiveTryStatement(self, ctx:SolidityParser.InteractiveTryStatementContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#interactiveCatchClause.
    def visitInteractiveCatchClause(self, ctx:SolidityParser.InteractiveCatchClauseContext):
        catch_node = f"Catch_{ctx.start.line}"
        self.contract_analyzer.add_control_flow_node(catch_node, ctx)

        # Catch 블록 내의 매개변수 목록 처리
        if ctx.parameterList():
            self.visit(ctx.parameterList())

        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#elementaryTypeName.
    def visitElementaryTypeName(self, ctx:SolidityParser.ElementaryTypeNameContext):
        return self.visitChildren(ctx)

    def visitExpression(self, ctx):
        # IndexAccess (배열 인덱스 접근)
        if isinstance(ctx, SolidityParser.IndexAccessContext):
            return self.visitIndexAccess(ctx)

        # IndexRangeAccess (배열 범위 접근)
        elif isinstance(ctx, SolidityParser.IndexRangeAccessContext):
            return self.visitIndexRangeAccess(ctx)

        # MemberAccess (객체 멤버 접근)
        elif isinstance(ctx, SolidityParser.MemberAccessContext):
            return self.visitMemberAccess(ctx)

        # FunctionCallOptions (함수 호출 옵션)
        elif isinstance(ctx, SolidityParser.FunctionCallOptionsContext):
            return self.visitFunctionCallOptions(ctx)

        # FunctionCall (함수 호출)
        elif isinstance(ctx, SolidityParser.FunctionCallContext):
            return self.visitFunctionCall(ctx)

        # PayableFunctionCall (Payable 함수 호출)
        elif isinstance(ctx, SolidityParser.PayableFunctionCallContext):
            return self.visitPayableFunctionCall(ctx)

        # TypeConversion (타입 변환)
        elif isinstance(ctx, SolidityParser.TypeConversionContext):
            return self.visitTypeConversion(ctx)

        elif isinstance(ctx, SolidityParser.MetaTypeContext):
            return self.visitMetaType(ctx)

        # UnaryPrefixOp (단항 연산자 - 전위)
        elif isinstance(ctx, SolidityParser.UnaryPrefixOpContext):
            return self.visitUnaryPrefixOp(ctx)

        # UnarySuffixOp (단항 연산자 - 후위)
        elif isinstance(ctx, SolidityParser.UnarySuffixOpContext):
            return self.visitUnarySuffixOp(ctx)

        # Exponentiation (지수 연산)
        elif isinstance(ctx, SolidityParser.ExponentiationContext):
            return self.visitExponentiation(ctx)

        # MultiplicativeOp (곱셈/나눗셈/나머지 연산)
        elif isinstance(ctx, SolidityParser.MultiplicativeOpContext):
            return self.visitMultiplicativeOp(ctx)

        # AdditiveOp (덧셈/뺄셈 연산)
        elif isinstance(ctx, SolidityParser.AdditiveOpContext):
            return self.visitAdditiveOp(ctx)

        # ShiftOp (비트 시프트 연산)
        elif isinstance(ctx, SolidityParser.ShiftOpContext):
            return self.visitShiftOp(ctx)

        # BitAndOp (비트 AND 연산)
        elif isinstance(ctx, SolidityParser.BitAndOpContext):
            return self.visitBitAndOp(ctx)

        # BitXorOp (비트 XOR 연산)
        elif isinstance(ctx, SolidityParser.BitXorOpContext):
            return self.visitBitXorOp(ctx)

        # BitOrOp (비트 OR 연산)
        elif isinstance(ctx, SolidityParser.BitOrOpContext):
            return self.visitBitOrOp(ctx)

        # RelationalOp (관계 연산자)
        elif isinstance(ctx, SolidityParser.RelationalOpContext):
            return self.visitRelationalOp(ctx)

        # EqualityOp (동등성 연산자)
        elif isinstance(ctx, SolidityParser.EqualityOpContext):
            return self.visitEqualityOp(ctx)

        # AndOperation (논리 AND 연산자)
        elif isinstance(ctx, SolidityParser.AndOperationContext):
            return self.visitAndOperation(ctx)

        # OrOperation (논리 OR 연산자)
        elif isinstance(ctx, SolidityParser.OrOperationContext):
            return self.visitOrOperation(ctx)

        # ConditionalExp (삼항 연산자)
        elif isinstance(ctx, SolidityParser.ConditionalExpContext):
            return self.visitConditionalExp(ctx)

        # Assignment (할당 연산자)
        elif isinstance(ctx, SolidityParser.AssignmentContext):
            return self.visitAssignment(ctx)

        # NewExp (new 연산자)
        elif isinstance(ctx, SolidityParser.NewExpContext):
            return self.visitNewExp(ctx)

        # TupleExp (튜플)
        elif isinstance(ctx, SolidityParser.TupleExpContext):
            return self.visitTupleExp(ctx)

        # InlineArrayExp (배열 리터럴)
        elif isinstance(ctx, SolidityParser.InlineArrayExpContext):
            return self.visitInlineArrayExp(ctx)

        # IdentifierExp (식별자)
        elif isinstance(ctx, SolidityParser.IdentifierExpContext):
            return self.visitIdentifierExp(ctx)

        # LiteralExp (리터럴)
        elif isinstance(ctx, SolidityParser.LiteralExpContext):
            return self.visitLiteralExp(ctx)

        # LiteralSubDenomination (리터럴 서브 단위)
        elif isinstance(ctx, SolidityParser.LiteralSubDenominationContext):
            return self.visitLiteralSubDenomination(ctx)

        # TypeNameExp (타입 이름)
        elif isinstance(ctx, SolidityParser.TypeNameExpContext):
            return self.visitTypeNameExp(ctx)

        else:
            raise NotImplementedError(f"Unhandled expression context: {type(ctx).__name__}")

    def visitIndexAccess(self, ctx):
        # 1. 배열 또는 매핑 표현식 방문
        base_expr = self.visitExpression(ctx.expression(0))

        # 2. 인덱스 표현식 방문 (optional)
        if ctx.expression(1):
            index_expr = self.visitExpression(ctx.expression(1))
        else:
            index_expr = None  # 인덱스가 없을 수도 있습니다 (예: array[])

        # 3. Expression 객체 생성
        result_expr = Expression(
            base=base_expr,
            index=index_expr,
            access='index_access',
            context='IndexAccessContext'
        )

        return result_expr

    def visitIndexRangeAccess(self, ctx):
        # 1. 베이스 표현식 방문 (예: array)
        base_expr = self.visitExpression(ctx.expression(0))

        # 2. 시작 인덱스 방문 (선택적)
        start_expr = None
        end_expr = None

        # 자식 노드의 개수
        child_count = ctx.getChildCount()

        # 구조 파악:
        # - ctx.getChild(0): base expression (array)
        # - ctx.getChild(1): '['
        # - 이후의 자식들은 다음과 같은 패턴을 가짐:
        #   - 만약 시작 인덱스가 존재하면 ctx.expression(1)이 있음
        #   - ':' 토큰은 반드시 존재함
        #   - 끝 인덱스가 존재하면 ctx.expression(2)이 있음
        #   - ']' 토큰은 마지막에 위치함

        # 3. 시작 인덱스와 끝 인덱스의 위치 파악
        # 표현식의 개수를 확인합니다.
        expression_count = len(ctx.expression())

        if expression_count == 1:
            # 시작 인덱스와 끝 인덱스가 모두 없는 경우 (예: array[:])
            # 이 경우는 슬라이스의 모든 요소를 선택하는 것을 의미합니다.
            start_expr = None
            end_expr = None
        elif expression_count == 2:
            # 시작 인덱스나 끝 인덱스 중 하나만 존재하는 경우
            # ':'의 위치를 찾아서 구분합니다.
            colon_index = None
            for i in range(child_count):
                if ctx.getChild(i).getText() == ':':
                    colon_index = i
                    break

            if colon_index is not None:
                # ':' 앞의 표현식을 확인하여 시작 인덱스인지 끝 인덱스인지 결정
                if ctx.getChild(colon_index - 1) in ctx.expression():
                    # ':' 앞에 표현식이 있으면 시작 인덱스
                    start_expr = self.visitExpression(ctx.expression(1))
                    end_expr = None
                else:
                    # ':' 앞에 표현식이 없으면 시작 인덱스 없음
                    start_expr = None
                    end_expr = self.visitExpression(ctx.expression(1))
            else:
                # ':'가 없으면 잘못된 구조이므로 예외 처리
                raise SyntaxError("Invalid index range access syntax.")
        elif expression_count == 3:
            # 시작 인덱스와 끝 인덱스가 모두 존재하는 경우
            start_expr = self.visitExpression(ctx.expression(1))
            end_expr = self.visitExpression(ctx.expression(2))
        else:
            # 예상치 못한 경우 예외 처리
            raise SyntaxError("Invalid number of expressions in index range access.")

        # 4. Expression 객체 생성
        result_expr = Expression(
            base=base_expr,
            start_index=start_expr,
            end_index=end_expr,
            operator='[:]',
            context='IndexRangeAccessContext'
        )

        return result_expr

    def visitMemberAccess(self, ctx):
        # 1. 베이스 표현식 방문
        base_expr = self.visitExpression(ctx.expression())

        # 2. 멤버 이름 추출
        if ctx.identifier():
            member_name = ctx.identifier().getText()
        else:
            # 'address' 키워드인 경우
            member_name = ctx.getChild(2).getText()

        # 3. Expression 객체 생성
        result_expr = Expression(
            base=base_expr,
            member=member_name,
            operator='.',
            context='MemberAccessContext'
        )

        return result_expr

    def visitMetaType(self, ctx: SolidityParser.MetaTypeContext):
        """
        grammar:
            MetaType : 'type' '(' typeName ')'   (#에 해당)
        반환값은 이후의 MemberAccess(.max / .min 등)를 처리하기 위해
        base-expression 역할만 하면 되므로 ‘identifier’ 하나만 넣어둔다.
        """
        # ① 안쪽 typeName 을 소스 그대로 추출
        type_name_txt = ctx.typeName().getText()  # 예: 'uint256'

        # ② Expression 생성
        #    identifier = 'type(uint256)'  로 두고
        #    context    = 'MetaTypeContext' 로 구분만 해둔다.
        return Expression(
            identifier=f"type({type_name_txt})",
            context="MetaTypeContext"
        )

    def visitFunctionCallOptions(self, ctx):
        # 1. 베이스 표현식 방문
        base_expr = self.visitExpression(ctx.expression())

        # 2. 옵션 매개변수 처리
        options = {}

        # 옵션 매개변수가 존재하는지 확인
        # 중괄호 안에 있는 자식 노드들을 순회하여 옵션들을 추출합니다.
        # 구조:
        # - '{' 토큰은 ctx.getChild(1)
        # - 옵션 매개변수들은 그 이후의 자식 노드들에 위치
        # - '}' 토큰은 마지막 자식 노드

        child_count = ctx.getChildCount()
        # 옵션 매개변수가 시작되는 인덱스 ( '{' 다음 )
        options_start_index = 2
        # 옵션 매개변수가 끝나는 인덱스 ( '}' 이전 )
        options_end_index = child_count - 1

        i = options_start_index
        while i < options_end_index:
            # 옵션 이름 추출 (identifier)
            option_name = ctx.getChild(i).getText()
            i += 1  # ':' 토큰으로 이동
            if ctx.getChild(i).getText() != ':':
                raise SyntaxError("Expected ':' after option name.")
            i += 1  # 옵션 값 표현식으로 이동
            # 옵션 값 표현식 방문
            option_value_expr = self.visitExpression(ctx.getChild(i))
            i += 1  # 다음 토큰으로 이동

            # 옵션 매개변수 딕셔너리에 추가
            options[option_name] = option_value_expr

            # 다음 옵션이 있는지 확인 (',' 또는 끝)
            if i < options_end_index and ctx.getChild(i).getText() == ',':
                i += 1  # 다음 옵션으로 이동
            else:
                break  # 옵션 매개변수의 끝

        # 3. Expression 객체 생성
        result_expr = Expression(
            function=base_expr,
            options=options,
            operator='{}',
            context='FunctionCallOptionContext'
        )

        return result_expr

    def visitFunctionCall(self, ctx):
        # 1. 함수 표현식 방문
        function_expr = self.visitExpression(ctx.expression())

        # 2. 인자 목록 처리
        arguments, named_arguments = self.process_arguments(ctx.callArgumentList())

        # 3. Expression 객체 생성
        result_expr = Expression(
            function=function_expr,
            arguments=arguments,
            named_arguments=named_arguments,
            operator='()',
            context='FunctionCallContext'
        )

        return result_expr

    def visitPayableFunctionCall(self, ctx):
        # 1. 'payable' 키워드 처리
        payable_keyword = ctx.PayableKeyword().getText()
        function_expr = Expression(identifier=payable_keyword)

        # 2. 인자 목록 처리
        arguments, named_arguments = self.process_arguments(ctx.callArgumentList())

        # 3. Expression 객체 생성
        result_expr = Expression(
            function=function_expr,
            arguments=arguments,
            named_arguments=named_arguments,
            operator='()',
            context='PayableFunctionCallContext'
        )

        return result_expr

    def process_arguments(self, call_args_ctx):
        arguments = []
        named_arguments = {}

        if call_args_ctx:
            child_count = call_args_ctx.getChildCount()
            if child_count < 2:
                raise SyntaxError("Invalid function call syntax.")

            if child_count == 2:
                # This means we have '()' with no arguments
                pass  # No arguments
            else:
                # Check if the first token after '(' is '{'
                if call_args_ctx.getChild(1).getText() == '{':
                    # Handle named arguments
                    i = 2  # Start after '{'
                    while i < child_count - 2:
                        arg_name = call_args_ctx.getChild(i).getText()
                        i += 1  # Move to ':'
                        if call_args_ctx.getChild(i).getText() != ':':
                            raise SyntaxError("Expected ':' after argument name.")
                        i += 1  # Move to expression
                        arg_expr_ctx = call_args_ctx.getChild(i)
                        arg_expr = self.visitExpression(arg_expr_ctx)
                        named_arguments[arg_name] = arg_expr
                        i += 1  # Move to next token
                        if i < child_count - 1 and call_args_ctx.getChild(i).getText() == ',':
                            i += 1  # Move to next argument
                        elif call_args_ctx.getChild(i).getText() == '}':
                            i += 1  # Skip '}'
                            break
                        else:
                            raise SyntaxError("Expected ',' or '}' in named arguments.")
                else:
                    # Handle positional arguments
                    i = 1  # Start after '('
                    while i < child_count - 1:
                        arg_ctx = call_args_ctx.getChild(i)
                        if arg_ctx.getText() == ',':
                            i += 1
                            continue
                        arg_expr = self.visitExpression(arg_ctx)
                        arguments.append(arg_expr)
                        i += 1
        else:
            pass  # No arguments (shouldn't occur with the adjusted grammar)

        return arguments if arguments else None, named_arguments if named_arguments else None

    # Visit a parse tree produced by SolidityParser#IdentifierExp.
    def visitIdentifierExp(self, ctx:SolidityParser.IdentifierExpContext):
        # 식별자 이름 추출
        identifier_name = ctx.getText()
        result_expr = Expression(identifier=identifier_name,
                                 context='IdentifierExpContext')
        return result_expr

    # Visit a parse tree produced by SolidityParser#LiteralExp.
    def visitLiteralExp(self, ctx:SolidityParser.LiteralExpContext):
        # 리터럴 값 추출
        literal_value = ctx.getText()
        result_expr = Expression(literal=literal_value,
                                 context='LiteralExpContext')

        # 리터럴 값이 숫자인 경우 int 또는 uint로 설정
        if literal_value.isdigit() or (literal_value.startswith('0x') or literal_value.startswith('0X')):
            # 숫자 리터럴 처리: 10진수, 16진수 구분
            result_expr.expr_type = 'uint' if literal_value.isdigit() else 'int'
            result_expr.type_length = 256  # 기본적으로 256비트로 가정

        # Boolean 리터럴인 경우
        elif literal_value.lower() == 'true' or literal_value.lower() == 'false':
            result_expr.expr_type = 'bool'

        # 그 외 문자열 리터럴 등
        else:
            result_expr.expr_type = 'string'  # 문자열 또는 기타 리터럴 값

        return result_expr

    # Visit a parse tree produced by SolidityParser#ConditionalExp.
    def visitConditionalExp(self, ctx:SolidityParser.ConditionalExpContext):
        # 조건식 방문
        condition_expr = self.visitExpression(ctx.expression(0))

        # 참일 때의 표현식 방문
        true_expr = self.visitExpression(ctx.expression(1))

        # 거짓일 때의 표현식 방문
        false_expr = self.visitExpression(ctx.expression(2))

        # Expression 객체 생성
        result_expr = Expression(
            condition=condition_expr,
            true_expr=true_expr,
            false_expr=false_expr,
            operator='?:',
            context='ConditionalExpContext'
        )

        return result_expr

    # Visit a parse tree produced by SolidityParser#Exponentiation.
    def visitExponentiation(self, ctx:SolidityParser.ExponentiationContext):
        # 좌측 표현식 방문
        left_expr = self.visitExpression(ctx.expression(0))

        # 우측 표현식 방문
        right_expr = self.visitExpression(ctx.expression(1))

        # 연산자 설정
        operator = '**'

        # Expression 객체 생성
        result_expr = Expression(
            left=left_expr,
            operator=operator,
            right=right_expr,
            context='ExponentiationContext'
        )

        return result_expr

    def visitLiteralSubDenomination(
            self, ctx: SolidityParser.LiteralSubDenominationContext):
        """
        1 weeks  → 604 800
        5 ether → 5 * 10**18
        """

        # ── ① wrapper 노드가 있으면 한 번 더 파고들기 ─────────────────
        if isinstance(ctx.getChild(0), SolidityParser.LiteralWithSubDenominationContext):
            ctx = ctx.getChild(0)  # 실제 numberLiteral · SubDenomination 가 있는 노드

        # ── ② 토큰 추출 ────────────────────────────────────────────────
        num_txt = ctx.numberLiteral().getText()  # '1', '0xFF', …
        denom_tok = ctx.getToken(SolidityParser.SubDenomination, 0)  # 토큰 객체
        denom_txt = denom_tok.getText()  # 'weeks', 'ether', …

        # ── ③ 숫자 → int 변환 -------------------------------------------------
        try:
            base_val = int(num_txt, 0)  # 0x… 형태 지원
        except ValueError:
            raise ValueError(f"invalid numeric literal “{num_txt}”")

        # ── ④ 단위 매핑 -------------------------------------------------------
        if denom_txt not in TIME_VALUE:
            raise ValueError(f"unknown sub-denomination “{denom_txt}”")
        final_val = base_val * TIME_VALUE[denom_txt]

        # ── ⑤ uint256 상수 Expression 반환 -----------------------------------
        return Expression(
            literal=str(final_val),  # 예: '604800'
            var_type="uint256",
            type_length=256,
            context="LiteralSubDenomination"
        )

    def visitTupleExp(self,
                      ctx: SolidityParser.TupleExpContext):
        inner = ctx.tupleExpression()  # ← 먼저 꺼냄
        elems = [self.visit(e) for e in inner.expression()]
        return Expression(
            context="TupleExpressionContext",
            elements=elems
        )

    # Visit a parse tree produced by SolidityParser#Assignment.
    def visitAssignment(self, ctx:SolidityParser.AssignmentContext):
        # 좌측 표현식 방문
        left_expr = self.visitExpression(ctx.expression(0))

        # 우측 표현식 방문
        right_expr = self.visitExpression(ctx.expression(1))

        # 연산자 추출
        operator = ctx.getChild(1).getText()

        # Expression 객체 생성
        result_expr = Expression(
            left=left_expr,
            operator=operator,
            right=right_expr,
            context='AssignmentOpContext'
        )

        return result_expr

    # Visit a parse tree produced by SolidityParser#TypeConversion.
    def visitTypeConversion(self, ctx: SolidityParser.TypeConversionContext):
        ty = ctx.elementaryTypeName().getText()  # 'address', 'uint256', …
        expr = self.visitExpression(ctx.expression())

        return Expression(
            typeName=ty,
            expression=expr,
            operator='typecast',
            context='TypeConversion'
        )

    # Visit a parse tree produced by SolidityParser#UnaryPrefixOp.
    def visitUnaryPrefixOp(self, ctx:SolidityParser.UnaryPrefixOpContext):
        operator = ctx.getChild(0).getText()
        expression = self.visitExpression(ctx.expression())
        result_expr = Expression(
            operator=operator,
            expression=expression,
            is_postfix=False,
            context='UnaryPrefixOpContext'
        )
        return result_expr

    # Visit a parse tree produced by SolidityParser#BitXorOp.
    def visitBitXorOp(self, ctx:SolidityParser.BitXorOpContext):
        # 좌측 표현식 방문
        left_expr = self.visitExpression(ctx.expression(0))

        # 우측 표현식 방문
        right_expr = self.visitExpression(ctx.expression(1))

        # 연산자 설정 ('^')
        operator = '^'

        # Expression 객체 생성
        result_expr = Expression(
            left=left_expr,
            operator=operator,
            right=right_expr,
            context='BitXorOpContext'
        )

        return result_expr

    # Visit a parse tree produced by SolidityParser#AdditiveOp.
    def visitAdditiveOp(self, ctx:SolidityParser.AdditiveOpContext):
        # 좌측 표현식 방문
        left_expr = self.visitExpression(ctx.expression(0))

        # 우측 표현식 방문
        right_expr = self.visitExpression(ctx.expression(1))

        # 연산자 추출 ('+', '-')
        operator = ctx.getChild(1).getText()

        # Expression 객체 생성
        result_expr = Expression(
            left=left_expr,
            operator=operator,
            right=right_expr,
            context='AdditiveOpContext'
        )

        return result_expr

    def _array_length_expr(self, type_ctx):
        """
        type_ctx : SolidityParser.TypeNameContext
        반환      : length  Expression  (없으면 None)
        """
        # 배열이 중첩되어도 가장 바깥쪽 ‘[]’ 부터 검사
        while isinstance(type_ctx, SolidityParser.ArrayTypeContext):
            # '[' expression? ']'  → 자식 0 = baseType, 1 = expression?
            if type_ctx.expression():
                return self.visit(type_ctx.expression())  # Expression 객체
            type_ctx = type_ctx.typeName()  # 더 안쪽으로…
        return None

    # Visit a parse tree produced by SolidityParser#NewExp.
    def visitNewExp(self, ctx: SolidityParser.NewExpContext):
        type_obj = SolType()
        self.visitTypeName(ctx.typeName(), type_obj)  # 타입 파싱

        length_expr = self._array_length_expr(ctx.typeName())

        return Expression(
            context="NewExpContext",
            typeName=type_obj,
            arguments=[length_expr] if length_expr else []  # ← 여기에만 넣음
        )

    # Visit a parse tree produced by SolidityParser#BitAndOp.
    def visitBitAndOp(self, ctx:SolidityParser.BitAndOpContext):
        # 좌측 표현식 방문
        left_expr = self.visitExpression(ctx.expression(0))

        # 우측 표현식 방문
        right_expr = self.visitExpression(ctx.expression(1))

        # 연산자 설정 ('&')
        operator = '&'

        # Expression 객체 생성
        result_expr = Expression(
            left=left_expr,
            operator=operator,
            right=right_expr,
            context='BitAndOpContext'
        )

        return result_expr

    # Visit a parse tree produced by SolidityParser#BitOrOp.
    def visitBitOrOp(self, ctx:SolidityParser.BitOrOpContext):
        # 좌측 표현식 방문
        left_expr = self.visitExpression(ctx.expression(0))

        # 우측 표현식 방문
        right_expr = self.visitExpression(ctx.expression(1))

        # 연산자 설정 ('|')
        operator = '|'

        # Expression 객체 생성
        result_expr = Expression(
            left=left_expr,
            operator=operator,
            right=right_expr,
            context='BitOrOpContext'
        )

        return result_expr

    # Visit a parse tree produced by SolidityParser#UnarySuffixOp.
    def visitUnarySuffixOp(self, ctx:SolidityParser.UnarySuffixOpContext):
        # 피연산자 표현식 방문
        expr = self.visitExpression(ctx.expression())

        # 연산자 추출
        operator = ctx.getChild(1).getText()

        # Expression 객체 생성
        result_expr = Expression(
            operator=operator,
            expression=expr,
            is_postfix=True,  # 후위 연산자임을 표시
            context='UnarySuffixOpContext'
        )

        return result_expr

    # Visit a parse tree produced by SolidityParser#MultiplicativeOp.
    def visitMultiplicativeOp(self, ctx:SolidityParser.MultiplicativeOpContext):
        # 좌측 표현식 방문
        left_expr = self.visitExpression(ctx.expression(0))

        # 우측 표현식 방문
        right_expr = self.visitExpression(ctx.expression(1))

        # 연산자 추출 ('*', '/', '%')
        operator = ctx.getChild(1).getText()

        # Expression 객체 생성
        result_expr = Expression(
            left=left_expr,
            operator=operator,
            right=right_expr,
            context='MultiplicativeOpContext'
        )

        return result_expr

    # Visit a parse tree produced by SolidityParser#EqualityOp.
    def visitEqualityOp(self, ctx:SolidityParser.EqualityOpContext):
        # 좌측 표현식 방문
        left_expr = self.visitExpression(ctx.expression(0))

        # 우측 표현식 방문
        right_expr = self.visitExpression(ctx.expression(1))

        # 연산자 추출 ('==', '!=')
        operator = ctx.getChild(1).getText()

        # Expression 객체 생성
        result_expr = Expression(
            left=left_expr,
            operator=operator,
            right=right_expr,
            context='EqualityOpContext'
        )

        return result_expr

    # Visit a parse tree produced by SolidityParser#AndOperation.
    def visitAndOperation(self, ctx:SolidityParser.AndOperationContext):
        # 좌측 표현식 방문
        left_expr = self.visitExpression(ctx.expression(0))

        # 우측 표현식 방문
        right_expr = self.visitExpression(ctx.expression(1))

        # 연산자 설정 ('&&')
        operator = '&&'

        # Expression 객체 생성
        result_expr = Expression(
            left=left_expr,
            operator=operator,
            right=right_expr,
            context='AndOperationOpContext'
        )

        return result_expr

    # Visit a parse tree produced by SolidityParser#RelationalOp.
    def visitRelationalOp(self, ctx:SolidityParser.RelationalOpContext):
        # 좌측 표현식 방문
        left_expr = self.visitExpression(ctx.expression(0))

        # 우측 표현식 방문
        right_expr = self.visitExpression(ctx.expression(1))

        # 연산자 추출 ('<', '>', '<=', '>=')
        operator = ctx.getChild(1).getText()

        # Expression 객체 생성
        result_expr = Expression(
            left=left_expr,
            operator=operator,
            right=right_expr,
            context='RelationalOpContext'
        )

        return result_expr

    # Visit a parse tree produced by SolidityParser#OrOperation.
    def visitOrOperation(self, ctx:SolidityParser.OrOperationContext):
        # 좌측 표현식 방문
        left_expr = self.visitExpression(ctx.expression(0))

        # 우측 표현식 방문
        right_expr = self.visitExpression(ctx.expression(1))

        # 연산자 설정 ('||')
        operator = '||'

        # Expression 객체 생성
        result_expr = Expression(
            left=left_expr,
            operator=operator,
            right=right_expr,
            context='OrOperationContext'
        )

        return result_expr

    # Visit a parse tree produced by SolidityParser#ShiftOp.
    def visitShiftOp(self, ctx:SolidityParser.ShiftOpContext):
        # 좌측 표현식 방문
        left_expr = self.visitExpression(ctx.expression(0))

        # 우측 표현식 방문
        right_expr = self.visitExpression(ctx.expression(1))

        # 연산자 추출 ('<<', '>>', '>>>')
        operator = ctx.getChild(1).getText()

        # Expression 객체 생성
        result_expr = Expression(
            left=left_expr,
            operator=operator,
            right=right_expr,
            context='ShiftOpContext'
        )

        return result_expr

    def visitLiteralWithSubDenomination(self, ctx: SolidityParser.LiteralWithSubDenominationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#TypeNameExp.
    def visitTypeNameExp(self, ctx:SolidityParser.TypeNameExpContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#InlineArrayExp.
    def visitInlineArrayExp(self, ctx:SolidityParser.InlineArrayExpContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#literal.
    def visitLiteral(self, ctx:SolidityParser.LiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#literalWithSubDenomination.
    def visitLiteralWithSubDenomination(self, ctx:SolidityParser.LiteralWithSubDenominationContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#numberLiteral.
    def visitNumberLiteral(self, ctx:SolidityParser.NumberLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#identifier.
    def visitIdentifier(self, ctx:SolidityParser.IdentifierContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#userDefinedValueTypeDefinition.
    def visitUserDefinedValueTypeDefinition(self, ctx:SolidityParser.UserDefinedValueTypeDefinitionContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#booleanLiteral.
    def visitBooleanLiteral(self, ctx:SolidityParser.BooleanLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#hexStringLiteral.
    def visitHexStringLiteral(self, ctx:SolidityParser.HexStringLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#unicodeStringLiteral.
    def visitUnicodeStringLiteral(self, ctx:SolidityParser.UnicodeStringLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#stringLiteral.
    def visitStringLiteral(self, ctx:SolidityParser.StringLiteralContext):
        return self.visitChildren(ctx)

    # Visit a parse tree produced by SolidityParser#overrideSpecifier.
    def visitOverrideSpecifier(self, ctx:SolidityParser.OverrideSpecifierContext):
        return self.visitChildren(ctx)

    def evaluate_literal_expression(self, expr):
        """
        literal 표현식 (숫자, 문자열, boolean 등)을 처리하는 함수.
        LiteralExpContext에서 리터럴 값을 분석하여 처리합니다.
        """
        literal_text = expr.getText()  # 리터럴 텍스트 가져오기

        # 숫자 리터럴인지 확인
        if literal_text.isdigit():
            return self.evaluate_number_literal(literal_text)

        # 불리언 리터럴인지 확인
        elif literal_text == 'true' or literal_text == 'false':
            return self.evaluate_boolean_literal(literal_text)

        # 기타 리터럴 타입 (16진수 문자열, 유니코드 등)
        elif literal_text.startswith("0x"):
            return self.evaluate_hex_string_literal(literal_text)

        elif literal_text.startswith('"') and literal_text.endswith('"'):
            return self.evaluate_string_literal(literal_text)

        else:
            raise ValueError(f"Unsupported literal type: {literal_text}")

    def evaluate_number_literal(self, literal_text):
        """
        숫자 리터럴 처리
        """
        return int(literal_text)

    def evaluate_boolean_literal(self, literal_text):
        """
        boolean 리터럴 처리
        """
        if literal_text == 'true':
            return True
        elif literal_text == 'false':
            return False

    def evaluate_hex_string_literal(self, literal_text):
        """
        16진수 리터럴 처리
        """
        return int(literal_text, 16)

    def evaluate_string_literal(self, literal_text):
        """
        문자열 리터럴 처리
        """
        return literal_text.strip('"')  # 따옴표 제거 후 반환


