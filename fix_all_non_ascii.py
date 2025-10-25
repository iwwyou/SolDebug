import sys

# Read the file
with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'r', encoding='utf-8') as f:
    content = f.read()

# Count before
counts_before = {
    'Section symbol': content.count('\u00A7'),
    'Registered': content.count('\u00AE'),
    'Trademark': content.count('\u2122'),
    'Non-breaking hyphen': content.count('\u2011'),
    'Curly apostrophe': content.count('\u2019'),
    'Left curly quote': content.count('\u201C'),
    'Right curly quote': content.count('\u201D'),
    'Korean characters': sum(1 for c in content if ord(c) >= 0xAC00 and ord(c) <= 0xD7A3),
}

print("Before replacement:")
for name, count in counts_before.items():
    if count > 0:
        print(f"  {name}: {count}")

# Perform replacements
replacements = [
    ('\u00A7', r'\S{}'),              # section symbol
    ('\u00AE', r'\textregistered{}'), # registered
    ('\u2122', r'\texttrademark{}'),  # trademark
    ('\u2011', '-'),                  # non-breaking hyphen to regular hyphen
    ('\u2019', "'"),                  # curly apostrophe to straight
    ('\u201C', '"'),                  # left curly quote to straight
    ('\u201D', '"'),                  # right curly quote to straight
]

for old, new in replacements:
    content = content.replace(old, new)

# Remove Korean comment lines
lines = content.split('\n')
new_lines = []

for i, line in enumerate(lines, 1):
    # Check if line contains Korean characters
    has_korean = any(ord(c) >= 0xAC00 and ord(c) <= 0xD7A3 for c in line)

    if has_korean and line.strip().startswith('%'):
        # Skip Korean comment lines
        continue
    else:
        new_lines.append(line)

content = '\n'.join(new_lines)

# Write back
with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'w', encoding='utf-8') as f:
    f.write(content)

print("\nReplacement complete!")
print("Replacements:")
print("  section symbol -> \\S{}")
print("  registered -> \\textregistered{}")
print("  trademark -> \\texttrademark{}")
print("  non-breaking hyphen -> regular hyphen")
print("  curly quotes -> straight quotes")
print("  Korean comment lines removed")
print("\nFile saved: paper/main.tex")
