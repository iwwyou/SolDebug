import sys

with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'r', encoding='utf-8') as f:
    lines = f.readlines()

# Write results to a file
with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\non_ascii_lines.txt', 'w', encoding='utf-8') as out:
    out.write("Lines with em dash (U+2014) or en dash (U+2013) or ellipsis (U+2026):\n")
    out.write("=" * 80 + "\n")
    count = 0
    for i, line in enumerate(lines, 1):
        if '\u2014' in line or '\u2013' in line or '\u2026' in line:
            count += 1
            out.write(f"Line {i}: {line}")

    out.write(f"\nTotal lines with non-ASCII characters: {count}\n")

print(f"Found {count} lines with non-ASCII dashes/ellipsis")
print("Results written to: non_ascii_lines.txt")
