with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'r', encoding='utf-8') as f:
    lines = f.readlines()

in_math_mode = False
math_start_line = 0

for i, line in enumerate(lines, 1):
    # Skip comments
    if '%' in line:
        comment_pos = line.find('%')
        # Check if % is escaped
        if comment_pos == 0 or line[comment_pos-1] != '\\':
            line = line[:comment_pos]

    # Count $ signs (not \$)
    j = 0
    while j < len(line):
        if line[j] == '$' and (j == 0 or line[j-1] != '\\'):
            if not in_math_mode:
                in_math_mode = True
                math_start_line = i
                print(f'Math mode ON at line {i}')
            else:
                in_math_mode = False
                print(f'Math mode OFF at line {i} (started at {math_start_line})')
        j += 1

if in_math_mode:
    print(f'\n=== UNCLOSED MATH MODE ===')
    print(f'Math mode started at line {math_start_line} but never closed!')
    print(f'  {lines[math_start_line-1].strip()[:100]}')
else:
    print('\n=== All $ math modes matched ===')
