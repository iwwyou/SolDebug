#!/usr/bin/env python3
"""
benchmark_table.tex에서 LOC 통계를 정확히 계산
"""

import re

# benchmark_table.tex 읽기
with open('benchmark_table.tex', 'r', encoding='utf-8') as f:
    content = f.read()

# LOC 값 추출 (각 줄의 마지막 숫자)
# 패턴: ID & Contract & Source & Function & LOC \\
pattern = r'^\d+\s+&.*?&.*?&.*?&\s*(\d+)\s*\\\\$'

locs = []
for line in content.split('\n'):
    match = re.match(pattern, line.strip())
    if match:
        loc = int(match.group(1))
        locs.append(loc)
        print(f"Found LOC: {loc}")

if locs:
    print("\n" + "="*50)
    print(f"Total contracts: {len(locs)}")
    print(f"Minimum LOC: {min(locs)}")
    print(f"Maximum LOC: {max(locs)}")
    print(f"Average LOC: {sum(locs)/len(locs):.1f}")
    print(f"All LOCs: {sorted(locs)}")
else:
    print("No LOC values found!")
