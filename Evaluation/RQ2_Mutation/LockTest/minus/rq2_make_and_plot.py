# rq2_make_and_plot.py  ─────────────────────────────────────────────
# 1)  입력 : pending_result2.csv       (쉼표 · 탭 · 공백 아무거나,
#                                      UTF-8 / CP949 모두 허용)
# 2)  출력 : rq2_precision.csv , fig_pending_f90.pdf
# ------------------------------------------------------------------
import pandas as pd, numpy as np, matplotlib.pyplot as plt
from pathlib import Path
from io import StringIO
import csv, re, sys

RAW = Path("pending_result2.csv")          # ★ 원본 파일
OUT = "rq2_precision.csv"

# ───────────────────── 1. 유연 로더 ────────────────────────────────
def read_flexible(path: Path) -> pd.DataFrame:
    """인코딩·구분자 자동 감지 CSV/TSV 로더.
       - 쉼표 / 탭 / 공백 혼용
       - UTF-8 · UTF-8-SIG · CP949 · Latin-1 모두 허용
       - NULL 바이트 / 혼합 개행 자동 정리
    """
    # ① 인코딩 탐색
    for enc in ("utf-8", "utf-8-sig", "cp949", "latin1"):
        try:
            txt = path.read_bytes().decode(enc)
            break
        except UnicodeDecodeError:
            continue
    else:
        sys.exit("⚠ 인코딩 감지 실패")

    # ② NULL 제거 + 개행 통일
    txt = txt.replace("\x00", "")
    txt = txt.replace("\r\n", "\n").replace("\r", "\n")

    # ③ 우선 : csv.Sniffer (쉼표·탭 구분 CSV)
    try:
        df = pd.read_csv(StringIO(txt),
                         sep=None, engine="python",
                         quoting=csv.QUOTE_NONE)
        return df
    except pd.errors.ParserError:
        pass                        # 실패하면 공백 기반으로 재시도

    # ④ 공백(스페이스·탭) 1 개 이상 구분
    return pd.read_csv(StringIO(txt),
                       sep=r"\s+",
                       engine="python",
                       quoting=csv.QUOTE_NONE,
                       on_bad_lines="skip")   # 열 불일치 행 건너뛰기

raw = read_flexible(RAW)

# ───────────────────── 2. 숫자형 변환 & 파생 ──────────────────────
for col in ("low", "high"):
    raw[col] = pd.to_numeric(raw[col], errors="coerce")

raw["finite"]      = np.isfinite(raw["high"])
raw["exit_width"]  = raw["high"] - raw["low"]
raw["input_width"] = raw["delta"].replace(0, 1)     # Δ=0 보정
raw["infl"]        = raw["exit_width"] / raw["input_width"]

# ───────────────────── 3. FinRatio · F90 요약 ─────────────────────
def summarise(gr):
    fin_ratio = float(gr["finite"].all())            # 1.0 또는 0.0
    f90       = np.percentile(gr["infl"], 90)
    return pd.Series(dict(fin_ratio=fin_ratio, f90=f90))

summary = (
    raw.groupby(["function", "pattern", "delta"], as_index=False)
        .apply(summarise)
)

summary.to_csv(OUT, index=False, encoding="utf-8")
print("✓", OUT, "saved")

# ───────────────────── 4. F90 그래프 ──────────────────────────────
plt.figure()
for pat, grp in summary.groupby("pattern"):
    plt.plot(grp["delta"], grp["f90"], marker="o", label=pat)
plt.xlabel("Δ (input range)")
plt.ylabel("F90 (inflation ×)")
#title_fn = ", ".join(summary["function"].unique())
plt.title(f"DIVIDE/SUB – F90 vs Δ")
plt.legend()
plt.tight_layout()
plt.savefig("fig_pending_f90.pdf")
plt.close()
print("✓ fig_pending_f90.pdf saved")
