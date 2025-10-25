import sys

# Read the file
with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'r', encoding='utf-8') as f:
    content = f.read()

# Count occurrences before replacement
em_dash_count = content.count('\u2014')
en_dash_count = content.count('\u2013')
ellipsis_count = content.count('\u2026')

print(f"Before replacement:")
print(f"  em dash: {em_dash_count}")
print(f"  en dash: {en_dash_count}")
print(f"  ellipsis: {ellipsis_count}")

# Replace non-ASCII characters with LaTeX equivalents
content = content.replace('\u2014', '---')  # em dash
content = content.replace('\u2013', '--')   # en dash
content = content.replace('\u2026', r'\ldots')  # ellipsis

# Write back
with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'w', encoding='utf-8') as f:
    f.write(content)

print(f"\nReplacement complete!")
print(f"  em dash (U+2014) -> ---")
print(f"  en dash (U+2013) -> --")
print(f"  ellipsis (U+2026) -> \\ldots")
print(f"File saved: paper/main.tex")
