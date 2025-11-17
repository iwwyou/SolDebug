import json, pathlib, itertools
from z3 import *

BEGIN_LINE = 14
DELTAS     = [1, 3, 6, 10, 15]
PATTERNS   = ["safe", "diff"]
MAX_TRIES  = 40

T_META = [
    ("_data.total",           "state"),
    ("_data.unlockedAmounts", "state"),
    ("_data.pending",         "state"),
    ("_data.estUnlock",       "state"),
    ("block.timestamp",       "global"),
    ("startLock",             "state"),
    ("lockedTime",            "state"),
    ("unlockDuration",        "state"),
]

TAG = {"state": "@StateVar", "global": "@GlobalVar"}
CONST_LOCKED  = 20_000_000
CONST_UNLOCK  = 2_592_000

def offset_tuple(i, d):
    """diff 패턴: 변수 인덱스별 (lo,hi) 튜플"""
    lo = i * (d + 1)
    return (lo, lo + d)

def build_ranges(pat, d):
    def off(i, d):
        return (i * (d + 1), i * (d + 1) + d)

    if pat == "safe":
        return [
            (200, 200+d),               # total
            (0, d), (0, d),             # unlockedAmounts / pending
            (0, 1),                     # estUnlock
            (0, d), (0, d),             # ts / startLock
            (CONST_LOCKED+d,  CONST_LOCKED+d),
            (CONST_UNLOCK+d, CONST_UNLOCK+d),
        ]
    else:  # diff
        base_total = 300
        return [
            (base_total, base_total + d),  # total
            off(0, d), off(1, d),  # unlockedAmounts / pending
            off(2, d),  # estUnlock
            off(4, d), off(3, d),  # ★ ts 는 4,  startLock 은 3  ← 순서 교체
            (CONST_LOCKED + d, CONST_LOCKED + d),
            (CONST_UNLOCK + d, CONST_UNLOCK + d),
        ]

def mk_solver(r):
    total, ua, pend, est, ts, st = Ints("T U P E TS ST")
    lockT, unDur = Ints("L UDur")
    s = Solver()
    s.add(total >= r[0][0], total <= r[0][1])
    s.add(ua    >= r[1][0], ua    <= r[1][1])
    s.add(pend  >= r[2][0], pend  <= r[2][1])
    s.add(est   >= r[3][0], est   <= r[3][1])
    s.add(ts    >= r[4][0], ts    <= r[4][1])
    s.add(st    >= r[5][0], st    <= r[5][1])
    s.add(lockT == r[6][0], unDur == r[7][0])

    tRemain = total - ua - pend
    nUnlock = (lockT - (ts - st) - 1) / unDur + 1
    p_out   = tRemain - est * nUnlock
    s.add(tRemain >= 0, p_out >= 0, ts <= st + lockT, ts>=st)
    return s

def widen_safe(r):
    r[0] = (r[0][0] + 10, r[0][1] + 10)               # total ↑
    r[1] = (max(0, r[1][0]-1), max(0, r[1][1]-1))     # unlocked ↓
    r[2] = (max(0, r[2][0]-1), max(0, r[2][1]-1))     # pending  ↓
    return r

# ─── 생성 루프 ─────────────────────────────────────────
for pat, d in itertools.product(PATTERNS, DELTAS):
    ranges = build_ranges(pat, d)
    for _ in range(MAX_TRIES):
        if mk_solver(ranges).check() == sat:
            break
        ranges = widen_safe(ranges)
    else:
        print(f"❌  {pat} Δ={d} : SAT 불가")
        continue

    # JSON events: 한 줄 = 한 이벤트
    events, cur = [], BEGIN_LINE + 1
    events.append({"code": "// @TestCase BEGIN",
                   "startLine": cur, "endLine": cur, "event": "add"})
    cur += 1
    for (expr, kind), (lo, hi) in zip(T_META, ranges):
        events.append({"code": f"// {TAG[kind]} {expr} = [{lo},{hi}]",
                       "startLine": cur, "endLine": cur, "event": "add"})
        cur += 1
    events.append({"code": "// @TestCase END",
                   "startLine": cur, "endLine": cur, "event": "add"})

    fname = f"pending_{pat}_{d}.json"
    pathlib.Path(fname).write_text(json.dumps(events, indent=2))
    print("✓", fname, "SAT")
