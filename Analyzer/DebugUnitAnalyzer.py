# Analyzer/DebugBatchManager.py
# ─────────────────────────────────────────────────────────────
from Utils.cfg                         import FunctionCFG
from Analyzer.EnhancedSolidityVisitor  import EnhancedSolidityVisitor
from Utils.util                        import ParserHelpers     # ★ here

class DebugBatchManager:
    def __init__(self, analyzer, snapman):
        self._lines: list[tuple[str, int, int]] = []
        self.analyzer = analyzer
        self.snapman  = snapman

    def add_line(self, code: str, s: int, e: int) -> None:
        self._lines.append((code, s, e))

    def flush(self) -> None:
        if not self._lines:
            return

        snap = self.snapman.snapshot()

        try:
            # (1) 전체 라인 방문 (interpret 지연)
            for code, s, e in self._lines:
                tree = ParserHelpers.generate_parse_tree(code, "debugUnit")
                EnhancedSolidityVisitor(self.analyzer).visit(tree)

            # (2) 모아둔 함수만 재-해석
            self.analyzer.flush_reinterpret_targets()

            # (3) 결과 → 프런트
            self.analyzer.send_report_to_front(self._lines)
        finally:
            self.snapman.restore(snap)
            self._lines.clear()
