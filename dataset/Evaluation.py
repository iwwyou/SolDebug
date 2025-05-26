import pandas as pd, math

# ────────────────────────────────────────────────
# 1.  raw CSV (함수·슬롯·Δ·iter) 로드
#     ‣ 열 이름 예:  function, annVars, stateSlots, byteOp, test_range, iter
#     ‣ 선택 열    : solq_const  (없으면 5 s 로 간주)
# ────────────────────────────────────────────────
df = pd.read_csv("latency_raw.csv")

if "solq_const" not in df.columns:          # 함수별 고정 오버헤드(기본 5 s)
    df["solq_const"] = 5

# ────────────────────────────────────────────────
# 2.  지연 모델
# ────────────────────────────────────────────────
def remix_base(r):
    return 3 + 2*r.stateSlots + 2 + r.byteOp/6      # seconds

def solq_base(r):
    c = r.solq_const
    return 10*r.annVars + c if r.iter == 1 else 5*math.ceil(r.annVars/2) + c

# ────────────────────────────────────────────────
# 3.  x-축( baseline )  /  z-축( 최종 latency ) 계산
# ────────────────────────────────────────────────
df["remix_base_s"] = df.apply(remix_base, axis=1)
df["remix_lat_s"]  = df.apply(
    lambda r: r.remix_base_s if r.test_range == 0
              else r.remix_base_s * r.test_range,
    axis=1)

df["solq_base_s"] = df.apply(solq_base, axis=1)
df["solq_lat_s"]  = df["solq_base_s"]          # Δ가 SolQ 지연에 영향 없음

# ────────────────────────────────────────────────
# 4.  저장
# ────────────────────────────────────────────────
df.to_csv("latency_full_updated.csv", index=False)
print("✔ latency_full_updated.csv written.")
