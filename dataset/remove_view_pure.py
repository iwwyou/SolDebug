"""
Remove view/pure modifiers from all Solidity contracts in contraction_remix folder
Keeps functions as public but removes view/pure to enable transaction debugging
"""
import re
import sys
import io
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def remove_view_pure_modifiers(sol_content):
    """
    Remove view and pure modifiers from function definitions
    """
    modified = sol_content

    # Remove 'view' modifier with surrounding whitespace
    modified = re.sub(r'\s+view\s+', ' ', modified)
    modified = re.sub(r'\s+view\b', '', modified)

    # Remove 'pure' modifier with surrounding whitespace
    modified = re.sub(r'\s+pure\s+', ' ', modified)
    modified = re.sub(r'\s+pure\b', '', modified)

    return modified


def process_solidity_file(sol_file):
    """Process a single Solidity file to remove view/pure"""
    print(f"\n{'='*70}")
    print(f"Processing: {sol_file.name}")
    print(f"{'='*70}")

    with open(sol_file, 'r', encoding='utf-8') as f:
        original_content = f.read()

    # Check if file has view or pure
    has_view = 'view' in original_content
    has_pure = 'pure' in original_content

    if not has_view and not has_pure:
        print("  → No view/pure modifiers found, skipping")
        return False

    print(f"  → Found: view={has_view}, pure={has_pure}")

    # Remove view/pure modifiers
    modified_content = remove_view_pure_modifiers(original_content)

    # Write back to file
    with open(sol_file, 'w', encoding='utf-8') as f:
        f.write(modified_content)

    print(f"  [OK] Removed view/pure modifiers")
    return True


def main():
    remix_dir = Path('contraction_remix')

    if not remix_dir.exists():
        print(f"ERROR: Directory {remix_dir} does not exist")
        return

    print("="*70)
    print("REMOVING VIEW/PURE MODIFIERS FROM SOLIDITY CONTRACTS")
    print("="*70)

    sol_files = list(remix_dir.glob('*.sol'))
    print(f"\nFound {len(sol_files)} Solidity files")

    modified_count = 0

    for sol_file in sorted(sol_files):
        try:
            if process_solidity_file(sol_file):
                modified_count += 1
        except Exception as e:
            print(f"  ERROR: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*70)
    print(f"SUMMARY: Modified {modified_count} / {len(sol_files)} contracts")
    print("="*70)


if __name__ == "__main__":
    main()
