"""
Change internal/private visibility to public for all functions and state variables
This makes everything debuggable in Remix IDE
"""
import re
import sys
import io
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


def change_visibility_to_public(sol_content):
    """
    Change internal and private to public
    """
    modified = sol_content

    # Change 'internal' to 'public' for functions and variables
    modified = re.sub(r'\binternal\b', 'public', modified)

    # Change 'private' to 'public' for functions and variables
    modified = re.sub(r'\bprivate\b', 'public', modified)

    return modified


def process_solidity_file(sol_file):
    """Process a single Solidity file to change visibility"""
    print(f"\n{'='*70}")
    print(f"Processing: {sol_file.name}")
    print(f"{'='*70}")

    with open(sol_file, 'r', encoding='utf-8') as f:
        original_content = f.read()

    # Check if file has internal or private
    has_internal = 'internal' in original_content
    has_private = 'private' in original_content

    if not has_internal and not has_private:
        print("  -> No internal/private visibility found, skipping")
        return False

    print(f"  -> Found: internal={has_internal}, private={has_private}")

    # Change visibility to public
    modified_content = change_visibility_to_public(original_content)

    # Write back to file
    with open(sol_file, 'w', encoding='utf-8') as f:
        f.write(modified_content)

    print(f"  [OK] Changed visibility to public")
    return True


def main():
    remix_dir = Path('contraction_remix')

    if not remix_dir.exists():
        print(f"ERROR: Directory {remix_dir} does not exist")
        return

    print("="*70)
    print("CHANGING VISIBILITY TO PUBLIC IN SOLIDITY CONTRACTS")
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
