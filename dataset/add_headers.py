"""
Add SPDX-License-Identifier and pragma solidity headers to all contracts
"""
import sys
import io
from pathlib import Path

# Fix Windows encoding
if sys.platform == 'win32':
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')


HEADER = """// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.0;

"""


def add_header_to_file(sol_file):
    """Add SPDX and pragma headers if not present"""
    print(f"\n{'='*70}")
    print(f"Processing: {sol_file.name}")
    print(f"{'='*70}")

    with open(sol_file, 'r', encoding='utf-8') as f:
        content = f.read()

    # Check if header already exists
    has_spdx = 'SPDX-License-Identifier' in content
    has_pragma = 'pragma solidity' in content

    if has_spdx and has_pragma:
        print("  -> Header already exists, skipping")
        return False

    print(f"  -> Adding header (SPDX={not has_spdx}, pragma={not has_pragma})")

    # Add header to the beginning
    new_content = HEADER + content

    # Write back to file
    with open(sol_file, 'w', encoding='utf-8') as f:
        f.write(new_content)

    print(f"  [OK] Header added")
    return True


def main():
    remix_dir = Path('contraction_remix')

    if not remix_dir.exists():
        print(f"ERROR: Directory {remix_dir} does not exist")
        return

    print("="*70)
    print("ADDING HEADERS TO SOLIDITY CONTRACTS")
    print("="*70)

    sol_files = list(remix_dir.glob('*.sol'))
    print(f"\nFound {len(sol_files)} Solidity files")

    modified_count = 0

    for sol_file in sorted(sol_files):
        try:
            if add_header_to_file(sol_file):
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
