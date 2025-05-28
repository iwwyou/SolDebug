# gen_pending_add_tests.py  –  덧셈(ver.) pending() 주석 생성기
import json, itertools, pathlib
from z3 import *

BEGIN_LINE = 14
DELTAS     = [1, 3, 6, 10, 15]
PATTERNS   = ["overlap", "diff"]      # ← safe → overlap
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

CONST_LOCKED  = 15_522_000
CONST_UNLOCK  = 2_592_000

def off(i, d):                      # 0,1,2 → 0~d , (d+1)~2d+1 , …
    base = i * (d + 1)
    return (base, base + d)

def build_ranges(pat, d):
    if pat == "overlap":            # 값 범위가 많이 겹치는 케이스
        return [
            (200, 200 + d),         # total
            (0, d),  (0, d),        # unlockedAmounts / pending
            (0, 1),                 # estUnlock
            (0, d),  (0, d),        # ts / startLock
            (CONST_LOCKED  + d, CONST_LOCKED  + d),
            (CONST_UNLOCK  + d, CONST_UNLOCK  + d),
        ]
    else:                           # diff  –  서로 다른 구간에 흩어짐
        base_total = 300
        return [
            (base_total, base_total + d),
            off(0, d), off(1, d),
            off(2, d),
            off(4, d), off(3, d),   # ts, startLock 순서 교환
            (CONST_LOCKED + d, CONST_LOCKED + d),
            (CONST_UNLOCK + d, CONST_UNLOCK + d),
        ]

def mk_solver(r):
    T,U,P,E,TS,ST = Ints("T U P E TS ST")
    L,UDur        = Ints("L UDur")
    s = Solver()
    for v, (lo, hi) in zip([T,U,P,E,TS,ST,L,UDur], r):
        s.add(v >= lo, v <= hi)

    # 양수·기간 제약
    s.add(E > 0, UDur > 0)

    # 덧셈 버전은 언더플로가 없으므로 추가 제약 없음
    return s

def widen(r):                       # 실패 시 살짝 완화
    r[0] = (r[0][0] + 10, r[0][1] + 10)   # total ↑
    return r

# ────────────────────────────── main ───────────────────────────────
for pat, d in itertools.product(PATTERNS, DELTAS):
    rg = build_ranges(pat, d)
    for _ in range(MAX_TRIES):
        if mk_solver(rg).check() == sat:
            break
        rg = widen(rg)
    else:
        print(f"❌  {pat} Δ={d}: no SAT")
        continue

    cur, evts = BEGIN_LINE + 1, []
    evts.append({"code": "// @TestCase BEGIN",
                 "startLine": cur, "endLine": cur, "event": "add"})
    cur += 1
    for (exp, kind), (lo, hi) in zip(T_META, rg):
        evts.append({"code": f"// {TAG[kind]} {exp} = [{lo},{hi}]",
                     "startLine": cur, "endLine": cur, "event": "add"})
        cur += 1
    evts.append({"code": "// @TestCase END",
                 "startLine": cur, "endLine": cur, "event": "add"})

    fname = f"pending_add_{pat}_{d}.json"
    pathlib.Path(fname).write_text(json.dumps(evts, indent=2))
    print("✓", fname, "SAT")
