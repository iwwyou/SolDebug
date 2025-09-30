from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:                                         # 타입 검사 전용
     from Analyzer.ContractAnalyzer import ContractAnalyzer

from Utils.CFG import ContractCFG, FunctionCFG
from Domain.Interval import UnsignedIntegerInterval, IntegerInterval, BoolInterval
from Domain.Variable import GlobalVariable, Variables, ArrayVariable, StructVariable, EnumVariable
from Domain.Address import AddressSymbolicManager
from Domain.Type import SolType

class StaticCFGFactory:

    @staticmethod
    def make_contract_cfg(an:ContractAnalyzer, contract_name: str) -> ContractCFG:
        if contract_name in an.contract_cfgs:
            return an.contract_cfgs[contract_name]

        cfg = ContractCFG(contract_name)

        # ────────── 1. local helpers ──────────
        def _u256(val: int = 0) -> UnsignedIntegerInterval:
            """[val,val] 256-bit uint Interval"""
            return UnsignedIntegerInterval(val, val, 256)

        def _addr_fixed(nid: int) -> UnsignedIntegerInterval:
            """symbolicAddress nid → Interval [nid,nid] (일관성 위해 매니저에 등록)"""
            an.sm.register_fixed_id(nid)
            return an.sm.get_interval(nid)

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

        for gv in cfg.globals.values():
            an.register_var(gv)

        an.contract_cfgs[contract_name] = cfg
        return cfg

    @staticmethod
    def make_modifier_cfg(an, contract_cfg, modifier_name: str,
                          parameters: dict[str, SolType] | None = None) -> FunctionCFG:
        """
        • modifier 정의부를 한 번만 호출
        • FunctionCFG 와 기본 abstract env 를 만들어 contract_cfg.functions 에 등록
        """
        if modifier_name in contract_cfg.functions:
            return contract_cfg.functions[modifier_name]  # 중복 선언 방지

        mod_cfg = FunctionCFG(function_type="modifier",
                              function_name=modifier_name)

        # ────────── 1. 파라미터 변수 생성 ──────────
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
                    var_obj.value = an.evaluator.calculate_default_interval(et)
                elif et == "address":
                    # 파라미터 address → 전체 범위
                    var_obj.value = UnsignedIntegerInterval(0, 2 ** 160 - 1, 160)
                else:  # bytes / string 등
                    var_obj.value = f"symbol_{var_name}"

            mod_cfg.add_related_variable(var_obj)

        # ────────── 2. 상태‧글로벌 변수 얕은 참조 등록 ──────────
        if contract_cfg.state_variable_node:
            for var in contract_cfg.state_variable_node.variables.values():
                mod_cfg.add_related_variable(var)
        for gv in contract_cfg.globals.values():
            mod_cfg.add_related_variable(gv)

        # ────────── 3. 저장 & snapshot 등록 ──────────
        contract_cfg.functions[modifier_name] = mod_cfg
        an.snapman.register(mod_cfg, an.ser)  # 원한다면 전체 CFG 스냅도

        return mod_cfg

    @staticmethod
    def make_constructor_cfg(an: ContractAnalyzer,
                             name: str,
                             params: list[tuple[SolType, str]],
                             modifiers: list[str]) -> FunctionCFG:
        cfg = FunctionCFG(function_type="constructor", function_name=name)

        # 파라미터->Variables
        for typ, pname in params:
            if pname:
                var = StaticCFGFactory.make_param_variable(
                    an,  # 🔑 ContractAnalyzer 인스턴스
                    typ,  # SolType
                    pname,  # 식별자
                    scope="local"
                )
                cfg.add_related_variable(var)
                cfg.parameters.append(pname)

        # 상태·글로벌 변수 복사
        ccf = an.contract_cfgs[an.current_target_contract]
        if ccf.state_variable_node:
            for v in ccf.state_variable_node.variables.values():
                cfg.add_related_variable(v)
        for gv in ccf.globals.values():
            cfg.add_related_variable(gv)

        return cfg

    @staticmethod
    def make_function_cfg(an: ContractAnalyzer,
                          name: str,
                          params,
                          modifiers,
                          returns) -> FunctionCFG:

        fcfg = FunctionCFG(function_type="function", function_name=name)

        # Get ENTRY node to add parameters to its variables
        entry_node = fcfg.get_entry_node()

        for p_type, p_name in params:
            if p_name:  # 이름이 있는 것만 변수화
                var = StaticCFGFactory.make_param_variable(
                    an,  # 🔑
                    p_type,
                    p_name,
                    scope="local"
                )
                fcfg.add_related_variable(var)
                fcfg.parameters.append(p_name)
                # Add parameter to ENTRY block's variables so it can be propagated
                entry_node.variables[p_name] = var

        for m_name in modifiers:
            an.process_modifier_invocation(fcfg, m_name)

        for r_type, r_name in returns:
            if r_name:
                rv = StaticCFGFactory.make_param_variable(
                    an,  # 🔑
                    r_type,
                    r_name,
                    scope="local"
                )
                fcfg.add_related_variable(rv)
                fcfg.return_vars.append(rv)
                # Add return variable to ENTRY block's variables so it can be propagated
                entry_node.variables[r_name] = rv
            else:
                fcfg.return_types.append(r_type)

        ccf = an.contract_cfgs[an.current_target_contract]
        if ccf.state_variable_node:
            for v in ccf.state_variable_node.variables.values():
                fcfg.add_related_variable(v)
                # Add state variables to ENTRY block's variables so they can be propagated
                entry_node.variables[v.identifier] = v
        for gv in ccf.globals.values():
            fcfg.add_related_variable(gv)
            # Add global variables to ENTRY block's variables so they can be propagated
            entry_node.variables[gv.identifier] = gv

        return fcfg

    @staticmethod
    def make_param_variable(an: ContractAnalyzer,
                            sol_type: SolType,
                            ident: str,
                            *,
                            scope: str = "local"
                            ) -> Variables | ArrayVariable | StructVariable | EnumVariable:
        """
        파라미터·리턴 변수 1개 생성 + 기본 interval 초기화.
        ▶ 기존 ContractAnalyzer._make_param_variable 의 로직 그대로,
          차이점은 `an` 인스턴스를 첫 인자로 받아 snap·structDef 등에 접근.
        """
        ccf = an.contract_cfgs[an.current_target_contract]

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
                    arr.initialize_elements(IntegerInterval.top(base_t.intTypeLength or 256))
                elif et and et.startswith("uint"):
                    arr.initialize_elements(UnsignedIntegerInterval.top(base_t.intTypeLength or 256))
                elif et == "bool":
                    arr.initialize_elements(BoolInterval.top())
                else:  # address / bytes / string / struct 등
                    arr.initialize_not_abstracted_type()
            else:  # 다차원
                arr.initialize_not_abstracted_type()

            an.register_var(arr)
            return arr

        # ──────────────────────────── ② struct ───────────────────────────
        if sol_type.typeCategory == "struct":
            sname = sol_type.structTypeName
            if sname not in ccf.structDefs:
                raise ValueError(f"Undefined struct '{sname}' used as parameter/return.")
            sv = StructVariable(identifier=ident, struct_type=sname, scope=scope)
            sv.initialize_struct(ccf.structDefs[sname])

            an.register_var(sv)
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
                v.value = IntegerInterval.top(sol_type.intTypeLength or 256)
            elif et.startswith("uint"):
                v.value = UnsignedIntegerInterval.top(sol_type.intTypeLength or 256)
            elif et == "bool":
                v.value = BoolInterval.top()
            elif et == "address":
                v.value = AddressSymbolicManager.top_interval()
            else:  # bytes / string …
                v.value = f"symbol_{ident}"

            an.register_var(v)
            return v

        raise ValueError(f"Unsupported typeCategory '{sol_type.typeCategory}'")
