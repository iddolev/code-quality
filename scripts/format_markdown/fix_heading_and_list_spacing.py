"""Rules 3-5: Ensure correct blank-line spacing around headings and lists.

3. Every heading is followed by exactly one blank line.
4. Every list is preceded by exactly one blank line.
5. Every list is followed by at least one blank line.
"""

from __future__ import annotations

import re

from scripts.format_markdown.markdown_formatter import MarkdownFormatter

_HEADING_RE = re.compile(r"^#{1,6}\s")


class FixHeadingAndListSpacing(MarkdownFormatter):
    """Fix blank-line spacing around headings and lists."""

    def apply(self, text: str) -> str:
        lines = text.splitlines()
        if not lines:
            return text

        start = self._skip_frontmatter(lines)
        result = list(lines[:start])

        code_fence: str | None = None
        in_list = False
        list_indent_depth = 0

        for i in range(start, len(lines)):
            line = lines[i]

            code_fence = self.check_code_fence(line, code_fence)
            in_code = code_fence is not None and not self.is_code_fence_line(line)

            if self.is_code_fence_line(line) or in_code:
                result.append(line)
                continue

            if result and self._is_heading(result[-1]) and not self.is_blank(line):
                if not (result and self.is_blank(result[-1])):
                    result.append("")
                    self._collapse_trailing_blanks(result)

            in_list, list_indent_depth = self._update_list_state(
                line, in_list, list_indent_depth, result)

            result.append(line)

        return "\n".join(result)

    # -- private helpers -------------------------------------------------------

    @staticmethod
    def _is_heading(line: str) -> bool:
        return bool(_HEADING_RE.match(line))

    @staticmethod
    def _is_frontmatter_fence(line: str) -> bool:
        return line.strip() == "---"

    @classmethod
    def _skip_frontmatter(cls, lines: list[str]) -> int:
        if lines and cls._is_frontmatter_fence(lines[0]):
            for j in range(1, len(lines)):
                if cls._is_frontmatter_fence(lines[j]):
                    return j + 1
        return 0

    @staticmethod
    def _ensure_blank_line(result: list[str]) -> None:
        if result and result[-1].strip():
            result.append("")

    @classmethod
    def _collapse_trailing_blanks(cls, result: list[str]) -> None:
        while len(result) >= 2 and not result[-1].strip() and not result[-2].strip():
            result.pop()

    def _is_list_continuation(self, line: str, list_indent_depth: int) -> bool:
        if self.is_blank(line) or self.is_list_item_start(line):
            return False
        indent = len(self.detect_indent(line))
        return indent >= list_indent_depth

    def _update_list_state(self, line: str, in_list: bool, list_indent_depth: int,
                           result: list[str]) -> tuple[bool, int]:
        is_item = self.is_list_item_start(line)
        is_continuation = in_list and self._is_list_continuation(line, list_indent_depth)

        if is_item:
            if not in_list:
                if result and not self._is_heading(result[-1]):
                    self._ensure_blank_line(result)
                    self._collapse_trailing_blanks(result)
                in_list = True
            list_indent_depth = len(self.list_continuation_indent(line))
        elif not is_continuation and not self.is_blank(line):
            if in_list:
                self._ensure_blank_line(result)
                self._collapse_trailing_blanks(result)
                in_list = False

        return in_list, list_indent_depth
