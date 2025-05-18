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
            # (1) 주석 라인 방문
            for code, s, e in self._lines:
                tree = ParserHelpers.generate_parse_tree(code, "debugUnit")
                EnhancedSolidityVisitor(self.analyzer).visit(tree)

            # (2) 함수 한 개 재-해석
            self.analyzer.flush_reinterpret_target()

            # (3) 보고서 – 주석 라인 그대로 넘겨주기
            self.analyzer.send_report_to_front(None)  # ★ 여기 수정
        finally:
            self.snapman.restore_from_snap(snap)
            self._lines.clear()
