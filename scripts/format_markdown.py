"""Format markdown files according to the project's markdown guidelines.

Rules enforced:
  1. Replace smart/curly quotes with ASCII equivalents.
  2. Wrap lines longer than 120 characters (exceptions: table rows, URLs).
  3. Ensure every heading is followed by exactly one blank line.
  4. Ensure every list is preceded by exactly one blank line.
  5. Ensure every list is followed by at least one blank line.

Usage:
    python scripts/format_markdown.py [paths...]

    If no paths are given, all *.md files in the repo are processed
    (excluding sandbox/ and tmp/ and .git/).
"""

from __future__ import annotations

import argparse
import re
import sys
import textwrap
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

SMART_QUOTES = {
    # left single curly quote
    "\u2018": "'",
    # right single curly quote
    "\u2019": "'",
    # left double curly quote
    "\u201C": '"',
    # right double curly quote
    "\u201D": '"',
}

MAX_LINE_LENGTH = 120
CODE_FENCE_PATTERN = r"^\s*(`{3,}|~{3,})"


EXCLUDE_PATTERNS = [
    "sandbox/",
    "tmp/",
    ".git/"
]


def _is_excluded(relative_path: str) -> bool:
    """Check if a relative path matches any exclusion pattern."""
    prefixed = f"/{relative_path}"
    return any(f"/{pattern}" in prefixed for pattern in EXCLUDE_PATTERNS)


def find_markdown_files(root: Path) -> list[Path]:
    """Find all markdown files in the repo, excluding EXCLUDE_PATTERNS and special files."""
    files = []
    for path in sorted(root.rglob("*.md")):
        relative_path = path.relative_to(root).as_posix()
        if not _is_excluded(relative_path):
            files.append(path)
    return files


_SMART_QUOTE_TABLE = str.maketrans(SMART_QUOTES)


def fix_smart_quotes(text: str) -> str:
    """Rule 1: Replace smart/curly quotes with ASCII equivalents."""
    return text.translate(_SMART_QUOTE_TABLE)


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|")


def _is_url_line(line: str) -> bool:
    """True if the line is long only because it contains a URL."""
    urls = re.findall(r"https?://\S+", line)
    if not urls:
        return False
    # If removing the longest URL brings the line under the limit, it's a URL line.
    longest_url = max(urls, key=len)
    without_url = line.replace(longest_url, "", 1)
    return len(without_url) <= MAX_LINE_LENGTH


def _detect_indent(line: str) -> str:
    """Return the leading whitespace of a line."""
    return re.match(r"^(\s*)", line).group(1)


def _is_list_item_start(line: str) -> bool:
    """True if this line starts a list item (numbered or bulleted)."""
    return bool(re.match(r"^\s*[-*+] ", line) or re.match(r"^\s*\d+[.)]\s", line))


def _list_continuation_indent(line: str) -> str:
    """Return the indent for continuation lines of a list item."""
    match = re.match(r"^(\s*[-*+] )", line) or re.match(r"^(\s*\d+[.)]\s)", line)
    if match:
        return " " * len(match.group(1))
    return _detect_indent(line)


def wrap_long_lines(lines: list[str]) -> list[str]:
    """Rule 2: Wrap lines exceeding 120 characters."""
    result = []
    in_code_fence = False
    for line in lines:
        if re.match(CODE_FENCE_PATTERN, line):
            in_code_fence = not in_code_fence
            result.append(line)
            continue

        if in_code_fence or len(line) <= MAX_LINE_LENGTH:
            result.append(line)
            continue

        # Exceptions: table rows, URL lines
        if _is_table_row(line) or _is_url_line(line):
            result.append(line)
            continue

        # Determine indent for wrapped continuation lines
        if _is_list_item_start(line):
            subsequent_indent = _list_continuation_indent(line)
        else:
            subsequent_indent = _detect_indent(line)

        wrapped = textwrap.fill(
            line,
            width=MAX_LINE_LENGTH,
            initial_indent="",
            subsequent_indent=subsequent_indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
        result.extend(wrapped.split("\n"))

    return result


def _is_heading(line: str) -> bool:
    return bool(re.match(r"^#{1,6}\s", line))


def _is_blank(line: str) -> bool:
    return line.strip() == ""


def _is_frontmatter_fence(line: str) -> bool:
    return line.strip() == "---"


def _is_list_continuation(line: str, list_indent_depth: int) -> bool:
    """True if line is a continuation of a list item (indented content, not a new item)."""
    if _is_blank(line) or _is_list_item_start(line):
        return False
    indent = len(_detect_indent(line))
    return indent >= list_indent_depth


def fix_heading_and_list_spacing(lines: list[str]) -> list[str]:
    """Rules 3-5: Fix blank-line spacing around headings and lists."""
    if not lines:
        return lines

    # Skip YAML frontmatter
    start = 0
    if lines and _is_frontmatter_fence(lines[0]):
        for j in range(1, len(lines)):
            if _is_frontmatter_fence(lines[j]):
                start = j + 1
                break

    result = list(lines[:start])

    in_code_fence = False
    in_list = False
    list_indent_depth = 0

    for i in range(start, len(lines)):
        line = lines[i]

        if re.match(CODE_FENCE_PATTERN, line):
            in_code_fence = not in_code_fence
            result.append(line)
            continue

        if in_code_fence:
            result.append(line)
            continue

        is_item = _is_list_item_start(line)
        is_continuation = in_list and _is_list_continuation(line, list_indent_depth)

        # Determine if we're entering, continuing, or leaving a list
        if is_item:
            if not in_list:
                # Rule 4: blank line before the start of a new list
                if result and not _is_blank(result[-1]) and not _is_heading(result[-1]):
                    result.append("")
                in_list = True
            list_indent_depth = len(_list_continuation_indent(line))
        elif is_continuation:
            # still inside the list
            pass
        elif _is_blank(line):
            # blank lines don't end a list by themselves
            pass
        else:
            if in_list:
                # Rule 5: blank line after the end of a list
                if result and not _is_blank(result[-1]):
                    result.append("")
                in_list = False

        # Rule 3: heading must be followed by exactly one blank line
        if result and _is_heading(result[-1]):
            if not _is_blank(line):
                result.append("")
            else:
                trailing_blanks = 0
                for prev_line in reversed(result):
                    if _is_blank(prev_line):
                        trailing_blanks += 1
                    else:
                        break
                if trailing_blanks >= 1:
                    continue

        result.append(line)

    return result


def format_content(text: str) -> str:
    """Apply all formatting rules to markdown content."""
    text = fix_smart_quotes(text)

    # Normalize line endings and split
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # Remove trailing whitespace on each line
    lines = [line.rstrip() for line in text.split("\n")]

    lines = wrap_long_lines(lines)
    lines = fix_heading_and_list_spacing(lines)

    # Ensure file ends with exactly one newline
    while lines and lines[-1] == "":
        lines.pop()

    return "\n".join(lines) + "\n"


def process_file(path: Path, is_dry_run: bool = False) -> bool:
    """Process a single file. Returns True if changes were made."""
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
            for md_file in sorted(path.rglob("*.md")):
                relative_path = md_file.relative_to(REPO_ROOT).as_posix()
                if not _is_excluded(relative_path):
                    files.append(md_file.resolve())
    return files


def _parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
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
