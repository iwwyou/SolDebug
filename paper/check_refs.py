import re

# Read the main.tex file
with open(r'C:\Users\isjeon\PycharmProjects\pythonProject\SolDebug\paper\main.tex', 'r', encoding='utf-8') as f:
    content = f.read()

# Find all cite commands
cites = re.findall(r'\\cite[pt]?\{([^}]+)\}', content)
cite_keys = set()
for cite in cites:
    cite_keys.update(c.strip() for c in cite.split(','))

# Find all bibitem keys
bibitems = re.findall(r'\\bibitem\[[^\]]+\]\{([^}]+)\}', content)
bibitem_keys = set(bibitems)

# Find missing bibitems
missing_bibitems = cite_keys - bibitem_keys

print("=" * 80)
print("CITE/BIBITEM ANALYSIS")
print("=" * 80)
print(f"\nTotal cited keys: {len(cite_keys)}")
print(f"Total bibitem keys: {len(bibitem_keys)}")
print(f"\nMissing bibitems ({len(missing_bibitems)}):")
for key in sorted(missing_bibitems):
    print(f"  - {key}")

# Find all labels
labels = re.findall(r'\\label\{([^}]+)\}', content)
label_keys = set(labels)

# Find all refs
refs = re.findall(r'\\ref\{([^}]+)\}', content)
ref_keys = set(refs)

# Find missing labels
missing_labels = ref_keys - label_keys

print("\n" + "=" * 80)
print("LABEL/REF ANALYSIS")
print("=" * 80)
print(f"\nTotal labels: {len(label_keys)}")
print(f"Total refs: {len(ref_keys)}")
print(f"\nMissing labels ({len(missing_labels)}):")
for key in sorted(missing_labels):
    print(f"  - {key}")

# Show all cited keys for reference
print("\n" + "=" * 80)
print("ALL CITED KEYS")
print("=" * 80)
for key in sorted(cite_keys):
    if key in bibitem_keys:
        print(f"  OK {key}")
    else:
        print(f"  MISSING {key}")
