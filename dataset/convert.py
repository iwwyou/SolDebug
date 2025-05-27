import pandas as pd, math, itertools

# ───────────────────────────────────
# 1.  벤치마크 메타데이터
# ───────────────────────────────────
records = [
    #  function-id,              annVars, stateSlots, byteOp
    ("_earmarkSomeForMaintenance", 4,       2,          75 ),
    ("pushRewardPerGas0",          4,       2,          134),
    ("_burn",                      3,       2,          39 ),
    ("updateUserInfo",             1,       0,          180),
    ("transferFrom_Citrus",        4,       3,          180),
    ("revokeStableMaster",         2,       2,          143),
    ("transferFrom_Dai",           4,       3,          180),
    ("mint_Dai",                   3,       2,          85 ),
    ("calculateUpdatePercentage",  2,       0,          57 ),
    ("transferFrom_Eden",          4,       3,          180),
    ("totalsAcrossChains",         4,       0,          180),
    ("removeUser",                 4,       4,          180),
    ("updateRewardMultiplier",     9,       2,          180),
    ("_bonusPoolLeaderboardKick",  7,       4,          180),
    ("pending",                    7,       0,          180),
]

df = pd.DataFrame(
    records, columns=["function", "annVars", "stateSlots", "byteOp"]
)

# ───────────────────────────────────
# 2.  함수별 고정 분석시간 c_f  (초)  ← 여기만 바꿔주면 됩니다
# ───────────────────────────────────
#   미측정 함수는 디폴트 5s 로 처리
#
c_f_map = {
    "_earmarkSomeForMaintenance": 0.009,
    "pushRewardPerGas0":          0.1008,
    "_burn":                      0.014,
    "updateUserInfo":             0.16418,
    "bep20_trnasferfrom":         0.01200,
    "revokeStableMaster":         0.17001,
    "dai_transferFrom":           0.05200,
    "dai_mint":                   0.02099,
    "revokeStableMaster":         0.17001,
    # … 측정한 함수 계속 추가 …
}
df["c_f"] = df["function"].map(c_f_map).fillna(5.0)   # default 5s

# ───────────────────────────────────
# 3.  Δ(test-range) × iteration  전개
#     → 모든 함수에 iter=1,2  /  Δ=0,2,5,10 행 생성
# ───────────────────────────────────
ranges   = [0, 2, 5, 10]
iters    = [1, 2]
df_full  = (
    df
    .merge(pd.DataFrame({"test_range": ranges}))
    .merge(pd.DataFrame({"iter": iters}))
    .reset_index(drop=True)
)

# ───────────────────────────────────
# 4.  Remix, SolQ 지연 모델
# ───────────────────────────────────
def remix_base(row):
    # 3 + 2·stateSlots  +2  + byteOp/6
    return 3 + 2*row.stateSlots + 2 + row.byteOp/6

df_full["remix_s"] = df_full.apply(
    lambda r: remix_base(r) if r.test_range == 0
              else remix_base(r) * r.test_range,
    axis=1
)

df_full["solq_s"] = df_full.apply(
    lambda r:
        (10*r.annVars + r.c_f)                                  # 1st
        if r.iter == 1 else
        (5*math.ceil(r.annVars/2) + r.c_f),                     # 2nd
    axis=1
)

# ───────────────────────────────────
# 5.  저장
# ───────────────────────────────────
df_full.to_csv("latency_full_updated.csv", index=False)
print("✔ latency_full_updated.csv 작성 완료")
