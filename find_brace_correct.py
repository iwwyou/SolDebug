import re

with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'r', encoding='utf-8') as f:
    lines = f.readlines()

depth = 0

for i, line in enumerate(lines, 1):
    line_start_depth = depth

    # Remove escaped braces \{ and \}
    cleaned = line.replace('\\{', '').replace('\\}', '')

    for char in cleaned:
        if char == '{':
            depth += 1
        elif char == '}':
            depth -= 1

    if i % 100 == 0:
        print(f'Line {i}: depth = {depth}')

print(f'\nFinal depth: {depth}')

if depth != 0:
    # Find problematic area
    depth = 0
    for i, line in enumerate(lines, 1):
        line_start_depth = depth
        cleaned = line.replace('\\{', '').replace('\\}', '')

        for char in cleaned:
            if char == '{':
                depth += 1
            elif char == '}':
                depth -= 1

        # Show lines where depth changes in problem area
        if abs(depth - line_start_depth) > 0 and 400 <= i <= 550:
            print(f'Line {i}: depth {line_start_depth} -> {depth}')
            print(f'  {line.strip()[:120]}')
