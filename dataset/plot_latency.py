# plot_latency_3d.py
import math, pandas as pd, matplotlib.pyplot as plt
from mpl_toolkits.mplot3d import Axes3D   # noqa: F401

df = pd.read_csv("latency_full_updated.csv")

# ────────────────────────────────
# 1.  x-축용 ‘원가 모델’ 컬럼 계산
# ────────────────────────────────
# Remix (iter 1 – 모델식은 test_range 미포함)
df["remix_x"] = 3 + 2*df["stateSlots"] + 2 + df["byteOp"]/6

# SolQ (iter 1, 2 각기 다름)
def solq_x(row):
    base1 = 10*row.annVars + row.c_f
    base2 = 5*math.ceil(row.annVars/2) + row.c_f
    return base1 if row.iter == 1 else base2
df["solq_x"] = df.apply(solq_x, axis=1)

# ────────────────────────────────
# 2.  산점도 정의 & 출력
# ────────────────────────────────
plots = [
    dict(label="Remix",      x="remix_x", y="test_range", z="remix_s",
         subset=df["iter"] == 1, marker="o", color="tab:orange",
         file="fig3d_remix.pdf"),

    dict(label="SolQ 1st",   x="solq_x",  y="test_range", z="solq_s",
         subset=df["iter"] == 1, marker="^", color="tab:blue",
         file="fig3d_solq_iter1.pdf"),

    dict(label="SolQ 2nd",   x="solq_x",  y="test_range", z="solq_s",
         subset=df["iter"] == 2, marker="v", color="tab:blue",
         file="fig3d_solq_iter2.pdf"),
]

for cfg in plots:
    sub = df[cfg["subset"]]

    fig = plt.figure()
    ax  = fig.add_subplot(111, projection="3d")        # type: ignore[attr-defined]

    ax.scatter(sub[cfg["x"]], sub[cfg["y"]], sub[cfg["z"]],
               marker=cfg["marker"], s=35,
               color=cfg["color"], edgecolors="none")

    ax.set_xlabel(f"{cfg['label']} cost model (s)")
    ax.set_ylabel("Test-case Δ")
    ax.set_zlabel("Latency (s)")                        # type: ignore[attr-defined]
    ax.set_title(f"{cfg['label']} – 3-D latency scatter")

    fig.tight_layout()
    fig.savefig(cfg["file"])
    plt.close(fig)

print("✔ 3-D plots saved:")
for cfg in plots:
    print("  •", cfg["file"])
