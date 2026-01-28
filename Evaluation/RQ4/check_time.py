import csv

with open('solqdebug-experiment.csv', 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

# run_id 1의 데이터만 보기
print("=== run_id 1 의 trial 순서 ===\n")
print(f"{'trial_idx':<10} {'trial_type':<25} {'rt (ms)':<15} {'time_elapsed (ms)':<20} {'task/name'}")
print("-" * 100)

run1 = [r for r in rows if r['run_id'] == '1']
for r in run1:
    trial_idx = r.get('trial_index', '')
    trial_type = r.get('trial_type', '')
    rt = r.get('rt', '')
    time_elapsed = r.get('time_elapsed', '')
    task = r.get('task', '')
    name = r.get('problem_name', '')

    print(f"{trial_idx:<10} {trial_type:<25} {rt:<15} {time_elapsed:<20} {task} {name}")
