import re

print("Reading main.tex...")
with open('main.tex', 'r', encoding='utf-8') as f:
    content = f.read()

text_ends = {
    'fig:new-simple-statement': 'splitting multi-statement blocks.',
    'fig:new-if': 'refined by the truth value of the guard.',
    'fig:new-else-if': 'remains a single diamond toward the if join.',
    'fig:new-else': 'according to standard block matching.',
    'fig:new-while': 'for widening/narrowing.',
    'fig:new-break': 'the environment at the break site.',
    'fig:new-continue': "the loop's join state.",
    'fig:new-return': 'the original successors of the current node are detached.',
    'fig:new-require': 'reconnects to the original successors.',
}

print("Extracting figures...")
figures = {}
pattern = r'(\begin\{figure\}\[!ht\].*?\label\{(fig:new-[^}]+)\}.*?\end\{figure\}\n)'

for match in re.finditer(pattern, content, re.DOTALL):
    fig_block = match.group(1)
    label = match.group(2)
    figures[label] = fig_block
    print(f"  Found {label}")

print("\nRemoving figures...")
for label, fig_block in figures.items():
    content = content.replace(fig_block, '', 1)
    print(f"  Removed {label}")

print("\nInserting figures after text...")
for label, end_text in text_ends.items():
    if label in figures:
        pos = content.find(end_text)
        if pos != -1:
            insert_pos = pos + len(end_text)
            content = content[:insert_pos] + '\n\n' + figures[label] + content[insert_pos:]
            print(f"  Inserted {label}")
        else:
            print(f"  WARNING: Could not find end text for {label}")

print("\nWriting main.tex...")
with open('main.tex', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done!")
