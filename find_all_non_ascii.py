import sys

with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'r', encoding='utf-8') as f:
    content = f.read()
    lines = content.split('\n')

# Find all non-ASCII characters
non_ascii_chars = {}
for line_num, line in enumerate(lines, 1):
    for char_pos, char in enumerate(line):
        if ord(char) > 127:  # non-ASCII
            char_info = f"U+{ord(char):04X} ({char})"
            if char_info not in non_ascii_chars:
                non_ascii_chars[char_info] = []
            non_ascii_chars[char_info].append((line_num, char_pos, line))

# Write results
with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\all_non_ascii.txt', 'w', encoding='utf-8') as out:
    out.write("All Non-ASCII Characters Found:\n")
    out.write("=" * 80 + "\n\n")

    for char_info in sorted(non_ascii_chars.keys()):
        occurrences = non_ascii_chars[char_info]
        out.write(f"\n{char_info}: {len(occurrences)} occurrences\n")
        out.write("-" * 80 + "\n")
        for line_num, char_pos, line in occurrences[:10]:  # Show first 10
            out.write(f"Line {line_num}, pos {char_pos}: {line.strip()}\n")
        if len(occurrences) > 10:
            out.write(f"... and {len(occurrences) - 10} more\n")

    out.write(f"\n\nTotal unique non-ASCII characters: {len(non_ascii_chars)}\n")
    out.write(f"Total occurrences: {sum(len(v) for v in non_ascii_chars.values())}\n")

print(f"Found {len(non_ascii_chars)} unique non-ASCII character types")
print(f"Total occurrences: {sum(len(v) for v in non_ascii_chars.values())}")
print("Results written to: all_non_ascii.txt")
