import re

print("Reading main.tex...")
with open('main.tex', 'r', encoding='utf-8') as f:
    content = f.read()

# Extract all fig:new-* figures
print("Extracting figures...")
figures = {}
pattern = r'(\\begin\{figure\}\[!ht\].*?\\label\{(fig:new-[^}]+)\}.*?\\end\{figure\}\n)'

for match in re.finditer(pattern, content, re.DOTALL):
    fig_block = match.group(1)
    label = match.group(2)
    figures[label] = fig_block
    print(f"  Found {label}")

# Remove all fig:new-* figures from content
print("\nRemoving figures from original positions...")
for label, fig_block in figures.items():
    content = content.replace(fig_block, '', 1)
    print(f"  Removed {label}")

# Define text patterns for each figure
patterns = {
    'fig:new-simple-statement': r'(Figure~\\ref\{fig:new-simple-statement\}.*?(?=\n\nFigure~|$))',
    'fig:new-if': r'(Figure~\\ref\{fig:new-if\}.*?(?=\n\n\\begin\{figure\}|$))',
    'fig:new-else-if': r'(Figure~\\ref\{fig:new-else-if\}.*?(?=\n\n\\begin\{figure\}|$))',
    'fig:new-else': r'(Figure~\\ref\{fig:new-else\}.*?(?=\n\n\\begin\{figure\}|$))',
    'fig:new-while': r'(Figure~\\ref\{fig:new-while\}.*?(?=\n\n\\begin\{figure\}|$))',
    'fig:new-break': r'(Figure~\\ref\{fig:new-break\}.*?(?=\n\n\\begin\{figure\}|$))',
    'fig:new-continue': r'(Figure~\\ref\{fig:new-continue\}.*?(?=\n\n\\begin\{figure\}|$))',
    'fig:new-return': r'(Figure~\\ref\{fig:new-return\}.*?(?=\n\n\\begin\{figure\}|$))',
    'fig:new-require': r'(Figure~\\ref\{fig:new-require\}.*?(?=\n\n\\subsection|$))',
}

# Insert figures after their text descriptions
print("\nInserting figures after text descriptions...")
for label, text_pattern in patterns.items():
    if label in figures:
        matches = list(re.finditer(text_pattern, content, re.DOTALL))
        if matches:
            match = matches[0]
            insert_pos = match.end()
            content = content[:insert_pos] + '\n\n' + figures[label] + content[insert_pos:]
            print(f"  Inserted {label}")
        else:
            print(f"  WARNING: Could not find text for {label}")

print("\nWriting updated main.tex...")
with open('main.tex', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")
