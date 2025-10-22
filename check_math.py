import re

with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'r', encoding='utf-8') as f:
    lines = f.readlines()

stack = []

for i, line in enumerate(lines, 1):
    # Find display math open \[ but not \\[
    # Look for \[ that is not preceded by \
    pos = 0
    while True:
        idx = line.find('\\[', pos)
        if idx == -1:
            break
        # Check if it's \\[ (linebreak with space) or \[ (display math)
        if idx > 0 and line[idx-1] == '\\':
            # This is \\[ - linebreak command, skip it
            pos = idx + 2
        else:
            # This is \[ - display math start
            stack.append(i)
            print(f'Open \\[ at line {i}')
            pos = idx + 2

    # Find display math close \]
    if '\\]' in line:
        if stack:
            opened_at = stack.pop()
            print(f'Close \\] at line {i} (matched with line {opened_at})')
        else:
            print(f'ERROR: Unmatched \\] at line {i}')

if stack:
    print(f'\n=== UNCLOSED DISPLAY MATH ===')
    for line_num in stack:
        print(f'Unclosed \\[ at line {line_num}')
        print(f'  {lines[line_num-1].strip()[:100]}')
else:
    print('\n=== All display math environments matched ===')
