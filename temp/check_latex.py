with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Count dollar signs per line
print("Lines with odd $ count:")
for i, line in enumerate(lines, 1):
    # Skip comments
    comment_pos = line.find('%')
    if comment_pos >= 0:
        line = line[:comment_pos]

    # Count dollar signs
    dollar_count = line.count('$')

    if dollar_count % 2 == 1:
        print(f'Line {i}: {dollar_count} dollar signs')
        print(f'  {line.strip()[:100]}')

# Count all $ signs in the file
with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'r', encoding='utf-8') as f:
    content = f.read()
    total_dollars = content.count('$')
    print(f'\nTotal $ signs in file: {total_dollars}')
