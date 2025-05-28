import pandas as pd, math

# 1. 메타데이터 --------------------------------------------------
records = [
    ("_earmarkSomeForMaintenance", 4, 2, 75),
    ("pushRewardPerGas0",          4, 2, 134),
    ("_burn",                      3, 2, 39),
    ("updateUserInfo",             1, 0, 180),
    ("transferFrom_Citrus",        4, 3, 180),
    ("revokeStableMaster",         2, 2, 143),
    ("transferFrom_Dai",           4, 3, 180),
    ("mint_Dai",                   3, 2, 85),
    ("calculateUpdatePercentage",  2, 0, 57),
    ("transferFrom_Eden",          4, 3, 180),
    ("removeUser",                 4, 4, 180),
    ("updateRewardMultiplier",     9, 2, 180),
    ("pending",                    7, 0, 180),
]

df = pd.DataFrame(records,
        columns=["function", "annVars", "stateSlots", "byteOp"])

# 2.   c_f  (sec) ------------------------------------------------
c_f_map = {
    "_earmarkSomeForMaintenance": 0.009,
    "pushRewardPerGas0":          0.1008,
    "_burn":                      0.014,
    "updateUserInfo":             0.16418,
    "transferFrom_Citrus":        0.01200,
    "revokeStableMaster":         0.17001,
    "transferFrom_Dai":           0.05200,
    "mint_Dai":                   0.02099,
    "calculateUpdatePercentage":  0.01303,
    "transferFrom_Eden":          0.02108,
    "removeUser":                 0.14307,
    "updateRewardMultiplier":     0.12192,
    "pending":                    0.09651,
}
df["c_f"] = df["function"].map(c_f_map).fillna(5.0)   # 미측정→5 s

# 3.  Δ × iteration  Cartesion Product ---------------------------
ranges = [0, 2, 5, 10]
iters  = [1, 2]

df_full = (
    df.assign(key=1)
      .merge(pd.DataFrame({"test_range": ranges, "key":1}), on="key")
      .merge(pd.DataFrame({"iter": iters,      "key":1}), on="key")
      .drop("key", axis=1)
)

# 4.  지연 모델 --------------------------------------------------
def remix_base(r):
    return 3 + 2*r.stateSlots + 2 + r.byteOp/6   # seconds

df_full["remix_s"] = df_full.apply(
    lambda r: remix_base(r) if r.test_range == 0
              else remix_base(r) * r.test_range,
    axis=1)

df_full["solq_s"] = df_full.apply(
    lambda r: (10*r.annVars + r.c_f)                    # 1st
              if r.iter == 1 else
              (5*math.ceil(r.annVars/2) + r.c_f),       # 2nd
    axis=1)

# 5.  저장 -------------------------------------------------------
df_full.to_csv("latency_full_updated.csv", index=False)
print("✔ latency_full_updated.csv 작성 완료")