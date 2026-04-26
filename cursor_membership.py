#!/usr/bin/env python3
"""Cursor membership type switcher — JS patch method (macOS)."""

import sys
import re
import shutil
import subprocess
from pathlib import Path
from typing import Optional

JS_PATH     = Path("/Applications/Cursor.app/Contents/Resources/app/out/vs/workbench/workbench.desktop.main.js")
BACKUP_PATH = Path.home() / ".cursor_membership_patch.bak"

MEMBERSHIP_TYPES = {
    "1": ("free",       "Free"),
    "2": ("free_trial", "Free Trial"),
    "3": ("pro",        "Pro"),
    "4": ("pro_plus",   "Pro+"),
    "5": ("ultra",      "Ultra"),
    "6": ("enterprise", "Enterprise"),
}

# The original snippet we patch inside storeMembershipType
# For Cursor 3.2.11, the original snippet is "r=r??Xl.FREE,"
ORIGINAL_SNIPPET = ["r=r??Xl.FREE,", "r=r??Pa.FREE,"]
PATCH_MARKER     = "/*__cursor_membership_patch__*/"


def check_env():
    if sys.platform != "darwin":
        print("Error: macOS only.")
        sys.exit(1)
    if not JS_PATH.exists():
        print(f"Error: JS file not found:\n  {JS_PATH}")
        sys.exit(1)


def is_cursor_running() -> bool:
    try:
        result = subprocess.run(["ps", "aux"], capture_output=True, text=True)
        for line in result.stdout.splitlines():
            if (
                "/Applications/Cursor.app/Contents/MacOS/Cursor" in line
                and "grep" not in line
            ):
                return True
        return False
    except Exception:
        return False


def read_js() -> str:
    return JS_PATH.read_text(encoding="utf-8", errors="surrogateescape")


def write_js(content: str):
    JS_PATH.write_text(content, encoding="utf-8", errors="surrogateescape")


def get_patch_snippet(value: str) -> str:
    return f'{PATCH_MARKER}r="{value}";'


def current_patch(content: str) -> Optional[str]:
    """Return the patched membership value, or None if not patched."""
    m = re.search(re.escape(PATCH_MARKER) + r'r="(\w+)";', content)
    return m.group(1) if m else None


def apply_patch(value: str):
    content = read_js()
    patched = current_patch(content)

    if patched is not None:
        # Already patched — just update the value
        content = re.sub(
            re.escape(PATCH_MARKER) + r'r="\w+";',
            get_patch_snippet(value),
            content
        )
    else:
        # First time — backup and insert patch
        if not BACKUP_PATH.exists():
            shutil.copy2(JS_PATH, BACKUP_PATH)
            print(f"  Backup saved: {BACKUP_PATH.name}")

        # Replace the original snippet with the new patch
        replace_success: bool = False
        for original_snippet in ORIGINAL_SNIPPET:
            new_content = content.replace(
                original_snippet, get_patch_snippet(value) + original_snippet, 1
            )
            if current_patch(new_content) is not None:
                replace_success = True
                break
        if not replace_success:
            print(f"Error: {'or '.join(ORIGINAL_SNIPPET).rstrip(',')} not found. Patch failed.")
            print("Possible causes:")
            print(" - Cursor has been updated and the snippet or the file path changed")
            print(" - Please contact the author for updates")
            sys.exit(1)
        content = new_content

    write_js(content)


def remove_patch():
    if not BACKUP_PATH.exists():
        print("  No backup found, cannot restore.")
        return False
    shutil.copy2(BACKUP_PATH, JS_PATH)
    print(f"  Restored from backup.")
    return True


def print_menu(patched_value: Optional[str]):
    status = f'patched → "{patched_value}"' if patched_value else "not patched (original)"
    print("\n" + "=" * 46)
    print("  Cursor Membership Switcher (macOS)")
    print("=" * 46)
    print(f"  JS patch : {status}")
    print("-" * 46)
    for key, (value, label) in MEMBERSHIP_TYPES.items():
        marker = " <" if value == patched_value else ""
        print(f"  [{key}] {label:<12} ({value}){marker}")
    print("  [r] Restore original (remove patch)")
    print("  [q] Quit")
    print("-" * 46)


def main():
    check_env()

    if is_cursor_running():
        print("Warning: Cursor is currently running.")
        print("Quit Cursor first, then re-run this tool for changes to take effect.")
        print()

    while True:
        content = read_js()
        patched = current_patch(content)
        print_menu(patched)

        choice = input("  Select: ").strip().lower()

        if choice == "q":
            print("Bye.")
            break

        if choice == "r":
            if remove_patch():
                print("  Patch removed. Restart Cursor to apply.")
            continue

        if choice not in MEMBERSHIP_TYPES:
            print("  Invalid choice.")
            continue

        value, label = MEMBERSHIP_TYPES[choice]
        apply_patch(value)
        print(f'\n  Patched: storeMembershipType will always use "{value}"')
        print("  Restart Cursor to apply.")


if __name__ == "__main__":
    main()
