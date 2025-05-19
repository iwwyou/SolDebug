# Generated from Solidity.g4 by ANTLR 4.13.2
from antlr4 import *
if "." in __name__:
    from .SolidityParser import SolidityParser
else:
    from SolidityParser import SolidityParser

# This class defines a complete listener for a parse tree produced by SolidityParser.
class SolidityListener(ParseTreeListener):

    # Enter a parse tree produced by SolidityParser#sourceUnit.
    def enterSourceUnit(self, ctx:SolidityParser.SourceUnitContext):
        pass

    # Exit a parse tree produced by SolidityParser#sourceUnit.
    def exitSourceUnit(self, ctx:SolidityParser.SourceUnitContext):
        pass


    # Enter a parse tree produced by SolidityParser#pragmaDirective.
    def enterPragmaDirective(self, ctx:SolidityParser.PragmaDirectiveContext):
        pass

    # Exit a parse tree produced by SolidityParser#pragmaDirective.
    def exitPragmaDirective(self, ctx:SolidityParser.PragmaDirectiveContext):
        pass


    # Enter a parse tree produced by SolidityParser#pragmaName.
    def enterPragmaName(self, ctx:SolidityParser.PragmaNameContext):
        pass

    # Exit a parse tree produced by SolidityParser#pragmaName.
    def exitPragmaName(self, ctx:SolidityParser.PragmaNameContext):
        pass


    # Enter a parse tree produced by SolidityParser#pragmaValue.
    def enterPragmaValue(self, ctx:SolidityParser.PragmaValueContext):
        pass

    # Exit a parse tree produced by SolidityParser#pragmaValue.
    def exitPragmaValue(self, ctx:SolidityParser.PragmaValueContext):
        pass


    # Enter a parse tree produced by SolidityParser#version.
    def enterVersion(self, ctx:SolidityParser.VersionContext):
        pass

    # Exit a parse tree produced by SolidityParser#version.
    def exitVersion(self, ctx:SolidityParser.VersionContext):
        pass


    # Enter a parse tree produced by SolidityParser#versionOperator.
    def enterVersionOperator(self, ctx:SolidityParser.VersionOperatorContext):
        pass

    # Exit a parse tree produced by SolidityParser#versionOperator.
    def exitVersionOperator(self, ctx:SolidityParser.VersionOperatorContext):
        pass


    # Enter a parse tree produced by SolidityParser#versionConstraint.
    def enterVersionConstraint(self, ctx:SolidityParser.VersionConstraintContext):
        pass

    # Exit a parse tree produced by SolidityParser#versionConstraint.
    def exitVersionConstraint(self, ctx:SolidityParser.VersionConstraintContext):
        pass


    # Enter a parse tree produced by SolidityParser#importDeclaration.
    def enterImportDeclaration(self, ctx:SolidityParser.ImportDeclarationContext):
        pass

    # Exit a parse tree produced by SolidityParser#importDeclaration.
    def exitImportDeclaration(self, ctx:SolidityParser.ImportDeclarationContext):
        pass


    # Enter a parse tree produced by SolidityParser#importDirective.
    def enterImportDirective(self, ctx:SolidityParser.ImportDirectiveContext):
        pass

    # Exit a parse tree produced by SolidityParser#importDirective.
    def exitImportDirective(self, ctx:SolidityParser.ImportDirectiveContext):
        pass


    # Enter a parse tree produced by SolidityParser#importPath.
    def enterImportPath(self, ctx:SolidityParser.ImportPathContext):
        pass

    # Exit a parse tree produced by SolidityParser#importPath.
    def exitImportPath(self, ctx:SolidityParser.ImportPathContext):
        pass


    # Enter a parse tree produced by SolidityParser#symbolAliases.
    def enterSymbolAliases(self, ctx:SolidityParser.SymbolAliasesContext):
        pass

    # Exit a parse tree produced by SolidityParser#symbolAliases.
    def exitSymbolAliases(self, ctx:SolidityParser.SymbolAliasesContext):
        pass


    # Enter a parse tree produced by SolidityParser#contractDefinition.
    def enterContractDefinition(self, ctx:SolidityParser.ContractDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#contractDefinition.
    def exitContractDefinition(self, ctx:SolidityParser.ContractDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#interfaceDefinition.
    def enterInterfaceDefinition(self, ctx:SolidityParser.InterfaceDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#interfaceDefinition.
    def exitInterfaceDefinition(self, ctx:SolidityParser.InterfaceDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#libraryDefinition.
    def enterLibraryDefinition(self, ctx:SolidityParser.LibraryDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#libraryDefinition.
    def exitLibraryDefinition(self, ctx:SolidityParser.LibraryDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#inheritanceSpecifier.
    def enterInheritanceSpecifier(self, ctx:SolidityParser.InheritanceSpecifierContext):
        pass

    # Exit a parse tree produced by SolidityParser#inheritanceSpecifier.
    def exitInheritanceSpecifier(self, ctx:SolidityParser.InheritanceSpecifierContext):
        pass


    # Enter a parse tree produced by SolidityParser#callArgumentList.
    def enterCallArgumentList(self, ctx:SolidityParser.CallArgumentListContext):
        pass

    # Exit a parse tree produced by SolidityParser#callArgumentList.
    def exitCallArgumentList(self, ctx:SolidityParser.CallArgumentListContext):
        pass


    # Enter a parse tree produced by SolidityParser#identifierPath.
    def enterIdentifierPath(self, ctx:SolidityParser.IdentifierPathContext):
        pass

    # Exit a parse tree produced by SolidityParser#identifierPath.
    def exitIdentifierPath(self, ctx:SolidityParser.IdentifierPathContext):
        pass


    # Enter a parse tree produced by SolidityParser#constantVariableDeclaration.
    def enterConstantVariableDeclaration(self, ctx:SolidityParser.ConstantVariableDeclarationContext):
        pass

    # Exit a parse tree produced by SolidityParser#constantVariableDeclaration.
    def exitConstantVariableDeclaration(self, ctx:SolidityParser.ConstantVariableDeclarationContext):
        pass


    # Enter a parse tree produced by SolidityParser#contractBodyElement.
    def enterContractBodyElement(self, ctx:SolidityParser.ContractBodyElementContext):
        pass

    # Exit a parse tree produced by SolidityParser#contractBodyElement.
    def exitContractBodyElement(self, ctx:SolidityParser.ContractBodyElementContext):
        pass


    # Enter a parse tree produced by SolidityParser#constructorDefinition.
    def enterConstructorDefinition(self, ctx:SolidityParser.ConstructorDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#constructorDefinition.
    def exitConstructorDefinition(self, ctx:SolidityParser.ConstructorDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#fallbackFunctionDefinition.
    def enterFallbackFunctionDefinition(self, ctx:SolidityParser.FallbackFunctionDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#fallbackFunctionDefinition.
    def exitFallbackFunctionDefinition(self, ctx:SolidityParser.FallbackFunctionDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#receiveFunctionDefinition.
    def enterReceiveFunctionDefinition(self, ctx:SolidityParser.ReceiveFunctionDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#receiveFunctionDefinition.
    def exitReceiveFunctionDefinition(self, ctx:SolidityParser.ReceiveFunctionDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#stateVariableDeclaration.
    def enterStateVariableDeclaration(self, ctx:SolidityParser.StateVariableDeclarationContext):
        pass

    # Exit a parse tree produced by SolidityParser#stateVariableDeclaration.
    def exitStateVariableDeclaration(self, ctx:SolidityParser.StateVariableDeclarationContext):
        pass


    # Enter a parse tree produced by SolidityParser#errorDefinition.
    def enterErrorDefinition(self, ctx:SolidityParser.ErrorDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#errorDefinition.
    def exitErrorDefinition(self, ctx:SolidityParser.ErrorDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#errorParameter.
    def enterErrorParameter(self, ctx:SolidityParser.ErrorParameterContext):
        pass

    # Exit a parse tree produced by SolidityParser#errorParameter.
    def exitErrorParameter(self, ctx:SolidityParser.ErrorParameterContext):
        pass


    # Enter a parse tree produced by SolidityParser#usingDirective.
    def enterUsingDirective(self, ctx:SolidityParser.UsingDirectiveContext):
        pass

    # Exit a parse tree produced by SolidityParser#usingDirective.
    def exitUsingDirective(self, ctx:SolidityParser.UsingDirectiveContext):
        pass


    # Enter a parse tree produced by SolidityParser#userDefinableOperators.
    def enterUserDefinableOperators(self, ctx:SolidityParser.UserDefinableOperatorsContext):
        pass

    # Exit a parse tree produced by SolidityParser#userDefinableOperators.
    def exitUserDefinableOperators(self, ctx:SolidityParser.UserDefinableOperatorsContext):
        pass


    # Enter a parse tree produced by SolidityParser#structDefinition.
    def enterStructDefinition(self, ctx:SolidityParser.StructDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#structDefinition.
    def exitStructDefinition(self, ctx:SolidityParser.StructDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#structMember.
    def enterStructMember(self, ctx:SolidityParser.StructMemberContext):
        pass

    # Exit a parse tree produced by SolidityParser#structMember.
    def exitStructMember(self, ctx:SolidityParser.StructMemberContext):
        pass


    # Enter a parse tree produced by SolidityParser#modifierDefinition.
    def enterModifierDefinition(self, ctx:SolidityParser.ModifierDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#modifierDefinition.
    def exitModifierDefinition(self, ctx:SolidityParser.ModifierDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#visibility.
    def enterVisibility(self, ctx:SolidityParser.VisibilityContext):
        pass

    # Exit a parse tree produced by SolidityParser#visibility.
    def exitVisibility(self, ctx:SolidityParser.VisibilityContext):
        pass


    # Enter a parse tree produced by SolidityParser#modifierInvocation.
    def enterModifierInvocation(self, ctx:SolidityParser.ModifierInvocationContext):
        pass

    # Exit a parse tree produced by SolidityParser#modifierInvocation.
    def exitModifierInvocation(self, ctx:SolidityParser.ModifierInvocationContext):
        pass


    # Enter a parse tree produced by SolidityParser#functionDefinition.
    def enterFunctionDefinition(self, ctx:SolidityParser.FunctionDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#functionDefinition.
    def exitFunctionDefinition(self, ctx:SolidityParser.FunctionDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#eventDefinition.
    def enterEventDefinition(self, ctx:SolidityParser.EventDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#eventDefinition.
    def exitEventDefinition(self, ctx:SolidityParser.EventDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#enumDefinition.
    def enterEnumDefinition(self, ctx:SolidityParser.EnumDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#enumDefinition.
    def exitEnumDefinition(self, ctx:SolidityParser.EnumDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#parameterList.
    def enterParameterList(self, ctx:SolidityParser.ParameterListContext):
        pass

    # Exit a parse tree produced by SolidityParser#parameterList.
    def exitParameterList(self, ctx:SolidityParser.ParameterListContext):
        pass


    # Enter a parse tree produced by SolidityParser#eventParameter.
    def enterEventParameter(self, ctx:SolidityParser.EventParameterContext):
        pass

    # Exit a parse tree produced by SolidityParser#eventParameter.
    def exitEventParameter(self, ctx:SolidityParser.EventParameterContext):
        pass


    # Enter a parse tree produced by SolidityParser#variableDeclaration.
    def enterVariableDeclaration(self, ctx:SolidityParser.VariableDeclarationContext):
        pass

    # Exit a parse tree produced by SolidityParser#variableDeclaration.
    def exitVariableDeclaration(self, ctx:SolidityParser.VariableDeclarationContext):
        pass


    # Enter a parse tree produced by SolidityParser#variableDeclarationTuple.
    def enterVariableDeclarationTuple(self, ctx:SolidityParser.VariableDeclarationTupleContext):
        pass

    # Exit a parse tree produced by SolidityParser#variableDeclarationTuple.
    def exitVariableDeclarationTuple(self, ctx:SolidityParser.VariableDeclarationTupleContext):
        pass


    # Enter a parse tree produced by SolidityParser#ArrayType.
    def enterArrayType(self, ctx:SolidityParser.ArrayTypeContext):
        pass

    # Exit a parse tree produced by SolidityParser#ArrayType.
    def exitArrayType(self, ctx:SolidityParser.ArrayTypeContext):
        pass


    # Enter a parse tree produced by SolidityParser#BasicType.
    def enterBasicType(self, ctx:SolidityParser.BasicTypeContext):
        pass

    # Exit a parse tree produced by SolidityParser#BasicType.
    def exitBasicType(self, ctx:SolidityParser.BasicTypeContext):
        pass


    # Enter a parse tree produced by SolidityParser#FunctionType.
    def enterFunctionType(self, ctx:SolidityParser.FunctionTypeContext):
        pass

    # Exit a parse tree produced by SolidityParser#FunctionType.
    def exitFunctionType(self, ctx:SolidityParser.FunctionTypeContext):
        pass


    # Enter a parse tree produced by SolidityParser#UserDefinedType.
    def enterUserDefinedType(self, ctx:SolidityParser.UserDefinedTypeContext):
        pass

    # Exit a parse tree produced by SolidityParser#UserDefinedType.
    def exitUserDefinedType(self, ctx:SolidityParser.UserDefinedTypeContext):
        pass


    # Enter a parse tree produced by SolidityParser#MapType.
    def enterMapType(self, ctx:SolidityParser.MapTypeContext):
        pass

    # Exit a parse tree produced by SolidityParser#MapType.
    def exitMapType(self, ctx:SolidityParser.MapTypeContext):
        pass


    # Enter a parse tree produced by SolidityParser#mapping.
    def enterMapping(self, ctx:SolidityParser.MappingContext):
        pass

    # Exit a parse tree produced by SolidityParser#mapping.
    def exitMapping(self, ctx:SolidityParser.MappingContext):
        pass


    # Enter a parse tree produced by SolidityParser#mappingKeyType.
    def enterMappingKeyType(self, ctx:SolidityParser.MappingKeyTypeContext):
        pass

    # Exit a parse tree produced by SolidityParser#mappingKeyType.
    def exitMappingKeyType(self, ctx:SolidityParser.MappingKeyTypeContext):
        pass


    # Enter a parse tree produced by SolidityParser#functionTypeName.
    def enterFunctionTypeName(self, ctx:SolidityParser.FunctionTypeNameContext):
        pass

    # Exit a parse tree produced by SolidityParser#functionTypeName.
    def exitFunctionTypeName(self, ctx:SolidityParser.FunctionTypeNameContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveSourceUnit.
    def enterInteractiveSourceUnit(self, ctx:SolidityParser.InteractiveSourceUnitContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveSourceUnit.
    def exitInteractiveSourceUnit(self, ctx:SolidityParser.InteractiveSourceUnitContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveEnumUnit.
    def enterInteractiveEnumUnit(self, ctx:SolidityParser.InteractiveEnumUnitContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveEnumUnit.
    def exitInteractiveEnumUnit(self, ctx:SolidityParser.InteractiveEnumUnitContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveStructUnit.
    def enterInteractiveStructUnit(self, ctx:SolidityParser.InteractiveStructUnitContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveStructUnit.
    def exitInteractiveStructUnit(self, ctx:SolidityParser.InteractiveStructUnitContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveBlockUnit.
    def enterInteractiveBlockUnit(self, ctx:SolidityParser.InteractiveBlockUnitContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveBlockUnit.
    def exitInteractiveBlockUnit(self, ctx:SolidityParser.InteractiveBlockUnitContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveDoWhileUnit.
    def enterInteractiveDoWhileUnit(self, ctx:SolidityParser.InteractiveDoWhileUnitContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveDoWhileUnit.
    def exitInteractiveDoWhileUnit(self, ctx:SolidityParser.InteractiveDoWhileUnitContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveIfElseUnit.
    def enterInteractiveIfElseUnit(self, ctx:SolidityParser.InteractiveIfElseUnitContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveIfElseUnit.
    def exitInteractiveIfElseUnit(self, ctx:SolidityParser.InteractiveIfElseUnitContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveCatchClauseUnit.
    def enterInteractiveCatchClauseUnit(self, ctx:SolidityParser.InteractiveCatchClauseUnitContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveCatchClauseUnit.
    def exitInteractiveCatchClauseUnit(self, ctx:SolidityParser.InteractiveCatchClauseUnitContext):
        pass


    # Enter a parse tree produced by SolidityParser#debugUnit.
    def enterDebugUnit(self, ctx:SolidityParser.DebugUnitContext):
        pass

    # Exit a parse tree produced by SolidityParser#debugUnit.
    def exitDebugUnit(self, ctx:SolidityParser.DebugUnitContext):
        pass


    # Enter a parse tree produced by SolidityParser#debugGlobalVar.
    def enterDebugGlobalVar(self, ctx:SolidityParser.DebugGlobalVarContext):
        pass

    # Exit a parse tree produced by SolidityParser#debugGlobalVar.
    def exitDebugGlobalVar(self, ctx:SolidityParser.DebugGlobalVarContext):
        pass


    # Enter a parse tree produced by SolidityParser#GlobalIntValue.
    def enterGlobalIntValue(self, ctx:SolidityParser.GlobalIntValueContext):
        pass

    # Exit a parse tree produced by SolidityParser#GlobalIntValue.
    def exitGlobalIntValue(self, ctx:SolidityParser.GlobalIntValueContext):
        pass


    # Enter a parse tree produced by SolidityParser#GlobalAddressValue.
    def enterGlobalAddressValue(self, ctx:SolidityParser.GlobalAddressValueContext):
        pass

    # Exit a parse tree produced by SolidityParser#GlobalAddressValue.
    def exitGlobalAddressValue(self, ctx:SolidityParser.GlobalAddressValueContext):
        pass


    # Enter a parse tree produced by SolidityParser#debugStateVar.
    def enterDebugStateVar(self, ctx:SolidityParser.DebugStateVarContext):
        pass

    # Exit a parse tree produced by SolidityParser#debugStateVar.
    def exitDebugStateVar(self, ctx:SolidityParser.DebugStateVarContext):
        pass


    # Enter a parse tree produced by SolidityParser#debugLocalVar.
    def enterDebugLocalVar(self, ctx:SolidityParser.DebugLocalVarContext):
        pass

    # Exit a parse tree produced by SolidityParser#debugLocalVar.
    def exitDebugLocalVar(self, ctx:SolidityParser.DebugLocalVarContext):
        pass


    # Enter a parse tree produced by SolidityParser#testingExpression.
    def enterTestingExpression(self, ctx:SolidityParser.TestingExpressionContext):
        pass

    # Exit a parse tree produced by SolidityParser#testingExpression.
    def exitTestingExpression(self, ctx:SolidityParser.TestingExpressionContext):
        pass


    # Enter a parse tree produced by SolidityParser#TestingMemberAccess.
    def enterTestingMemberAccess(self, ctx:SolidityParser.TestingMemberAccessContext):
        pass

    # Exit a parse tree produced by SolidityParser#TestingMemberAccess.
    def exitTestingMemberAccess(self, ctx:SolidityParser.TestingMemberAccessContext):
        pass


    # Enter a parse tree produced by SolidityParser#TestingIndexAccess.
    def enterTestingIndexAccess(self, ctx:SolidityParser.TestingIndexAccessContext):
        pass

    # Exit a parse tree produced by SolidityParser#TestingIndexAccess.
    def exitTestingIndexAccess(self, ctx:SolidityParser.TestingIndexAccessContext):
        pass


    # Enter a parse tree produced by SolidityParser#StateLocalIntValue.
    def enterStateLocalIntValue(self, ctx:SolidityParser.StateLocalIntValueContext):
        pass

    # Exit a parse tree produced by SolidityParser#StateLocalIntValue.
    def exitStateLocalIntValue(self, ctx:SolidityParser.StateLocalIntValueContext):
        pass


    # Enter a parse tree produced by SolidityParser#StateLocalAddressValue.
    def enterStateLocalAddressValue(self, ctx:SolidityParser.StateLocalAddressValueContext):
        pass

    # Exit a parse tree produced by SolidityParser#StateLocalAddressValue.
    def exitStateLocalAddressValue(self, ctx:SolidityParser.StateLocalAddressValueContext):
        pass


    # Enter a parse tree produced by SolidityParser#StateLocalByteValue.
    def enterStateLocalByteValue(self, ctx:SolidityParser.StateLocalByteValueContext):
        pass

    # Exit a parse tree produced by SolidityParser#StateLocalByteValue.
    def exitStateLocalByteValue(self, ctx:SolidityParser.StateLocalByteValueContext):
        pass


    # Enter a parse tree produced by SolidityParser#StateLocalStringValue.
    def enterStateLocalStringValue(self, ctx:SolidityParser.StateLocalStringValueContext):
        pass

    # Exit a parse tree produced by SolidityParser#StateLocalStringValue.
    def exitStateLocalStringValue(self, ctx:SolidityParser.StateLocalStringValueContext):
        pass


    # Enter a parse tree produced by SolidityParser#StateLocalBoolValue.
    def enterStateLocalBoolValue(self, ctx:SolidityParser.StateLocalBoolValueContext):
        pass

    # Exit a parse tree produced by SolidityParser#StateLocalBoolValue.
    def exitStateLocalBoolValue(self, ctx:SolidityParser.StateLocalBoolValueContext):
        pass


    # Enter a parse tree produced by SolidityParser#StateLocalEnumValue.
    def enterStateLocalEnumValue(self, ctx:SolidityParser.StateLocalEnumValueContext):
        pass

    # Exit a parse tree produced by SolidityParser#StateLocalEnumValue.
    def exitStateLocalEnumValue(self, ctx:SolidityParser.StateLocalEnumValueContext):
        pass


    # Enter a parse tree produced by SolidityParser#StateLocalInlineValue.
    def enterStateLocalInlineValue(self, ctx:SolidityParser.StateLocalInlineValueContext):
        pass

    # Exit a parse tree produced by SolidityParser#StateLocalInlineValue.
    def exitStateLocalInlineValue(self, ctx:SolidityParser.StateLocalInlineValueContext):
        pass


    # Enter a parse tree produced by SolidityParser#inlineArrayAnnotation.
    def enterInlineArrayAnnotation(self, ctx:SolidityParser.InlineArrayAnnotationContext):
        pass

    # Exit a parse tree produced by SolidityParser#inlineArrayAnnotation.
    def exitInlineArrayAnnotation(self, ctx:SolidityParser.InlineArrayAnnotationContext):
        pass


    # Enter a parse tree produced by SolidityParser#InlineIntElement.
    def enterInlineIntElement(self, ctx:SolidityParser.InlineIntElementContext):
        pass

    # Exit a parse tree produced by SolidityParser#InlineIntElement.
    def exitInlineIntElement(self, ctx:SolidityParser.InlineIntElementContext):
        pass


    # Enter a parse tree produced by SolidityParser#NestedArrayElement.
    def enterNestedArrayElement(self, ctx:SolidityParser.NestedArrayElementContext):
        pass

    # Exit a parse tree produced by SolidityParser#NestedArrayElement.
    def exitNestedArrayElement(self, ctx:SolidityParser.NestedArrayElementContext):
        pass


    # Enter a parse tree produced by SolidityParser#AddrArrayElement.
    def enterAddrArrayElement(self, ctx:SolidityParser.AddrArrayElementContext):
        pass

    # Exit a parse tree produced by SolidityParser#AddrArrayElement.
    def exitAddrArrayElement(self, ctx:SolidityParser.AddrArrayElementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveSimpleStatement.
    def enterInteractiveSimpleStatement(self, ctx:SolidityParser.InteractiveSimpleStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveSimpleStatement.
    def exitInteractiveSimpleStatement(self, ctx:SolidityParser.InteractiveSimpleStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveVariableDeclarationStatement.
    def enterInteractiveVariableDeclarationStatement(self, ctx:SolidityParser.InteractiveVariableDeclarationStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveVariableDeclarationStatement.
    def exitInteractiveVariableDeclarationStatement(self, ctx:SolidityParser.InteractiveVariableDeclarationStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveExpressionStatement.
    def enterInteractiveExpressionStatement(self, ctx:SolidityParser.InteractiveExpressionStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveExpressionStatement.
    def exitInteractiveExpressionStatement(self, ctx:SolidityParser.InteractiveExpressionStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveStateVariableElement.
    def enterInteractiveStateVariableElement(self, ctx:SolidityParser.InteractiveStateVariableElementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveStateVariableElement.
    def exitInteractiveStateVariableElement(self, ctx:SolidityParser.InteractiveStateVariableElementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveEnumDefinition.
    def enterInteractiveEnumDefinition(self, ctx:SolidityParser.InteractiveEnumDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveEnumDefinition.
    def exitInteractiveEnumDefinition(self, ctx:SolidityParser.InteractiveEnumDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveStructDefinition.
    def enterInteractiveStructDefinition(self, ctx:SolidityParser.InteractiveStructDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveStructDefinition.
    def exitInteractiveStructDefinition(self, ctx:SolidityParser.InteractiveStructDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveEnumItems.
    def enterInteractiveEnumItems(self, ctx:SolidityParser.InteractiveEnumItemsContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveEnumItems.
    def exitInteractiveEnumItems(self, ctx:SolidityParser.InteractiveEnumItemsContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveFunctionElement.
    def enterInteractiveFunctionElement(self, ctx:SolidityParser.InteractiveFunctionElementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveFunctionElement.
    def exitInteractiveFunctionElement(self, ctx:SolidityParser.InteractiveFunctionElementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveBlockItem.
    def enterInteractiveBlockItem(self, ctx:SolidityParser.InteractiveBlockItemContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveBlockItem.
    def exitInteractiveBlockItem(self, ctx:SolidityParser.InteractiveBlockItemContext):
        pass


    # Enter a parse tree produced by SolidityParser#dataLocation.
    def enterDataLocation(self, ctx:SolidityParser.DataLocationContext):
        pass

    # Exit a parse tree produced by SolidityParser#dataLocation.
    def exitDataLocation(self, ctx:SolidityParser.DataLocationContext):
        pass


    # Enter a parse tree produced by SolidityParser#stateMutability.
    def enterStateMutability(self, ctx:SolidityParser.StateMutabilityContext):
        pass

    # Exit a parse tree produced by SolidityParser#stateMutability.
    def exitStateMutability(self, ctx:SolidityParser.StateMutabilityContext):
        pass


    # Enter a parse tree produced by SolidityParser#block.
    def enterBlock(self, ctx:SolidityParser.BlockContext):
        pass

    # Exit a parse tree produced by SolidityParser#block.
    def exitBlock(self, ctx:SolidityParser.BlockContext):
        pass


    # Enter a parse tree produced by SolidityParser#uncheckedBlock.
    def enterUncheckedBlock(self, ctx:SolidityParser.UncheckedBlockContext):
        pass

    # Exit a parse tree produced by SolidityParser#uncheckedBlock.
    def exitUncheckedBlock(self, ctx:SolidityParser.UncheckedBlockContext):
        pass


    # Enter a parse tree produced by SolidityParser#statement.
    def enterStatement(self, ctx:SolidityParser.StatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#statement.
    def exitStatement(self, ctx:SolidityParser.StatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#expressionStatement.
    def enterExpressionStatement(self, ctx:SolidityParser.ExpressionStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#expressionStatement.
    def exitExpressionStatement(self, ctx:SolidityParser.ExpressionStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#ifStatement.
    def enterIfStatement(self, ctx:SolidityParser.IfStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#ifStatement.
    def exitIfStatement(self, ctx:SolidityParser.IfStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#tryStatement.
    def enterTryStatement(self, ctx:SolidityParser.TryStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#tryStatement.
    def exitTryStatement(self, ctx:SolidityParser.TryStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#catchClause.
    def enterCatchClause(self, ctx:SolidityParser.CatchClauseContext):
        pass

    # Exit a parse tree produced by SolidityParser#catchClause.
    def exitCatchClause(self, ctx:SolidityParser.CatchClauseContext):
        pass


    # Enter a parse tree produced by SolidityParser#whileStatement.
    def enterWhileStatement(self, ctx:SolidityParser.WhileStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#whileStatement.
    def exitWhileStatement(self, ctx:SolidityParser.WhileStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#VDContext.
    def enterVDContext(self, ctx:SolidityParser.VDContextContext):
        pass

    # Exit a parse tree produced by SolidityParser#VDContext.
    def exitVDContext(self, ctx:SolidityParser.VDContextContext):
        pass


    # Enter a parse tree produced by SolidityParser#EContext.
    def enterEContext(self, ctx:SolidityParser.EContextContext):
        pass

    # Exit a parse tree produced by SolidityParser#EContext.
    def exitEContext(self, ctx:SolidityParser.EContextContext):
        pass


    # Enter a parse tree produced by SolidityParser#forStatement.
    def enterForStatement(self, ctx:SolidityParser.ForStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#forStatement.
    def exitForStatement(self, ctx:SolidityParser.ForStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#inlineArrayExpression.
    def enterInlineArrayExpression(self, ctx:SolidityParser.InlineArrayExpressionContext):
        pass

    # Exit a parse tree produced by SolidityParser#inlineArrayExpression.
    def exitInlineArrayExpression(self, ctx:SolidityParser.InlineArrayExpressionContext):
        pass


    # Enter a parse tree produced by SolidityParser#assemblyStatement.
    def enterAssemblyStatement(self, ctx:SolidityParser.AssemblyStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#assemblyStatement.
    def exitAssemblyStatement(self, ctx:SolidityParser.AssemblyStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#assemblyFlags.
    def enterAssemblyFlags(self, ctx:SolidityParser.AssemblyFlagsContext):
        pass

    # Exit a parse tree produced by SolidityParser#assemblyFlags.
    def exitAssemblyFlags(self, ctx:SolidityParser.AssemblyFlagsContext):
        pass


    # Enter a parse tree produced by SolidityParser#assemblyFlagString.
    def enterAssemblyFlagString(self, ctx:SolidityParser.AssemblyFlagStringContext):
        pass

    # Exit a parse tree produced by SolidityParser#assemblyFlagString.
    def exitAssemblyFlagString(self, ctx:SolidityParser.AssemblyFlagStringContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulStatement.
    def enterYulStatement(self, ctx:SolidityParser.YulStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulStatement.
    def exitYulStatement(self, ctx:SolidityParser.YulStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulBlock.
    def enterYulBlock(self, ctx:SolidityParser.YulBlockContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulBlock.
    def exitYulBlock(self, ctx:SolidityParser.YulBlockContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulVariableDeclaration.
    def enterYulVariableDeclaration(self, ctx:SolidityParser.YulVariableDeclarationContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulVariableDeclaration.
    def exitYulVariableDeclaration(self, ctx:SolidityParser.YulVariableDeclarationContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulAssignment.
    def enterYulAssignment(self, ctx:SolidityParser.YulAssignmentContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulAssignment.
    def exitYulAssignment(self, ctx:SolidityParser.YulAssignmentContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulIfStatement.
    def enterYulIfStatement(self, ctx:SolidityParser.YulIfStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulIfStatement.
    def exitYulIfStatement(self, ctx:SolidityParser.YulIfStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulForStatement.
    def enterYulForStatement(self, ctx:SolidityParser.YulForStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulForStatement.
    def exitYulForStatement(self, ctx:SolidityParser.YulForStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulSwitchStatement.
    def enterYulSwitchStatement(self, ctx:SolidityParser.YulSwitchStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulSwitchStatement.
    def exitYulSwitchStatement(self, ctx:SolidityParser.YulSwitchStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulFunctionDefinition.
    def enterYulFunctionDefinition(self, ctx:SolidityParser.YulFunctionDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulFunctionDefinition.
    def exitYulFunctionDefinition(self, ctx:SolidityParser.YulFunctionDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulPath.
    def enterYulPath(self, ctx:SolidityParser.YulPathContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulPath.
    def exitYulPath(self, ctx:SolidityParser.YulPathContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulFunctionCall.
    def enterYulFunctionCall(self, ctx:SolidityParser.YulFunctionCallContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulFunctionCall.
    def exitYulFunctionCall(self, ctx:SolidityParser.YulFunctionCallContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulBoolean.
    def enterYulBoolean(self, ctx:SolidityParser.YulBooleanContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulBoolean.
    def exitYulBoolean(self, ctx:SolidityParser.YulBooleanContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulLiteral.
    def enterYulLiteral(self, ctx:SolidityParser.YulLiteralContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulLiteral.
    def exitYulLiteral(self, ctx:SolidityParser.YulLiteralContext):
        pass


    # Enter a parse tree produced by SolidityParser#yulExpression.
    def enterYulExpression(self, ctx:SolidityParser.YulExpressionContext):
        pass

    # Exit a parse tree produced by SolidityParser#yulExpression.
    def exitYulExpression(self, ctx:SolidityParser.YulExpressionContext):
        pass


    # Enter a parse tree produced by SolidityParser#doWhileStatement.
    def enterDoWhileStatement(self, ctx:SolidityParser.DoWhileStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#doWhileStatement.
    def exitDoWhileStatement(self, ctx:SolidityParser.DoWhileStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#continueStatement.
    def enterContinueStatement(self, ctx:SolidityParser.ContinueStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#continueStatement.
    def exitContinueStatement(self, ctx:SolidityParser.ContinueStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#breakStatement.
    def enterBreakStatement(self, ctx:SolidityParser.BreakStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#breakStatement.
    def exitBreakStatement(self, ctx:SolidityParser.BreakStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#returnStatement.
    def enterReturnStatement(self, ctx:SolidityParser.ReturnStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#returnStatement.
    def exitReturnStatement(self, ctx:SolidityParser.ReturnStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#emitStatement.
    def enterEmitStatement(self, ctx:SolidityParser.EmitStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#emitStatement.
    def exitEmitStatement(self, ctx:SolidityParser.EmitStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#revertStatement.
    def enterRevertStatement(self, ctx:SolidityParser.RevertStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#revertStatement.
    def exitRevertStatement(self, ctx:SolidityParser.RevertStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#requireStatement.
    def enterRequireStatement(self, ctx:SolidityParser.RequireStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#requireStatement.
    def exitRequireStatement(self, ctx:SolidityParser.RequireStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#assertStatement.
    def enterAssertStatement(self, ctx:SolidityParser.AssertStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#assertStatement.
    def exitAssertStatement(self, ctx:SolidityParser.AssertStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#variableDeclarationStatement.
    def enterVariableDeclarationStatement(self, ctx:SolidityParser.VariableDeclarationStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#variableDeclarationStatement.
    def exitVariableDeclarationStatement(self, ctx:SolidityParser.VariableDeclarationStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveStatement.
    def enterInteractiveStatement(self, ctx:SolidityParser.InteractiveStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveStatement.
    def exitInteractiveStatement(self, ctx:SolidityParser.InteractiveStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveIfStatement.
    def enterInteractiveIfStatement(self, ctx:SolidityParser.InteractiveIfStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveIfStatement.
    def exitInteractiveIfStatement(self, ctx:SolidityParser.InteractiveIfStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveElseStatement.
    def enterInteractiveElseStatement(self, ctx:SolidityParser.InteractiveElseStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveElseStatement.
    def exitInteractiveElseStatement(self, ctx:SolidityParser.InteractiveElseStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveForStatement.
    def enterInteractiveForStatement(self, ctx:SolidityParser.InteractiveForStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveForStatement.
    def exitInteractiveForStatement(self, ctx:SolidityParser.InteractiveForStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveWhileStatement.
    def enterInteractiveWhileStatement(self, ctx:SolidityParser.InteractiveWhileStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveWhileStatement.
    def exitInteractiveWhileStatement(self, ctx:SolidityParser.InteractiveWhileStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveDoWhileDoStatement.
    def enterInteractiveDoWhileDoStatement(self, ctx:SolidityParser.InteractiveDoWhileDoStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveDoWhileDoStatement.
    def exitInteractiveDoWhileDoStatement(self, ctx:SolidityParser.InteractiveDoWhileDoStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveDoWhileWhileStatement.
    def enterInteractiveDoWhileWhileStatement(self, ctx:SolidityParser.InteractiveDoWhileWhileStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveDoWhileWhileStatement.
    def exitInteractiveDoWhileWhileStatement(self, ctx:SolidityParser.InteractiveDoWhileWhileStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveTryStatement.
    def enterInteractiveTryStatement(self, ctx:SolidityParser.InteractiveTryStatementContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveTryStatement.
    def exitInteractiveTryStatement(self, ctx:SolidityParser.InteractiveTryStatementContext):
        pass


    # Enter a parse tree produced by SolidityParser#interactiveCatchClause.
    def enterInteractiveCatchClause(self, ctx:SolidityParser.InteractiveCatchClauseContext):
        pass

    # Exit a parse tree produced by SolidityParser#interactiveCatchClause.
    def exitInteractiveCatchClause(self, ctx:SolidityParser.InteractiveCatchClauseContext):
        pass


    # Enter a parse tree produced by SolidityParser#elementaryTypeName.
    def enterElementaryTypeName(self, ctx:SolidityParser.ElementaryTypeNameContext):
        pass

    # Exit a parse tree produced by SolidityParser#elementaryTypeName.
    def exitElementaryTypeName(self, ctx:SolidityParser.ElementaryTypeNameContext):
        pass


    # Enter a parse tree produced by SolidityParser#IdentifierExp.
    def enterIdentifierExp(self, ctx:SolidityParser.IdentifierExpContext):
        pass

    # Exit a parse tree produced by SolidityParser#IdentifierExp.
    def exitIdentifierExp(self, ctx:SolidityParser.IdentifierExpContext):
        pass


    # Enter a parse tree produced by SolidityParser#LiteralExp.
    def enterLiteralExp(self, ctx:SolidityParser.LiteralExpContext):
        pass

    # Exit a parse tree produced by SolidityParser#LiteralExp.
    def exitLiteralExp(self, ctx:SolidityParser.LiteralExpContext):
        pass


    # Enter a parse tree produced by SolidityParser#ConditionalExp.
    def enterConditionalExp(self, ctx:SolidityParser.ConditionalExpContext):
        pass

    # Exit a parse tree produced by SolidityParser#ConditionalExp.
    def exitConditionalExp(self, ctx:SolidityParser.ConditionalExpContext):
        pass


    # Enter a parse tree produced by SolidityParser#Exponentiation.
    def enterExponentiation(self, ctx:SolidityParser.ExponentiationContext):
        pass

    # Exit a parse tree produced by SolidityParser#Exponentiation.
    def exitExponentiation(self, ctx:SolidityParser.ExponentiationContext):
        pass


    # Enter a parse tree produced by SolidityParser#LiteralSubDenomination.
    def enterLiteralSubDenomination(self, ctx:SolidityParser.LiteralSubDenominationContext):
        pass

    # Exit a parse tree produced by SolidityParser#LiteralSubDenomination.
    def exitLiteralSubDenomination(self, ctx:SolidityParser.LiteralSubDenominationContext):
        pass


    # Enter a parse tree produced by SolidityParser#TupleExp.
    def enterTupleExp(self, ctx:SolidityParser.TupleExpContext):
        pass

    # Exit a parse tree produced by SolidityParser#TupleExp.
    def exitTupleExp(self, ctx:SolidityParser.TupleExpContext):
        pass


    # Enter a parse tree produced by SolidityParser#Assignment.
    def enterAssignment(self, ctx:SolidityParser.AssignmentContext):
        pass

    # Exit a parse tree produced by SolidityParser#Assignment.
    def exitAssignment(self, ctx:SolidityParser.AssignmentContext):
        pass


    # Enter a parse tree produced by SolidityParser#TypeConversion.
    def enterTypeConversion(self, ctx:SolidityParser.TypeConversionContext):
        pass

    # Exit a parse tree produced by SolidityParser#TypeConversion.
    def exitTypeConversion(self, ctx:SolidityParser.TypeConversionContext):
        pass


    # Enter a parse tree produced by SolidityParser#UnaryPrefixOp.
    def enterUnaryPrefixOp(self, ctx:SolidityParser.UnaryPrefixOpContext):
        pass

    # Exit a parse tree produced by SolidityParser#UnaryPrefixOp.
    def exitUnaryPrefixOp(self, ctx:SolidityParser.UnaryPrefixOpContext):
        pass


    # Enter a parse tree produced by SolidityParser#BitXorOp.
    def enterBitXorOp(self, ctx:SolidityParser.BitXorOpContext):
        pass

    # Exit a parse tree produced by SolidityParser#BitXorOp.
    def exitBitXorOp(self, ctx:SolidityParser.BitXorOpContext):
        pass


    # Enter a parse tree produced by SolidityParser#AdditiveOp.
    def enterAdditiveOp(self, ctx:SolidityParser.AdditiveOpContext):
        pass

    # Exit a parse tree produced by SolidityParser#AdditiveOp.
    def exitAdditiveOp(self, ctx:SolidityParser.AdditiveOpContext):
        pass


    # Enter a parse tree produced by SolidityParser#PayableFunctionCall.
    def enterPayableFunctionCall(self, ctx:SolidityParser.PayableFunctionCallContext):
        pass

    # Exit a parse tree produced by SolidityParser#PayableFunctionCall.
    def exitPayableFunctionCall(self, ctx:SolidityParser.PayableFunctionCallContext):
        pass


    # Enter a parse tree produced by SolidityParser#FunctionCall.
    def enterFunctionCall(self, ctx:SolidityParser.FunctionCallContext):
        pass

    # Exit a parse tree produced by SolidityParser#FunctionCall.
    def exitFunctionCall(self, ctx:SolidityParser.FunctionCallContext):
        pass


    # Enter a parse tree produced by SolidityParser#NewExp.
    def enterNewExp(self, ctx:SolidityParser.NewExpContext):
        pass

    # Exit a parse tree produced by SolidityParser#NewExp.
    def exitNewExp(self, ctx:SolidityParser.NewExpContext):
        pass


    # Enter a parse tree produced by SolidityParser#BitAndOp.
    def enterBitAndOp(self, ctx:SolidityParser.BitAndOpContext):
        pass

    # Exit a parse tree produced by SolidityParser#BitAndOp.
    def exitBitAndOp(self, ctx:SolidityParser.BitAndOpContext):
        pass


    # Enter a parse tree produced by SolidityParser#IndexRangeAccess.
    def enterIndexRangeAccess(self, ctx:SolidityParser.IndexRangeAccessContext):
        pass

    # Exit a parse tree produced by SolidityParser#IndexRangeAccess.
    def exitIndexRangeAccess(self, ctx:SolidityParser.IndexRangeAccessContext):
        pass


    # Enter a parse tree produced by SolidityParser#BitOrOp.
    def enterBitOrOp(self, ctx:SolidityParser.BitOrOpContext):
        pass

    # Exit a parse tree produced by SolidityParser#BitOrOp.
    def exitBitOrOp(self, ctx:SolidityParser.BitOrOpContext):
        pass


    # Enter a parse tree produced by SolidityParser#UnarySuffixOp.
    def enterUnarySuffixOp(self, ctx:SolidityParser.UnarySuffixOpContext):
        pass

    # Exit a parse tree produced by SolidityParser#UnarySuffixOp.
    def exitUnarySuffixOp(self, ctx:SolidityParser.UnarySuffixOpContext):
        pass


    # Enter a parse tree produced by SolidityParser#MultiplicativeOp.
    def enterMultiplicativeOp(self, ctx:SolidityParser.MultiplicativeOpContext):
        pass

    # Exit a parse tree produced by SolidityParser#MultiplicativeOp.
    def exitMultiplicativeOp(self, ctx:SolidityParser.MultiplicativeOpContext):
        pass


    # Enter a parse tree produced by SolidityParser#IndexAccess.
    def enterIndexAccess(self, ctx:SolidityParser.IndexAccessContext):
        pass

    # Exit a parse tree produced by SolidityParser#IndexAccess.
    def exitIndexAccess(self, ctx:SolidityParser.IndexAccessContext):
        pass


    # Enter a parse tree produced by SolidityParser#EqualityOp.
    def enterEqualityOp(self, ctx:SolidityParser.EqualityOpContext):
        pass

    # Exit a parse tree produced by SolidityParser#EqualityOp.
    def exitEqualityOp(self, ctx:SolidityParser.EqualityOpContext):
        pass


    # Enter a parse tree produced by SolidityParser#AndOperation.
    def enterAndOperation(self, ctx:SolidityParser.AndOperationContext):
        pass

    # Exit a parse tree produced by SolidityParser#AndOperation.
    def exitAndOperation(self, ctx:SolidityParser.AndOperationContext):
        pass


    # Enter a parse tree produced by SolidityParser#RelationalOp.
    def enterRelationalOp(self, ctx:SolidityParser.RelationalOpContext):
        pass

    # Exit a parse tree produced by SolidityParser#RelationalOp.
    def exitRelationalOp(self, ctx:SolidityParser.RelationalOpContext):
        pass


    # Enter a parse tree produced by SolidityParser#OrOperation.
    def enterOrOperation(self, ctx:SolidityParser.OrOperationContext):
        pass

    # Exit a parse tree produced by SolidityParser#OrOperation.
    def exitOrOperation(self, ctx:SolidityParser.OrOperationContext):
        pass


    # Enter a parse tree produced by SolidityParser#MemberAccess.
    def enterMemberAccess(self, ctx:SolidityParser.MemberAccessContext):
        pass

    # Exit a parse tree produced by SolidityParser#MemberAccess.
    def exitMemberAccess(self, ctx:SolidityParser.MemberAccessContext):
        pass


    # Enter a parse tree produced by SolidityParser#FunctionCallOptions.
    def enterFunctionCallOptions(self, ctx:SolidityParser.FunctionCallOptionsContext):
        pass

    # Exit a parse tree produced by SolidityParser#FunctionCallOptions.
    def exitFunctionCallOptions(self, ctx:SolidityParser.FunctionCallOptionsContext):
        pass


    # Enter a parse tree produced by SolidityParser#ShiftOp.
    def enterShiftOp(self, ctx:SolidityParser.ShiftOpContext):
        pass

    # Exit a parse tree produced by SolidityParser#ShiftOp.
    def exitShiftOp(self, ctx:SolidityParser.ShiftOpContext):
        pass


    # Enter a parse tree produced by SolidityParser#TypeNameExp.
    def enterTypeNameExp(self, ctx:SolidityParser.TypeNameExpContext):
        pass

    # Exit a parse tree produced by SolidityParser#TypeNameExp.
    def exitTypeNameExp(self, ctx:SolidityParser.TypeNameExpContext):
        pass


    # Enter a parse tree produced by SolidityParser#MetaType.
    def enterMetaType(self, ctx:SolidityParser.MetaTypeContext):
        pass

    # Exit a parse tree produced by SolidityParser#MetaType.
    def exitMetaType(self, ctx:SolidityParser.MetaTypeContext):
        pass


    # Enter a parse tree produced by SolidityParser#InlineArrayExp.
    def enterInlineArrayExp(self, ctx:SolidityParser.InlineArrayExpContext):
        pass

    # Exit a parse tree produced by SolidityParser#InlineArrayExp.
    def exitInlineArrayExp(self, ctx:SolidityParser.InlineArrayExpContext):
        pass


    # Enter a parse tree produced by SolidityParser#literal.
    def enterLiteral(self, ctx:SolidityParser.LiteralContext):
        pass

    # Exit a parse tree produced by SolidityParser#literal.
    def exitLiteral(self, ctx:SolidityParser.LiteralContext):
        pass


    # Enter a parse tree produced by SolidityParser#literalWithSubDenomination.
    def enterLiteralWithSubDenomination(self, ctx:SolidityParser.LiteralWithSubDenominationContext):
        pass

    # Exit a parse tree produced by SolidityParser#literalWithSubDenomination.
    def exitLiteralWithSubDenomination(self, ctx:SolidityParser.LiteralWithSubDenominationContext):
        pass


    # Enter a parse tree produced by SolidityParser#tupleExpression.
    def enterTupleExpression(self, ctx:SolidityParser.TupleExpressionContext):
        pass

    # Exit a parse tree produced by SolidityParser#tupleExpression.
    def exitTupleExpression(self, ctx:SolidityParser.TupleExpressionContext):
        pass


    # Enter a parse tree produced by SolidityParser#numberLiteral.
    def enterNumberLiteral(self, ctx:SolidityParser.NumberLiteralContext):
        pass

    # Exit a parse tree produced by SolidityParser#numberLiteral.
    def exitNumberLiteral(self, ctx:SolidityParser.NumberLiteralContext):
        pass


    # Enter a parse tree produced by SolidityParser#identifier.
    def enterIdentifier(self, ctx:SolidityParser.IdentifierContext):
        pass

    # Exit a parse tree produced by SolidityParser#identifier.
    def exitIdentifier(self, ctx:SolidityParser.IdentifierContext):
        pass


    # Enter a parse tree produced by SolidityParser#userDefinedValueTypeDefinition.
    def enterUserDefinedValueTypeDefinition(self, ctx:SolidityParser.UserDefinedValueTypeDefinitionContext):
        pass

    # Exit a parse tree produced by SolidityParser#userDefinedValueTypeDefinition.
    def exitUserDefinedValueTypeDefinition(self, ctx:SolidityParser.UserDefinedValueTypeDefinitionContext):
        pass


    # Enter a parse tree produced by SolidityParser#booleanLiteral.
    def enterBooleanLiteral(self, ctx:SolidityParser.BooleanLiteralContext):
        pass

    # Exit a parse tree produced by SolidityParser#booleanLiteral.
    def exitBooleanLiteral(self, ctx:SolidityParser.BooleanLiteralContext):
        pass


    # Enter a parse tree produced by SolidityParser#hexStringLiteral.
    def enterHexStringLiteral(self, ctx:SolidityParser.HexStringLiteralContext):
        pass

    # Exit a parse tree produced by SolidityParser#hexStringLiteral.
    def exitHexStringLiteral(self, ctx:SolidityParser.HexStringLiteralContext):
        pass


    # Enter a parse tree produced by SolidityParser#unicodeStringLiteral.
    def enterUnicodeStringLiteral(self, ctx:SolidityParser.UnicodeStringLiteralContext):
        pass

    # Exit a parse tree produced by SolidityParser#unicodeStringLiteral.
    def exitUnicodeStringLiteral(self, ctx:SolidityParser.UnicodeStringLiteralContext):
        pass


    # Enter a parse tree produced by SolidityParser#stringLiteral.
    def enterStringLiteral(self, ctx:SolidityParser.StringLiteralContext):
        pass

    # Exit a parse tree produced by SolidityParser#stringLiteral.
    def exitStringLiteral(self, ctx:SolidityParser.StringLiteralContext):
        pass


    # Enter a parse tree produced by SolidityParser#overrideSpecifier.
    def enterOverrideSpecifier(self, ctx:SolidityParser.OverrideSpecifierContext):
        pass

    # Exit a parse tree produced by SolidityParser#overrideSpecifier.
    def exitOverrideSpecifier(self, ctx:SolidityParser.OverrideSpecifierContext):
        pass



del SolidityParser