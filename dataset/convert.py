import pandas as pd, math

# ── 1. 표를 그대로 코드에 작성 ─────────────────────────
data = [
    ("_earmarkSomeForMaintenance", 4, 2, 75),
    ("pushRewardPerGas0",          4, 2, 134),
    ("_burn",                      3, 2, 39),
    ("updateUserInfo",             1, 0, 180),   # >180 → 180
    ("transferFrom_Citrus",        4, 3, 180),
    ("revokeStableMaster",         2, 2, 143),
    ("transferFrom_Dai",           4, 3, 180),
    ("mint_Dai",                   3, 2, 85),
    ("calculateUpdatePercentage",  2, 0, 57),
    ("transferFrom_Eden",          4, 3, 180),
    ("totalsAcrossChains",         4, 0, 180),
    ("removeUser",                 4, 4, 180),
    ("updateRewardMultiplier",     9, 2, 180),
    ("_bonusPoolLeaderboardKick",  7, 4, 180),
    ("pending",                    7, 0, 180),
]

df = pd.DataFrame(data,
    columns=["function", "annVars", "stateSlots", "byteOp"])

# Δ(test-range)와 iteration 값 생성
df = df.assign(**{
    "test_range":  [0,2,5,10]* (len(df)//4) + [0]* (len(df)%4),  # 예시
    "iter":        [1,2]* (len(df)//2) + [1]* (len(df)%2)       # 예시
})

# ── 2. 지연 계산 공식 ───────────────────────────────
def remix_base(row):
    return 3 + 2*row.stateSlots + 2 + row.byteOp/6    # seconds

df["remix_s"] = df.apply(
    lambda r: remix_base(r) if r.test_range == 0
              else remix_base(r) * r.test_range,
    axis=1)

df["solq_s"] = df.apply(
    lambda r: (10*r.annVars + 5)
              if r.iter == 1
              else (5*math.ceil(r.annVars/2) + 5),
    axis=1)   # milliseconds → seconds

df.to_csv("latency_full_updated.csv", index=False)
print("✔ latency_full_updated.csv 저장 완료")
