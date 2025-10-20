"""
Remove all auto-generated setter functions from contracts
"""
import re
from pathlib import Path


def remove_auto_generated_setters(sol_file):
    """Remove all auto-generated setters from a .sol file"""
    print(f"\nProcessing: {sol_file.name}")

    with open(sol_file, 'r', encoding='utf-8') as f:
        content = f.read()

    original_content = content

    # Pattern to match auto-generated setter functions
    # Matches from "// Auto-generated setter" comment to the end of the function
    # More robust pattern that handles multiline functions
    pattern = r'// Auto-generated setter[^\n]*\n\s*function\s+\w+[^{]*\{[^}]*\}'

    content = re.sub(pattern, '', content, flags=re.DOTALL)

    if content != original_content:
        with open(sol_file, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  [OK] Removed auto-generated setters")
        return True
    else:
        print(f"  [SKIP] No auto-generated setters found")
        return False


def main():
    remix_dir = Path(__file__).parent

    print("="*70)
    print("REMOVING AUTO-GENERATED SETTERS")
    print("="*70)

    sol_files = list(remix_dir.glob('*_c.sol'))
    print(f"\nFound {len(sol_files)} contract files")

    modified_count = 0

    for sol_file in sorted(sol_files):
        try:
            if remove_auto_generated_setters(sol_file):
                modified_count += 1
        except Exception as e:
            print(f"  ERROR: {e}")

    print("\n" + "="*70)
    print(f"SUMMARY: Modified {modified_count} / {len(sol_files)} contracts")
    print("="*70)


if __name__ == "__main__":
    main()
