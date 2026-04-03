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
_CODE_FENCE_RE = re.compile(r"^\s*(`{3,}|~{3,})")
_HEADING_RE = re.compile(r"^#{1,6}\s")
_URL_RE = re.compile(r"https?://\S+")

EXCLUDE_PATTERNS = [
    "sandbox/",
    "tmp/",
    ".git/"
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


_SMART_QUOTE_TABLE = str.maketrans(SMART_QUOTES)
_BULLETED_ITEM_RE = re.compile(r"^(\s*[-*+] )")
_NUMBERED_ITEM_RE = re.compile(r"^(\s*\d+[.)]\s)")


def _check_code_fence(line: str, current_fence: str | None) -> str | None:
    """Track code fence state using matching markers.

    Returns the updated fence marker: a non-None string when inside a fenced
    block, or None when outside.  A closing fence must use the same character
    (backtick or tilde) and be *at least* as long as the opening fence.
    """
    m = _CODE_FENCE_RE.match(line)
    if not m:
        return current_fence

    marker = m.group(1)
    fence_char = marker[0]
    fence_len = len(marker)

    if current_fence is None:
        # Opening a new fenced block – remember the marker.
        return marker
    else:
        # Only close if the character matches and length is >= the opener.
        open_char = current_fence[0]
        open_len = len(current_fence)
        if fence_char == open_char and fence_len >= open_len:
            return None
        # Not a valid close – still inside the block.
        return current_fence


def fix_smart_quotes(text: str) -> str:
    """Rule 1: Replace smart/curly quotes with ASCII equivalents."""
    return text.translate(_SMART_QUOTE_TABLE)


def _is_table_row(line: str) -> bool:
    stripped = line.strip()
    return stripped.startswith("|") and stripped.endswith("|")


def _is_url_line(line: str) -> bool:
    """True if the line is long only because it contains a URL."""
    urls = _URL_RE.findall(line)
    if not urls:
        return False
    # If removing the longest URL brings the line under the limit, it's a URL line.
    longest_url = max(urls, key=len)
    without_url = line.replace(longest_url, "", 1)
    return len(without_url) <= MAX_LINE_LENGTH


def _detect_indent(line: str) -> str:
    """Return the leading whitespace of a line."""
    return line[:len(line) - len(line.lstrip())]


def _match_list_item(line: str):
    return _BULLETED_ITEM_RE.match(line) or _NUMBERED_ITEM_RE.match(line)


def _is_list_item_start(line: str) -> bool:
    """True if this line starts a list item (numbered or bulleted)."""
    return bool(_match_list_item(line))


def _list_continuation_indent(line: str) -> str:
    """Return the indent for continuation lines of a list item."""
    match = _match_list_item(line)
    if match:
        return " " * len(match.group(1))
    return _detect_indent(line)


def _should_skip_wrapping(line: str) -> bool:
    """True if this line should not be wrapped (table row or URL line)."""
    return _is_table_row(line) or _is_url_line(line)


def _wrap_single_line(line: str) -> list[str]:
    """Wrap a single long non-code line, returning a list of wrapped lines."""
    if _is_list_item_start(line):
        subsequent_indent = _list_continuation_indent(line)
    else:
        subsequent_indent = _detect_indent(line)

    initial_indent = _detect_indent(line)

    wrapped = textwrap.fill(
        line,
        width=MAX_LINE_LENGTH,
        initial_indent=initial_indent,
        subsequent_indent=subsequent_indent,
        break_long_words=False,
        break_on_hyphens=False,
    )
    return wrapped.split("\n")


def wrap_long_lines(lines: list[str]) -> list[str]:
    """Rule 2: Wrap lines exceeding 120 characters."""
    result = []
    code_fence: str | None = None
    for line in lines:
        code_fence = _check_code_fence(line, code_fence)
        in_code = code_fence is not None and not _CODE_FENCE_RE.match(line)

        if _CODE_FENCE_RE.match(line) or in_code or len(line) <= MAX_LINE_LENGTH:
            result.append(line)
        elif _should_skip_wrapping(line):
            result.append(line)
        else:
            result.extend(_wrap_single_line(line))

    return result


def _is_heading(line: str) -> bool:
    return bool(_HEADING_RE.match(line))


def _is_blank(line: str) -> bool:
    return not line.strip()


def _is_frontmatter_fence(line: str) -> bool:
    return line.strip() == "---"


def _ensure_blank_line(result: list[str]) -> None:
    if result and not _is_blank(result[-1]):
        result.append("")


def _collapse_trailing_blanks(result: list[str]) -> None:
    """Collapse consecutive trailing blank lines in result down to exactly one."""
    while len(result) >= 2 and _is_blank(result[-1]) and _is_blank(result[-2]):
        result.pop()


def _is_list_continuation(line: str, list_indent_depth: int) -> bool:
    """True if line is a continuation of a list item (indented content, not a new item)."""
    if _is_blank(line) or _is_list_item_start(line):
        return False
    indent = len(_detect_indent(line))
    return indent >= list_indent_depth


def _skip_frontmatter(lines: list[str]) -> int:
    """Return the index of the first line after YAML frontmatter, or 0."""
    if lines and _is_frontmatter_fence(lines[0]):
        for j in range(1, len(lines)):
            if _is_frontmatter_fence(lines[j]):
                return j + 1
    return 0


def _update_list_state(line: str, in_list: bool, list_indent_depth: int,
                       result: list[str]) -> tuple[bool, int]:
    """Handle list enter/exit logic, returning updated (in_list, list_indent_depth)."""
    is_item = _is_list_item_start(line)
    is_continuation = in_list and _is_list_continuation(line, list_indent_depth)

    if is_item:
        if not in_list:
            if result and not _is_heading(result[-1]):
                _ensure_blank_line(result)
                _collapse_trailing_blanks(result)
            in_list = True
        list_indent_depth = len(_list_continuation_indent(line))
    elif not is_continuation and not _is_blank(line):
        if in_list:
            _ensure_blank_line(result)
            _collapse_trailing_blanks(result)
            in_list = False

    return in_list, list_indent_depth


def fix_heading_and_list_spacing(lines: list[str]) -> list[str]:
    """Rules 3-5: Fix blank-line spacing around headings and lists."""
    if not lines:
        return lines

    start = _skip_frontmatter(lines)
    result = list(lines[:start])

    code_fence: str | None = None
    in_list = False
    list_indent_depth = 0

    for i in range(start, len(lines)):
        line = lines[i]

        code_fence = _check_code_fence(line, code_fence)
        in_code = code_fence is not None and not _CODE_FENCE_RE.match(line)

        if _CODE_FENCE_RE.match(line) or in_code:
            result.append(line)
            continue

        # Check heading-blank-line rule *before* list-state update mutates result
        if result and _is_heading(result[-1]) and not _is_blank(line):
            if not (result and _is_blank(result[-1])):
                result.append("")
                _collapse_trailing_blanks(result)

        in_list, list_indent_depth = _update_list_state(
            line, in_list, list_indent_depth, result)

        result.append(line)

    return result


def format_content(text: str) -> str:
    """Apply all formatting rules to markdown content."""
    text = fix_smart_quotes(text)

    lines = [line.rstrip() for line in text.splitlines()]

    lines = wrap_long_lines(lines)
    lines = fix_heading_and_list_spacing(lines)

    # Ensure file ends with exactly one newline
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
    except Exception as exc:
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