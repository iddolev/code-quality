"""Rule 2: Wrap lines longer than 120 characters.

Exceptions: table rows, lines long only because of a URL, and code blocks.
"""

from __future__ import annotations

import re
import textwrap

from scripts.format_markdown.markdown_formatter import MarkdownFormatter

MAX_LINE_LENGTH = 120
_URL_RE = re.compile(r"https?://\S+")

# Patterns for inline Markdown constructs that should not be split across lines.
_INLINE_CONSTRUCTS_RE = re.compile(
    r"!\[[^\]]*\]\([^)]*\)"   # images  ![alt](url)
    r"|\[[^\]]*\]\([^)]*\)"   # links   [text](url)
    r"|\[[^\]]*\]\[[^\]]*\]"  # ref links [text][ref]
    r"|`[^`]+`"                # inline code `code`
)

_PLACEHOLDER_CHAR = "\x00"


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

        output = "\n".join(result)
        if text.endswith("\n"):
            output += "\n"
        return output

    # -- private helpers -------------------------------------------------------

    @staticmethod
    def _is_table_row(line: str) -> bool:
        """Return True if the line appears to be a Markdown table row."""
        stripped = line.strip()
        return stripped.startswith("|") and stripped.endswith("|")

    @staticmethod
    def _is_url_line(line: str) -> bool:
        """True if the line is long only because it contains a URL."""
        urls = _URL_RE.findall(line)
        if not urls:
            return False
        without_urls = _URL_RE.sub('', line)
        return len(without_urls) <= MAX_LINE_LENGTH

    @classmethod
    def _should_skip_wrapping(cls, line: str) -> bool:
        """Return True if the line is a table row or is long only due to a URL."""
        return cls._is_table_row(line) or cls._is_url_line(line)

    @staticmethod
    def _protect_inline_constructs(text: str) -> tuple[str, list[str]]:
        """Replace spaces inside inline Markdown constructs with placeholders.

        Returns the modified text and a list of original matched spans so we
        can verify the round-trip (though restoration relies on the placeholder
        character, not on the list).
        """
        originals: list[str] = []

        def _replace_spaces(m: re.Match[str]) -> str:
            original = m.group(0)
            originals.append(original)
            return original.replace(" ", _PLACEHOLDER_CHAR)

        protected = _INLINE_CONSTRUCTS_RE.sub(_replace_spaces, text)
        return protected, originals

    @staticmethod
    def _restore_inline_constructs(text: str) -> str:
        """Restore placeholder characters back to spaces."""
        return text.replace(_PLACEHOLDER_CHAR, " ")

    def _wrap_single_line(self, line: str) -> list[str]:
        """Wrap a single long line respecting its indentation and list-item context.

        Returns a list of wrapped line strings.
        """
        initial_indent = self.detect_indent(line)
        is_list = self.is_list_item_start(line)
        subsequent_indent = (
            self.list_continuation_indent(line) if is_list else initial_indent
        )

        if is_list:
            marker_width = len(subsequent_indent) - len(initial_indent)
            stripped = line.lstrip()
            marker = stripped[:marker_width]
            content_after_marker = stripped[marker_width:]
            full_initial_indent = initial_indent + marker
        else:
            full_initial_indent = initial_indent
            content_after_marker = line.lstrip()

        # Protect inline constructs from being split by textwrap.
        protected, _ = self._protect_inline_constructs(content_after_marker)

        wrapped = textwrap.fill(protected,
                                width=MAX_LINE_LENGTH,
                                initial_indent=full_initial_indent,
                                subsequent_indent=subsequent_indent,
                                break_long_words=False,
                                break_on_hyphens=False)

        # Restore the protected spaces.
        wrapped = self._restore_inline_constructs(wrapped)
        return wrapped.split("\n")