import re

with open('main.tex', 'r', encoding='utf-8') as f:
    content = f.read()

# Define figure movements: (label, text_pattern_to_find_after)
movements = [
    ('fig:new-else-if', r'Figure~\ref\{fig:new-else-if\}[^\n]+\n(?:[^\n]+\n)*?(?=\n\begin\{figure\})'),
    ('fig:new-else', r'Figure~\ref\{fig:new-else\}[^\n]+\n(?:[^\n]+\n)*?(?=\n\begin\{figure\})'),
    ('fig:new-while', r'Figure~\ref\{fig:new-while\}[^\n]+\n(?:[^\n]+\n)*?(?=\n\begin\{figure\})'),
    ('fig:new-break', r'Figure~\ref\{fig:new-break\}[^\n]+\n(?:[^\n]+\n)*?(?=\n\begin\{figure\})'),
    ('fig:new-continue', r'Figure~\ref\{fig:new-continue\}[^\n]+\n(?:[^\n]+\n)*?(?=\n\begin\{figure\})'),
    ('fig:new-return', r'Figure~\ref\{fig:new-return\}[^\n]+\n(?:[^\n]+\n)*?(?=\n\begin\{figure\})'),
    ('fig:new-require', r'Figure~\ref\{fig:new-require\}[^\n]+\n(?:[^\n]+\n)*?(?=\n\begin\{figure\})'),
]

# Extract all figures into a dict
figures = {}
figure_pattern = r'\begin\{figure\}\[!ht\]\n(.*?)\label\{([^}]+)\}\n\end\{figure\}\n'
for match in re.finditer(figure_pattern, content, re.DOTALL):
    label = match.group(2)
    figures[label] = match.group(0)

print(f"Extracted {len(figures)} figures")

# Remove all figure blocks first
for label, fig_block in figures.items():
    if label.startswith('fig:new-'):
        content = content.replace(fig_block, '', 1)
        print(f"Removed {label}")

# Now insert each figure after its corresponding text
for label, text_pattern in movements:
    if label in figures:
        fig_block = figures[label]
        # Find the text description
        text_match = re.search(text_pattern, content, re.DOTALL)
        if text_match:
            # Insert figure after the text description
            insert_pos = text_match.end()
            content = content[:insert_pos] + '\n' + fig_block + content[insert_pos:]
            print(f"Inserted {label} after its description")
        else:
            print(f"WARNING: Could not find text for {label}")

with open('main.tex', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")
