"""
Fix AP-04: Remove incorrect '=' prefix from jsonBody values in deploy scripts.

In n8n v4.2+ httpRequest nodes with specifyBody: "json", the jsonBody should be
a plain JSON string. The '=' prefix is unnecessary and incorrect when followed
by a literal JSON object '{'.

This script fixes:
  "jsonBody": "={..."  ->  "jsonBody": "{..."
  "jsonBody": triple_quote={...  ->  "jsonBody": triple_quote{...

It does NOT touch:
  "jsonBody": "={{ ... }}"  (n8n expressions that need the '=' prefix)

Usage:
  python tools/fix_jsonbody_prefix.py          # Dry run (preview changes)
  python tools/fix_jsonbody_prefix.py --apply  # Apply changes with backups
"""

import os
import re
import sys
import shutil
import glob


def main():
    apply_mode = "--apply" in sys.argv

    # Paths
    base_dir = os.path.dirname(os.path.abspath(__file__))
    project_root = os.path.dirname(base_dir)
    tools_dir = os.path.join(project_root, "tools")
    backup_dir = os.path.join(project_root, ".tmp", "backups", "ap04_fix")

    # Find all deploy_*.py files
    pattern = os.path.join(tools_dir, "deploy_*.py")
    deploy_files = sorted(glob.glob(pattern))

    print(f"Scanning {len(deploy_files)} deploy scripts...")
    print(f"Mode: {'APPLY' if apply_mode else 'DRY RUN'}")
    print()

    # Two regex patterns:
    # 1. Double-quote: "jsonBody": "={  but NOT "jsonBody": "={{
    # 2. Triple-quote: "jsonBody": """={  (no """={{ exists, but safe anyway)
    #
    # We use a negative lookahead to skip ={{ patterns.
    regex_double = re.compile(r'("jsonBody":\s*")(=)(\{(?!\{))')
    regex_triple = re.compile(r'("jsonBody":\s*""")( *=)(\{(?!\{))')

    total_fixes = 0
    files_changed = 0
    file_summary = []

    for filepath in deploy_files:
        filename = os.path.basename(filepath)

        with open(filepath, "r", encoding="utf-8") as f:
            original = f.read()

        content = original
        fix_count = 0

        # Apply double-quote fix
        new_content, n = regex_double.subn(r'\1\3', content)
        fix_count += n
        content = new_content

        # Apply triple-quote fix
        new_content, n = regex_triple.subn(r'\1\3', content)
        fix_count += n
        content = new_content

        if fix_count > 0:
            files_changed += 1
            total_fixes += fix_count
            file_summary.append((filename, fix_count))

            print(f"  {filename}: {fix_count} fix(es)")

            if apply_mode:
                # Create backup
                os.makedirs(backup_dir, exist_ok=True)
                backup_path = os.path.join(backup_dir, filename)
                shutil.copy2(filepath, backup_path)

                # Write fixed content
                with open(filepath, "w", encoding="utf-8") as f:
                    f.write(content)

    print()
    print("=" * 50)
    print(f"Files scanned:  {len(deploy_files)}")
    print(f"Files changed:  {files_changed}")
    print(f"Total fixes:    {total_fixes}")

    if apply_mode and files_changed > 0:
        print(f"Backups saved:  {backup_dir}")
    elif not apply_mode and total_fixes > 0:
        print()
        print("Run with --apply to apply changes:")
        print("  python tools/fix_jsonbody_prefix.py --apply")

    return total_fixes


if __name__ == "__main__":
    main()
