# normalize_to_tsv.py  (한 번만 실행)
from pathlib import Path
import re, sys

src = Path("pending_result2.csv")          # 원본
dst = Path("pending_result_norm2.tsv")     # 출력 (탭 TSV)

text = src.read_text(errors="ignore")     # 인코딩 자동 감지
text = text.replace("\x00", "")           # NULL 제거
text = text.replace("\r\n", "\n").replace("\r", "\n")
# 1) 헤더 줄 앞뒤 공백 제거
lines = [re.sub(r"^\s+|\s+$", "", ln) for ln in text.splitlines() if ln.strip()]
# 2) 연속 공백(스페이스·탭) → 탭 1개
lines = [re.sub(r"[ \t]+", "\t", ln) for ln in lines]
dst.write_text("\n".join(lines), encoding="utf-8")   # ← ❷ 명시
print("✓ UTF-8 TSV 작성 →", dst)
print("✓ 정규화 완료 →", dst)

# ── 행별 필드 개수 검사 ─────────────────────────────
bad = []
for idx, ln in enumerate(lines, 1):           # 1-based line 번호
    nfield = ln.count("\t") + 1
    if nfield != 6:                           # 정상이면 6개
        bad.append((idx, nfield, ln))

if bad:
    print("⚠ 열 개수 불일치 행 발견:")
    for idx, nf, ln in bad:
        print(f"  line {idx}: {nf} fields → {ln}")
else:
    print("✓ 모든 행 6필드 확인")
