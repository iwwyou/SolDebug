# Analyzer/RecordManager.py
"""RecordManager
========================================
A *thin* utility that turns rich, nested CFG variable environments into a flat
serialisable structure that can be consumed by the UI (or tests) and keeps the
per‑line analysis ledger.

This class intentionally **knows nothing about control‑flow** – it only
receives events (with optional `Expression`, `Variables`, environment dicts,
etc.) and converts them to a uniform dict‑based record which the front‑end can
render.
"""

from __future__ import annotations

from collections import defaultdict
from typing import Dict, List, Any, Union

from Domain.IR import Expression
from Domain.Variable import (
    Variables,
    StructVariable,
    ArrayVariable,
    MappingVariable,
    EnumVariable,
)

class RecordManager:
    """A *stateless* façade – you hand it pieces of information and it stores
    them inside an internal `defaultdict( list )` keyed by source‑line.

    ContractAnalyzer (or the forthcoming DynamicCFGBuilder) is expected to own
    a *single* `RecordManager` instance and call the public helpers whenever it
    wants to publish something for debugging / UI.
    """

    # ---------------------------------------------------------------------
    # CTOR / internal state
    # ---------------------------------------------------------------------

    def __init__(self) -> None:
        # line_no -> List[record‑dict]
        self._acc: defaultdict[int, List[Dict[str, Any]]] = defaultdict(list)

    # ─────────────────────────────────────────────────────
    # 지역변수 선언 기록
    # ─────────────────────────────────────────────────────
    def record_variable_declaration(
            self,
            *,
            line_no: int,
            var_name: str,
            var_obj
    ) -> None:
        """
        · line_no : 선언이 등장한 소스 라인
        · var_name: 식별자
        · var_obj : Variables / ArrayVariable / StructVariable …
        """
        lhs_expr = Expression(identifier=var_name,
                              context="IdentifierExpContext")

        # ① 기록용 dict 준비
        record = {
            "kind": "varDeclaration",
            "vars": {}
        }

        # ② 복합-타입 flatten / 단일-값 직렬화
        if isinstance(var_obj, (ArrayVariable, StructVariable, MappingVariable)):
            self._flatten_var(var_obj, var_name, record["vars"])
        else:  # Variables / EnumVariable
            key = self._expr_to_str(lhs_expr)
            record["vars"][key] = self._serialize_val(
                getattr(var_obj, "value", None)
            )

        # ③ analysis_per_line[line_no] 에 저장/교체
        rec_list = self.analysis_per_line[line_no]
        # 같은 식별자 선언이 이미 있으면 덮어쓰기
        for i, old in enumerate(rec_list):
            if old.get("kind") == "varDeclaration" and \
                    set(old.get("vars", {}).keys()) == set(record["vars"].keys()):
                rec_list[i] = record
                break
        else:
            rec_list.append(record)

    # ---------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------

    def add_env_record(self, line_no: int, stmt_type: str, env: Dict[str, Variables]) -> None:
        """Flatten **entire** variable environment and store it under *line_no*.
        """
        flat: Dict[str, Any] = {}
        for v in env.values():
            self._flatten_var(v, v.identifier, flat)
        self._append_or_replace(
            line_no,
            {"kind": stmt_type, "vars": flat},
            replace_rule=lambda old, new: old.get("kind") == new["kind"],
        )

    def add_single_var_record(
        self,
        line_no: int,
        stmt_type: str,
        expr: Expression,
        var_obj: Union[Variables, StructVariable, ArrayVariable, MappingVariable, EnumVariable],
    ) -> None:
        """Record only *one* variable (or composite root) that the statement
        just touched.
        """
        key_prefix: str = self._expr_to_str(expr)
        record: Dict[str, Any] = {"kind": stmt_type}

        # (A) Composite – flatten recursively ▾
        if isinstance(var_obj, (StructVariable, ArrayVariable, MappingVariable)):
            flat: Dict[str, Any] = {}
            self._flatten_var(var_obj, key_prefix, flat)
            record["vars"] = flat

        # (B) Leaf (Variables / EnumVariable) – serialize directly
        else:
            val_ser = self._serialize_val(getattr(var_obj, "value", None))
            record["vars"] = {key_prefix: val_ser}

        self._append_or_replace(
            line_no,
            record,
            replace_rule=lambda old, new: (
                old.get("kind") == new["kind"]
                and set(old.get("vars", {}).keys()) == set(new["vars"].keys())
            ),
        )

    # ------------------------------------------------------------------
    # Query helpers (for UI / tests)
    # ------------------------------------------------------------------

    def get_range(self, start_ln: int, end_ln: int) -> Dict[int, List[Dict[str, Any]]]:
        """Return the slice `[start_ln, end_ln]` (inclusive) of the ledger."""
        return {ln: self._acc[ln] for ln in range(start_ln, end_ln + 1) if ln in self._acc}

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _append_or_replace(self, line_no: int, new_rec: Dict[str, Any], *, replace_rule) -> None:
        existing = self._acc[line_no]
        for idx, rec in enumerate(existing):
            if replace_rule(rec, new_rec):
                existing[idx] = new_rec  # replace in‑place
                return
        existing.append(new_rec)

    # ------------------------------------------------------------
    # (de)serialisation utilities – mostly copied from ContractAnalyzer
    # ------------------------------------------------------------

    def _expr_to_str(self, e: Expression) -> str:
        """Convert *partial* Expression trees (identifier / member / index) back
        to a Solidity‑like string representation so that the UI can display a
        familiar *path* to the variable.
        """
        if e is None:
            return ""

        # ① root identifier or literal
        if e.base is None:
            return e.identifier or str(e.literal)

        # ② member access
        if e.member is not None:
            return f"{self._expr_to_str(e.base)}.{e.member}"

        # ③ index access
        if e.index is not None:
            return f"{self._expr_to_str(e.base)}[{self._expr_to_str(e.index)}]"

        return "<expr>"  # fallback – should rarely happen for LHS paths

    # -------------------------------------- flatten composite variables ----

    def _flatten_var(self, var_obj: Any, prefix: str, out: Dict[str, Any]):
        # ArrayVariable ---------------------------------------------------
        if isinstance(var_obj, ArrayVariable):
            for idx, elem in enumerate(var_obj.elements):
                self._flatten_var(elem, f"{prefix}[{idx}]", out)
            return

        # StructVariable --------------------------------------------------
        if isinstance(var_obj, StructVariable):
            for m, mem in var_obj.members.items():
                self._flatten_var(mem, f"{prefix}.{m}", out)
            return

        # MappingVariable -------------------------------------------------
        if isinstance(var_obj, MappingVariable):
            for k, mv in var_obj.mapping.items():
                self._flatten_var(mv, f"{prefix}[{k}]", out)
            return

        # Leaf (Variables / EnumVariable) ---------------------------------
        val_ser = self._serialize_val(getattr(var_obj, "value", None))
        out[prefix] = val_ser

    # -------------------------------------- value serialisation  ---------

    def _serialize_val(self, v: Any) -> str:
        # Interval / BoolInterval  ---------------------------------------
        if hasattr(v, "min_value"):
            return f"[{v.min_value},{v.max_value}]"

        # ArrayVariable – serialise shallowly (recursion handled in
        # _flatten_var already). Here we just show a summary.
        if isinstance(v, ArrayVariable):
            return f"array(len={len(v.elements)})"

        # StructVariable / MappingVariable – brief summary only
        if isinstance(v, StructVariable):
            return "struct"  # UI will show individual members anyway
        if isinstance(v, MappingVariable):
            return f"mapping(size={len(v.mapping)})"

        # Fallback str()
        return str(v)
