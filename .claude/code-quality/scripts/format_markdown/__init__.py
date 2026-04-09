"""Format markdown files according to the project's markdown guidelines.

Rules enforced:
  1. Replace smart/curly quotes with ASCII equivalents.
  2. Wrap lines longer than 120 characters (exceptions: table rows, URLs).
  3. Ensure every heading is followed by exactly one blank line.
  4. Ensure every list is preceded by exactly one blank line.
  5. Ensure every list is followed by at least one blank line.

Usage:
    python -m format_markdown [paths...]

    If no paths are given, all *.md files in the repo are processed
    (excluding sandbox/ and tmp/ and .git/).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Ensure sibling modules are importable regardless of how this package is invoked
# (e.g. via ``python -m format_markdown`` or direct sys.path manipulation in tests).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from fix_heading_and_list_spacing import FixHeadingAndListSpacing
from replace_with_ascii import ReplaceWithAscii
from wrap_long_lines import WrapLongLines

REPO_ROOT = Path(__file__).resolve().parent.parent.parent.parent.parent

EXCLUDE_PATTERNS = [
    "sandbox/",
    "tmp/",
    ".git/"
]

RULES = [
    ReplaceWithAscii(),
    WrapLongLines(),
    FixHeadingAndListSpacing(),
]


def _is_excluded(relative_path: str) -> bool:
    """Check if a relative path matches any exclusion pattern."""
    parts = Path(relative_path).parts
    return any(
        part.rstrip("/") in parts
        for part in EXCLUDE_PATTERNS
    )


def find_markdown_files(root: Path) -> list[Path]:
    """Find all markdown files in the repo, excluding EXCLUDE_PATTERNS and special files."""
    files = []
    for path in sorted(root.rglob("*.md")):
        relative_path = path.relative_to(root).as_posix()
        if not _is_excluded(relative_path):
            files.append(path)
    return files


def format_content(text: str) -> str:
    """Apply all formatting rules to markdown content."""
    for rule in RULES:
        text = rule.apply(text)

    # Ensure file ends with exactly one newline
    lines = text.splitlines()
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines) + "\n"


def process_file(path: Path, is_dry_run: bool = False) -> bool:
    """Returns True if the file needed changes."""
    try:
        original = path.read_text(encoding="utf-8")
        formatted = format_content(original)

        if formatted == original:
            return False

        if is_dry_run:
            print(f"  WOULD FIX: {path}")
        else:
            path.write_text(formatted, encoding="utf-8")
            print(f"  FIXED: {path}")
        return True
    except Exception as exc:  # pylint: disable=broad-exception-caught
        # Per-file safety net: a failure on one file must not abort the batch.
        print(f"  WARNING: Could not process {path}: {exc}", file=sys.stderr)
        return False


def _collect_files(path_args: list[str]) -> list[Path]:
    """Collect markdown files from explicit paths, or all repo files if none given."""
    if not path_args:
        return find_markdown_files(REPO_ROOT)

    files = []
    for path_arg in path_args:
        path = Path(path_arg)
        if path.is_file():
            files.append(path.resolve())
        elif path.is_dir():
            files.extend(find_markdown_files(path))
    return files


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Format markdown files according to project guidelines."
    )
    parser.add_argument(
        "paths",
        nargs="*",
        help="Specific files or directories to process. Defaults to all repo markdown files.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be changed without modifying files.",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with code 1 if any files need formatting (for CI).",
    )
    return parser.parse_args()


def main() -> None:
    args = _parse_args()
    files = _collect_files(args.paths)

    if not files:
        print("No markdown files found.")
        return

    is_dry_run = args.dry_run or args.check
    changed_count = 0

    print(f"Processing {len(files)} markdown file(s)...\n")
    for file_path in files:
        if process_file(file_path, is_dry_run=is_dry_run):
            changed_count += 1

    print(f"\n{'Would fix' if is_dry_run else 'Fixed'}: {changed_count} file(s)")

    if args.check and changed_count > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
