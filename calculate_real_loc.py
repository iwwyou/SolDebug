#!/usr/bin/env python3
"""
paper/benchmark_table.tex에서 실제 LOC 통계 계산
"""

import re

# paper/benchmark_table.tex 읽기
with open('paper/benchmark_table.tex', 'r', encoding='utf-8') as f:
    content = f.read()

# 라인 범위 추출 (예: 537-552)
pattern = r'^(.+?\.sol)\s+&\s+\\texttt\{(.+?)\}\s+&\s+(\d+)-(\d+)\s*\\\\$'

locs = []
details = []

for line in content.split('\n'):
    match = re.match(pattern, line.strip())
    if match:
        filename = match.group(1)
        function = match.group(2)
        start_line = int(match.group(3))
        end_line = int(match.group(4))
        loc = end_line - start_line + 1

        locs.append(loc)
        details.append((filename, function, start_line, end_line, loc))
        print(f"{filename:40s} {function:35s} {start_line:4d}-{end_line:4d} = {loc:3d} LOC")

if locs:
    print("\n" + "="*90)
    print(f"Total contracts: {len(locs)}")
    print(f"Minimum LOC: {min(locs)}")
    print(f"Maximum LOC: {max(locs)}")
    print(f"Average LOC: {sum(locs)/len(locs):.1f}")
    print(f"\nSorted LOCs: {sorted(locs)}")

    print("\n" + "="*90)
    print("Min LOC contract:")
    min_loc = min(locs)
    for detail in details:
        if detail[4] == min_loc:
            print(f"  {detail[0]} - {detail[1]} ({detail[2]}-{detail[3]}) = {detail[4]} LOC")

    print("\nMax LOC contract:")
    max_loc = max(locs)
    for detail in details:
        if detail[4] == max_loc:
            print(f"  {detail[0]} - {detail[1]} ({detail[2]}-{detail[3]}) = {detail[4]} LOC")
else:
    print("No LOC values found!")
