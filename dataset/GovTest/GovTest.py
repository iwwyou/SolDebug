# gen_rewardMultiplier_tests.py  (patch version)
# -----------------------------------------------------------
import json, itertools, pathlib
from z3 import *

BEGIN_LINE = 40
DELTAS     = [1, 3, 6, 10]
PATTERNS   = ["safe", "diff"]
MAX_TRIES  = 40
WEEK, DIV  = 604800, 100000

V_META = [
    ("oldRate",               "local"),
    ("newRate",               "local"),
    ("passedTime",            "local"),
    ("oldLockPeriod",         "local"),
    ("newLockPeriod",         "local"),
    ("oldAmount",             "local"),
    ("newAmount",             "local"),
    ("info.rewardMultiplier", "state"),
    ("totalRewardMultiplier", "state"),
]
TAG = {"local": "@LocalVar", "state": "@StateVar"}

POSITIVE_IDX = {        # ranges 리스트에서 0 을 빼고 싶은 위치
    0,      # oldRate
    1,      # newRate
    5,      # oldAmount
    6,      # newAmount
}

SCALE = 10          # 10×-100× 정도면 충분

# ---------- helpers -------------------------------------------------
def same(base, d):   return (base*SCALE, (base+d)*SCALE)

def diff(idx, d, force_pos=False):
    """idx·Δ로 구간 만들기.  force_pos=True면 0 을 건너뜀"""
    base = idx * (d + 1) * SCALE
    if force_pos or d == 0:        # Δ=0 인 경우에도 0 제외
        base += 1                  # → [1, 1+Δ]
    return (base, base + d*SCALE)


def build_ranges(style, Δ):
    WEEK_H = 604800
    BIG = 50_000  # 충분히 큰 base
    if style == "safe":
        #  “old < new, 덧셈이 더 크게” 조건을 확실히 만족하도록
        return [
            same(  5, Δ),             # oldRate
            same(  8, Δ),             # newRate   (≥ oldRate)
            same(  1, Δ),             # passedTime
            same(  8 * WEEK, Δ),      # oldLockPeriod
            same( 12 * WEEK, Δ),      # newLockPeriod (> old)
            same( 10, Δ),             # oldAmount
            same( 20, Δ),             # newAmount  (> old)
            same(1000, 0),            # rewardMultiplier (fixed)
            same(5000, 0),            # totalRewardMultiplier (fixed)
        ]
    else:
        return [
            diff(2, Δ, True),  # oldRate  ≥ 3
            diff(6, Δ, True),  # newRate  ≥ 7
            diff(1, Δ),  # passedTime
            (12 * WEEK_H, 12 * WEEK_H + Δ),  # oldLockPeriod ≥ 12w
            (20 * WEEK_H, 20 * WEEK_H + Δ),  # newLockPeriod ≥ 20w
            diff(5, Δ, True),  # oldAmount ≥ 6
            diff(10, Δ, True),  # newAmount ≥11
            same(1000, 0),
            same(5000, 0),
        ]

def mk_solver(r):
    orate, nrate, ptime, oLock, nLock, oAmt, nAmt, rmul, tot = Ints(
        "orate nrate ptime oLock nLock oAmt nAmt rmul tot")
    s = Solver()
    for v, (lo, hi) in zip(
            [orate, nrate, ptime, oLock, nLock, oAmt, nAmt, rmul, tot],
            r):
        s.add(v >= lo, v <= hi)

    WEEK, DIV = 604800, 100000

    # (1) 기간·양수 제약
    s.add(orate > 0, nrate > 0, oAmt > 0, nAmt > 0)
    s.add(oLock >= ptime)  # under-flow 방지

    # (2)   / 1 weeks  결과가 0이 되지 않도록
    s.add(oLock - ptime >= WEEK)  # ⇒ (oLock-ptime)/WEEK ≥ 1
    s.add(nLock >= WEEK)  # ⇒ nLock/WEEK          ≥ 1

    # (3) toAdd ≥ toRemove  (언더플로 방지)
    toRem = (((oLock - ptime) / WEEK) * orate * oAmt) / DIV
    toAdd = ((nLock / WEEK) * nrate * nAmt) / DIV
    s.add(toAdd >= toRem)
    return s

def widen(r):                                     # gradually relax
    r[1] = (r[1][0]+2, r[1][1]+2)
    r[6] = (r[6][0]+2, r[6][1]+2)
    r[5] = (max(1, r[5][0]-1), r[5][1])
    r[4] = (r[4][0]+WEEK, r[4][1]+WEEK)
    return r

# ---------- main loop -----------------------------------------------
for style, Δ in itertools.product(PATTERNS, DELTAS):
    rng = build_ranges(style, Δ)
    for _ in range(MAX_TRIES):
        if mk_solver(rng).check() == sat:
            break
        rng = widen(rng)
    else:
        print(f"❌  {style} Δ={Δ}: no SAT")
        continue

    # build JSON event list
    cur, evts = BEGIN_LINE + 1, []
    evts.append({"code": "// @TestCase BEGIN",
                 "startLine": cur, "endLine": cur, "event": "add"})
    cur += 1
    for (exp, kind), (lo, hi) in zip(V_META, rng):
        evts.append({"code": f"// {TAG[kind]} {exp} = [{lo},{hi}]",
                     "startLine": cur, "endLine": cur, "event": "add"})
        cur += 1
    evts.append({"code": "// @TestCase END",
                 "startLine": cur, "endLine": cur, "event": "add"})

    fname = f"updateRewardMultiplier_{style}_{Δ}.json"
    pathlib.Path(fname).write_text(json.dumps(evts, indent=2))
    print("✓", fname, "generated")
