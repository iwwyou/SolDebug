with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'r', encoding='utf-8') as f:
    lines = f.readlines()

depth = 0
max_depth = 0
max_depth_line = 0

for i, line in enumerate(lines, 1):
    for char in line:
        if char == '{':
            depth += 1
            if depth > max_depth:
                max_depth = depth
                max_depth_line = i
        elif char == '}':
            depth -= 1

    # Print lines where depth doesn't return to what it was
    if i % 100 == 0:
        print(f'Line {i}: depth = {depth}')

print(f'\nFinal depth: {depth}')
print(f'Max depth: {max_depth} at line {max_depth_line}')

if depth > 0:
    print(f'\n{depth} unclosed {{ remaining')
    # Find where the unclosed brace might be
    depth_tracker = 0
    for i, line in enumerate(lines, 1):
        line_start_depth = depth_tracker
        for char in line:
            if char == '{':
                depth_tracker += 1
            elif char == '}':
                depth_tracker -= 1

        # If depth increased and never fully decreased again, this might be the problem line
        if depth_tracker > line_start_depth and i > len(lines) - 100:
            print(f'Suspect line {i}: depth {line_start_depth} -> {depth_tracker}')
            print(f'  {line.strip()[:120]}')
elif depth < 0:
    print(f'\n{-depth} extra }} found')
