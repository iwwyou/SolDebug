import csv
import json
from collections import defaultdict

with open('solqdebug-experiment.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

problems = [r for r in rows if r.get('task') == 'problem']

print("=== RT Values (in seconds) ===\n")

# Group by problem
by_problem = defaultdict(list)
for r in problems:
    rt_sec = float(r['rt']) / 1000
    by_problem[r['problem_name']].append({
        'run_id': r['run_id'],
        'rt_sec': rt_sec,
        'rt_min': rt_sec / 60
    })

for pname in ['GreenHouse', 'HubPool', 'PercentageFeeModel', 'LockupContract', 'Lock']:
    data = by_problem[pname]
    print(f"\n{pname}:")
    sorted_data = sorted(data, key=lambda x: x['rt_sec'])
    for d in sorted_data:
        flag = " <-- OUTLIER?" if d['rt_sec'] > 300 else ""
        print(f"  run_id {d['run_id']}: {d['rt_sec']:.1f}s ({d['rt_min']:.1f}min){flag}")

    times = [d['rt_sec'] for d in data]
    print(f"  Mean: {sum(times)/len(times):.1f}s, Median: {sorted(times)[len(times)//2]:.1f}s")

# Check raw rt values
print("\n\n=== Sample raw rt values ===")
for i, r in enumerate(problems[:10]):
    print(f"rt={r['rt']} ms = {float(r['rt'])/1000:.1f}s")
