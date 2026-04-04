"""Rule 2: Wrap lines longer than 120 characters.

Exceptions: table rows, lines long only because of a URL, and code blocks.
"""

from __future__ import annotations

import re
import textwrap

from scripts.format_markdown.markdown_formatter import MarkdownFormatter

MAX_LINE_LENGTH = 120
_URL_RE = re.compile(r"https?://\S+")


class WrapLongLines(MarkdownFormatter):
    """Wrap lines exceeding 120 characters."""

    def apply(self, text: str) -> str:
        lines = text.splitlines()
        result: list[str] = []
        code_fence: str | None = None

        for line in lines:
            code_fence = self.check_code_fence(line, code_fence)
            in_code = code_fence is not None and not self.is_code_fence_line(line)

            if self.is_code_fence_line(line) or in_code or len(line) <= MAX_LINE_LENGTH:
                result.append(line)
            elif self._should_skip_wrapping(line):
                result.append(line)
            else:
                result.extend(self._wrap_single_line(line))

        return "\n".join(result)

    # -- private helpers -------------------------------------------------------

    @staticmethod
    def _is_table_row(line: str) -> bool:
        stripped = line.strip()
        return stripped.startswith("|") and stripped.endswith("|")

    @staticmethod
    def _is_url_line(line: str) -> bool:
        """True if the line is long only because it contains a URL."""
        urls = _URL_RE.findall(line)
        if not urls:
            return False
        longest_url = max(urls, key=len)
        without_url = line.replace(longest_url, "", 1)
        return len(without_url) <= MAX_LINE_LENGTH

    @classmethod
    def _should_skip_wrapping(cls, line: str) -> bool:
        return cls._is_table_row(line) or cls._is_url_line(line)

    def _wrap_single_line(self, line: str) -> list[str]:
        if self.is_list_item_start(line):
            subsequent_indent = self.list_continuation_indent(line)
        else:
            subsequent_indent = self.detect_indent(line)

        initial_indent = self.detect_indent(line)

        wrapped = textwrap.fill(
            line,
            width=MAX_LINE_LENGTH,
            initial_indent=initial_indent,
            subsequent_indent=subsequent_indent,
            break_long_words=False,
            break_on_hyphens=False,
        )
        return wrapped.split("\n")
