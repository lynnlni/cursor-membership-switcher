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
ORIGINAL_SNIPPET = "r=r??Pa.FREE,"
PATCH_MARKER     = "/*__cursor_membership_patch__*/"


def check_env():
    if sys.platform != "darwin":
        print("Error: macOS only.")
        sys.exit(1)
    if not JS_PATH.exists():
        print(f"Error: JS file not found:\n  {JS_PATH}")
        sys.exit(1)


def is_cursor_running() -> bool:
    return subprocess.run(["pgrep", "-x", "Cursor"], capture_output=True).returncode == 0


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
        content = content.replace(
            ORIGINAL_SNIPPET,
            get_patch_snippet(value) + ORIGINAL_SNIPPET,
            1
        )

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
