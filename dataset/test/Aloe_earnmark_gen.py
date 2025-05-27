# gen_earmarkSome_tests.py
# -----------------------------------------------------------
"""
Generate a single  Δ=5  test-case annotation block for
AloeBlend._earmarkSomeForMaintenance().

Output:  JSON file with the incremental-editing events expected
         by SolQDebug.
"""

import json, pathlib
from z3 import *

# ---- 튜닝 파라미터 ----------------------------------------
START_LINE   = 15       #  BEGIN 을 삽입할 첫 행 (원하는 위치로 수정)
WIDTH        = 5         #  hi = lo + WIDTH
MAINT_FEE    = 10
MIN_TOMAINT  = 100       #  toMaintenance  ≥ 100
MAX_TRIES    = 40        #  SAT 실패 시 완화용 반복 한도
# -----------------------------------------------------------

VARS = [                               # (표현식, kind)
    ("earned0",            "local"),
    ("earned1",            "local"),
    ("maintenanceBudget0", "state"),
    ("maintenanceBudget1", "state"),
]
TAG  = {"local": "@LocalVar", "state": "@StateVar"}

def solve_base():
    """
    Z3로 각 변수의 interval 하한(lo)만 찾아낸다.
    상한은 lo + WIDTH 로 고정.
    """
    earned0, earned1, mb0, mb1 = Ints("earned0 earned1 mb0 mb1")
    s = Solver()

    # 기본 범위 – 모두 양수 & 0 제외
    s.add(earned0 >= 1000, earned1 >= 1000)
    s.add(mb0 >= 1, mb1 >= 1)

    # toMaintenance >= MIN_TOMAINT
    s.add(earned0 / MAINT_FEE >= MIN_TOMAINT)
    s.add(earned1 / MAINT_FEE >= MIN_TOMAINT)

    # 언더플로 방지  (사실 정수 나눗셈 성질상 자동 보장되지만 명시)
    s.add(earned0 - (earned0 / MAINT_FEE) >= 0)
    s.add(earned1 - (earned1 / MAINT_FEE) >= 0)

    # (필요하면) 오버플로 상한도 걸 수 있음 – 여기선 생략

    if s.check() == sat:
        m = s.model()
        return [m[v].as_long() for v in (earned0, earned1, mb0, mb1)]
    raise ValueError("❌  constraints unsat – 검토 필요")

# ---- 메인 --------------------------------------------------
lo_vals = solve_base()                    # [earned0, earned1, mb0, mb1]
hi_vals = [v + WIDTH for v in lo_vals]    # 고정 폭

events, line = [], START_LINE
events.append({"code": "// @TestCase BEGIN",
               "startLine": line, "endLine": line, "event": "add"})
line += 1

for (expr, kind), lo, hi in zip(VARS, lo_vals, hi_vals):
    events.append({"code": f"// {TAG[kind]} {expr} = [{lo},{hi}]",
                   "startLine": line, "endLine": line, "event": "add"})
    line += 1

events.append({"code": "// @TestCase END",
               "startLine": line, "endLine": line, "event": "add"})

outfile = "earmarkSomeMaintenance_D5.json"
pathlib.Path(outfile).write_text(json.dumps(events, indent=2))
print(f"✓  {outfile} generated")
