import csv
import json
from collections import defaultdict

# Load data
with open('solqdebug-experiment.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print("=" * 60)
print("RQ4 DATA ANALYSIS")
print("=" * 60)

# 1. Basic Statistics - Problems only
problems = [r for r in rows if r.get('task') == 'problem']
print(f"\n[1] BASIC STATISTICS")
print(f"Total problem responses: {len(problems)}")

run_ids = set(r['run_id'] for r in problems)
print(f"Unique participants (run_id): {len(run_ids)}")

# Overall accuracy
correct_count = sum(1 for r in problems if r.get('is_correct') == 'true')
accuracy = correct_count / len(problems) * 100 if problems else 0
print(f"\nOverall Accuracy: {accuracy:.1f}% ({correct_count}/{len(problems)})")

# Overall response time (convert from ms to seconds)
rts = [float(r['rt'])/1000 for r in problems if r.get('rt')]
mean_rt = sum(rts) / len(rts) if rts else 0
sorted_rts = sorted(rts)
median_rt = sorted_rts[len(sorted_rts)//2] if sorted_rts else 0
print(f"Mean Response Time: {mean_rt:.1f} sec")
print(f"Median Response Time: {median_rt:.1f} sec")

# 2. Per-problem analysis
print(f"\n[2] PER-PROBLEM ANALYSIS")
print("-" * 60)
problem_stats = defaultdict(lambda: {'correct': 0, 'total': 0, 'times': []})
for r in problems:
    key = (r.get('problem_number', ''), r.get('problem_name', ''))
    problem_stats[key]['total'] += 1
    if r.get('is_correct') == 'true':
        problem_stats[key]['correct'] += 1
    if r.get('rt'):
        problem_stats[key]['times'].append(float(r['rt'])/1000)

print(f"{'#':<3} {'Name':<20} {'Correct':<10} {'Accuracy':<10} {'Mean Time':<12} {'Median Time'}")
for key in sorted(problem_stats.keys()):
    stats = problem_stats[key]
    acc = stats['correct'] / stats['total'] * 100 if stats['total'] else 0
    times = stats['times']
    mean_t = sum(times) / len(times) if times else 0
    sorted_t = sorted(times)
    median_t = sorted_t[len(sorted_t)//2] if sorted_t else 0
    print(f"{key[0]:<3} {key[1]:<20} {stats['correct']}/{stats['total']:<7} {acc:>6.1f}%    {mean_t:>8.1f}s    {median_t:>8.1f}s")

# 3. Tool usage analysis
print(f"\n[3] TOOL USAGE ANALYSIS")
print("-" * 60)
tool_counts = defaultdict(int)
tool_run_ids = defaultdict(list)

for r in rows:
    if r.get('trial_type') == 'survey-multi-choice':
        resp_str = r.get('response', '')
        if 'tools_used' in resp_str:
            try:
                resp = json.loads(resp_str)
                tool = resp.get('tools_used', 'Unknown')
                tool_counts[tool] += 1
                tool_run_ids[tool].append(r['run_id'])
            except:
                pass

print("Tool Usage Distribution:")
total_tools = sum(tool_counts.values())
for tool, count in sorted(tool_counts.items(), key=lambda x: -x[1]):
    pct = count / total_tools * 100 if total_tools else 0
    print(f"  {tool}: {count} ({pct:.1f}%)")

# 4. Accuracy by tool
print(f"\n[4] ACCURACY BY TOOL")
print("-" * 60)
for tool, rids in sorted(tool_run_ids.items(), key=lambda x: -tool_counts[x[0]]):
    tool_problems = [p for p in problems if p['run_id'] in rids]
    if tool_problems:
        correct = sum(1 for p in tool_problems if p.get('is_correct') == 'true')
        acc = correct / len(tool_problems) * 100
        times = [float(p['rt'])/1000 for p in tool_problems if p.get('rt')]
        mean_t = sum(times) / len(times) if times else 0
        print(f"{tool}:")
        print(f"  Participants: {len(rids)}, Accuracy: {acc:.1f}% ({correct}/{len(tool_problems)}), Mean Time: {mean_t:.1f}s")

# 5. Experience analysis
print(f"\n[5] EXPERIENCE ANALYSIS")
print("-" * 60)
exp_data = {}
for r in rows:
    if r.get('trial_type') == 'survey-multi-choice':
        resp_str = r.get('response', '')
        if 'programming_exp' in resp_str:
            try:
                resp = json.loads(resp_str)
                run_id = r['run_id']
                exp_data[run_id] = {
                    'programming_exp': resp.get('programming_exp', 'Unknown'),
                    'solidity_exp': resp.get('solidity_exp', 'Unknown')
                }
            except:
                pass

# Programming experience vs accuracy
print("\nBy Programming Experience:")
for exp_level in ['Less than 1 year', '1-2 years', '3-5 years', 'More than 5 years']:
    rids = [rid for rid, data in exp_data.items() if data['programming_exp'] == exp_level]
    if rids:
        exp_problems = [p for p in problems if p['run_id'] in rids]
        if exp_problems:
            correct = sum(1 for p in exp_problems if p.get('is_correct') == 'true')
            acc = correct / len(exp_problems) * 100
            print(f"  {exp_level}: {len(rids)} participants, Accuracy: {acc:.1f}% ({correct}/{len(exp_problems)})")

# Solidity experience vs accuracy
print("\nBy Solidity Experience:")
for exp_level in ['None', 'Beginner (read some code)', 'Intermediate (written some contracts)', 'Advanced (deployed contracts)']:
    rids = [rid for rid, data in exp_data.items() if data['solidity_exp'] == exp_level]
    if rids:
        exp_problems = [p for p in problems if p['run_id'] in rids]
        if exp_problems:
            correct = sum(1 for p in exp_problems if p.get('is_correct') == 'true')
            acc = correct / len(exp_problems) * 100
            print(f"  {exp_level}: {len(rids)} participants, Accuracy: {acc:.1f}% ({correct}/{len(exp_problems)})")

# 6. Role distribution
print(f"\n[6] ROLE DISTRIBUTION")
print("-" * 60)
role_counts = defaultdict(int)
for rid, data in exp_data.items():
    # Need to get role from the same survey
    pass

for r in rows:
    if r.get('trial_type') == 'survey-multi-choice':
        resp_str = r.get('response', '')
        if 'role' in resp_str and 'programming_exp' in resp_str:
            try:
                resp = json.loads(resp_str)
                role = resp.get('role', 'Unknown')
                role_counts[role] += 1
            except:
                pass

for role, count in sorted(role_counts.items(), key=lambda x: -x[1]):
    print(f"  {role}: {count}")

print("\n" + "=" * 60)
print("ANALYSIS COMPLETE")
print("=" * 60)
