# Analyzer/DebugBatchManager.py
# ────────────────────────────
from Utils.util              import ParserHelpers
from Analyzer.EnhancedSolidityVisitor import EnhancedSolidityVisitor

class DebugBatchManager:
    """
    테스트-케이스(@TestCase … END) 안의
    디버그 주석 라인을 **영구 보관**하고,
      • add     → 그대로 추가
      • modify  → 같은 startLine 교체
      • delete  → 제거
    flush() 는 ‘현재 보관 중인 모든 라인’을 해석만 하고
    _lines 는 지우지 않는다.  (@TestCase BEGIN 때만 초기화)
    """
    def __init__(self, analyzer, snapman):
        # key = startLine, value = (code,start,end)
        self._lines: dict[int, tuple[str, int, int]] = {}
        self.analyzer = analyzer
        self.snapman  = snapman

    # ── 라인 조작 ──────────────────────────────────────────
    def add_line(self, code: str, s: int, e: int):
        self._lines[s] = (code, s, e)

    def modify_line(self, code: str, s: int, e: int):
        self._lines[s] = (code, s, e)          # 같은 key 교체

    def delete_line(self, s: int):
        self._lines.pop(s, None)

    # ── flush : 현재까지의 _lines 전부 해석 ────────────────
    def flush(self):
        if not self._lines:
            return
        snap = self.snapman.snapshot()
        try:
            for code, s, e in self._lines.values():
                tree = ParserHelpers.generate_parse_tree(code, "debugUnit")
                EnhancedSolidityVisitor(self.analyzer).visit(tree)

            # 선택된 한 함수만 재-해석
            self.analyzer.flush_reinterpret_target()

            # 결과 전송
            self.analyzer.send_report_to_front(None)
        finally:
            self.snapman.restore_from_snap(snap)

    # ── 테스트-케이스 새로 시작할 때 호출 ──────────────────
    def reset(self):
        self._lines.clear()
